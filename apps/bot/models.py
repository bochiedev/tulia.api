"""
Bot models - consolidated imports from organized model files.

This file serves as the main entry point for all bot models,
importing from logically organized model files.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from apps.core.models import BaseModel

# Import knowledge models
from apps.bot.models_knowledge import (
    KnowledgeEntry,
    Document,
    DocumentChunk,
)

# Import conversation models
from apps.bot.models_conversation import (
    IntentEvent,
    ConversationContext,
)

from apps.bot.models_conversation_state import (
    ConversationSession,
    ConversationStateService,
)

# Import analytics models
from apps.bot.models_analytics import (
    AgentInteraction,
    MessageHarmonizationLog,
    IntentClassificationLog,
    LLMUsageLog,
    PaymentRequest,
)

# Import transaction models
from apps.bot.models_transactions import (
    BrowseSession,
    ReferenceContext,
    ProductAnalysis,
    LanguagePreference,
)

# Import feedback models
from apps.bot.models_feedback import (
    InteractionFeedback,
    HumanCorrection
)


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
    
    enable_feedback_collection = models.BooleanField(
        default=True,
        help_text="Enable feedback collection buttons after bot responses"
    )
    
    feedback_frequency = models.CharField(
        max_length=20,
        choices=[
            ('always', 'Always'),
            ('sometimes', 'Sometimes (every 3rd message)'),
            ('never', 'Never'),
        ],
        default='sometimes',
        help_text="How often to show feedback buttons"
    )
    
    enable_grounded_validation = models.BooleanField(
        default=True,
        help_text="Enable validation that responses are grounded in actual data (prevents hallucinations)"
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
    
    # Branding Configuration
    use_business_name_as_identity = models.BooleanField(
        default=True,
        help_text="Use tenant's business name in bot identity"
    )
    
    custom_bot_greeting = models.TextField(
        blank=True,
        help_text="Custom greeting message for first contact (overrides default)"
    )
    
    # LLM Budget Configuration
    monthly_llm_budget_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Monthly LLM budget in USD"
    )
    llm_budget_exceeded_action = models.CharField(
        max_length=20,
        choices=[
            ('fallback', 'Fallback to rules'),
            ('throttle', 'Throttle usage'),
            ('stop', 'Stop LLM usage'),
        ],
        default='fallback',
        help_text="Action to take when LLM budget is exceeded"
    )
    
    # Business Hours
    business_hours_start = models.TimeField(
        default='08:00:00',
        help_text="Business hours start time"
    )
    business_hours_end = models.TimeField(
        default='20:00:00',
        help_text="Business hours end time"
    )
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Quiet hours start time (no automated messages)"
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="Quiet hours end time"
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


__all__ = [
    # Configuration
    'AgentConfiguration',
    # Knowledge models
    'KnowledgeEntry',
    'Document',
    'DocumentChunk',
    # Core conversation models
    'IntentEvent',
    'ConversationContext',
    'ConversationSession',
    'ConversationStateService',
    # Analytics models
    'AgentInteraction',
    'MessageHarmonizationLog',
    'IntentClassificationLog',
    'LLMUsageLog',
    'PaymentRequest',
    # Transaction models
    'BrowseSession',
    'ReferenceContext',
    'ProductAnalysis',
    'LanguagePreference',
    # Feedback models
    'InteractionFeedback',
    'HumanCorrection',
]