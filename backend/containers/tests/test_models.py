import pytest
from django.utils import timezone
from datetime import timedelta
from containers.models import Host, ContainerRecord, ContainerLifecycleEvent, ExecTicket
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser',
        password='testpass123'
    )


@pytest.fixture
def host(db):
    return Host.objects.create(
        name='local-docker',
        ip_address='127.0.0.1',
        port=2375
    )


@pytest.fixture
def container_record(db, host, user):
    return ContainerRecord.objects.create(
        host=host,
        created_by=user,
        container_id='abc123def456abc123def456',
        name='test-nginx',
        image_ref='nginx:alpine',
        status=ContainerRecord.Status.RUNNING,
        port_bindings={'80/tcp': [{'HostPort': '8080'}]},
        environment={'ENV': 'dev'},
        volumes=[],
    )

class TestHost:

    def test_host_created(self, host):
        assert host.name == 'local-docker'
        assert host.ip_address == '127.0.0.1'
        assert host.port == 2375

    def test_host_str(self, host):
        assert str(host) == 'local-docker (127.0.0.1:2375)'

class TestContainerRecord:

    def test_created_successfully(self, container_record):
        assert container_record.name == 'test-nginx'
        assert container_record.image_ref == 'nginx:alpine'
        assert container_record.status == 'RUNNING'

    def test_str(self, container_record):
        assert str(container_record) == 'test-nginx [RUNNING]'

    def test_uuid_primary_key(self, container_record):
        assert container_record.id is not None
        assert len(str(container_record.id)) == 36  # UUID format

    def test_default_port_bindings(self, db, host, user):
        record = ContainerRecord.objects.create(
            host=host,
            created_by=user,
            container_id='xyz999',
            name='bare-container',
            image_ref='alpine:latest',
        )
        assert record.port_bindings == {}
        assert record.environment == {}
        assert record.volumes == []

    def test_all_status_transitions(self, container_record):
        for s in ContainerRecord.Status:
            container_record.status = s
            container_record.save()
            container_record.refresh_from_db()
            assert container_record.status == s.value

    def test_ordering_newest_first(self, db, host, user):
        r1 = ContainerRecord.objects.create(
            host=host, created_by=user,
            container_id='first111', name='first',
            image_ref='nginx:alpine',
        )
        r2 = ContainerRecord.objects.create(
            host=host, created_by=user,
            container_id='second222', name='second',
            image_ref='nginx:alpine',
        )
        records = list(ContainerRecord.objects.all())
        assert records[0].name == 'second'  # newest first
        assert records[1].name == 'first'

class TestContainerLifecycleEvent:

    def test_success_event(self, db, container_record, user):
        event = ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action=ContainerLifecycleEvent.Action.START,
            status=ContainerLifecycleEvent.Status.SUCCESS,
        )
        assert event.action == 'START'
        assert event.status == 'SUCCESS'
        assert event.error_message is None

    def test_failed_event_stores_error(self, db, container_record, user):
        event = ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action=ContainerLifecycleEvent.Action.STOP,
            status=ContainerLifecycleEvent.Status.FAILED,
            error_message='Container already stopped',
        )
        assert event.status == 'FAILED'
        assert event.error_message == 'Container already stopped'

    def test_all_actions_are_valid(self, db, container_record, user):
        for action in ContainerLifecycleEvent.Action:
            event = ContainerLifecycleEvent.objects.create(
                container=container_record,
                triggered_by=user,
                action=action,
                status=ContainerLifecycleEvent.Status.SUCCESS,
            )
            assert event.action == action.value

    def test_event_linked_to_container(self, db, container_record, user):
        ContainerLifecycleEvent.objects.create(
            container=container_record,
            triggered_by=user,
            action='START',
            status='SUCCESS',
        )
        assert container_record.events.count() == 1

class TestExecTicket:

    def test_issue_creates_ticket(self, db, container_record, user):
        ticket = ExecTicket.issue(container_record, user)
        assert ticket.ticket is not None
        assert len(ticket.ticket) == 64
        assert ticket.is_used is False
        assert ticket.expires_at > timezone.now()

    def test_fresh_ticket_is_valid(self, db, container_record, user):
        ticket = ExecTicket.issue(container_record, user)
        assert ticket.is_valid() is True

    def test_consumed_ticket_is_invalid(self, db, container_record, user):
        ticket = ExecTicket.issue(container_record, user)