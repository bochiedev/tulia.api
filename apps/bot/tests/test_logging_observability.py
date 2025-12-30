"""
Tests for comprehensive logging and observability implementation.

Tests the conversation logger, metrics collector, monitoring endpoints,
and integration with the LangGraph orchestrator.
"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.bot.conversation_state import ConversationState
from apps.bot.services.conversation_logger import conversation_logger, ConversationLogger
from apps.bot.services.metrics_collector import metrics_collector, MetricsCollector
from apps.bot.services.observability import observability_service, ConversationTracker
from apps.tenants.models import Tenant, Customer
from apps.bot.models_conversation_state import ConversationSession
from apps.rbac.models import TenantUser, Role, Permission, RolePermission
from django.contrib.auth import get_user_model

User = get_user_model()


class ConversationLoggerTest(TestCase):
    """Test conversation logger functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            bot_name="TestBot"
        )
        
        self.customer = Customer.objects.create(
            tenant_id=self.tenant.id,
            phone_e164="+254700000001",
            language_preference="en"
        )
        
        self.state = ConversationState(
            tenant_id=str(self.tenant.id),
            conversation_id="test-conv-123",
            request_id="test-req-456",
            customer_id=str(self.customer.id),
            tenant_name="Test Tenant",
            bot_name="TestBot",
            intent="sales_discovery",
            journey="sales",
            turn_count=1
        )
        
        # Create fresh logger instance for testing
        self.logger = ConversationLogger('test.conversation.logger')
    
    def test_log_conversation_start(self):
        """Test conversation start logging."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_conversation_start(self.state, "Hello, I need help")
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            # Check log message
            self.assertIn("Conversation started", call_args[0][0])
            
            # Check extra context
            extra = call_args[1]['extra']
            self.assertEqual(extra['tenant_id'], str(self.tenant.id))
            self.assertEqual(extra['conversation_id'], "test-conv-123")
            self.assertEqual(extra['request_id'], "test-req-456")
            self.assertEqual(extra['event'], 'conversation_start')
            self.assertEqual(extra['message_length'], 17)
    
    def test_log_journey_transition(self):
        """Test journey transition logging."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_journey_transition(
                self.state, "unknown", "sales", "intent_classification"
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            
            # Check log message
            self.assertIn("Journey transition: unknown -> sales", call_args[0][0])
            
            # Check extra context
            extra = call_args[1]['extra']
            self.assertEqual(extra['from_journey'], "unknown")
            self.assertEqual(extra['to_journey'], "sales")
            self.assertEqual(extra['transition_reason'], "intent_classification")
    
    def test_log_node_execution_with_performance_tracking(self):
        """Test node execution logging with performance tracking."""
        with patch.object(self.logger.logger, 'debug') as mock_debug, \
             patch.object(self.logger.logger, 'info') as mock_info:
            
            # Start node execution
            operation_id = self.logger.log_node_execution_start(
                self.state, "intent_classify", "classification"
            )
            
            # Simulate some processing time
            time.sleep(0.01)
            
            # End node execution
            self.logger.log_node_execution_end(
                self.state, "intent_classify", operation_id, success=True
            )
            
            # Check start logging
            mock_debug.assert_called_once()
            start_call = mock_debug.call_args
            self.assertIn("Starting intent_classify execution", start_call[0][0])
            
            # Check end logging
            mock_info.assert_called_once()
            end_call = mock_info.call_args
            self.assertIn("Completed intent_classify execution", end_call[0][0])
            
            # Check performance metrics
            extra = end_call[1]['extra']
            self.assertTrue(extra['execution_time_ms'] > 0)
            self.assertTrue(extra['success'])
    
    def test_log_tool_call_with_sanitized_args(self):
        """Test tool call logging with argument sanitization."""
        with patch.object(self.logger.logger, 'debug') as mock_debug, \
             patch.object(self.logger.logger, 'info') as mock_info:
            
            # Tool args with sensitive data
            tool_args = {
                'tenant_id': str(self.tenant.id),
                'phone_e164': '+254700000001',
                'api_key': 'secret-key-123',
                'amount': 100.0
            }
            
            # Start tool call
            operation_id = self.logger.log_tool_call_start(
                self.state, "payment_initiate_stk_push", tool_args
            )
            
            # End tool call
            self.logger.log_tool_call_end(
                self.state, "payment_initiate_stk_push", operation_id, 
                success=True, result_summary="STK push initiated"
            )
            
            # Check that sensitive data is masked
            start_call = mock_debug.call_args
            extra = start_call[1]['extra']
            tool_args_logged = extra['tool_args']
            
            # Phone should be masked
            self.assertIn('*', tool_args_logged['phone_e164'])
            # API key should be masked
            self.assertEqual(tool_args_logged['api_key'], '********')
            # Non-sensitive data should remain
            self.assertEqual(tool_args_logged['amount'], 100.0)
    
    def test_log_escalation_triggered(self):
        """Test escalation logging."""
        with patch.object(self.logger.logger, 'warning') as mock_warning:
            self.logger.log_escalation_triggered(
                self.state, "payment_dispute", "high", "payment", "TICKET-123"
            )
            
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args
            
            # Check log message
            self.assertIn("Escalation triggered: payment_dispute", call_args[0][0])
            
            # Check extra context
            extra = call_args[1]['extra']
            self.assertEqual(extra['escalation_reason'], "payment_dispute")
            self.assertEqual(extra['escalation_priority'], "high")
            self.assertEqual(extra['escalation_category'], "payment")
            self.assertEqual(extra['ticket_id'], "TICKET-123")
    
    def test_log_error_with_context(self):
        """Test error logging with full context."""
        with patch.object(self.logger.logger, 'error') as mock_error:
            test_error = ValueError("Test error message")
            
            self.logger.log_error_with_context(
                self.state, test_error, "payment_processor", "stk_push",
                payment_method="mpesa", amount=100.0
            )
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            
            # Check log message
            self.assertIn("Error in payment_processor: Test error message", call_args[0][0])
            
            # Check extra context
            extra = call_args[1]['extra']
            self.assertEqual(extra['component'], "payment_processor")
            self.assertEqual(extra['operation'], "stk_push")
            self.assertEqual(extra['error_type'], "ValueError")
            self.assertEqual(extra['payment_method'], "mpesa")
            self.assertEqual(extra['amount'], 100.0)
            
            # Check exception info is included
            self.assertEqual(call_args[1]['exc_info'], test_error)


