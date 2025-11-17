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
        read_only_fields = [
            'id',
            'customer',
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
            'media_type',
            'media_url',
            'media_caption',
            'buttons',
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
    
    # Rich Media Fields
    media_type = serializers.ChoiceField(
        choices=['text', 'image', 'video', 'document'],
        default='text',
        help_text="Type of media to include"
    )
    media_url = serializers.URLField(
        required=False,
        allow_null=True,
        max_length=500,
        help_text="URL to media file (required for non-text media types)"
    )
    media_caption = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1024,
        help_text="Caption for media (max 1024 characters)"
    )
    buttons = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        default=list,
        max_length=3,
        help_text="Button configurations (max 3): [{id, title, type, url?, phone_number?}]"
    )
    
    def validate_scheduled_at(self, value):
        """Validate that scheduled_at is in the future."""
        from django.utils import timezone
        if value and value <= timezone.now():
            raise serializers.ValidationError("scheduled_at must be in the future")
        return value
    
    def validate_buttons(self, value):
        """Validate button configurations."""
        if not value:
            return value
        
        # Max 3 buttons
        if len(value) > 3:
            raise serializers.ValidationError("Maximum 3 buttons allowed per message")
        
        # Validate each button
        for idx, button in enumerate(value):
            # Check required fields
            if 'id' not in button:
                raise serializers.ValidationError(f"Button {idx} missing required field: id")
            if 'title' not in button:
                raise serializers.ValidationError(f"Button {idx} missing required field: title")
            
            # Validate title length (WhatsApp limit: 20 characters)
            if len(button['title']) > 20:
                raise serializers.ValidationError(
                    f"Button {idx} title exceeds 20 characters: {button['title']}"
                )
            
            # Validate button type
            button_type = button.get('type', 'reply')
            if button_type not in ['reply', 'url', 'call']:
                raise serializers.ValidationError(
                    f"Button {idx} has invalid type: {button_type}. "
                    f"Must be 'reply', 'url', or 'call'"
                )
            
            # Validate type-specific fields
            if button_type == 'url' and 'url' not in button:
                raise serializers.ValidationError(
                    f"Button {idx} of type 'url' missing url field"
                )
            if button_type == 'call' and 'phone_number' not in button:
                raise serializers.ValidationError(
                    f"Button {idx} of type 'call' missing phone_number field"
                )
        
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
        
        # Validate media configuration
        media_type = data.get('media_type', 'text')
        media_url = data.get('media_url')
        
        if media_type != 'text' and not media_url:
            raise serializers.ValidationError({
                'media_url': f"media_url is required for media_type '{media_type}'"
            })
        
        # Validate caption length
        media_caption = data.get('media_caption', '')
        if media_caption and len(media_caption) > 1024:
            raise serializers.ValidationError({
                'media_caption': f"media_caption exceeds 1024 characters: {len(media_caption)}"
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
    button_analytics = serializers.JSONField(read_only=True, required=False)


class CampaignButtonInteractionSerializer(serializers.Serializer):
    """Serializer for campaign button interactions."""
    
    id = serializers.UUIDField(read_only=True)
    campaign_id = serializers.UUIDField(read_only=True)
    customer_id = serializers.UUIDField(read_only=True)
    message_id = serializers.UUIDField(read_only=True)
    button_id = serializers.CharField(read_only=True)
    button_title = serializers.CharField(read_only=True)
    button_type = serializers.CharField(read_only=True)
    clicked_at = serializers.DateTimeField(read_only=True)
    led_to_conversion = serializers.BooleanField(read_only=True)
    conversion_type = serializers.CharField(read_only=True, allow_null=True)
    conversion_reference_id = serializers.UUIDField(read_only=True, allow_null=True)


class TrackButtonClickSerializer(serializers.Serializer):
    """Serializer for tracking button clicks."""
    
    button_id = serializers.CharField(
        required=True,
        help_text="ID of the button that was clicked"
    )
    button_title = serializers.CharField(
        required=True,
        max_length=100,
        help_text="Title/text of the button"
    )
    button_type = serializers.ChoiceField(
        choices=['reply', 'url', 'call'],
        default='reply',
        help_text="Type of button clicked"
    )
    message_id = serializers.UUIDField(
        required=True,
        help_text="ID of the campaign message containing the button"
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Additional metadata"
    )
