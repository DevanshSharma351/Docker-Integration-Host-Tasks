import logging

import docker
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RegistryCredential
from .permissions import IsCredentialOwner
from .serializers import (
    RegistryCredentialCreateSerializer,
    RegistryCredentialSerializer,
    RegistryCredentialUpdateSerializer,
)

logger = logging.getLogger(__name__)


class RegistryCredentialListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/registries/       → list credentials for the authenticated user
    POST /api/registries/       → save a new credential (token stored encrypted)
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RegistryCredentialCreateSerializer
        return RegistryCredentialSerializer

    def get_queryset(self):
        return RegistryCredential.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        credential = serializer.save(owner=self.request.user)
        logger.info(
            "Registry credential created id=%s alias=%s user_id=%s",
            credential.id,
            credential.alias,
            self.request.user.id,
        )


class RegistryCredentialDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/registries/{id}/  → retrieve a specific credential
    PUT    /api/registries/{id}/  → update (owner only)
    DELETE /api/registries/{id}/  → delete (owner only)
    """

    permission_classes = [IsAuthenticated, IsCredentialOwner]
    lookup_field = "pk"

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return RegistryCredentialUpdateSerializer
        return RegistryCredentialSerializer

    def get_queryset(self):
        return RegistryCredential.objects.filter(owner=self.request.user)

    def perform_update(self, serializer):
        credential = serializer.save()
        logger.info(
            "Registry credential updated id=%s updated_by=%s",
            credential.id,
            self.request.user.id,
        )

    def perform_destroy(self, instance):
        credential_id = instance.id
        instance.delete()
        logger.info(
            "Registry credential deleted id=%s deleted_by=%s",
            credential_id,
            self.request.user.id,
        )


class RegistryCredentialVerifyView(APIView):
    """
    POST /api/registries/{id}/verify/
    Performs a live ``docker login`` against the registry to verify the credential.
    Updates ``last_verified_at`` on success.
    """

    permission_classes = [IsAuthenticated, IsCredentialOwner]

    def get_object(self):
        credential = generics.get_object_or_404(
            RegistryCredential.objects.filter(owner=self.request.user),
            pk=self.kwargs["pk"],
        )
        # Check object-level permissions
        for permission in self.get_permissions():
            if hasattr(permission, "has_object_permission"):
                if not permission.has_object_permission(self.request, self, credential):
                    self.permission_denied(self.request)
        return credential

    def post(self, request, pk=None):
        credential = self.get_object()

        try:
            client = docker.from_env()
            login_result = client.login(
                username=credential.username,
                password=credential.token,
                registry=credential.registry_url,
            )
            logger.info(
                "Registry verify success id=%s registry=%s user_id=%s",
                credential.id,
                credential.registry_url,
                request.user.id,
            )
        except docker.errors.APIError as exc:
            logger.warning(
                "Registry verify failed id=%s registry=%s error=%s",
                credential.id,
                credential.registry_url,
                exc,
            )
            explanation = getattr(exc, "explanation", None) or str(exc)
            return Response(
                {"detail": f"Docker login failed: {explanation}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception(
                "Registry verify error id=%s registry=%s",
                credential.id,
                credential.registry_url,
            )
            return Response(
                {"detail": f"Verification error: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        credential.last_verified_at = timezone.now()
        credential.save(update_fields=["last_verified_at"])

        return Response(
            {
                "detail": "Login successful",
                "login_result": login_result,
                "last_verified_at": credential.last_verified_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
