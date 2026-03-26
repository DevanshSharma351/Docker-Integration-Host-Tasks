from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from containers.models import ContainerRecord, Host
from containers.serializers import ExecTicketResponseSerializer
from containers.auth import require_auth, require_role
from containers import services


class ExecTicketView(APIView):
    @require_auth
    @require_role(['ADMIN', 'HOST_OWNER'])
    def post(self, request, host_id, container_id):
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        ticket = services.issue_exec_ticket(record, request.user)

        ws_url = (
            f'ws://{request.get_host()}'
            f'/ws/hosts/{host_id}/containers/{container_id}/exec/'
            f'?ticket={ticket.ticket}'
        )

        return Response(ExecTicketResponseSerializer({
            'ticket':             ticket.ticket,
            'ws_url':             ws_url,
            'expires_in_seconds': 30,
        }).data)