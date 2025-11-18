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
        """
        Increment low confidence counter atomically.
        
        Uses F() expression to prevent race conditions where multiple
        concurrent requests could lose count updates.
        """
        from django.db.models import F
        
        # Atomically increment the counter
        Conversation.objects.filter(id=self.id).update(
            low_confidence_count=F('low_confidence_count') + 1
        )
        
        # Refresh from database to get updated value
        self.refresh_from_db(fields=['low_confidence_count'])
        
        # Auto-handoff after 2 consecutive low confidence intents
        if self.low_confidence_count >= 2:
            self.mark_handoff()
    
    def reset_low_confidence(self):
        """
        Reset low confidence counter after successful intent.
        
        Uses atomic update to prevent race conditions.
        """
        Conversation.objects.filter(id=self.id).update(low_confidence_count=0)
        self.low_confidence_count = 0


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
        max_length=10000,
        help_text="Message text content (max 10,000 characters)"
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
        max_length=5000,
        help_text="Template content with {{placeholder}} syntax (max 5,000 characters)"
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
        """
        Increment usage counter atomically.
        
        Uses F() expression to prevent race conditions when multiple
        messages use the same template concurrently.
        """
        from django.db.models import F
        MessageTemplate.objects.filter(id=self.id).update(
            usage_count=F('usage_count') + 1
        )
        self.refresh_from_db(fields=['usage_count'])


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
        max_length=5000,
        blank=True,
        help_text="Additional notes about preference changes (max 5,000 characters)"
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


class ScheduledMessageManager(models.Manager):
    """Manager for scheduled message queries."""
    
    def for_tenant(self, tenant):
        """Get scheduled messages for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def pending(self, tenant=None):
        """Get pending scheduled messages."""
        qs = self.filter(status='pending')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    def due_for_sending(self):
        """Get messages that are due to be sent."""
        from django.utils import timezone
        return self.filter(
            status='pending',
            scheduled_at__lte=timezone.now()
        )
    
    def for_customer(self, tenant, customer):
        """Get scheduled messages for a specific customer."""
        return self.filter(tenant=tenant, customer=customer)


class ScheduledMessage(BaseModel):
    """
    Scheduled message for future delivery.
    
    Used for:
    - Promotional campaigns scheduled in advance
    - Appointment reminders (24h, 2h before)
    - Re-engagement messages for inactive conversations
    - Any message that should be sent at a specific future time
    
    Messages can be:
    - Individual (customer specified)
    - Broadcast (customer=null, uses recipient_criteria)
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='scheduled_messages',
        db_index=True,
        help_text="Tenant this scheduled message belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='scheduled_messages',
        db_index=True,
        help_text="Target customer (null for broadcast campaigns)"
    )
    
    # Content
    content = models.TextField(
        max_length=10000,
        help_text="Message content to send (max 10,000 characters)"
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_messages',
        help_text="Template used for this message"
    )
    template_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context data for template rendering"
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(
        db_index=True,
        help_text="When to send this message"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current status of scheduled message"
    )
    
    # Broadcast Configuration (for campaigns)
    recipient_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Criteria for selecting recipients (for broadcast messages)"
    )
    message_type = models.CharField(
        max_length=30,
        default='scheduled_promotional',
        help_text="Type of message for consent checking"
    )
    
    # Delivery Tracking
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was actually sent"
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when sending failed"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if sending failed"
    )
    
    # Reference to created message(s)
    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_from',
        help_text="Message record created when sent"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (campaign_id, appointment_id, etc.)"
    )
    
    # Custom manager
    objects = ScheduledMessageManager()
    
    class Meta:
        db_table = 'scheduled_messages'
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['tenant', 'status', 'scheduled_at']),
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
        ]
    
    def __str__(self):
        customer_str = f"to {self.customer}" if self.customer else "broadcast"
        return f"ScheduledMessage {self.id} - {customer_str} at {self.scheduled_at}"
    
    def mark_sent(self, message=None):
        """Mark scheduled message as sent."""
        from django.utils import timezone
        
        # Validate message belongs to same tenant if provided
        if message and message.conversation.tenant_id != self.tenant_id:
            raise ValueError("Message must belong to same tenant as scheduled message")
        
        self.status = 'sent'
        self.sent_at = timezone.now()
        if message:
            self.message = message
        self.save(update_fields=['status', 'sent_at', 'message'])
    
    def mark_failed(self, error_message=None):
        """Mark scheduled message as failed."""
        from django.utils import timezone
        self.status = 'failed'
        self.failed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['status', 'failed_at', 'error_message'])
    
    def cancel(self):
        """Cancel a pending scheduled message."""
        if self.status == 'pending':
            self.status = 'canceled'
            self.save(update_fields=['status'])
            return True
        return False
    
    def is_due(self):
        """Check if message is due to be sent."""
        from django.utils import timezone
        return self.status == 'pending' and self.scheduled_at <= timezone.now()


