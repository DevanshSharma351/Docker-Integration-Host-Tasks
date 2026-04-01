import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock
from django.contrib.auth import get_user_model

from containers.models import Host, ContainerRecord, ContainerLifecycleEvent, ExecTicket

User = get_user_model()

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='viewuser',
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
def container_record(db, host, user):
    return ContainerRecord.objects.create(
        host=host,
        created_by=user,
        container_id='sha256viewtest',
        name='view-test-nginx',
        image_ref='nginx:alpine',
        status=ContainerRecord.Status.RUNNING,
    )


@pytest.fixture
def mock_docker(monkeypatch):
    """Patches get_docker_client at the services layer."""
    mock_client = MagicMock()
    monkeypatch.setattr(
        'containers.services.get_docker_client',
        lambda host: mock_client
    )
    return mock_client

class TestContainerListCreateView:

    def test_list_returns_200(self, client, db, host, container_record, mock_docker):
        sdk_mock = MagicMock()
        sdk_mock.attrs = {'State': {'Status': 'running'}}
        mock_docker.containers.get.return_value = sdk_mock
        response = client.get(f'/api/hosts/{host.id}/containers/')
        assert response.status_code == 200

    def test_list_returns_correct_count(
        self, client, db, host, container_record, mock_docker
    ):
        sdk_mock = MagicMock()
        sdk_mock.attrs = {'State': {'Status': 'running'}}
        mock_docker.containers.get.return_value = sdk_mock
        response = client.get(f'/api/hosts/{host.id}/containers/')
        assert response.data['count'] == 1
        assert response.data['results'][0]['name'] == 'view-test-nginx'

    def test_list_filters_by_status(
        self, client, db, host, container_record, mock_docker
    ):
        sdk_mock = MagicMock()
        sdk_mock.attrs = {'State': {'Status': 'running'}}
        mock_docker.containers.get.return_value = sdk_mock
        response = client.get(
            f'/api/hosts/{host.id}/containers/?status=running'
        )
        assert response.data['count'] == 1

        response = client.get(
            f'/api/hosts/{host.id}/containers/?status=stopped'
        )
        assert response.data['count'] == 0

    def test_list_returns_404_for_unknown_host(self, client, db):
        response = client.get('/api/hosts/99999/containers/')
        assert response.status_code == 404

    def test_create_returns_201(
        self, client, db, host, user, mock_docker
    ):
        mock_sdk_container = MagicMock()
        mock_sdk_container.id = 'sha256newone'
        mock_docker.containers.run.return_value = mock_sdk_container

        response = client.post(
            f'/api/hosts/{host.id}/containers/',
            {
                'image_ref': 'nginx:alpine',
                'name':      'brand-new',
            },
            format='json'
        )
        assert response.status_code == 201
        assert response.data['name'] == 'brand-new'
        assert response.data['status'] == 'RUNNING'

    def test_create_returns_400_on_missing_fields(
        self, client, db, host
    ):
        response = client.post(
            f'/api/hosts/{host.id}/containers/',
            {'name': 'missing-image'},
            format='json'
        )
        assert response.status_code == 400
        assert 'image_ref' in response.data

    def test_create_returns_400_on_docker_error(
        self, client, db, host, mock_docker
    ):
        import docker.errors
        mock_docker.containers.run.side_effect = \
            docker.errors.APIError('port already in use')

        response = client.post(
            f'/api/hosts/{host.id}/containers/',
            {'image_ref': 'nginx:alpine', 'name': 'fail-web'},
            format='json'
        )
        assert response.status_code == 400
        assert 'error' in response.data

class TestContainerDetailView:

    def test_get_returns_200(
        self, client, db, host, container_record
    ):
        response = client.get(
            f'/api/hosts/{host.id}/containers/{container_record.id}/'
        )
        assert response.status_code == 200
        assert response.data['name'] == 'view-test-nginx'

    def test_get_returns_404_for_unknown_container(
        self, client, db, host
    ):
        import uuid
        response = client.get(
            f'/api/hosts/{host.id}/containers/{uuid.uuid4()}/'
        )
        assert response.status_code == 404

    def test_delete_returns_200(
        self, client, db, host, container_record, mock_docker
    ):
        mock_docker.containers.get.return_value = MagicMock()

        response = client.delete(
            f'/api/hosts/{host.id}/containers/{container_record.id}/'
        )
        assert response.status_code == 200
        container_record.refresh_from_db()
        assert container_record.status == 'REMOVED'

    def test_delete_returns_400_on_docker_error(
        self, client, db, host, container_record, mock_docker
    ):
        import docker.errors
        mock_docker.containers.get.return_value.remove.side_effect = \
            docker.errors.APIError('removal failed')

        response = client.delete(
            f'/api/hosts/{host.id}/containers/{container_record.id}/'
        )
        assert response.status_code == 400


