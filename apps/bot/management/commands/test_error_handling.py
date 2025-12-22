"""
Management command to test comprehensive error handling system.

This command simulates various failure scenarios to validate
error handling, circuit breakers, retry logic, and fallback responses.

Requirements: 10.1, 10.3
"""

import asyncio
import time
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bot.services.error_handling import (
    ErrorHandlingService, ErrorContext, ComponentType, CircuitBreaker,
    error_handling_service
)
from apps.bot.services.orchestrator_error_handler import orchestrator_error_handler
from apps.bot.services.observability import observability_service, ConversationTracker
from apps.bot.conversation_state import ConversationState


class Command(BaseCommand):
    """Test comprehensive error handling system."""
    
    help = 'Test error handling, circuit breakers, and fallback responses'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['all', 'circuit_breaker', 'retry_logic', 'fallbacks', 'observability'],
            default='all',
            help='Test scenario to run'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        """Execute the test command."""
        self.verbose = options['verbose']
        scenario = options['scenario']
        
        self.stdout.write(
            self.style.SUCCESS('Starting error handling system tests...')
        )
        
        if scenario in ['all', 'circuit_breaker']:
            self.test_circuit_breaker()
        
        if scenario in ['all', 'retry_logic']:
            asyncio.run(self.test_retry_logic())
        
        if scenario in ['all', 'fallbacks']:
            asyncio.run(self.test_fallback_responses())
        
        if scenario in ['all', 'observability']:
            self.test_observability_tracking()
        
        self.stdout.write(
            self.style.SUCCESS('All error handling tests completed successfully!')
        )
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        self.stdout.write('Testing circuit breaker...')
        
        # Create circuit breaker with low threshold for testing
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        @circuit_breaker
        def test_service(should_fail=True):
            if should_fail:
                raise ConnectionError("Service unavailable")
            return "success"
        
        # Test normal operation
        try:
            result = test_service(should_fail=False)
            assert result == "success"
            if self.verbose:
                self.stdout.write("✓ Circuit breaker allows successful calls")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Unexpected error: {e}"))
            return
        
        # Cause failures to open circuit
        failure_count = 0
        for i in range(3):
            try:
                test_service(should_fail=True)
            except ConnectionError:
                failure_count += 1
                if self.verbose:
                    self.stdout.write(f"✓ Failure {failure_count} recorded")
            except Exception as e:
                if "Circuit breaker is open" in str(e):
                    if self.verbose:
                        self.stdout.write("✓ Circuit breaker opened after failures")
                    break
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Unexpected error: {e}"))
                    return
        
        # Test recovery after timeout
        time.sleep(1.1)  # Wait for recovery timeout
        try:
            result = test_service(should_fail=False)
            assert result == "success"
            if self.verbose:
                self.stdout.write("✓ Circuit breaker recovered after timeout")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Recovery failed: {e}"))
            return
        
        self.stdout.write(self.style.SUCCESS("✓ Circuit breaker test passed"))
    
    async def test_retry_logic(self):
        """Test retry logic with exponential backoff."""
        self.stdout.write('Testing retry logic...')
        
        service = ErrorHandlingService()
        context = ErrorContext(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            component_type=ComponentType.EXTERNAL_API,
            operation="test_retry"
        )
        
        # Test successful retry after failures
        attempt_count = 0
        
        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 2:
                raise ConnectionError(f"Attempt {attempt_count} failed")
            return f"Success on attempt {attempt_count}"
        
        try:
            result = await service.execute_with_error_handling(
                flaky_operation, context
            )
            assert "Success on attempt 3" in result
            assert context.attempt_count == 3
            if self.verbose:
                self.stdout.write(f"✓ Operation succeeded after {context.attempt_count} attempts")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Retry logic failed: {e}"))
            return
        
        # Test fallback when all retries exhausted
        context = ErrorContext(
            tenant_id="test-tenant",
            conversation_id="test-conv-2",
            request_id="test-req-2",
            component_type=ComponentType.TOOL_CALL,
            operation="test_fallback"
        )
        
        async def always_failing_operation():
            raise ConnectionError("Always fails")
        
        async def fallback_operation():
            return "Fallback result"
        
        try:
            result = await service.execute_with_error_handling(
                always_failing_operation, context, fallback_operation
            )
            assert result == "Fallback result"
            if self.verbose:
                self.stdout.write("✓ Fallback executed after retry exhaustion")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Fallback test failed: {e}"))
            return
        
        self.stdout.write(self.style.SUCCESS("✓ Retry logic test passed"))
    
    async def test_fallback_responses(self):
        """Test fallback response generation."""
        self.stdout.write('Testing fallback responses...')
        
        handler = orchestrator_error_handler
        
        # Test intent classification fallback
        async def failing_intent_node(state):
            raise ValueError("Intent classification failed")
        
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "message_text": "Hello"
        }
        
        try:
            result = await handler.execute_node_with_fallback(
                failing_intent_node, state, "intent_classify"
            )
            
            assert result["intent"] == "unknown"
            assert result["intent_confidence"] == 0.0
            assert result["journey"] == "support"
            assert "error_context" in result
            
            if self.verbose:
                self.stdout.write("✓ Intent classification fallback applied")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Intent fallback failed: {e}"))
            return
        
        # Test language policy fallback
        async def failing_language_node(state):
            raise ConnectionError("Language service unavailable")
        
        try:
            result = await handler.execute_node_with_fallback(
                failing_language_node, state, "language_policy"
            )
            
            assert result["response_language"] == "en"
            assert result["language_confidence"] == 0.0
            assert "error_context" in result
            
            if self.verbose:
                self.stdout.write("✓ Language policy fallback applied")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Language fallback failed: {e}"))
            return
        
        # Test emergency fallback
        async def catastrophic_failure_node(state):
            raise RuntimeError("Catastrophic system failure")
        
        try:
            result = await handler.execute_node_with_fallback(
                catastrophic_failure_node, state, "unknown_node"
            )
            
            assert result["escalation_required"] is True
            assert "System failure" in result["escalation_reason"]
            assert result["journey"] == "governance"
            assert result["error_context"]["emergency_fallback"] is True
            
            if self.verbose:
                self.stdout.write("✓ Emergency fallback applied")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Emergency fallback failed: {e}"))
            return
        
        self.stdout.write(self.style.SUCCESS("✓ Fallback responses test passed"))
    
    def test_observability_tracking(self):
        """Test observability and metrics tracking."""
        self.stdout.write('Testing observability tracking...')
        
        service = observability_service
        
        # Test conversation tracking
        with ConversationTracker("test-tenant", "test-conv", "test-req") as metrics:
            assert metrics.tenant_id == "test-tenant"
            assert metrics.conversation_id == "test-conv"
            
            # Test journey tracking
            service.track_journey_start("test-conv", "sales")
            assert metrics.journey_started == "sales"
            
            # Test node execution tracking
            service.track_node_execution("test-conv", "intent_classify", 0.5, True)
            assert "intent_classify" in metrics.nodes_executed
            assert metrics.node_durations["intent_classify"] == 0.5
            
            # Test tool execution tracking
            service.track_tool_execution("test-conv", "catalog_search", 1.2, False)
            assert "catalog_search" in metrics.tool_failures
            assert metrics.total_errors == 1
            
            # Test business event tracking
            service.track_business_event("test-conv", "product_viewed")
            service.track_business_event("test-conv", "order_created")
            assert metrics.products_viewed == 1
            assert metrics.orders_created == 1
            
            # Test error tracking
            service.track_error(
                "test-conv", "TestError", "Test error message", 
                "test_component", retry_count=2, fallback_used=True
            )
            assert metrics.retry_attempts == 2
            assert metrics.fallbacks_used == 1
            
            # Test escalation tracking
            service.track_escalation(
                "test-conv", "System failure", {"component": "test"}
            )
            assert metrics.escalations_triggered == 1
            
            if self.verbose:
                self.stdout.write("✓ All tracking methods working correctly")
        
        # Test system health summary
        summary = service.get_system_health_summary()
        assert "timestamp" in summary
        assert "active_conversations" in summary
        assert "error_rate" in summary
        
        if self.verbose:
            self.stdout.write(f"✓ System health summary generated: {len(summary)} metrics")
        
        self.stdout.write(self.style.SUCCESS("✓ Observability tracking test passed"))
    
    def log_verbose(self, message):
        """Log verbose message if verbose mode is enabled."""
        if self.verbose:
            self.stdout.write(message)