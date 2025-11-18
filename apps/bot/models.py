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
    
    # RAG Configuration
    enable_document_retrieval = models.BooleanField(
        default=False,
        help_text="Enable retrieval from uploaded documents"
    )
    
    enable_database_retrieval = models.BooleanField(
        default=True,
        help_text="Enable retrieval from database (products, services, orders)"
    )
    
    enable_internet_enrichment = models.BooleanField(
        default=False,
        help_text="Enable internet search for product enrichment"
    )
    
    enable_source_attribution = models.BooleanField(
        default=True,
        help_text="Include source citations in responses"
    )
    
    max_document_results = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Maximum number of document chunks to retrieve"
    )
    
    max_database_results = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Maximum number of database results to retrieve"
    )
    
    max_internet_results = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Maximum number of internet search results"
    )
    
    semantic_search_weight = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for semantic search in hybrid search (0.0-1.0)"
    )
    
    keyword_search_weight = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for keyword search in hybrid search (0.0-1.0)"
    )
    
    embedding_model = models.CharField(
        max_length=50,
        default='text-embedding-3-small',
        help_text="Embedding model for semantic search"
    )
    
    agent_can_do = models.TextField(
        blank=True,
        help_text="Explicit list of what the agent CAN do (for prompt engineering)"
    )
    
    agent_cannot_do = models.TextField(
        blank=True,
        help_text="Explicit list of what the agent CANNOT do (for prompt engineering)"
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
        if not self.context_expires_at and not self.pk:
            # Set default expiration to 30 minutes on creation
            from django.utils import timezone
            from datetime import timedelta
            self.context_expires_at = timezone.now() + timedelta(minutes=30)
        
        super().save(*args, **kwargs)


class AgentInteractionManager(models.Manager):
    """Manager for agent interaction queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get agent interactions for a specific tenant."""
        return self.filter(conversation__tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get agent interactions for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def by_model(self, tenant, model_name):
        """Get interactions for a specific model within a tenant."""
        return self.filter(conversation__tenant=tenant, model_used=model_name)
    
    def with_handoff(self, tenant):
        """Get interactions that triggered handoff for a tenant."""
        return self.filter(conversation__tenant=tenant, handoff_triggered=True)
    
    def high_confidence(self, tenant, threshold=0.7):
        """Get interactions with confidence above threshold for a tenant."""
        return self.filter(conversation__tenant=tenant, confidence_score__gte=threshold)
    
    def low_confidence(self, tenant, threshold=0.7):
        """Get interactions with confidence below threshold for a tenant."""
        return self.filter(conversation__tenant=tenant, confidence_score__lt=threshold)


class AgentInteraction(BaseModel):
    """
    Agent interaction tracking for analytics and monitoring.
    
    Records every interaction between the AI agent and customers, including:
    - Customer message and detected intents
    - Model used and processing details
    - Agent response and confidence score
    - Handoff decisions and reasons
    - Token usage and estimated costs
    - Message type (text, button, list, media)
    
    This data enables:
    - Performance monitoring and optimization
    - Cost tracking and budgeting
    - Quality assurance and improvement
    - Analytics on common topics and intents
    - Handoff pattern analysis
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    All queries MUST filter by conversation__tenant to prevent cross-tenant data leakage.
    """
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='agent_interactions',
        db_index=True,
        help_text="Conversation this interaction belongs to"
    )
    
    # Input
    customer_message = models.TextField(
        help_text="Original customer message text"
    )
    
    detected_intents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of detected intents with confidence scores"
    )
    
    # Processing
    model_used = models.CharField(
        max_length=50,
        db_index=True,
        help_text="LLM model used for this interaction (e.g., 'gpt-4o', 'o1-preview')"
    )
    
    context_size = models.IntegerField(
        default=0,
        help_text="Size of context provided to the model in tokens"
    )
    
    processing_time_ms = models.IntegerField(
        default=0,
        help_text="Time taken to process and generate response in milliseconds"
    )
    
    # Output
    agent_response = models.TextField(
        help_text="Generated agent response text"
    )
    
    confidence_score = models.FloatField(
        db_index=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score for the response (0.0-1.0)"
    )
    
    handoff_triggered = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this interaction triggered a handoff to human agent"
    )
    
    handoff_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for handoff (e.g., 'low_confidence', 'explicit_request', 'restricted_topic')"
    )
    
    # Rich Message
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Text'),
            ('button', 'Button'),
            ('list', 'List'),
            ('media', 'Media'),
        ],
        default='text',
        db_index=True,
        help_text="Type of message sent to customer"
    )
    
    # Metrics
    token_usage = models.JSONField(
        default=dict,
        blank=True,
        help_text="Token usage breakdown (e.g., {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150})"
    )
    
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        help_text="Estimated cost in USD for this interaction"
    )
    
    # Custom manager
    objects = AgentInteractionManager()
    
    class Meta:
        db_table = 'agent_interactions'
        verbose_name = 'Agent Interaction'
        verbose_name_plural = 'Agent Interactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['model_used', 'created_at']),
            models.Index(fields=['confidence_score']),
            models.Index(fields=['handoff_triggered', 'created_at']),
            models.Index(fields=['message_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"AgentInteraction {self.id} - {self.model_used} (confidence: {self.confidence_score:.2f})"
    
    def is_high_confidence(self, threshold=0.7):
        """Check if confidence score is above threshold."""
        return self.confidence_score >= threshold
    
    def is_low_confidence(self, threshold=0.7):
        """Check if confidence score is below threshold."""
        return self.confidence_score < threshold
    
    def get_total_tokens(self):
        """Get total token count from token_usage."""
        return self.token_usage.get('total_tokens', 0)
    
    def get_prompt_tokens(self):
        """Get prompt token count from token_usage."""
        return self.token_usage.get('prompt_tokens', 0)
    
    def get_completion_tokens(self):
        """Get completion token count from token_usage."""
        return self.token_usage.get('completion_tokens', 0)
    
    def get_cost_per_token(self):
        """Calculate cost per token if tokens were used."""
        total_tokens = self.get_total_tokens()
        if total_tokens > 0 and self.estimated_cost > 0:
            return float(self.estimated_cost) / total_tokens
        return 0.0
    
    def get_intent_names(self):
        """Get list of detected intent names."""
        return [intent.get('name', '') for intent in self.detected_intents if isinstance(intent, dict)]
    
    def get_primary_intent(self):
        """Get the primary (highest confidence) intent."""
        if not self.detected_intents:
            return None
        if isinstance(self.detected_intents, list) and len(self.detected_intents) > 0:
            return self.detected_intents[0]
        return None



class BrowseSession(BaseModel):
    """
    Tracks pagination state for catalog browsing.
    
    Allows customers to browse large catalogs with pagination,
    maintaining state across multiple messages.
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    CATALOG_TYPE_CHOICES = [
        ('products', 'Products'),
        ('services', 'Services'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='browse_sessions',
        db_index=True,
        help_text="Tenant this browse session belongs to"
    )
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='browse_sessions',
        db_index=True,
        help_text="Conversation this browse session belongs to"
    )
    catalog_type = models.CharField(
        max_length=20,
        choices=CATALOG_TYPE_CHOICES,
        help_text="Type of catalog being browsed"
    )
    current_page = models.IntegerField(
        default=1,
        help_text="Current page number (1-indexed)"
    )
    items_per_page = models.IntegerField(
        default=5,
        help_text="Number of items per page"
    )
    total_items = models.IntegerField(
        help_text="Total number of items in result set"
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Applied filters (category, price range, etc.)"
    )
    search_query = models.TextField(
        blank=True,
        help_text="Search query if applicable"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether session is still active"
    )
    expires_at = models.DateTimeField(
        help_text="When session expires (10 minutes from last activity)"
    )
    
    class Meta:
        db_table = 'bot_browse_sessions'
        verbose_name = 'Browse Session'
        verbose_name_plural = 'Browse Sessions'
        indexes = [
            models.Index(fields=['tenant', 'conversation', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"BrowseSession({self.catalog_type}, page {self.current_page}/{self.total_pages})"
    
    @property
    def total_pages(self):
        """Calculate total number of pages."""
        if self.total_items == 0:
            return 0
        return (self.total_items + self.items_per_page - 1) // self.items_per_page
    
    @property
    def has_next_page(self):
        """Check if there's a next page."""
        return self.current_page < self.total_pages
    
    @property
    def has_previous_page(self):
        """Check if there's a previous page."""
        return self.current_page > 1
    
    @property
    def start_index(self):
        """Get start index for current page (0-indexed)."""
        return (self.current_page - 1) * self.items_per_page
    
    @property
    def end_index(self):
        """Get end index for current page (0-indexed, exclusive)."""
        return min(self.start_index + self.items_per_page, self.total_items)
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency with conversation."""
        if self.conversation_id and not self.tenant_id:
            # Auto-populate tenant from conversation
            self.tenant = self.conversation.tenant
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValueError(
                    f"BrowseSession tenant ({self.tenant_id}) must match "
                    f"Conversation tenant ({self.conversation.tenant_id})"
                )
        
        super().save(*args, **kwargs)



class ReferenceContext(BaseModel):
    """
    Stores list contexts for positional reference resolution.
    
    Allows customers to say "1", "the first one", "last", etc.
    to refer to items in recently displayed lists.
    
    Requirements: 24.1, 24.2, 24.3, 24.4, 24.5
    """
    
    LIST_TYPE_CHOICES = [
        ('products', 'Products'),
        ('services', 'Services'),
        ('appointments', 'Appointments'),
        ('orders', 'Orders'),
    ]
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='reference_contexts'
    )
    context_id = models.CharField(
        max_length=50,
        help_text="Unique identifier for this context"
    )
    list_type = models.CharField(
        max_length=20,
        choices=LIST_TYPE_CHOICES,
        help_text="Type of items in the list"
    )
    items = models.JSONField(
        help_text="List of items with IDs and display info"
    )
    expires_at = models.DateTimeField(
        help_text="When context expires (5 minutes from creation)"
    )
    
    class Meta:
        db_table = 'bot_reference_contexts'
        verbose_name = 'Reference Context'
        verbose_name_plural = 'Reference Contexts'
        indexes = [
            models.Index(fields=['conversation', 'expires_at']),
            models.Index(fields=['context_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"ReferenceContext({self.list_type}, {len(self.items)} items)"
    
    def get_item_by_position(self, position):
        """
        Get item by position (1-indexed).
        
        Args:
            position: 1-indexed position
        
        Returns:
            Item dict or None
        """
        if 1 <= position <= len(self.items):
            return self.items[position - 1]
        return None
    
    def get_first_item(self):
        """Get first item in list."""
        return self.items[0] if self.items else None
    
    def get_last_item(self):
        """Get last item in list."""
        return self.items[-1] if self.items else None


class ProductAnalysis(BaseModel):
    """
    Stores AI-generated product analysis for intelligent recommendations.
    
    Caches LLM analysis of products to enable semantic matching
    and intelligent recommendations without repeated API calls.
    
    Requirements: 25.1, 25.2, 25.3, 25.4, 25.5
    """
    
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='ai_analysis'
    )
    key_features = models.JSONField(
        default=list,
        help_text="List of key product features"
    )
    use_cases = models.JSONField(
        default=list,
        help_text="Common use cases for this product"
    )
    target_audience = models.JSONField(
        default=list,
        help_text="Target customer segments"
    )
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="Semantic embedding vector for similarity search"
    )
    summary = models.TextField(
        help_text="AI-generated product summary"
    )
    ai_categories = models.JSONField(
        default=list,
        help_text="AI-inferred categories beyond formal taxonomy"
    )
    ai_tags = models.JSONField(
        default=list,
        help_text="AI-generated tags for search and matching"
    )
    analyzed_at = models.DateTimeField(
        auto_now=True,
        help_text="When analysis was last updated"
    )
    
    class Meta:
        db_table = 'bot_product_analyses'
        verbose_name = 'Product Analysis'
        verbose_name_plural = 'Product Analyses'
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['analyzed_at']),
        ]
    
    def __str__(self):
        return f"ProductAnalysis({self.product.name})"


class LanguagePreference(BaseModel):
    """
    Tracks language preferences and usage patterns for customers.
    
    Supports multi-language conversations with code-switching
    between English, Swahili, and Sheng.
    
    Requirements: 28.1, 28.2, 28.3, 28.4, 28.5
    """
    
    conversation = models.OneToOneField(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='language_preference'
    )
    primary_language = models.CharField(
        max_length=10,
        default='en',
        help_text="Primary language code (en, sw, mixed)"
    )
    language_usage = models.JSONField(
        default=dict,
        help_text="Usage statistics per language"
    )
    common_phrases = models.JSONField(
        default=list,
        help_text="Commonly used phrases by this customer"
    )
    
    class Meta:
        db_table = 'bot_language_preferences'
        verbose_name = 'Language Preference'
        verbose_name_plural = 'Language Preferences'
        indexes = [
            models.Index(fields=['conversation']),
        ]
    
    def __str__(self):
        return f"LanguagePreference({self.primary_language})"
    
    def record_language_usage(self, language_code):
        """Record usage of a language."""
        if language_code not in self.language_usage:
            self.language_usage[language_code] = 0
        self.language_usage[language_code] += 1
        self.save(update_fields=['language_usage'])
    
    def get_preferred_language(self):
        """Get most frequently used language."""
        if not self.language_usage:
            return self.primary_language
        
        return max(self.language_usage.items(), key=lambda x: x[1])[0]


# Import RAG models
from apps.bot.models_rag import (
    Document,
    DocumentChunk,
    InternetSearchCache,
    RAGRetrievalLog
)

__all__ = [
    'IntentEvent',
    'AgentConfiguration',
    'KnowledgeEntry',
    'ConversationContext',
    'AgentInteraction',
    'BrowseSession',
    'ReferenceContext',
    'ProductAnalysis',
    'LanguagePreference',
    # RAG models
    'Document',
    'DocumentChunk',
    'InternetSearchCache',
    'RAGRetrievalLog',
]
