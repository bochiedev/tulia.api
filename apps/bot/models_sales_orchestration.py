"""
Sales Orchestration models for the refactored bot system.

These models support the deterministic, sales-oriented bot architecture
that minimizes LLM usage and prevents hallucinations.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from apps.core.models import BaseModel


class IntentClassificationLogManager(models.Manager):
    """Manager for intent classification log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get classification logs for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get classification logs for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def by_method(self, tenant, method):
        """Get logs for a specific classification method within a tenant."""
        return self.filter(tenant=tenant, method=method)
    
    def rule_based(self, tenant):
        """Get rule-based classifications for a tenant."""
        return self.filter(tenant=tenant, method='rule')
    
    def llm_based(self, tenant):
        """Get LLM-based classifications for a tenant."""
        return self.filter(tenant=tenant, method='llm')


class IntentClassificationLog(BaseModel):
    """
    Track intent classification for analytics and debugging.
    
    Records every intent classification attempt, including:
    - Classification method (rule-based, LLM, context)
    - Detected intent and confidence
    - Extracted slots
    - Language detection
    - Processing time
    
    This enables:
    - Analytics on classification method distribution
    - Performance monitoring
    - Cost optimization (rule vs LLM usage)
    - Quality assurance
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='intent_classification_logs',
        db_index=True,
        help_text="Tenant this classification belongs to"
    )
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='intent_classification_logs',
        db_index=True,
        help_text="Conversation this classification belongs to"
    )
    message = models.ForeignKey(
        'messaging.Message',
        on_delete=models.CASCADE,
        related_name='intent_classification_logs',
        null=True,
        blank=True,
        help_text="Message that was classified"
    )
    
    # Classification
    detected_intent = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Detected intent (e.g., BROWSE_PRODUCTS, PLACE_ORDER)"
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score from 0.0 to 1.0"
    )
    method = models.CharField(
        max_length=20,
        choices=[
            ('rule', 'Rule-based'),
            ('llm', 'LLM-based'),
            ('context', 'Context-based'),
        ],
        db_index=True,
        help_text="Classification method used"
    )
    
    # Slots
    extracted_slots = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extracted slots/entities (e.g., {'category': 'shoes', 'budget': 5000})"
    )
    
    # Language
    detected_language = models.JSONField(
        default=list,
        blank=True,
        help_text="Detected languages (e.g., ['en'], ['sw'], ['en', 'sw'])"
    )
    
    # Timing
    classification_time_ms = models.IntegerField(
        help_text="Time taken to classify in milliseconds"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (matched_patterns, llm_model, etc.)"
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
            models.Index(fields=['tenant', 'detected_intent', 'created_at']),
            models.Index(fields=['tenant', 'method', 'created_at']),
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"IntentClassificationLog {self.id} - {self.detected_intent} ({self.method})"
    
    def is_high_confidence(self, threshold=0.65):
        """Check if confidence is above threshold."""
        return self.confidence >= threshold
    
    def is_rule_based(self):
        """Check if classification was rule-based."""
        return self.method == 'rule'
    
    def is_llm_based(self):
        """Check if classification was LLM-based."""
        return self.method == 'llm'
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency with conversation."""
        if self.conversation_id and not self.tenant_id:
            # Auto-populate tenant from conversation
            self.tenant = self.conversation.tenant
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValueError(
                    f"IntentClassificationLog tenant ({self.tenant_id}) must match "
                    f"Conversation tenant ({self.conversation.tenant_id})"
                )
        
        super().save(*args, **kwargs)


