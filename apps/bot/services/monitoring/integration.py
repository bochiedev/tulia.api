"""
Integration module for monitoring in AI agent service.

Provides convenient wrappers and decorators for integrating
structured logging and metrics collection into the AI agent workflow.
"""
import time
import functools
from typing import Optional, Callable, Any
from decimal import Decimal

from .structured_logger import get_agent_logger
from .metrics_collector import get_metrics_collector
from .alerting import get_alert_manager, get_error_monitor


class AgentMonitor:
    """
    Unified monitoring interface for AI agent operations.
    
    Combines structured logging, metrics collection, and alerting
    into a single convenient interface.
    """
    
    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize agent monitor.
        
        Args:
            tenant_id: Optional tenant ID for tenant-specific monitoring
        """
        self.tenant_id = tenant_id
        self.logger = get_agent_logger()
        self.metrics = get_metrics_collector(tenant_id)
        self.alerts = get_alert_manager(tenant_id)
        self.error_monitor = get_error_monitor(tenant_id)
    
    def log_and_record_interaction(
        self,
        conversation_id: str,
        customer_message: str,
        agent_response: str,
        model_used: str,
        confidence_score: float,
        processing_time_ms: int,
        token_usage: dict,
        estimated_cost: Decimal,
        handoff_triggered: bool = False,
        handoff_reason: str = '',
        **kwargs
    ):
        """
        Log and record a complete agent interaction.
        
        Combines structured logging and metrics collection in one call.
        
        Args:
            conversation_id: Conversation UUID
            customer_message: Customer's message
            agent_response: Agent's response
            model_used: LLM model identifier
            confidence_score: Response confidence
            processing_time_ms: Processing time in milliseconds
            token_usage: Token usage dict
            estimated_cost: Estimated cost
            handoff_triggered: Whether handoff was triggered
            handoff_reason: Reason for handoff
            **kwargs: Additional metadata
        """
        # Log interaction
        self.logger.log_agent_interaction(
            conversation_id=conversation_id,
            tenant_id=str(self.tenant_id) if self.tenant_id else 'unknown',
            customer_message=customer_message,
            agent_response=agent_response,
            model_used=model_used,
            confidence_score=confidence_score,
            processing_time_ms=processing_time_ms,
            token_usage=token_usage,
            estimated_cost=float(estimated_cost),
            handoff_triggered=handoff_triggered,
            handoff_reason=handoff_reason,
            **kwargs
        )
        
        # Record metrics
        self.metrics.record_interaction(
            response_time_ms=processing_time_ms,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
            model_used=model_used,
            handoff_triggered=handoff_triggered,
            handoff_reason=handoff_reason,
            confidence_score=confidence_score
        )
        
        # Record success for error rate monitoring
        self.error_monitor.record_success()
        
        # Check metrics against alert thresholds periodically
        if self.metrics.interaction_count % 10 == 0:
            metrics_data = self.metrics.get_all_metrics()
            self.alerts.check_metrics(metrics_data)
    
    def log_and_record_llm_call(
        self,
        conversation_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        estimated_cost: Decimal,
        response_time_ms: int,
        success: bool = True,
        error: Optional[str] = None,
        **kwargs
    ):
        """
        Log and record an LLM API call.
        
        Args:
            conversation_id: Conversation UUID
            provider: LLM provider name
            model: Model identifier
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            total_tokens: Total tokens
            estimated_cost: Estimated cost
            response_time_ms: Response time in milliseconds
            success: Whether call succeeded
            error: Error message if failed
            **kwargs: Additional metadata
        """
        # Log LLM call
        self.logger.log_llm_call(
            conversation_id=conversation_id,
            tenant_id=str(self.tenant_id) if self.tenant_id else 'unknown',
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=float(estimated_cost),
            response_time_ms=response_time_ms,
            success=success,
            error=error,
            **kwargs
        )
        
        # Record error if failed
        if not success:
            self.error_monitor.record_error(
                error_type='llm_api_error',
                operation=f'{provider}:{model}'
            )
    
    def log_context_building(
        self,
        conversation_id: str,
        context_data: dict,
        build_time_ms: int,
        **kwargs
    ):
        """
        Log context building operation.
        
        Args:
            conversation_id: Conversation UUID
            context_data: Context data dict with counts
            build_time_ms: Build time in milliseconds
            **kwargs: Additional metadata
        """
        self.logger.log_context_building(
            conversation_id=conversation_id,
            tenant_id=str(self.tenant_id) if self.tenant_id else 'unknown',
            history_messages=context_data.get('history_count', 0),
            knowledge_entries=context_data.get('knowledge_count', 0),
            products_count=context_data.get('products_count', 0),
            services_count=context_data.get('services_count', 0),
            orders_count=context_data.get('orders_count', 0),
            appointments_count=context_data.get('appointments_count', 0),
            context_size_tokens=context_data.get('context_size_tokens', 0),
            truncated=context_data.get('truncated', False),
            build_time_ms=build_time_ms,
            **kwargs
        )
    
    def log_handoff_decision(
        self,
        conversation_id: str,
        should_handoff: bool,
        reason: str,
        confidence_score: float,
        consecutive_low_confidence: int,
        **kwargs
    ):
        """
        Log handoff decision.
        
        Args:
            conversation_id: Conversation UUID
            should_handoff: Whether handoff was triggered
            reason: Reason for decision
            confidence_score: Current confidence score
            consecutive_low_confidence: Count of consecutive low-confidence responses
            **kwargs: Additional metadata
        """
        self.logger.log_handoff_decision(
            conversation_id=conversation_id,
            tenant_id=str(self.tenant_id) if self.tenant_id else 'unknown',
            should_handoff=should_handoff,
            reason=reason,
            confidence_score=confidence_score,
            consecutive_low_confidence=consecutive_low_confidence,
            **kwargs
        )
    
    def log_knowledge_search(
        self,
        conversation_id: str,
        query: str,
        results_count: int,
        top_similarity_score: Optional[float] = None,
        search_time_ms: int = 0,
        **kwargs
    ):
        """
        Log knowledge base search.
        
        Args:
            conversation_id: Conversation UUID
            query: Search query
            results_count: Number of results
            top_similarity_score: Top similarity score
            search_time_ms: Search time in milliseconds
            **kwargs: Additional metadata
        """
        # Log search
        self.logger.log_knowledge_search(
            conversation_id=conversation_id,
            tenant_id=str(self.tenant_id) if self.tenant_id else 'unknown',
            query=query,
            results_count=results_count,
            top_similarity_score=top_similarity_score,
            search_time_ms=search_time_ms,
            **kwargs
        )
        
        # Record metrics
        self.metrics.record_knowledge_search(
            results_count=results_count,
            top_similarity_score=top_similarity_score,
            search_time_ms=search_time_ms
        )
    
    def log_error(
        self,
        conversation_id: str,
        error_type: str,
        error_message: str,
        operation: str,
        **kwargs
    ):
        """
        Log error with context.
        
        Args:
            conversation_id: Conversation UUID
            error_type: Type of error
            error_message: Error message
            operation: Operation that failed
            **kwargs: Additional metadata
        """
        # Log error
        self.logger.log_error(
            conversation_id=conversation_id,
            tenant_id=str(self.tenant_id) if self.tenant_id else 'unknown',
            error_type=error_type,
            error_message=error_message,
            operation=operation,
            **kwargs
        )
        
        # Record error for rate monitoring
        self.error_monitor.record_error(
            error_type=error_type,
            operation=operation
        )
    
    def get_metrics_summary(self) -> dict:
        """
        Get current metrics summary.
        
        Returns:
            Dict with all metrics
        """
        return self.metrics.get_all_metrics()


def monitor_operation(operation_name: str):
    """
    Decorator to monitor an operation with timing and error tracking.
    
    Args:
        operation_name: Name of the operation being monitored
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Record success
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                return result
                
            except Exception as e:
                # Record error
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # Re-raise exception
                raise
        
        return wrapper
    return decorator


# Global monitor instances
_monitors: dict = {}


def get_agent_monitor(tenant_id: Optional[str] = None) -> AgentMonitor:
    """
    Get agent monitor instance.
    
    Args:
        tenant_id: Optional tenant ID
        
    Returns:
        AgentMonitor instance
    """
    key = tenant_id or 'global'
    
    if key not in _monitors:
        _monitors[key] = AgentMonitor(tenant_id=tenant_id)
    
    return _monitors[key]
