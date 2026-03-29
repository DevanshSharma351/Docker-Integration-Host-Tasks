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
    ContainerLifecycleEvent.objects.create(
        container=container,
        triggered_by=user,
        action=action,
        status=ContainerLifecycleEvent.Status.SUCCESS if success
               else ContainerLifecycleEvent.Status.FAILED,
        error_message=error,
    )


def _get_sdk_container(record):
    client = get_docker_client(record.host)
    return client.containers.get(record.container_id)


def _default_command_for_image(image_ref, command):
    if (command or '').strip():
        return command

    image = (image_ref or '').strip().lower()
    if image == 'alpine' or image.startswith('alpine:'):
        return 'sleep infinity'
    if image == 'node' or image.startswith('node:'):
        return 'sleep infinity'

    return ''


def _map_docker_state_to_record_status(state_status):
    mapping = {
        'created': ContainerRecord.Status.CREATED,
        'running': ContainerRecord.Status.RUNNING,
        'paused': ContainerRecord.Status.PAUSED,
        'restarting': ContainerRecord.Status.RUNNING,
        'exited': ContainerRecord.Status.STOPPED,
        'dead': ContainerRecord.Status.KILLED,
    }
    return mapping.get((state_status or '').lower(), ContainerRecord.Status.STOPPED)


def sync_record_with_docker(record):
    """
    Refresh a DB record from live Docker state.
    If the container no longer exists on daemon, mark as REMOVED.
    """
    try:
        sdk_container = _get_sdk_container(record)
        sdk_container.reload()
        state_status = (sdk_container.attrs.get('State') or {}).get('Status')
        resolved_status = _map_docker_state_to_record_status(state_status)
    except docker.errors.NotFound:
        resolved_status = ContainerRecord.Status.REMOVED
    except docker.errors.APIError:
        return

    if record.status != resolved_status:
        record.status = resolved_status
        record.save(update_fields=['status', 'updated_at'])


def sync_host_records(host):
    for record in ContainerRecord.objects.filter(host=host).exclude(
        status=ContainerRecord.Status.REMOVED
    ):
        sync_record_with_docker(record)

def create_container(host, user, image_ref, name, environment,
                     port_bindings, volumes, command=''):

    client = get_docker_client(host)
    try:
        resolved_command = _default_command_for_image(image_ref, command)
        run_kwargs = {
            'image': image_ref,
            'name': name,
            'environment': environment,
            'ports': port_bindings,
            'volumes': volumes,
            'detach': True,
        }
        if resolved_command:
            run_kwargs['command'] = resolved_command

        sdk_container = client.containers.run(
            **run_kwargs
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

    except docker.errors.NotFound:
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
    action = _ACTION_MAP[sdk_method]
    try:
        sdk_container = _get_sdk_container(record)
        getattr(sdk_container, sdk_method)()

        record.status = _STATUS_MAP[sdk_method]
        record.save(update_fields=['status', 'updated_at'])
        _log_event(record, user, action, True)
        return None

    except docker.errors.NotFound:
        record.status = ContainerRecord.Status.REMOVED
        record.save(update_fields=['status', 'updated_at'])
        _log_event(record, user, action, True)
        return None

    except docker.errors.APIError as e:
        _log_event(record, user, action, False, error=str(e))
        return str(e.explanation)

def get_container_stats(record):
    try:
        sdk_container = _get_sdk_container(record)
        raw = sdk_container.stats(stream=False)

        cpu_stats = raw.get('cpu_stats') or {}
        precpu_stats = raw.get('precpu_stats') or {}
        cpu_usage = cpu_stats.get('cpu_usage') or {}
        precpu_usage = precpu_stats.get('cpu_usage') or {}

        # Docker may omit system_cpu_usage for stopped/exited containers.
        cpu_delta = (
            cpu_usage.get('total_usage', 0)
            - precpu_usage.get('total_usage', 0)
        )
        cpu_system = cpu_stats.get('system_cpu_usage')
        precpu_system = precpu_stats.get('system_cpu_usage')
        if cpu_system is None or precpu_system is None:
            system_delta = 0
        else:
            system_delta = cpu_system - precpu_system

        num_cpus = cpu_stats.get('online_cpus')
        if not num_cpus:
            num_cpus = len(cpu_usage.get('percpu_usage') or []) or 1

        cpu_percent  = (
            (cpu_delta / system_delta) * num_cpus * 100.0
            if system_delta > 0 else 0.0
        )

        # Memory
        mem = raw.get('memory_stats') or {}
        mem_usage = mem.get('usage', 0)
        mem_limit = mem.get('limit', 0)
        mem_percent = round((mem_usage / mem_limit) * 100, 2) if mem_limit > 0 else 0.0

        # Network — sum across all interfaces
        net    = raw.get('networks', {})
        rx     = sum((v or {}).get('rx_bytes', 0) for v in net.values())
        tx     = sum((v or {}).get('tx_bytes', 0) for v in net.values())

        # Block I/O
        blk         = (raw.get('blkio_stats', {})
                          .get('io_service_bytes_recursive')) or []
        read_bytes  = next((b.get('value', 0) for b in blk if (b or {}).get('op') == 'Read'), 0)
        write_bytes = next((b.get('value', 0) for b in blk if (b or {}).get('op') == 'Write'), 0)

        return {
            'container_id': record.container_id,
            'name':         record.name,
            'cpu_percent':  round(cpu_percent, 2),
            'memory': {
                'usage_bytes': mem_usage,
                'limit_bytes': mem_limit,
                'percent':     mem_percent,
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

    return ExecTicket.issue(container=record, user=user)


def validate_and_consume_ticket(ticket_value):

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
    