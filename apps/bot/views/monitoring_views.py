"""
Monitoring and observability API views for system health tracking.

Provides endpoints for accessing conversation metrics, system health,
and performance data for monitoring dashboards and alerting systems.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.permissions import HasTenantScopes
from apps.bot.services.metrics_collector import metrics_collector
from apps.bot.services.observability import observability_service
from apps.bot.models_conversation_state import ConversationSession
from apps.tenants.models import Customer

logger = logging.getLogger(__name__)


class SystemHealthView(APIView):
    """
    System health and metrics overview.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get system health metrics",
        description="Returns comprehensive system health metrics including journey completion rates, payment success, escalation frequency, and performance data.",
        responses={
            200: OpenApiResponse(description="System health metrics retrieved successfully"),
            403: OpenApiResponse(description="Insufficient permissions"),
        }
    )
    def get(self, request):
        """Get comprehensive system health metrics."""
        try:
            # Get comprehensive metrics from collector
            metrics_summary = metrics_collector.get_comprehensive_metrics_summary()
            
            # Get system health from observability service
            system_health = observability_service.get_system_health_summary()
            
            # Get tenant-specific metrics
            tenant = request.tenant
            tenant_metrics = self._get_tenant_metrics(tenant)
            
            # Combine all metrics
            health_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'system_health': system_health,
                'metrics_summary': metrics_summary,
                'tenant_metrics': tenant_metrics,
                'status': self._determine_system_status(system_health, metrics_summary)
            }
            
            logger.info(
                "System health metrics retrieved",
                extra={
                    'tenant_id': str(tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                    'metrics_count': len(metrics_summary.get('journey_metrics', {})),
                    'system_status': health_data['status']
                }
            )
            
            return Response(health_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve system health metrics: {e}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                },
                exc_info=True
            )
            
            return Response(
                {'error': 'Failed to retrieve system health metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_tenant_metrics(self, tenant) -> Dict[str, Any]:
        """Get tenant-specific metrics."""
        try:
            # Get conversation counts for the tenant
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)
            
            # Active conversations
            active_conversations = ConversationSession.objects.filter(
                tenant_id=tenant.id,
                is_active=True
            ).count()
            
            # Recent conversations
            conversations_24h = ConversationSession.objects.filter(
                tenant_id=tenant.id,
                created_at__gte=last_24h
            ).count()
            
            conversations_7d = ConversationSession.objects.filter(
                tenant_id=tenant.id,
                created_at__gte=last_7d
            ).count()
            
            # Customer counts
            total_customers = Customer.objects.filter(tenant_id=tenant.id).count()
            active_customers_24h = Customer.objects.filter(
                tenant_id=tenant.id,
                last_seen__gte=last_24h
            ).count()
            
            return {
                'active_conversations': active_conversations,
                'conversations_24h': conversations_24h,
                'conversations_7d': conversations_7d,
                'total_customers': total_customers,
                'active_customers_24h': active_customers_24h,
                'bot_name': tenant.bot_name,
                'max_chattiness_level': tenant.max_chattiness_level,
                'default_language': tenant.default_language,
            }
            
        except Exception as e:
            logger.warning(f"Failed to get tenant metrics: {e}")
            return {}
    
    def _determine_system_status(self, system_health: Dict[str, Any], metrics_summary: Dict[str, Any]) -> str:
        """Determine overall system status based on metrics."""
        try:
            # Check error rates
            error_rate = system_health.get('error_rate', 0)
            escalation_rate = system_health.get('escalation_rate', 0)
            
            # Check journey completion rates
            journey_metrics = metrics_summary.get('journey_metrics', {})
            avg_completion_rate = 0
            if journey_metrics:
                completion_rates = [
                    metrics.get('completion_rate', 0) 
                    for metrics in journey_metrics.values()
                ]
                avg_completion_rate = sum(completion_rates) / len(completion_rates)
            
            # Check payment success rates
            payment_metrics = metrics_summary.get('payment_metrics', {})
            avg_payment_success = 0
            if payment_metrics:
                success_rates = [
                    metrics.get('success_rate', 0) 
                    for metrics in payment_metrics.values()
                ]
                avg_payment_success = sum(success_rates) / len(success_rates)
            
            # Determine status based on thresholds
            if error_rate > 0.1 or escalation_rate > 0.3:  # 10% error rate or 30% escalation rate
                return 'critical'
            elif error_rate > 0.05 or escalation_rate > 0.2 or avg_completion_rate < 0.7:
                return 'warning'
            elif avg_completion_rate > 0.8 and avg_payment_success > 0.8:
                return 'excellent'
            else:
                return 'healthy'
                
        except Exception as e:
            logger.warning(f"Failed to determine system status: {e}")
            return 'unknown'


class JourneyMetricsView(APIView):
    """
    Journey completion metrics and analytics.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get journey completion metrics",
        description="Returns detailed journey completion rates, durations, and failure analysis.",
        responses={
            200: OpenApiResponse(description="Journey metrics retrieved successfully"),
            403: OpenApiResponse(description="Insufficient permissions"),
        }
    )
    def get(self, request):
        """Get detailed journey completion metrics."""
        try:
            # Get journey completion rates
            completion_rates = metrics_collector.get_journey_completion_rates()
            
            # Get detailed journey metrics
            journey_metrics = metrics_collector.get_comprehensive_metrics_summary().get('journey_metrics', {})
            
            # Calculate additional analytics
            analytics = self._calculate_journey_analytics(journey_metrics)
            
            response_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tenant_id': str(request.tenant.id),
                'completion_rates': completion_rates,
                'detailed_metrics': journey_metrics,
                'analytics': analytics
            }
            
            logger.info(
                "Journey metrics retrieved",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                    'journey_count': len(journey_metrics)
                }
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve journey metrics: {e}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                },
                exc_info=True
            )
            
            return Response(
                {'error': 'Failed to retrieve journey metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_journey_analytics(self, journey_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate additional journey analytics."""
        try:
            total_started = sum(metrics.get('total_started', 0) for metrics in journey_metrics.values())
            total_completed = sum(metrics.get('total_completed', 0) for metrics in journey_metrics.values())
            total_failed = sum(metrics.get('total_failed', 0) for metrics in journey_metrics.values())
            total_abandoned = sum(metrics.get('total_abandoned', 0) for metrics in journey_metrics.values())
            
            # Find best and worst performing journeys
            best_journey = None
            worst_journey = None
            best_rate = 0
            worst_rate = 1
            
            for journey_type, metrics in journey_metrics.items():
                completion_rate = metrics.get('completion_rate', 0)
                if completion_rate > best_rate:
                    best_rate = completion_rate
                    best_journey = journey_type
                if completion_rate < worst_rate:
                    worst_rate = completion_rate
                    worst_journey = journey_type
            
            return {
                'overall_completion_rate': total_completed / max(total_started, 1),
                'overall_failure_rate': total_failed / max(total_started, 1),
                'overall_abandonment_rate': total_abandoned / max(total_started, 1),
                'total_journeys_started': total_started,
                'best_performing_journey': {
                    'journey_type': best_journey,
                    'completion_rate': best_rate
                },
                'worst_performing_journey': {
                    'journey_type': worst_journey,
                    'completion_rate': worst_rate
                }
            }
            
        except Exception as e:
            logger.warning(f"Failed to calculate journey analytics: {e}")
            return {}


class PaymentMetricsView(APIView):
    """
    Payment success metrics and analytics.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get payment success metrics",
        description="Returns detailed payment success rates, processing times, and method performance.",
        responses={
            200: OpenApiResponse(description="Payment metrics retrieved successfully"),
            403: OpenApiResponse(description="Insufficient permissions"),
        }
    )
    def get(self, request):
        """Get detailed payment success metrics."""
        try:
            # Get payment success rates
            success_rates = metrics_collector.get_payment_success_rates()
            
            # Get detailed payment metrics
            payment_metrics = metrics_collector.get_comprehensive_metrics_summary().get('payment_metrics', {})
            
            # Calculate additional analytics
            analytics = self._calculate_payment_analytics(payment_metrics)
            
            response_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tenant_id': str(request.tenant.id),
                'success_rates': success_rates,
                'detailed_metrics': payment_metrics,
                'analytics': analytics
            }
            
            logger.info(
                "Payment metrics retrieved",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                    'payment_method_count': len(payment_metrics)
                }
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve payment metrics: {e}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                },
                exc_info=True
            )
            
            return Response(
                {'error': 'Failed to retrieve payment metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_payment_analytics(self, payment_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate additional payment analytics."""
        try:
            total_initiated = sum(metrics.get('total_initiated', 0) for metrics in payment_metrics.values())
            total_completed = sum(metrics.get('total_completed', 0) for metrics in payment_metrics.values())
            total_failed = sum(metrics.get('total_failed', 0) for metrics in payment_metrics.values())
            total_abandoned = sum(metrics.get('total_abandoned', 0) for metrics in payment_metrics.values())
            
            # Calculate total revenue (sum of average amounts * completed payments)
            total_revenue = sum(
                metrics.get('avg_amount', 0) * metrics.get('total_completed', 0)
                for metrics in payment_metrics.values()
            )
            
            # Find best and worst performing payment methods
            best_method = None
            worst_method = None
            best_rate = 0
            worst_rate = 1
            
            for method, metrics in payment_metrics.items():
                success_rate = metrics.get('success_rate', 0)
                if success_rate > best_rate:
                    best_rate = success_rate
                    best_method = method
                if success_rate < worst_rate:
                    worst_rate = success_rate
                    worst_method = method
            
            return {
                'overall_success_rate': total_completed / max(total_initiated, 1),
                'overall_failure_rate': total_failed / max(total_initiated, 1),
                'overall_abandonment_rate': total_abandoned / max(total_initiated, 1),
                'total_payments_initiated': total_initiated,
                'total_revenue_estimate': total_revenue,
                'best_performing_method': {
                    'payment_method': best_method,
                    'success_rate': best_rate
                },
                'worst_performing_method': {
                    'payment_method': worst_method,
                    'success_rate': worst_rate
                }
            }
            
        except Exception as e:
            logger.warning(f"Failed to calculate payment analytics: {e}")
            return {}


class EscalationMetricsView(APIView):
    """
    Escalation frequency metrics and analysis.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get escalation frequency metrics",
        description="Returns detailed escalation frequencies, reasons, and trigger analysis.",
        responses={
            200: OpenApiResponse(description="Escalation metrics retrieved successfully"),
            403: OpenApiResponse(description="Insufficient permissions"),
        }
    )
    def get(self, request):
        """Get detailed escalation frequency metrics."""
        try:
            # Get escalation frequencies
            escalation_frequencies = metrics_collector.get_escalation_frequencies()
            
            # Get detailed escalation metrics
            escalation_metrics = metrics_collector.get_comprehensive_metrics_summary().get('escalation_metrics', {})
            
            # Calculate additional analytics
            analytics = self._calculate_escalation_analytics(escalation_metrics)
            
            response_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tenant_id': str(request.tenant.id),
                'escalation_frequencies': escalation_frequencies,
                'detailed_metrics': escalation_metrics,
                'analytics': analytics
            }
            
            logger.info(
                "Escalation metrics retrieved",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                    'escalation_reason_count': len(escalation_metrics)
                }
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve escalation metrics: {e}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                },
                exc_info=True
            )
            
            return Response(
                {'error': 'Failed to retrieve escalation metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_escalation_analytics(self, escalation_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate additional escalation analytics."""
        try:
            total_escalations = sum(metrics.get('total_escalations', 0) for metrics in escalation_metrics.values())
            
            # Calculate trigger breakdown
            trigger_totals = {
                'explicit_human_requests': 0,
                'payment_disputes': 0,
                'missing_information': 0,
                'repeated_failures': 0,
                'sensitive_content': 0,
                'user_frustration': 0,
                'system_errors': 0
            }
            
            for metrics in escalation_metrics.values():
                for trigger in trigger_totals.keys():
                    trigger_totals[trigger] += metrics.get(trigger, 0)
            
            # Find most common escalation reason
            most_common_reason = None
            most_common_count = 0
            
            for reason, metrics in escalation_metrics.items():
                count = metrics.get('total_escalations', 0)
                if count > most_common_count:
                    most_common_count = count
                    most_common_reason = reason
            
            return {
                'total_escalations': total_escalations,
                'trigger_breakdown': trigger_totals,
                'trigger_percentages': {
                    trigger: (count / max(total_escalations, 1)) * 100
                    for trigger, count in trigger_totals.items()
                },
                'most_common_reason': {
                    'reason': most_common_reason,
                    'count': most_common_count,
                    'percentage': (most_common_count / max(total_escalations, 1)) * 100
                }
            }
            
        except Exception as e:
            logger.warning(f"Failed to calculate escalation analytics: {e}")
            return {}


class PerformanceMetricsView(APIView):
    """
    System performance metrics and monitoring.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get system performance metrics",
        description="Returns detailed performance metrics including response times, success rates, and component health.",
        responses={
            200: OpenApiResponse(description="Performance metrics retrieved successfully"),
            403: OpenApiResponse(description="Insufficient permissions"),
        }
    )
    def get(self, request):
        """Get detailed system performance metrics."""
        try:
            # Get performance summary
            performance_summary = metrics_collector.get_performance_summary()
            
            # Get system health metrics
            system_health = observability_service.get_system_health_summary()
            
            response_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'tenant_id': str(request.tenant.id),
                'performance_summary': performance_summary,
                'system_health': system_health,
                'recommendations': self._generate_performance_recommendations(performance_summary)
            }
            
            logger.info(
                "Performance metrics retrieved",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                    'component_count': len(performance_summary)
                }
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve performance metrics: {e}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'request_id': getattr(request, 'request_id', 'unknown'),
                },
                exc_info=True
            )
            
            return Response(
                {'error': 'Failed to retrieve performance metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_performance_recommendations(self, performance_summary: Dict[str, Any]) -> list:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        try:
            for component, metrics in performance_summary.items():
                avg_response_time = metrics.get('avg_response_time', 0)
                p95_response_time = metrics.get('p95_response_time', 0)
                success_rate = metrics.get('success_rate', 1)
                error_rate = metrics.get('error_rate', 0)
                
                # Check for slow response times
                if avg_response_time > 2.0:  # 2 seconds
                    recommendations.append({
                        'type': 'performance',
                        'severity': 'high' if avg_response_time > 5.0 else 'medium',
                        'component': component,
                        'issue': f'High average response time: {avg_response_time:.2f}s',
                        'recommendation': 'Consider optimizing queries, adding caching, or scaling resources'
                    })
                
                # Check for high P95 response times
                if p95_response_time > 5.0:  # 5 seconds
                    recommendations.append({
                        'type': 'performance',
                        'severity': 'medium',
                        'component': component,
                        'issue': f'High P95 response time: {p95_response_time:.2f}s',
                        'recommendation': 'Investigate outlier requests and optimize slow operations'
                    })
                
                # Check for high error rates
                if error_rate > 0.05:  # 5%
                    recommendations.append({
                        'type': 'reliability',
                        'severity': 'high' if error_rate > 0.1 else 'medium',
                        'component': component,
                        'issue': f'High error rate: {error_rate:.1%}',
                        'recommendation': 'Review error logs and implement better error handling'
                    })
                
                # Check for low success rates
                if success_rate < 0.95:  # 95%
                    recommendations.append({
                        'type': 'reliability',
                        'severity': 'high' if success_rate < 0.9 else 'medium',
                        'component': component,
                        'issue': f'Low success rate: {success_rate:.1%}',
                        'recommendation': 'Investigate failures and improve system reliability'
                    })
            
        except Exception as e:
            logger.warning(f"Failed to generate performance recommendations: {e}")
        
        return recommendations