"""
Serializers for analytics API endpoints.

Provides serialization for analytics data including:
- Daily metrics
- Overview aggregations
- Messaging analytics
- Conversion funnel metrics
"""
from rest_framework import serializers
from apps.analytics.models import AnalyticsDaily


class AnalyticsDailySerializer(serializers.ModelSerializer):
    """Serializer for daily analytics records."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    avg_order_value = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    total_messages = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AnalyticsDaily
        fields = [
            'id',
            'tenant_name',
            'date',
            # Messaging
            'msgs_in',
            'msgs_out',
            'total_messages',
            'conversations',
            'avg_first_response_secs',
            'handoffs',
            # Commerce
            'enquiries',
            'orders',
            'revenue',
            'avg_order_value',
            # Services
            'bookings',
            'booking_conversion_rate',
            'no_show_rate',
            # Campaigns
            'campaign_sends',
            'campaign_responses',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class AnalyticsOverviewSerializer(serializers.Serializer):
    """Serializer for overview metrics."""
    
    date_range = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Messaging
    msgs_in = serializers.IntegerField()
    msgs_out = serializers.IntegerField()
    conversations = serializers.IntegerField()
    avg_first_response_secs = serializers.FloatField(allow_null=True)
    handoffs = serializers.IntegerField()
    
    # Commerce
    enquiries = serializers.IntegerField()
    orders = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    avg_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Services
    bookings = serializers.IntegerField()
    booking_conversion_rate = serializers.FloatField(allow_null=True)
    no_show_rate = serializers.FloatField(allow_null=True)
    
    # Campaigns
    campaign_sends = serializers.IntegerField()
    campaign_responses = serializers.IntegerField()


class MessagingAnalyticsSerializer(serializers.Serializer):
    """Serializer for messaging analytics by message type."""
    
    date_range = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    by_message_type = serializers.DictField()


class ConversionFunnelSerializer(serializers.Serializer):
    """Serializer for conversion funnel metrics."""
    
    date_range = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Product funnel
    product_views = serializers.IntegerField()
    add_to_cart = serializers.IntegerField()
    checkout_initiated = serializers.IntegerField()
    orders_completed = serializers.IntegerField()
    product_conversion_rate = serializers.FloatField(allow_null=True)
    
    # Service funnel
    service_views = serializers.IntegerField()
    availability_checks = serializers.IntegerField()
    bookings_completed = serializers.IntegerField()
    service_conversion_rate = serializers.FloatField(allow_null=True)


class RevenueAnalyticsSerializer(serializers.Serializer):
    """Serializer for platform revenue analytics (admin only)."""
    
    date_range = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Payment facilitation
    payment_volume = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fees = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Subscriptions
    subscription_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_subscriptions = serializers.IntegerField()
    
    # By tier
    by_tier = serializers.ListField(child=serializers.DictField())
