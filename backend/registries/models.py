import uuid
from django.conf import settings
from django.db import models

from .encryption import decrypt_token, encrypt_token


class RegistryCredential(models.Model):
    """Stores encrypted authentication credentials for a Docker registry."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registry_credentials",
    )
    alias = models.CharField(max_length=100, help_text="Human-readable label, e.g. 'My DockerHub'")
    registry_url = models.CharField(
        max_length=255,
        help_text="Registry endpoint, e.g. https://index.docker.io/v1/",
    )
    username = models.CharField(max_length=150, help_text="Registry login username")
    _encrypted_token = models.TextField(
        db_column="encrypted_token",
        help_text="Fernet-encrypted password or access token",
    )
    is_default = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("owner", "alias")

    # ---- token property (encrypt on write, decrypt on read) ---- #
    @property
    def token(self) -> str:
        """Return the decrypted token."""
        if not self._encrypted_token:
            return ""
        return decrypt_token(self._encrypted_token)

    @token.setter
    def token(self, value: str) -> None:
        """Encrypt and store *value*."""
        self._encrypted_token = encrypt_token(value)

    def __str__(self) -> str:
        return f"{self.alias} ({self.registry_url})"
