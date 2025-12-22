"""
Enhanced logging service for comprehensive system observability.

This module extends the existing logging infrastructure with additional
structured logging capabilities, request tracking, and monitoring integration.

Requirements: 10.1, 10.4, 10.5
"""

import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import threading
from contextlib import contextmanager

from apps.core.logging import JSONFormatter, PIIMasker, SecurityLogger
from apps.bot.services.observability import observability_service, ConversationMetrics


class LogContext(Enum):
    """Log context types for categorizing log entries."""
    CONVERSATION = "conversation"
    JOURNEY = "journey"
    NODE_EXECUTION = "node_execution"
    TOOL_EXECUTION = "tool_execution"
    PAYMENT = "payment"
    ESCALATION = "escalation"
    ERROR = "error"
    PERFORMANCE = "performance"
    BUSINESS_EVENT = "business_event"
    SYSTEM_HEALTH = "system_health"


@dataclass
class RequestContext:
    """Request context for tracking throughout conversation flow."""
    request_id: str
    tenant_id: str
    conversation_id: str
    customer_id: Optional[str] = None
    phone_e164: Optional[str] = None
    journey: Optional[str] = None
    step: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'request_id': self.request_id,
            'tenant_id': self.tenant_id,
            'conversation_id': self.conversation_id,
            'customer_id': self.customer_id,
            'phone_e164': self.phone_e164,
            'journey': self.journey,
            'step': self.step,
            'request_duration': time.time() - self.start_time
        }


