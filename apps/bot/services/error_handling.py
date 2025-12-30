"""
Comprehensive error handling service for LangGraph orchestration.

This module implements graceful degradation, circuit breaker patterns,
retry logic, and fallback responses to ensure conversation continuity
during component failures.

Requirements: 10.1, 10.3
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Callable, List, Union
from functools import wraps
import random

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for different handling strategies."""
    LOW = "low"           # Minor issues, continue with fallback
    MEDIUM = "medium"     # Moderate issues, retry with backoff
    HIGH = "high"         # Serious issues, escalate but continue
    CRITICAL = "critical" # System failures, immediate escalation


class ComponentType(Enum):
    """Types of system components for targeted error handling."""
    LLM_NODE = "llm_node"
    TOOL_CALL = "tool_call"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    VECTOR_DB = "vector_db"
    PAYMENT_GATEWAY = "payment_gateway"


@dataclass
class ErrorContext:
    """Context information for error handling decisions."""
    tenant_id: str
    conversation_id: str
    request_id: str
    component_type: ComponentType
    operation: str
    attempt_count: int = 0
    last_error: Optional[Exception] = None
    error_history: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker pattern."""
    failure_count: int = 0
    last_failure_time: float = 0
    state: str = "closed"  # closed, open, half_open
    success_count: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.
    
    Prevents cascading failures by temporarily disabling calls
    to failing services and providing fallback responses.
    """
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.state = CircuitBreakerState()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker logic."""
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self._call(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return asyncio.run(self._call(func, *args, **kwargs))
            return sync_wrapper
    
    async def _call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state.state == "open":
            if time.time() - self.state.last_failure_time < self.recovery_timeout:
                raise CircuitBreakerOpenError("Circuit breaker is open")
            else:
                self.state.state = "half_open"
                self.state.success_count = 0
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            if self.state.state == "half_open":
                self.state.success_count += 1
                if self.state.success_count >= 3:  # Require 3 successes to close
                    self.state.state = "closed"
                    self.state.failure_count = 0
            
            return result
            
        except self.expected_exception as e:
            self.state.failure_count += 1
            self.state.last_failure_time = time.time()
            
            if self.state.failure_count >= self.failure_threshold:
                self.state.state = "open"
                logger.warning(f"Circuit breaker opened after {self.state.failure_count} failures")
            
            raise e


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RetryStrategy:
    """
    Retry logic with exponential backoff and jitter.
    
    Implements intelligent retry patterns for different types of failures
    with configurable backoff strategies.
    """
    
    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True):
        """
        Initialize retry strategy.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add ±25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def should_retry(self, attempt: int, error: Exception, context: ErrorContext) -> bool:
        """Determine if operation should be retried."""
        if attempt >= self.max_attempts:
            return False
        
        # Don't retry certain error types
        if isinstance(error, (ValueError, TypeError, KeyError)):
            return False
        
        # Don't retry authentication/authorization errors
        if "401" in str(error) or "403" in str(error):
            return False
        
        # Don't retry if circuit breaker is open
        if isinstance(error, CircuitBreakerOpenError):
            return False
        
        return True


