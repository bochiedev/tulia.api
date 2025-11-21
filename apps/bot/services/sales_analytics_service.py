"""
Sales Analytics Service for sales orchestration refactor.

This service provides analytics and monitoring for the sales bot.

Design principles:
- Track intent classification method distribution
- Track LLM usage per tenant
- Track conversion rates (enquiry → order → payment)
- Track payment success/failure rates
- Track response times by handler
- Track error rates by type
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from decimal import Decimal

logger = logging.getLogger(__name__)


class SalesAnalyticsService:
    """
    Analytics service for sales orchestration monitoring.
    
    Responsibilities:
    - Track intent classification metrics
    - Track LLM usage and costs
    - Track conversion funnel metrics
    - Track payment metrics
    - Track error rates
    """
    
    def get_intent_classification_stats(
        self,
        tenant,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get intent classification method distribution.
        
        Args:
            tenant: Tenant instance
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dict with classification stats
        """
        from apps.bot.models_sales_orchestration import IntentClassificationLog
        
        # Default to last 7 days
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        # Get logs for period
        logs = IntentClassificationLog.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Count by method
        method_counts = logs.values('method').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Calculate percentages
        total = logs.count()
        method_distribution = {}
        for item in method_counts:
            method = item['method']
            count = item['count']
            percentage = (count / total * 100) if total > 0 else 0
            method_distribution[method] = {
                'count': count,
                'percentage': round(percentage, 2)
            }
        
        # Average confidence by method
        avg_confidence = logs.values('method').annotate(
            avg_confidence=Avg('confidence')
        )
        
        for item in avg_confidence:
            method = item['method']
            if method in method_distribution:
                method_distribution[method]['avg_confidence'] = round(
                    item['avg_confidence'], 3
                )
        
        return {
            'total_classifications': total,
            'method_distribution': method_distribution,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def get_llm_usage_stats(
        self,
        tenant,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get LLM usage and cost statistics.
        
        Args:
            tenant: Tenant instance
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dict with LLM usage stats
        """
        from apps.bot.models_sales_orchestration import LLMUsageLog
        
        # Default to current month
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0)
        
        # Get logs for period
        logs = LLMUsageLog.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Aggregate stats
        stats = logs.aggregate(
            total_calls=Count('id'),
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('estimated_cost_usd')
        )
        
        # Usage by model
        model_usage = logs.values('model_name').annotate(
            calls=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('estimated_cost_usd')
        ).order_by('-calls')
        
        # Usage by task type
        task_usage = logs.values('task_type').annotate(
            calls=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('estimated_cost_usd')
        ).order_by('-calls')
        
        return {
            'total_calls': stats['total_calls'] or 0,
            'total_tokens': stats['total_tokens'] or 0,
            'total_cost_usd': float(stats['total_cost'] or Decimal('0')),
            'model_usage': list(model_usage),
            'task_usage': list(task_usage),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def get_conversion_funnel_stats(
        self,
        tenant,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get conversion funnel metrics (enquiry → order → payment).
        
        Args:
            tenant: Tenant instance
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dict with conversion funnel stats
        """
        from apps.bot.models_sales_orchestration import IntentClassificationLog
        from apps.orders.models import Order
        from apps.bot.models_sales_orchestration import PaymentRequest
        
        # Default to last 30 days
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Count enquiries (product browsing intents)
        enquiries = IntentClassificationLog.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date,
            detected_intent__in=['BROWSE_PRODUCTS', 'PRODUCT_DETAILS']
        ).values('conversation').distinct().count()
        
        # Count orders created
        orders = Order.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        # Count successful payments
        payments = PaymentRequest.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date,
            status='SUCCESS'
        ).count()
        
        # Calculate conversion rates
        enquiry_to_order = (orders / enquiries * 100) if enquiries > 0 else 0
        order_to_payment = (payments / orders * 100) if orders > 0 else 0
        enquiry_to_payment = (payments / enquiries * 100) if enquiries > 0 else 0
        
        return {
            'enquiries': enquiries,
            'orders': orders,
            'payments': payments,
            'conversion_rates': {
                'enquiry_to_order': round(enquiry_to_order, 2),
                'order_to_payment': round(order_to_payment, 2),
                'enquiry_to_payment': round(enquiry_to_payment, 2)
            },
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def get_payment_stats(
        self,
        tenant,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get payment success/failure rates.
        
        Args:
            tenant: Tenant instance
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dict with payment stats
        """
        from apps.bot.models_sales_orchestration import PaymentRequest
        
        # Default to last 30 days
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Get payment requests for period
        payments = PaymentRequest.objects.filter(
            tenant=tenant,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Count by status
        status_counts = payments.values('status').annotate(
            count=Count('id')
        )
        
        # Count by payment method
        method_counts = payments.values('payment_method').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(status='SUCCESS'))
        )
        
        # Calculate success rate
        total = payments.count()
        successful = payments.filter(status='SUCCESS').count()
        success_rate = (successful / total * 100) if total > 0 else 0
        
        # Calculate total amount
        total_amount = payments.filter(status='SUCCESS').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        return {
            'total_requests': total,
            'successful': successful,
            'success_rate': round(success_rate, 2),
            'total_amount': float(total_amount),
            'status_distribution': {
                item['status']: item['count']
                for item in status_counts
            },
            'method_performance': list(method_counts),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def log_handler_response_time(
        self,
        tenant,
        handler_name: str,
        response_time_ms: int,
        success: bool = True
    ) -> None:
        """
        Log response time for a handler.
        
        Args:
            tenant: Tenant instance
            handler_name: Name of the handler
            response_time_ms: Response time in milliseconds
            success: Whether the handler succeeded
        """
        # This would typically go to a time-series database or metrics system
        # For now, just log it
        logger.info(
            f"Handler response time: tenant={tenant.id}, "
            f"handler={handler_name}, time={response_time_ms}ms, "
            f"success={success}"
        )
    
    def log_error(
        self,
        tenant,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an error for analytics.
        
        Args:
            tenant: Tenant instance
            error_type: Type of error
            error_message: Error message
            context: Optional context dict
        """
        logger.error(
            f"Sales bot error: tenant={tenant.id}, "
            f"type={error_type}, message={error_message}, "
            f"context={context}"
        )


__all__ = ['SalesAnalyticsService']
