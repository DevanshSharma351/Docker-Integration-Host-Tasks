import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path

from containers.models import Host, ContainerRecord, ExecTicket
from containers.consumers.exec_consumer import ExecConsumer
from containers.consumers.log_consumer import LogConsumer

User = get_user_model()


# ── TEST APP ──────────────────────────────────────────────────────────────

application = URLRouter([
    re_path(
        r'^ws/hosts/(?P<host_id>\d+)/containers/(?P<container_id>[^/]+)/exec/$',
        ExecConsumer.as_asgi()
    ),
    re_path(
        r'^ws/hosts/(?P<host_id>\d+)/containers/(?P<container_id>[^/]+)/logs/$',
        LogConsumer.as_asgi()
    ),
])


# ── ASYNC DB HELPERS ──────────────────────────────────────────────────────
# All DB calls inside async tests must go through sync_to_async.
# Never call ORM methods directly in async def test bodies.

create_user = sync_to_async(
    lambda: User.objects.get_or_create(
        username='ws_test_user',
        defaults={'is_active': True}
    )
)

create_host = sync_to_async(
    lambda: Host.objects.create(
        name='local', ip_address='127.0.0.1', port=2375
    )
)


@sync_to_async
def create_container(host, user):
    return ContainerRecord.objects.create(
        host=host,
        created_by=user,
        container_id='sha256wsconsumer',
        name='ws-test-nginx',
        image_ref='nginx:alpine',
        status=ContainerRecord.Status.RUNNING,
    )


@sync_to_async
def issue_ticket(container, user):
    return ExecTicket.issue(container, user)


@sync_to_async
def refresh_ticket(ticket):
    ticket.refresh_from_db()
    return ticket


@sync_to_async
def get_latest_event(action):
    from containers.models import ContainerLifecycleEvent
    return ContainerLifecycleEvent.objects.filter(
        action=action
    ).latest('timestamp')


# ── FIXTURES ──────────────────────────────────────────────────────────────

@pytest.fixture
async def user(db):
    u, _ = await create_user()
    return u


@pytest.fixture
async def host(db):
    return await create_host()


@pytest.fixture
async def container_record(db, host, user):
    return await create_container(host, user)


@pytest.fixture
async def valid_ticket(db, container_record, user):
    return await issue_ticket(container_record, user)