class LLMUsageLogManager(models.Manager):
    """Manager for LLM usage log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get usage logs for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get usage logs for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def by_model(self, tenant, model_name):
        """Get logs for a specific model within a tenant."""
        return self.filter(tenant=tenant, model_name=model_name)
    
    def by_task_type(self, tenant, task_type):
        """Get logs for a specific task type within a tenant."""
        return self.filter(tenant=tenant, task_type=task_type)
    
    def monthly_usage(self, tenant, year, month):
        """Get usage for a specific month."""
        return self.filter(
            tenant=tenant,
            created_at__year=year,
            created_at__month=month
        )
    
    def monthly_cost(self, tenant, year, month):
        """Calculate total cost for a specific month."""
        logs = self.monthly_usage(tenant, year, month)
        return logs.aggregate(
            total_cost=models.Sum('estimated_cost_usd')
        )['total_cost'] or Decimal('0.00')


class LLMUsageLog(BaseModel):
    """
    Track LLM usage and costs per tenant.
    
    Records every LLM API call, including:
    - Model used and task type
    - Token usage (input, output, total)
    - Estimated cost
    - Prompt and response previews
    
    This enables:
    - Cost tracking and budgeting
    - Model performance comparison
    - Usage optimization
    - Budget enforcement
    
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
        db_index=True,
        help_text="Conversation this usage belongs to (if applicable)"
    )
    
    # Model
    model_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="LLM model name (e.g., 'gpt-4o-mini', 'qwen-2.5-7b', 'gemini-flash')"
    )
    task_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Task type (e.g., 'intent_classification', 'slot_extraction', 'rag_answer')"
    )
    
    # Usage
    input_tokens = models.IntegerField(
        help_text="Number of input tokens"
    )
    output_tokens = models.IntegerField(
        help_text="Number of output tokens"
    )
    total_tokens = models.IntegerField(
        help_text="Total tokens (input + output)"
    )
    
    # Cost
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Estimated cost in USD"
    )
    
    # Metadata
    prompt_template = models.TextField(
        blank=True,
        help_text="Prompt template used (for debugging)"
    )
    response_preview = models.TextField(
        blank=True,
        help_text="First 500 chars of response (for debugging)"
    )
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
            models.Index(fields=['tenant', 'model_name', 'created_at']),
            models.Index(fields=['tenant', 'task_type', 'created_at']),
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"LLMUsageLog {self.id} - {self.model_name} ({self.task_type})"
    
    def get_cost_per_token(self):
        """Calculate cost per token."""
        if self.total_tokens > 0:
            return float(self.estimated_cost_usd) / self.total_tokens
        return 0.0
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency with conversation."""
        if self.conversation_id and not self.tenant_id:
            # Auto-populate tenant from conversation
            self.tenant = self.conversation.tenant
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValueError(
                    f"LLMUsageLog tenant ({self.tenant_id}) must match "
                    f"Conversation tenant ({self.conversation.tenant_id})"
                )
        
        super().save(*args, **kwargs)


class PaymentRequestManager(models.Manager):
    """Manager for payment request queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get payment requests for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_customer(self, customer):
        """Get payment requests for a specific customer."""
        return self.filter(customer=customer).order_by('-created_at')
    
    def for_order(self, order):
        """Get payment requests for a specific order."""
        return self.filter(order=order).order_by('-created_at')
    
    def for_appointment(self, appointment):
        """Get payment requests for a specific appointment."""
        return self.filter(appointment=appointment).order_by('-created_at')
    
    def by_status(self, tenant, status):
        """Get payment requests by status within a tenant."""
        return self.filter(tenant=tenant, status=status)
    
    def pending(self, tenant):
        """Get pending payment requests for a tenant."""
        return self.filter(tenant=tenant, status='PENDING')
    
    def successful(self, tenant):
        """Get successful payment requests for a tenant."""
        return self.filter(tenant=tenant, status='SUCCESS')
    
    def failed(self, tenant):
        """Get failed payment requests for a tenant."""
        return self.filter(tenant=tenant, status='FAILED')


