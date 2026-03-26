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


class ImagePushJob(models.Model):
    """Tracks background image push operations to registries."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        TAGGING = "TAGGING", "Tagging"
        PUSHING = "PUSHING", "Pushing"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        "hosts.Host",
        on_delete=models.CASCADE,
        related_name="image_push_jobs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_push_jobs",
    )
    source_image_ref = models.CharField(
        max_length=500,
        help_text="Local image reference to push, e.g. nginx:1.25-alpine",
    )
    target_image_ref = models.CharField(
        max_length=500,
        help_text="Target image reference in registry, e.g. myregistry.com/myapp:v1.0",
    )
    registry_credential = models.ForeignKey(
        "registries.RegistryCredential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="image_push_jobs",
        help_text="Credential used for authentication with the registry",
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
        help_text="When the background worker began the push",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the push finished or failed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PushJob({self.source_image_ref} → {self.target_image_ref}) [{self.status}]"


class ImageDeleteJob(models.Model):
    """Tracks background image deletion/pruning operations."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DELETING = "DELETING", "Deleting"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    class DeleteMode(models.TextChoices):
        SPECIFIC = "SPECIFIC", "Delete specific image(s)"
        UNUSED = "UNUSED", "Prune all unused images"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        "hosts.Host",
        on_delete=models.CASCADE,
        related_name="image_delete_jobs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_delete_jobs",
    )
    delete_mode = models.CharField(
        max_length=20,
        choices=DeleteMode.choices,
        default=DeleteMode.SPECIFIC,
        help_text="Whether to delete specific image(s) or prune all unused",
    )
    image_refs = models.TextField(
        blank=True,
        help_text="Comma-separated list of image references to delete (for SPECIFIC mode)",
    )
    force = models.BooleanField(
        default=False,
        help_text="Force delete even if image is in use",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    progress_log = models.TextField(
        blank=True,
        default="",
        help_text="Progress information from Docker daemon",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error detail if status is FAILED",
    )
    deleted_count = models.IntegerField(
        default=0,
        help_text="Number of images deleted",
    )
    space_freed_bytes = models.BigIntegerField(
        default=0,
        help_text="Bytes of storage freed",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the background worker began the deletion",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the deletion finished or failed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        mode_label = self.get_delete_mode_display()
        return f"DeleteJob({mode_label}) [{self.status}]"
