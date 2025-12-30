"""
Observability and monitoring service for comprehensive system tracking.

This module implements structured logging, metrics collection, and
monitoring integration for real-time system health tracking.

Requirements: 10.1, 10.4, 10.5
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected by the system."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ConversationMetrics:
    """Metrics for conversation tracking."""
    tenant_id: str
    conversation_id: str
    request_id: str
    customer_id: Optional[str] = None
    
    # Journey metrics
    journey_started: Optional[str] = None
    journey_completed: Optional[str] = None
    journey_duration: Optional[float] = None
    journey_success: bool = False
    
    # Node execution metrics
    nodes_executed: List[str] = field(default_factory=list)
    node_durations: Dict[str, float] = field(default_factory=dict)
    node_failures: List[str] = field(default_factory=list)
    
    # Tool execution metrics
    tools_called: List[str] = field(default_factory=list)
    tool_durations: Dict[str, float] = field(default_factory=dict)
    tool_failures: List[str] = field(default_factory=list)
    
    # Business metrics
    products_viewed: int = 0
    orders_created: int = 0
    payments_initiated: int = 0
    payments_completed: int = 0
    escalations_triggered: int = 0
    
    # Error metrics
    total_errors: int = 0
    retry_attempts: int = 0
    fallbacks_used: int = 0
    
    # Timing metrics
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration: Optional[float] = None


@dataclass
class SystemHealthMetrics:
    """System-wide health metrics."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Performance metrics
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Success rates
    journey_completion_rate: float = 0.0
    payment_success_rate: float = 0.0
    tool_success_rate: float = 0.0
    
    # Error rates
    error_rate: float = 0.0
    escalation_rate: float = 0.0
    fallback_usage_rate: float = 0.0
    
    # Volume metrics
    total_conversations: int = 0
    active_conversations: int = 0
    messages_per_hour: int = 0


