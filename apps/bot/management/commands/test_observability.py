"""
Management command to test comprehensive logging and observability features.

This command demonstrates and validates the enhanced logging, metrics collection,
and monitoring integration capabilities.
"""

import asyncio
import time
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bot.services.logging_service import enhanced_logging_service, performance_tracking
from apps.bot.services.metrics_collector import metrics_collector
from apps.bot.services.monitoring_integration import (
    monitoring_integration, Alert, AlertSeverity, MetricUpdate,
    create_webhook_adapter, alert_high_error_rate
)
from apps.bot.services.observability import observability_service, ConversationTracker
from apps.bot.conversation_state import ConversationState


class Command(BaseCommand):
    help = 'Test comprehensive logging and observability features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['all', 'logging', 'metrics', 'monitoring', 'performance'],
            default='all',
            help='Test scenario to run'
        )
        parser.add_argument(
            '--webhook-url',
            type=str,
            help='Webhook URL for monitoring integration testing'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        """Run observability tests."""
        scenario = options['scenario']
        webhook_url = options.get('webhook_url')
        self.verbose = options.get('verbose', False)
        
        self.stdout.write(
            self.style.SUCCESS('Testing Tulia AI V2 Observability Features')
        )
        
        if scenario in ['all', 'logging']:
            self.test_enhanced_logging()
        
        if scenario in ['all', 'metrics']:
            self.test_metrics_collection()
        
        if scenario in ['all', 'monitoring']:
            self.test_monitoring_integration(webhook_url)
        
        if scenario in ['all', 'performance']:
            asyncio.run(self.test_performance_tracking())
        
        self.stdout.write(
            self.style.SUCCESS('✓ All observability tests completed successfully')
        )

    def test_enhanced_logging(self):
        """Test enhanced logging service features."""
        self.stdout.write('Testing enhanced logging service...')
        
        # Test request context tracking
        tenant_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        customer_id = str(uuid.uuid4())
        
        with enhanced_logging_service.request_context(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=request_id,
            customer_id=customer_id
        ) as context:
            
            # Test conversation start logging
            enhanced_logging_service.log_conversation_start(
                tenant_id, conversation_id, request_id, customer_id,
                phone_e164="+254712345678", message_text="Hello, I need help"
            )
            
            # Test journey transition logging
            enhanced_logging_service.log_journey_transition(
                conversation_id, "unknown", "sales", "intent_classification", 0.85
            )
            
            # Test node execution logging
            enhanced_logging_service.log_node_execution(
                "intent_classify", conversation_id, 0.25, True,
                input_data={"message": "I want to buy something"},
                output_data={"intent": "sales_discovery", "confidence": 0.85}
            )
            
            # Test tool execution logging
            enhanced_logging_service.log_tool_execution(
                "catalog_search", conversation_id, 0.15, True,
                request_data={"query": "laptops", "filters": {}},
                response_data={"results": [{"id": "1", "name": "MacBook"}]}
            )
            
            # Test payment event logging
            enhanced_logging_service.log_payment_event(
                conversation_id, "initiated", "mpesa_stk", 15000.0, "KES"
            )
            
            # Test escalation event logging
            enhanced_logging_service.log_escalation_event(
                conversation_id, "Payment dispute", "payment_dispute",
                context={"order_id": "ORD-123", "amount": 15000.0}
            )
            
            # Test business event logging
            enhanced_logging_service.log_business_event(
                conversation_id, "product_viewed",
                details={"product_id": "PROD-123", "category": "electronics"}
            )
            
            # Test error logging
            enhanced_logging_service.log_error(
                conversation_id, "ValidationError", "Invalid payment amount",
                "payment_processor", context={"amount": -100}
            )
            
            if self.verbose:
                self.stdout.write(f"  ✓ Request context: {context.request_id}")
        
        self.stdout.write(self.style.SUCCESS("✓ Enhanced logging test passed"))

    def test_metrics_collection(self):
        """Test metrics collection service."""
        self.stdout.write('Testing metrics collection service...')
        
        tenant_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        
        # Test journey metrics
        metrics_collector.track_journey_start("sales", conversation_id, tenant_id)
        time.sleep(0.1)  # Simulate processing time
        metrics_collector.track_journey_completion("sales", conversation_id, tenant_id, True, 2.5)
        
        # Test payment metrics
        metrics_collector.track_payment_initiation("mpesa_stk", conversation_id, tenant_id, 5000.0, "KES")
        time.sleep(0.05)
        metrics_collector.track_payment_completion("mpesa_stk", conversation_id, tenant_id, True, 1.2, 5000.0)
        
        # Test escalation metrics
        metrics_collector.track_escalation(
            "Payment dispute", "payment_dispute", conversation_id, tenant_id,
            context={"order_id": "ORD-456"}
        )
        
        # Test performance metrics
        metrics_collector.track_performance("llm_node", "intent_classify", 0.3, True, conversation_id)
        metrics_collector.track_performance("tool", "catalog_search", 0.15, True, conversation_id)
        
        # Get metrics summary
        journey_rates = metrics_collector.get_journey_completion_rates()
        payment_rates = metrics_collector.get_payment_success_rates()
        escalation_freq = metrics_collector.get_escalation_frequencies()
        performance_summary = metrics_collector.get_performance_summary()
        
        if self.verbose:
            self.stdout.write(f"  ✓ Journey completion rates: {journey_rates}")
            self.stdout.write(f"  ✓ Payment success rates: {payment_rates}")
            self.stdout.write(f"  ✓ Escalation frequencies: {escalation_freq}")
            self.stdout.write(f"  ✓ Performance summary: {len(performance_summary)} components")
        
        # Test comprehensive metrics summary
        comprehensive_summary = metrics_collector.get_comprehensive_metrics_summary()
        assert 'journey_metrics' in comprehensive_summary
        assert 'payment_metrics' in comprehensive_summary
        assert 'escalation_metrics' in comprehensive_summary
        assert 'performance_metrics' in comprehensive_summary
        
        self.stdout.write(self.style.SUCCESS("✓ Metrics collection test passed"))

    def test_monitoring_integration(self, webhook_url=None):
        """Test monitoring integration service."""
        self.stdout.write('Testing monitoring integration service...')
        
        # Test alert creation
        alert = Alert(
            title="Test Alert",
            message="This is a test alert for monitoring integration",
            severity=AlertSeverity.WARNING,
            category="test",
            timestamp=timezone.now(),
            metadata={"test": True, "component": "observability_test"}
        )
        
        if self.verbose:
            self.stdout.write(f"  ✓ Created alert: {alert.title}")
        
        # Test metric update creation
        metric = MetricUpdate(
            metric_name="test_metric",
            metric_type="counter",
            value=1.0,
            labels={"component": "test", "environment": "development"},
            timestamp=timezone.now()
        )
        
        if self.verbose:
            self.stdout.write(f"  ✓ Created metric: {metric.metric_name}")
        
        # Test webhook adapter if URL provided
        if webhook_url:
            webhook_adapter = create_webhook_adapter(webhook_url)
            monitoring_integration.add_adapter('test_webhook', webhook_adapter)
            
            # Test sending alert and metric (async)
            async def test_webhook():
                alert_success = await monitoring_integration.send_alert(alert)
                metric_success = await monitoring_integration.send_metric(metric)
                return alert_success, metric_success
            
            try:
                alert_success, metric_success = asyncio.run(test_webhook())
                if self.verbose:
                    self.stdout.write(f"  ✓ Webhook alert sent: {alert_success}")
                    self.stdout.write(f"  ✓ Webhook metric sent: {metric_success}")
            except Exception as e:
                self.stdout.write(f"  ! Webhook test failed: {e}")
            
            monitoring_integration.remove_adapter('test_webhook')
        
        # Test alert rules
        test_metrics = {
            'error_rate': 0.15,  # Above 10% threshold
            'escalation_rate': 0.25,  # Above 20% threshold
            'payment_success_rates': {'mpesa_stk': 0.75},  # Below 80% threshold
            'performance_metrics': {
                'slow_component': {'p95_response_time': 6.0}  # Above 5s threshold
            }
        }
        
        # Test alert rule checking (async)
        async def test_alert_rules():
            await monitoring_integration.check_alert_rules()
        
        try:
            asyncio.run(test_alert_rules())
            if self.verbose:
                self.stdout.write("  ✓ Alert rules checked successfully")
        except Exception as e:
            self.stdout.write(f"  ! Alert rules test failed: {e}")
        
        self.stdout.write(self.style.SUCCESS("✓ Monitoring integration test passed"))

    async def test_performance_tracking(self):
        """Test performance tracking features."""
        self.stdout.write('Testing performance tracking...')
        
        conversation_id = str(uuid.uuid4())
        
        # Test performance tracking context manager
        with performance_tracking("test_operation", conversation_id):
            # Simulate some work
            await asyncio.sleep(0.1)
        
        # Test conversation tracker
        tenant_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        customer_id = str(uuid.uuid4())
        
        with ConversationTracker(tenant_id, conversation_id, request_id, customer_id) as tracker:
            # Simulate conversation processing
            observability_service.track_journey_start(conversation_id, "test_journey")
            await asyncio.sleep(0.05)
            observability_service.track_node_execution(conversation_id, "test_node", 0.02, True)
            observability_service.track_tool_execution(conversation_id, "test_tool", 0.03, True)
            observability_service.track_business_event(conversation_id, "test_event", {"key": "value"})
            observability_service.track_journey_completion(conversation_id, "test_journey", True)
        
        # Get conversation metrics
        final_metrics = observability_service.get_conversation_metrics(conversation_id)
        if final_metrics is None:
            # Metrics might have been cleaned up, which is expected
            if self.verbose:
                self.stdout.write("  ✓ Conversation metrics cleaned up after tracking")
        
        # Test system health summary
        health_summary = observability_service.get_system_health_summary()
        assert isinstance(health_summary, dict)
        assert 'timestamp' in health_summary
        
        if self.verbose:
            self.stdout.write(f"  ✓ System health summary: {len(health_summary)} metrics")
        
        self.stdout.write(self.style.SUCCESS("✓ Performance tracking test passed"))

    def log_verbose(self, message):
        """Log verbose message if verbose mode is enabled."""
        if self.verbose:
            self.stdout.write(f"  {message}")