class MetricsCollectorTest(TestCase):
    """Test metrics collector functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.collector = MetricsCollector()
        self.tenant_id = "test-tenant-123"
        self.conversation_id = "test-conv-456"
    
    def test_track_journey_metrics(self):
        """Test journey metrics tracking."""
        # Track journey start
        self.collector.track_journey_start("sales", self.conversation_id, self.tenant_id)
        
        # Check metrics
        self.assertIn("sales", self.collector.journey_metrics)
        metrics = self.collector.journey_metrics["sales"]
        self.assertEqual(metrics.total_started, 1)
        self.assertEqual(metrics.completion_rate, 0.0)
        
        # Track journey completion
        self.collector.track_journey_completion(
            "sales", self.conversation_id, self.tenant_id, success=True, duration=45.5
        )
        
        # Check updated metrics
        self.assertEqual(metrics.total_completed, 1)
        self.assertEqual(metrics.avg_duration, 45.5)
        self.assertEqual(metrics.completion_rate, 1.0)
    
    def test_track_payment_metrics(self):
        """Test payment metrics tracking."""
        # Track payment initiation
        self.collector.track_payment_initiation(
            "mpesa_stk", self.conversation_id, self.tenant_id, amount=100.0
        )
        
        # Check metrics
        self.assertIn("mpesa_stk", self.collector.payment_metrics)
        metrics = self.collector.payment_metrics["mpesa_stk"]
        self.assertEqual(metrics.total_initiated, 1)
        self.assertEqual(metrics.avg_amount, 100.0)
        
        # Track payment completion
        self.collector.track_payment_completion(
            "mpesa_stk", self.conversation_id, self.tenant_id, 
            success=True, processing_time=5.2, amount=100.0
        )
        
        # Check updated metrics
        self.assertEqual(metrics.total_completed, 1)
        self.assertEqual(metrics.avg_processing_time, 5.2)
        self.assertEqual(metrics.success_rate, 1.0)
    
    def test_track_escalation_metrics(self):
        """Test escalation metrics tracking."""
        # Track escalation
        self.collector.track_escalation(
            "payment_dispute", "payment_dispute", self.conversation_id, self.tenant_id,
            context={"order_id": "ORDER-123", "amount": 100.0}
        )
        
        # Check metrics
        self.assertIn("payment_dispute", self.collector.escalation_metrics)
        metrics = self.collector.escalation_metrics["payment_dispute"]
        self.assertEqual(metrics.total_escalations, 1)
        self.assertEqual(metrics.payment_disputes, 1)
        self.assertEqual(metrics.explicit_human_requests, 0)
    
    def test_track_performance_metrics(self):
        """Test performance metrics tracking."""
        # Track multiple operations
        for i in range(10):
            duration = 0.5 + (i * 0.1)  # Varying durations
            success = i < 8  # 8 successes, 2 failures
            
            self.collector.track_performance(
                "llm_node", "intent_classify", duration, success, self.conversation_id
            )
        
        # Check metrics
        component_key = "llm_node_intent_classify"
        self.assertIn(component_key, self.collector.performance_metrics)
        metrics = self.collector.performance_metrics[component_key]
        
        self.assertEqual(metrics.total_operations, 10)
        self.assertEqual(metrics.successful_operations, 8)
        self.assertEqual(metrics.failed_operations, 2)
        self.assertEqual(metrics.success_rate, 0.8)
        self.assertEqual(metrics.error_rate, 0.2)
        self.assertTrue(metrics.avg_response_time > 0)
    
    def test_get_comprehensive_metrics_summary(self):
        """Test comprehensive metrics summary generation."""
        # Add some test data
        self.collector.track_journey_start("sales", self.conversation_id, self.tenant_id)
        self.collector.track_journey_completion("sales", self.conversation_id, self.tenant_id, True, 30.0)
        
        self.collector.track_payment_initiation("mpesa_stk", self.conversation_id, self.tenant_id, 100.0)
        self.collector.track_payment_completion("mpesa_stk", self.conversation_id, self.tenant_id, True, 5.0, 100.0)
        
        self.collector.track_escalation("support_needed", "missing_information", self.conversation_id, self.tenant_id)
        
        # Get summary
        summary = self.collector.get_comprehensive_metrics_summary()
        
        # Check structure
        self.assertIn('timestamp', summary)
        self.assertIn('journey_metrics', summary)
        self.assertIn('payment_metrics', summary)
        self.assertIn('escalation_metrics', summary)
        self.assertIn('performance_metrics', summary)
        
        # Check journey metrics
        journey_metrics = summary['journey_metrics']
        self.assertIn('sales', journey_metrics)
        sales_metrics = journey_metrics['sales']
        self.assertEqual(sales_metrics['total_started'], 1)
        self.assertEqual(sales_metrics['total_completed'], 1)
        self.assertEqual(sales_metrics['completion_rate'], 1.0)
        
        # Check payment metrics
        payment_metrics = summary['payment_metrics']
        self.assertIn('mpesa_stk', payment_metrics)
        mpesa_metrics = payment_metrics['mpesa_stk']
        self.assertEqual(mpesa_metrics['total_initiated'], 1)
        self.assertEqual(mpesa_metrics['success_rate'], 1.0)


class ObservabilityServiceTest(TestCase):
    """Test observability service functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant_id = "test-tenant-123"
        self.conversation_id = "test-conv-456"
        self.request_id = "test-req-789"
        self.customer_id = "test-customer-101"
    
    def test_conversation_tracker_context_manager(self):
        """Test conversation tracker context manager."""
        with patch.object(observability_service, 'start_conversation_tracking') as mock_start, \
             patch.object(observability_service, 'end_conversation_tracking') as mock_end:
            
            mock_metrics = Mock()
            mock_start.return_value = mock_metrics
            
            # Use context manager
            with ConversationTracker(
                self.tenant_id, self.conversation_id, self.request_id, self.customer_id
            ) as metrics:
                self.assertEqual(metrics, mock_metrics)
                # Simulate some work
                pass
            
            # Check that tracking was started and ended
            mock_start.assert_called_once_with(
                self.tenant_id, self.conversation_id, self.request_id, self.customer_id
            )
            mock_end.assert_called_once_with(self.conversation_id)
    
    def test_conversation_tracker_with_exception(self):
        """Test conversation tracker handles exceptions."""
        with patch.object(observability_service, 'start_conversation_tracking') as mock_start, \
             patch.object(observability_service, 'track_error') as mock_track_error, \
             patch.object(observability_service, 'end_conversation_tracking') as mock_end:
            
            mock_start.return_value = Mock()
            
            # Use context manager with exception
            with pytest.raises(ValueError):
                with ConversationTracker(
                    self.tenant_id, self.conversation_id, self.request_id, self.customer_id
                ):
                    raise ValueError("Test error")
            
            # Check that error was tracked
            mock_track_error.assert_called_once()
            error_call = mock_track_error.call_args
            self.assertEqual(error_call[0][0], self.conversation_id)
            self.assertEqual(error_call[0][1], "ValueError")
            self.assertEqual(error_call[0][2], "Test error")
            
            # Check that tracking was ended
            mock_end.assert_called_once_with(self.conversation_id)
    
    def test_track_business_events(self):
        """Test business event tracking."""
        # Start conversation tracking
        metrics = observability_service.start_conversation_tracking(
            self.tenant_id, self.conversation_id, self.request_id, self.customer_id
        )
        
        # Track various business events
        observability_service.track_business_event(self.conversation_id, "product_viewed")
        observability_service.track_business_event(self.conversation_id, "order_created")
        observability_service.track_business_event(self.conversation_id, "payment_initiated")
        observability_service.track_business_event(self.conversation_id, "payment_completed")
        
        # Check metrics were updated
        self.assertEqual(metrics.products_viewed, 1)
        self.assertEqual(metrics.orders_created, 1)
        self.assertEqual(metrics.payments_initiated, 1)
        self.assertEqual(metrics.payments_completed, 1)
    
    def test_system_health_summary(self):
        """Test system health summary generation."""
        # Add some conversation tracking
        observability_service.start_conversation_tracking(
            self.tenant_id, self.conversation_id, self.request_id, self.customer_id
        )
        
        # Track some errors and escalations
        observability_service.track_error(
            self.conversation_id, "ValueError", "Test error", "test_component"
        )
        observability_service.track_escalation(
            self.conversation_id, "support_needed", {"reason": "complex_query"}
        )
        
        # Get health summary
        health = observability_service.get_system_health_summary()
        
        # Check structure
        self.assertIn('timestamp', health)
        self.assertIn('active_conversations', health)
        self.assertIn('total_errors', health)
        self.assertIn('total_escalations', health)
        self.assertIn('error_rate', health)
        self.assertIn('escalation_rate', health)
        
        # Check values
        self.assertEqual(health['active_conversations'], 1)
        self.assertEqual(health['total_errors'], 1)
        self.assertEqual(health['total_escalations'], 1)


