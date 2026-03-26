"""
Background worker that pulls Docker images in a separate thread.

Uses Python threading (no Celery required). Each pull job runs in its own
daemon thread, streams progress from the Docker daemon, and updates the
ImagePullJob model as it progresses.
"""

import json
import logging
import threading

import docker
from django.utils import timezone

logger = logging.getLogger(__name__)


def _is_local_hostname(hostname: str) -> bool:
    value = (hostname or "").strip().lower()
    return value in {"localhost", "127.0.0.1", "::1"}


def _do_pull(job_id: str) -> None:
    """Execute the image pull in a background thread."""
    # Import here to avoid circular imports & ensure Django is ready
    from .models import ImagePullJob

    try:
        job = ImagePullJob.objects.select_related(
            "host", "registry_credential"
        ).get(pk=job_id)
    except ImagePullJob.DoesNotExist:
        logger.error("Pull job %s not found, aborting.", job_id)
        return

    # If the job was cancelled before the thread started, bail out
    if job.status == ImagePullJob.Status.CANCELLED:
        logger.info("Pull job %s was cancelled before starting.", job_id)
        return

    # Mark as PULLING
    job.status = ImagePullJob.Status.PULLING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        # Connect to the Docker daemon on the target host
        host = job.host
        if _is_local_hostname(host.hostname):
            try:
                client = docker.from_env(timeout=300)
            except docker.errors.DockerException:
                client = docker.DockerClient(
                    base_url=f"tcp://{host.hostname}:{host.port}",
                    timeout=300,
                )
        else:
            client = docker.DockerClient(
                base_url=f"tcp://{host.hostname}:{host.port}",
                timeout=300,
            )

        # Build auth_config if a credential is linked
        auth_config = None
        if job.registry_credential:
            cred = job.registry_credential
            auth_config = {
                "username": cred.username,
                "password": cred.token,  # decrypted via property
            }

        # Parse image name and tag
        if ":" in job.image_ref and "@" not in job.image_ref:
            repository, tag = job.image_ref.rsplit(":", 1)
        else:
            repository = job.image_ref
            tag = None

        # Stream the pull and capture progress
        progress_lines = []
        pull_kwargs = {"repository": repository, "stream": True, "decode": True}
        if tag:
            pull_kwargs["tag"] = tag
        if auth_config:
            pull_kwargs["auth_config"] = auth_config

        for chunk in client.api.pull(**pull_kwargs):
            line = json.dumps(chunk)
            progress_lines.append(line)

            # Periodically flush progress to DB (every 20 lines)
            if len(progress_lines) % 20 == 0:
                job.progress_log = "\n".join(progress_lines)
                job.save(update_fields=["progress_log"])

        # Final progress flush
        job.progress_log = "\n".join(progress_lines)
        job.status = ImagePullJob.Status.SUCCESS
        job.completed_at = timezone.now()
        job.save(update_fields=["progress_log", "status", "completed_at"])

        logger.info(
            "Pull job %s completed successfully image=%s host=%s",
            job.id,
            job.image_ref,
            host.name,
        )

    except docker.errors.APIError as exc:
        explanation = getattr(exc, "explanation", None) or str(exc)
        job.status = ImagePullJob.Status.FAILED
        job.error_message = explanation
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        logger.warning("Pull job %s failed: %s", job.id, explanation)

    except Exception as exc:
        job.status = ImagePullJob.Status.FAILED
        job.error_message = str(exc)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        logger.exception("Pull job %s unexpected error", job.id)


def enqueue_pull(job_id: str) -> None:
    """
    Spawn a daemon thread to pull the image.
    The thread will exit automatically when the pull completes or fails.
    """
    thread = threading.Thread(
        target=_do_pull,
        args=(str(job_id),),
        name=f"pull-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Enqueued pull job %s in thread %s", job_id, thread.name)


# --------------------------------------------------------------------------- #
# Image Push Operations
# --------------------------------------------------------------------------- #


