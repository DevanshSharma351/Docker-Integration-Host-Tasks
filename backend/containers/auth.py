# ─────────────────────────────────────────────────────────────────────────
# AUTH MODULE
#
# Phase 1 (now):    DummyUser lets everything through — no JWT needed
# Phase 2 (routes): Same, just add @require_auth to views
# Phase 3 (integration): When Module 1 delivers JWT:
#   1. Delete DummyUser class
#   2. Replace body of get_user_from_request() with real JWT validation
#   3. Replace body of check_role() with real UserHostRole lookup
#   Nothing else in the codebase changes.
# ─────────────────────────────────────────────────────────────────────────

from functools import wraps
from rest_framework.response import Response


class DummyUser:
    """
    Fake user for development.
    Mimics Django's User interface so all code that
    touches request.user works without a real login.
    """
    id             = 1
    pk             = 1
    username       = 'dev_user'
    is_authenticated = True
    is_active      = True

    def __str__(self):
        return self.username


def get_user_from_request(request):
    """
    Phase 1/2 — always returns DummyUser.

    Phase 3 — replace this entire body with:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        try:
            auth = JWTAuthentication()
            result = auth.authenticate(request)
            if result is None:
                return None
            user, token = result
            return user
        except Exception:
            return None
    """
    return DummyUser()


def check_role(user, host_id, allowed_roles):
    """
    Phase 1/2 — always returns True.

    Phase 3 — replace this entire body with:
        from hosts.models import UserHostRole
        return UserHostRole.objects.filter(
            user=user,
            host_id=host_id,
            role__in=allowed_roles
        ).exists()
    """
    return True


def require_auth(view_func):
    """
    Decorator that ensures request.user is set.
    Apply to every view method.

    Usage:
        @require_auth
        def get(self, request, ...):
    """
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        user = get_user_from_request(request)
        if not user or not user.is_authenticated:
            return Response(
                {'error': 'Unauthorized. Valid JWT required.'},
                status=401
            )
        request.user = user
        return view_func(self, request, *args, **kwargs)
    return wrapper


def require_role(allowed_roles):
    """
    Decorator for role-based access control.
    Always call @require_auth before this.

    Usage:
        @require_auth
        @require_role(['ADMIN', 'HOST_OWNER'])
        def post(self, request, host_id, ...):
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            host_id = kwargs.get('host_id')
            if not check_role(request.user, host_id, allowed_roles):
                return Response(
                    {'error': f'Forbidden. Required roles: {allowed_roles}'},
                    status=403
                )
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator