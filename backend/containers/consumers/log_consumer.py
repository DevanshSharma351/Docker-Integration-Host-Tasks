import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import asyncio


class LogConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        ticket_value = self._get_ticket_from_query()

        if not ticket_value:
            await self.close(code=4001)
            return

        ticket = await self._validate_ticket(ticket_value)
        if not ticket:
            await self.close(code=4001)
            return

        self.container_record = ticket.container
        self.user             = ticket.issued_to
        self.streaming        = True

        await self.accept()
        asyncio.ensure_future(self._stream_logs())

    async def disconnect(self, close_code):
        self.streaming = False

    async def receive(self, text_data):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'data': 'This is a read-only log stream. No input accepted.',
        }))

    def _get_ticket_from_query(self):
        query_string = self.scope.get('query_string', b'').decode()
        params = dict(
            part.split('=') for part in query_string.split('&')
            if '=' in part
        )
        return params.get('ticket')

    @sync_to_async
    def _validate_ticket(self, ticket_value):
        from containers.services import validate_and_consume_ticket
        return validate_and_consume_ticket(ticket_value)

    async def _stream_logs(self):
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._blocking_log_stream
            )
        except Exception as e:
            if self.streaming:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'data': f'Log stream error: {str(e)}',
                }))

    def _blocking_log_stream(self):
        import docker.errors
        from containers.docker_client import get_docker_client
        import asyncio

        client        = get_docker_client(self.container_record.host)
        sdk_container = client.containers.get(
            self.container_record.container_id
        )

        log_stream = sdk_container.logs(
            stream=True,
            follow=True,
            timestamps=True,
        )

        loop = asyncio.new_event_loop()

        for chunk in log_stream:
            if not self.streaming:
                break

            line = chunk.decode(errors='replace').strip()
            if line:
                asyncio.run_coroutine_threadsafe(
                    self.send(text_data=json.dumps({
                        'type': 'log',
                        'data': line,
                    })),
                    asyncio.get_event_loop()
                )

        loop.close()