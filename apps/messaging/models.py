"""
Messaging models for conversations and messages.

Implements conversation tracking and message history with
tenant scoping and status management.
"""
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel

User = get_user_model()


class ConversationManager(models.Manager):
    """Manager for conversation queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get conversations for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_customer(self, tenant, customer):
        """Get conversations for a specific customer within a tenant."""
        return self.filter(tenant=tenant, customer=customer)
    
    def active(self, tenant):
        """Get active conversations (open or bot status)."""
        return self.filter(tenant=tenant, status__in=['open', 'bot'])
    
    def requiring_handoff(self, tenant):
        """Get conversations requiring human handoff."""
        return self.filter(tenant=tenant, status='handoff')
    
    def inactive_since(self, tenant, days=7):
        """Get conversations inactive for N days."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(tenant=tenant, updated_at__lt=cutoff, status='open')


class Conversation(BaseModel):
    """
    Conversation model representing a chat session between customer and tenant.
    
    Each conversation:
    - Belongs to a specific tenant and customer
    - Has a status tracking bot/human handling
    - Contains message history
    - Tracks last intent and assigned agent
    """
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('bot', 'Bot Handling'),
        ('handoff', 'Human Handoff'),
        ('closed', 'Closed'),
        ('dormant', 'Dormant'),
    ]
    
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('telegram', 'Telegram'),
        ('web', 'Web Chat'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='conversations',
        db_index=True,
        help_text="Tenant this conversation belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='conversations',
        db_index=True,
        help_text="Customer in this conversation"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        db_index=True,
        help_text="Current conversation status"
    )
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='whatsapp',
        help_text="Communication channel"
    )
    
    # Intent Tracking
    last_intent = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Last detected intent"
    )
    intent_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence score of last intent"
    )
    low_confidence_count = models.IntegerField(
        default=0,
        help_text="Count of consecutive low-confidence intents"
    )
    
    # Agent Assignment
    last_agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_conversations',
        help_text="Last human agent assigned"
    )
    handoff_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when handed off to human"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional conversation metadata"
    )
    
    # Custom manager
    objects = ConversationManager()
    
    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['tenant', 'status', 'updated_at']),
            models.Index(fields=['tenant', 'updated_at']),
            models.Index(fields=['status', 'updated_at']),
        ]
    
    def __str__(self):
        return f"Conversation {self.id} - {self.customer} ({self.status})"
    
    def mark_handoff(self, agent=None):
        """Mark conversation for human handoff."""
        from django.utils import timezone
        self.status = 'handoff'
        self.handoff_at = timezone.now()
        if agent:
            self.last_agent = agent
        self.save(update_fields=['status', 'handoff_at', 'last_agent'])
    
    def mark_closed(self):
        """Close the conversation."""
        self.status = 'closed'
        self.save(update_fields=['status'])
    
    def mark_dormant(self):
        """Mark conversation as dormant (inactive)."""
        self.status = 'dormant'
        self.save(update_fields=['status'])
    
    def reopen(self):
        """Reopen a closed or dormant conversation."""
        self.status = 'open'
        self.low_confidence_count = 0
        self.save(update_fields=['status', 'low_confidence_count'])
    
    def increment_low_confidence(self):
        """Increment low confidence counter."""
        self.low_confidence_count += 1
        
        # Auto-handoff after 2 consecutive low confidence intents
        if self.low_confidence_count >= 2:
            self.mark_handoff()
        else:
            self.save(update_fields=['low_confidence_count'])
    
    def reset_low_confidence(self):
        """Reset low confidence counter after successful intent."""
        self.low_confidence_count = 0
        self.save(update_fields=['low_confidence_count'])


class MessageManager(models.Manager):
    """Manager for message queries."""
    
    def for_conversation(self, conversation):
        """Get messages for a specific conversation."""
        return self.filter(conversation=conversation).order_by('created_at')
    
    def inbound(self, conversation):
        """Get inbound messages for a conversation."""
        return self.filter(conversation=conversation, direction='in')
    
    def outbound(self, conversation):
        """Get outbound messages for a conversation."""
        return self.filter(conversation=conversation, direction='out')
    
    def by_type(self, conversation, message_type):
        """Get messages of a specific type."""
        return self.filter(conversation=conversation, message_type=message_type)


