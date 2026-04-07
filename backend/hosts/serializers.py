from rest_framework import serializers
from .models import Host, UserHostRole, Profile
from django.contrib.auth import get_user_model

User = get_user_model()


#Profile Serializer
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar_url', 'created_at']
        read_only_fields = ['created_at']


#Host Serializer (GET responses)
class HostSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Host
        fields = ['id', 'alias', 'ip_address', 'port', 'created_by', 'created_at', 'role']
        read_only_fields = ['id', 'created_by', 'created_at', 'role']

    def get_role(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        if request.user.is_superuser:
            return 'ADMIN'
        
        # Look up role in junction table
        role_entry = UserHostRole.objects.filter(user=request.user, host=obj).first()
        if role_entry:
            return role_entry.role
        
        # Fallback to checking the user's global role if they somehow bypass the junction
        if request.user.role.upper() == 'ADMIN':
            return 'ADMIN'
        return 'VIEWER'


#Host Create Serializer (POST /api/hosts/)
class HostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Host
        fields = ['alias', 'ip_address', 'port', 'ssh_credentials']
        extra_kwargs = {'ssh_credentials': {'write_only': True}}

    def validate(self, attrs):
        ip_address = attrs.get('ip_address')
        port = attrs.get('port')

        qs = Host.objects.filter(ip_address=ip_address, port=port)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                {
                    'ip_address': (
                        'A host with this IP and port already exists. '
                        'Use the existing host instead of creating a duplicate.'
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        return super().create(validated_data)


#User-Host Role Serializer (Assignment API)
class UserHostRoleSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    host = serializers.StringRelatedField(read_only=True)

    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = UserHostRole
        fields = ['user', 'user_id', 'host', 'role', 'assigned_at']
        read_only_fields = ['user', 'host', 'assigned_at']

    def create(self, validated_data):
        request = self.context.get('request')

        host_id = self.context['view'].kwargs.get('id')
        
        user_id = validated_data.pop('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            host = Host.objects.get(id=host_id)
        except (User.DoesNotExist, Host.DoesNotExist):
            raise serializers.ValidationError("Invalid User or Host ID.")

        if UserHostRole.objects.filter(user=user, host=host).exists():
            raise serializers.ValidationError("User already assigned to this host.")

        validated_data['user'] = user
        validated_data['host'] = host
        validated_data['assigned_by'] = request.user 

        return super().create(validated_data)