"""
Analytics and tracking models for bot performance monitoring.

Consolidates all analytics-related models including usage tracking,
performance metrics, and provider monitoring.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from apps.core.models import BaseModel


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


class MessageHarmonizationLogManager(models.Manager):
    """Manager for message harmonization log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get harmonization logs for a specific tenant."""
        return self.filter(conversation__tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get harmonization logs for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def recent(self, tenant, hours=24):
        """Get recent harmonization logs for a tenant."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(conversation__tenant=tenant, created_at__gte=cutoff)


class MessageHarmonizationLog(BaseModel):
    """
    Tracks message harmonization events for analytics and debugging.
    
    Records when multiple rapid messages are combined into a single
    conversational turn, enabling analysis of harmonization effectiveness
    and customer messaging patterns.
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    All queries MUST filter by conversation__tenant to prevent cross-tenant data leakage.
    """
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='harmonization_logs',
        db_index=True,
        help_text="Conversation this harmonization belongs to"
    )
    
    # Input Messages
    message_ids = models.JSONField(
        help_text="List of message IDs that were combined"
    )
    
    message_count = models.IntegerField(
        default=0,
        help_text="Number of messages combined"
    )
    
    combined_text = models.TextField(
        help_text="Combined text from all messages"
    )
    
    # Timing
    wait_time_ms = models.IntegerField(
        help_text="Time waited before processing in milliseconds"
    )
    
    first_message_at = models.DateTimeField(
        help_text="Timestamp of first message in burst"
    )
    
    last_message_at = models.DateTimeField(
        help_text="Timestamp of last message in burst"
    )
    
    # Output
    response_generated = models.TextField(
        help_text="Generated response to harmonized messages"
    )
    
    response_time_ms = models.IntegerField(
        default=0,
        help_text="Time taken to generate response in milliseconds"
    )
    
    # Metadata
    typing_indicator_shown = models.BooleanField(
        default=False,
        help_text="Whether typing indicator was shown during wait"
    )
    
    success = models.BooleanField(
        default=True,
        help_text="Whether harmonization was successful"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if harmonization failed"
    )
    
    # Custom manager
    objects = MessageHarmonizationLogManager()
    
    class Meta:
        db_table = 'bot_message_harmonization_logs'
        verbose_name = 'Message Harmonization Log'
        verbose_name_plural = 'Message Harmonization Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'success']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"MessageHarmonizationLog {self.id} - {self.message_count} messages"
    
    def get_time_span_seconds(self):
        """Calculate time span between first and last message in seconds."""
        if self.first_message_at and self.last_message_at:
            delta = self.last_message_at - self.first_message_at
            return delta.total_seconds()
        return 0.0
    
    def get_average_message_gap_ms(self):
        """Calculate average gap between messages in milliseconds."""
        if self.message_count <= 1:
            return 0
        time_span_ms = self.get_time_span_seconds() * 1000
        return time_span_ms / (self.message_count - 1)
    
    def save(self, *args, **kwargs):
        """Override save to auto-populate message_count."""
        if isinstance(self.message_ids, list):
            self.message_count = len(self.message_ids)
        super().save(*args, **kwargs)


class IntentClassificationLogManager(models.Manager):
    """Manager for intent classification log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get intent classification logs for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def by_intent(self, tenant, intent_name):
        """Get logs for a specific intent within a tenant."""
        return self.filter(tenant=tenant, intent_name=intent_name)
    
    def recent(self, tenant, hours=24):
        """Get recent intent classification logs for a tenant."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(tenant=tenant, created_at__gte=cutoff)


class IntentClassificationLog(BaseModel):
    """
    Track intent classification for analytics and debugging.
    
    Records every intent classification attempt to enable:
    - Intent accuracy monitoring
    - Model performance analysis
    - Debugging classification issues
    - Training data collection
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='intent_classification_logs',
        db_index=True,
        help_text="Tenant this log belongs to"
    )
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='intent_logs',
        db_index=True,
        help_text="Conversation this classification belongs to"
    )
    
    # Input
    message_text = models.TextField(
        help_text="Original message text that was classified"
    )
    
    # Classification Results
    intent_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Classified intent name"
    )
    
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score for the classification (0.0-1.0)"
    )
    
    # Model Information
    model_used = models.CharField(
        max_length=50,
        db_index=True,
        help_text="LLM model used for classification"
    )
    
    processing_time_ms = models.IntegerField(
        default=0,
        help_text="Time taken for classification in milliseconds"
    )
    
    # Additional Results
    all_intents = models.JSONField(
        default=list,
        blank=True,
        help_text="All detected intents with scores"
    )
    
    slots = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extracted slots from the message"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (context, features, etc.)"
    )
    
    # Custom manager
    objects = IntentClassificationLogManager()
    
    class Meta:
        db_table = 'bot_intent_classification_logs'
        verbose_name = 'Intent Classification Log'
        verbose_name_plural = 'Intent Classification Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'intent_name']),
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['model_used', 'created_at']),
        ]
    
    def __str__(self):
        return f"IntentLog {self.id} - {self.intent_name} ({self.confidence_score:.2f})"


class LLMUsageLogManager(models.Manager):
    """Manager for LLM usage log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get LLM usage logs for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def by_provider(self, tenant, provider):
        """Get logs for a specific provider within a tenant."""
        return self.filter(tenant=tenant, provider=provider)
    
    def by_model(self, tenant, model):
        """Get logs for a specific model within a tenant."""
        return self.filter(tenant=tenant, model=model)
    
    def current_month(self, tenant):
        """Get current month usage for a tenant."""
        from django.utils import timezone
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(tenant=tenant, created_at__gte=current_month)


