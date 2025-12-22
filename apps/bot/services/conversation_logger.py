"""
Comprehensive conversation logging and observability service for LangGraph orchestration.

Provides structured logging with tenant_id, customer_id, journey, step context
and request_id tracking throughout conversation flow.
"""
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from django.utils import timezone
from django.db import transaction

from apps.bot.conversation_state import ConversationState
from apps.core.logging import PIIMasker


class ConversationLogger:
    """
    Centralized logging service for conversation flows with structured context.
    
    Provides consistent logging patterns across all LangGraph nodes with:
    - Tenant and customer scoping
    - Journey and step tracking
    - Request ID correlation
    - Performance metrics
    - Error context preservation
    """
    
    def __init__(self, logger_name: str = __name__):
        """Initialize conversation logger."""
        self.logger = logging.getLogger(logger_name)
        self._start_times = {}  # Track operation start times for performance metrics
    
    def _get_base_context(self, state: ConversationState) -> Dict[str, Any]:
        """Extract base logging context from conversation state."""
        return {
            'tenant_id': state.tenant_id,
            'conversation_id': state.conversation_id,
            'request_id': state.request_id,
            'customer_id': state.customer_id,
            'journey': state.journey,
            'intent': state.intent,
            'intent_confidence': state.intent_confidence,
            'turn_count': state.turn_count,
            'response_language': state.response_language,
        }
    
    def log_conversation_start(self, state: ConversationState, message_text: str):
        """Log conversation initiation."""
        context = self._get_base_context(state)
        context.update({
            'event': 'conversation_start',
            'message_length': len(message_text) if message_text else 0,
            'tenant_name': state.tenant_name,
            'bot_name': state.bot_name,
        })
        
        self.logger.info(
            f"Conversation started for tenant {state.tenant_name}",
            extra=context
        )
    
    def log_journey_transition(
        self, 
        state: ConversationState, 
        from_journey: str, 
        to_journey: str,
        reason: str = None
    ):
        """Log journey transitions for analytics."""
        context = self._get_base_context(state)
        context.update({
            'event': 'journey_transition',
            'from_journey': from_journey,
            'to_journey': to_journey,
            'transition_reason': reason,
        })
        
        self.logger.info(
            f"Journey transition: {from_journey} -> {to_journey}",
            extra=context
        )
    
    def log_node_execution_start(
        self, 
        state: ConversationState, 
        node_name: str,
        step: str = None,
        **additional_context
    ):
        """Log start of node execution with performance tracking."""
        operation_id = f"{state.conversation_id}:{node_name}:{int(time.time() * 1000)}"
        self._start_times[operation_id] = time.time()
        
        context = self._get_base_context(state)
        context.update({
            'event': 'node_execution_start',
            'node_name': node_name,
            'step': step,
            'operation_id': operation_id,
            **additional_context
        })
        
        self.logger.debug(
            f"Starting {node_name} execution",
            extra=context
        )
        
        return operation_id
    
    def log_node_execution_end(
        self, 
        state: ConversationState, 
        node_name: str,
        operation_id: str,
        success: bool = True,
        error: Exception = None,
        **additional_context
    ):
        """Log end of node execution with performance metrics."""
        start_time = self._start_times.pop(operation_id, time.time())
        execution_time = time.time() - start_time
        
        context = self._get_base_context(state)
        context.update({
            'event': 'node_execution_end',
            'node_name': node_name,
            'operation_id': operation_id,
            'execution_time_ms': round(execution_time * 1000, 2),
            'success': success,
            **additional_context
        })
        
        if error:
            context['error_type'] = type(error).__name__
            context['error_message'] = PIIMasker.mask_text(str(error))
        
        log_level = 'info' if success else 'error'
        log_method = getattr(self.logger, log_level)
        
        log_method(
            f"Completed {node_name} execution in {execution_time:.3f}s",
            extra=context,
            exc_info=error if error else None
        )
    
    def log_tool_call_start(
        self, 
        state: ConversationState, 
        tool_name: str,
        tool_args: Dict[str, Any] = None
    ):
        """Log start of tool call with sanitized arguments."""
        operation_id = f"{state.conversation_id}:{tool_name}:{int(time.time() * 1000)}"
        self._start_times[operation_id] = time.time()
        
        context = self._get_base_context(state)
        context.update({
            'event': 'tool_call_start',
            'tool_name': tool_name,
            'operation_id': operation_id,
        })
        
        # Sanitize tool arguments for logging
        if tool_args:
            context['tool_args'] = PIIMasker.mask_dict(tool_args)
        
        self.logger.debug(
            f"Starting {tool_name} tool call",
            extra=context
        )
        
        return operation_id
    
    def log_tool_call_end(
        self, 
        state: ConversationState, 
        tool_name: str,
        operation_id: str,
        success: bool = True,
        error: Exception = None,
        result_summary: str = None
    ):
        """Log end of tool call with performance metrics."""
        start_time = self._start_times.pop(operation_id, time.time())
        execution_time = time.time() - start_time
        
        context = self._get_base_context(state)
        context.update({
            'event': 'tool_call_end',
            'tool_name': tool_name,
            'operation_id': operation_id,
            'execution_time_ms': round(execution_time * 1000, 2),
            'success': success,
        })
        
        if result_summary:
            context['result_summary'] = result_summary
        
        if error:
            context['error_type'] = type(error).__name__
            context['error_message'] = PIIMasker.mask_text(str(error))
        
        log_level = 'info' if success else 'error'
        log_method = getattr(self.logger, log_level)
        
        log_method(
            f"Completed {tool_name} tool call in {execution_time:.3f}s",
            extra=context,
            exc_info=error if error else None
        )
    
    def log_llm_call_start(
        self, 
        state: ConversationState, 
        llm_node: str,
        prompt_type: str = None,
        model: str = None
    ):
        """Log start of LLM call."""
        operation_id = f"{state.conversation_id}:{llm_node}:{int(time.time() * 1000)}"
        self._start_times[operation_id] = time.time()
        
        context = self._get_base_context(state)
        context.update({
            'event': 'llm_call_start',
            'llm_node': llm_node,
            'prompt_type': prompt_type,
            'model': model,
            'operation_id': operation_id,
        })
        
        self.logger.debug(
            f"Starting {llm_node} LLM call",
            extra=context
        )
        
        return operation_id
    
    def log_llm_call_end(
        self, 
        state: ConversationState, 
        llm_node: str,
        operation_id: str,
        success: bool = True,
        error: Exception = None,
        token_usage: Dict[str, int] = None,
        confidence: float = None
    ):
        """Log end of LLM call with performance and usage metrics."""
        start_time = self._start_times.pop(operation_id, time.time())
        execution_time = time.time() - start_time
        
        context = self._get_base_context(state)
        context.update({
            'event': 'llm_call_end',
            'llm_node': llm_node,
            'operation_id': operation_id,
            'execution_time_ms': round(execution_time * 1000, 2),
            'success': success,
        })
        
        if token_usage:
            context['token_usage'] = token_usage
        
        if confidence is not None:
            context['confidence'] = confidence
        
        if error:
            context['error_type'] = type(error).__name__
            context['error_message'] = PIIMasker.mask_text(str(error))
        
        log_level = 'info' if success else 'error'
        log_method = getattr(self.logger, log_level)
        
        log_method(
            f"Completed {llm_node} LLM call in {execution_time:.3f}s",
            extra=context,
            exc_info=error if error else None
        )
    
    def log_escalation_triggered(
        self, 
        state: ConversationState, 
        reason: str,
        priority: str,
        category: str,
        ticket_id: str = None
    ):
        """Log escalation events with full context."""
        context = self._get_base_context(state)
        context.update({
            'event': 'escalation_triggered',
            'escalation_reason': reason,
            'escalation_priority': priority,
            'escalation_category': category,
            'ticket_id': ticket_id,
            'escalation_required': True,
        })
        
        self.logger.warning(
            f"Escalation triggered: {reason}",
            extra=context
        )
    
    def log_conversation_end(
        self, 
        state: ConversationState, 
        completion_reason: str,
        success: bool = True
    ):
        """Log conversation completion with summary metrics."""
        context = self._get_base_context(state)
        context.update({
            'event': 'conversation_end',
            'completion_reason': completion_reason,
            'success': success,
            'final_journey': state.journey,
            'total_turns': state.turn_count,
            'casual_turns': state.casual_turns,
            'spam_turns': state.spam_turns,
            'escalated': state.escalation_required,
        })
        
        # Add order/payment context if available
        if state.order_id:
            context['order_created'] = True
            context['order_id'] = state.order_id
            context['payment_status'] = state.payment_status
        
        self.logger.info(
            f"Conversation completed: {completion_reason}",
            extra=context
        )
    
    def log_error_with_context(
        self, 
        state: ConversationState, 
        error: Exception,
        component: str,
        operation: str = None,
        **additional_context
    ):
        """Log errors with full conversation context for debugging."""
        context = self._get_base_context(state)
        context.update({
            'event': 'error_occurred',
            'component': component,
            'operation': operation,
            'error_type': type(error).__name__,
            'error_message': PIIMasker.mask_text(str(error)),
            **additional_context
        })
        
        self.logger.error(
            f"Error in {component}: {str(error)}",
            extra=context,
            exc_info=error
        )
    
    def log_state_transition(
        self, 
        state: ConversationState, 
        field_name: str,
        old_value: Any,
        new_value: Any
    ):
        """Log important state transitions for debugging."""
        context = self._get_base_context(state)
        context.update({
            'event': 'state_transition',
            'field_name': field_name,
            'old_value': str(old_value) if old_value is not None else None,
            'new_value': str(new_value) if new_value is not None else None,
        })
        
        self.logger.debug(
            f"State transition: {field_name} = {old_value} -> {new_value}",
            extra=context
        )


# Global conversation logger instance
conversation_logger = ConversationLogger('apps.bot.conversation')