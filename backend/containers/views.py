from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from containers import services
from containers.auth import require_auth, require_role
from containers.models import ContainerLifecycleEvent, ContainerRecord, Host
from containers.serializers import (
    HostSerializer,
    ContainerCreateSerializer,
    ContainerLifecycleEventSerializer,
    ContainerLogsSerializer,
    ContainerRecordListSerializer,
    ContainerRecordSerializer,
    ContainerStatsSerializer,
    ExecTicketResponseSerializer,
)
from hosts.models import Host as AccessHost


def _connection_string_for_access_host(host):
    if host.ip_address in ('127.0.0.1', 'localhost', '::1'):
        return 'unix:///var/run/docker.sock'
    return f'tcp://{host.ip_address}:{host.port}'


class ContainerListCreateView(APIView):
    @require_auth
    def get(self, request, host_id):
        host = get_object_or_404(Host, pk=host_id)
        services.sync_host_records(host)
        status_filter = request.query_params.get("status", None)

        qs = ContainerRecord.objects.filter(host=host)
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        else:
            qs = qs.exclude(status=ContainerRecord.Status.REMOVED)

        serializer = ContainerRecordListSerializer(qs, many=True)
        return Response({"count": qs.count(), "results": serializer.data})

    @require_auth
    @require_role(["ADMIN", "HOST_OWNER"])
    def post(self, request, host_id):
        host = get_object_or_404(Host, pk=host_id)

        serializer = ContainerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        record, error = services.create_container(
            host=host,
            user=request.user,
            image_ref=serializer.validated_data["image_ref"],
            name=serializer.validated_data["name"],
            environment=serializer.validated_data["environment"],
            port_bindings=serializer.validated_data["port_bindings"],
            volumes=serializer.validated_data["volumes"],
            command=serializer.validated_data.get("command", ""),
        )

        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ContainerRecordSerializer(record).data, status=status.HTTP_201_CREATED
        )


class ContainerDetailView(APIView):
    @require_auth
    def get(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)
        services.sync_record_with_docker(record)
        record.refresh_from_db()
        return Response(ContainerRecordSerializer(record).data)

    @require_auth
    @require_role(["ADMIN"])
    def delete(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        error = services.remove_container(record, request.user)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": f"Container {record.name} removed successfully."},
            status=status.HTTP_200_OK,
        )


class BaseLifecycleView(APIView):
    sdk_method = None

    @require_auth
    @require_role(["ADMIN", "HOST_OWNER"])
    def post(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        error = services.lifecycle_action(record, request.user, self.sdk_method)

        if error:
            return Response(
                {
                    "error": error,
                    "action": self.sdk_method.upper(),
                    "status": "FAILED",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "container_id": record.container_id,
                "name": record.name,
                "action": self.sdk_method.upper(),
                "status": "SUCCESS",
                "timestamp": timezone.now(),
            }
        )


class ContainerStartView(BaseLifecycleView):
    sdk_method = "start"


class ContainerStopView(BaseLifecycleView):
    sdk_method = "stop"


class ContainerRestartView(BaseLifecycleView):
    sdk_method = "restart"


class ContainerKillView(BaseLifecycleView):
    sdk_method = "kill"


class ContainerPauseView(BaseLifecycleView):
    sdk_method = "pause"


class ContainerUnpauseView(BaseLifecycleView):
    sdk_method = "unpause"


class ContainerStatsView(APIView):
    @require_auth
    def get(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        stats, error = services.get_container_stats(record)

        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ContainerStatsSerializer(stats).data)


class ContainerLogsView(APIView):
    @require_auth
    def get(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        tail = int(request.query_params.get("tail", 200))
        timestamps = request.query_params.get("timestamps", "false").lower() == "true"

        lines, error = services.get_container_logs(
            record, tail=tail, timestamps=timestamps
        )

        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ContainerLogsSerializer(
                {
                    "container_id": record.container_id,
                    "name": record.name,
                    "tail": tail,
                    "logs": lines,
                }
            ).data
        )


class ContainerLogStreamTicketView(APIView):
    @require_auth
    def post(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        ticket = services.issue_exec_ticket(record, request.user)

        ws_url = (
            f"ws://{request.get_host()}"
            f"/ws/hosts/{host_id}/containers/{container_id}/logs/"
            f"?ticket={ticket.ticket}"
        )

        return Response(
            ExecTicketResponseSerializer(
                {
                    "ticket": ticket.ticket,
                    "ws_url": ws_url,
                    "expires_in_seconds": 30,
                }
            ).data
        )


class ExecTicketView(APIView):
    @require_auth
    @require_role(["ADMIN", "HOST_OWNER"])
    def post(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        ticket = services.issue_exec_ticket(record, request.user)

        ws_url = (
            f"ws://{request.get_host()}"
            f"/ws/hosts/{host_id}/containers/{container_id}/exec/"
            f"?ticket={ticket.ticket}"
        )

        return Response(
            ExecTicketResponseSerializer(
                {
                    "ticket": ticket.ticket,
                    "ws_url": ws_url,
                    "expires_in_seconds": 30,
                }
            ).data
        )


class ContainerEventListView(APIView):
    @require_auth
    def get(self, request, host_id, container_id):
        host = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(ContainerRecord, pk=container_id, host=host)

        qs = ContainerLifecycleEvent.objects.filter(container=record)

        action_filter = request.query_params.get("action")
        status_filter = request.query_params.get("status")
        if action_filter:
            qs = qs.filter(action=action_filter.upper())
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        start = (page - 1) * page_size
        end = start + page_size

        total = qs.count()
        page_qs = qs[start:end]
        serializer = ContainerLifecycleEventSerializer(page_qs, many=True)

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            }
        )


class ContainerHostBootstrapView(APIView):
    @require_auth
    @require_role(["ADMIN", "HOST_OWNER"])
    def post(self, request):
        host, _ = Host.objects.get_or_create(
            name="local-docker",
            defaults={
                "ip_address": "127.0.0.1",
                "port": 2375,
                "connection_string": "unix:///var/run/docker.sock",
            },
        )

        return Response(HostSerializer(host).data, status=status.HTTP_200_OK)


class ContainerHostResolveView(APIView):
    @require_auth
    def post(self, request, access_host_id):
        access_host = get_object_or_404(AccessHost, pk=access_host_id)

        host, created = Host.objects.get_or_create(
            ip_address=access_host.ip_address,
            port=access_host.port,
            defaults={
                'name': access_host.alias,
                'connection_string': _connection_string_for_access_host(access_host),
            },
        )

        if not created:
            updates = {}
            if host.name != access_host.alias:
                updates['name'] = access_host.alias
            resolved_conn = _connection_string_for_access_host(access_host)
            if host.connection_string != resolved_conn:
                updates['connection_string'] = resolved_conn
            if updates:
                for field, value in updates.items():
                    setattr(host, field, value)
                host.save(update_fields=list(updates.keys()))

        return Response(
            {
                'container_host': HostSerializer(host).data,
                'source_host_id': str(access_host.id),
            },
            status=status.HTTP_200_OK,
        )