class ObservabilityService:
    """
    Central service for observability, monitoring, and metrics collection.
    
    Provides structured logging, metrics tracking, and integration
    with monitoring systems for real-time system health visibility.
    """
    
    def __init__(self):
        """Initialize observability service."""
        self.conversation_metrics: Dict[str, ConversationMetrics] = {}
        self.system_metrics = SystemHealthMetrics()
        self.structured_logger = self._setup_structured_logger()
    
    def _setup_structured_logger(self) -> logging.Logger:
        """Set up structured logging with JSON formatting."""
        structured_logger = logging.getLogger("tulia.structured")
        
        # Create JSON formatter
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                
                # Add extra fields if present
                if hasattr(record, 'tenant_id'):
                    log_entry["tenant_id"] = record.tenant_id
                if hasattr(record, 'conversation_id'):
                    log_entry["conversation_id"] = record.conversation_id
                if hasattr(record, 'request_id'):
                    log_entry["request_id"] = record.request_id
                if hasattr(record, 'customer_id'):
                    log_entry["customer_id"] = record.customer_id
                if hasattr(record, 'journey'):
                    log_entry["journey"] = record.journey
                if hasattr(record, 'node_name'):
                    log_entry["node_name"] = record.node_name
                if hasattr(record, 'tool_name'):
                    log_entry["tool_name"] = record.tool_name
                if hasattr(record, 'duration'):
                    log_entry["duration"] = record.duration
                if hasattr(record, 'error_type'):
                    log_entry["error_type"] = record.error_type
                if hasattr(record, 'escalation_reason'):
                    log_entry["escalation_reason"] = record.escalation_reason
                
                # Add exception info if present
                if record.exc_info:
                    log_entry["exception"] = self.formatException(record.exc_info)
                
                return json.dumps(log_entry)
        
        # Set up handler with JSON formatter
        if not structured_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(JSONFormatter())
            structured_logger.addHandler(handler)
            structured_logger.setLevel(logging.INFO)
        
        return structured_logger
    
    def start_conversation_tracking(self, 
                                  tenant_id: str, 
                                  conversation_id: str, 
                                  request_id: str,
                                  customer_id: Optional[str] = None) -> ConversationMetrics:
        """
        Start tracking metrics for a conversation.
        
        Args:
            tenant_id: Tenant identifier
            conversation_id: Conversation identifier
            request_id: Request identifier
            customer_id: Customer identifier (optional)
            
        Returns:
            ConversationMetrics instance for tracking
        """
        metrics = ConversationMetrics(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=request_id,
            customer_id=customer_id
        )
        
        self.conversation_metrics[conversation_id] = metrics
        
        self.structured_logger.info(
            "Conversation tracking started",
            extra={
                'tenant_id': tenant_id,
                'conversation_id': conversation_id,
                'request_id': request_id,
                'customer_id': customer_id
            }
        )
        
        return metrics
    
    def track_journey_start(self, conversation_id: str, journey: str):
        """Track the start of a journey."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.journey_started = journey
            
            self.structured_logger.info(
                "Journey started",
                extra={
                    'tenant_id': metrics.tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': metrics.request_id,
                    'journey': journey
                }
            )
    
    def track_journey_completion(self, conversation_id: str, journey: str, success: bool):
        """Track the completion of a journey."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.journey_completed = journey
            metrics.journey_success = success
            
            if metrics.journey_started == journey:
                metrics.journey_duration = time.time() - metrics.start_time
            
            self.structured_logger.info(
                "Journey completed",
                extra={
                    'tenant_id': metrics.tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': metrics.request_id,
                    'journey': journey,
                    'success': success,
                    'duration': metrics.journey_duration
                }
            )
    
    def track_node_execution(self, conversation_id: str, node_name: str, duration: float, success: bool):
        """Track node execution metrics."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.nodes_executed.append(node_name)
            metrics.node_durations[node_name] = duration
            
            if not success:
                metrics.node_failures.append(node_name)
                metrics.total_errors += 1
            
            self.structured_logger.info(
                "Node executed",
                extra={
                    'tenant_id': metrics.tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': metrics.request_id,
                    'node_name': node_name,
                    'duration': duration,
                    'success': success
                }
            )
    
    def track_tool_execution(self, conversation_id: str, tool_name: str, duration: float, success: bool):
        """Track tool execution metrics."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.tools_called.append(tool_name)
            metrics.tool_durations[tool_name] = duration
            
            if not success:
                metrics.tool_failures.append(tool_name)
                metrics.total_errors += 1
            
            self.structured_logger.info(
                "Tool executed",
                extra={
                    'tenant_id': metrics.tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': metrics.request_id,
                    'tool_name': tool_name,
                    'duration': duration,
                    'success': success
                }
            )
    
    def track_business_event(self, conversation_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
        """Track business events like orders, payments, etc."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            
            # Update relevant counters
            if event_type == "product_viewed":
                metrics.products_viewed += 1
            elif event_type == "order_created":
                metrics.orders_created += 1
            elif event_type == "payment_initiated":
                metrics.payments_initiated += 1
            elif event_type == "payment_completed":
                metrics.payments_completed += 1
            elif event_type == "escalation_triggered":
                metrics.escalations_triggered += 1
            
            log_extra = {
                'tenant_id': metrics.tenant_id,
                'conversation_id': conversation_id,
                'request_id': metrics.request_id,
                'event_type': event_type
            }
            
            if details:
                log_extra.update(details)
            
            self.structured_logger.info(
                "Business event tracked",
                extra=log_extra
            )
    
    def track_error(self, conversation_id: str, error_type: str, error_message: str, 
                   component: str, retry_count: int = 0, fallback_used: bool = False):
        """Track error occurrences and recovery attempts."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.total_errors += 1
            metrics.retry_attempts += retry_count
            
            if fallback_used:
                metrics.fallbacks_used += 1
        
        self.structured_logger.error(
            "Error tracked",
            extra={
                'tenant_id': self.conversation_metrics.get(conversation_id, ConversationMetrics("", "", "")).tenant_id,
                'conversation_id': conversation_id,
                'request_id': self.conversation_metrics.get(conversation_id, ConversationMetrics("", "", "")).request_id,
                'error_type': error_type,
                'error_message': error_message,
                'component': component,
                'retry_count': retry_count,
                'fallback_used': fallback_used
            }
        )
    
    def track_escalation(self, conversation_id: str, escalation_reason: str, context: Dict[str, Any]):
        """Track escalation events."""
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.escalations_triggered += 1
        
        log_extra = {
            'tenant_id': self.conversation_metrics.get(conversation_id, ConversationMetrics("", "", "")).tenant_id,
            'conversation_id': conversation_id,
            'request_id': self.conversation_metrics.get(conversation_id, ConversationMetrics("", "", "")).request_id,
            'escalation_reason': escalation_reason
        }
        log_extra.update(context)
        
        self.structured_logger.warning(
            "Escalation triggered",
            extra=log_extra
        )
    
    def end_conversation_tracking(self, conversation_id: str) -> Optional[ConversationMetrics]:
        """
        End conversation tracking and return final metrics.
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            Final conversation metrics or None if not found
        """
        if conversation_id in self.conversation_metrics:
            metrics = self.conversation_metrics[conversation_id]
            metrics.end_time = time.time()
            metrics.total_duration = metrics.end_time - metrics.start_time
            
            self.structured_logger.info(
                "Conversation tracking ended",
                extra={
                    'tenant_id': metrics.tenant_id,
                    'conversation_id': conversation_id,
                    'request_id': metrics.request_id,
                    'total_duration': metrics.total_duration,
                    'journey_success': metrics.journey_success,
                    'total_errors': metrics.total_errors,
                    'escalations_triggered': metrics.escalations_triggered
                }
            )
            
            # Remove from active tracking
            final_metrics = self.conversation_metrics.pop(conversation_id)
            return final_metrics
        
        return None
    
    def get_conversation_metrics(self, conversation_id: str) -> Optional[ConversationMetrics]:
        """Get current metrics for a conversation."""
        return self.conversation_metrics.get(conversation_id)
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Get current system health summary.
        
        Returns:
            Dictionary with system health metrics
        """
        active_conversations = len(self.conversation_metrics)
        
        # Calculate aggregate metrics from active conversations
        total_errors = sum(m.total_errors for m in self.conversation_metrics.values())
        total_escalations = sum(m.escalations_triggered for m in self.conversation_metrics.values())
        total_fallbacks = sum(m.fallbacks_used for m in self.conversation_metrics.values())
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_conversations": active_conversations,
            "total_errors": total_errors,
            "total_escalations": total_escalations,
            "total_fallbacks": total_fallbacks,
            "error_rate": total_errors / max(active_conversations, 1),
            "escalation_rate": total_escalations / max(active_conversations, 1),
            "fallback_usage_rate": total_fallbacks / max(active_conversations, 1)
        }
    
    def log_structured(self, level: LogLevel, message: str, **kwargs):
        """
        Log structured message with context.
        
        Args:
            level: Log level
            message: Log message
            **kwargs: Additional context fields
        """
        log_method = getattr(self.structured_logger, level.value)
        log_method(message, extra=kwargs)


# Global observability service instance
observability_service = ObservabilityService()


class ConversationTracker:
    """Context manager for conversation tracking."""
    
    def __init__(self, tenant_id: str, conversation_id: str, request_id: str, customer_id: Optional[str] = None):
        """Initialize conversation tracker."""
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id
        self.request_id = request_id
        self.customer_id = customer_id
        self.metrics: Optional[ConversationMetrics] = None
    
    def __enter__(self) -> ConversationMetrics:
        """Start conversation tracking."""
        self.metrics = observability_service.start_conversation_tracking(
            self.tenant_id, self.conversation_id, self.request_id, self.customer_id
        )
        return self.metrics
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End conversation tracking."""
        if exc_type:
            # Track error if exception occurred
            observability_service.track_error(
                self.conversation_id,
                exc_type.__name__,
                str(exc_val),
                "conversation_tracker"
            )
        
        observability_service.end_conversation_tracking(self.conversation_id)


def track_performance(operation_name: str):
    """
    Decorator for tracking operation performance.
    
    Args:
        operation_name: Name of the operation being tracked
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            conversation_id = kwargs.get('conversation_id', 'unknown')
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track successful execution
                if 'node' in operation_name.lower():
                    observability_service.track_node_execution(
                        conversation_id, operation_name, duration, True
                    )
                elif 'tool' in operation_name.lower():
                    observability_service.track_tool_execution(
                        conversation_id, operation_name, duration, True
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Track failed execution
                if 'node' in operation_name.lower():
                    observability_service.track_node_execution(
                        conversation_id, operation_name, duration, False
                    )
                elif 'tool' in operation_name.lower():
                    observability_service.track_tool_execution(
                        conversation_id, operation_name, duration, False
                    )
                
                raise e
        
        return wrapper
    return decorator