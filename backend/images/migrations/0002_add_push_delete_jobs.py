# Generated migration for ImagePushJob and ImageDeleteJob models

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0001_initial'),
        ('hosts', '0001_initial'),
        ('registries', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ImagePushJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source_image_ref', models.CharField(help_text='Local image reference to push, e.g. nginx:1.25-alpine', max_length=500)),
                ('target_image_ref', models.CharField(help_text='Target image reference in registry, e.g. myregistry.com/myapp:v1.0', max_length=500)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('TAGGING', 'Tagging'), ('PUSHING', 'Pushing'), ('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20)),
                ('progress_log', models.TextField(blank=True, default='', help_text='Streamed JSON progress lines from Docker daemon')),
                ('error_message', models.TextField(blank=True, help_text='Error detail if status is FAILED', null=True)),
                ('started_at', models.DateTimeField(blank=True, help_text='When the background worker began the push', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When the push finished or failed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image_push_jobs', to='hosts.host')),
                ('registry_credential', models.ForeignKey(blank=True, help_text='Credential used for authentication with the registry', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='image_push_jobs', to='registries.registrycredential')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image_push_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ImageDeleteJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('delete_mode', models.CharField(choices=[('SPECIFIC', 'Delete specific image(s)'), ('UNUSED', 'Prune all unused images')], default='SPECIFIC', help_text='Whether to delete specific image(s) or prune all unused', max_length=20)),
                ('image_refs', models.TextField(blank=True, help_text='Comma-separated list of image references to delete (for SPECIFIC mode)')),
                ('force', models.BooleanField(default=False, help_text='Force delete even if image is in use')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('DELETING', 'Deleting'), ('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20)),
                ('progress_log', models.TextField(blank=True, default='', help_text='Progress information from Docker daemon')),
                ('error_message', models.TextField(blank=True, help_text='Error detail if status is FAILED', null=True)),
                ('deleted_count', models.IntegerField(default=0, help_text='Number of images deleted')),
                ('space_freed_bytes', models.BigIntegerField(default=0, help_text='Bytes of storage freed')),
                ('started_at', models.DateTimeField(blank=True, help_text='When the background worker began the deletion', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When the deletion finished or failed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image_delete_jobs', to='hosts.host')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image_delete_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
