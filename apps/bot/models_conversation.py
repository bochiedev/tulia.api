"""
Core conversation models for bot interactions.

Consolidates conversation-related models including state management,
intent tracking, and interaction logging.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from apps.core.models import BaseModel


class IntentEventManager(models.Manager):
    """Manager for intent event queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get intent events for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get intent events for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def by_intent(self, tenant, intent_name):
        """Get events for a specific intent within a tenant."""
        return self.filter(tenant=tenant, intent_name=intent_name)
    
    def high_confidence(self, tenant, threshold=0.7):
        """Get events with confidence above threshold for a tenant."""
        return self.filter(tenant=tenant, confidence_score__gte=threshold)
    
    def low_confidence(self, tenant, threshold=0.7):
        """Get events with confidence below threshold for a tenant."""
        return self.filter(tenant=tenant, confidence_score__lt=threshold)


class IntentEvent(BaseModel):
    """
    Intent event model for tracking AI intent classifications.
    
    Each intent event:
    - Records the classified intent from customer message
    - Stores confidence score for quality monitoring
    - Captures extracted slots/entities
    - Tracks which AI model was used
    - Enables analytics on intent patterns
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='intent_events',
        db_index=True,
        help_text="Tenant this intent event belongs to"
    )
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='intent_events',
        db_index=True,
        help_text="Conversation this intent belongs to"
    )
    
    # Intent Classification
    intent_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Classified intent name (e.g., BROWSE_PRODUCTS, BOOK_APPOINTMENT)"
    )
    confidence_score = models.FloatField(
        help_text="Confidence score from 0.0 to 1.0"
    )
    
    # Extracted Data
    slots = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extracted entities/slots from the message"
    )
    
    # Model Tracking
    model = models.CharField(
        max_length=50,
        help_text="AI model used for classification (e.g., gpt-4, claude-3)"
    )
    
    # Input Context
    message_text = models.TextField(
        help_text="Original message text that was classified"
    )
    
    # Processing Metadata
    processing_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time taken to classify intent in milliseconds"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (prompt tokens, response tokens, etc.)"
    )
    
    # Custom manager
    objects = IntentEventManager()
    
    class Meta:
        db_table = 'intent_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'intent_name', 'created_at']),
            models.Index(fields=['tenant', 'confidence_score']),
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'intent_name']),
        ]
    
    def __str__(self):
        return f"IntentEvent {self.id} - {self.intent_name} ({self.confidence_score:.2f})"
    
    def is_high_confidence(self, threshold=0.7):
        """Check if confidence score is above threshold."""
        return self.confidence_score >= threshold
    
    def is_low_confidence(self, threshold=0.7):
        """Check if confidence score is below threshold."""
        return self.confidence_score < threshold
    
    def get_slot(self, slot_name, default=None):
        """Get a specific slot value."""
        return self.slots.get(slot_name, default)
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency with conversation."""
        if self.conversation_id and not self.tenant_id:
            # Auto-populate tenant from conversation
            self.tenant = self.conversation.tenant
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValueError(
                    f"IntentEvent tenant ({self.tenant_id}) must match "
                    f"Conversation tenant ({self.conversation.tenant_id})"
                )
        
        super().save(*args, **kwargs)


class ConversationContextManager(models.Manager):
    """Manager for conversation context queries with tenant scoping."""
    
    def for_conversation(self, conversation):
        """Get context for a specific conversation."""
        return self.filter(conversation=conversation).first()
    
    def for_tenant(self, tenant):
        """Get contexts for a specific tenant."""
        return self.filter(conversation__tenant=tenant)
    
    def active(self):
        """Get contexts that haven't expired."""
        from django.utils import timezone
        return self.filter(
            models.Q(context_expires_at__isnull=True) |
            models.Q(context_expires_at__gt=timezone.now())
        )
    
    def expired(self):
        """Get contexts that have expired."""
        from django.utils import timezone
        return self.filter(
            context_expires_at__isnull=False,
            context_expires_at__lte=timezone.now()
        )


