from functools import wraps
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


def get_user_from_request(request):
    try:
        result = JWTAuthentication().authenticate(request)
    except (InvalidToken, TokenError):
        return None

    if result is None:
        return None
    user, _ = result
    return user


def check_role(user, host_id, allowed_roles):
    role_map = {
        'admin': 'ADMIN',
        'host': 'HOST_OWNER',
        'viewer': 'VIEWER',
    }

    if getattr(user, 'is_superuser', False):
        return True

    normalized_role = role_map.get(getattr(user, 'role', '').lower())
    return normalized_role in allowed_roles


def require_auth(view_func):
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