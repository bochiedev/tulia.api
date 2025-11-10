"""
Bot models for intent classification and tracking.

Implements intent event tracking for analytics and debugging
of AI-powered conversation handling.
"""
from django.db import models
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
