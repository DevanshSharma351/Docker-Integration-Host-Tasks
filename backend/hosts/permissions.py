from rest_framework.permissions import BasePermission
from .models import UserHostRole

def get_user_role_for_host(user, host_id):
    return UserHostRole.objects.filter(
        user=user,
        host_id=host_id
    ).values_list('role', flat=True).first()

class IsAdminRole(BasePermission):
    """Allows access only to global ADMINs (those who have ADMIN role on any host, or Django superuser)."""
    message = "Only ADMIN users can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        global_role = getattr(request.user, 'role', '')
        return (
            request.user.is_superuser or 
            request.user.is_staff or 
            str(global_role).lower() == 'admin' or
            UserHostRole.objects.filter(user=request.user, role='ADMIN').exists()
        )

class IsHostOwnerOrAdmin(BasePermission):
    """For host-specific actions: allows HOST_OWNER or ADMIN assigned to that host."""
    message = "You do not have write access to this host."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        role = get_user_role_for_host(request.user, obj.id)
        return role in ['ADMIN', 'HOST_OWNER'] or request.user.is_superuser


class CanAccessHost(BasePermission):
    """Any role (VIEWER, HOST_OWNER, ADMIN) grants read access to a host."""
    message = "You are not assigned to this host."

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return UserHostRole.objects.filter(user=request.user, host_id=obj.id).exists()
