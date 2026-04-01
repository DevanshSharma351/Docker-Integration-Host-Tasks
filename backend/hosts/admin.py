from django.contrib import admin

from .models import Host


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ("id", "alias", "ip_address", "port", "created_by")
    search_fields = ("alias", "ip_address", "created_by__username")
