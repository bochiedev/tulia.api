"""
Celery tasks for provider tracking and analytics.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='bot.aggregate_provider_daily_summary')
def aggregate_provider_daily_summary(date_str=None):
    """
    Aggregate provider usage into daily summaries.
    
    Args:
        date_str: Optional date string (YYYY-MM-DD), defaults to yesterday
    """
    from apps.bot.models_provider_tracking import ProviderUsage, ProviderDailySummary
    from apps.tenants.models import Tenant
    
    # Parse date or use yesterday
    if date_str:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        target_date = (timezone.now() - timedelta(days=1)).date()
    
    logger.info(f"Aggregating provider usage for date: {target_date}")
    
    # Get all tenants
    tenants = Tenant.objects.filter(is_deleted=False)
    
    total_summaries = 0
    
    for tenant in tenants:
        # Get usage for this tenant and date
        usage_qs = ProviderUsage.objects.filter(
            tenant=tenant,
            created_at__date=target_date,
            is_deleted=False
        )
        
        if not usage_qs.exists():
            continue
        
        # Group by provider and model
        grouped = usage_qs.values('provider', 'model').annotate(
            total_calls=Count('id'),
            successful_calls=Count('id', filter=Q(success=True)),
            failed_calls=Count('id', filter=Q(success=False)),
            total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
            total_tokens_sum=Sum('total_tokens'),
            total_cost_sum=Sum('estimated_cost'),
            avg_latency=Avg('latency_ms'),
            failover_count=Count('id', filter=Q(was_failover=True))
        )
        
        for group in grouped:
            # Calculate percentiles (simplified - would use proper percentile in production)
            latencies = list(
                usage_qs.filter(
                    provider=group['provider'],
                    model=group['model']
                ).values_list('latency_ms', flat=True).order_by('latency_ms')
            )
            
            p50 = latencies[len(latencies) // 2] if latencies else None
            p95 = latencies[int(len(latencies) * 0.95)] if latencies else None
            p99 = latencies[int(len(latencies) * 0.99)] if latencies else None
            
            # Create or update summary
            summary, created = ProviderDailySummary.objects.update_or_create(
                tenant=tenant,
                date=target_date,
                provider=group['provider'],
                model=group['model'],
                defaults={
                    'total_calls': group['total_calls'],
                    'successful_calls': group['successful_calls'],
                    'failed_calls': group['failed_calls'],
                    'total_input_tokens': group['total_input_tokens'] or 0,
                    'total_output_tokens': group['total_output_tokens'] or 0,
                    'total_tokens': group['total_tokens_sum'] or 0,
                    'total_cost': group['total_cost_sum'] or Decimal('0'),
                    'avg_latency_ms': group['avg_latency'],
                    'p50_latency_ms': p50,
                    'p95_latency_ms': p95,
                    'p99_latency_ms': p99,
                    'failover_count': group['failover_count']
                }
            )
            
            total_summaries += 1
            
            logger.info(
                f"{'Created' if created else 'Updated'} summary for "
                f"{tenant.name} - {target_date} - {group['provider']}/{group['model']}"
            )
    
    logger.info(
        f"Aggregation complete: {total_summaries} summaries for {target_date}"
    )
    
    return {
        'date': str(target_date),
        'summaries_created': total_summaries
    }


@shared_task(name='bot.cleanup_old_provider_usage')
def cleanup_old_provider_usage(days_to_keep=90):
    """
    Clean up old provider usage records.
    
    Keeps daily summaries but removes detailed usage records older than specified days.
    
    Args:
        days_to_keep: Number of days of detailed usage to keep (default 90)
    """
    from apps.bot.models_provider_tracking import ProviderUsage
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    logger.info(f"Cleaning up provider usage older than {cutoff_date}")
    
    # Soft delete old records
    deleted_count = ProviderUsage.objects.filter(
        created_at__lt=cutoff_date,
        is_deleted=False
    ).update(is_deleted=True)
    
    logger.info(f"Soft deleted {deleted_count} old provider usage records")
    
    return {
        'cutoff_date': str(cutoff_date),
        'deleted_count': deleted_count
    }


@shared_task(name='bot.calculate_provider_health_metrics')
def calculate_provider_health_metrics():
    """
    Calculate and log provider health metrics.
    
    Analyzes recent provider performance and logs warnings for unhealthy providers.
    """
    from apps.bot.models_provider_tracking import ProviderUsage
    from apps.tenants.models import Tenant
    
    # Analyze last 24 hours
    since = timezone.now() - timedelta(hours=24)
    
    logger.info("Calculating provider health metrics for last 24 hours")
    
    # Get all tenants
    tenants = Tenant.objects.filter(is_deleted=False)
    
    health_report = []
    
    for tenant in tenants:
        # Get usage stats per provider
        stats = ProviderUsage.objects.filter(
            tenant=tenant,
            created_at__gte=since,
            is_deleted=False
        ).values('provider', 'model').annotate(
            total_calls=Count('id'),
            successful_calls=Count('id', filter=Q(success=True)),
            failed_calls=Count('id', filter=Q(success=False)),
            avg_latency=Avg('latency_ms'),
            total_cost=Sum('estimated_cost')
        )
        
        for stat in stats:
            if stat['total_calls'] == 0:
                continue
            
            success_rate = stat['successful_calls'] / stat['total_calls']
            failure_rate = stat['failed_calls'] / stat['total_calls']
            
            health_status = {
                'tenant': tenant.name,
                'provider': stat['provider'],
                'model': stat['model'],
                'total_calls': stat['total_calls'],
                'success_rate': success_rate,
                'failure_rate': failure_rate,
                'avg_latency_ms': stat['avg_latency'],
                'total_cost': float(stat['total_cost'] or 0)
            }
            
            health_report.append(health_status)
            
            # Log warnings for unhealthy providers
            if failure_rate > 0.1:  # >10% failure rate
                logger.warning(
                    f"High failure rate for {tenant.name} - "
                    f"{stat['provider']}/{stat['model']}: {failure_rate:.2%}"
                )
            
            if stat['avg_latency'] and stat['avg_latency'] > 5000:  # >5 seconds
                logger.warning(
                    f"High latency for {tenant.name} - "
                    f"{stat['provider']}/{stat['model']}: {stat['avg_latency']:.0f}ms"
                )
    
    logger.info(f"Health metrics calculated for {len(health_report)} provider/model combinations")
    
    return health_report
