from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsCredentialOwner(BasePermission):
    """
    Object-level permission:
    - Any authenticated user may list / retrieve (safe methods).
    - Only the credential *owner* may update or delete.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.owner == request.user
