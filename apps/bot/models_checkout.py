"""
Checkout flow models for bot conversation flow fixes.

Implements checkout state tracking and response validation
to enable quick sales completion.
"""
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import BaseModel


class CheckoutState(models.TextChoices):
    """Checkout state enum for state machine."""
    BROWSING = 'browsing', 'Browsing'
    PRODUCT_SELECTED = 'product_selected', 'Product Selected'
    QUANTITY_CONFIRMED = 'quantity_confirmed', 'Quantity Confirmed'
    PAYMENT_METHOD_SELECTED = 'payment_method_selected', 'Payment Method Selected'
    PAYMENT_INITIATED = 'payment_initiated', 'Payment Initiated'
    PAYMENT_CONFIRMED = 'payment_confirmed', 'Payment Confirmed'
    ORDER_COMPLETE = 'order_complete', 'Order Complete'


class CheckoutSessionManager(models.Manager):
    """Manager for checkout session queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get checkout sessions for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get checkout sessions for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def active(self, tenant=None):
        """Get active checkout sessions (not completed or abandoned)."""
        qs = self.exclude(state__in=[CheckoutState.ORDER_COMPLETE]).filter(
            abandoned_at__isnull=True
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    def completed(self, tenant=None):
        """Get completed checkout sessions."""
        qs = self.filter(state=CheckoutState.ORDER_COMPLETE, completed_at__isnull=False)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    def abandoned(self, tenant=None):
        """Get abandoned checkout sessions."""
        qs = self.filter(abandoned_at__isnull=False)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs


class CheckoutSession(BaseModel):
    """
    Track checkout progress for sales completion.
    
    Each checkout session:
    - Tracks state machine progress from browsing to payment
    - References selected product, quantity, order, and payment
    - Counts messages to enforce quick checkout (≤3 messages)
    - Records completion or abandonment timestamps
    
    Requirements: 10.1
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='checkout_sessions',
        db_index=True,
        help_text="Conversation this checkout session belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='checkout_sessions',
        db_index=True,
        help_text="Customer in this checkout session"
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='checkout_sessions',
        db_index=True,
        help_text="Tenant this checkout session belongs to"
    )
    
    # State
    state = models.CharField(
        max_length=50,
        choices=CheckoutState.choices,
        default=CheckoutState.BROWSING,
        db_index=True,
        help_text="Current checkout state"
    )
    
    # Data
    selected_product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_sessions',
        help_text="Selected product for purchase"
    )
    quantity = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Selected quantity"
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_sessions',
        help_text="Created order"
    )
    payment_request = models.ForeignKey(
        'bot.PaymentRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_sessions',
        help_text="Payment request for this checkout"
    )
    
    # Metadata
    started_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When checkout session started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When checkout was completed"
    )
    abandoned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When checkout was abandoned"
    )
    message_count = models.IntegerField(
        default=0,
        help_text="Number of messages in this checkout session"
    )
    
    # Custom manager
    objects = CheckoutSessionManager()
    
    class Meta:
        db_table = 'bot_checkout_sessions'
        verbose_name = 'Checkout Session'
        verbose_name_plural = 'Checkout Sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['tenant', 'state', 'started_at']),
            models.Index(fields=['conversation', 'state']),
            models.Index(fields=['conversation', 'started_at']),
            models.Index(fields=['state', 'started_at']),
        ]
    
    def __str__(self):
        return f"CheckoutSession {self.id} - {self.state} ({self.message_count} messages)"
    
    def increment_message_count(self):
        """Increment message counter atomically."""
        from django.db.models import F
        CheckoutSession.objects.filter(id=self.id).update(
            message_count=F('message_count') + 1
        )
        self.refresh_from_db(fields=['message_count'])
    
    def mark_completed(self):
        """Mark checkout session as completed."""
        from django.utils import timezone
        self.state = CheckoutState.ORDER_COMPLETE
        self.completed_at = timezone.now()
        self.save(update_fields=['state', 'completed_at'])
    
    def mark_abandoned(self):
        """Mark checkout session as abandoned."""
        from django.utils import timezone
        self.abandoned_at = timezone.now()
        self.save(update_fields=['abandoned_at'])
    
    def is_active(self):
        """Check if checkout session is still active."""
        return (
            self.state != CheckoutState.ORDER_COMPLETE and
            self.abandoned_at is None
        )
    
    def is_completed(self):
        """Check if checkout session is completed."""
        return self.state == CheckoutState.ORDER_COMPLETE and self.completed_at is not None
    
    def is_abandoned(self):
        """Check if checkout session is abandoned."""
        return self.abandoned_at is not None
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency with conversation."""
        if self.conversation_id and not self.tenant_id:
            # Auto-populate tenant from conversation
            self.tenant = self.conversation.tenant
        
        if self.conversation_id and not self.customer_id:
            # Auto-populate customer from conversation
            self.customer = self.conversation.customer
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValueError(
                    f"CheckoutSession tenant ({self.tenant_id}) must match "
                    f"Conversation tenant ({self.conversation.tenant_id})"
                )
        
        super().save(*args, **kwargs)


class ResponseValidationLogManager(models.Manager):
    """Manager for response validation log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get validation logs for a specific tenant."""
        return self.filter(conversation__tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get validation logs for a specific conversation."""
        return self.filter(conversation=conversation).order_by('-created_at')
    
    def with_issues(self, tenant=None):
        """Get validation logs that had issues."""
        qs = self.filter(
            models.Q(had_echo=True) |
            models.Q(had_disclaimer=True) |
            models.Q(exceeded_length=True) |
            models.Q(missing_cta=True)
        )
        if tenant:
            qs = qs.filter(conversation__tenant=tenant)
        return qs
    
    def clean_responses(self, tenant=None):
        """Get validation logs with no issues."""
        qs = self.filter(
            had_echo=False,
            had_disclaimer=False,
            exceeded_length=False,
            missing_cta=False
        )
        if tenant:
            qs = qs.filter(conversation__tenant=tenant)
        return qs


