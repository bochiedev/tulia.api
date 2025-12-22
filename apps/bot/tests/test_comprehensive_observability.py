"""
Comprehensive tests for logging and observability features.

Tests the enhanced logging service, metrics collection, monitoring integration,
and performance tracking capabilities.
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
import pytest

from apps.bot.services.logging_service import (
    enhanced_logging_service, EnhancedLoggingService, RequestContext,
    LogContext, performance_tracking
)
from apps.bot.services.metrics_collector import (
    metrics_collector, MetricsCollector, JourneyMetrics, PaymentMetrics,
    EscalationMetrics, PerformanceMetrics, track_journey_metrics, track_payment_metrics
)
from apps.bot.services.monitoring_integration import (
    monitoring_integration, MonitoringIntegration, Alert, AlertSeverity,
    MetricUpdate, PrometheusAdapter, WebhookAdapter, alert_high_error_rate
)
from apps.bot.services.observability import observability_service, ConversationTracker


class TestEnhancedLoggingService:
    """Test enhanced logging service functionality."""
    
    def test_request_context_creation(self):
        """Test request context creation and management."""
        tenant_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        customer_id = str(uuid.uuid4())
        
        context = RequestContext(
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            customer_id=customer_id
        )
        
        assert context.request_id == request_id
        assert context.tenant_id == tenant_id
        assert context.conversation_id == conversation_id
        assert context.customer_id == customer_id
        assert context.start_time > 0
        
        context_dict = context.to_dict()
        assert 'request_id' in context_dict
        assert 'tenant_id' in context_dict
        assert 'request_duration' in context_dict
    
    def test_request_context_manager(self):
        """Test request context manager functionality."""
        service = EnhancedLoggingService()
        tenant_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        
        with service.request_context(tenant_id, conversation_id) as context:
            assert context.tenant_id == tenant_id
            assert context.conversation_id == conversation_id
            assert service.get_request_context() == context
        
        # Context should be cleared after exiting
        assert service.get_request_context() is None
    
    def test_conversation_start_logging(self):
        """Test conversation start logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.logger, 'info') as mock_log:
            service.log_conversation_start(
                tenant_id="test-tenant",
                conversation_id="test-conv",
                request_id="test-req",
                customer_id="test-customer",
                phone_e164="+254712345678",
                message_text="Hello"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Conversation started" in call_args[0][0]
            assert call_args[1]['extra']['log_context'] == LogContext.CONVERSATION
    
    def test_journey_transition_logging(self):
        """Test journey transition logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.logger, 'info') as mock_log:
            service.log_journey_transition(
                conversation_id="test-conv",
                previous_journey="unknown",
                new_journey="sales",
                reason="intent_classification",
                confidence=0.85
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Journey transition: unknown -> sales" in call_args[0][0]
            assert call_args[1]['extra']['log_context'] == LogContext.JOURNEY
    
    def test_node_execution_logging(self):
        """Test node execution logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.performance_logger, 'log') as mock_log:
            service.log_node_execution(
                node_name="intent_classify",
                conversation_id="test-conv",
                duration=0.25,
                success=True,
                input_data={"message": "test"},
                output_data={"intent": "sales"}
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]['extra']['log_context'] == LogContext.NODE_EXECUTION
            assert call_args[1]['extra']['performance_metrics']['success'] is True
    
    def test_tool_execution_logging(self):
        """Test tool execution logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.performance_logger, 'log') as mock_log:
            service.log_tool_execution(
                tool_name="catalog_search",
                conversation_id="test-conv",
                duration=0.15,
                success=True,
                request_data={"query": "laptops"},
                response_data={"results": []}
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]['extra']['log_context'] == LogContext.TOOL_EXECUTION
            assert call_args[1]['extra']['performance_metrics']['tool_category'] == 'catalog'
    
    def test_payment_event_logging(self):
        """Test payment event logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.business_logger, 'log') as mock_log:
            service.log_payment_event(
                conversation_id="test-conv",
                event_type="initiated",
                payment_method="mpesa_stk",
                amount=5000.0,
                currency="KES"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]['extra']['log_context'] == LogContext.PAYMENT
            assert call_args[1]['extra']['business_metrics']['payment_method'] == 'mpesa_stk'
    
    def test_escalation_event_logging(self):
        """Test escalation event logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.logger, 'warning') as mock_log:
            service.log_escalation_event(
                conversation_id="test-conv",
                escalation_reason="Payment dispute",
                escalation_trigger="payment_dispute",
                ticket_id="TICKET-123"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Escalation triggered: Payment dispute" in call_args[0][0]
            assert call_args[1]['extra']['log_context'] == LogContext.ESCALATION
    
    def test_error_logging(self):
        """Test error logging."""
        service = EnhancedLoggingService()
        
        with patch.object(service.error_logger, 'error') as mock_log:
            service.log_error(
                conversation_id="test-conv",
                error_type="ValidationError",
                error_message="Invalid input",
                component="payment_processor",
                retry_count=2,
                fallback_used=True
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Error in payment_processor: ValidationError" in call_args[0][0]
            assert call_args[1]['extra']['log_context'] == LogContext.ERROR
    
    def test_performance_tracking_context_manager(self):
        """Test performance tracking context manager."""
        conversation_id = str(uuid.uuid4())
        
        with patch.object(enhanced_logging_service, 'log_performance_metrics') as mock_log:
            with performance_tracking("test_operation", conversation_id):
                time.sleep(0.01)  # Small delay
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == "test_operation"
            assert call_args[0][1] > 0  # Duration should be positive
            assert call_args[0][2] is True  # Success


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    def test_journey_metrics_tracking(self):
        """Test journey metrics tracking."""
        collector = MetricsCollector()
        
        # Track journey start
        collector.track_journey_start("sales", "conv-1", "tenant-1")
        assert "sales" in collector.journey_metrics
        assert collector.journey_metrics["sales"].total_started == 1
        
        # Track journey completion
        collector.track_journey_completion("sales", "conv-1", "tenant-1", True, 2.5)
        metrics = collector.journey_metrics["sales"]
        assert metrics.total_completed == 1
        assert metrics.avg_duration == 2.5
        assert metrics.completion_rate > 0
    
    def test_payment_metrics_tracking(self):
        """Test payment metrics tracking."""
        collector = MetricsCollector()
        
        # Track payment initiation
        collector.track_payment_initiation("mpesa_stk", "conv-1", "tenant-1", 5000.0, "KES")
        assert "mpesa_stk" in collector.payment_metrics
        assert collector.payment_metrics["mpesa_stk"].total_initiated == 1
        assert collector.payment_metrics["mpesa_stk"].avg_amount == 5000.0
        
        # Track payment completion
        collector.track_payment_completion("mpesa_stk", "conv-1", "tenant-1", True, 1.2, 5000.0)
        metrics = collector.payment_metrics["mpesa_stk"]
        assert metrics.total_completed == 1
        assert metrics.success_rate == 1.0
        assert metrics.avg_processing_time == 1.2
    
    def test_escalation_metrics_tracking(self):
        """Test escalation metrics tracking."""
        collector = MetricsCollector()
        
        collector.track_escalation(
            "Payment dispute", "payment_dispute", "conv-1", "tenant-1"
        )
        
        assert "Payment dispute" in collector.escalation_metrics
        metrics = collector.escalation_metrics["Payment dispute"]
        assert metrics.total_escalations == 1
        assert metrics.payment_disputes == 1
    
    def test_performance_metrics_tracking(self):
        """Test performance metrics tracking."""
        collector = MetricsCollector()
        
        # Track successful operation
        collector.track_performance("llm_node", "intent_classify", 0.3, True, "conv-1")
        
        component_key = "llm_node_intent_classify"
        assert component_key in collector.performance_metrics
        metrics = collector.performance_metrics[component_key]
        assert metrics.total_operations == 1
        assert metrics.successful_operations == 1
        assert metrics.success_rate == 1.0
        assert len(metrics.response_times) == 1
    
    def test_comprehensive_metrics_summary(self):
        """Test comprehensive metrics summary generation."""
        collector = MetricsCollector()
        
        # Add some test data
        collector.track_journey_start("sales", "conv-1", "tenant-1")
        collector.track_journey_completion("sales", "conv-1", "tenant-1", True, 2.0)
        collector.track_payment_initiation("mpesa_stk", "conv-1", "tenant-1", 1000.0)
        collector.track_payment_completion("mpesa_stk", "conv-1", "tenant-1", True, 1.0)
        collector.track_escalation("Test reason", "test_trigger", "conv-1", "tenant-1")
        collector.track_performance("test_component", "test_op", 0.5, True)
        
        summary = collector.get_comprehensive_metrics_summary()
        
        assert 'timestamp' in summary
        assert 'journey_metrics' in summary
        assert 'payment_metrics' in summary
        assert 'escalation_metrics' in summary
        assert 'performance_metrics' in summary
        
        assert 'sales' in summary['journey_metrics']
        assert 'mpesa_stk' in summary['payment_metrics']
        assert 'Test reason' in summary['escalation_metrics']
    
    def test_journey_metrics_decorator(self):
        """Test journey metrics tracking decorator."""
        @track_journey_metrics("test_journey")
        def test_function(conversation_id="test-conv", tenant_id="test-tenant"):
            time.sleep(0.01)
            return "success"
        
        # Mock the metrics collector
        with patch.object(metrics_collector, 'track_journey_start') as mock_start, \
             patch.object(metrics_collector, 'track_journey_completion') as mock_complete:
            
            result = test_function()
            
            assert result == "success"
            mock_start.assert_called_once_with("test_journey", "test-conv", "test-tenant")
            mock_complete.assert_called_once()
            # Check that completion was called with success=True
            assert mock_complete.call_args[0][3] is True  # success parameter
    
    def test_payment_metrics_decorator(self):
        """Test payment metrics tracking decorator."""
        @track_payment_metrics("test_payment")
        def test_function(conversation_id="test-conv", tenant_id="test-tenant", amount=100.0):
            time.sleep(0.01)
            return "success"
        
        with patch.object(metrics_collector, 'track_payment_initiation') as mock_init, \
             patch.object(metrics_collector, 'track_payment_completion') as mock_complete:
            
            result = test_function()
            
            assert result == "success"
            mock_init.assert_called_once_with("test_payment", "test-conv", "test-tenant", 100.0)
            mock_complete.assert_called_once()
            assert mock_complete.call_args[0][3] is True  # success parameter


class TestMonitoringIntegration:
    """Test monitoring integration functionality."""
    
    def test_alert_creation(self):
        """Test alert creation and serialization."""
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            category="test",
            timestamp=datetime.now(timezone.utc),
            metadata={"key": "value"}
        )
        
        alert_dict = alert.to_dict()
        assert alert_dict['title'] == "Test Alert"
        assert alert_dict['severity'] == "warning"
        assert alert_dict['category'] == "test"
        assert 'timestamp' in alert_dict
    
    def test_metric_update_creation(self):
        """Test metric update creation and serialization."""
        metric = MetricUpdate(
            metric_name="test_metric",
            metric_type="counter",
            value=1.0,
            labels={"component": "test"},
            timestamp=datetime.now(timezone.utc)
        )
        
        metric_dict = metric.to_dict()
        assert metric_dict['metric_name'] == "test_metric"
        assert metric_dict['metric_type'] == "counter"
        assert metric_dict['value'] == 1.0
        assert metric_dict['labels']['component'] == "test"
    
    def test_webhook_adapter(self):
        """Test webhook adapter functionality."""
        adapter = WebhookAdapter("http://test.example.com/webhook")
        
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.INFO,
            category="test",
            timestamp=datetime.now(timezone.utc),
            metadata={}
        )
        
        # Mock requests
        with patch('apps.bot.services.monitoring_integration.requests') as mock_requests:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_requests.post.return_value = mock_response
            
            # Test sending alert
            result = asyncio.run(adapter.send_alert(alert))
            assert result is True
            mock_requests.post.assert_called_once()
    
    def test_monitoring_integration_service(self):
        """Test monitoring integration service."""
        integration = MonitoringIntegration()
        
        # Test adding adapter
        mock_adapter = Mock()
        integration.add_adapter("test", mock_adapter)
        assert "test" in integration.adapters
        
        # Test removing adapter
        integration.remove_adapter("test")
        assert "test" not in integration.adapters
    
    @pytest.mark.asyncio
    async def test_alert_sending(self):
        """Test alert sending to adapters."""
        integration = MonitoringIntegration()
        
        # Add mock adapter
        mock_adapter = AsyncMock()
        mock_adapter.send_alert.return_value = True
        integration.add_adapter("test", mock_adapter)
        
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.ERROR,
            category="test",
            timestamp=datetime.now(timezone.utc),
            metadata={}
        )
        
        await integration.send_alert(alert)
        mock_adapter.send_alert.assert_called_once_with(alert)
    
    def test_default_alert_rules(self):
        """Test default alert rules."""
        integration = MonitoringIntegration()
        
        # Test high error rate rule
        test_metrics = {'error_rate': 0.15}  # Above 10% threshold
        rule = integration.alert_rules['high_error_rate']
        alert = rule(test_metrics)
        
        assert alert is not None
        assert alert.severity == AlertSeverity.ERROR
        assert "High Error Rate" in alert.title
        
        # Test low error rate (should not alert)
        test_metrics = {'error_rate': 0.05}  # Below threshold
        alert = rule(test_metrics)
        assert alert is None
    
    @pytest.mark.asyncio
    async def test_convenience_alert_functions(self):
        """Test convenience alert functions."""
        with patch.object(monitoring_integration, 'send_alert') as mock_send:
            # Test high error rate alert
            await alert_high_error_rate(0.15, 0.10)
            mock_send.assert_called_once()
            
            # Check alert properties
            alert = mock_send.call_args[0][0]
            assert alert.severity == AlertSeverity.ERROR
            assert "High Error Rate" in alert.title


class TestObservabilityIntegration:
    """Test integration between observability components."""
    
    def test_conversation_tracker_integration(self):
        """Test conversation tracker with metrics collection."""
        tenant_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        customer_id = str(uuid.uuid4())
        
        with ConversationTracker(tenant_id, conversation_id, request_id, customer_id) as tracker:
            assert tracker.tenant_id == tenant_id
            assert tracker.conversation_id == conversation_id
            
            # Simulate some tracking
            observability_service.track_journey_start(conversation_id, "test_journey")
            observability_service.track_node_execution(conversation_id, "test_node", 0.1, True)
            observability_service.track_business_event(conversation_id, "test_event")
        
        # Metrics should be cleaned up after context exit
        final_metrics = observability_service.get_conversation_metrics(conversation_id)
        assert final_metrics is None  # Should be cleaned up
    
    def test_enhanced_logging_with_metrics(self):
        """Test enhanced logging integration with metrics collection."""
        conversation_id = str(uuid.uuid4())
        
        # Mock metrics collector
        with patch.object(metrics_collector, 'track_performance') as mock_track:
            enhanced_logging_service.log_performance_metrics(
                "test_operation", 0.5, True, conversation_id=conversation_id
            )
            
            # Should not directly call metrics collector (different responsibilities)
            # Enhanced logging focuses on structured logging, metrics collector on aggregation
            mock_track.assert_not_called()
    
    def test_system_health_monitoring(self):
        """Test system health monitoring integration."""
        # Get system health summary
        health_summary = observability_service.get_system_health_summary()
        
        assert isinstance(health_summary, dict)
        assert 'timestamp' in health_summary
        assert 'active_conversations' in health_summary
        assert 'error_rate' in health_summary
        assert 'escalation_rate' in health_summary
    
    @pytest.mark.asyncio
    async def test_end_to_end_observability_flow(self):
        """Test complete observability flow from logging to monitoring."""
        tenant_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        
        # Set up monitoring integration with mock adapter
        mock_adapter = AsyncMock()
        mock_adapter.send_alert.return_value = True
        mock_adapter.send_metric.return_value = True
        monitoring_integration.add_adapter("test", mock_adapter)
        
        try:
            # Start conversation tracking
            with enhanced_logging_service.request_context(
                tenant_id, conversation_id, request_id
            ):
                # Log conversation start
                enhanced_logging_service.log_conversation_start(
                    tenant_id, conversation_id, request_id
                )
                
                # Track journey metrics
                metrics_collector.track_journey_start("sales", conversation_id, tenant_id)
                
                # Simulate node execution
                enhanced_logging_service.log_node_execution(
                    "intent_classify", conversation_id, 0.2, True
                )
                
                # Track performance
                metrics_collector.track_performance("llm_node", "intent_classify", 0.2, True)
                
                # Complete journey
                metrics_collector.track_journey_completion("sales", conversation_id, tenant_id, True, 2.0)
            
            # Get comprehensive metrics
            metrics_summary = metrics_collector.get_comprehensive_metrics_summary()
            assert 'journey_metrics' in metrics_summary
            assert 'sales' in metrics_summary['journey_metrics']
            
            # Test alert rule checking
            await monitoring_integration.check_alert_rules()
            
        finally:
            # Clean up
            monitoring_integration.remove_adapter("test")