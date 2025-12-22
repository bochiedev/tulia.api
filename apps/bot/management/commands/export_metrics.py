"""
Management command to export metrics for external monitoring systems.

Exports comprehensive metrics data in various formats for integration
with monitoring dashboards, alerting systems, and analytics platforms.
"""
import json
import csv
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as django_timezone

from apps.bot.services.metrics_collector import metrics_collector
from apps.bot.services.observability import observability_service
from apps.tenants.models import Tenant, Customer
from apps.bot.models_conversation_state import ConversationSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Export metrics command."""
    
    help = 'Export comprehensive metrics for external monitoring systems'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv', 'prometheus'],
            default='json',
            help='Output format (default: json)'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: stdout)'
        )
        
        parser.add_argument(
            '--tenant',
            type=str,
            help='Export metrics for specific tenant (slug or ID)'
        )
        
        parser.add_argument(
            '--period',
            type=str,
            choices=['1h', '24h', '7d', '30d'],
            default='24h',
            help='Time period for metrics (default: 24h)'
        )
        
        parser.add_argument(
            '--include-system-health',
            action='store_true',
            help='Include system health metrics'
        )
        
        parser.add_argument(
            '--include-performance',
            action='store_true',
            help='Include performance metrics'
        )
        
        parser.add_argument(
            '--aggregate',
            action='store_true',
            help='Trigger metrics aggregation before export'
        )
    
    def handle(self, *args, **options):
        """Handle command execution."""
        try:
            # Trigger aggregation if requested
            if options['aggregate']:
                self.stdout.write("Aggregating metrics...")
                metrics_collector.aggregate_hourly_metrics()
                metrics_collector.aggregate_daily_metrics()
            
            # Get tenant filter
            tenant_filter = self._get_tenant_filter(options.get('tenant'))
            
            # Get time period
            period = self._get_time_period(options['period'])
            
            # Collect metrics
            metrics_data = self._collect_metrics(
                tenant_filter=tenant_filter,
                period=period,
                include_system_health=options['include_system_health'],
                include_performance=options['include_performance']
            )
            
            # Export in requested format
            output_format = options['format']
            output_file = options.get('output')
            
            if output_format == 'json':
                self._export_json(metrics_data, output_file)
            elif output_format == 'csv':
                self._export_csv(metrics_data, output_file)
            elif output_format == 'prometheus':
                self._export_prometheus(metrics_data, output_file)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported metrics in {output_format} format"
                )
            )
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}", exc_info=True)
            raise CommandError(f"Failed to export metrics: {e}")
    
    def _get_tenant_filter(self, tenant_param: str) -> Tenant:
        """Get tenant filter from parameter."""
        if not tenant_param:
            return None
        
        try:
            # Try to get by ID first
            if tenant_param.isdigit():
                return Tenant.objects.get(id=tenant_param)
            else:
                # Try to get by slug
                return Tenant.objects.get(slug=tenant_param)
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant not found: {tenant_param}")
    
    def _get_time_period(self, period_str: str) -> timedelta:
        """Convert period string to timedelta."""
        period_map = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30)
        }
        return period_map[period_str]
    
    def _collect_metrics(
        self, 
        tenant_filter: Tenant = None,
        period: timedelta = None,
        include_system_health: bool = False,
        include_performance: bool = False
    ) -> Dict[str, Any]:
        """Collect comprehensive metrics data."""
        now = django_timezone.now()
        start_time = now - period if period else now - timedelta(hours=24)
        
        # Base metrics from collector
        metrics_data = {
            'export_timestamp': now.isoformat(),
            'period_start': start_time.isoformat(),
            'period_end': now.isoformat(),
            'tenant_filter': str(tenant_filter.id) if tenant_filter else None,
            'comprehensive_metrics': metrics_collector.get_comprehensive_metrics_summary()
        }
        
        # Add tenant-specific data
        if tenant_filter:
            metrics_data['tenant_data'] = self._get_tenant_data(tenant_filter, start_time, now)
        else:
            metrics_data['tenant_summary'] = self._get_all_tenants_summary(start_time, now)
        
        # Add system health if requested
        if include_system_health:
            metrics_data['system_health'] = observability_service.get_system_health_summary()
        
        # Add performance metrics if requested
        if include_performance:
            metrics_data['performance_metrics'] = metrics_collector.get_performance_summary()
        
        return metrics_data
    
    def _get_tenant_data(self, tenant: Tenant, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get detailed data for specific tenant."""
        # Conversation metrics
        conversations_total = ConversationSession.objects.filter(
            tenant_id=tenant.id
        ).count()
        
        conversations_period = ConversationSession.objects.filter(
            tenant_id=tenant.id,
            created_at__gte=start_time,
            created_at__lte=end_time
        ).count()
        
        active_conversations = ConversationSession.objects.filter(
            tenant_id=tenant.id,
            is_active=True
        ).count()
        
        # Customer metrics
        customers_total = Customer.objects.filter(tenant_id=tenant.id).count()
        
        customers_active = Customer.objects.filter(
            tenant_id=tenant.id,
            last_seen__gte=start_time
        ).count()
        
        return {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name,
            'tenant_slug': tenant.slug,
            'bot_name': tenant.bot_name,
            'conversations': {
                'total': conversations_total,
                'period': conversations_period,
                'active': active_conversations
            },
            'customers': {
                'total': customers_total,
                'active_in_period': customers_active
            },
            'configuration': {
                'default_language': tenant.default_language,
                'max_chattiness_level': tenant.max_chattiness_level,
                'tone_style': getattr(tenant, 'tone_style', 'friendly_concise')
            }
        }
    
    def _get_all_tenants_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get summary data for all tenants."""
        total_tenants = Tenant.objects.count()
        
        total_conversations = ConversationSession.objects.filter(
            created_at__gte=start_time,
            created_at__lte=end_time
        ).count()
        
        active_conversations = ConversationSession.objects.filter(
            is_active=True
        ).count()
        
        total_customers = Customer.objects.count()
        
        active_customers = Customer.objects.filter(
            last_seen__gte=start_time
        ).count()
        
        return {
            'total_tenants': total_tenants,
            'conversations': {
                'total_in_period': total_conversations,
                'currently_active': active_conversations
            },
            'customers': {
                'total': total_customers,
                'active_in_period': active_customers
            }
        }
    
    def _export_json(self, metrics_data: Dict[str, Any], output_file: str = None):
        """Export metrics as JSON."""
        json_output = json.dumps(metrics_data, indent=2, default=str)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_output)
            self.stdout.write(f"Metrics exported to {output_file}")
        else:
            self.stdout.write(json_output)
    
    def _export_csv(self, metrics_data: Dict[str, Any], output_file: str = None):
        """Export metrics as CSV."""
        # Flatten metrics for CSV format
        flattened_data = self._flatten_metrics_for_csv(metrics_data)
        
        if output_file:
            with open(output_file, 'w', newline='') as csvfile:
                if flattened_data:
                    fieldnames = flattened_data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(flattened_data)
            self.stdout.write(f"Metrics exported to {output_file}")
        else:
            # Output CSV to stdout
            if flattened_data:
                fieldnames = flattened_data[0].keys()
                writer = csv.DictWriter(self.stdout, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flattened_data)
    
    def _export_prometheus(self, metrics_data: Dict[str, Any], output_file: str = None):
        """Export metrics in Prometheus format."""
        prometheus_output = self._format_prometheus_metrics(metrics_data)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(prometheus_output)
            self.stdout.write(f"Metrics exported to {output_file}")
        else:
            self.stdout.write(prometheus_output)
    
    def _flatten_metrics_for_csv(self, metrics_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten nested metrics data for CSV export."""
        flattened_rows = []
        
        # Extract journey metrics
        journey_metrics = metrics_data.get('comprehensive_metrics', {}).get('journey_metrics', {})
        for journey_type, metrics in journey_metrics.items():
            row = {
                'metric_type': 'journey',
                'metric_name': journey_type,
                'timestamp': metrics_data['export_timestamp'],
                'tenant_id': metrics_data.get('tenant_filter'),
                'total_started': metrics.get('total_started', 0),
                'total_completed': metrics.get('total_completed', 0),
                'total_failed': metrics.get('total_failed', 0),
                'completion_rate': metrics.get('completion_rate', 0),
                'avg_duration': metrics.get('avg_duration', 0)
            }
            flattened_rows.append(row)
        
        # Extract payment metrics
        payment_metrics = metrics_data.get('comprehensive_metrics', {}).get('payment_metrics', {})
        for payment_method, metrics in payment_metrics.items():
            row = {
                'metric_type': 'payment',
                'metric_name': payment_method,
                'timestamp': metrics_data['export_timestamp'],
                'tenant_id': metrics_data.get('tenant_filter'),
                'total_initiated': metrics.get('total_initiated', 0),
                'total_completed': metrics.get('total_completed', 0),
                'total_failed': metrics.get('total_failed', 0),
                'success_rate': metrics.get('success_rate', 0),
                'avg_amount': metrics.get('avg_amount', 0),
                'avg_processing_time': metrics.get('avg_processing_time', 0)
            }
            flattened_rows.append(row)
        
        # Extract escalation metrics
        escalation_metrics = metrics_data.get('comprehensive_metrics', {}).get('escalation_metrics', {})
        for reason, metrics in escalation_metrics.items():
            row = {
                'metric_type': 'escalation',
                'metric_name': reason,
                'timestamp': metrics_data['export_timestamp'],
                'tenant_id': metrics_data.get('tenant_filter'),
                'total_escalations': metrics.get('total_escalations', 0),
                'explicit_human_requests': metrics.get('explicit_human_requests', 0),
                'payment_disputes': metrics.get('payment_disputes', 0),
                'missing_information': metrics.get('missing_information', 0),
                'repeated_failures': metrics.get('repeated_failures', 0),
                'sensitive_content': metrics.get('sensitive_content', 0),
                'user_frustration': metrics.get('user_frustration', 0),
                'system_errors': metrics.get('system_errors', 0)
            }
            flattened_rows.append(row)
        
        return flattened_rows
    
    def _format_prometheus_metrics(self, metrics_data: Dict[str, Any]) -> str:
        """Format metrics in Prometheus exposition format."""
        lines = []
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        tenant_id = metrics_data.get('tenant_filter', 'all')
        
        # Journey completion metrics
        journey_metrics = metrics_data.get('comprehensive_metrics', {}).get('journey_metrics', {})
        for journey_type, metrics in journey_metrics.items():
            labels = f'journey_type="{journey_type}",tenant_id="{tenant_id}"'
            
            lines.append(f'# HELP tulia_journey_started_total Total journeys started')
            lines.append(f'# TYPE tulia_journey_started_total counter')
            lines.append(f'tulia_journey_started_total{{{labels}}} {metrics.get("total_started", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_journey_completed_total Total journeys completed')
            lines.append(f'# TYPE tulia_journey_completed_total counter')
            lines.append(f'tulia_journey_completed_total{{{labels}}} {metrics.get("total_completed", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_journey_completion_rate Journey completion rate')
            lines.append(f'# TYPE tulia_journey_completion_rate gauge')
            lines.append(f'tulia_journey_completion_rate{{{labels}}} {metrics.get("completion_rate", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_journey_avg_duration_seconds Average journey duration')
            lines.append(f'# TYPE tulia_journey_avg_duration_seconds gauge')
            lines.append(f'tulia_journey_avg_duration_seconds{{{labels}}} {metrics.get("avg_duration", 0)} {timestamp}')
        
        # Payment success metrics
        payment_metrics = metrics_data.get('comprehensive_metrics', {}).get('payment_metrics', {})
        for payment_method, metrics in payment_metrics.items():
            labels = f'payment_method="{payment_method}",tenant_id="{tenant_id}"'
            
            lines.append(f'# HELP tulia_payment_initiated_total Total payments initiated')
            lines.append(f'# TYPE tulia_payment_initiated_total counter')
            lines.append(f'tulia_payment_initiated_total{{{labels}}} {metrics.get("total_initiated", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_payment_completed_total Total payments completed')
            lines.append(f'# TYPE tulia_payment_completed_total counter')
            lines.append(f'tulia_payment_completed_total{{{labels}}} {metrics.get("total_completed", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_payment_success_rate Payment success rate')
            lines.append(f'# TYPE tulia_payment_success_rate gauge')
            lines.append(f'tulia_payment_success_rate{{{labels}}} {metrics.get("success_rate", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_payment_avg_amount Average payment amount')
            lines.append(f'# TYPE tulia_payment_avg_amount gauge')
            lines.append(f'tulia_payment_avg_amount{{{labels}}} {metrics.get("avg_amount", 0)} {timestamp}')
        
        # Escalation frequency metrics
        escalation_metrics = metrics_data.get('comprehensive_metrics', {}).get('escalation_metrics', {})
        for reason, metrics in escalation_metrics.items():
            labels = f'escalation_reason="{reason}",tenant_id="{tenant_id}"'
            
            lines.append(f'# HELP tulia_escalations_total Total escalations')
            lines.append(f'# TYPE tulia_escalations_total counter')
            lines.append(f'tulia_escalations_total{{{labels}}} {metrics.get("total_escalations", 0)} {timestamp}')
        
        # System health metrics
        if 'system_health' in metrics_data:
            health = metrics_data['system_health']
            labels = f'tenant_id="{tenant_id}"'
            
            lines.append(f'# HELP tulia_active_conversations Active conversations')
            lines.append(f'# TYPE tulia_active_conversations gauge')
            lines.append(f'tulia_active_conversations{{{labels}}} {health.get("active_conversations", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_error_rate System error rate')
            lines.append(f'# TYPE tulia_error_rate gauge')
            lines.append(f'tulia_error_rate{{{labels}}} {health.get("error_rate", 0)} {timestamp}')
            
            lines.append(f'# HELP tulia_escalation_rate System escalation rate')
            lines.append(f'# TYPE tulia_escalation_rate gauge')
            lines.append(f'tulia_escalation_rate{{{labels}}} {health.get("escalation_rate", 0)} {timestamp}')
        
        # Performance metrics
        if 'performance_metrics' in metrics_data:
            perf_metrics = metrics_data['performance_metrics']
            for component, metrics in perf_metrics.items():
                labels = f'component="{component}",tenant_id="{tenant_id}"'
                
                lines.append(f'# HELP tulia_component_avg_response_time_seconds Average response time')
                lines.append(f'# TYPE tulia_component_avg_response_time_seconds gauge')
                lines.append(f'tulia_component_avg_response_time_seconds{{{labels}}} {metrics.get("avg_response_time", 0)} {timestamp}')
                
                lines.append(f'# HELP tulia_component_success_rate Component success rate')
                lines.append(f'# TYPE tulia_component_success_rate gauge')
                lines.append(f'tulia_component_success_rate{{{labels}}} {metrics.get("success_rate", 0)} {timestamp}')
        
        return '\n'.join(lines) + '\n'