from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone

from containers.models import ContainerRecord, Host
from containers.serializers import (
    ContainerLogsSerializer,
    ExecTicketResponseSerializer,
)
from containers.auth import require_auth
from containers import services


class ContainerLogsView(APIView):

    @require_auth
    def get(self, request, host_id, container_id):
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        tail       = int(request.query_params.get('tail', 200))
        timestamps = request.query_params.get('timestamps', 'false').lower() \
                     == 'true'

        lines, error = services.get_container_logs(
            record, tail=tail, timestamps=timestamps
        )

        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(ContainerLogsSerializer({
            'container_id': record.container_id,
            'name':         record.name,
            'tail':         tail,
            'logs':         lines,
        }).data)


class ContainerLogStreamTicketView(APIView):
    @require_auth
    def post(self, request, host_id, container_id):
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        ticket = services.issue_exec_ticket(record, request.user)

        ws_url = (
            f'ws://{request.get_host()}'
            f'/ws/hosts/{host_id}/containers/{container_id}/logs/'
            f'?ticket={ticket.ticket}'
        )

        return Response(ExecTicketResponseSerializer({
            'ticket':             ticket.ticket,
            'ws_url':             ws_url,
            'expires_in_seconds': 30,
        }).data)