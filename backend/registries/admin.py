from django.contrib import admin

from .models import RegistryCredential


@admin.register(RegistryCredential)
class RegistryCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "alias", "registry_url", "username", "owner", "is_default", "last_verified_at", "updated_at")
    search_fields = ("alias", "registry_url", "username", "owner__username")
    list_filter = ("is_default",)
    readonly_fields = ("id", "created_at", "updated_at", "last_verified_at")
