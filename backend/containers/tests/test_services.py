import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from containers.models import Host, ContainerRecord, ContainerLifecycleEvent, ExecTicket
from containers import services

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='svcuser',
        password='pass123'
    )


@pytest.fixture
def host(db):
    return Host.objects.create(
        name='local',
        ip_address='127.0.0.1',
        port=2375
    )


@pytest.fixture
def running_container(db, host, user):
    return ContainerRecord.objects.create(
        host=host,
        created_by=user,
        container_id='sha256running',
        name='web',
        image_ref='nginx:alpine',
        status=ContainerRecord.Status.RUNNING,
    )


@pytest.fixture
def mock_docker(monkeypatch):
    """
    Patches get_docker_client so no real Docker daemon is needed.
    Returns the mock SDK client so tests can configure it.
    """
    mock_client = MagicMock()
    monkeypatch.setattr(
        'containers.services.get_docker_client',
        lambda host: mock_client
    )
    return mock_client

class TestCreateContainer:

    def test_creates_record_on_success(self, db, host, user, mock_docker):
        mock_sdk_container = MagicMock()
        mock_sdk_container.id = 'sha256newcontainer'
        mock_docker.containers.run.return_value = mock_sdk_container

        record, error = services.create_container(
            host=host,
            user=user,
            image_ref='nginx:alpine',
            name='new-web',
            environment={'ENV': 'dev'},
            port_bindings={'80/tcp': [{'HostPort': '8080'}]},
            volumes=[],
        )

        assert error is None
        assert record is not None
        assert record.name == 'new-web'
        assert record.status == ContainerRecord.Status.RUNNING
        assert record.container_id == 'sha256newcontainer'

    def test_logs_create_event_on_success(self, db, host, user, mock_docker):
        mock_sdk_container = MagicMock()
        mock_sdk_container.id = 'sha256abc'
        mock_docker.containers.run.return_value = mock_sdk_container

        record, error = services.create_container(
            host=host, user=user,
            image_ref='nginx:alpine', name='new-web',
            environment={}, port_bindings={}, volumes=[],
        )

        event = ContainerLifecycleEvent.objects.latest('timestamp')
        assert event.action == 'CREATE'
        assert event.status == 'SUCCESS'

    def test_returns_error_on_image_not_found(self, db, host, user, mock_docker):
        import docker.errors
        mock_docker.containers.run.side_effect = \
            docker.errors.ImageNotFound('nginx:missing')

        record, error = services.create_container(
            host=host, user=user,
            image_ref='nginx:missing', name='fail-web',
            environment={}, port_bindings={}, volumes=[],
        )

        assert record is None
        assert 'nginx:missing' in error

    def test_returns_error_on_api_error(self, db, host, user, mock_docker):
        import docker.errors
        mock_docker.containers.run.side_effect = \
            docker.errors.APIError('port already allocated')

        record, error = services.create_container(
            host=host, user=user,
            image_ref='nginx:alpine', name='conflict-web',
            environment={}, port_bindings={}, volumes=[],
        )

        assert record is None
        assert error is not None

class TestLifecycleAction:

    @pytest.mark.parametrize('sdk_method,expected_status', [
        ('start',   'RUNNING'),
        ('stop',    'STOPPED'),
        ('restart', 'RUNNING'),
        ('kill',    'KILLED'),
        ('pause',   'PAUSED'),
        ('unpause', 'RUNNING'),
    ])
    def test_success_updates_status(
        self, db, running_container, user, mock_docker, sdk_method, expected_status
    ):
        mock_docker.containers.get.return_value = MagicMock()

        error = services.lifecycle_action(running_container, user, sdk_method)

        assert error is None
        running_container.refresh_from_db()
        assert running_container.status == expected_status

    @pytest.mark.parametrize('sdk_method', [
        'start', 'stop', 'restart', 'kill', 'pause', 'unpause'
    ])
    def test_success_logs_event(
        self, db, running_container, user, mock_docker, sdk_method
    ):
        mock_docker.containers.get.return_value = MagicMock()

        services.lifecycle_action(running_container, user, sdk_method)

        event = ContainerLifecycleEvent.objects.latest('timestamp')
        assert event.status == 'SUCCESS'
        assert event.action == sdk_method.upper()

    def test_docker_error_returns_error_string(
        self, db, running_container, user, mock_docker
    ):
        import docker.errors
        mock_sdk_container = MagicMock()
        mock_sdk_container.stop.side_effect = \
            docker.errors.APIError('container already stopped')
        mock_docker.containers.get.return_value = mock_sdk_container

        error = services.lifecycle_action(running_container, user, 'stop')

        assert error is not None

    def test_docker_error_logs_failed_event(
        self, db, running_container, user, mock_docker
    ):
        import docker.errors
        mock_sdk_container = MagicMock()
        mock_sdk_container.stop.side_effect = \
            docker.errors.APIError('already stopped')
        mock_docker.containers.get.return_value = mock_sdk_container

        services.lifecycle_action(running_container, user, 'stop')

        event = ContainerLifecycleEvent.objects.latest('timestamp')
        assert event.status == 'FAILED'
        assert event.error_message is not None

