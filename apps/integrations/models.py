"""
Integration models for external service webhooks and logs.

Implements webhook logging for audit trail and troubleshooting.
"""
from django.db import models
from apps.core.models import BaseModel


class WebhookLogManager(models.Manager):
    """Manager for webhook log queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get webhook logs for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def by_provider(self, provider):
        """Get webhook logs for a specific provider."""
        return self.filter(provider=provider)
    
    def by_status(self, status):
        """Get webhook logs with a specific status."""
        return self.filter(status=status)
    
    def failed(self):
        """Get all failed webhook logs."""
        return self.filter(status__in=['error', 'unauthorized'])
    
    def successful(self):
        """Get all successful webhook logs."""
        return self.filter(status='success')
    
    def recent(self, hours=24):
        """Get webhook logs from the last N hours."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(received_at__gte=cutoff)


class WebhookLog(BaseModel):
    """
    Webhook log model for tracking all incoming webhook requests.
    
    Provides complete audit trail of webhook processing including:
    - Provider identification (Twilio, WooCommerce, Shopify, etc.)
    - Full request payload
    - Processing status and errors
    - Tenant association for multi-tenant tracking
    
    Used for debugging, compliance, and monitoring webhook reliability.
    """
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('unauthorized', 'Unauthorized'),
        ('subscription_inactive', 'Subscription Inactive'),
    ]
    
    PROVIDER_CHOICES = [
        ('twilio', 'Twilio'),
        ('woocommerce', 'WooCommerce'),
        ('shopify', 'Shopify'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='webhook_logs',
        db_index=True,
        help_text="Tenant this webhook is associated with (null if resolution failed)"
    )
    
    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        db_index=True,
        help_text="Webhook provider/source"
    )
    event = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Event type or webhook action"
    )
    
    # Request Data
    payload = models.JSONField(
        help_text="Full webhook request payload"
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Request headers (excluding sensitive data)"
    )
    
    # Processing Status
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        db_index=True,
        help_text="Processing status"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if processing failed"
    )
    error_traceback = models.TextField(
        null=True,
        blank=True,
        help_text="Full error traceback for debugging"
    )
    
    # Timing
    received_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when webhook was received"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when processing completed"
    )
    processing_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Processing time in milliseconds"
    )
    
    # Additional Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Source IP address of webhook request"
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User agent from webhook request"
    )
    request_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Request ID for tracing"
    )
    
    # Custom manager
    objects = WebhookLogManager()
    
    class Meta:
        db_table = 'webhook_logs'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['tenant', 'received_at']),
            models.Index(fields=['provider', 'status', 'received_at']),
            models.Index(fields=['status', 'received_at']),
            models.Index(fields=['event', 'received_at']),
        ]
    
    def __str__(self):
        tenant_name = self.tenant.name if self.tenant else 'Unknown'
        return f"{self.provider} - {self.event} ({tenant_name}) - {self.status}"
    
    def mark_success(self, processing_time_ms: int = None):
        """Mark webhook processing as successful."""
        from django.utils import timezone
        self.status = 'success'
        self.processed_at = timezone.now()
        if processing_time_ms is not None:
            self.processing_time_ms = processing_time_ms
        self.save(update_fields=['status', 'processed_at', 'processing_time_ms'])
    
    def mark_error(self, error_message: str, error_traceback: str = None, processing_time_ms: int = None):
        """Mark webhook processing as failed with error details."""
        from django.utils import timezone
        self.status = 'error'
        self.error_message = error_message
        self.error_traceback = error_traceback
        self.processed_at = timezone.now()
        if processing_time_ms is not None:
            self.processing_time_ms = processing_time_ms
        self.save(update_fields=[
            'status', 'error_message', 'error_traceback', 
            'processed_at', 'processing_time_ms'
        ])
    
    def mark_unauthorized(self, error_message: str = None):
        """Mark webhook as unauthorized (signature verification failed)."""
        from django.utils import timezone
        self.status = 'unauthorized'
        self.error_message = error_message or 'Signature verification failed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'processed_at'])
    
    def mark_subscription_inactive(self):
        """Mark webhook as blocked due to inactive subscription."""
        from django.utils import timezone
        self.status = 'subscription_inactive'
        self.error_message = 'Tenant subscription is inactive'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'processed_at'])
    
    def calculate_processing_time(self):
        """Calculate processing time in milliseconds."""
        if self.processed_at and self.received_at:
            delta = self.processed_at - self.received_at
            return int(delta.total_seconds() * 1000)
        return None