class Message(BaseModel):
    """
    Message model representing individual communications within a conversation.
    
    Each message:
    - Belongs to a conversation
    - Has direction (in/out)
    - Has a type indicating purpose
    - Contains text content and optional media
    - Tracks provider message ID for delivery status
    """
    
    DIRECTION_CHOICES = [
        ('in', 'Inbound'),
        ('out', 'Outbound'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('customer_inbound', 'Customer Inbound'),
        ('bot_response', 'Bot Response'),
        ('automated_transactional', 'Automated Transactional'),
        ('automated_reminder', 'Automated Reminder'),
        ('automated_reengagement', 'Automated Re-engagement'),
        ('scheduled_promotional', 'Scheduled Promotional'),
        ('manual_outbound', 'Manual Outbound'),
    ]
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True,
        help_text="Conversation this message belongs to"
    )
    
    direction = models.CharField(
        max_length=3,
        choices=DIRECTION_CHOICES,
        db_index=True,
        help_text="Message direction"
    )
    message_type = models.CharField(
        max_length=30,
        choices=MESSAGE_TYPE_CHOICES,
        db_index=True,
        help_text="Type of message"
    )
    
    # Content
    text = models.TextField(
        help_text="Message text content"
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional message data (media URLs, buttons, etc.)"
    )
    
    # Provider Tracking
    provider_msg_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Provider message ID (e.g., Twilio SID)"
    )
    provider_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Provider delivery status"
    )
    
    # Template Reference
    template = models.ForeignKey(
        'MessageTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        help_text="Template used for this message"
    )
    
    # Delivery Tracking
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was sent"
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was delivered"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was read"
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message failed"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if delivery failed"
    )
    
    # Custom manager
    objects = MessageManager()
    
    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'direction', 'created_at']),
            models.Index(fields=['provider_msg_id']),
            models.Index(fields=['message_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"Message {self.id} - {self.direction} ({self.message_type})"
    
    def mark_sent(self, provider_msg_id=None):
        """Mark message as sent."""
        from django.utils import timezone
        self.sent_at = timezone.now()
        if provider_msg_id:
            self.provider_msg_id = provider_msg_id
        self.save(update_fields=['sent_at', 'provider_msg_id'])
    
    def mark_delivered(self):
        """Mark message as delivered."""
        from django.utils import timezone
        self.delivered_at = timezone.now()
        self.save(update_fields=['delivered_at'])
    
    def mark_read(self):
        """Mark message as read."""
        from django.utils import timezone
        self.read_at = timezone.now()
        self.save(update_fields=['read_at'])
    
    def mark_failed(self, error_message=None):
        """Mark message as failed."""
        from django.utils import timezone
        self.failed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['failed_at', 'error_message'])


class MessageTemplate(BaseModel):
    """
    Message template for reusable message content with placeholders.
    
    Templates support placeholder syntax like {{customer_name}}, {{product_name}}, etc.
    Used for automated messages, campaigns, and consistent branding.
    """
    
    MESSAGE_TYPE_CHOICES = [
        ('transactional', 'Transactional'),
        ('reminder', 'Reminder'),
        ('promotional', 'Promotional'),
        ('reengagement', 'Re-engagement'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='message_templates',
        db_index=True,
        help_text="Tenant this template belongs to"
    )
    
    name = models.CharField(
        max_length=255,
        help_text="Template name for identification"
    )
    content = models.TextField(
        help_text="Template content with {{placeholder}} syntax"
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        help_text="Type of message this template is for"
    )
    
    # Usage Tracking
    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times this template has been used"
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        help_text="Template description"
    )
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text="List of available variables/placeholders"
    )
    
    class Meta:
        db_table = 'message_templates'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'message_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.slug})"
    
    def increment_usage(self):
        """Increment usage counter."""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])


class CustomerPreferencesManager(models.Manager):
    """Manager for customer preferences queries."""
    
    def for_customer(self, tenant, customer):
        """Get preferences for a specific customer."""
        return self.filter(tenant=tenant, customer=customer).first()
    
    def get_or_create_for_customer(self, tenant, customer):
        """Get or create preferences with default values."""
        prefs, created = self.get_or_create(
            tenant=tenant,
            customer=customer,
            defaults={
                'transactional_messages': True,
                'reminder_messages': True,
                'promotional_messages': False,
            }
        )
        return prefs, created


