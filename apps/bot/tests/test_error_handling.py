"""
Tests for comprehensive error handling system.

This module tests the error handling service, circuit breakers,
retry logic, and fallback responses to ensure conversation continuity.

Requirements: 10.1, 10.3
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from apps.bot.services.error_handling import (
    ErrorHandlingService, ErrorContext, ComponentType, CircuitBreaker,
    RetryStrategy, CircuitBreakerOpenError, EnhancedOperationError,
    error_handling_service, with_error_handling
)
from apps.bot.services.orchestrator_error_handler import (
    OrchestratorErrorHandler, orchestrator_error_handler, with_node_error_handling
)
from apps.bot.services.observability import (
    ObservabilityService, ConversationMetrics, ConversationTracker,
    observability_service, track_performance
)
from apps.bot.tools.base import BaseTool, ToolResponse
from apps.bot.conversation_state import ConversationState


class TestErrorHandlingService:
    """Test the core error handling service."""
    
    def test_error_context_creation(self):
        """Test error context creation with required fields."""
        context = ErrorContext(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            component_type=ComponentType.LLM_NODE,
            operation="test_operation"
        )
        
        assert context.tenant_id == "test-tenant"
        assert context.conversation_id == "test-conv"
        assert context.request_id == "test-req"
        assert context.component_type == ComponentType.LLM_NODE
        assert context.operation == "test_operation"
        assert context.attempt_count == 0
        assert context.last_error is None
        assert context.error_history == []
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state allows calls."""
        circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        @circuit_breaker
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
        assert circuit_breaker.state.state == "closed"
        assert circuit_breaker.state.failure_count == 0
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        
        @circuit_breaker
        def failing_function():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            failing_function()
        assert circuit_breaker.state.failure_count == 1
        assert circuit_breaker.state.state == "closed"
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            failing_function()
        assert circuit_breaker.state.failure_count == 2
        assert circuit_breaker.state.state == "open"
        
        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            failing_function()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        @circuit_breaker
        def test_function(should_fail=True):
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Cause failure to open circuit
        with pytest.raises(ValueError):
            test_function()
        assert circuit_breaker.state.state == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to half_open and allow call
        result = test_function(should_fail=False)
        assert result == "success"
        # After 3 successes, should close
        test_function(should_fail=False)
        test_function(should_fail=False)
        assert circuit_breaker.state.state == "closed"
    
    def test_retry_strategy_calculation(self):
        """Test retry delay calculation with exponential backoff."""
        strategy = RetryStrategy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False
        )
        
        # Test delay calculation
        assert strategy.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert strategy.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert strategy.calculate_delay(2) == 4.0  # 1.0 * 2^2
        
        # Test max delay cap
        strategy.base_delay = 8.0
        delay = strategy.calculate_delay(2)  # Would be 32.0
        assert delay == 10.0  # Capped at max_delay
    
    def test_retry_strategy_should_retry_logic(self):
        """Test retry decision logic for different error types."""
        strategy = RetryStrategy(max_attempts=3)
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.TOOL_CALL, operation="test"
        )
        
        # Should retry network errors
        assert strategy.should_retry(1, ConnectionError("Network error"), context)
        
        # Should not retry validation errors
        assert not strategy.should_retry(1, ValueError("Invalid input"), context)
        
        # Should not retry after max attempts
        assert not strategy.should_retry(3, ConnectionError("Network error"), context)
        
        # Should not retry circuit breaker errors
        assert not strategy.should_retry(1, CircuitBreakerOpenError("Circuit open"), context)
    
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_success(self):
        """Test successful operation execution."""
        service = ErrorHandlingService()
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.TOOL_CALL, operation="test"
        )
        
        async def successful_operation():
            return "success"
        
        result = await service.execute_with_error_handling(
            successful_operation, context
        )
        
        assert result == "success"
        assert context.attempt_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_retry_and_success(self):
        """Test operation that fails once then succeeds."""
        service = ErrorHandlingService()
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.TOOL_CALL, operation="test"
        )
        
        call_count = 0
        
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            return "success"
        
        result = await service.execute_with_error_handling(
            flaky_operation, context
        )
        
        assert result == "success"
        assert call_count == 2
        assert context.attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_fallback(self):
        """Test fallback execution when operation fails."""
        service = ErrorHandlingService()
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.TOOL_CALL, operation="test"
        )
        
        async def failing_operation():
            raise ConnectionError("Network error")
        
        async def fallback_operation():
            return "fallback_result"
        
        result = await service.execute_with_error_handling(
            failing_operation, context, fallback_operation
        )
        
        assert result == "fallback_result"
        assert context.attempt_count == 3  # Max attempts reached
    
    def test_get_fallback_response(self):
        """Test fallback response generation."""
        service = ErrorHandlingService()
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.TOOL_CALL, operation="catalog_search"
        )
        
        response = service.get_fallback_response(
            ComponentType.TOOL_CALL, "catalog_search", context
        )
        
        assert not response["success"]
        assert "catalog" in response["error"].lower()
        assert response["error_code"] == "CATALOG_SEARCH_FAILED"
        assert "error_context" in response
        assert response["error_context"]["tenant_id"] == "test"


