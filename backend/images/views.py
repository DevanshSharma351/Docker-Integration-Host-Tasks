import logging

import docker
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hosts.models import Host

from .models import ImagePullJob
from .permissions import IsAdminOrHostOwner
from .serializers import (
    ImageInspectSerializer,
    ImagePullJobCreateSerializer,
    ImagePullJobSerializer,
)
from .worker import enqueue_pull

logger = logging.getLogger(__name__)


class ImagePullJobListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/hosts/{host_id}/images/pull/   → list all pull jobs for this host
    POST /api/hosts/{host_id}/images/pull/   → enqueue a background image pull
    """

    permission_classes = [IsAuthenticated, IsAdminOrHostOwner]

    def get_host(self):
        return get_object_or_404(Host, pk=self.kwargs["host_id"])

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ImagePullJobCreateSerializer
        return ImagePullJobSerializer

    def get_queryset(self):
        return (
            ImagePullJob.objects.filter(host_id=self.kwargs["host_id"])
            .select_related("host", "requested_by", "registry_credential")
        )

    def create(self, request, *args, **kwargs):
        host = self.get_host()

        # Check object-level permission (is user admin or host owner?)
        if request.user.role != "admin" and host.owner != request.user:
            return Response(
                {"detail": "You do not have permission to pull images on this host."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ImagePullJobCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        registry_cred = validated.get("registry_credential")

        job = ImagePullJob.objects.create(
            host=host,
            requested_by=request.user,
            image_ref=validated["image_ref"],
            registry_credential=registry_cred,
        )

        logger.info(
            "Image pull job created id=%s image=%s host=%s user=%s",
            job.id,
            job.image_ref,
            host.name,
            request.user.username,
        )

        # Fire the background worker
        enqueue_pull(job.id)

        output_serializer = ImagePullJobSerializer(job)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ImagePullJobDetailCancelView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/hosts/{host_id}/images/pull/{job_id}/  → retrieve job status & progress
    DELETE /api/hosts/{host_id}/images/pull/{job_id}/  → cancel a PENDING job (admin only)
    """

    serializer_class = ImagePullJobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    lookup_url_kwarg = "job_id"

    def get_queryset(self):
        return (
            ImagePullJob.objects.filter(host_id=self.kwargs["host_id"])
            .select_related("host", "requested_by", "registry_credential")
        )

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()

        # Only admins can cancel
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can cancel pull jobs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if job.status != ImagePullJob.Status.PENDING:
            return Response(
                {"detail": f"Cannot cancel a job with status '{job.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        job.status = ImagePullJob.Status.CANCELLED
        job.save(update_fields=["status"])
        logger.info(
            "Pull job cancelled id=%s cancelled_by=%s",
            job.id,
            request.user.username,
        )

        return Response(
            {"detail": "Pull job cancelled.", "id": str(job.id)},
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------------- #
# Image Inspect view
# --------------------------------------------------------------------------- #


class ImageInspectView(APIView):
    """
    GET /api/hosts/{host_id}/images/inspect/?image_ref=<image_ref>

    Connects to the Docker daemon on the specified host, inspects the
    given image, and returns:
      • ENV variables
      • ENTRYPOINT
      • CMD
      • Total size
      • Architecture / OS
      • Exposed ports
      • Full layer history
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, host_id):
        host = get_object_or_404(Host, pk=host_id)

        image_ref = request.query_params.get("image_ref")
        if not image_ref:
            return Response(
                {"detail": "Query parameter 'image_ref' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Connect to the Docker daemon on the target host
        base_url = f"tcp://{host.hostname}:{host.port}"
        try:
            client = docker.DockerClient(base_url=base_url, timeout=30)
        except docker.errors.DockerException as exc:
            logger.error(
                "Cannot connect to Docker daemon on host %s: %s",
                host.name,
                exc,
            )
            return Response(
                {"detail": f"Cannot connect to Docker daemon: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Inspect the image
        try:
            image = client.images.get(image_ref)
        except docker.errors.ImageNotFound:
            return Response(
                {"detail": f"Image '{image_ref}' not found on host '{host.name}'."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except docker.errors.APIError as exc:
            logger.error(
                "Docker API error inspecting image %s on host %s: %s",
                image_ref,
                host.name,
                exc,
            )
            return Response(
                {"detail": f"Docker API error: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        attrs = image.attrs  # raw inspect dict from Docker daemon
        config = attrs.get("Config") or {}

        # Retrieve the image history (layer list)
        try:
            history_raw = image.history()
        except docker.errors.APIError as exc:
            logger.warning(
                "Failed to get history for image %s: %s", image_ref, exc
            )
            history_raw = []

        layers = [
            {
                "created": entry.get("Created", ""),
                "created_by": entry.get("CreatedBy", ""),
                "size": entry.get("Size", 0),
                "comment": entry.get("Comment", ""),
                "tags": entry.get("Tags") or [],
            }
            for entry in history_raw
        ]

        inspect_data = {
            "image_id": attrs.get("Id", ""),
            "repo_tags": attrs.get("RepoTags") or [],
            "repo_digests": attrs.get("RepoDigests") or [],
            "size": attrs.get("Size", 0),
            "virtual_size": attrs.get("VirtualSize"),
            "created": attrs.get("Created", ""),
            "architecture": attrs.get("Architecture", ""),
            "os": attrs.get("Os", ""),
            "env": config.get("Env") or [],
            "entrypoint": config.get("Entrypoint"),
            "cmd": config.get("Cmd"),
            "exposed_ports": config.get("ExposedPorts") or {},
            "layers": layers,
        }

        serializer = ImageInspectSerializer(inspect_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