class CustomerPreferences(BaseModel):
    """
    Customer communication preferences and consent settings.
    
    Manages three types of consent:
    - transactional_messages: Order updates, payment confirmations (always true, cannot opt-out)
    - reminder_messages: Appointment reminders, cart abandonment (default true, can opt-out)
    - promotional_messages: Marketing, offers, campaigns (default false, requires opt-in)
    
    Each customer has one preferences record per tenant.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='customer_preferences',
        db_index=True,
        help_text="Tenant this preference record belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='preferences',
        db_index=True,
        help_text="Customer these preferences belong to"
    )
    
    # Consent Types
    transactional_messages = models.BooleanField(
        default=True,
        help_text="Consent for transactional messages (order updates, payment confirmations)"
    )
    reminder_messages = models.BooleanField(
        default=True,
        help_text="Consent for reminder messages (appointment reminders, cart abandonment)"
    )
    promotional_messages = models.BooleanField(
        default=False,
        help_text="Consent for promotional messages (marketing, offers, campaigns)"
    )
    
    # Metadata
    last_updated_by = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Source of last update (customer, tenant, system)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about preference changes"
    )
    
    # Custom manager
    objects = CustomerPreferencesManager()
    
    class Meta:
        db_table = 'customer_preferences'
        unique_together = [('tenant', 'customer')]
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['tenant', 'promotional_messages']),
            models.Index(fields=['tenant', 'reminder_messages']),
        ]
        verbose_name_plural = 'Customer preferences'
    
    def __str__(self):
        return f"Preferences for {self.customer} ({self.tenant.slug})"
    
    def has_consent_for(self, message_type):
        """
        Check if customer has consented to a specific message type.
        
        Args:
            message_type: One of 'transactional', 'reminder', 'promotional'
            
        Returns:
            bool: True if customer has consented
        """
        consent_map = {
            'transactional': self.transactional_messages,
            'reminder': self.reminder_messages,
            'promotional': self.promotional_messages,
            'automated_transactional': self.transactional_messages,
            'automated_reminder': self.reminder_messages,
            'automated_reengagement': self.promotional_messages,
            'scheduled_promotional': self.promotional_messages,
        }
        return consent_map.get(message_type, False)
    
    def opt_out_all(self):
        """Opt out of all optional message types (keeps transactional)."""
        self.reminder_messages = False
        self.promotional_messages = False
        self.save(update_fields=['reminder_messages', 'promotional_messages'])
    
    def opt_in_all(self):
        """Opt in to all message types."""
        self.reminder_messages = True
        self.promotional_messages = True
        self.save(update_fields=['reminder_messages', 'promotional_messages'])


class ConsentEventManager(models.Manager):
    """Manager for consent event queries."""
    
    def for_customer(self, tenant, customer):
        """Get consent events for a specific customer."""
        return self.filter(tenant=tenant, customer=customer).order_by('-created_at')
    
    def by_consent_type(self, tenant, customer, consent_type):
        """Get consent events for a specific consent type."""
        return self.filter(
            tenant=tenant,
            customer=customer,
            consent_type=consent_type
        ).order_by('-created_at')


class ConsentEvent(BaseModel):
    """
    Audit trail for customer consent preference changes.
    
    Records all changes to consent preferences for compliance and regulatory purposes.
    Each event captures:
    - What changed (consent_type)
    - Previous and new values
    - Who/what triggered the change (source)
    - When it happened (created_at from BaseModel)
    """
    
    CONSENT_TYPE_CHOICES = [
        ('transactional_messages', 'Transactional Messages'),
        ('reminder_messages', 'Reminder Messages'),
        ('promotional_messages', 'Promotional Messages'),
    ]
    
    SOURCE_CHOICES = [
        ('customer_initiated', 'Customer Initiated'),
        ('tenant_updated', 'Tenant Updated'),
        ('system_default', 'System Default'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='consent_events',
        db_index=True,
        help_text="Tenant this event belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='consent_events',
        db_index=True,
        help_text="Customer this event is for"
    )
    preferences = models.ForeignKey(
        CustomerPreferences,
        on_delete=models.CASCADE,
        related_name='events',
        help_text="Preferences record this event relates to"
    )
    
    # Event Details
    consent_type = models.CharField(
        max_length=30,
        choices=CONSENT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of consent that changed"
    )
    previous_value = models.BooleanField(
        help_text="Previous consent value"
    )
    new_value = models.BooleanField(
        help_text="New consent value"
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        help_text="Source of the change"
    )
    
    # Additional Context
    reason = models.TextField(
        blank=True,
        help_text="Reason for the change (if provided)"
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consent_changes',
        help_text="User who made the change (if tenant_updated)"
    )
    
    # Custom manager
    objects = ConsentEventManager()
    
    class Meta:
        db_table = 'consent_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'customer', 'created_at']),
            models.Index(fields=['tenant', 'consent_type', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
        ]
    
    def __str__(self):
        return f"ConsentEvent: {self.customer} - {self.consent_type} ({self.previous_value} → {self.new_value})"
