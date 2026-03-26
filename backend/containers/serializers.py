from rest_framework import serializers
from containers.models import (
    Host,
    ContainerRecord,
    ContainerLifecycleEvent,
)

class HostSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Host
        fields = ['id', 'name', 'ip_address', 'port']

class ContainerRecordSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = ContainerRecord
        fields = [
            'id', 'host', 'created_by',
            'container_id', 'name', 'image_ref', 'status',
            'port_bindings', 'environment', 'volumes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'container_id', 'status',
            'created_at', 'updated_at', 'created_by',
        ]

class ContainerRecordListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ContainerRecord
        fields = [
            'id', 'container_id', 'name',
            'image_ref', 'status', 'created_at',
        ]

class ContainerCreateSerializer(serializers.Serializer):
    image_ref     = serializers.CharField(max_length=500)
    name          = serializers.CharField(max_length=255)
    environment   = serializers.DictField(
                        child=serializers.CharField(),
                        required=False,
                        default=dict
                    )
    port_bindings = serializers.DictField(
                        required=False,
                        default=dict
                    )
    volumes       = serializers.ListField(
                        required=False,
                        default=list
                    )

class ContainerLifecycleEventSerializer(serializers.ModelSerializer):
    triggered_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = ContainerLifecycleEvent
        fields = [
            'id', 'action', 'status',
            'triggered_by', 'error_message', 'timestamp',
        ]
        read_only_fields = fields

class LifecycleActionResponseSerializer(serializers.Serializer):
    container_id = serializers.CharField()
    name         = serializers.CharField()
    action       = serializers.CharField()
    status       = serializers.CharField()
    timestamp    = serializers.DateTimeField()

class MemoryStatsSerializer(serializers.Serializer):
    usage_bytes  = serializers.IntegerField()
    limit_bytes  = serializers.IntegerField()
    percent      = serializers.FloatField()


class NetworkStatsSerializer(serializers.Serializer):
    rx_bytes = serializers.IntegerField()
    tx_bytes = serializers.IntegerField()


class BlockIOStatsSerializer(serializers.Serializer):
    read_bytes  = serializers.IntegerField()
    write_bytes = serializers.IntegerField()


class ContainerStatsSerializer(serializers.Serializer):
    container_id = serializers.CharField()
    name         = serializers.CharField()
    cpu_percent  = serializers.FloatField()
    memory       = MemoryStatsSerializer()
    network      = NetworkStatsSerializer()
    block_io     = BlockIOStatsSerializer()
    recorded_at  = serializers.DateTimeField()

class ContainerLogsSerializer(serializers.Serializer):
    container_id = serializers.CharField()
    name         = serializers.CharField()
    tail         = serializers.IntegerField()
    logs         = serializers.ListField(child=serializers.CharField())


class ExecTicketResponseSerializer(serializers.Serializer):
    ticket           = serializers.CharField()
    ws_url           = serializers.CharField()
    expires_in_seconds = serializers.IntegerField()