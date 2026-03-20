import docker
from docker.errors import DockerException
from rest_framework.exceptions import ServiceUnavailable


def get_docker_client(host):
    """
    Returns a connected DockerClient for the given Host instance.
    Supports both local unix socket and remote TCP connections.
    Raises ServiceUnavailable if the host cannot be reached.
    """
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