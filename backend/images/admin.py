from django.contrib import admin

from .models import ImagePullJob


@admin.register(ImagePullJob)
class ImagePullJobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "image_ref",
        "host",
        "requested_by",
        "status",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["image_ref", "host__name", "requested_by__username"]
    readonly_fields = [
        "id",
        "progress_log",
        "error_message",
        "started_at",
        "completed_at",
        "created_at",
    ]
