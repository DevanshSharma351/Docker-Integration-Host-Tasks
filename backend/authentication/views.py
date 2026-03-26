import logging

from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from hosts.models import Host
from .serializers import RegisterSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


def ensure_default_host_for_user(user):
    """Ensure host-role users always have at least one Host record."""
    if user.role != User.HOST:
        return None

    existing = Host.objects.filter(owner=user).first()
    if existing:
        return existing

    host = Host.objects.create(
        name=f"{user.username}-local-host",
        hostname="localhost",
        port=2375,
        owner=user,
    )
    logger.info(
        "Auto-created default host id=%s for user_id=%s username=%s",
        host.id,
        user.id,
        user.username,
    )
    return host


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        ensure_default_host_for_user(self.user)
        logger.info("User logged in successfully user_id=%s username=%s", self.user.id, self.user.username)
        data['role'] = self.user.role
        data['username'] = self.user.username
        data['email'] = self.user.email
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        ensure_default_host_for_user(user)
        logger.info("User registered successfully user_id=%s username=%s", user.id, user.username)