class ResponseValidationLog(BaseModel):
    """
    Track response validation for monitoring and debugging.
    
    Records validation results for each bot response to enable:
    - Monitoring of echo detection rate
    - Tracking of disclaimer removal rate
    - Analysis of response length compliance
    - Debugging of validation issues
    
    Requirements: 1.1, 5.5
    
    TENANT SCOPING: Inherits tenant from conversation relationship.
    All queries MUST filter by conversation__tenant to prevent cross-tenant data leakage.
    """
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='validation_logs',
        db_index=True,
        help_text="Conversation this validation belongs to"
    )
    message = models.ForeignKey(
        'messaging.Message',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validation_logs',
        help_text="Message that was validated"
    )
    
    # Validation results
    had_echo = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether response contained customer message echo"
    )
    had_disclaimer = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether response contained disclaimer phrases"
    )
    exceeded_length = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether response exceeded maximum length"
    )
    missing_cta = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether response was missing call-to-action"
    )
    
    # Original vs cleaned
    original_response = models.TextField(
        help_text="Original response before validation/cleaning"
    )
    cleaned_response = models.TextField(
        help_text="Cleaned response after validation/cleaning"
    )
    
    # Metadata
    validation_time_ms = models.IntegerField(
        default=0,
        help_text="Time taken to validate in milliseconds"
    )
    issues_found = models.JSONField(
        default=list,
        blank=True,
        help_text="List of specific issues found during validation"
    )
    
    # Custom manager
    objects = ResponseValidationLogManager()
    
    class Meta:
        db_table = 'bot_response_validation_logs'
        verbose_name = 'Response Validation Log'
        verbose_name_plural = 'Response Validation Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'had_echo']),
            models.Index(fields=['conversation', 'had_disclaimer']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        issues = []
        if self.had_echo:
            issues.append('echo')
        if self.had_disclaimer:
            issues.append('disclaimer')
        if self.exceeded_length:
            issues.append('length')
        if self.missing_cta:
            issues.append('cta')
        
        issues_str = ', '.join(issues) if issues else 'clean'
        return f"ResponseValidationLog {self.id} - {issues_str}"
    
    def has_any_issues(self):
        """Check if validation found any issues."""
        return (
            self.had_echo or
            self.had_disclaimer or
            self.exceeded_length or
            self.missing_cta
        )
    
    def get_issue_count(self):
        """Get count of issues found."""
        count = 0
        if self.had_echo:
            count += 1
        if self.had_disclaimer:
            count += 1
        if self.exceeded_length:
            count += 1
        if self.missing_cta:
            count += 1
        return count


__all__ = [
    'CheckoutState',
    'CheckoutSession',
    'ResponseValidationLog',
]
