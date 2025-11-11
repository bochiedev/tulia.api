"""
Serializers for messaging API endpoints.
"""
from rest_framework import serializers
from apps.messaging.models import CustomerPreferences, ConsentEvent


class CustomerPreferencesSerializer(serializers.ModelSerializer):
    """Serializer for CustomerPreferences."""
    
    customer_id = serializers.UUIDField(source='customer.id', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    customer_phone = serializers.CharField(source='customer.phone_e164', read_only=True)
    
    class Meta:
        model = CustomerPreferences
        fields = [
            'id',
            'tenant',
            'customer',
            'customer_id',
            'customer_name',
            'customer_phone',
            'transactional_messages',
            'reminder_messages',
            'promotional_messages',
            'last_updated_by',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'customer',
            'customer_id',
            'customer_name',
            'customer_phone',
            'created_at',
            'updated_at',
        ]


class CustomerPreferencesUpdateSerializer(serializers.Serializer):
    """Serializer for updating customer preferences."""
    
    transactional_messages = serializers.BooleanField(required=False)
    reminder_messages = serializers.BooleanField(required=False)
    promotional_messages = serializers.BooleanField(required=False)
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Reason for updating preferences"
    )
    
    def validate_transactional_messages(self, value):
        """Validate that transactional messages cannot be disabled."""
        if value is False:
            raise serializers.ValidationError(
                "Transactional messages cannot be disabled as they are essential for service delivery."
            )
        return value
    
    def validate(self, data):
        """Validate that at least one preference is being updated."""
        consent_fields = ['transactional_messages', 'reminder_messages', 'promotional_messages']
        if not any(field in data for field in consent_fields):
            raise serializers.ValidationError(
                "At least one consent preference must be provided."
            )
        return data


class ConsentEventSerializer(serializers.ModelSerializer):
    """Serializer for ConsentEvent (audit trail)."""
    
    customer_id = serializers.UUIDField(source='customer.id', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True, allow_null=True)
    consent_type_display = serializers.CharField(source='get_consent_type_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    
    class Meta:
        model = ConsentEvent
        fields = [
            'id',
            'tenant',
            'customer',
            'customer_id',
            'customer_name',
            'preferences',
            'consent_type',
            'consent_type_display',
            'previous_value',
            'new_value',
            'source',
            'source_display',
            'reason',
            'changed_by',
            'changed_by_email',
            'created_at',
        ]
        read_only_fields = '__all__'


class CustomerPreferencesWithHistorySerializer(CustomerPreferencesSerializer):
    """Serializer for CustomerPreferences with consent history."""
    
    consent_history = ConsentEventSerializer(source='events', many=True, read_only=True)
    
    class Meta(CustomerPreferencesSerializer.Meta):
        fields = CustomerPreferencesSerializer.Meta.fields + ['consent_history']
