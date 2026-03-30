from django.urls import path

from .views import (
    RegistryCredentialDetailView,
    RegistryCredentialListCreateView,
    RegistryCredentialVerifyView,
)

urlpatterns = [
    path("", RegistryCredentialListCreateView.as_view(), name="registry-list-create"),
    path("<uuid:pk>/", RegistryCredentialDetailView.as_view(), name="registry-detail"),
    path("<uuid:pk>/verify/", RegistryCredentialVerifyView.as_view(), name="registry-verify"),
]