# ── EXEC CONSUMER TESTS ───────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestExecConsumer:

    async def test_connect_with_valid_ticket(self, valid_ticket):
        """Valid ticket → connection accepted."""
        communicator = WebsocketCommunicator(
            application,
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        connected, code = await communicator.connect()
        assert connected is True

        response = await communicator.receive_json_from()
        assert response['type'] == 'connected'

        await communicator.disconnect()

    async def test_connect_with_invalid_ticket(self, db):
        """Invalid ticket → connection rejected."""
        communicator = WebsocketCommunicator(
            application,
            '/ws/hosts/1/containers/some-id/exec/'
            '?ticket=completelyfaketicket'
        )
        connected, code = await communicator.connect()
        assert connected is False
        assert code == 4001

    async def test_connect_with_no_ticket(self, db):
        """Missing ticket → connection rejected."""
        communicator = WebsocketCommunicator(
            application,
            '/ws/hosts/1/containers/some-id/exec/'
        )
        connected, code = await communicator.connect()
        assert connected is False
        assert code == 4001

    async def test_connect_consumes_ticket(self, valid_ticket):
        """Ticket is marked used after connect."""
        communicator = WebsocketCommunicator(
            application,
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        await communicator.connect()
        await communicator.receive_json_from()

        refreshed = await refresh_ticket(valid_ticket)
        assert refreshed.is_used is True

        await communicator.disconnect()

    async def test_ticket_cannot_be_reused(self, valid_ticket):
        """Used ticket → second connection rejected."""
        url = (
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        c1 = WebsocketCommunicator(application, url)
        connected, _ = await c1.connect()
        assert connected is True
        await c1.receive_json_from()
        await c1.disconnect()

        c2 = WebsocketCommunicator(application, url)
        connected, code = await c2.connect()
        assert connected is False
        assert code == 4001

    async def test_exec_open_event_logged(self, valid_ticket):
        """EXEC_OPEN written to DB on connect."""
        communicator = WebsocketCommunicator(
            application,
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.disconnect()

        event = await get_latest_event('EXEC_OPEN')
        assert event.action == 'EXEC_OPEN'
        assert event.status == 'SUCCESS'

    async def test_exec_close_event_logged(self, valid_ticket):
        """EXEC_CLOSE written to DB on disconnect."""
        communicator = WebsocketCommunicator(
            application,
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.disconnect()

        event = await get_latest_event('EXEC_CLOSE')
        assert event.action == 'EXEC_CLOSE'
        assert event.status == 'SUCCESS'

    async def test_input_returns_output(self, valid_ticket):
        """Sending input returns exec output."""
        communicator = WebsocketCommunicator(
            application,
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        await communicator.connect()
        await communicator.receive_json_from()  # welcome

        with patch.object(
            ExecConsumer,
            '_run_exec',
            new=AsyncMock(return_value=('output of: ls -la', None))
        ):
            await communicator.send_json_to({
                'type': 'input',
                'data': 'ls -la'
            })
            response = await communicator.receive_json_from()
            assert response['type'] == 'output'
            assert 'ls -la' in response['data']

        await communicator.disconnect()

    async def test_invalid_json_returns_error(self, valid_ticket):
        """Non-JSON input returns error response."""
        communicator = WebsocketCommunicator(
            application,
            f'/ws/hosts/1/containers/{valid_ticket.container_id}/exec/'
            f'?ticket={valid_ticket.ticket}'
        )
        await communicator.connect()
        await communicator.receive_json_from()  # welcome

        await communicator.send_to(text_data='not json at all')
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'

        await communicator.disconnect()


# ── LOG CONSUMER TESTS ────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestLogConsumer:

    async def test_connect_with_valid_ticket(self, container_record, user):
        """Valid ticket → log consumer accepts connection."""
        ticket = await issue_ticket(container_record, user)

        with patch.object(
            LogConsumer, '_stream_logs',
            new=AsyncMock(return_value=None)
        ):
            communicator = WebsocketCommunicator(
                application,
                f'/ws/hosts/1/containers/{container_record.id}/logs/'
                f'?ticket={ticket.ticket}'
            )
            connected, code = await communicator.connect()
            assert connected is True
            await communicator.disconnect()

    async def test_connect_with_invalid_ticket(self, db):
        """Invalid ticket → rejected."""
        communicator = WebsocketCommunicator(
            application,
            '/ws/hosts/1/containers/some-id/logs/?ticket=faketicket'
        )
        connected, code = await communicator.connect()
        assert connected is False
        assert code == 4001

    async def test_input_rejected(self, container_record, user):
        """Log consumer is read-only — input returns error."""
        ticket = await issue_ticket(container_record, user)

        with patch.object(
            LogConsumer, '_stream_logs',
            new=AsyncMock(return_value=None)
        ):
            communicator = WebsocketCommunicator(
                application,
                f'/ws/hosts/1/containers/{container_record.id}/logs/'
                f'?ticket={ticket.ticket}'
            )
            await communicator.connect()

            await communicator.send_json_to({'type': 'input', 'data': 'anything'})
            response = await communicator.receive_json_from()
            assert response['type'] == 'error'
            assert 'read-only' in response['data']

            await communicator.disconnect()

    async def test_log_ticket_consumed_on_connect(
        self, container_record, user
    ):
        """Ticket marked used after log consumer connects."""
        ticket = await issue_ticket(container_record, user)

        with patch.object(
            LogConsumer, '_stream_logs',
            new=AsyncMock(return_value=None)
        ):
            communicator = WebsocketCommunicator(
                application,
                f'/ws/hosts/1/containers/{container_record.id}/logs/'
                f'?ticket={ticket.ticket}'
            )
            await communicator.connect()
            await communicator.disconnect()

        refreshed = await refresh_ticket(ticket)
        assert refreshed.is_used is True