"""
Analytics API views.

Provides REST endpoints for:
- Overview metrics with date range filtering
- Daily metrics retrieval
- Messaging analytics by message type
- Conversion funnel tracking
- Platform revenue analytics (admin only)
"""
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.core.permissions import HasTenantScopes, requires_scopes
from apps.analytics.models import AnalyticsDaily
from apps.analytics.services import AnalyticsService
from apps.analytics.serializers import (
    AnalyticsDailySerializer,
    AnalyticsOverviewSerializer,
    MessagingAnalyticsSerializer,
    ConversionFunnelSerializer,
    RevenueAnalyticsSerializer,
)
from apps.bot.models import IntentEvent
from apps.orders.models import Order
from apps.services.models import Appointment
from apps.tenants.models import Subscription, Transaction


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
def analytics_overview(request):
    """
    Get overview metrics for dashboard with date range aggregation.
    
    Query Parameters:
        range: Date range like '7d', '30d', '90d' (default: '7d')
    
    Returns:
        200: Aggregated metrics
        400: Invalid date range
        403: Missing analytics:view permission
    
    Example:
        GET /v1/analytics/overview?range=30d
    
    Required scope: analytics:view
    """
    # Check scope manually for function-based view
    if 'analytics:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: analytics:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    date_range = request.query_params.get('range', '7d')
    
    # Validate date range format
    if not date_range.endswith('d') or not date_range[:-1].isdigit():
        return Response(
            {'error': 'Invalid date range format. Use format like "7d", "30d"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get analytics service for tenant
    analytics_service = AnalyticsService(request.tenant)
    
    # Get overview metrics
    overview = analytics_service.get_overview(date_range)
    
    # Serialize and return
    serializer = AnalyticsOverviewSerializer(overview)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
def analytics_daily(request):
    """
    Get daily analytics metrics with optional date filtering.
    
    Query Parameters:
        date: Specific date (YYYY-MM-DD)
        start_date: Start of date range (YYYY-MM-DD)
        end_date: End of date range (YYYY-MM-DD)
    
    Returns:
        200: List of daily analytics records
        400: Invalid date format
        403: Missing analytics:view permission
    
    Example:
        GET /v1/analytics/daily?start_date=2025-11-01&end_date=2025-11-10
    
    Required scope: analytics:view
    """
    # Check scope manually for function-based view
    if 'analytics:view' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: analytics:view'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get query parameters
    date_str = request.query_params.get('date')
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    
    try:
        if date_str:
            # Single date query
            date = datetime.fromisoformat(date_str).date()
            analytics_service = AnalyticsService(request.tenant)
            daily = analytics_service.get_daily_metrics(date)
            
            if daily:
                serializer = AnalyticsDailySerializer(daily)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'No analytics data for this date'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif start_date_str and end_date_str:
            # Date range query
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
            
            daily_records = AnalyticsDaily.objects.for_date_range(
                request.tenant, start_date, end_date
            )
            
            serializer = AnalyticsDailySerializer(daily_records, many=True)
            return Response(serializer.data)
        
        else:
            # Default: last 7 days
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=7)
            
            daily_records = AnalyticsDaily.objects.for_date_range(
                request.tenant, start_date, end_date
            )
            
            serializer = AnalyticsDailySerializer(daily_records, many=True)
            return Response(serializer.data)
    
    except ValueError as e:
        return Response(
            {'error': f'Invalid date format: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
@requires_scopes('analytics:view')
def analytics_messaging(request):
    """
    Get messaging analytics grouped by message_type.
    
    Query Parameters:
        range: Date range like '7d', '30d' (default: '7d')
    
    Returns:
        200: Messaging metrics by type
        400: Invalid date range
        403: Missing analytics:view permission
    
    Example:
        GET /v1/analytics/messaging?range=30d
    """
    date_range = request.query_params.get('range', '7d')
    
    # Validate date range format
    if not date_range.endswith('d') or not date_range[:-1].isdigit():
        return Response(
            {'error': 'Invalid date range format. Use format like "7d", "30d"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get analytics service for tenant
    analytics_service = AnalyticsService(request.tenant)
    
    # Get messaging analytics
    messaging_data = analytics_service.get_messaging_analytics(date_range)
    
    # Serialize and return
    serializer = MessagingAnalyticsSerializer(messaging_data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
@requires_scopes('analytics:view')
def analytics_funnel(request):
    """
    Get conversion funnel metrics for products and services.
    
    Query Parameters:
        range: Date range like '7d', '30d' (default: '7d')
    
    Returns:
        200: Funnel metrics
        400: Invalid date range
        403: Missing analytics:view permission
    
    Example:
        GET /v1/analytics/funnel?range=30d
    """
    date_range = request.query_params.get('range', '7d')
    
    # Validate date range format
    if not date_range.endswith('d') or not date_range[:-1].isdigit():
        return Response(
            {'error': 'Invalid date range format. Use format like "7d", "30d"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Calculate date range
    days = int(date_range.rstrip('d'))
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Product funnel
    product_views = IntentEvent.objects.filter(
        conversation__tenant=request.tenant,
        intent_name__in=['BROWSE_PRODUCTS', 'PRODUCT_DETAILS'],
        created_at__gte=start_date
    ).count()
    
    add_to_cart = IntentEvent.objects.filter(
        conversation__tenant=request.tenant,
        intent_name='ADD_TO_CART',
        created_at__gte=start_date
    ).count()
    
    checkout_initiated = IntentEvent.objects.filter(
        conversation__tenant=request.tenant,
        intent_name='CHECKOUT_LINK',
        created_at__gte=start_date
    ).count()
    
    orders_completed = Order.objects.filter(
        tenant=request.tenant,
        status__in=['paid', 'fulfilled'],
        created_at__gte=start_date
    ).count()
    
    product_conversion_rate = None
    if product_views > 0:
        product_conversion_rate = (orders_completed / product_views) * 100
    
    # Service funnel
    service_views = IntentEvent.objects.filter(
        conversation__tenant=request.tenant,
        intent_name__in=['BROWSE_SERVICES', 'SERVICE_DETAILS'],
        created_at__gte=start_date
    ).count()
    
    availability_checks = IntentEvent.objects.filter(
        conversation__tenant=request.tenant,
        intent_name='CHECK_AVAILABILITY',
        created_at__gte=start_date
    ).count()
    
    bookings_completed = Appointment.objects.filter(
        tenant=request.tenant,
        status__in=['confirmed', 'done'],
        created_at__gte=start_date
    ).count()
    
    service_conversion_rate = None
    if service_views > 0:
        service_conversion_rate = (bookings_completed / service_views) * 100
    
    # Build response
    funnel_data = {
        'date_range': date_range,
        'start_date': start_date.date(),
        'end_date': end_date.date(),
        'product_views': product_views,
        'add_to_cart': add_to_cart,
        'checkout_initiated': checkout_initiated,
        'orders_completed': orders_completed,
        'product_conversion_rate': product_conversion_rate,
        'service_views': service_views,
        'availability_checks': availability_checks,
        'bookings_completed': bookings_completed,
        'service_conversion_rate': service_conversion_rate,
    }
    
    serializer = ConversionFunnelSerializer(funnel_data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_analytics_revenue(request):
    """
    Get platform revenue analytics (admin/platform operator only).
    
    This endpoint is NOT tenant-scoped and requires superuser access.
    
    Query Parameters:
        range: Date range like '7d', '30d' (default: '30d')
        group_by: 'date', 'tier', or 'tenant' (default: 'date')
    
    Returns:
        200: Revenue metrics
        400: Invalid parameters
        403: Not a superuser
    
    Example:
        GET /v1/admin/analytics/revenue?range=30d&group_by=tier
    
    Required scope: Platform operator (superuser)
    """
    # Check if user is superuser (platform operator)
    if not request.user.is_superuser:
        return Response(
            {'error': 'This endpoint requires platform operator access'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    date_range = request.query_params.get('range', '30d')
    group_by = request.query_params.get('group_by', 'date')
    
    # Validate date range format
    if not date_range.endswith('d') or not date_range[:-1].isdigit():
        return Response(
            {'error': 'Invalid date range format. Use format like "7d", "30d"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate group_by parameter
    if group_by not in ['date', 'tier', 'tenant']:
        return Response(
            {'error': 'Invalid group_by parameter. Use "date", "tier", or "tenant"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Calculate date range
    days = int(date_range.rstrip('d'))
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Payment facilitation metrics
    payment_transactions = Transaction.objects.filter(
        transaction_type='customer_payment',
        status='completed',
        created_at__gte=start_date
    ).aggregate(
        total_volume=Sum('amount'),
        total_fees=Sum('fee')
    )
    
    payment_volume = payment_transactions['total_volume'] or Decimal('0')
    platform_fees = payment_transactions['total_fees'] or Decimal('0')
    
    # Subscription revenue
    subscription_charges = Transaction.objects.filter(
        transaction_type='subscription_charge',
        status='completed',
        created_at__gte=start_date
    ).aggregate(total=Sum('amount'))
    
    subscription_revenue = subscription_charges['total'] or Decimal('0')
    
    # Active subscriptions
    active_subscriptions = Subscription.objects.filter(
        status='active'
    ).count()
    
    # Group by date if requested
    by_date = []
    if group_by == 'date':
        from django.db.models.functions import TruncDate
        
        daily_payments = Transaction.objects.filter(
            transaction_type='customer_payment',
            status='completed',
            created_at__gte=start_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            volume=Sum('amount'),
            fees=Sum('fee')
        ).order_by('date')
        
        daily_subscriptions = Transaction.objects.filter(
            transaction_type='subscription_charge',
            status='completed',
            created_at__gte=start_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            revenue=Sum('amount')
        ).order_by('date')
        
        # Merge daily data
        date_map = {}
        for item in daily_payments:
            date_map[item['date']] = {
                'date': item['date'],
                'payment_volume': float(item['volume'] or 0),
                'platform_fees': float(item['fees'] or 0),
                'subscription_revenue': 0,
            }
        
        for item in daily_subscriptions:
            if item['date'] in date_map:
                date_map[item['date']]['subscription_revenue'] = float(item['revenue'] or 0)
            else:
                date_map[item['date']] = {
                    'date': item['date'],
                    'payment_volume': 0,
                    'platform_fees': 0,
                    'subscription_revenue': float(item['revenue'] or 0),
                }
        
        by_date = list(date_map.values())
    
    # Group by tier if requested
    by_tier = []
    if group_by == 'tier':
        from apps.tenants.models import SubscriptionTier
        tiers = SubscriptionTier.objects.all()
        
        for tier in tiers:
            tier_subs = Subscription.objects.filter(
                tier=tier,
                status='active'
            ).count()
            
            tier_revenue = Transaction.objects.filter(
                tenant__subscription__tier=tier,
                transaction_type='customer_payment',
                status='completed',
                created_at__gte=start_date
            ).aggregate(
                volume=Sum('amount'),
                fees=Sum('fee')
            )
            
            tier_sub_revenue = Transaction.objects.filter(
                tenant__subscription__tier=tier,
                transaction_type='subscription_charge',
                status='completed',
                created_at__gte=start_date
            ).aggregate(revenue=Sum('amount'))
            
            by_tier.append({
                'tier_name': tier.name,
                'active_subscriptions': tier_subs,
                'payment_volume': float(tier_revenue['volume'] or 0),
                'platform_fees': float(tier_revenue['fees'] or 0),
                'subscription_revenue': float(tier_sub_revenue['revenue'] or 0),
            })
    
    # Group by tenant if requested
    by_tenant = []
    if group_by == 'tenant':
        from apps.tenants.models import Tenant
        
        # Get tenants with transactions in the period
        tenant_ids = Transaction.objects.filter(
            transaction_type__in=['customer_payment', 'subscription_charge'],
            status='completed',
            created_at__gte=start_date
        ).values_list('tenant_id', flat=True).distinct()
        
        tenants = Tenant.objects.filter(id__in=tenant_ids)
        
        for tenant in tenants:
            tenant_payments = Transaction.objects.filter(
                tenant=tenant,
                transaction_type='customer_payment',
                status='completed',
                created_at__gte=start_date
            ).aggregate(
                volume=Sum('amount'),
                fees=Sum('fee')
            )
            
            tenant_sub_revenue = Transaction.objects.filter(
                tenant=tenant,
                transaction_type='subscription_charge',
                status='completed',
                created_at__gte=start_date
            ).aggregate(revenue=Sum('amount'))
            
            by_tenant.append({
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'tenant_slug': tenant.slug,
                'tier_name': tenant.subscription_tier.name if tenant.subscription_tier else None,
                'payment_volume': float(tenant_payments['volume'] or 0),
                'platform_fees': float(tenant_payments['fees'] or 0),
                'subscription_revenue': float(tenant_sub_revenue['revenue'] or 0),
            })
    
    # Build response
    revenue_data = {
        'date_range': date_range,
        'start_date': start_date.date(),
        'end_date': end_date.date(),
        'group_by': group_by,
        'payment_volume': payment_volume,
        'platform_fees': platform_fees,
        'subscription_revenue': subscription_revenue,
        'active_subscriptions': active_subscriptions,
        'by_date': by_date,
        'by_tier': by_tier,
        'by_tenant': by_tenant,
    }
    
    serializer = RevenueAnalyticsSerializer(revenue_data)
    return Response(serializer.data)
