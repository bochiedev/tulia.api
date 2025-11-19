"""
Provider tracking models for multi-provider LLM support.

Tracks costs, performance, and usage across different LLM providers.
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import BaseModel


class ProviderUsageManager(models.Manager):
    """Manager for provider usage queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get usage for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_provider(self, tenant, provider):
        """Get usage for a specific provider within a tenant."""
        return self.filter(tenant=tenant, provider=provider)
    
    def daily_summary(self, tenant, date):
        """Get daily summary for a tenant."""
        return self.filter(
            tenant=tenant,
            created_at__date=date
        ).values('provider', 'model').annotate(
            total_calls=models.Count('id'),
            total_tokens=models.Sum('total_tokens'),
            total_cost=models.Sum('estimated_cost'),
            avg_latency=models.Avg('latency_ms')
        )


class ProviderUsage(BaseModel):
    """
    Track individual LLM provider API calls.
    
    Records:
    - Provider and model used
    - Token usage and costs
    - Latency and performance
    - Success/failure status
    
    TENANT SCOPING: All queries MUST filter by tenant.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='provider_usage',
        db_index=True,
        help_text="Tenant this usage belongs to"
    )
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='provider_usage',
        null=True,
        blank=True,
        help_text="Conversation this usage is associated with"
    )
    
    agent_interaction = models.ForeignKey(
        'bot.AgentInteraction',
        on_delete=models.CASCADE,
        related_name='provider_usage',
        null=True,
        blank=True,
        help_text="Agent interaction this usage is associated with"
    )
    
    # Provider Information
    provider = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Provider name (openai, gemini, together)"
    )
    
    model = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Model name (gpt-4o, gemini-1.5-pro, etc.)"
    )
    
    # Token Usage
    input_tokens = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of input tokens"
    )
    
    output_tokens = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of output tokens"
    )
    
    total_tokens = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Total tokens (input + output)"
    )
    
    # Cost Tracking
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Estimated cost in USD"
    )
    
    # Performance Metrics
    latency_ms = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="API call latency in milliseconds"
    )
    
    # Status
    success = models.BooleanField(
        default=True,
        help_text="Whether the API call succeeded"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if call failed"
    )
    
    finish_reason = models.CharField(
        max_length=50,
        blank=True,
        help_text="Finish reason (stop, length, safety, etc.)"
    )
    
    # Routing Information
    was_failover = models.BooleanField(
        default=False,
        help_text="Whether this was a failover attempt"
    )
    
    routing_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for provider/model selection"
    )
    
    complexity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Complexity score that influenced routing"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific metadata"
    )
    
    objects = ProviderUsageManager()
    
    class Meta:
        db_table = 'bot_provider_usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'provider', 'created_at']),
            models.Index(fields=['tenant', 'model', 'created_at']),
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.provider}/{self.model} - {self.total_tokens} tokens - ${self.estimated_cost}"


class ProviderDailySummaryManager(models.Manager):
    """Manager for provider daily summary queries."""
    
    def for_tenant(self, tenant):
        """Get summaries for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_date_range(self, tenant, start_date, end_date):
        """Get summaries for a date range."""
        return self.filter(
            tenant=tenant,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')


class ProviderDailySummary(BaseModel):
    """
    Daily aggregated summary of provider usage.
    
    Aggregates:
    - Total calls per provider/model
    - Total tokens and costs
    - Average latency
    - Success/failure rates
    
    TENANT SCOPING: All queries MUST filter by tenant.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='provider_daily_summaries',
        db_index=True,
        help_text="Tenant this summary belongs to"
    )
    
    date = models.DateField(
        db_index=True,
        help_text="Date of this summary"
    )
    
    provider = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Provider name"
    )
    
    model = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Model name"
    )
    
    # Call Statistics
    total_calls = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total number of API calls"
    )
    
    successful_calls = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of successful calls"
    )
    
    failed_calls = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of failed calls"
    )
    
    # Token Statistics
    total_input_tokens = models.BigIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total input tokens"
    )
    
    total_output_tokens = models.BigIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total output tokens"
    )
    
    total_tokens = models.BigIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total tokens"
    )
    
    # Cost Statistics
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Total cost in USD"
    )
    
    # Performance Statistics
    avg_latency_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Average latency in milliseconds"
    )
    
    p50_latency_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="50th percentile latency"
    )
    
    p95_latency_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="95th percentile latency"
    )
    
    p99_latency_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="99th percentile latency"
    )
    
    # Routing Statistics
    failover_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of failover attempts"
    )
    
    objects = ProviderDailySummaryManager()
    
    class Meta:
        db_table = 'bot_provider_daily_summary'
        ordering = ['-date', 'provider', 'model']
        unique_together = [['tenant', 'date', 'provider', 'model']]
        indexes = [
            models.Index(fields=['tenant', 'date']),
            models.Index(fields=['tenant', 'provider', 'date']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.date} - {self.provider}/{self.model}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    @property
    def avg_cost_per_call(self) -> Decimal:
        """Calculate average cost per call."""
        if self.total_calls == 0:
            return Decimal('0')
        return self.total_cost / self.total_calls
