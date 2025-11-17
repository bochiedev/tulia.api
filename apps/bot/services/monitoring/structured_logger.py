"""
Structured logging for AI agent interactions.

Provides JSON-formatted structured logging for all agent operations including:
- Agent interactions with full context
- LLM API calls and responses
- Context building steps
- Handoff decisions with reasons
- Performance metrics
- Error tracking
"""
import logging
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from django.utils import timezone


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Converts log records to JSON format with consistent structure
    for easy parsing and analysis.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: LogRecord to format
            
        Returns:
            JSON-formatted log string
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        # Convert Decimal to float for JSON serialization
        log_data = self._convert_decimals(log_data)
        
        return json.dumps(log_data)
    
    def _convert_decimals(self, obj: Any) -> Any:
        """
        Recursively convert Decimal objects to float for JSON serialization.
        
        Args:
            obj: Object to convert
            
        Returns:
            Converted object
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals(item) for item in obj]
        return obj


class StructuredLogger:
    """
    Structured logger for AI agent operations.
    
    Provides methods for logging different types of agent events
    with consistent structure and rich context.
    """
    
    def __init__(self, logger_name: str = 'apps.bot.agent'):
        """
        Initialize structured logger.
        
        Args:
            logger_name: Name for the logger instance
        """
        self.logger = logging.getLogger(logger_name)
        self._setup_json_handler()
    
    def _setup_json_handler(self):
        """Set up JSON handler if not already configured."""
        # Check if JSON handler already exists
        has_json_handler = any(
            isinstance(handler.formatter, JSONFormatter)
            for handler in self.logger.handlers
        )
        
        if not has_json_handler and not self.logger.handlers:
            # Add JSON handler
            handler = logging.StreamHandler()
            handler.setFormatter(JSONFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_agent_interaction(
        self,
        conversation_id: str,
        tenant_id: str,
        customer_message: str,
        agent_response: str,
        model_used: str,
        confidence_score: float,
        processing_time_ms: int,
        token_usage: Dict[str, int],
        estimated_cost: float,
        handoff_triggered: bool = False,
        handoff_reason: str = '',
        detected_intents: Optional[list] = None,
        message_type: str = 'text',
        context_size_tokens: int = 0,
        context_truncated: bool = False,
        **kwargs
    ):
        """
        Log complete agent interaction with structured data.
        
        Args:
            conversation_id: Conversation UUID
            tenant_id: Tenant UUID
            customer_message: Customer's message text
            agent_response: Agent's response text
            model_used: LLM model identifier
            confidence_score: Response confidence (0.0-1.0)
            processing_time_ms: Processing time in milliseconds
            token_usage: Dict with prompt_tokens, completion_tokens, total_tokens
            estimated_cost: Estimated cost in USD
            handoff_triggered: Whether handoff was triggered
            handoff_reason: Reason for handoff if triggered
            detected_intents: List of detected intents
            message_type: Type of message (text, button, list, media)
            context_size_tokens: Size of context in tokens
            context_truncated: Whether context was truncated
            **kwargs: Additional metadata
        """
        extra_data = {
            'event_type': 'agent_interaction',
            'conversation_id': str(conversation_id),
            'tenant_id': str(tenant_id),
            'customer_message_length': len(customer_message),
            'agent_response_length': len(agent_response),
            'model_used': model_used,
            'confidence_score': confidence_score,
            'processing_time_ms': processing_time_ms,
            'token_usage': token_usage,
            'estimated_cost': estimated_cost,
            'handoff_triggered': handoff_triggered,
            'handoff_reason': handoff_reason,
            'detected_intents': detected_intents or [],
            'message_type': message_type,
            'context_size_tokens': context_size_tokens,
            'context_truncated': context_truncated,
        }
        
        # Add any additional metadata
        extra_data.update(kwargs)
        
        # Log at appropriate level
        if handoff_triggered:
            level = logging.WARNING
            message = f"Agent interaction with handoff: {handoff_reason}"
        elif confidence_score < 0.7:
            level = logging.WARNING
            message = f"Agent interaction with low confidence: {confidence_score:.2f}"
        else:
            level = logging.INFO
            message = f"Agent interaction completed successfully"
        
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '',
            0,
            message,
            (),
            None
        )
        record.extra_data = extra_data
        
        self.logger.handle(record)
    
    def log_llm_call(
        self,
        conversation_id: str,
        tenant_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        estimated_cost: float,
        response_time_ms: int,
        success: bool = True,
        error: Optional[str] = None,
        **kwargs
    ):
        """
        Log LLM API call with request and response details.
        
        Args:
            conversation_id: Conversation UUID
            tenant_id: Tenant UUID
            provider: LLM provider name (openai, together, etc.)
            model: Model identifier
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens used
            estimated_cost: Estimated cost in USD
            response_time_ms: API response time in milliseconds
            success: Whether call succeeded
            error: Error message if failed
            **kwargs: Additional metadata
        """
        extra_data = {
            'event_type': 'llm_api_call',
            'conversation_id': str(conversation_id),
            'tenant_id': str(tenant_id),
            'provider': provider,
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'estimated_cost': estimated_cost,
            'response_time_ms': response_time_ms,
            'success': success,
            'error': error,
        }
        
        # Add any additional metadata
        extra_data.update(kwargs)
        
        # Log at appropriate level
        if not success:
            level = logging.ERROR
            message = f"LLM API call failed: {error}"
        elif response_time_ms > 5000:
            level = logging.WARNING
            message = f"Slow LLM API call: {response_time_ms}ms"
        else:
            level = logging.INFO
            message = f"LLM API call completed: {model}"
        
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '',
            0,
            message,
            (),
            None
        )
        record.extra_data = extra_data
        
        self.logger.handle(record)
    
    def log_context_building(
        self,
        conversation_id: str,
        tenant_id: str,
        history_messages: int,
        knowledge_entries: int,
        products_count: int,
        services_count: int,
        orders_count: int,
        appointments_count: int,
        context_size_tokens: int,
        truncated: bool,
        build_time_ms: int,
        **kwargs
    ):
        """
        Log context building operation with details.
        
        Args:
            conversation_id: Conversation UUID
            tenant_id: Tenant UUID
            history_messages: Number of history messages included
            knowledge_entries: Number of knowledge entries retrieved
            products_count: Number of products in context
            services_count: Number of services in context
            orders_count: Number of orders in customer history
            appointments_count: Number of appointments in customer history
            context_size_tokens: Total context size in tokens
            truncated: Whether context was truncated
            build_time_ms: Time to build context in milliseconds
            **kwargs: Additional metadata
        """
        extra_data = {
            'event_type': 'context_building',
            'conversation_id': str(conversation_id),
            'tenant_id': str(tenant_id),
            'history_messages': history_messages,
            'knowledge_entries': knowledge_entries,
            'products_count': products_count,
            'services_count': services_count,
            'orders_count': orders_count,
            'appointments_count': appointments_count,
            'context_size_tokens': context_size_tokens,
            'truncated': truncated,
            'build_time_ms': build_time_ms,
        }
        
        # Add any additional metadata
        extra_data.update(kwargs)
        
        # Log at appropriate level
        if truncated:
            level = logging.WARNING
            message = f"Context built with truncation: {context_size_tokens} tokens"
        elif build_time_ms > 1000:
            level = logging.WARNING
            message = f"Slow context building: {build_time_ms}ms"
        else:
            level = logging.DEBUG
            message = f"Context built successfully: {context_size_tokens} tokens"
        
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '',
            0,
            message,
            (),
            None
        )
        record.extra_data = extra_data
        
        self.logger.handle(record)
    
    def log_handoff_decision(
        self,
        conversation_id: str,
        tenant_id: str,
        should_handoff: bool,
        reason: str,
        confidence_score: float,
        consecutive_low_confidence: int,
        customer_requested: bool = False,
        auto_handoff_topic: Optional[str] = None,
        **kwargs
    ):
        """
        Log handoff decision with reasoning.
        
        Args:
            conversation_id: Conversation UUID
            tenant_id: Tenant UUID
            should_handoff: Whether handoff was triggered
            reason: Reason for handoff decision
            confidence_score: Current response confidence
            consecutive_low_confidence: Count of consecutive low-confidence responses
            customer_requested: Whether customer explicitly requested human
            auto_handoff_topic: Topic that triggered auto-handoff if applicable
            **kwargs: Additional metadata
        """
        extra_data = {
            'event_type': 'handoff_decision',
            'conversation_id': str(conversation_id),
            'tenant_id': str(tenant_id),
            'should_handoff': should_handoff,
            'reason': reason,
            'confidence_score': confidence_score,
            'consecutive_low_confidence': consecutive_low_confidence,
            'customer_requested': customer_requested,
            'auto_handoff_topic': auto_handoff_topic,
        }
        
        # Add any additional metadata
        extra_data.update(kwargs)
        
        # Log at appropriate level
        if should_handoff:
            level = logging.WARNING
            message = f"Handoff triggered: {reason}"
        else:
            level = logging.DEBUG
            message = f"No handoff needed (confidence: {confidence_score:.2f})"
        
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '',
            0,
            message,
            (),
            None
        )
        record.extra_data = extra_data
        
        self.logger.handle(record)
    
    def log_knowledge_search(
        self,
        conversation_id: str,
        tenant_id: str,
        query: str,
        results_count: int,
        top_similarity_score: Optional[float] = None,
        search_time_ms: int = 0,
        entry_types: Optional[list] = None,
        **kwargs
    ):
        """
        Log knowledge base search operation.
        
        Args:
            conversation_id: Conversation UUID
            tenant_id: Tenant UUID
            query: Search query text
            results_count: Number of results returned
            top_similarity_score: Highest similarity score
            search_time_ms: Search time in milliseconds
            entry_types: Types of entries searched
            **kwargs: Additional metadata
        """
        extra_data = {
            'event_type': 'knowledge_search',
            'conversation_id': str(conversation_id),
            'tenant_id': str(tenant_id),
            'query_length': len(query),
            'results_count': results_count,
            'top_similarity_score': top_similarity_score,
            'search_time_ms': search_time_ms,
            'entry_types': entry_types or [],
        }
        
        # Add any additional metadata
        extra_data.update(kwargs)
        
        # Log at appropriate level
        if results_count == 0:
            level = logging.WARNING
            message = f"Knowledge search returned no results"
        elif search_time_ms > 500:
            level = logging.WARNING
            message = f"Slow knowledge search: {search_time_ms}ms"
        else:
            level = logging.DEBUG
            message = f"Knowledge search completed: {results_count} results"
        
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '',
            0,
            message,
            (),
            None
        )
        record.extra_data = extra_data
        
        self.logger.handle(record)
    
    def log_error(
        self,
        conversation_id: str,
        tenant_id: str,
        error_type: str,
        error_message: str,
        operation: str,
        **kwargs
    ):
        """
        Log error with context.
        
        Args:
            conversation_id: Conversation UUID
            tenant_id: Tenant UUID
            error_type: Type of error (e.g., 'llm_api_error', 'context_building_error')
            error_message: Error message
            operation: Operation that failed
            **kwargs: Additional metadata
        """
        extra_data = {
            'event_type': 'error',
            'conversation_id': str(conversation_id),
            'tenant_id': str(tenant_id),
            'error_type': error_type,
            'error_message': error_message,
            'operation': operation,
        }
        
        # Add any additional metadata
        extra_data.update(kwargs)
        
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            logging.ERROR,
            '',
            0,
            f"Error in {operation}: {error_message}",
            (),
            None
        )
        record.extra_data = extra_data
        
        self.logger.handle(record)


# Global logger instance
_global_logger: Optional[StructuredLogger] = None


def get_agent_logger() -> StructuredLogger:
    """
    Get global structured logger instance.
    
    Returns:
        StructuredLogger instance
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = StructuredLogger()
    
    return _global_logger
