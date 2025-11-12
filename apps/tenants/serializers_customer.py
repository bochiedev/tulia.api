"""
Serializers for customer management.
"""
from rest_framework import serializers
from apps.tenants.models import Customer
from apps.messaging.models import CustomerPreferences


class CustomerConsentStatusSerializer(serializers.Serializer):
    """Serializer for customer consent status indicators."""
    
    transactional_messages = serializers.BooleanField()
    reminder_messages = serializers.BooleanField()
    promotional_messages = serializers.BooleanField()


class CustomerListSerializer(serializers.ModelSerializer):
    """Serializer for customer list view with consent indicators."""
    
    consent_status = serializers.SerializerMethodField()
    conversation_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id',
            'phone_e164',
            'name',
            'timezone',
            'language',
            'tags',
            'last_seen_at',
            'first_interaction_at',
            'consent_status',
            'conversation_count',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_consent_status(self, obj):
        """Get customer consent preferences."""
        try:
            preferences = CustomerPreferences.objects.get(
                tenant=obj.tenant,
                customer=obj
            )
            return {
                'transactional_messages': preferences.transactional_messages,
                'reminder_messages': preferences.reminder_messages,
                'promotional_messages': preferences.promotional_messages,
            }
        except CustomerPreferences.DoesNotExist:
            # Return defaults if preferences don't exist yet
            return {
                'transactional_messages': True,
                'reminder_messages': True,
                'promotional_messages': False,
            }
    
    def get_conversation_count(self, obj):
        """Get total conversation count for customer."""
        return obj.conversations.count()


class CustomerDetailSerializer(serializers.ModelSerializer):
    """Serializer for customer detail view."""
    
    consent_status = serializers.SerializerMethodField()
    conversation_count = serializers.SerializerMethodField()
    recent_conversations = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id',
            'phone_e164',
            'name',
            'timezone',
            'language',
            'tags',
            'metadata',
            'last_seen_at',
            'first_interaction_at',
            'consent_status',
            'conversation_count',
            'recent_conversations',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_consent_status(self, obj):
        """Get customer consent preferences."""
        try:
            preferences = CustomerPreferences.objects.get(
                tenant=obj.tenant,
                customer=obj
            )
            return {
                'transactional_messages': preferences.transactional_messages,
                'reminder_messages': preferences.reminder_messages,
                'promotional_messages': preferences.promotional_messages,
            }
        except CustomerPreferences.DoesNotExist:
            return {
                'transactional_messages': True,
                'reminder_messages': True,
                'promotional_messages': False,
            }
    
    def get_conversation_count(self, obj):
        """Get total conversation count for customer."""
        return obj.conversations.count()
    
    def get_recent_conversations(self, obj):
        """Get recent conversations for customer."""
        recent = obj.conversations.order_by('-updated_at')[:5]
        return [{
            'id': str(conv.id),
            'status': conv.status,
            'channel': conv.channel,
            'last_intent': conv.last_intent,
            'updated_at': conv.updated_at,
        } for conv in recent]


class CustomerExportSerializer(serializers.Serializer):
    """Serializer for customer data export request."""
    
    mask_pii = serializers.BooleanField(
        default=False,
        help_text="Whether to mask PII fields (phone numbers)"
    )
    include_conversations = serializers.BooleanField(
        default=False,
        help_text="Whether to include conversation history"
    )
    include_consent_history = serializers.BooleanField(
        default=False,
        help_text="Whether to include consent change history"
    )
    format = serializers.ChoiceField(
        choices=['json', 'csv'],
        default='json',
        help_text="Export format"
    )
