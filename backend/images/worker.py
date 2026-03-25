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
        base_url = f"tcp://{host.hostname}:{host.port}"
        client = docker.DockerClient(base_url=base_url, timeout=300)

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
