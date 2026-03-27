import logging
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Host, UserHostRole
from .serializers import HostSerializer, HostCreateSerializer, UserHostRoleSerializer
from .permissions import IsAdminRole, CanAccessHost

logger = logging.getLogger(__name__)
User = get_user_model()


# =========================
# HOST LIST + CREATE
# =========================
class HostListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user   
        if user.is_superuser:
            return Host.objects.all()

        assigned_host_ids = UserHostRole.objects.filter(
            user=user
        ).values_list('host_id', flat=True)

        return Host.objects.filter(id__in=assigned_host_ids)

    def get_serializer_class(self):
        return HostCreateSerializer if self.request.method == 'POST' else HostSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        host = serializer.save(created_by=self.request.user)
        logger.info(f"Host '{host.alias}' registered by {self.request.user.username}")


# =========================
# HOST DETAIL
# =========================
class HostDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Host.objects.all()
    permission_classes = [IsAuthenticated, CanAccessHost]

    lookup_field = "id"          
    lookup_url_kwarg = "id"

    def get_serializer_class(self):
        return HostCreateSerializer if self.request.method in ['PUT','PATCH'] else HostSerializer

    def get_permissions(self):
        if self.request.method in ['PUT','PATCH','DELETE']:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated(), CanAccessHost()]


# =========================
# ASSIGN / REMOVE USER
# =========================
class AssignUserToHostView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, id):
        try:
            host = Host.objects.get(id=id)
        except Host.DoesNotExist:
            return Response({"error": "Host not found"}, status=404)

        user_id = request.data.get("user_id")
        role = request.data.get("role")

        try:
            user = User.objects.get(id=user_id)   
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        assignment, created = UserHostRole.objects.update_or_create(
            user=user,
            host=host,
            defaults={"role": role, "assigned_by": request.user},
        )

        serializer = UserHostRoleSerializer(assignment)
        return Response(serializer.data, status=201 if created else 200)

    def delete(self, request, id, user_id):
        try:
            assignment = UserHostRole.objects.get(host_id=id, user_id=user_id)
            assignment.delete()
            return Response(status=204)
        except UserHostRole.DoesNotExist:
            return Response({"error": "Assignment not found"}, status=404)


# =========================
# LIST USERS ON HOST
# =========================
class HostUsersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = UserHostRoleSerializer

    def get_queryset(self):
        return UserHostRole.objects.filter(host_id=self.kwargs['id'])  