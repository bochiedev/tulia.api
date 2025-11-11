"""
Analytics models for aggregated metrics and reporting.

Implements daily rollup of metrics for messages, orders, bookings,
and revenue with tenant isolation.
"""
from django.db import models
from apps.core.models import BaseModel


class AnalyticsDailyManager(models.Manager):
    """Manager for analytics queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get analytics for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_date_range(self, tenant, start_date, end_date):
        """Get analytics for a date range."""
        return self.filter(
            tenant=tenant,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
    
    def get_or_create_for_date(self, tenant, date):
        """Get or create analytics record for a specific date."""
        return self.get_or_create(tenant=tenant, date=date)


class AnalyticsDaily(BaseModel):
    """
    Daily aggregated analytics metrics per tenant.
    
    This model stores pre-calculated metrics for each tenant per day,
    enabling fast dashboard queries without real-time aggregation.
    
    Metrics include:
    - Messaging: inbound/outbound messages, conversations, response times
    - Commerce: orders, revenue, average order value
    - Services: bookings, conversion rates, no-show rates
    - Campaigns: sends, responses, conversions
    
    Updated by nightly Celery task that aggregates previous day's data.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='analytics_daily',
        db_index=True,
        help_text="Tenant these metrics belong to"
    )
    date = models.DateField(
        db_index=True,
        help_text="Date for these metrics"
    )
    
    # Messaging Metrics
    msgs_in = models.IntegerField(
        default=0,
        help_text="Number of inbound messages"
    )
    msgs_out = models.IntegerField(
        default=0,
        help_text="Number of outbound messages"
    )
    conversations = models.IntegerField(
        default=0,
        help_text="Number of new conversations started"
    )
    avg_first_response_secs = models.FloatField(
        null=True,
        blank=True,
        help_text="Average first response time in seconds"
    )
    handoffs = models.IntegerField(
        default=0,
        help_text="Number of conversations handed off to humans"
    )
    
    # Commerce Metrics
    enquiries = models.IntegerField(
        default=0,
        help_text="Number of product/service enquiries"
    )
    orders = models.IntegerField(
        default=0,
        help_text="Number of orders created"
    )
    revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total revenue from paid/fulfilled orders"
    )
    
    # Services Metrics
    bookings = models.IntegerField(
        default=0,
        help_text="Number of appointments booked"
    )
    booking_conversion_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Bookings divided by availability checks"
    )
    no_show_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="No-shows divided by confirmed appointments"
    )
    
    # Campaign Metrics
    campaign_sends = models.IntegerField(
        default=0,
        help_text="Number of campaign messages sent"
    )
    campaign_responses = models.IntegerField(
        default=0,
        help_text="Number of responses to campaign messages"
    )
    
    # Custom manager
    objects = AnalyticsDailyManager()
    
    class Meta:
        db_table = 'analytics_daily'
        ordering = ['-date']
        unique_together = [('tenant', 'date')]
        indexes = [
            models.Index(fields=['tenant', 'date']),
            models.Index(fields=['tenant', '-date']),
            models.Index(fields=['date']),
        ]
        verbose_name = 'Daily Analytics'
        verbose_name_plural = 'Daily Analytics'
    
    def __str__(self):
        return f"Analytics for {self.tenant.name} on {self.date}"
    
    @property
    def avg_order_value(self):
        """Calculate average order value."""
        if self.orders > 0:
            return self.revenue / self.orders
        return 0
    
    @property
    def total_messages(self):
        """Get total message count (in + out)."""
        return self.msgs_in + self.msgs_out
