from django.contrib import admin

from .models import Host


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "hostname", "port", "owner")
    search_fields = ("name", "hostname", "owner__username")
