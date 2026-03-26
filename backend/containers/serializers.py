from rest_framework import serializers


class ContainerCreateSerializer(serializers.Serializer):
    host_id = serializers.IntegerField(min_value=1)
    image_ref = serializers.CharField(max_length=500)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ports = serializers.CharField(required=False, allow_blank=True)
    command = serializers.CharField(required=False, allow_blank=True)

    def validate_ports(self, value):
        raw = (value or '').strip()
        if not raw:
            return {}

        parsed = {}
        parts = [item.strip() for item in raw.split(',') if item.strip()]
        for part in parts:
            if ':' not in part:
                raise serializers.ValidationError(
                    "Invalid port mapping format. Use host:container, e.g. 8080:80"
                )

            host_port, container_port = [segment.strip() for segment in part.split(':', 1)]
            if not host_port.isdigit() or not container_port.isdigit():
                raise serializers.ValidationError(
                    "Port values must be numeric, e.g. 8080:80"
                )

            parsed[f"{int(container_port)}/tcp"] = int(host_port)

        return parsed


class ContainerCreateResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    image = serializers.CharField()
    host_id = serializers.IntegerField()