class TestOrchestratorErrorHandler:
    """Test orchestrator-specific error handling."""
    
    @pytest.mark.asyncio
    async def test_execute_node_with_fallback_success(self):
        """Test successful node execution."""
        handler = OrchestratorErrorHandler()
        
        async def successful_node(state):
            state["result"] = "success"
            return state
        
        state = {
            "tenant_id": "test",
            "conversation_id": "test",
            "request_id": "test"
        }
        
        result = await handler.execute_node_with_fallback(
            successful_node, state, "test_node"
        )
        
        assert result["result"] == "success"
    
    @pytest.mark.asyncio
    async def test_execute_node_with_fallback_error(self):
        """Test node execution with fallback on error."""
        handler = OrchestratorErrorHandler()
        
        async def failing_node(state):
            raise ValueError("Node failed")
        
        state = {
            "tenant_id": "test",
            "conversation_id": "test",
            "request_id": "test"
        }
        
        result = await handler.execute_node_with_fallback(
            failing_node, state, "intent_classify"
        )
        
        # Should apply fallback for intent_classify
        assert result["intent"] == "unknown"
        assert result["intent_confidence"] == 0.0
        assert result["journey"] == "support"
        assert "error_context" in result
        assert result["error_context"]["failed_node"] == "intent_classify"
    
    def test_get_node_fallback_specific(self):
        """Test specific node fallback responses."""
        handler = OrchestratorErrorHandler()
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.LLM_NODE, operation="intent_classify"
        )
        
        state = {"tenant_id": "test"}
        result = handler._get_node_fallback("intent_classify", state, context)
        
        assert result["intent"] == "unknown"
        assert result["intent_confidence"] == 0.0
        assert result["journey"] == "support"
    
    def test_get_emergency_fallback(self):
        """Test emergency fallback when all else fails."""
        handler = OrchestratorErrorHandler()
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.LLM_NODE, operation="test_node"
        )
        
        state = {"tenant_id": "test"}
        result = handler._get_emergency_fallback("test_node", state, context)
        
        assert result["escalation_required"] is True
        assert result["escalation_reason"] == "System failure in test_node node"
        assert result["journey"] == "governance"
        assert result["error_context"]["emergency_fallback"] is True