class MessageCampaignManager(models.Manager):
    """Manager for message campaign queries."""
    
    def for_tenant(self, tenant):
        """Get campaigns for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def active(self, tenant=None):
        """Get active campaigns (not canceled)."""
        qs = self.exclude(status='canceled')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    def completed(self, tenant=None):
        """Get completed campaigns."""
        qs = self.filter(status='completed')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    def by_status(self, tenant, status):
        """Get campaigns by status."""
        return self.filter(tenant=tenant, status=status)


class MessageCampaign(BaseModel):
    """
    Message campaign for broadcasting messages to multiple customers.
    
    Campaigns support:
    - Targeted messaging based on customer criteria (tags, purchase history, activity)
    - A/B testing with multiple message variants
    - Comprehensive metrics tracking (delivery, engagement, conversion)
    - Consent-based filtering (only sends to customers who opted in)
    - Tier-based limits on campaign sends per month
    
    Campaign workflow:
    1. Create campaign with target criteria and message content
    2. Calculate reach (count eligible customers)
    3. Execute campaign (send to all matching customers with consent)
    4. Track metrics (delivery, reads, responses, conversions)
    5. Generate report with engagement analytics
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='campaigns',
        db_index=True,
        help_text="Tenant this campaign belongs to"
    )
    
    # Campaign Details
    name = models.CharField(
        max_length=255,
        help_text="Campaign name for identification"
    )
    description = models.TextField(
        blank=True,
        help_text="Campaign description and notes"
    )
    
    # Message Content
    message_content = models.TextField(
        max_length=10000,
        help_text="Default message content to send (max 10,000 characters)"
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
        help_text="Template used for this campaign"
    )
    
    # Rich Media Support
    media_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Text Only'),
            ('image', 'Image'),
            ('video', 'Video'),
            ('document', 'Document'),
        ],
        default='text',
        help_text="Type of media included in campaign"
    )
    media_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="URL to media file (image, video, or document)"
    )
    media_caption = models.TextField(
        blank=True,
        help_text="Caption for media (used with images, videos, documents)"
    )
    
    # Button Configuration (WhatsApp Interactive Messages)
    buttons = models.JSONField(
        default=list,
        blank=True,
        help_text="List of button configurations (max 3): [{id, title, type}]"
    )
    
    # Targeting
    target_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Criteria for selecting recipients (tags, purchase_history, activity)"
    )
    
    # A/B Testing
    is_ab_test = models.BooleanField(
        default=False,
        help_text="Whether this campaign is an A/B test"
    )
    variants = models.JSONField(
        default=list,
        blank=True,
        help_text="A/B test variants: [{name, content, customer_ids, metrics}]"
    )
    
    # Metrics - Delivery
    delivery_count = models.IntegerField(
        default=0,
        help_text="Total customers targeted"
    )
    delivered_count = models.IntegerField(
        default=0,
        help_text="Successfully delivered messages"
    )
    failed_count = models.IntegerField(
        default=0,
        help_text="Failed delivery attempts"
    )
    
    # Metrics - Engagement
    read_count = models.IntegerField(
        default=0,
        help_text="Messages read by customers"
    )
    response_count = models.IntegerField(
        default=0,
        help_text="Customer responses received"
    )
    conversion_count = models.IntegerField(
        default=0,
        help_text="Conversions (orders/bookings) from campaign"
    )
    
    # Status and Scheduling
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        help_text="Current campaign status"
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When to execute this campaign"
    )
    
    # Execution Tracking
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When campaign execution started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When campaign execution completed"
    )
    
    # Creator
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns_created',
        help_text="User who created this campaign"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional campaign metadata"
    )
    
    # Custom manager
    objects = MessageCampaignManager()
    
    class Meta:
        db_table = 'message_campaigns'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['status', 'scheduled_at']),
        ]
    
    def __str__(self):
        return f"Campaign: {self.name} ({self.tenant.slug}) - {self.status}"
    
    def calculate_delivery_rate(self):
        """Calculate delivery success rate."""
        if self.delivery_count == 0:
            return 0.0
        return (self.delivered_count / self.delivery_count) * 100
    
    def calculate_engagement_rate(self):
        """Calculate engagement rate (responses / delivered)."""
        if self.delivered_count == 0:
            return 0.0
        return (self.response_count / self.delivered_count) * 100
    
    def calculate_conversion_rate(self):
        """Calculate conversion rate (conversions / delivered)."""
        if self.delivered_count == 0:
            return 0.0
        return (self.conversion_count / self.delivered_count) * 100
    
    def calculate_read_rate(self):
        """Calculate read rate (reads / delivered)."""
        if self.delivered_count == 0:
            return 0.0
        return (self.read_count / self.delivered_count) * 100
    
    def mark_sending(self):
        """Mark campaign as currently sending."""
        from django.utils import timezone
        self.status = 'sending'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self):
        """Mark campaign as completed."""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def cancel(self):
        """Cancel a draft or scheduled campaign."""
        if self.status in ['draft', 'scheduled']:
            self.status = 'canceled'
            self.save(update_fields=['status'])
            return True
        return False
    
    def increment_delivery(self):
        """
        Increment delivery count atomically.
        
        Uses F() expression to prevent race conditions in concurrent campaign sends.
        """
        from django.db.models import F
        MessageCampaign.objects.filter(id=self.id).update(
            delivery_count=F('delivery_count') + 1
        )
        self.refresh_from_db(fields=['delivery_count'])
    
    def increment_delivered(self):
        """
        Increment delivered count atomically.
        
        Uses F() expression to prevent race conditions in concurrent deliveries.
        """
        from django.db.models import F
        MessageCampaign.objects.filter(id=self.id).update(
            delivered_count=F('delivered_count') + 1
        )
        self.refresh_from_db(fields=['delivered_count'])
    
    def increment_failed(self):
        """
        Increment failed count atomically.
        
        Uses F() expression to prevent race conditions in concurrent failures.
        """
        from django.db.models import F
        MessageCampaign.objects.filter(id=self.id).update(
            failed_count=F('failed_count') + 1
        )
        self.refresh_from_db(fields=['failed_count'])
    
    def increment_read(self):
        """
        Increment read count atomically.
        
        Uses F() expression to prevent race conditions in concurrent read receipts.
        """
        from django.db.models import F
        MessageCampaign.objects.filter(id=self.id).update(
            read_count=F('read_count') + 1
        )
        self.refresh_from_db(fields=['read_count'])
    
    def increment_response(self):
        """
        Increment response count atomically.
        
        Uses F() expression to prevent race conditions in concurrent responses.
        """
        from django.db.models import F
        MessageCampaign.objects.filter(id=self.id).update(
            response_count=F('response_count') + 1
        )
        self.refresh_from_db(fields=['response_count'])
    
    def increment_conversion(self):
        """
        Increment conversion count atomically.
        
        Uses F() expression to prevent race conditions in concurrent conversions.
        """
        from django.db.models import F
        MessageCampaign.objects.filter(id=self.id).update(
            conversion_count=F('conversion_count') + 1
        )
        self.refresh_from_db(fields=['conversion_count'])
    
    def validate_buttons(self):
        """
        Validate button configuration against WhatsApp limits.
        
        Raises:
            ValueError: If button configuration is invalid
        """
        if not self.buttons:
            return
        
        # WhatsApp allows max 3 buttons
        if len(self.buttons) > 3:
            raise ValueError("Maximum 3 buttons allowed per message")
        
        # Validate each button
        for idx, button in enumerate(self.buttons):
            # Check required fields
            if 'id' not in button:
                raise ValueError(f"Button {idx} missing required field: id")
            if 'title' not in button:
                raise ValueError(f"Button {idx} missing required field: title")
            
            # Validate title length (WhatsApp limit: 20 characters)
            if len(button['title']) > 20:
                raise ValueError(
                    f"Button {idx} title exceeds 20 characters: {button['title']}"
                )
            
            # Validate button type
            button_type = button.get('type', 'reply')
            if button_type not in ['reply', 'url', 'call']:
                raise ValueError(
                    f"Button {idx} has invalid type: {button_type}. "
                    f"Must be 'reply', 'url', or 'call'"
                )
            
            # Validate type-specific fields
            if button_type == 'url' and 'url' not in button:
                raise ValueError(f"Button {idx} of type 'url' missing url field")
            if button_type == 'call' and 'phone_number' not in button:
                raise ValueError(f"Button {idx} of type 'call' missing phone_number field")
    
    def validate_media(self):
        """
        Validate media configuration.
        
        Raises:
            ValueError: If media configuration is invalid
        """
        if self.media_type == 'text':
            # Text-only messages don't need media_url
            return
        
        # Non-text messages require media_url
        if not self.media_url:
            raise ValueError(
                f"media_url is required for media_type '{self.media_type}'"
            )
        
        # Validate caption length (WhatsApp limit: 1024 characters)
        if self.media_caption and len(self.media_caption) > 1024:
            raise ValueError(
                f"media_caption exceeds 1024 characters: {len(self.media_caption)}"
            )
    
    def save(self, *args, **kwargs):
        """Override save to validate button and media configuration."""
        # Validate buttons if present
        if self.buttons:
            self.validate_buttons()
        
        # Validate media configuration
        self.validate_media()
        
        super().save(*args, **kwargs)