def _do_push(job_id: str) -> None:
    """Execute the image tag and push in a background thread."""
    from .models import ImagePushJob

    try:
        job = ImagePushJob.objects.select_related(
            "host", "registry_credential"
        ).get(pk=job_id)
    except ImagePushJob.DoesNotExist:
        logger.error("Push job %s not found, aborting.", job_id)
        return

    # If the job was cancelled before the thread started, bail out
    if job.status == ImagePushJob.Status.CANCELLED:
        logger.info("Push job %s was cancelled before starting.", job_id)
        return

    # Mark as TAGGING
    job.status = ImagePushJob.Status.TAGGING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        # Connect to the Docker daemon on the target host
        host = job.host
        if _is_local_hostname(host.hostname):
            try:
                client = docker.from_env(timeout=300)
            except docker.errors.DockerException:
                client = docker.DockerClient(
                    base_url=f"tcp://{host.hostname}:{host.port}",
                    timeout=300,
                )
        else:
            client = docker.DockerClient(
                base_url=f"tcp://{host.hostname}:{host.port}",
                timeout=300,
            )

        # Step 1: Tag the image
        try:
            image = client.images.get(job.source_image_ref)
            image.tag(job.target_image_ref)
            progress = {
                "status": "tagged",
                "source": job.source_image_ref,
                "target": job.target_image_ref,
            }
            job.progress_log = json.dumps(progress)
            job.status = ImagePushJob.Status.PUSHING
            job.save(update_fields=["progress_log", "status"])
            logger.info(
                "Tagged image %s as %s on host %s",
                job.source_image_ref,
                job.target_image_ref,
                host.name,
            )
        except docker.errors.ImageNotFound:
            job.status = ImagePushJob.Status.FAILED
            job.error_message = f"Source image '{job.source_image_ref}' not found on host"
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "error_message", "completed_at"])
            logger.warning(
                "Push job %s failed: image not found %s", job.id, job.source_image_ref
            )
            return

        # Step 2: Push the tagged image
        auth_config = None
        if job.registry_credential:
            cred = job.registry_credential
            auth_config = {
                "username": cred.username,
                "password": cred.token,  # decrypted via property
            }

        # Stream the push and capture progress
        progress_lines = []
        push_kwargs = {
            "repository": job.target_image_ref,
            "stream": True,
            "decode": True,
        }
        if auth_config:
            push_kwargs["auth_config"] = auth_config

        for chunk in client.api.push(**push_kwargs):
            line = json.dumps(chunk)
            progress_lines.append(line)

            # Periodically flush progress to DB (every 20 lines)
            if len(progress_lines) % 20 == 0:
                job.progress_log = "\n".join(progress_lines)
                job.save(update_fields=["progress_log"])

        # Final progress flush
        job.progress_log = "\n".join(progress_lines)
        job.status = ImagePushJob.Status.SUCCESS
        job.completed_at = timezone.now()
        job.save(update_fields=["progress_log", "status", "completed_at"])

        logger.info(
            "Push job %s completed successfully source=%s target=%s host=%s",
            job.id,
            job.source_image_ref,
            job.target_image_ref,
            host.name,
        )

    except docker.errors.APIError as exc:
        explanation = getattr(exc, "explanation", None) or str(exc)
        job.status = ImagePushJob.Status.FAILED
        job.error_message = explanation
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        logger.warning("Push job %s failed: %s", job.id, explanation)

    except Exception as exc:
        job.status = ImagePushJob.Status.FAILED
        job.error_message = str(exc)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        logger.exception("Push job %s unexpected error", job.id)


def enqueue_push(job_id: str) -> None:
    """
    Spawn a daemon thread to tag and push the image.
    The thread will exit automatically when the push completes or fails.
    """
    thread = threading.Thread(
        target=_do_push,
        args=(str(job_id),),
        name=f"push-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Enqueued push job %s in thread %s", job_id, thread.name)


# --------------------------------------------------------------------------- #
# Image Delete/Prune Operations
# --------------------------------------------------------------------------- #