class TestLifecycleViews:

    @pytest.mark.parametrize('action,expected_status', [
        ('start',   'RUNNING'),
        ('stop',    'STOPPED'),
        ('restart', 'RUNNING'),
        ('kill',    'KILLED'),
        ('pause',   'PAUSED'),
        ('unpause', 'RUNNING'),
    ])
    def test_action_returns_200(
        self, client, db, host, container_record,
        mock_docker, action, expected_status
    ):
        mock_docker.containers.get.return_value = MagicMock()

        response = client.post(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/{action}/'
        )
        assert response.status_code == 200
        assert response.data['action'] == action.upper()
        assert response.data['status'] == 'SUCCESS'

    @pytest.mark.parametrize('action', [
        'start', 'stop', 'restart', 'kill', 'pause', 'unpause'
    ])
    def test_action_returns_409_on_docker_error(
        self, client, db, host, container_record, mock_docker, action
    ):
        import docker.errors
        sdk_mock = MagicMock()
        getattr(sdk_mock, action).side_effect = \
            docker.errors.APIError('operation failed')
        mock_docker.containers.get.return_value = sdk_mock

        response = client.post(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/{action}/'
        )
        assert response.status_code == 409
        assert response.data['status'] == 'FAILED'

    @pytest.mark.parametrize('action', [
        'start', 'stop', 'restart', 'kill', 'pause', 'unpause'
    ])
    def test_action_writes_lifecycle_event(
        self, client, db, host, container_record, mock_docker, action
    ):
        mock_docker.containers.get.return_value = MagicMock()

        client.post(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/{action}/'
        )
        event = ContainerLifecycleEvent.objects.latest('timestamp')
        assert event.action == action.upper()
        assert event.status == 'SUCCESS'

class TestStatsView:

    @pytest.fixture
    def mock_stats(self):
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

    def test_stats_returns_200(
        self, client, db, host, container_record,
        mock_docker, mock_stats
    ):
        mock_docker.containers.get.return_value.stats.return_value = \
            mock_stats

        response = client.get(
            f'/api/hosts/{host.id}/containers/{container_record.id}/stats/'
        )
        assert response.status_code == 200
        assert 'cpu_percent' in response.data
        assert 'memory' in response.data
        assert 'network' in response.data
        assert 'block_io' in response.data

    def test_stats_returns_400_on_docker_error(
        self, client, db, host, container_record, mock_docker
    ):
        import docker.errors
        mock_docker.containers.get.return_value.stats.side_effect = \
            docker.errors.APIError('container not running')

        response = client.get(
            f'/api/hosts/{host.id}/containers/{container_record.id}/stats/'
        )
        assert response.status_code == 400

class TestLogsView:

    def test_logs_returns_200(
        self, client, db, host, container_record, mock_docker
    ):
        mock_docker.containers.get.return_value.logs.return_value = \
            b'line one\nline two\nline three'

        response = client.get(
            f'/api/hosts/{host.id}/containers/{container_record.id}/logs/'
        )
        assert response.status_code == 200
        assert response.data['logs'] == ['line one', 'line two', 'line three']
        assert response.data['tail'] == 200

    def test_logs_respects_tail_param(
        self, client, db, host, container_record, mock_docker
    ):
        mock_docker.containers.get.return_value.logs.return_value = b'one'

        client.get(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/logs/?tail=50'
        )
        mock_docker.containers.get.return_value.logs.assert_called_once_with(
            tail=50, timestamps=False, stream=False
        )

    def test_log_stream_ticket_returns_ticket(
        self, client, db, host, container_record
    ):
        response = client.post(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/logs/stream/'
        )
        assert response.status_code == 200
        assert 'ticket' in response.data
        assert 'ws_url' in response.data
        assert response.data['expires_in_seconds'] == 30

class TestExecTicketView:

    def test_returns_ticket_and_ws_url(
        self, client, db, host, container_record
    ):
        response = client.post(
            f'/api/hosts/{host.id}/containers/{container_record.id}/exec/'
        )
        assert response.status_code == 200
        assert 'ticket' in response.data
        assert 'ws_url' in response.data
        assert len(response.data['ticket']) == 64
        assert response.data['expires_in_seconds'] == 30

    def test_ticket_is_stored_in_db(
        self, client, db, host, container_record
    ):
        response = client.post(
            f'/api/hosts/{host.id}/containers/{container_record.id}/exec/'
        )
        ticket_value = response.data['ticket']
        assert ExecTicket.objects.filter(ticket=ticket_value).exists()

    def test_each_request_generates_unique_ticket(
        self, client, db, host, container_record
    ):
        r1 = client.post(
            f'/api/hosts/{host.id}/containers/{container_record.id}/exec/'
        )
        r2 = client.post(
            f'/api/hosts/{host.id}/containers/{container_record.id}/exec/'
        )
        assert r1.data['ticket'] != r2.data['ticket']

class TestEventListView:

    def test_returns_200_with_events(
        self, client, db, host, container_record, user
    ):
        ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action='START',
            status='SUCCESS',
        )
        response = client.get(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/events/'
        )
        assert response.status_code == 200
        assert response.data['count'] == 1

    def test_filters_by_action(
        self, client, db, host, container_record, user
    ):
        ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action='START',
            status='SUCCESS',
        )
        ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action='STOP',
            status='SUCCESS',
        )
        response = client.get(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/events/?action=START'
        )
        assert response.data['count'] == 1
        assert response.data['results'][0]['action'] == 'START'

    def test_filters_by_status(
        self, client, db, host, container_record, user
    ):
        ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action='STOP',
            status='FAILED',
            error_message='already stopped',
        )
        response = client.get(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/events/?status=FAILED'
        )
        assert response.data['count'] == 1
        assert response.data['results'][0]['status'] == 'FAILED'

    def test_pagination(
        self, client, db, host, container_record, user
    ):
        for i in range(5):
            ContainerLifecycleEvent.objects.create(
                container=container_record,
                triggered_by=user,
                action='START',
                status='SUCCESS',
            )
        response = client.get(
            f'/api/hosts/{host.id}/containers/'
            f'{container_record.id}/events/?page=1&page_size=2'
        )
        assert response.data['count'] == 5
        assert len(response.data['results']) == 2