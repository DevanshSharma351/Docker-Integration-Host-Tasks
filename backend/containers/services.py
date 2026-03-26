# ─────────────────────────────────────────────────────────────────────────
# SERVICE LAYER
#
# All Docker SDK logic lives here. Views are thin — they just call these
# functions. This makes testing trivial since you mock the SDK here,
# not in the views.
# ─────────────────────────────────────────────────────────────────────────

import docker
import docker.errors
from django.shortcuts import get_object_or_404
from django.utils import timezone

from containers.models import ContainerRecord, ContainerLifecycleEvent, ExecTicket
from containers.docker_client import get_docker_client


def _log_event(container, user, action, success, error=None):
    """
    Always call this after every SDK action — success or failure.
    Never let a view write to ContainerLifecycleEvent directly.
    """
    ContainerLifecycleEvent.objects.create(
        container=container,
        triggered_by=user,
        action=action,
        status=ContainerLifecycleEvent.Status.SUCCESS if success
               else ContainerLifecycleEvent.Status.FAILED,
        error_message=error,
    )


def _get_sdk_container(record):
    """
    Gets the live Docker SDK container object from a ContainerRecord.
    Raises ServiceUnavailable if host unreachable.
    Raises ContainerRecord.DoesNotExist equivalent via docker.errors if
    container is missing on the daemon.
    """
    client = get_docker_client(record.host)
    return client.containers.get(record.container_id)

def create_container(host, user, image_ref, name, environment,
                     port_bindings, volumes):
    """
    Creates and starts a container on the given host.
    Returns (ContainerRecord, error_string).
    error_string is None on success.
    """
    client = get_docker_client(host)
    try:
        sdk_container = client.containers.run(
            image=image_ref,
            name=name,
            environment=environment,
            ports=port_bindings,
            volumes=volumes,
            detach=True,
        )
        record = ContainerRecord.objects.create(
            host=host,
            created_by=user,
            container_id=sdk_container.id,
            name=name,
            image_ref=image_ref,
            status=ContainerRecord.Status.RUNNING,
            port_bindings=port_bindings,
            environment=environment,
            volumes=volumes,
        )
        _log_event(record, user, ContainerLifecycleEvent.Action.CREATE, True)
        return record, None

    except docker.errors.ImageNotFound:
        return None, f'Image "{image_ref}" not found on host.'

    except docker.errors.APIError as e:
        return None, str(e.explanation)


def remove_container(record, user):
    try:
        sdk_container = _get_sdk_container(record)
        sdk_container.remove(force=True)
        record.status = ContainerRecord.Status.REMOVED
        record.save(update_fields=['status', 'updated_at'])
        _log_event(record, user, ContainerLifecycleEvent.Action.REMOVE, True)
        return None

    except docker.errors.APIError as e:
        _log_event(record, user, ContainerLifecycleEvent.Action.REMOVE,
                   False, error=str(e))
        return str(e.explanation)


# Maps SDK method name → resulting ContainerRecord status
_STATUS_MAP = {
    'start':   ContainerRecord.Status.RUNNING,
    'stop':    ContainerRecord.Status.STOPPED,
    'restart': ContainerRecord.Status.RUNNING,
    'kill':    ContainerRecord.Status.KILLED,
    'pause':   ContainerRecord.Status.PAUSED,
    'unpause': ContainerRecord.Status.RUNNING,
}

# Maps SDK method name → ContainerLifecycleEvent action
_ACTION_MAP = {
    'start':   ContainerLifecycleEvent.Action.START,
    'stop':    ContainerLifecycleEvent.Action.STOP,
    'restart': ContainerLifecycleEvent.Action.RESTART,
    'kill':    ContainerLifecycleEvent.Action.KILL,
    'pause':   ContainerLifecycleEvent.Action.PAUSE,
    'unpause': ContainerLifecycleEvent.Action.UNPAUSE,
}


