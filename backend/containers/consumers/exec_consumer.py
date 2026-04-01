import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async


class ExecConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Parse ticket from query string
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

        await self.accept()
        await self._log_event('EXEC_OPEN', 'SUCCESS')

        await self.send(text_data=json.dumps({
            'type': 'connected',
            'data': f'Connected to {self.container_record.name}\r\n',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'container_record'):
            await self._log_event('EXEC_CLOSE', 'SUCCESS')

    async def receive(self, text_data):
        """Client sends input — we run it on the container and return output."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type':  'error',
                'data':  'Invalid JSON received.',
            }))
            return

        if data.get('type') == 'input':
            cmd    = data.get('data', '').strip()
            if not cmd:
                return

            output, error = await self._run_exec(cmd)

            if error:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'data': error,
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'output',
                    'data': output,
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

    @sync_to_async
    def _run_exec(self, cmd):

        import docker.errors
        from containers.docker_client import get_docker_client

        try:
            client        = get_docker_client(self.container_record.host)
            sdk_container = client.containers.get(
                self.container_record.container_id
            )
            result = sdk_container.exec_run(
                cmd,
                stdout=True,
                stderr=True,
            )
            output = result.output.decode(errors='replace')
            return output, None

        except docker.errors.APIError as e:
            return None, str(e.explanation)

    @sync_to_async
    def _log_event(self, action, status):
        from containers.models import ContainerLifecycleEvent
        ContainerLifecycleEvent.objects.create(
            container=self.container_record,
            triggered_by=self.user,
            action=action,
            status=status,
        )