class EnhancedLoggingService:
    """
    Enhanced logging service with comprehensive observability features.
    
    Provides structured logging with tenant_id, customer_id, journey, and step context,
    request_id tracking throughout conversation flow, and integration with monitoring systems.
    """
    
    def __init__(self):
        """Initialize enhanced logging service."""
        self.logger = logging.getLogger("tulia.enhanced")
        self.performance_logger = logging.getLogger("tulia.performance")
        self.business_logger = logging.getLogger("tulia.business")
        self.error_logger = logging.getLogger("tulia.error")
        
        # Thread-local storage for request context
        self._local = threading.local()
        
        # Setup specialized loggers
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Set up specialized loggers with appropriate formatters."""
        # Enhanced JSON formatter with additional context
        class EnhancedJSONFormatter(JSONFormatter):
            def format(self, record):
                # Get base JSON log entry
                log_entry = json.loads(super().format(record))
                
                # Add request context if available
                if hasattr(self, '_local') and hasattr(self._local, 'request_context'):
                    context = self._local.request_context
                    log_entry.update(context.to_dict())
                
                # Add log context type
                if hasattr(record, 'log_context'):
                    log_entry['log_context'] = record.log_context.value
                
                # Add performance metrics
                if hasattr(record, 'performance_metrics'):
                    log_entry['performance_metrics'] = record.performance_metrics
                
                # Add business metrics
                if hasattr(record, 'business_metrics'):
                    log_entry['business_metrics'] = record.business_metrics
                
                return json.dumps(log_entry)
        
        # Set up formatters for different logger types
        formatter = EnhancedJSONFormatter()
        
        # Configure main logger
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Configure performance logger
        if not self.performance_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.performance_logger.addHandler(handler)
            self.performance_logger.setLevel(logging.INFO)
        
        # Configure business logger
        if not self.business_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.business_logger.addHandler(handler)
            self.business_logger.setLevel(logging.INFO)
        
        # Configure error logger
        if not self.error_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.error_logger.addHandler(handler)
            self.error_logger.setLevel(logging.WARNING)
    
    def set_request_context(self, context: RequestContext):
        """Set request context for current thread."""
        self._local.request_context = context
    
    def get_request_context(self) -> Optional[RequestContext]:
        """Get current request context."""
        return getattr(self._local, 'request_context', None)
    
    def clear_request_context(self):
        """Clear request context for current thread."""
        if hasattr(self._local, 'request_context'):
            delattr(self._local, 'request_context')
    
    @contextmanager
    def request_context(self, tenant_id: str, conversation_id: str, request_id: str = None,
                       customer_id: str = None, phone_e164: str = None):
        """Context manager for request tracking."""
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        context = RequestContext(
            request_id=request_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            phone_e164=phone_e164
        )
        
        self.set_request_context(context)
        try:
            yield context
        finally:
            self.clear_request_context()
    
    def log_conversation_start(self, tenant_id: str, conversation_id: str, request_id: str,
                              customer_id: str = None, phone_e164: str = None, message_text: str = None):
        """Log conversation start with full context."""
        self.logger.info(
            "Conversation started",
            extra={
                'log_context': LogContext.CONVERSATION,
                'tenant_id': tenant_id,
                'conversation_id': conversation_id,
                'request_id': request_id,
                'customer_id': customer_id,
                'phone_e164': PIIMasker.mask_phone(phone_e164) if phone_e164 else None,
                'message_length': len(message_text) if message_text else 0,
                'event_type': 'conversation_start'
            }
        )
    
    def log_journey_transition(self, conversation_id: str, previous_journey: str, 
                              new_journey: str, reason: str, confidence: float = None,
                              metadata: Dict[str, Any] = None):
        """Log journey transitions with detailed context."""
        self.logger.info(
            f"Journey transition: {previous_journey} -> {new_journey}",
            extra={
                'log_context': LogContext.JOURNEY,
                'conversation_id': conversation_id,
                'previous_journey': previous_journey,
                'new_journey': new_journey,
                'transition_reason': reason,
                'transition_confidence': confidence,
                'transition_metadata': metadata or {},
                'event_type': 'journey_transition'
            }
        )
    
    def log_node_execution(self, node_name: str, conversation_id: str, 
                          duration: float, success: bool, error: str = None,
                          input_data: Dict[str, Any] = None, output_data: Dict[str, Any] = None):
        """Log LLM node execution with performance metrics."""
        performance_metrics = {
            'duration_ms': duration * 1000,
            'success': success,
            'node_type': 'llm_node' if any(x in node_name.lower() for x in ['intent', 'language', 'governor']) else 'workflow_node'
        }
        
        if error:
            performance_metrics['error'] = error
        
        log_level = logging.INFO if success else logging.ERROR
        message = f"Node executed: {node_name}"
        
        self.performance_logger.log(
            log_level,
            message,
            extra={
                'log_context': LogContext.NODE_EXECUTION,
                'conversation_id': conversation_id,
                'node_name': node_name,
                'performance_metrics': performance_metrics,
                'input_size': len(str(input_data)) if input_data else 0,
                'output_size': len(str(output_data)) if output_data else 0,
                'event_type': 'node_execution'
            }
        )
        
        # Track in observability service
        observability_service.track_node_execution(conversation_id, node_name, duration, success)
    
    def log_tool_execution(self, tool_name: str, conversation_id: str,
                          duration: float, success: bool, error: str = None,
                          request_data: Dict[str, Any] = None, response_data: Dict[str, Any] = None):
        """Log tool call execution with performance metrics."""
        performance_metrics = {
            'duration_ms': duration * 1000,
            'success': success,
            'tool_category': self._categorize_tool(tool_name)
        }
        
        if error:
            performance_metrics['error'] = error
        
        # Mask sensitive data in request/response
        masked_request = PIIMasker.mask_dict(request_data) if request_data else None
        masked_response = PIIMasker.mask_dict(response_data) if response_data else None
        
        log_level = logging.INFO if success else logging.ERROR
        message = f"Tool executed: {tool_name}"
        
        self.performance_logger.log(
            log_level,
            message,
            extra={
                'log_context': LogContext.TOOL_EXECUTION,
                'conversation_id': conversation_id,
                'tool_name': tool_name,
                'performance_metrics': performance_metrics,
                'request_data': masked_request,
                'response_data': masked_response,
                'event_type': 'tool_execution'
            }
        )
        
        # Track in observability service
        observability_service.track_tool_execution(conversation_id, tool_name, duration, success)
    
    def log_payment_event(self, conversation_id: str, event_type: str, 
                         payment_method: str = None, amount: float = None,
                         currency: str = None, status: str = None, 
                         transaction_id: str = None, error: str = None):
        """Log payment-related events with business metrics."""
        business_metrics = {
            'event_type': event_type,
            'payment_method': payment_method,
            'amount': amount,
            'currency': currency,
            'status': status,
            'transaction_id': transaction_id
        }
        
        if error:
            business_metrics['error'] = error
        
        log_level = logging.INFO if not error else logging.ERROR
        message = f"Payment event: {event_type}"
        
        self.business_logger.log(
            log_level,
            message,
            extra={
                'log_context': LogContext.PAYMENT,
                'conversation_id': conversation_id,
                'business_metrics': business_metrics,
                'event_type': 'payment_event'
            }
        )
        
        # Track business event in observability service
        observability_service.track_business_event(
            conversation_id, 
            f"payment_{event_type}",
            business_metrics
        )
    
    def log_escalation_event(self, conversation_id: str, escalation_reason: str,
                           escalation_trigger: str = None, ticket_id: str = None,
                           context: Dict[str, Any] = None):
        """Log escalation events with comprehensive context."""
        escalation_data = {
            'escalation_reason': escalation_reason,
            'escalation_trigger': escalation_trigger,
            'ticket_id': ticket_id,
            'context': context or {}
        }
        
        self.logger.warning(
            f"Escalation triggered: {escalation_reason}",
            extra={
                'log_context': LogContext.ESCALATION,
                'conversation_id': conversation_id,
                'escalation_data': escalation_data,
                'event_type': 'escalation'
            }
        )
        
        # Track escalation in observability service
        observability_service.track_escalation(conversation_id, escalation_reason, escalation_data)
    
    def log_business_event(self, conversation_id: str, event_type: str,
                          details: Dict[str, Any] = None):
        """Log business events like product views, cart additions, etc."""
        business_metrics = {
            'event_type': event_type,
            'details': details or {}
        }
        
        self.business_logger.info(
            f"Business event: {event_type}",
            extra={
                'log_context': LogContext.BUSINESS_EVENT,
                'conversation_id': conversation_id,
                'business_metrics': business_metrics,
                'event_type': 'business_event'
            }
        )
        
        # Track in observability service
        observability_service.track_business_event(conversation_id, event_type, details)
    
    def log_error(self, conversation_id: str, error_type: str, error_message: str,
                 component: str, stack_trace: str = None, context: Dict[str, Any] = None,
                 retry_count: int = 0, fallback_used: bool = False):
        """Log errors with comprehensive context and recovery information."""
        error_data = {
            'error_type': error_type,
            'error_message': PIIMasker.mask_text(error_message),
            'component': component,
            'stack_trace': PIIMasker.mask_text(stack_trace) if stack_trace else None,
            'context': PIIMasker.mask_dict(context) if context else {},
            'retry_count': retry_count,
            'fallback_used': fallback_used
        }
        
        self.error_logger.error(
            f"Error in {component}: {error_type}",
            extra={
                'log_context': LogContext.ERROR,
                'conversation_id': conversation_id,
                'error_data': error_data,
                'event_type': 'error'
            }
        )
        
        # Track error in observability service
        observability_service.track_error(
            conversation_id, error_type, error_message, component, retry_count, fallback_used
        )
    
    def log_performance_metrics(self, operation: str, duration: float, 
                               success: bool, metadata: Dict[str, Any] = None):
        """Log performance metrics for operations."""
        performance_data = {
            'operation': operation,
            'duration_ms': duration * 1000,
            'success': success,
            'metadata': metadata or {}
        }
        
        self.performance_logger.info(
            f"Performance metric: {operation}",
            extra={
                'log_context': LogContext.PERFORMANCE,
                'performance_metrics': performance_data,
                'event_type': 'performance_metric'
            }
        )
    
    def log_system_health(self, health_data: Dict[str, Any]):
        """Log system health metrics."""
        self.logger.info(
            "System health update",
            extra={
                'log_context': LogContext.SYSTEM_HEALTH,
                'health_data': health_data,
                'event_type': 'system_health'
            }
        )
    
    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize tool by name for metrics."""
        if 'catalog' in tool_name.lower():
            return 'catalog'
        elif 'payment' in tool_name.lower():
            return 'payment'
        elif 'order' in tool_name.lower():
            return 'order'
        elif 'customer' in tool_name.lower():
            return 'customer'
        elif 'tenant' in tool_name.lower():
            return 'tenant'
        elif 'kb' in tool_name.lower() or 'knowledge' in tool_name.lower():
            return 'knowledge'
        elif 'handoff' in tool_name.lower():
            return 'handoff'
        elif 'offers' in tool_name.lower():
            return 'offers'
        else:
            return 'other'


# Global enhanced logging service instance
enhanced_logging_service = EnhancedLoggingService()


def with_request_tracking(tenant_id: str, conversation_id: str, request_id: str = None,
                         customer_id: str = None, phone_e164: str = None):
    """Decorator for automatic request context tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with enhanced_logging_service.request_context(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                customer_id=customer_id,
                phone_e164=phone_e164
            ) as context:
                # Add context to kwargs if function accepts it
                if 'request_context' in func.__code__.co_varnames:
                    kwargs['request_context'] = context
                
                return func(*args, **kwargs)
        return wrapper
    return decorator


@contextmanager
def performance_tracking(operation_name: str, conversation_id: str = None):
    """Context manager for tracking operation performance."""
    start_time = time.time()
    success = True
    error = None
    
    try:
        yield
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        duration = time.time() - start_time
        
        if conversation_id:
            enhanced_logging_service.log_performance_metrics(
                operation_name, duration, success, {'error': error} if error else None
            )