class ConversationContext(BaseModel):
    """
    Conversation context for memory storage and state tracking.
    
    Stores contextual information about ongoing conversations to enable
    the AI agent to maintain memory across messages. This includes:
    - Current topic being discussed
    - Pending actions or requests
    - Extracted entities (product names, dates, etc.)
    - References to last viewed items
    - Conversation summary for long histories
    - Key facts to remember
    
    Context expires after 30 minutes of inactivity by default, but key
    facts are preserved for future sessions.
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    """
    
    conversation = models.OneToOneField(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='context',
        db_index=True,
        help_text="Conversation this context belongs to"
    )
    
    # Current State
    current_topic = models.CharField(
        max_length=100,
        blank=True,
        help_text="Current topic being discussed (e.g., 'product_inquiry', 'booking_appointment')"
    )
    
    pending_action = models.CharField(
        max_length=100,
        blank=True,
        help_text="Pending action waiting for customer input (e.g., 'awaiting_date_selection')"
    )
    
    extracted_entities = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extracted entities from conversation (e.g., {'product_name': 'Blue Shirt', 'size': 'L'})"
    )
    
    # References to Catalog Items
    last_product_viewed = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='context_views',
        help_text="Last product the customer viewed or inquired about"
    )
    
    last_service_viewed = models.ForeignKey(
        'services.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='context_views',
        help_text="Last service the customer viewed or inquired about"
    )
    
    # Memory and Summary
    conversation_summary = models.TextField(
        blank=True,
        help_text="AI-generated summary of conversation history for context window management"
    )
    
    key_facts = models.JSONField(
        default=list,
        blank=True,
        help_text="List of key facts to remember (e.g., ['Customer prefers blue', 'Budget is $50'])"
    )
    
    # Timing
    last_interaction = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last interaction (auto-updated)"
    )
    
    context_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When this context expires (null = never expires)"
    )
    
    # Progressive Handoff
    clarification_attempts = models.IntegerField(
        default=0,
        help_text="Number of clarification attempts made before handoff"
    )
    
    # Shopping Cart
    shopping_cart = models.JSONField(
        default=dict,
        blank=True,
        help_text="Shopping cart for multi-item purchases"
    )
    
    # Language Consistency
    language_locked = models.BooleanField(
        default=False,
        help_text="Whether language preference is locked for this conversation"
    )
    
    # Sales Orchestration - Flow State
    current_flow = models.CharField(
        max_length=50,
        blank=True,
        help_text="Current flow state (e.g., 'browsing_products', 'checkout', 'booking')"
    )
    awaiting_response = models.BooleanField(
        default=False,
        help_text="Whether bot is awaiting a specific response from customer"
    )
    last_question = models.TextField(
        blank=True,
        help_text="Last question asked by bot (for context)"
    )
    
    # Reference Resolution
    last_menu = models.JSONField(
        default=dict,
        blank=True,
        help_text="Last displayed menu for reference resolution (e.g., {'type': 'products', 'items': [...]})"
    )
    last_menu_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last_menu was created (for expiration checking)"
    )
    
    # Language Detection
    detected_language = models.JSONField(
        default=list,
        blank=True,
        help_text="Detected languages (e.g., ['en'], ['sw'], ['sheng'])"
    )
    
    # Checkout State
    checkout_state = models.CharField(
        max_length=50,
        default='browsing',
        help_text="Current checkout state (browsing, product_selected, etc.)"
    )
    selected_product_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of currently selected product in checkout"
    )
    selected_quantity = models.IntegerField(
        null=True,
        blank=True,
        help_text="Selected quantity for checkout"
    )
    
    # Session Tracking
    current_session_start = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Start time of current conversation session"
    )
    session_message_count = models.IntegerField(
        default=0,
        help_text="Number of messages in current session"
    )
    
    # Last Messages (for echo prevention)
    last_bot_message = models.TextField(
        blank=True,
        help_text="Last message sent by bot (for echo prevention)"
    )
    last_customer_message = models.TextField(
        blank=True,
        help_text="Last message sent by customer (for echo prevention)"
    )
    
    # Custom manager
    objects = ConversationContextManager()
    
    class Meta:
        db_table = 'conversation_contexts'
        verbose_name = 'Conversation Context'
        verbose_name_plural = 'Conversation Contexts'
        indexes = [
            models.Index(fields=['conversation', 'last_interaction']),
            models.Index(fields=['context_expires_at']),
        ]
    
    def __str__(self):
        return f"Context for Conversation {self.conversation_id} - {self.current_topic or 'No topic'}"
    
    def get_entity(self, entity_name, default=None):
        """Get a specific extracted entity value."""
        return self.extracted_entities.get(entity_name, default)
    
    def set_entity(self, entity_name, value):
        """Set a specific extracted entity value."""
        self.extracted_entities[entity_name] = value
        self.save(update_fields=['extracted_entities'])
    
    def add_key_fact(self, fact):
        """Add a key fact to remember."""
        if fact not in self.key_facts:
            self.key_facts.append(fact)
            self.save(update_fields=['key_facts'])
    
    def clear_key_facts(self):
        """Clear all key facts."""
        self.key_facts = []
        self.save(update_fields=['key_facts'])
    
    def is_expired(self):
        """Check if context has expired."""
        if not self.context_expires_at:
            return False
        from django.utils import timezone
        return self.context_expires_at <= timezone.now()
    
    def extend_expiration(self, minutes=30):
        """Extend context expiration by specified minutes."""
        from django.utils import timezone
        from datetime import timedelta
        self.context_expires_at = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=['context_expires_at'])
    
    def clear_context(self, preserve_key_facts=True):
        """Clear context state, optionally preserving key facts."""
        self.current_topic = ''
        self.pending_action = ''
        self.extracted_entities = {}
        self.last_product_viewed = None
        self.last_service_viewed = None
        self.conversation_summary = ''
        
        if not preserve_key_facts:
            self.key_facts = []
        
        update_fields = [
            'current_topic', 'pending_action', 'extracted_entities',
            'last_product_viewed', 'last_service_viewed', 'conversation_summary'
        ]
        if not preserve_key_facts:
            update_fields.append('key_facts')
        
        self.save(update_fields=update_fields)
    
    def save(self, *args, **kwargs):
        """Override save to set default expiration if not set."""
        # Check if this is a new object (not yet in database)
        is_new = self._state.adding
        
        if not self.context_expires_at and is_new:
            # Set default expiration to 30 minutes on creation
            from django.utils import timezone
            from datetime import timedelta
            self.context_expires_at = timezone.now() + timedelta(minutes=30)
        
        super().save(*args, **kwargs)


# Import ConversationSession from the existing file
from apps.bot.models_conversation_state import (
    ConversationSession,
    ConversationStateService,
)