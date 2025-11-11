"""
Serializers for messaging API endpoints.
"""
from rest_framework import serializers
from apps.messaging.models import (
    CustomerPreferences, ConsentEvent, MessageTemplate, ScheduledMessage, MessageCampaign
)


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


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending outbound messages."""
    
    customer_id = serializers.UUIDField(
        required=True,
        help_text="Customer ID to send message to"
    )
    content = serializers.CharField(
        required=True,
        max_length=4096,
        help_text="Message content"
    )
    message_type = serializers.ChoiceField(
        choices=[
            ('manual_outbound', 'Manual Outbound'),
            ('automated_transactional', 'Automated Transactional'),
            ('automated_reminder', 'Automated Reminder'),
            ('automated_reengagement', 'Automated Re-engagement'),
            ('scheduled_promotional', 'Scheduled Promotional'),
        ],
        default='manual_outbound',
        help_text="Type of message"
    )
    template_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional template ID"
    )
    template_context = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Template context variables"
    )
    media_url = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="Optional media URL"
    )
    skip_consent_check = serializers.BooleanField(
        default=False,
        help_text="Skip consent validation (for transactional messages)"
    )


class ScheduleMessageSerializer(serializers.Serializer):
    """Serializer for scheduling messages."""
    
    customer_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Customer ID (null for broadcast)"
    )
    content = serializers.CharField(
        required=True,
        max_length=4096,
        help_text="Message content"
    )
    scheduled_at = serializers.DateTimeField(
        required=True,
        help_text="When to send the message (ISO 8601 format)"
    )
    message_type = serializers.ChoiceField(
        choices=[
            ('scheduled_promotional', 'Scheduled Promotional'),
            ('automated_reminder', 'Automated Reminder'),
            ('automated_reengagement', 'Automated Re-engagement'),
        ],
        default='scheduled_promotional',
        help_text="Type of message"
    )
    template_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional template ID"
    )
    template_context = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Template context variables"
    )
    recipient_criteria = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Criteria for broadcast targeting"
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Additional metadata"
    )
    
    def validate_scheduled_at(self, value):
        """Validate that scheduled_at is in the future."""
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError("scheduled_at must be in the future")
        return value


class MessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for MessageTemplate."""
    
    message_type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    
    class Meta:
        model = MessageTemplate
        fields = [
            'id',
            'tenant',
            'name',
            'content',
            'message_type',
            'message_type_display',
            'usage_count',
            'description',
            'variables',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'usage_count', 'created_at', 'updated_at']


class MessageTemplateCreateSerializer(serializers.Serializer):
    """Serializer for creating message templates."""
    
    name = serializers.CharField(
        max_length=255,
        help_text="Template name"
    )
    content = serializers.CharField(
        help_text="Template content with {{placeholder}} syntax"
    )
    message_type = serializers.ChoiceField(
        choices=[
            ('transactional', 'Transactional'),
            ('reminder', 'Reminder'),
            ('promotional', 'Promotional'),
            ('reengagement', 'Re-engagement'),
        ],
        help_text="Type of message"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Template description"
    )
    variables = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="List of available variables"
    )
    
    def validate_content(self, value):
        """Validate template content has valid placeholder syntax."""
        import re
        # Check for valid {{placeholder}} syntax
        placeholders = re.findall(r'\{\{(\w+)\}\}', value)
        if not placeholders:
            # No placeholders is fine
            return value
        
        # Check for malformed placeholders
        malformed = re.findall(r'\{[^{]|\}[^}]', value)
        if malformed:
            raise serializers.ValidationError(
                "Template contains malformed placeholders. Use {{placeholder}} syntax."
            )
        
        return value


class ScheduledMessageSerializer(serializers.ModelSerializer):
    """Serializer for ScheduledMessage."""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ScheduledMessage
        fields = [
            'id',
            'tenant',
            'customer',
            'customer_name',
            'content',
            'template',
            'template_context',
            'scheduled_at',
            'status',
            'status_display',
            'recipient_criteria',
            'message_type',
            'sent_at',
            'failed_at',
            'error_message',
            'message',
            'metadata',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'status',
            'status_display',
            'sent_at',
            'failed_at',
            'error_message',
            'message',
            'created_at',
        ]


class RateLimitStatusSerializer(serializers.Serializer):
    """Serializer for rate limit status."""
    
    current_count = serializers.IntegerField(read_only=True)
    daily_limit = serializers.IntegerField(read_only=True, allow_null=True)
    percentage_used = serializers.FloatField(read_only=True)
    remaining = serializers.IntegerField(read_only=True, allow_null=True)
    is_unlimited = serializers.BooleanField(read_only=True)
    warning_threshold_reached = serializers.BooleanField(read_only=True)