class ErrorHandlingService:
    """
    Central service for comprehensive error handling across the system.
    
    Provides graceful degradation, retry logic, circuit breakers,
    and fallback responses to maintain conversation continuity.
    """
    
    def __init__(self):
        """Initialize error handling service."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_strategies: Dict[ComponentType, RetryStrategy] = {
            ComponentType.LLM_NODE: RetryStrategy(max_attempts=2, base_delay=1.0),
            ComponentType.TOOL_CALL: RetryStrategy(max_attempts=3, base_delay=0.5),
            ComponentType.DATABASE: RetryStrategy(max_attempts=3, base_delay=0.2),
            ComponentType.EXTERNAL_API: RetryStrategy(max_attempts=3, base_delay=2.0),
            ComponentType.VECTOR_DB: RetryStrategy(max_attempts=2, base_delay=1.0),
            ComponentType.PAYMENT_GATEWAY: RetryStrategy(max_attempts=2, base_delay=3.0),
        }
        self.fallback_responses = self._initialize_fallback_responses()
    
    def get_circuit_breaker(self, service_name: str, component_type: ComponentType) -> CircuitBreaker:
        """Get or create circuit breaker for a service."""
        key = f"{service_name}_{component_type.value}"
        
        if key not in self.circuit_breakers:
            # Configure circuit breaker based on component type
            if component_type == ComponentType.PAYMENT_GATEWAY:
                self.circuit_breakers[key] = CircuitBreaker(
                    failure_threshold=3, recovery_timeout=300  # 5 minutes
                )
            elif component_type == ComponentType.EXTERNAL_API:
                self.circuit_breakers[key] = CircuitBreaker(
                    failure_threshold=5, recovery_timeout=120  # 2 minutes
                )
            else:
                self.circuit_breakers[key] = CircuitBreaker()
        
        return self.circuit_breakers[key]
    
    async def execute_with_error_handling(self,
                                        operation: Callable,
                                        context: ErrorContext,
                                        fallback: Optional[Callable] = None) -> Any:
        """
        Execute operation with comprehensive error handling.
        
        Args:
            operation: The operation to execute
            context: Error context for handling decisions
            fallback: Optional fallback operation
            
        Returns:
            Operation result or fallback result
        """
        retry_strategy = self.retry_strategies.get(
            context.component_type, 
            RetryStrategy()
        )
        
        last_error = None
        
        for attempt in range(retry_strategy.max_attempts):
            context.attempt_count = attempt + 1
            
            try:
                # Execute operation
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    result = operation()
                
                # Log successful recovery if this was a retry
                if attempt > 0:
                    logger.info(
                        f"Operation recovered after {attempt} retries",
                        extra={
                            'tenant_id': context.tenant_id,
                            'conversation_id': context.conversation_id,
                            'request_id': context.request_id,
                            'component_type': context.component_type.value,
                            'operation': context.operation,
                            'attempt': attempt + 1
                        }
                    )
                
                return result
                
            except Exception as e:
                last_error = e
                context.last_error = e
                context.error_history.append(str(e))
                
                # Log error with context
                logger.error(
                    f"Operation failed: {context.operation}",
                    extra={
                        'tenant_id': context.tenant_id,
                        'conversation_id': context.conversation_id,
                        'request_id': context.request_id,
                        'component_type': context.component_type.value,
                        'operation': context.operation,
                        'attempt': attempt + 1,
                        'error': str(e),
                        'error_type': type(e).__name__
                    },
                    exc_info=True
                )
                
                # Check if we should retry
                if not retry_strategy.should_retry(attempt, e, context):
                    break
                
                # Calculate and apply delay
                if attempt < retry_strategy.max_attempts - 1:
                    delay = retry_strategy.calculate_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
        
        # All retries exhausted, try fallback
        if fallback:
            try:
                logger.info(
                    f"Executing fallback for failed operation: {context.operation}",
                    extra={
                        'tenant_id': context.tenant_id,
                        'conversation_id': context.conversation_id,
                        'request_id': context.request_id,
                        'component_type': context.component_type.value
                    }
                )
                
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback()
                else:
                    return fallback()
                    
            except Exception as fallback_error:
                logger.error(
                    f"Fallback also failed for operation: {context.operation}",
                    extra={
                        'tenant_id': context.tenant_id,
                        'conversation_id': context.conversation_id,
                        'request_id': context.request_id,
                        'component_type': context.component_type.value,
                        'fallback_error': str(fallback_error)
                    },
                    exc_info=True
                )
        
        # Final fallback - raise the last error with enhanced context
        error_summary = self._create_error_summary(context, last_error)
        raise EnhancedOperationError(error_summary, context, last_error)
    
    def get_fallback_response(self, 
                            component_type: ComponentType, 
                            operation: str,
                            context: ErrorContext) -> Dict[str, Any]:
        """
        Get appropriate fallback response for failed operation.
        
        Args:
            component_type: Type of component that failed
            operation: Name of the failed operation
            context: Error context
            
        Returns:
            Fallback response data
        """
        fallback_key = f"{component_type.value}_{operation}"
        
        # Try specific fallback first
        if fallback_key in self.fallback_responses:
            response = self.fallback_responses[fallback_key].copy()
        else:
            # Use generic fallback for component type
            response = self.fallback_responses.get(
                component_type.value, 
                self.fallback_responses["generic"]
            ).copy()
        
        # Add context to response
        response["error_context"] = {
            "tenant_id": context.tenant_id,
            "conversation_id": context.conversation_id,
            "request_id": context.request_id,
            "component_type": component_type.value,
            "operation": operation,
            "attempt_count": context.attempt_count
        }
        
        return response
    
    def _initialize_fallback_responses(self) -> Dict[str, Dict[str, Any]]:
        """Initialize fallback responses for different failure scenarios."""
        return {
            "generic": {
                "success": False,
                "data": None,
                "error": "I'm experiencing technical difficulties. Let me connect you with a human agent who can help.",
                "error_code": "SYSTEM_ERROR",
                "escalation_required": True,
                "escalation_reason": "System component failure"
            },
            
            # LLM Node fallbacks
            "llm_node_intent_classify": {
                "success": True,
                "data": {
                    "intent": "unknown",
                    "confidence": 0.0,
                    "notes": "Classification failed - using fallback",
                    "suggested_journey": "support"
                }
            },
            
            "llm_node_language_policy": {
                "success": True,
                "data": {
                    "response_language": "en",
                    "confidence": 0.0,
                    "should_ask_language_question": False
                }
            },
            
            "llm_node_governor_spam_casual": {
                "success": True,
                "data": {
                    "classification": "business",
                    "confidence": 0.0,
                    "recommended_action": "proceed"
                }
            },
            
            # Tool call fallbacks
            "tool_call_catalog_search": {
                "success": False,
                "data": None,
                "error": "I'm having trouble searching our catalog right now. You can browse our full catalog at our website, or I can connect you with someone who can help find what you're looking for.",
                "error_code": "CATALOG_SEARCH_FAILED",
                "suggested_action": "catalog_link_or_handoff"
            },
            
            "tool_call_payment_initiate": {
                "success": False,
                "data": None,
                "error": "I'm unable to process payments right now. Please try again in a few minutes, or I can connect you with our support team to complete your order.",
                "error_code": "PAYMENT_SYSTEM_ERROR",
                "escalation_required": True,
                "escalation_reason": "Payment system failure"
            },
            
            "tool_call_order_create": {
                "success": False,
                "data": None,
                "error": "I'm having trouble creating your order right now. Let me connect you with our team to complete your purchase manually.",
                "error_code": "ORDER_CREATION_FAILED",
                "escalation_required": True,
                "escalation_reason": "Order creation system failure"
            },
            
            # Database fallbacks
            "database": {
                "success": False,
                "data": None,
                "error": "I'm experiencing database connectivity issues. Please try again in a moment, or I can connect you with support.",
                "error_code": "DATABASE_ERROR",
                "retry_suggested": True
            },
            
            # External API fallbacks
            "external_api": {
                "success": False,
                "data": None,
                "error": "I'm having trouble connecting to external services. Let me try an alternative approach or connect you with support.",
                "error_code": "EXTERNAL_API_ERROR",
                "fallback_available": True
            },
            
            # Vector DB fallbacks
            "vector_db": {
                "success": False,
                "data": None,
                "error": "I'm having trouble accessing our knowledge base. Let me connect you with a human agent who can help answer your questions.",
                "error_code": "KNOWLEDGE_BASE_ERROR",
                "escalation_required": True,
                "escalation_reason": "Knowledge base system failure"
            },
            
            # Payment gateway fallbacks
            "payment_gateway": {
                "success": False,
                "data": None,
                "error": "Our payment system is temporarily unavailable. You can try again in a few minutes, or I can help you complete your order through alternative methods.",
                "error_code": "PAYMENT_GATEWAY_ERROR",
                "escalation_required": True,
                "escalation_reason": "Payment gateway failure",
                "alternative_methods_available": True
            }
        }
    
    def _create_error_summary(self, context: ErrorContext, error: Exception) -> str:
        """Create comprehensive error summary for logging and escalation."""
        duration = time.time() - context.start_time
        
        return (
            f"Operation '{context.operation}' failed after {context.attempt_count} attempts "
            f"over {duration:.2f} seconds. Component: {context.component_type.value}. "
            f"Final error: {type(error).__name__}: {str(error)}"
        )


class EnhancedOperationError(Exception):
    """Enhanced exception with error context for better error handling."""
    
    def __init__(self, message: str, context: ErrorContext, original_error: Exception):
        super().__init__(message)
        self.context = context
        self.original_error = original_error


# Global error handling service instance
error_handling_service = ErrorHandlingService()


def with_error_handling(component_type: ComponentType, operation: str):
    """
    Decorator for adding comprehensive error handling to functions.
    
    Args:
        component_type: Type of component being protected
        operation: Name of the operation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract context from kwargs or create minimal context
            context = ErrorContext(
                tenant_id=kwargs.get('tenant_id', 'unknown'),
                conversation_id=kwargs.get('conversation_id', 'unknown'),
                request_id=kwargs.get('request_id', 'unknown'),
                component_type=component_type,
                operation=operation
            )
            
            return await error_handling_service.execute_with_error_handling(
                lambda: func(*args, **kwargs),
                context
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, create a simple wrapper
            context = ErrorContext(
                tenant_id=kwargs.get('tenant_id', 'unknown'),
                conversation_id=kwargs.get('conversation_id', 'unknown'),
                request_id=kwargs.get('request_id', 'unknown'),
                component_type=component_type,
                operation=operation
            )
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Operation failed: {operation}",
                    extra={
                        'tenant_id': context.tenant_id,
                        'conversation_id': context.conversation_id,
                        'request_id': context.request_id,
                        'component_type': component_type.value,
                        'error': str(e)
                    },
                    exc_info=True
                )
                raise EnhancedOperationError(
                    f"Operation '{operation}' failed: {str(e)}",
                    context,
                    e
                )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator