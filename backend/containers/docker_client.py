import docker
from docker.errors import DockerException
from rest_framework.exceptions import APIException
from rest_framework import status


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Docker host is unreachable.'
    default_code = 'service_unavailable'


def get_docker_client(host):
    try:
        if host.ip_address in ('localhost', '127.0.0.1'):
            client = docker.DockerClient(
                base_url='unix:///var/run/docker.sock'
            )
        else:
            client = docker.DockerClient(
                base_url=f'tcp://{host.ip_address}:{host.port}'
            )

        client.ping()  # fail fast if host is unreachable
        return client

    except DockerException as e:
        raise ServiceUnavailable(
            detail=f'Could not connect to Docker host "{host.name}": {str(e)}'
        )