class LLMUsageLog(BaseModel):
    """
    Track LLM usage and costs per tenant.
    
    Records every LLM API call to enable:
    - Cost tracking and budgeting
    - Usage analytics and optimization
    - Provider performance monitoring
    - Billing and reporting
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='llm_usage_logs',
        db_index=True,
        help_text="Tenant this usage belongs to"
    )
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='llm_usage_logs',
        null=True,
        blank=True,
        help_text="Conversation this usage belongs to (if applicable)"
    )
    
    # Provider Information
    provider = models.CharField(
        max_length=50,
        db_index=True,
        help_text="LLM provider (e.g., 'openai', 'anthropic')"
    )
    
    model = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Model name (e.g., 'gpt-4o', 'claude-3-sonnet')"
    )
    
    # Task Information
    task_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of task (e.g., 'intent_classification', 'response_generation')"
    )
    
    # Usage Metrics
    input_tokens = models.IntegerField(
        default=0,
        help_text="Number of input tokens used"
    )
    
    output_tokens = models.IntegerField(
        default=0,
        help_text="Number of output tokens generated"
    )
    
    total_tokens = models.IntegerField(
        default=0,
        help_text="Total tokens (input + output)"
    )
    
    # Cost Information
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Cost in USD for this API call"
    )
    
    # Performance Metrics
    response_time_ms = models.IntegerField(
        default=0,
        help_text="Response time in milliseconds"
    )
    
    # Status
    success = models.BooleanField(
        default=True,
        help_text="Whether the API call was successful"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if the call failed"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (temperature, max_tokens, etc.)"
    )
    
    # Custom manager
    objects = LLMUsageLogManager()
    
    class Meta:
        db_table = 'bot_llm_usage_logs'
        verbose_name = 'LLM Usage Log'
        verbose_name_plural = 'LLM Usage Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'provider', 'created_at']),
            models.Index(fields=['tenant', 'model', 'created_at']),
            models.Index(fields=['task_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"LLMUsage {self.id} - {self.provider}/{self.model} (${self.cost})"
    
    def save(self, *args, **kwargs):
        """Override save to calculate total tokens."""
        self.total_tokens = self.input_tokens + self.output_tokens
        super().save(*args, **kwargs)


class PaymentRequestManager(models.Manager):
    """Manager for payment request queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get payment requests for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def by_status(self, tenant, status):
        """Get payment requests by status within a tenant."""
        return self.filter(tenant=tenant, status=status)
    
    def successful(self, tenant):
        """Get successful payment requests for a tenant."""
        return self.filter(tenant=tenant, status='completed')
    
    def failed(self, tenant):
        """Get failed payment requests for a tenant."""
        return self.filter(tenant=tenant, status='failed')


class PaymentRequest(BaseModel):
    """
    Track payment attempts for analytics and debugging.
    
    Records payment requests initiated through the bot to enable:
    - Payment success rate monitoring
    - Failure analysis and debugging
    - Revenue tracking and reporting
    - Customer payment behavior analysis
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        db_index=True,
        help_text="Tenant this payment request belongs to"
    )
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        db_index=True,
        help_text="Conversation this payment was initiated from"
    )
    
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        null=True,
        blank=True,
        help_text="Order this payment is for (if applicable)"
    )
    
    # Payment Information
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Payment amount"
    )
    
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code (ISO 4217)"
    )
    
    # Status Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current status of the payment request"
    )
    
    # Provider Information
    payment_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment provider used (e.g., 'stripe', 'paypal')"
    )
    
    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Transaction ID from payment provider"
    )
    
    # Timing
    initiated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the payment request was initiated"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the payment was completed"
    )
    
    # Error Tracking
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Error code if payment failed"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if payment failed"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (payment method, customer info, etc.)"
    )
    
    # Custom manager
    objects = PaymentRequestManager()
    
    class Meta:
        db_table = 'bot_payment_requests'
        verbose_name = 'Payment Request'
        verbose_name_plural = 'Payment Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"PaymentRequest {self.id} - {self.amount} {self.currency} ({self.status})"
    
    def is_successful(self):
        """Check if payment was successful."""
        return self.status == 'completed'
    
    def is_failed(self):
        """Check if payment failed."""
        return self.status == 'failed'
    
    def get_processing_time_seconds(self):
        """Get processing time in seconds if completed."""
        if self.completed_at and self.initiated_at:
            delta = self.completed_at - self.initiated_at
            return delta.total_seconds()
        return None