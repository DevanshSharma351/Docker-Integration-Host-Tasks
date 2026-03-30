from rest_framework import serializers

from .models import RegistryCredential


class RegistryCredentialSerializer(serializers.ModelSerializer):
    """Read / list serializer — never exposes the raw token."""

    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = RegistryCredential
        fields = [
            "id",
            "owner",
            "alias",
            "registry_url",
            "username",
            "is_default",
            "last_verified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "last_verified_at",
            "created_at",
            "updated_at",
        ]


class RegistryCredentialCreateSerializer(serializers.ModelSerializer):
    """Create serializer — accepts a plain-text ``token`` field."""

    token = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = RegistryCredential
        fields = [
            "id",
            "alias",
            "registry_url",
            "username",
            "token",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> RegistryCredential:
        token = validated_data.pop("token")
        credential = RegistryCredential(**validated_data)
        credential.token = token  # encrypts via the property setter
        credential.save()
        return credential


class RegistryCredentialUpdateSerializer(serializers.ModelSerializer):
    """Update serializer — token is optional on update."""

    token = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
    )

    class Meta:
        model = RegistryCredential
        fields = [
            "alias",
            "registry_url",
            "username",
            "token",
            "is_default",
        ]

    def update(self, instance: RegistryCredential, validated_data: dict) -> RegistryCredential:
        token = validated_data.pop("token", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if token is not None:
            instance.token = token  # re-encrypts
        instance.save()
        return instance