def lifecycle_action(record, user, sdk_method):
    """
    Generic handler for start/stop/restart/kill/pause/unpause.
    All six lifecycle views call this one function.

    Returns error string or None on success.

    Usage:
        error = lifecycle_action(record, request.user, 'stop')
    """
    action = _ACTION_MAP[sdk_method]
    try:
        sdk_container = _get_sdk_container(record)
        getattr(sdk_container, sdk_method)()  # calls e.g. sdk_container.stop()

        record.status = _STATUS_MAP[sdk_method]
        record.save(update_fields=['status', 'updated_at'])
        _log_event(record, user, action, True)
        return None

    except docker.errors.APIError as e:
        _log_event(record, user, action, False, error=str(e))
        return str(e.explanation)

def get_container_stats(record):
    """
    Returns a live stats snapshot dict from the Docker daemon.
    Calls container.stats(stream=False) — nothing is stored in the DB.
    Returns (stats_dict, error_string).
    """
    try:
        sdk_container = _get_sdk_container(record)
        raw = sdk_container.stats(stream=False)

        # CPU %
        cpu_delta    = (raw['cpu_stats']['cpu_usage']['total_usage']
                      - raw['precpu_stats']['cpu_usage']['total_usage'])
        system_delta = (raw['cpu_stats']['system_cpu_usage']
                      - raw['precpu_stats']['system_cpu_usage'])
        num_cpus     = raw['cpu_stats'].get('online_cpus', 1)
        cpu_percent  = (
            (cpu_delta / system_delta) * num_cpus * 100.0
            if system_delta > 0 else 0.0
        )

        # Memory
        mem = raw['memory_stats']

        # Network — sum across all interfaces
        net    = raw.get('networks', {})
        rx     = sum(v['rx_bytes'] for v in net.values())
        tx     = sum(v['tx_bytes'] for v in net.values())

        # Block I/O
        blk         = (raw.get('blkio_stats', {})
                          .get('io_service_bytes_recursive')) or []
        read_bytes  = next((b['value'] for b in blk if b['op'] == 'Read'), 0)
        write_bytes = next((b['value'] for b in blk if b['op'] == 'Write'), 0)

        return {
            'container_id': record.container_id,
            'name':         record.name,
            'cpu_percent':  round(cpu_percent, 2),
            'memory': {
                'usage_bytes': mem.get('usage', 0),
                'limit_bytes': mem.get('limit', 0),
                'percent':     round(
                    mem.get('usage', 0) / mem.get('limit', 1) * 100, 2
                ),
            },
            'network': {
                'rx_bytes': rx,
                'tx_bytes': tx,
            },
            'block_io': {
                'read_bytes':  read_bytes,
                'write_bytes': write_bytes,
            },
            'recorded_at': timezone.now().isoformat(),
        }, None

    except docker.errors.APIError as e:
        return None, str(e.explanation)


def get_container_logs(record, tail=200, timestamps=False):
    """
    Fetches recent logs as a static snapshot.
    Calls container.logs(stream=False) — nothing stored in DB.
    Returns (lines_list, error_string).
    """
    try:
        sdk_container = _get_sdk_container(record)
        raw = sdk_container.logs(
            tail=tail,
            timestamps=timestamps,
            stream=False
        )
        lines = raw.decode(errors='replace').splitlines()
        return lines, None

    except docker.errors.APIError as e:
        return None, str(e.explanation)


def issue_exec_ticket(record, user):
    """
    Creates and returns a short-lived ExecTicket for WebSocket auth.
    The ticket is stored in Postgres (single-use, 30s TTL).
    Returns the ExecTicket instance.
    """
    return ExecTicket.issue(container=record, user=user)


def validate_and_consume_ticket(ticket_value):
    """
    Called by the WebSocket consumer on connect.
    Validates the ticket, marks it used, returns the ExecTicket or None.
    """
    try:
        ticket = ExecTicket.objects.select_related(
            'container', 'container__host', 'issued_to'
        ).get(ticket=ticket_value)

        if not ticket.is_valid():
            return None

        ticket.consume()
        return ticket

    except ExecTicket.DoesNotExist:
        return None
    