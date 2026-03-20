import uuid
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


# ── HOST STUB ─────────────────────────────────────────────────────────────
# Temporary model for local development.
# When Module 1's 'hosts' app is merged:
#   1. Delete this class
#   2. Change ForeignKey below from 'containers.Host' to 'hosts.Host'
#   3. Run makemigrations
# ─────────────────────────────────────────────────────────────────────────
class Host(models.Model):
    name       = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(default='127.0.0.1')
    port       = models.IntegerField(default=2375)

    class Meta:
        app_label = 'containers'

    def __str__(self):
        return f"{self.name} ({self.ip_address}:{self.port})"


# ── CONTAINER RECORD ──────────────────────────────────────────────────────
class ContainerRecord(models.Model):

    class Status(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        RUNNING = 'RUNNING', 'Running'
        PAUSED  = 'PAUSED',  'Paused'
        STOPPED = 'STOPPED', 'Stopped'
        KILLED  = 'KILLED',  'Killed'
        REMOVED = 'REMOVED', 'Removed'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host          = models.ForeignKey(
                        'containers.Host',
                        on_delete=models.CASCADE,
                        related_name='containers'
                    )
    created_by    = models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.SET_NULL,
                        null=True,
                        related_name='created_containers'
                    )
    container_id  = models.CharField(max_length=72, unique=True)
    name          = models.CharField(max_length=255)
    image_ref     = models.CharField(max_length=500)
    status        = models.CharField(
                        max_length=20,
                        choices=Status.choices,
                        default=Status.CREATED
                    )
    port_bindings = models.JSONField(default=dict, blank=True)
    environment   = models.JSONField(default=dict, blank=True)
    volumes       = models.JSONField(default=list, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.status}]"


# ── CONTAINER LIFECYCLE EVENT ─────────────────────────────────────────────
class ContainerLifecycleEvent(models.Model):

    class Action(models.TextChoices):
        CREATE     = 'CREATE',     'Create'
        START      = 'START',      'Start'
        STOP       = 'STOP',       'Stop'
        RESTART    = 'RESTART',    'Restart'
        KILL       = 'KILL',       'Kill'
        PAUSE      = 'PAUSE',      'Pause'
        UNPAUSE    = 'UNPAUSE',    'Unpause'
        REMOVE     = 'REMOVE',     'Remove'
        EXEC_OPEN  = 'EXEC_OPEN',  'Exec Open'
        EXEC_CLOSE = 'EXEC_CLOSE', 'Exec Close'

    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        FAILED  = 'FAILED',  'Failed'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    container     = models.ForeignKey(
                        ContainerRecord,
                        on_delete=models.CASCADE,
                        related_name='events'
                    )
    triggered_by  = models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.SET_NULL,
                        null=True
                    )
    action        = models.CharField(max_length=20, choices=Action.choices)
    status        = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(null=True, blank=True)
    timestamp     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} → {self.status} @ {self.timestamp}"


# ── EXEC TICKET ───────────────────────────────────────────────────────────
class ExecTicket(models.Model):

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    container  = models.ForeignKey(
                     ContainerRecord,
                     on_delete=models.CASCADE,
                     related_name='exec_tickets'
                 )
    issued_to  = models.ForeignKey(
                     settings.AUTH_USER_MODEL,
                     on_delete=models.CASCADE
                 )
    ticket     = models.CharField(max_length=64, unique=True)
    is_used    = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['ticket'])]

    @classmethod
    def issue(cls, container, user):
        """
        Always use this factory method instead of .objects.create() directly.
        Generates a cryptographically secure token and sets 30s expiry.
        """
        return cls.objects.create(
            container=container,
            issued_to=user,
            ticket=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(seconds=30),
        )

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def consume(self):
        """Call exactly once when WebSocket connects successfully."""
        self.is_used = True
        self.save(update_fields=['is_used'])

    def __str__(self):
        return f"Ticket for {self.container.name} ({'used' if self.is_used else 'valid'})"