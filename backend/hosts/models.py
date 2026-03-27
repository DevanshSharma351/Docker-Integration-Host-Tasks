import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from encrypted_fields import EncryptedTextField

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True)
    avatar_url = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile({self.user.username})"


class Host(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alias = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()
    ssh_credentials = ssh_credentials = EncryptedTextField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='hosts_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.alias} ({self.ip_address}:{self.port})"


class UserHostRole(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('HOST_OWNER', 'Host Owner'),
        ('VIEWER', 'Viewer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='host_roles')
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='user_roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='roles_assigned')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'host')  # one role per user per host

    def __str__(self):
        return f"{self.user.username} -> {self.host.alias} [{self.role}]"