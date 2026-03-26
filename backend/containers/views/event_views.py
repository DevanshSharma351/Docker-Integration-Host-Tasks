from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from containers.models import ContainerRecord, ContainerLifecycleEvent, Host
from containers.serializers import ContainerLifecycleEventSerializer
from containers.auth import require_auth


class ContainerEventListView(APIView):

    @require_auth
    def get(self, request, host_id, container_id):
        """
        Paginated audit log of all lifecycle events for a container.
        Supports ?action=START&status=FAILED&page=1&page_size=20
        """
        host   = get_object_or_404(Host, pk=host_id)
        record = get_object_or_404(
            ContainerRecord, pk=container_id, host=host
        )

        qs = ContainerLifecycleEvent.objects.filter(container=record)

        # Optional filters
        action_filter = request.query_params.get('action')
        status_filter = request.query_params.get('status')
        if action_filter:
            qs = qs.filter(action=action_filter.upper())
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        # Pagination
        page      = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start     = (page - 1) * page_size
        end       = start + page_size

        total      = qs.count()
        page_qs    = qs[start:end]
        serializer = ContainerLifecycleEventSerializer(page_qs, many=True)

        return Response({
            'count':     total,
            'page':      page,
            'page_size': page_size,
            'results':   serializer.data,
        })