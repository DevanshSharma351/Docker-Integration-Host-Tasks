import uuid

from django.conf import settings
from django.db import models


class ImagePullJob(models.Model):
    """Tracks background image pull operations."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PULLING = "PULLING", "Pulling"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        "hosts.Host",
        on_delete=models.CASCADE,
        related_name="image_pull_jobs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_pull_jobs",
    )
    image_ref = models.CharField(
        max_length=500,
        help_text="Full image reference, e.g. nginx:1.25-alpine",
    )
    registry_credential = models.ForeignKey(
        "registries.RegistryCredential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="image_pull_jobs",
        help_text="Credential used for private registries",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    progress_log = models.TextField(
        blank=True,
        default="",
        help_text="Streamed JSON progress lines from Docker daemon",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error detail if status is FAILED",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the background worker began the pull",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the pull finished or failed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PullJob({self.image_ref}) [{self.status}]"
