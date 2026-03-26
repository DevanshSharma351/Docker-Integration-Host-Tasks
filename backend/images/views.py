import logging
import json
import tarfile
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

import docker
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hosts.models import Host

from .models import ImagePullJob, ImagePushJob, ImageDeleteJob
from .permissions import IsAdminOrHostOwner
from .serializers import (
    ImageBuildRequestSerializer,
    ImageInspectSerializer,
    ImagePullJobCreateSerializer,
    ImagePullJobSerializer,
    ImagePushJobCreateSerializer,
    ImagePushJobSerializer,
    ImageDeleteJobCreateSerializer,
    ImageDeleteJobSerializer,
)
from .worker import enqueue_pull, enqueue_push, enqueue_delete

logger = logging.getLogger(__name__)


def _is_local_hostname(hostname: str) -> bool:
    value = (hostname or "").strip().lower()
    return value in {"localhost", "127.0.0.1", "::1"}


def _get_docker_client_for_host(host: Host, timeout: int):
    # Prefer local socket for localhost hosts (OrbStack / Docker Desktop on macOS)
    if _is_local_hostname(host.hostname):
        try:
            return docker.from_env(timeout=timeout)
        except docker.errors.DockerException:
            pass

    return docker.DockerClient(
        base_url=f"tcp://{host.hostname}:{host.port}",
        timeout=timeout,
    )


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


