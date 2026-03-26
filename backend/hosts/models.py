from django.conf import settings
from django.db import models


class Host(models.Model):
    name = models.CharField(max_length=120)
    hostname = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=2375)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hosts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.hostname}:{self.port})"