class PaymentRequest(BaseModel):
    """
    Track payment attempts.
    
    Records every payment initiation and callback, including:
    - Payment method and provider
    - Amount and currency
    - Status tracking
    - Provider responses and callbacks
    
    This enables:
    - Payment flow tracking
    - Success/failure analytics
    - Reconciliation
    - Customer support
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        db_index=True,
        help_text="Tenant this payment belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        db_index=True,
        help_text="Customer making the payment"
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        null=True,
        blank=True,
        db_index=True,
        help_text="Order being paid for (if applicable)"
    )
    appointment = models.ForeignKey(
        'services.Appointment',
        on_delete=models.CASCADE,
        related_name='payment_requests',
        null=True,
        blank=True,
        db_index=True,
        help_text="Appointment being paid for (if applicable)"
    )
    
    # Payment details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Payment amount"
    )
    currency = models.CharField(
        max_length=3,
        default="KES",
        help_text="Currency code (e.g., KES, USD)"
    )
    payment_method = models.CharField(
        max_length=50,
        db_index=True,
        choices=[
            ('mpesa_stk', 'M-Pesa STK Push'),
            ('mpesa_manual', 'M-Pesa Manual'),
            ('paystack', 'Paystack'),
            ('stripe', 'Stripe'),
            ('pesapal', 'Pesapal'),
        ],
        help_text="Payment method used"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        db_index=True,
        choices=[
            ('PENDING', 'Pending'),
            ('SUCCESS', 'Success'),
            ('FAILED', 'Failed'),
            ('CANCELLED', 'Cancelled'),
            ('PENDING_REVIEW', 'Pending Review'),
        ],
        default='PENDING',
        help_text="Payment status"
    )
    
    # Provider details
    provider_reference = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Provider's reference/transaction ID"
    )
    provider_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider's initial response"
    )
    
    # Callback
    callback_received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When callback was received"
    )
    callback_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Callback data from provider"
    )
    
    # Phone number (for M-Pesa)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number used for payment (M-Pesa)"
    )
    
    # Payment link (for card payments)
    payment_link = models.URLField(
        blank=True,
        max_length=500,
        help_text="Payment link sent to customer (card payments)"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata"
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
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['appointment', 'created_at']),
            models.Index(fields=['provider_reference']),
        ]
    
    def __str__(self):
        return f"PaymentRequest {self.id} - {self.payment_method} ({self.status})"
    
    def is_pending(self):
        """Check if payment is pending."""
        return self.status == 'PENDING'
    
    def is_successful(self):
        """Check if payment was successful."""
        return self.status == 'SUCCESS'
    
    def is_failed(self):
        """Check if payment failed."""
        return self.status == 'FAILED'
    
    def mark_success(self, callback_data=None):
        """Mark payment as successful."""
        self.status = 'SUCCESS'
        if callback_data:
            self.callback_data = callback_data
            from django.utils import timezone
            self.callback_received_at = timezone.now()
        self.save(update_fields=['status', 'callback_data', 'callback_received_at'])
    
    def mark_failed(self, callback_data=None):
        """Mark payment as failed."""
        self.status = 'FAILED'
        if callback_data:
            self.callback_data = callback_data
            from django.utils import timezone
            self.callback_received_at = timezone.now()
        self.save(update_fields=['status', 'callback_data', 'callback_received_at'])
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency."""
        if self.customer_id and not self.tenant_id:
            # Auto-populate tenant from customer
            self.tenant = self.customer.tenant
        
        # Validate tenant consistency
        if self.customer_id and self.tenant_id:
            if self.customer.tenant_id != self.tenant_id:
                raise ValueError(
                    f"PaymentRequest tenant ({self.tenant_id}) must match "
                    f"Customer tenant ({self.customer.tenant_id})"
                )
        
        if self.order_id and self.tenant_id:
            if self.order.tenant_id != self.tenant_id:
                raise ValueError(
                    f"PaymentRequest tenant ({self.tenant_id}) must match "
                    f"Order tenant ({self.order.tenant_id})"
                )
        
        if self.appointment_id and self.tenant_id:
            if self.appointment.tenant_id != self.tenant_id:
                raise ValueError(
                    f"PaymentRequest tenant ({self.tenant_id}) must match "
                    f"Appointment tenant ({self.appointment.tenant_id})"
                )
        
        super().save(*args, **kwargs)


__all__ = [
    'IntentClassificationLog',
    'LLMUsageLog',
    'PaymentRequest',
]
