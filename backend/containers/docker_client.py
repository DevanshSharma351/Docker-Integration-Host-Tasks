import docker
from docker.errors import DockerException
from rest_framework.exceptions import APIException
from rest_framework import status


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Docker host is unreachable.'
    default_code = 'service_unavailable'


def _resolve_base_url(host):
    base_url = host.get_connection_string().strip()
    if not base_url:
        raise ServiceUnavailable(
            detail=f'Docker connection string is empty for host "{host.name}".'
        )

    if base_url.startswith('unix://') or base_url.startswith('tcp://'):
        return base_url

    raise ServiceUnavailable(
        detail=(
            f'Unsupported Docker connection string for host "{host.name}": '
            f'{base_url}. Use unix:// or tcp://.'
        )
    )


def get_docker_client(host):
    try:
        client = docker.DockerClient(base_url=_resolve_base_url(host))

        client.ping()  # fail fast if host is unreachable
        return client

    except DockerException as e:
        raise ServiceUnavailable(
            detail=f'Could not connect to Docker host "{host.name}": {str(e)}'
        )