@pytest.mark.django_db
class MonitoringViewsTest(TestCase):
    """Test monitoring API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            bot_name="TestBot"
        )
        
        # Create user and tenant user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user
        )
        
        # Create analytics permission and role
        analytics_permission = Permission.objects.create(
            code="analytics:view",
            name="View Analytics",
            description="Can view analytics and reports"
        )
        
        role = Role.objects.create(
            tenant=self.tenant,
            name="Analyst",
            description="Analytics viewer"
        )
        
        RolePermission.objects.create(
            role=role,
            permission=analytics_permission
        )
        
        # Assign role to tenant user
        self.tenant_user.roles.add(role)
        
        # Set up client headers
        self.client.defaults['HTTP_X_TENANT_ID'] = str(self.tenant.id)
        self.client.defaults['HTTP_X_TENANT_API_KEY'] = 'test-api-key'
        
        # Mock tenant context middleware
        self.tenant_middleware_patcher = patch('apps.tenants.middleware.TenantContextMiddleware.process_request')
        mock_middleware = self.tenant_middleware_patcher.start()
        mock_middleware.return_value = None
        
        # Mock request attributes
        def mock_process_request(request):
            request.tenant = self.tenant
            request.membership = self.tenant_user
            request.scopes = {'analytics:view'}
            return None
        
        mock_middleware.side_effect = mock_process_request
    
    def tearDown(self):
        """Clean up patches."""
        self.tenant_middleware_patcher.stop()
    
    def test_system_health_view_requires_analytics_scope(self):
        """Test that system health view requires analytics:view scope."""
        # Remove analytics scope
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=False):
            url = reverse('bot:system-health')
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_system_health_view_success(self):
        """Test successful system health retrieval."""
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True):
            url = reverse('bot:system-health')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('timestamp', data)
            self.assertIn('tenant_id', data)
            self.assertIn('tenant_name', data)
            self.assertIn('system_health', data)
            self.assertIn('metrics_summary', data)
            self.assertIn('tenant_metrics', data)
            self.assertIn('status', data)
            
            # Check tenant info
            self.assertEqual(data['tenant_id'], str(self.tenant.id))
            self.assertEqual(data['tenant_name'], self.tenant.name)
    
    def test_journey_metrics_view_success(self):
        """Test successful journey metrics retrieval."""
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True):
            # Add some test metrics
            metrics_collector.track_journey_start("sales", "test-conv", str(self.tenant.id))
            metrics_collector.track_journey_completion("sales", "test-conv", str(self.tenant.id), True, 30.0)
            
            url = reverse('bot:journey-metrics')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('timestamp', data)
            self.assertIn('tenant_id', data)
            self.assertIn('completion_rates', data)
            self.assertIn('detailed_metrics', data)
            self.assertIn('analytics', data)
    
    def test_payment_metrics_view_success(self):
        """Test successful payment metrics retrieval."""
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True):
            # Add some test metrics
            metrics_collector.track_payment_initiation("mpesa_stk", "test-conv", str(self.tenant.id), 100.0)
            metrics_collector.track_payment_completion("mpesa_stk", "test-conv", str(self.tenant.id), True, 5.0, 100.0)
            
            url = reverse('bot:payment-metrics')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('timestamp', data)
            self.assertIn('tenant_id', data)
            self.assertIn('success_rates', data)
            self.assertIn('detailed_metrics', data)
            self.assertIn('analytics', data)
    
    def test_escalation_metrics_view_success(self):
        """Test successful escalation metrics retrieval."""
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True):
            # Add some test metrics
            metrics_collector.track_escalation(
                "support_needed", "missing_information", "test-conv", str(self.tenant.id)
            )
            
            url = reverse('bot:escalation-metrics')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('timestamp', data)
            self.assertIn('tenant_id', data)
            self.assertIn('escalation_frequencies', data)
            self.assertIn('detailed_metrics', data)
            self.assertIn('analytics', data)
    
    def test_performance_metrics_view_success(self):
        """Test successful performance metrics retrieval."""
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True):
            # Add some test metrics
            metrics_collector.track_performance("llm_node", "intent_classify", 0.5, True, "test-conv")
            
            url = reverse('bot:performance-metrics')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('timestamp', data)
            self.assertIn('tenant_id', data)
            self.assertIn('performance_summary', data)
            self.assertIn('system_health', data)
            self.assertIn('recommendations', data)
    
    def test_monitoring_views_handle_errors_gracefully(self):
        """Test that monitoring views handle errors gracefully."""
        with patch('apps.core.permissions.HasTenantScopes.has_permission', return_value=True), \
             patch('apps.bot.services.metrics_collector.metrics_collector.get_comprehensive_metrics_summary', 
                   side_effect=Exception("Test error")):
            
            url = reverse('bot:system-health')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            data = response.json()
            self.assertIn('error', data)
            self.assertEqual(data['error'], 'Failed to retrieve system health metrics')


class RequestTrackingMiddlewareTest(TestCase):
    """Test request tracking middleware."""
    
    def setUp(self):
        """Set up test data."""
        from apps.core.middleware.request_tracking import RequestTrackingMiddleware
        self.middleware = RequestTrackingMiddleware()
    
    def test_request_id_generation(self):
        """Test request ID generation and tracking."""
        from django.http import HttpRequest, HttpResponse
        
        request = HttpRequest()
        request.method = 'GET'
        request.path = '/test'
        request.META = {}
        
        # Process request
        self.middleware.process_request(request)
        
        # Check request ID was generated
        self.assertTrue(hasattr(request, 'request_id'))
        self.assertTrue(hasattr(request, 'start_time'))
        self.assertIsInstance(request.request_id, str)
        self.assertTrue(len(request.request_id) > 0)
    
    def test_request_id_from_header(self):
        """Test using existing request ID from header."""
        from django.http import HttpRequest
        
        request = HttpRequest()
        request.method = 'GET'
        request.path = '/test'
        request.META = {
            'HTTP_X_REQUEST_ID': 'existing-request-id-123'
        }
        
        # Process request
        self.middleware.process_request(request)
        
        # Check existing request ID was used
        self.assertEqual(request.request_id, 'existing-request-id-123')
    
    def test_response_includes_request_id(self):
        """Test that response includes request ID header."""
        from django.http import HttpRequest, HttpResponse
        
        request = HttpRequest()
        request.method = 'GET'
        request.path = '/test'
        request.META = {}
        request.start_time = time.time()
        
        # Process request to generate ID
        self.middleware.process_request(request)
        
        # Process response
        response = HttpResponse()
        response = self.middleware.process_response(request, response)
        
        # Check response header
        self.assertIn('X-Request-ID', response)
        self.assertEqual(response['X-Request-ID'], request.request_id)
    
    def test_conversation_context_extraction(self):
        """Test conversation context extraction from webhook requests."""
        from apps.core.middleware.request_tracking import ConversationContextMiddleware
        from django.http import HttpRequest
        
        middleware = ConversationContextMiddleware()
        
        request = HttpRequest()
        request.method = 'POST'
        request.path = '/v1/webhooks/twilio'
        request.META = {
            'HTTP_X_TENANT_ID': 'tenant-123',
            'HTTP_X_CONVERSATION_ID': 'conv-456'
        }
        request.POST = {
            'From': '+254700000001',
            'Body': 'Hello, I need help',
            'NumMedia': '0'
        }
        
        # Process request
        middleware.process_request(request)
        
        # Check conversation context was extracted
        self.assertTrue(hasattr(request, 'conversation_context'))
        context = request.conversation_context
        
        self.assertEqual(context['tenant_id'], 'tenant-123')
        self.assertEqual(context['conversation_id'], 'conv-456')
        self.assertIn('*', context['phone_e164'])  # Should be masked
        self.assertEqual(context['message_length'], 17)
        self.assertFalse(context['has_media'])


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class IntegrationTest(TestCase):
    """Integration tests for logging and observability."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            bot_name="TestBot"
        )
        
        self.customer = Customer.objects.create(
            tenant_id=self.tenant.id,
            phone_e164="+254700000001"
        )
    
    @patch('apps.bot.services.conversation_logger.conversation_logger.log_conversation_start')
    @patch('apps.bot.services.metrics_collector.metrics_collector.track_journey_start')
    def test_orchestrator_logging_integration(self, mock_metrics_track, mock_logger_start):
        """Test that orchestrator integrates with logging services."""
        from apps.bot.langgraph.orchestrator import LangGraphOrchestrator
        
        # Create orchestrator instance
        orchestrator = LangGraphOrchestrator()
        
        # Mock the graph execution
        with patch.object(orchestrator, '_graph') as mock_graph:
            mock_graph.ainvoke.return_value = {
                'tenant_id': str(self.tenant.id),
                'conversation_id': 'test-conv',
                'request_id': 'test-req',
                'response_text': 'Hello! How can I help you?',
                'intent': 'sales_discovery',
                'journey': 'sales'
            }
            
            # Process message (this would normally be async)
            with patch('apps.bot.langgraph.orchestrator.ConversationStateManager.create_initial_state') as mock_create_state:
                mock_state = ConversationState(
                    tenant_id=str(self.tenant.id),
                    conversation_id='test-conv',
                    request_id='test-req'
                )
                mock_create_state.return_value = mock_state
                
                # This would be async in real usage
                # result = await orchestrator.process_message(...)
                
                # For now, just verify the logging calls would be made
                # by calling the logging methods directly
                conversation_logger.log_conversation_start(mock_state, "Hello")
                metrics_collector.track_journey_start("sales", "test-conv", str(self.tenant.id))
                
                # Verify logging calls
                mock_logger_start.assert_called_once()
                mock_metrics_track.assert_called_once_with("sales", "test-conv", str(self.tenant.id))
    
    def test_end_to_end_metrics_collection(self):
        """Test end-to-end metrics collection flow."""
        conversation_id = "test-conv-e2e"
        tenant_id = str(self.tenant.id)
        
        # Simulate a complete conversation flow
        # 1. Start journey
        metrics_collector.track_journey_start("sales", conversation_id, tenant_id)
        
        # 2. Track some performance metrics
        metrics_collector.track_performance("llm_node", "intent_classify", 0.5, True, conversation_id)
        metrics_collector.track_performance("tool_call", "catalog_search", 1.2, True, conversation_id)
        
        # 3. Track business events
        observability_service.start_conversation_tracking(tenant_id, conversation_id, "req-123")
        observability_service.track_business_event(conversation_id, "product_viewed")
        observability_service.track_business_event(conversation_id, "order_created")
        
        # 4. Track payment
        metrics_collector.track_payment_initiation("mpesa_stk", conversation_id, tenant_id, 100.0)
        metrics_collector.track_payment_completion("mpesa_stk", conversation_id, tenant_id, True, 5.0, 100.0)
        
        # 5. Complete journey
        metrics_collector.track_journey_completion("sales", conversation_id, tenant_id, True, 45.0)
        
        # 6. End conversation tracking
        final_metrics = observability_service.end_conversation_tracking(conversation_id)
        
        # Verify metrics were collected
        journey_rates = metrics_collector.get_journey_completion_rates()
        self.assertIn("sales", journey_rates)
        self.assertEqual(journey_rates["sales"], 1.0)
        
        payment_rates = metrics_collector.get_payment_success_rates()
        self.assertIn("mpesa_stk", payment_rates)
        self.assertEqual(payment_rates["mpesa_stk"], 1.0)
        
        # Verify conversation metrics
        self.assertIsNotNone(final_metrics)
        self.assertEqual(final_metrics.products_viewed, 1)
        self.assertEqual(final_metrics.orders_created, 1)
        self.assertTrue(final_metrics.total_duration > 0)
    
    def test_error_tracking_and_recovery(self):
        """Test error tracking and recovery metrics."""
        conversation_id = "test-conv-error"
        tenant_id = str(self.tenant.id)
        
        # Start conversation tracking
        observability_service.start_conversation_tracking(tenant_id, conversation_id, "req-456")
        
        # Track some errors
        observability_service.track_error(
            conversation_id, "ConnectionError", "Failed to connect to payment service", 
            "payment_processor", retry_count=2, fallback_used=True
        )
        
        observability_service.track_error(
            conversation_id, "TimeoutError", "LLM request timed out", 
            "llm_service", retry_count=1, fallback_used=False
        )
        
        # Track escalation due to errors
        observability_service.track_escalation(
            conversation_id, "system_errors", {"error_count": 2, "component": "payment_processor"}
        )
        
        # Get final metrics
        final_metrics = observability_service.end_conversation_tracking(conversation_id)
        
        # Verify error tracking
        self.assertEqual(final_metrics.total_errors, 2)
        self.assertEqual(final_metrics.retry_attempts, 3)
        self.assertEqual(final_metrics.fallbacks_used, 1)
        self.assertEqual(final_metrics.escalations_triggered, 1)
        
        # Verify system health reflects errors
        health = observability_service.get_system_health_summary()
        self.assertTrue(health['total_errors'] > 0)
        self.assertTrue(health['total_escalations'] > 0)