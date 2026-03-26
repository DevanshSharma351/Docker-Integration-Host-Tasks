from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from containers.models import ContainerRecord, Host
from containers.serializers import ContainerStatsSerializer
from containers.auth import require_auth
from containers import services


class ContainerStatsView(APIView):

    @require_auth
    def get(self, request, host_id, container_id):
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        stats, error = services.get_container_stats(record)

        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(ContainerStatsSerializer(stats).data)