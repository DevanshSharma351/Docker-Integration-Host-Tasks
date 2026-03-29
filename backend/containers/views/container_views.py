from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone

from containers.models import ContainerRecord, Host
from containers.serializers import (
    ContainerRecordSerializer,
    ContainerRecordListSerializer,
    ContainerCreateSerializer,
    LifecycleActionResponseSerializer,
)
from containers.auth import require_auth, require_role
from containers import services
class ContainerListCreateView(APIView):

    @require_auth
    def get(self, request, host_id):
        """List all containers on a host — any authenticated user."""
        host = get_object_or_404(Host, pk=host_id)
        services.sync_host_records(host)
        status_filter = request.query_params.get('status', None)

        qs = ContainerRecord.objects.filter(host=host)
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        serializer = ContainerRecordListSerializer(qs, many=True)
        return Response({
            'count':   qs.count(),
            'results': serializer.data,
        })

    @require_auth
    @require_role(['ADMIN', 'HOST_OWNER'])
    def post(self, request, host_id):
        """Create and start a new container."""
        host = get_object_or_404(Host, pk=host_id)

        serializer = ContainerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        record, error = services.create_container(
            host=host,
            user=request.user,
            image_ref=serializer.validated_data['image_ref'],
            name=serializer.validated_data['name'],
            environment=serializer.validated_data['environment'],
            port_bindings=serializer.validated_data['port_bindings'],
            volumes=serializer.validated_data['volumes'],
            command=serializer.validated_data.get('command', ''),
        )

        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            ContainerRecordSerializer(record).data,
            status=status.HTTP_201_CREATED
        )

class ContainerDetailView(APIView):

    @require_auth
    def get(self, request, host_id, container_id):
        """Inspect a single container."""
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )
        services.sync_record_with_docker(record)
        record.refresh_from_db()
        return Response(ContainerRecordSerializer(record).data)

    @require_auth
    @require_role(['ADMIN'])
    def delete(self, request, host_id, container_id):
        """Force remove a container."""
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        error = services.remove_container(record, request.user)
        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {'message': f'Container {record.name} removed successfully.'},
            status=status.HTTP_200_OK
        )


# LIFECYCLE ACTIONS 
# The only difference is the sdk_method string passed to lifecycle_action().

class BaseLifecycleView(APIView):
    sdk_method    = None
    allowed_roles = ['ADMIN', 'HOST_OWNER']

    @require_auth
    @require_role(['ADMIN', 'HOST_OWNER'])
    def post(self, request, host_id, container_id):
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        error = services.lifecycle_action(
            record, request.user, self.sdk_method
        )

        if error:
            return Response(
                {
                    'error':  error,
                    'action': self.sdk_method.upper(),
                    'status': 'FAILED',
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response({
            'container_id': record.container_id,
            'name':         record.name,
            'action':       self.sdk_method.upper(),
            'status':       'SUCCESS',
            'timestamp':    timezone.now(),
        })


class ContainerStartView(BaseLifecycleView):
    sdk_method = 'start'

class ContainerStopView(BaseLifecycleView):
    sdk_method = 'stop'

class ContainerRestartView(BaseLifecycleView):
    sdk_method = 'restart'

class ContainerKillView(BaseLifecycleView):
    sdk_method = 'kill'

class ContainerPauseView(BaseLifecycleView):
    sdk_method = 'pause'

class ContainerUnpauseView(BaseLifecycleView):
    sdk_method = 'unpause'