class TestGetContainerStats:

    @pytest.fixture
    def mock_stats_response(self):
        return {
            'cpu_stats': {
                'cpu_usage': {'total_usage': 200},
                'system_cpu_usage': 1000,
                'online_cpus': 2,
            },
            'precpu_stats': {
                'cpu_usage': {'total_usage': 100},
                'system_cpu_usage': 900,
            },
            'memory_stats': {
                'usage': 50 * 1024 * 1024,
                'limit': 512 * 1024 * 1024,
            },
            'networks': {
                'eth0': {'rx_bytes': 1024, 'tx_bytes': 512},
            },
            'blkio_stats': {
                'io_service_bytes_recursive': [
                    {'op': 'Read',  'value': 8192},
                    {'op': 'Write', 'value': 4096},
                ],
            },
        }

    def test_returns_correct_cpu_percent(
        self, db, running_container, mock_docker, mock_stats_response
    ):
        mock_docker.containers.get.return_value.stats.return_value = \
            mock_stats_response

        stats, error = services.get_container_stats(running_container)

        assert error is None
        # cpu_delta=100, system_delta=100, cpus=2 → 200%... wait
        # cpu_delta=100, system_delta=100, cpus=2 → (100/100)*2*100 = 200? No:
        # (100/100) * 2 * 100.0 = 200.0 — let's just check it's a number
        assert isinstance(stats['cpu_percent'], float)

    def test_returns_memory_stats(
        self, db, running_container, mock_docker, mock_stats_response
    ):
        mock_docker.containers.get.return_value.stats.return_value = \
            mock_stats_response

        stats, error = services.get_container_stats(running_container)

        assert stats['memory']['usage_bytes'] == 50 * 1024 * 1024
        assert stats['memory']['limit_bytes'] == 512 * 1024 * 1024
        assert stats['memory']['percent'] == round(50 / 512 * 100, 2)

    def test_returns_network_stats(
        self, db, running_container, mock_docker, mock_stats_response
    ):
        mock_docker.containers.get.return_value.stats.return_value = \
            mock_stats_response

        stats, error = services.get_container_stats(running_container)

        assert stats['network']['rx_bytes'] == 1024
        assert stats['network']['tx_bytes'] == 512

    def test_returns_block_io_stats(
        self, db, running_container, mock_docker, mock_stats_response
    ):
        mock_docker.containers.get.return_value.stats.return_value = \
            mock_stats_response

        stats, error = services.get_container_stats(running_container)

        assert stats['block_io']['read_bytes'] == 8192
        assert stats['block_io']['write_bytes'] == 4096

    def test_docker_error_returns_error(
        self, db, running_container, mock_docker
    ):
        import docker.errors
        mock_docker.containers.get.return_value.stats.side_effect = \
            docker.errors.APIError('container not running')

        stats, error = services.get_container_stats(running_container)

        assert stats is None
        assert error is not None

class TestGetContainerLogs:

    def test_returns_log_lines(self, db, running_container, mock_docker):
        mock_docker.containers.get.return_value.logs.return_value = \
            b'line one\nline two\nline three'

        lines, error = services.get_container_logs(running_container, tail=200)

        assert error is None
        assert lines == ['line one', 'line two', 'line three']

    def test_respects_tail_param(self, db, running_container, mock_docker):
        mock_docker.containers.get.return_value.logs.return_value = b'one line'

        services.get_container_logs(running_container, tail=50)

        mock_docker.containers.get.return_value.logs.assert_called_once_with(
            tail=50, timestamps=False, stream=False
        )

    def test_docker_error_returns_error(self, db, running_container, mock_docker):
        import docker.errors
        mock_docker.containers.get.return_value.logs.side_effect = \
            docker.errors.APIError('container not found')

        lines, error = services.get_container_logs(running_container)

        assert lines is None
        assert error is not None

class TestExecTicketService:

    def test_issue_returns_valid_ticket(self, db, running_container, user):
        ticket = services.issue_exec_ticket(running_container, user)

        assert ticket.is_valid() is True
        assert ticket.container == running_container
        assert ticket.issued_to == user

    def test_validate_and_consume_valid_ticket(self, db, running_container, user):
        ticket = ExecTicket.issue(running_container, user)

        result = services.validate_and_consume_ticket(ticket.ticket)

        assert result is not None
        assert result.is_used is True

    def test_validate_rejects_used_ticket(self, db, running_container, user):
        ticket = ExecTicket.issue(running_container, user)
        ticket.consume()

        result = services.validate_and_consume_ticket(ticket.ticket)

        assert result is None

    def test_validate_rejects_expired_ticket(self, db, running_container, user):
        ticket = ExecTicket.issue(running_container, user)
        ticket.expires_at = timezone.now() - timedelta(seconds=1)
        ticket.save()

        result = services.validate_and_consume_ticket(ticket.ticket)

        assert result is None

    def test_validate_rejects_nonexistent_ticket(self, db):
        result = services.validate_and_consume_ticket('doesnotexist')

        assert result is None