from rest_framework import serializers

from .models import ImagePullJob


class ImagePullJobSerializer(serializers.ModelSerializer):
    """Read serializer for listing / retrieving pull jobs."""

    requested_by = serializers.ReadOnlyField(source="requested_by.username")
    host_name = serializers.ReadOnlyField(source="host.name")
    registry_alias = serializers.ReadOnlyField(
        source="registry_credential.alias", default=None
    )

    class Meta:
        model = ImagePullJob
        fields = [
            "id",
            "host",
            "host_name",
            "requested_by",
            "image_ref",
            "registry_credential",
            "registry_alias",
            "status",
            "progress_log",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "host",
            "requested_by",
            "status",
            "progress_log",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        ]


class ImagePullJobCreateSerializer(serializers.Serializer):
    """
    Accepts the image reference and an optional registry credential to
    enqueue a pull job.
    """

    image_ref = serializers.CharField(max_length=500)
    registry_credential = serializers.UUIDField(required=False, allow_null=True)

    def validate_registry_credential(self, value):
        """Ensure the credential exists and belongs to the requesting user."""
        if value is None:
            return None
        from registries.models import RegistryCredential

        user = self.context["request"].user
        try:
            return RegistryCredential.objects.get(pk=value, owner=user)
        except RegistryCredential.DoesNotExist:
            raise serializers.ValidationError(
                "Registry credential not found or not owned by you."
            )


# --------------------------------------------------------------------------- #
# Image Inspect serializers
# --------------------------------------------------------------------------- #


class ImageLayerSerializer(serializers.Serializer):
    """One layer from an image's history."""

    created = serializers.CharField(allow_null=True)
    created_by = serializers.CharField(allow_blank=True, allow_null=True)
    size = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True, default="")
    tags = serializers.ListField(
        child=serializers.CharField(), allow_empty=True, default=list
    )


class ImageInspectSerializer(serializers.Serializer):
    """
    Structured response for the image inspect endpoint.

    Returns the image's ENV variables, ENTRYPOINT, total size,
    and layer history.
    """

    image_id = serializers.CharField()
    repo_tags = serializers.ListField(
        child=serializers.CharField(), allow_empty=True, default=list
    )
    repo_digests = serializers.ListField(
        child=serializers.CharField(), allow_empty=True, default=list
    )
    size = serializers.IntegerField(help_text="Total image size in bytes")
    virtual_size = serializers.IntegerField(
        help_text="Virtual size in bytes", required=False, allow_null=True
    )
    created = serializers.CharField(help_text="ISO 8601 creation timestamp")
    architecture = serializers.CharField(allow_blank=True, default="")
    os = serializers.CharField(allow_blank=True, default="")
    env = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        default=list,
        help_text="Environment variables set in the image",
    )
    entrypoint = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        allow_null=True,
        default=None,
        help_text="Image ENTRYPOINT as a list of strings",
    )
    cmd = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        allow_null=True,
        default=None,
        help_text="Default CMD",
    )
    exposed_ports = serializers.DictField(
        allow_empty=True,
        default=dict,
        help_text="Ports exposed by the image",
    )
    layers = ImageLayerSerializer(many=True, help_text="Layer history")