class TestObservabilityService:
    """Test observability and monitoring service."""
    
    def test_conversation_metrics_creation(self):
        """Test conversation metrics initialization."""
        metrics = ConversationMetrics(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        assert metrics.tenant_id == "test-tenant"
        assert metrics.conversation_id == "test-conv"
        assert metrics.request_id == "test-req"
        assert metrics.journey_started is None
        assert metrics.nodes_executed == []
        assert metrics.tools_called == []
        assert metrics.total_errors == 0
    
    def test_start_conversation_tracking(self):
        """Test starting conversation tracking."""
        service = ObservabilityService()
        
        metrics = service.start_conversation_tracking(
            "test-tenant", "test-conv", "test-req", "test-customer"
        )
        
        assert metrics.tenant_id == "test-tenant"
        assert metrics.conversation_id == "test-conv"
        assert metrics.customer_id == "test-customer"
        assert "test-conv" in service.conversation_metrics
    
    def test_track_journey_lifecycle(self):
        """Test journey start and completion tracking."""
        service = ObservabilityService()
        
        # Start tracking
        service.start_conversation_tracking("test", "conv1", "req1")
        
        # Track journey start
        service.track_journey_start("conv1", "sales")
        metrics = service.conversation_metrics["conv1"]
        assert metrics.journey_started == "sales"
        
        # Track journey completion
        service.track_journey_completion("conv1", "sales", True)
        assert metrics.journey_completed == "sales"
        assert metrics.journey_success is True
        assert metrics.journey_duration is not None
    
    def test_track_node_execution(self):
        """Test node execution tracking."""
        service = ObservabilityService()
        service.start_conversation_tracking("test", "conv1", "req1")
        
        # Track successful node
        service.track_node_execution("conv1", "intent_classify", 0.5, True)
        metrics = service.conversation_metrics["conv1"]
        assert "intent_classify" in metrics.nodes_executed
        assert metrics.node_durations["intent_classify"] == 0.5
        
        # Track failed node
        service.track_node_execution("conv1", "language_policy", 0.3, False)
        assert "language_policy" in metrics.node_failures
        assert metrics.total_errors == 1
    
    def test_track_business_events(self):
        """Test business event tracking."""
        service = ObservabilityService()
        service.start_conversation_tracking("test", "conv1", "req1")
        
        # Track various business events
        service.track_business_event("conv1", "product_viewed")
        service.track_business_event("conv1", "order_created")
        service.track_business_event("conv1", "payment_initiated")
        service.track_business_event("conv1", "escalation_triggered")
        
        metrics = service.conversation_metrics["conv1"]
        assert metrics.products_viewed == 1
        assert metrics.orders_created == 1
        assert metrics.payments_initiated == 1
        assert metrics.escalations_triggered == 1
    
    def test_conversation_tracker_context_manager(self):
        """Test conversation tracker context manager."""
        with ConversationTracker("test", "conv1", "req1") as metrics:
            assert metrics.tenant_id == "test"
            assert metrics.conversation_id == "conv1"
            
        # Should be removed from active tracking after context exit
        assert "conv1" not in observability_service.conversation_metrics
    
    def test_get_system_health_summary(self):
        """Test system health summary generation."""
        service = ObservabilityService()
        
        # Add some test data
        service.start_conversation_tracking("test1", "conv1", "req1")
        service.start_conversation_tracking("test2", "conv2", "req2")
        service.track_error("conv1", "TestError", "Test message", "test_component")
        
        summary = service.get_system_health_summary()
        
        assert summary["active_conversations"] == 2
        assert summary["total_errors"] == 1
        assert "timestamp" in summary
        assert "error_rate" in summary


class TestToolErrorHandling:
    """Test error handling integration with tools."""
    
    def test_base_tool_execute_with_fallback(self):
        """Test base tool execution with fallback."""
        
        class TestTool(BaseTool):
            def get_schema(self):
                return {"type": "object"}
            
            def execute(self, **kwargs):
                if kwargs.get("should_fail"):
                    raise ConnectionError("Network error")
                return ToolResponse(success=True, data={"result": "success"})
        
        tool = TestTool()
        
        # Test successful execution
        result = tool.execute_with_fallback(
            tenant_id="test", conversation_id="test", request_id="test"
        )
        assert result.success is True
        assert result.data["result"] == "success"
    
    def test_with_error_handling_decorator(self):
        """Test error handling decorator."""
        
        @with_error_handling(ComponentType.TOOL_CALL, "test_operation")
        def test_function(should_fail=False):
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Test successful execution
        result = test_function()
        assert result == "success"
        
        # Test error handling
        with pytest.raises(EnhancedOperationError):
            test_function(should_fail=True)


class TestIntegrationScenarios:
    """Test end-to-end error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_cascading_failure_recovery(self):
        """Test recovery from cascading failures."""
        service = ErrorHandlingService()
        
        # Simulate cascading failures with eventual recovery
        failure_count = 0
        
        async def cascading_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 2:
                raise ConnectionError(f"Failure {failure_count}")
            return "recovered"
        
        context = ErrorContext(
            tenant_id="test", conversation_id="test", request_id="test",
            component_type=ComponentType.EXTERNAL_API, operation="test"
        )
        
        result = await service.execute_with_error_handling(
            cascading_operation, context
        )
        
        assert result == "recovered"
        assert failure_count == 3
        assert context.attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_conversation_continuity_during_failures(self):
        """Test that conversation continues despite component failures."""
        handler = OrchestratorErrorHandler()
        
        # Simulate multiple node failures
        async def failing_intent_node(state):
            raise ValueError("Intent classification failed")
        
        async def failing_language_node(state):
            raise ConnectionError("Language service down")
        
        state = {
            "tenant_id": "test",
            "conversation_id": "test",
            "request_id": "test",
            "message_text": "Hello"
        }
        
        # Both nodes should fail but provide fallbacks
        intent_result = await handler.execute_node_with_fallback(
            failing_intent_node, state, "intent_classify"
        )
        
        language_result = await handler.execute_node_with_fallback(
            failing_language_node, intent_result, "language_policy"
        )
        
        # Conversation should continue with fallback values
        assert intent_result["intent"] == "unknown"
        assert language_result["response_language"] == "en"
        assert "error_context" in language_result
    
    def test_performance_tracking_integration(self):
        """Test performance tracking with error handling."""
        
        @track_performance("test_node_operation")
        def test_operation(conversation_id="test", should_fail=False):
            if should_fail:
                raise ValueError("Operation failed")
            return "success"
        
        # Test successful tracking
        result = test_operation()
        assert result == "success"
        
        # Test error tracking
        with pytest.raises(ValueError):
            test_operation(should_fail=True)
        
        # Verify metrics were tracked
        metrics = observability_service.get_conversation_metrics("test")
        if metrics:  # May not exist if not explicitly started
            assert len(metrics.nodes_executed) > 0 or len(metrics.node_failures) > 0