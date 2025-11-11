"""
Analytics service for metric calculation and reporting.

Provides methods for:
- Overview metrics with date range aggregation
- Daily metrics retrieval
- Booking conversion rate calculation
- No-show rate calculation
- Messaging analytics grouped by message type
"""
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from apps.analytics.models import AnalyticsDaily
from apps.messaging.models import Message, Conversation
from apps.orders.models import Order
from apps.services.models import Appointment
from apps.bot.models import IntentEvent


class AnalyticsService:
    """
    Service for calculating and retrieving analytics metrics.
    
    Provides aggregated metrics for dashboards and reports,
    with tenant scoping and date range filtering.
    """
    
    def __init__(self, tenant):
        """
        Initialize analytics service for a tenant.
        
        Args:
            tenant: Tenant instance to scope analytics to
        """
        self.tenant = tenant
    
    def get_overview(self, date_range='7d'):
        """
        Get overview metrics for dashboard with date range aggregation.
        
        Args:
            date_range: String like '7d', '30d', '90d' for days back
        
        Returns:
            dict: Aggregated metrics including:
                - msgs_in, msgs_out, conversations
                - orders, revenue, avg_order_value
                - bookings, booking_conversion_rate, no_show_rate
                - avg_first_response_secs, handoffs
        """
        # Parse date range
        days = int(date_range.rstrip('d'))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Aggregate from AnalyticsDaily
        daily_records = AnalyticsDaily.objects.for_date_range(
            self.tenant, start_date, end_date
        )
        
        aggregates = daily_records.aggregate(
            msgs_in=Sum('msgs_in'),
            msgs_out=Sum('msgs_out'),
            conversations=Sum('conversations'),
            handoffs=Sum('handoffs'),
            enquiries=Sum('enquiries'),
            orders=Sum('orders'),
            revenue=Sum('revenue'),
            bookings=Sum('bookings'),
            campaign_sends=Sum('campaign_sends'),
            campaign_responses=Sum('campaign_responses'),
            avg_first_response_secs=Avg('avg_first_response_secs'),
        )
        
        # Calculate derived metrics
        avg_order_value = Decimal('0')
        if aggregates['orders'] and aggregates['orders'] > 0:
            avg_order_value = aggregates['revenue'] / aggregates['orders']
        
        # Calculate booking conversion rate (average across days)
        booking_conversion_rates = [
            r.booking_conversion_rate for r in daily_records 
            if r.booking_conversion_rate is not None
        ]
        avg_booking_conversion = (
            sum(booking_conversion_rates) / len(booking_conversion_rates)
            if booking_conversion_rates else None
        )
        
        # Calculate no-show rate (average across days)
        no_show_rates = [
            r.no_show_rate for r in daily_records 
            if r.no_show_rate is not None
        ]
        avg_no_show_rate = (
            sum(no_show_rates) / len(no_show_rates)
            if no_show_rates else None
        )
        
        return {
            'date_range': date_range,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'msgs_in': aggregates['msgs_in'] or 0,
            'msgs_out': aggregates['msgs_out'] or 0,
            'conversations': aggregates['conversations'] or 0,
            'avg_first_response_secs': aggregates['avg_first_response_secs'],
            'handoffs': aggregates['handoffs'] or 0,
            'enquiries': aggregates['enquiries'] or 0,
            'orders': aggregates['orders'] or 0,
            'revenue': float(aggregates['revenue'] or 0),
            'avg_order_value': float(avg_order_value),
            'bookings': aggregates['bookings'] or 0,
            'booking_conversion_rate': avg_booking_conversion,
            'no_show_rate': avg_no_show_rate,
            'campaign_sends': aggregates['campaign_sends'] or 0,
            'campaign_responses': aggregates['campaign_responses'] or 0,
        }
    
    def get_daily_metrics(self, date):
        """
        Retrieve AnalyticsDaily record for a specific date.
        
        Args:
            date: Date object or ISO string (YYYY-MM-DD)
        
        Returns:
            AnalyticsDaily instance or None if not found
        """
        if isinstance(date, str):
            date = datetime.fromisoformat(date).date()
        
        try:
            return AnalyticsDaily.objects.get(tenant=self.tenant, date=date)
        except AnalyticsDaily.DoesNotExist:
            return None
    
    def calculate_booking_conversion_rate(self, date_range='7d'):
        """
        Calculate booking conversion rate: bookings / availability checks.
        
        Args:
            date_range: String like '7d', '30d' for days back
        
        Returns:
            float: Conversion rate as percentage (0-100) or None
        """
        days = int(date_range.rstrip('d'))
        start_date = timezone.now() - timedelta(days=days)
        
        # Count CHECK_AVAILABILITY intents
        availability_checks = IntentEvent.objects.filter(
            conversation__tenant=self.tenant,
            intent_name='CHECK_AVAILABILITY',
            created_at__gte=start_date
        ).count()
        
        # Count confirmed bookings
        bookings = Appointment.objects.filter(
            tenant=self.tenant,
            status__in=['confirmed', 'done'],
            created_at__gte=start_date
        ).count()
        
        if availability_checks > 0:
            return (bookings / availability_checks) * 100
        return None
    
    def calculate_no_show_rate(self, date_range='7d'):
        """
        Calculate no-show rate: no-shows / confirmed appointments.
        
        Args:
            date_range: String like '7d', '30d' for days back
        
        Returns:
            float: No-show rate as percentage (0-100) or None
        """
        days = int(date_range.rstrip('d'))
        start_date = timezone.now() - timedelta(days=days)
        
        # Count confirmed appointments
        confirmed = Appointment.objects.filter(
            tenant=self.tenant,
            status__in=['confirmed', 'done', 'no_show'],
            created_at__gte=start_date
        ).count()
        
        # Count no-shows
        no_shows = Appointment.objects.filter(
            tenant=self.tenant,
            status='no_show',
            created_at__gte=start_date
        ).count()
        
        if confirmed > 0:
            return (no_shows / confirmed) * 100
        return None
    
    def get_messaging_analytics(self, date_range='7d'):
        """
        Get messaging analytics grouped by message_type.
        
        Args:
            date_range: String like '7d', '30d' for days back
        
        Returns:
            dict: Metrics by message type including:
                - sent_count, delivered_count, failed_count, read_count
                - delivery_rate, engagement_rate
        """
        days = int(date_range.rstrip('d'))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get outbound messages grouped by type
        message_stats = Message.objects.filter(
            conversation__tenant=self.tenant,
            direction='out',
            created_at__gte=start_date
        ).values('message_type').annotate(
            sent_count=Count('id'),
            # Note: delivered_count, failed_count, read_count would come from
            # webhook status callbacks stored in message metadata
        )
        
        # Calculate metrics per message type
        results = {}
        for stat in message_stats:
            msg_type = stat['message_type']
            sent = stat['sent_count']
            
            # For now, we'll use simplified metrics
            # In production, these would come from Twilio status callbacks
            results[msg_type] = {
                'sent_count': sent,
                'delivered_count': sent,  # Placeholder
                'failed_count': 0,  # Placeholder
                'read_count': 0,  # Placeholder
                'delivery_rate': 100.0,  # Placeholder
                'engagement_rate': 0.0,  # Placeholder
            }
        
        # Count responses to outbound messages
        for msg_type in results:
            # Get conversations with this message type
            convs_with_type = Message.objects.filter(
                conversation__tenant=self.tenant,
                direction='out',
                message_type=msg_type,
                created_at__gte=start_date
            ).values_list('conversation_id', flat=True).distinct()
            
            # Count inbound messages in those conversations after outbound
            responses = Message.objects.filter(
                conversation__tenant=self.tenant,
                conversation_id__in=convs_with_type,
                direction='in',
                created_at__gte=start_date
            ).count()
            
            if results[msg_type]['delivered_count'] > 0:
                results[msg_type]['engagement_rate'] = (
                    responses / results[msg_type]['delivered_count']
                ) * 100
        
        return {
            'date_range': date_range,
            'start_date': start_date.date().isoformat(),
            'end_date': timezone.now().date().isoformat(),
            'by_message_type': results
        }
