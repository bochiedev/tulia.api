"""
Bot models for intent classification and tracking.

Implements intent event tracking for analytics and debugging
of AI-powered conversation handling.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
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


class AgentConfiguration(BaseModel):
    """
    Tenant-specific AI agent configuration.
    
    Controls the agent's persona, behavior, model selection, and features.
    Each tenant has one configuration that defines how their AI agent
    interacts with customers.
    
    TENANT SCOPING: One-to-one relationship with Tenant ensures isolation.
    """
    
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='agent_configuration',
        db_index=True,
        help_text="Tenant this configuration belongs to"
    )
    
    # Persona Configuration
    agent_name = models.CharField(
        max_length=100,
        default="Assistant",
        help_text="Name of the AI agent (e.g., 'Sarah', 'TechBot')"
    )
    
    personality_traits = models.JSONField(
        default=dict,
        blank=True,
        help_text="Personality traits as key-value pairs (e.g., {'helpful': true, 'empathetic': true})"
    )
    
    tone = models.CharField(
        max_length=20,
        choices=[
            ('professional', 'Professional'),
            ('friendly', 'Friendly'),
            ('casual', 'Casual'),
            ('formal', 'Formal'),
        ],
        default='friendly',
        help_text="Communication tone for the agent"
    )
    
    # Model Configuration
    default_model = models.CharField(
        max_length=50,
        default='gpt-4o',
        help_text="Default LLM model to use (e.g., 'gpt-4o', 'o1-preview', 'o1-mini')"
    )
    
    fallback_models = models.JSONField(
        default=list,
        blank=True,
        help_text="List of fallback models to try if default fails (e.g., ['gpt-4o-mini', 'gpt-3.5-turbo'])"
    )
    
    temperature = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
        help_text="Temperature for response generation (0.0-2.0, higher = more creative)"
    )
    
    # Behavior Configuration
    max_response_length = models.IntegerField(
        default=500,
        validators=[MinValueValidator(50), MaxValueValidator(2000)],
        help_text="Maximum length of agent responses in characters"
    )
    
    behavioral_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of topics or behaviors to avoid (e.g., ['politics', 'medical advice'])"
    )
    
    required_disclaimers = models.JSONField(
        default=list,
        blank=True,
        help_text="List of disclaimers to include in responses (e.g., ['I am an AI assistant'])"
    )
    
    # Handoff Configuration
    confidence_threshold = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum confidence score to proceed without handoff (0.0-1.0)"
    )
    
    auto_handoff_topics = models.JSONField(
        default=list,
        blank=True,
        help_text="Topics that always trigger handoff to human (e.g., ['refund', 'complaint'])"
    )
    
    max_low_confidence_attempts = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Number of low-confidence responses before triggering handoff"
    )
    
    # Feature Flags
    enable_proactive_suggestions = models.BooleanField(
        default=True,
        help_text="Enable proactive product/service suggestions"
    )
    
    enable_spelling_correction = models.BooleanField(
        default=True,
        help_text="Enable automatic spelling correction for customer messages"
    )
    
    enable_rich_messages = models.BooleanField(
        default=True,
        help_text="Enable rich WhatsApp messages (buttons, lists, media)"
    )
    
    class Meta:
        db_table = 'agent_configurations'
        verbose_name = 'Agent Configuration'
        verbose_name_plural = 'Agent Configurations'
    
    def __str__(self):
        return f"AgentConfiguration for {self.tenant.name} - {self.agent_name}"
    
    def get_personality_trait(self, trait_name, default=None):
        """Get a specific personality trait value."""
        return self.personality_traits.get(trait_name, default)
    
    def has_behavioral_restriction(self, topic):
        """Check if a topic is in behavioral restrictions."""
        return topic.lower() in [r.lower() for r in self.behavioral_restrictions]
    
    def should_auto_handoff(self, topic):
        """Check if a topic should trigger automatic handoff."""
        return topic.lower() in [t.lower() for t in self.auto_handoff_topics]
    
    def get_fallback_model(self, index=0):
        """Get a fallback model by index, or None if not available."""
        if index < len(self.fallback_models):
            return self.fallback_models[index]
        return None


class KnowledgeEntryManager(models.Manager):
    """Manager for knowledge entry queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get active knowledge entries for a specific tenant."""
        return self.filter(tenant=tenant, is_active=True)
    
    def by_category(self, tenant, category):
        """Get entries for a specific category within a tenant."""
        return self.filter(tenant=tenant, category=category, is_active=True)
    
    def by_type(self, tenant, entry_type):
        """Get entries of a specific type within a tenant."""
        return self.filter(tenant=tenant, entry_type=entry_type, is_active=True)
    
    def search_by_keywords(self, tenant, keywords):
        """Search entries by keywords within a tenant."""
        query = self.filter(tenant=tenant, is_active=True)
        for keyword in keywords:
            query = query.filter(keywords__icontains=keyword)
        return query


class KnowledgeEntry(BaseModel):
    """
    Knowledge base entry for AI agent context.
    
    Stores information that the AI agent can reference when responding
    to customer queries. Supports semantic search via embeddings for
    intelligent context retrieval.
    
    Entry types:
    - faq: Frequently asked questions and answers
    - policy: Business policies (returns, shipping, etc.)
    - product_info: Detailed product information
    - service_info: Detailed service information
    - procedure: Step-by-step procedures
    - general: General knowledge
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='knowledge_entries',
        db_index=True,
        help_text="Tenant this knowledge entry belongs to"
    )
    
    # Entry Classification
    entry_type = models.CharField(
        max_length=20,
        choices=[
            ('faq', 'FAQ'),
            ('policy', 'Policy'),
            ('product_info', 'Product Information'),
            ('service_info', 'Service Information'),
            ('procedure', 'Procedure'),
            ('general', 'General Knowledge'),
        ],
        default='general',
        db_index=True,
        help_text="Type of knowledge entry"
    )
    
    category = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Category for organizing entries (e.g., 'shipping', 'returns', 'technical')"
    )
    
    # Content
    title = models.CharField(
        max_length=255,
        help_text="Title or question for this entry"
    )
    
    content = models.TextField(
        help_text="Full content or answer for this entry"
    )
    
    # Search Optimization
    keywords = models.TextField(
        blank=True,
        help_text="Comma-separated keywords for search optimization"
    )
    
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="Vector embedding for semantic search (generated from title + content)"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (source, author, related_entries, etc.)"
    )
    
    # Priority and Status
    priority = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Priority for ranking search results (0-100, higher = more important)"
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this entry is active and should be used by the agent"
    )
    
    # Versioning
    version = models.IntegerField(
        default=1,
        help_text="Version number for tracking updates"
    )
    
    # Custom manager
    objects = KnowledgeEntryManager()
    
    class Meta:
        db_table = 'knowledge_entries'
        verbose_name = 'Knowledge Entry'
        verbose_name_plural = 'Knowledge Entries'
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'priority']),
            models.Index(fields=['tenant', 'entry_type', 'is_active']),
            models.Index(fields=['tenant', 'category', 'is_active']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        return f"KnowledgeEntry {self.id} - {self.title} ({self.tenant.name})"
    
    def get_keywords_list(self):
        """Get keywords as a list."""
        if not self.keywords:
            return []
        return [k.strip() for k in self.keywords.split(',') if k.strip()]
    
    def set_keywords_list(self, keywords_list):
        """Set keywords from a list."""
        self.keywords = ', '.join(keywords_list)
    
    def increment_version(self):
        """Increment version number."""
        self.version += 1
    
    def get_metadata_field(self, field_name, default=None):
        """Get a specific metadata field value."""
        return self.metadata.get(field_name, default)
    
    def save(self, *args, **kwargs):
        """Override save to validate tenant consistency."""
        super().save(*args, **kwargs)
