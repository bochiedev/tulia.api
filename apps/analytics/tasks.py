"""
Celery tasks for analytics aggregation.

Implements nightly rollup of metrics for each tenant,
aggregating messages, conversations, orders, bookings,
and calculating conversion rates.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from celery import shared_task
from apps.tenants.models import Tenant
from apps.analytics.models import AnalyticsDaily
from apps.messaging.models import Message, Conversation
from apps.orders.models import Order
from apps.services.models import Appointment
from apps.bot.models import IntentEvent

logger = logging.getLogger(__name__)


@shared_task(name='analytics.rollup_daily_metrics')
def rollup_daily_metrics(date_str=None):
    """
    Nightly analytics rollup task to aggregate metrics for each tenant.
    
    Aggregates:
    - Message counts (in/out)
    - Conversation counts
    - Order counts and revenue
    - Booking counts
    - Conversion rates and no-show rates
    
    Args:
        date_str: Optional date string (YYYY-MM-DD). Defaults to yesterday.
    
    Returns:
        dict: Summary of processed tenants and any errors
    """
    # Determine target date (default to yesterday)
    if date_str:
        target_date = datetime.fromisoformat(date_str).date()
    else:
        target_date = (timezone.now() - timedelta(days=1)).date()
    
    logger.info(f"Starting analytics rollup for date: {target_date}")
    
    # Get all active tenants
    tenants = Tenant.objects.filter(status__in=['active', 'trial'])
    
    results = {
        'date': target_date.isoformat(),
        'tenants_processed': 0,
        'tenants_failed': 0,
        'errors': []
    }
    
    for tenant in tenants:
        try:
            logger.info(f"Processing analytics for tenant: {tenant.name} ({tenant.id})")
            
            # Aggregate metrics for this tenant and date
            metrics = _aggregate_tenant_metrics(tenant, target_date)
            
            # Create or update AnalyticsDaily record
            analytics, created = AnalyticsDaily.objects.update_or_create(
                tenant=tenant,
                date=target_date,
                defaults=metrics
            )
            
            action = "Created" if created else "Updated"
            logger.info(
                f"{action} analytics for {tenant.name}: "
                f"{metrics['msgs_in']} msgs_in, {metrics['orders']} orders, "
                f"{metrics['bookings']} bookings"
            )
            
            results['tenants_processed'] += 1
            
        except Exception as e:
            logger.error(
                f"Failed to process analytics for tenant {tenant.name}: {str(e)}",
                exc_info=True
            )
            results['tenants_failed'] += 1
            results['errors'].append({
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'error': str(e)
            })
    
    logger.info(
        f"Analytics rollup completed: {results['tenants_processed']} processed, "
        f"{results['tenants_failed']} failed"
    )
    
    return results


def _aggregate_tenant_metrics(tenant, date):
    """
    Aggregate all metrics for a tenant on a specific date.
    
    Args:
        tenant: Tenant instance
        date: Date object
    
    Returns:
        dict: Metrics dictionary for AnalyticsDaily
    """
    # Define date range for the target date
    start_dt = timezone.make_aware(datetime.combine(date, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(date, datetime.max.time()))
    
    # Messaging Metrics
    msgs_in = Message.objects.filter(
        conversation__tenant=tenant,
        direction='in',
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    msgs_out = Message.objects.filter(
        conversation__tenant=tenant,
        direction='out',
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # New conversations started on this date
    conversations = Conversation.objects.filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # Calculate average first response time
    # (time between first customer message and first bot response)
    avg_first_response = _calculate_avg_first_response(tenant, start_dt, end_dt)
    
    # Handoffs to human agents
    handoffs = Conversation.objects.filter(
        tenant=tenant,
        status='handoff',
        updated_at__gte=start_dt,
        updated_at__lte=end_dt
    ).count()
    
    # Enquiries (product/service intent events)
    enquiry_intents = [
        'BROWSE_PRODUCTS', 'PRODUCT_DETAILS', 'PRICE_CHECK',
        'BROWSE_SERVICES', 'SERVICE_DETAILS', 'CHECK_AVAILABILITY'
    ]
    enquiries = IntentEvent.objects.filter(
        conversation__tenant=tenant,
        intent_name__in=enquiry_intents,
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # Commerce Metrics
    orders = Order.objects.filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # Revenue from paid/fulfilled orders
    revenue_data = Order.objects.filter(
        tenant=tenant,
        status__in=['paid', 'fulfilled'],
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).aggregate(total=Sum('total'))
    
    revenue = revenue_data['total'] or Decimal('0')
    
    # Services Metrics
    bookings = Appointment.objects.filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # Booking conversion rate
    booking_conversion_rate = _calculate_booking_conversion_rate(
        tenant, start_dt, end_dt
    )
    
    # No-show rate
    no_show_rate = _calculate_no_show_rate(tenant, start_dt, end_dt)
    
    # Campaign Metrics
    campaign_sends = Message.objects.filter(
        conversation__tenant=tenant,
        direction='out',
        message_type='scheduled_promotional',
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # Campaign responses (inbound messages after campaign sends)
    campaign_responses = 0  # Simplified for now
    
    return {
        'msgs_in': msgs_in,
        'msgs_out': msgs_out,
        'conversations': conversations,
        'avg_first_response_secs': avg_first_response,
        'handoffs': handoffs,
        'enquiries': enquiries,
        'orders': orders,
        'revenue': revenue,
        'bookings': bookings,
        'booking_conversion_rate': booking_conversion_rate,
        'no_show_rate': no_show_rate,
        'campaign_sends': campaign_sends,
        'campaign_responses': campaign_responses,
    }


def _calculate_avg_first_response(tenant, start_dt, end_dt):
    """
    Calculate average first response time for conversations.
    
    Args:
        tenant: Tenant instance
        start_dt: Start datetime
        end_dt: End datetime
    
    Returns:
        float: Average response time in seconds or None
    """
    # Get conversations started in this period
    conversations = Conversation.objects.filter(
        tenant=tenant,
        created_at__gte=start_dt,
        created_at__lte=end_dt
    )
    
    response_times = []
    
    for conv in conversations:
        # Get first customer message
        first_customer_msg = Message.objects.filter(
            conversation=conv,
            direction='in'
        ).order_by('created_at').first()
        
        if not first_customer_msg:
            continue
        
        # Get first bot response after customer message
        first_bot_msg = Message.objects.filter(
            conversation=conv,
            direction='out',
            created_at__gt=first_customer_msg.created_at
        ).order_by('created_at').first()
        
        if first_bot_msg:
            delta = first_bot_msg.created_at - first_customer_msg.created_at
            response_times.append(delta.total_seconds())
    
    if response_times:
        return sum(response_times) / len(response_times)
    return None


def _calculate_booking_conversion_rate(tenant, start_dt, end_dt):
    """
    Calculate booking conversion rate: bookings / availability checks.
    
    Args:
        tenant: Tenant instance
        start_dt: Start datetime
        end_dt: End datetime
    
    Returns:
        float: Conversion rate as percentage or None
    """
    # Count CHECK_AVAILABILITY intents
    availability_checks = IntentEvent.objects.filter(
        conversation__tenant=tenant,
        intent_name='CHECK_AVAILABILITY',
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    # Count confirmed bookings
    bookings = Appointment.objects.filter(
        tenant=tenant,
        status__in=['confirmed', 'done'],
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).count()
    
    if availability_checks > 0:
        return (bookings / availability_checks) * 100
    return None


def _calculate_no_show_rate(tenant, start_dt, end_dt):
    """
    Calculate no-show rate: no-shows / confirmed appointments.
    
    Args:
        tenant: Tenant instance
        start_dt: Start datetime
        end_dt: End datetime
    
    Returns:
        float: No-show rate as percentage or None
    """
    # Count confirmed appointments (that could have been no-shows)
    confirmed = Appointment.objects.filter(
        tenant=tenant,
        status__in=['confirmed', 'done', 'no_show'],
        start_dt__gte=start_dt,
        start_dt__lte=end_dt
    ).count()
    
    # Count no-shows
    no_shows = Appointment.objects.filter(
        tenant=tenant,
        status='no_show',
        start_dt__gte=start_dt,
        start_dt__lte=end_dt
    ).count()
    
    if confirmed > 0:
        return (no_shows / confirmed) * 100
    return None