def _do_delete(job_id: str) -> None:
    """Execute the image deletion/pruning in a background thread."""
    from .models import ImageDeleteJob

    try:
        job = ImageDeleteJob.objects.select_related("host").get(pk=job_id)
    except ImageDeleteJob.DoesNotExist:
        logger.error("Delete job %s not found, aborting.", job_id)
        return

    # If the job was cancelled before the thread started, bail out
    if job.status == ImageDeleteJob.Status.CANCELLED:
        logger.info("Delete job %s was cancelled before starting.", job_id)
        return

    # Mark as DELETING
    job.status = ImageDeleteJob.Status.DELETING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        # Connect to the Docker daemon on the target host
        host = job.host
        if _is_local_hostname(host.hostname):
            try:
                client = docker.from_env(timeout=300)
            except docker.errors.DockerException:
                client = docker.DockerClient(
                    base_url=f"tcp://{host.hostname}:{host.port}",
                    timeout=300,
                )
        else:
            client = docker.DockerClient(
                base_url=f"tcp://{host.hostname}:{host.port}",
                timeout=300,
            )

        deleted_count = 0
        space_freed = 0
        progress_log = []

        if job.delete_mode == ImageDeleteJob.DeleteMode.UNUSED:
            # Prune all unused images
            try:
                result = client.images.prune(filters={"dangling": False})
                deleted_count = len(result.get("ImagesDeleted") or [])
                space_freed = result.get("SpaceReclaimed", 0)

                progress = {
                    "status": "pruned",
                    "mode": "unused",
                    "deleted": deleted_count,
                    "space_freed": space_freed,
                }
                progress_log.append(json.dumps(progress))
                logger.info(
                    "Pruned %d unused images on host %s, freed %d bytes",
                    deleted_count,
                    host.name,
                    space_freed,
                )
            except docker.errors.APIError as exc:
                raise Exception(f"Prune failed: {exc}")

        else:  # SPECIFIC mode
            # Delete specific images
            image_refs = [
                ref.strip() for ref in job.image_refs.split(",") if ref.strip()
            ]

            for image_ref in image_refs:
                try:
                    # Get image info before deletion (to get size)
                    try:
                        image = client.images.get(image_ref)
                        image_size = image.attrs.get("Size", 0)
                    except docker.errors.ImageNotFound:
                        logger.warning(
                            "Image %s not found for deletion on host %s",
                            image_ref,
                            host.name,
                        )
                        progress = {
                            "status": "warning",
                            "image": image_ref,
                            "reason": "not_found",
                        }
                        progress_log.append(json.dumps(progress))
                        continue

                    # Delete the image
                    client.images.remove(image_ref, force=job.force)
                    deleted_count += 1
                    space_freed += image_size

                    progress = {
                        "status": "deleted",
                        "image": image_ref,
                        "size": image_size,
                    }
                    progress_log.append(json.dumps(progress))
                    logger.info(
                        "Deleted image %s on host %s (size: %d bytes)",
                        image_ref,
                        host.name,
                        image_size,
                    )

                except docker.errors.APIError as exc:
                    explanation = getattr(exc, "explanation", None) or str(exc)
                    logger.warning(
                        "Delete job %s failed to delete %s: %s",
                        job.id,
                        image_ref,
                        explanation,
                    )
                    progress = {
                        "status": "error",
                        "image": image_ref,
                        "error": explanation,
                    }
                    progress_log.append(json.dumps(progress))

        # Final update
        job.progress_log = "\n".join(progress_log)
        job.deleted_count = deleted_count
        job.space_freed_bytes = space_freed
        job.status = ImageDeleteJob.Status.SUCCESS
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "progress_log",
                "deleted_count",
                "space_freed_bytes",
                "status",
                "completed_at",
            ]
        )

        logger.info(
            "Delete job %s completed: deleted %d images, freed %d bytes on host %s",
            job.id,
            deleted_count,
            space_freed,
            host.name,
        )

    except Exception as exc:
        job.status = ImageDeleteJob.Status.FAILED
        job.error_message = str(exc)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        logger.exception("Delete job %s unexpected error", job.id)


def enqueue_delete(job_id: str) -> None:
    """
    Spawn a daemon thread to delete images.
    The thread will exit automatically when deletion completes or fails.
    """
    thread = threading.Thread(
        target=_do_delete,
        args=(str(job_id),),
        name=f"delete-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Enqueued delete job %s in thread %s", job_id, thread.name)