class ImageBuildStreamView(APIView):
    """
    POST /api/hosts/{host_id}/images/build/

    Accepts either:
      - dockerfile: raw Dockerfile string
      - context_zip: uploaded ZIP file with build context

    Streams Docker build output back to the client as NDJSON.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _safe_zip_member(name: str) -> bool:
        path = PurePosixPath(name)
        if path.is_absolute():
            return False
        if any(part in {"..", ""} for part in path.parts):
            return False
        return True

    def _build_context_tar(
        self,
        dockerfile_text: str,
        context_zip,
    ) -> BytesIO:
        tar_buffer = BytesIO()

        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            if context_zip:
                context_zip.seek(0)
                with zipfile.ZipFile(context_zip) as archive:
                    for member in archive.infolist():
                        if member.is_dir():
                            continue
                        if not self._safe_zip_member(member.filename):
                            continue

                        content = archive.read(member.filename)
                        tar_info = tarfile.TarInfo(name=member.filename)
                        tar_info.size = len(content)
                        tar.addfile(tar_info, BytesIO(content))

            if dockerfile_text:
                dockerfile_bytes = dockerfile_text.encode("utf-8")
                dockerfile_info = tarfile.TarInfo(name="Dockerfile")
                dockerfile_info.size = len(dockerfile_bytes)
                tar.addfile(dockerfile_info, BytesIO(dockerfile_bytes))

        tar_buffer.seek(0)
        return tar_buffer

    def post(self, request, host_id):
        host = get_object_or_404(Host, pk=host_id)

        if request.user.role != "admin" and host.owner != request.user:
            return Response(
                {"detail": "You do not have permission to build images on this host."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ImageBuildRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dockerfile_text = (data.get("dockerfile") or "").strip()
        context_zip = data.get("context_zip")
        tag = (data.get("tag") or "").strip() or None
        pull = data.get("pull", False)
        nocache = data.get("nocache", False)

        try:
            context_tar = self._build_context_tar(
                dockerfile_text=dockerfile_text,
                context_zip=context_zip,
            )
        except zipfile.BadZipFile:
            return Response(
                {"detail": "context_zip must be a valid ZIP archive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = _get_docker_client_for_host(host=host, timeout=600)
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

        def stream_output():
            try:
                image, logs = client.images.build(
                    fileobj=context_tar,
                    custom_context=True,
                    rm=True,
                    pull=pull,
                    nocache=nocache,
                    tag=tag,
                )
                for chunk in logs:
                    yield f"{json.dumps(chunk)}\n"

                yield json.dumps({"status": "done", "image_id": image.id}) + "\n"
            except docker.errors.BuildError as exc:
                logger.warning("Image build failed on host %s: %s", host.name, exc)
                yield json.dumps({"error": "build_failed", "detail": str(exc)}) + "\n"
            except docker.errors.APIError as exc:
                logger.warning("Docker API build error on host %s: %s", host.name, exc)
                yield (
                    json.dumps({"error": "docker_api_error", "detail": str(exc)})
                    + "\n"
                )
            except Exception as exc:
                logger.exception("Unexpected image build error on host %s", host.name)
                yield (
                    json.dumps({"error": "unexpected_error", "detail": str(exc)})
                    + "\n"
                )

        return StreamingHttpResponse(
            streaming_content=stream_output(),
            content_type="application/x-ndjson",
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
        try:
            client = _get_docker_client_for_host(host=host, timeout=30)
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


# --------------------------------------------------------------------------- #
# Image Push/Tag views
# --------------------------------------------------------------------------- #


class ImagePushJobListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/hosts/{host_id}/images/push/   → list all push jobs for this host
    POST /api/hosts/{host_id}/images/push/   → enqueue a background image tag + push
    """

    permission_classes = [IsAuthenticated, IsAdminOrHostOwner]

    def get_host(self):
        return get_object_or_404(Host, pk=self.kwargs["host_id"])

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ImagePushJobCreateSerializer
        return ImagePushJobSerializer

    def get_queryset(self):
        return (
            ImagePushJob.objects.filter(host_id=self.kwargs["host_id"])
            .select_related("host", "requested_by", "registry_credential")
        )

    def create(self, request, *args, **kwargs):
        host = self.get_host()

        # Check object-level permission (is user admin or host owner?)
        if request.user.role != "admin" and host.owner != request.user:
            return Response(
                {"detail": "You do not have permission to push images on this host."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ImagePushJobCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        registry_cred = validated.get("registry_credential")

        job = ImagePushJob.objects.create(
            host=host,
            requested_by=request.user,
            source_image_ref=validated["source_image_ref"],
            target_image_ref=validated["target_image_ref"],
            registry_credential=registry_cred,
        )

        logger.info(
            "Image push job created id=%s source=%s target=%s host=%s user=%s",
            job.id,
            job.source_image_ref,
            job.target_image_ref,
            host.name,
            request.user.username,
        )

        # Fire the background worker
        enqueue_push(job.id)

        output_serializer = ImagePushJobSerializer(job)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ImagePushJobDetailCancelView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/hosts/{host_id}/images/push/{job_id}/  → retrieve job status & progress
    DELETE /api/hosts/{host_id}/images/push/{job_id}/  → cancel a PENDING job (admin only)
    """

    serializer_class = ImagePushJobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    lookup_url_kwarg = "job_id"

    def get_queryset(self):
        return (
            ImagePushJob.objects.filter(host_id=self.kwargs["host_id"])
            .select_related("host", "requested_by", "registry_credential")
        )

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()

        # Only admins can cancel
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can cancel push jobs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if job.status != ImagePushJob.Status.PENDING:
            return Response(
                {"detail": f"Cannot cancel a job with status '{job.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        job.status = ImagePushJob.Status.CANCELLED
        job.save(update_fields=["status"])
        logger.info(
            "Push job cancelled id=%s cancelled_by=%s",
            job.id,
            request.user.username,
        )

        return Response(
            {"detail": "Push job cancelled.", "id": str(job.id)},
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------------- #
# Image Delete/Prune views
# --------------------------------------------------------------------------- #


class ImageDeleteJobListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/hosts/{host_id}/images/delete/  → list all delete jobs for this host
    POST /api/hosts/{host_id}/images/delete/  → enqueue a background image delete
    """

    permission_classes = [IsAuthenticated, IsAdminOrHostOwner]

    def get_host(self):
        return get_object_or_404(Host, pk=self.kwargs["host_id"])

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ImageDeleteJobCreateSerializer
        return ImageDeleteJobSerializer

    def get_queryset(self):
        return ImageDeleteJob.objects.filter(host_id=self.kwargs["host_id"]).select_related(
            "host", "requested_by"
        )

    def create(self, request, *args, **kwargs):
        host = self.get_host()

        # Check object-level permission (is user admin or host owner?)
        if request.user.role != "admin" and host.owner != request.user:
            return Response(
                {"detail": "You do not have permission to delete images on this host."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ImageDeleteJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data

        job = ImageDeleteJob.objects.create(
            host=host,
            requested_by=request.user,
            delete_mode=validated["delete_mode"],
            image_refs=validated.get("image_refs", ""),
            force=validated.get("force", False),
        )

        logger.info(
            "Image delete job created id=%s mode=%s host=%s user=%s",
            job.id,
            job.delete_mode,
            host.name,
            request.user.username,
        )

        # Fire the background worker
        enqueue_delete(job.id)

        output_serializer = ImageDeleteJobSerializer(job)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ImageDeleteJobDetailCancelView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/hosts/{host_id}/images/delete/{job_id}/  → retrieve job status
    DELETE /api/hosts/{host_id}/images/delete/{job_id}/  → cancel a PENDING job (admin only)
    """

    serializer_class = ImageDeleteJobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    lookup_url_kwarg = "job_id"

    def get_queryset(self):
        return ImageDeleteJob.objects.filter(host_id=self.kwargs["host_id"]).select_related(
            "host", "requested_by"
        )

    def destroy(self, request, *args, **kwargs):
        job = self.get_object()

        # Only admins can cancel
        if request.user.role != "admin":
            return Response(
                {"detail": "Only admins can cancel delete jobs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if job.status != ImageDeleteJob.Status.PENDING:
            return Response(
                {"detail": f"Cannot cancel a job with status '{job.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        job.status = ImageDeleteJob.Status.CANCELLED
        job.save(update_fields=["status"])
        logger.info(
            "Delete job cancelled id=%s cancelled_by=%s",
            job.id,
            request.user.username,
        )

        return Response(
            {"detail": "Delete job cancelled.", "id": str(job.id)},
            status=status.HTTP_200_OK,
        )