class MessageQueueManager(models.Manager):
    """Manager for message queue queries."""
    
    def for_conversation(self, conversation):
        """Get queued messages for a specific conversation."""
        return self.filter(conversation=conversation).order_by('queue_position')
    
    def pending(self, conversation=None):
        """Get pending messages in queue."""
        qs = self.filter(status='queued')
        if conversation:
            qs = qs.filter(conversation=conversation)
        return qs.order_by('queue_position')
    
    def processing(self, conversation=None):
        """Get messages currently being processed."""
        qs = self.filter(status='processing')
        if conversation:
            qs = qs.filter(conversation=conversation)
        return qs
    
    def ready_for_batch(self, conversation, delay_seconds=5):
        """
        Get messages ready for batch processing.
        
        Returns messages that have been queued for at least delay_seconds
        and are still in queued status.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(seconds=delay_seconds)
        
        return self.filter(
            conversation=conversation,
            status='queued',
            queued_at__lte=cutoff_time
        ).order_by('queue_position')


class CampaignButtonInteraction(BaseModel):
    """
    Tracks button clicks from campaign messages.
    
    Records when customers interact with buttons in campaign messages,
    enabling analytics on button engagement and conversion tracking.
    
    TENANT SCOPING: Inherits tenant from campaign relationship.
    """
    
    campaign = models.ForeignKey(
        MessageCampaign,
        on_delete=models.CASCADE,
        related_name='button_interactions',
        db_index=True,
        help_text="Campaign this interaction belongs to"
    )
    
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='campaign_button_interactions',
        db_index=True,
        help_text="Customer who clicked the button"
    )
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='button_interactions',
        help_text="Campaign message that contained the button"
    )
    
    # Button Details
    button_id = models.CharField(
        max_length=100,
        help_text="ID of the button that was clicked"
    )
    button_title = models.CharField(
        max_length=100,
        help_text="Title/text of the button"
    )
    button_type = models.CharField(
        max_length=20,
        choices=[
            ('reply', 'Reply Button'),
            ('url', 'URL Button'),
            ('call', 'Call Button'),
        ],
        help_text="Type of button clicked"
    )
    
    # Interaction Context
    clicked_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when button was clicked"
    )
    
    # Response Tracking
    response_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_by_button',
        help_text="Customer's response message after clicking button"
    )
    
    # Conversion Tracking
    led_to_conversion = models.BooleanField(
        default=False,
        help_text="Whether this interaction led to a conversion (order/booking)"
    )
    conversion_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('order', 'Order'),
            ('appointment', 'Appointment'),
        ],
        help_text="Type of conversion if applicable"
    )
    conversion_reference_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the order or appointment"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional interaction metadata"
    )
    
    class Meta:
        db_table = 'campaign_button_interactions'
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['campaign', 'clicked_at']),
            models.Index(fields=['campaign', 'button_id']),
            models.Index(fields=['customer', 'clicked_at']),
            models.Index(fields=['campaign', 'led_to_conversion']),
        ]
    
    def __str__(self):
        return f"ButtonInteraction: {self.button_title} - Campaign {self.campaign_id}"
    
    def mark_conversion(self, conversion_type: str, reference_id: str):
        """
        Mark this interaction as leading to a conversion.
        
        Args:
            conversion_type: Type of conversion ('order' or 'appointment')
            reference_id: ID of the order or appointment
        """
        self.led_to_conversion = True
        self.conversion_type = conversion_type
        self.conversion_reference_id = reference_id
        self.save(update_fields=['led_to_conversion', 'conversion_type', 'conversion_reference_id'])


class MessageQueue(BaseModel):
    """
    Message queue for handling message bursts.
    
    When customers send multiple messages in rapid succession (within 5 seconds),
    messages are queued instead of being processed immediately. This allows the
    AI agent to:
    - Process all messages together with full context
    - Detect and handle multiple intents in a single response
    - Prevent duplicate intent processing
    - Provide more coherent responses to message bursts
    
    Queue workflow:
    1. Detect rapid messages (within 5 seconds of previous)
    2. Add to queue with incremental position
    3. Wait for delay period (5 seconds)
    4. Batch process all queued messages together
    5. Mark as processed
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    """
    
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='message_queue',
        db_index=True,
        help_text="Conversation this queued message belongs to"
    )
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='queue_entries',
        help_text="Message that is queued"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='queued',
        db_index=True,
        help_text="Current status of queued message"
    )
    
    queue_position = models.IntegerField(
        help_text="Position in queue (lower = earlier)"
    )
    
    queued_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when message was queued"
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was processed"
    )
    
    # Error tracking
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if processing failed"
    )
    
    # Custom manager
    objects = MessageQueueManager()
    
    class Meta:
        db_table = 'message_queue'
        ordering = ['conversation', 'queue_position']
        indexes = [
            models.Index(fields=['conversation', 'status', 'queue_position']),
            models.Index(fields=['status', 'queued_at']),
            models.Index(fields=['conversation', 'queued_at']),
        ]
        unique_together = [('conversation', 'queue_position')]
    
    def __str__(self):
        return f"MessageQueue {self.id} - Conversation {self.conversation_id} - Position {self.queue_position}"
    
    def mark_processing(self):
        """Mark message as currently being processed."""
        self.status = 'processing'
        self.save(update_fields=['status'])
    
    def mark_processed(self):
        """Mark message as successfully processed."""
        from django.utils import timezone
        self.status = 'processed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])
    
    def mark_failed(self, error_message=None):
        """Mark message processing as failed."""
        from django.utils import timezone
        self.status = 'failed'
        self.processed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['status', 'processed_at', 'error_message'])
    
    def is_ready_for_batch(self, delay_seconds=5):
        """Check if message has been queued long enough for batch processing."""
        from django.utils import timezone
        from datetime import timedelta
        
        if self.status != 'queued':
            return False
        
        cutoff_time = timezone.now() - timedelta(seconds=delay_seconds)
        return self.queued_at <= cutoff_time
    
    def save(self, *args, **kwargs):
        """Override save to validate message belongs to same conversation."""
        if self.message_id and self.conversation_id:
            if self.message.conversation_id != self.conversation_id:
                raise ValueError(
                    f"MessageQueue conversation ({self.conversation_id}) must match "
                    f"Message conversation ({self.message.conversation_id})"
                )
        
        super().save(*args, **kwargs)
