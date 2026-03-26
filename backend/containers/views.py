import logging
import shlex

import docker
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hosts.models import Host
from .serializers import ContainerCreateSerializer, ContainerCreateResponseSerializer

logger = logging.getLogger(__name__)


def _is_local_hostname(hostname: str) -> bool:
    value = (hostname or '').strip().lower()
    return value in {'localhost', '127.0.0.1', '::1'}


def _get_docker_client_for_host(host: Host, timeout: int = 30):
    if _is_local_hostname(host.hostname):
        try:
            return docker.from_env(timeout=timeout)
        except docker.errors.DockerException:
            pass

    return docker.DockerClient(
        base_url=f"tcp://{host.hostname}:{host.port}",
        timeout=timeout,
    )


class ContainerCreateView(APIView):
    """
    POST /api/containers/create/

    Creates and starts a container on the selected host.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ContainerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        host = get_object_or_404(Host, pk=data['host_id'])
        if request.user.role != 'admin' and host.owner != request.user:
            return Response(
                {'detail': 'You do not have permission to deploy containers on this host.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            client = _get_docker_client_for_host(host=host)
        except docker.errors.DockerException as exc:
            logger.error('Cannot connect to Docker daemon on host %s: %s', host.name, exc)
            return Response(
                {'detail': f'Cannot connect to Docker daemon: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        command_value = (data.get('command') or '').strip()
        command = shlex.split(command_value) if command_value else None

        try:
            container = client.containers.run(
                image=data['image_ref'].strip(),
                name=(data.get('name') or '').strip() or None,
                command=command,
                ports=data.get('ports') or None,
                detach=True,
            )
            container.reload()
        except docker.errors.ImageNotFound:
            return Response(
                {'detail': f"Image '{data['image_ref']}' not found on host '{host.name}'."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except docker.errors.APIError as exc:
            logger.error('Docker API error creating container on host %s: %s', host.name, exc)
            return Response(
                {'detail': f'Docker API error: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        output = {
            'id': container.id,
            'name': container.name,
            'status': container.status,
            'image': data['image_ref'].strip(),
            'host_id': host.id,
        }
        response_serializer = ContainerCreateResponseSerializer(output)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
