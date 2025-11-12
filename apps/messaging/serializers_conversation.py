"""
Serializers for conversation and message management.
"""
from rest_framework import serializers
from apps.messaging.models import Conversation, Message
from apps.tenants.models import Customer


class CustomerBasicSerializer(serializers.ModelSerializer):
    """Basic customer information for conversation listings."""
    
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone_e164', 'tags', 'last_seen_at']
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for message details."""
    
    class Meta:
        model = Message
        fields = [
            'id',
            'direction',
            'message_type',
            'text',
            'payload',
            'provider_msg_id',
            'provider_status',
            'sent_at',
            'delivered_at',
            'read_at',
            'failed_at',
            'error_message',
            'created_at',
        ]
        read_only_fields = fields


class ConversationListSerializer(serializers.ModelSerializer):
    """Serializer for conversation list view."""
    
    customer = CustomerBasicSerializer(read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id',
            'customer',
            'status',
            'channel',
            'last_intent',
            'intent_confidence',
            'low_confidence_count',
            'last_agent',
            'handoff_at',
            'message_count',
            'last_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_message_count(self, obj):
        """Get total message count for conversation."""
        return obj.messages.count()
    
    def get_last_message(self, obj):
        """Get last message preview."""
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'text': last_msg.text[:100] + '...' if len(last_msg.text) > 100 else last_msg.text,
                'direction': last_msg.direction,
                'created_at': last_msg.created_at,
            }
        return None


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Serializer for conversation detail view."""
    
    customer = CustomerBasicSerializer(read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id',
            'customer',
            'status',
            'channel',
            'last_intent',
            'intent_confidence',
            'low_confidence_count',
            'last_agent',
            'handoff_at',
            'metadata',
            'message_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_message_count(self, obj):
        """Get total message count for conversation."""
        return obj.messages.count()


class ConversationHandoffSerializer(serializers.Serializer):
    """Serializer for handoff request."""
    
    agent_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional agent ID to assign conversation to"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional reason for handoff"
    )
