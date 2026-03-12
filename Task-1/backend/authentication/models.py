from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ADMIN = 'admin'
    HOST = 'host'
    VIEWER = 'viewer'
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (HOST, 'Host'),
        (VIEWER, 'Viewer'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=VIEWER)
    
    def __str__(self):
        return f"{self.username} ({self.role})"
