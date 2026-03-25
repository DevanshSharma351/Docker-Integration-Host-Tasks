from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrHostOwner(BasePermission):
    """
    POST (enqueue pull): only admin or the host owner.
    Safe methods (GET list/detail): any authenticated user.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in {"admin", "host"}

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # For writes, must be admin or the host's owner
        return (
            request.user.role == "admin"
            or obj.host.owner == request.user
        )


class IsAdminOnly(BasePermission):
    """DELETE (cancel): admin only."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == "admin"