class MessageCampaignSerializer(serializers.ModelSerializer):
    """Serializer for MessageCampaign."""
    
    tenant_id = serializers.UUIDField(source='tenant.id', read_only=True)
    template_id = serializers.UUIDField(source='template.id', read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(source='created_by.id', read_only=True, allow_null=True)
    
    # Calculated fields
    delivery_rate = serializers.SerializerMethodField()
    engagement_rate = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    read_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageCampaign
        fields = [
            'id',
            'tenant',
            'tenant_id',
            'name',
            'description',
            'message_content',
            'template',
            'template_id',
            'target_criteria',
            'is_ab_test',
            'variants',
            'delivery_count',
            'delivered_count',
            'failed_count',
            'read_count',
            'response_count',
            'conversion_count',
            'status',
            'scheduled_at',
            'started_at',
            'completed_at',
            'created_by',
            'created_by_id',
            'metadata',
            'created_at',
            'updated_at',
            'delivery_rate',
            'engagement_rate',
            'conversion_rate',
            'read_rate',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_id',
            'template_id',
            'delivery_count',
            'delivered_count',
            'failed_count',
            'read_count',
            'response_count',
            'conversion_count',
            'status',
            'started_at',
            'completed_at',
            'created_by',
            'created_by_id',
            'metadata',
            'created_at',
            'updated_at',
            'delivery_rate',
            'engagement_rate',
            'conversion_rate',
            'read_rate',
        ]
    
    def get_delivery_rate(self, obj) -> float:
        """Get delivery success rate."""
        return obj.calculate_delivery_rate()
    
    def get_engagement_rate(self, obj) -> float:
        """Get engagement rate."""
        return obj.calculate_engagement_rate()
    
    def get_conversion_rate(self, obj) -> float:
        """Get conversion rate."""
        return obj.calculate_conversion_rate()
    
    def get_read_rate(self, obj) -> float:
        """Get read rate."""
        return obj.calculate_read_rate()


class MessageCampaignCreateSerializer(serializers.Serializer):
    """Serializer for creating message campaigns."""
    
    name = serializers.CharField(
        max_length=255,
        help_text="Campaign name"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Campaign description"
    )
    message_content = serializers.CharField(
        help_text="Message content to send"
    )
    template_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional template ID"
    )
    target_criteria = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Targeting criteria (tags, purchase_history, activity)"
    )
    scheduled_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="When to execute campaign (ISO 8601 format)"
    )
    is_ab_test = serializers.BooleanField(
        default=False,
        help_text="Whether this is an A/B test"
    )
    variants = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        default=list,
        help_text="A/B test variants: [{name, content}]"
    )
    
    def validate_scheduled_at(self, value):
        """Validate that scheduled_at is in the future."""
        from django.utils import timezone
        if value and value <= timezone.now():
            raise serializers.ValidationError("scheduled_at must be in the future")
        return value
    
    def validate(self, data):
        """Validate campaign configuration."""
        # Validate A/B test
        if data.get('is_ab_test'):
            variants = data.get('variants', [])
            if len(variants) < 2:
                raise serializers.ValidationError({
                    'variants': 'A/B test requires at least 2 variants'
                })
            
            # Validate each variant has required fields
            for idx, variant in enumerate(variants):
                if 'name' not in variant:
                    raise serializers.ValidationError({
                        'variants': f'Variant {idx} missing required field: name'
                    })
                if 'content' not in variant:
                    raise serializers.ValidationError({
                        'variants': f'Variant {idx} missing required field: content'
                    })
        
        return data


class CampaignExecuteSerializer(serializers.Serializer):
    """Serializer for executing a campaign."""
    
    confirm = serializers.BooleanField(
        default=False,
        help_text="Confirm campaign execution"
    )
    
    def validate_confirm(self, value):
        """Validate confirmation."""
        if not value:
            raise serializers.ValidationError(
                "You must confirm campaign execution by setting confirm=true"
            )
        return value


class CampaignReportSerializer(serializers.Serializer):
    """Serializer for campaign analytics report."""
    
    campaign_id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    duration_seconds = serializers.IntegerField(read_only=True, allow_null=True)
    
    targeting = serializers.JSONField(read_only=True)
    delivery = serializers.JSONField(read_only=True)
    engagement = serializers.JSONField(read_only=True)
    ab_test = serializers.JSONField(read_only=True)
