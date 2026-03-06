from django.db import models

class Todo(models.Model):
    LABEL_CHOICES = [
        ('Personal', 'Personal'),
        ('Work', 'Work'),
        ('Health', 'Health'),
        ('Learning', 'Learning'),
        ('Home', 'Home'),
        ('Errands', 'Errands'),
    ]

    title        = models.CharField(max_length=255)
    completed    = models.BooleanField(default=False)
    label        = models.CharField(max_length=50, choices=LABEL_CHOICES, default='Personal')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering=['-created_at']