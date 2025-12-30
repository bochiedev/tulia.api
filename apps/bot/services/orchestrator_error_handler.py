"""
Error handling integration for LangGraph orchestrator.

This module provides error handling wrappers and fallback logic
specifically for the LangGraph orchestrator nodes.

Requirements: 10.1, 10.3
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import asdict

from apps.bot.services.error_handling import (
    ErrorHandlingService, ErrorContext, ComponentType,
    error_handling_service, EnhancedOperationError
)
from apps.bot.conversation_state import ConversationState

logger = logging.getLogger(__name__)


class OrchestratorErrorHandler:
    """
    Error handling wrapper for LangGraph orchestrator nodes.
    
    Provides graceful degradation and fallback responses for
    node failures while maintaining conversation continuity.
    """
    
    def __init__(self):
        """Initialize orchestrator error handler."""
        self.error_service = error_handling_service
        self.fallback_responses = self._initialize_orchestrator_fallbacks()
    
    async def execute_node_with_fallback(self,
                                       node_func: Callable,
                                       state: Dict[str, Any],
                                       node_name: str,
                                       component_type: ComponentType = ComponentType.LLM_NODE) -> Dict[str, Any]:
        """
        Execute orchestrator node with comprehensive error handling.
        
        Args:
            node_func: The node function to execute
            state: Current conversation state
            node_name: Name of the node for logging
            component_type: Type of component for error handling
            
        Returns:
            Updated state dict or fallback state
        """
        context = ErrorContext(
            tenant_id=state.get('tenant_id', 'unknown'),
            conversation_id=state.get('conversation_id', 'unknown'),
            request_id=state.get('request_id', 'unknown'),
            component_type=component_type,
            operation=node_name
        )
        
        try:
            # Create fallback function
            async def fallback():
                return self._get_node_fallback(node_name, state, context)
            
            # Execute the node function directly since it's already async
            result = await node_func(state)
            
            return result
            
        except Exception as e:
            logger.error(
                f"Node execution failed completely: {node_name}",
                extra={
                    'tenant_id': context.tenant_id,
                    'conversation_id': context.conversation_id,
                    'request_id': context.request_id,
                    'node_name': node_name,
                    'error': str(e)
                },
                exc_info=True
            )
            
            # Final fallback - return state with error handling
            return self._get_emergency_fallback(node_name, state, context)
    
    def _get_node_fallback(self, node_name: str, state: Dict[str, Any], context: ErrorContext) -> Dict[str, Any]:
        """
        Get fallback response for specific orchestrator node.
        
        Args:
            node_name: Name of the failed node
            state: Current conversation state
            context: Error context
            
        Returns:
            Fallback state update
        """
        fallback_key = f"node_{node_name}"
        
        if fallback_key in self.fallback_responses:
            fallback = self.fallback_responses[fallback_key].copy()
        else:
            fallback = self.fallback_responses["node_generic"].copy()
        
        # Update state with fallback data
        updated_state = state.copy()
        updated_state.update(fallback["state_updates"])
        
        # Add error context
        updated_state["error_context"] = {
            "failed_node": node_name,
            "error_handled": True,
            "fallback_applied": True,
            "attempt_count": context.attempt_count
        }
        
        logger.info(
            f"Applied fallback for node: {node_name}",
            extra={
                'tenant_id': context.tenant_id,
                'conversation_id': context.conversation_id,
                'request_id': context.request_id,
                'fallback_type': fallback_key
            }
        )
        
        return updated_state
    
    def _get_emergency_fallback(self, node_name: str, state: Dict[str, Any], context: ErrorContext) -> Dict[str, Any]:
        """
        Get emergency fallback when all other fallbacks fail.
        
        This ensures conversation continuity even in catastrophic failures.
        """
        updated_state = state.copy()
        
        # Set emergency response
        updated_state.update({
            "response_text": "I'm experiencing technical difficulties. Let me connect you with a human agent who can help.",
            "escalation_required": True,
            "escalation_reason": f"System failure in {node_name} node",
            "journey": "governance",
            "error_context": {
                "failed_node": node_name,
                "emergency_fallback": True,
                "requires_immediate_attention": True
            }
        })
        
        logger.critical(
            f"Emergency fallback activated for node: {node_name}",
            extra={
                'tenant_id': context.tenant_id,
                'conversation_id': context.conversation_id,
                'request_id': context.request_id,
                'node_name': node_name
            }
        )
        
        return updated_state
    
    def _initialize_orchestrator_fallbacks(self) -> Dict[str, Dict[str, Any]]:
        """Initialize fallback responses for orchestrator nodes."""
        return {
            "node_generic": {
                "state_updates": {
                    "response_text": "I'm having a brief technical issue. Let me try to help you in a different way.",
                    "journey": "support",
                    "escalation_required": False
                }
            },
            
            "node_intent_classify": {
                "state_updates": {
                    "intent": "unknown",
                    "intent_confidence": 0.0,
                    "journey": "support",
                    "response_text": "I'm not sure what you're looking for. Could you tell me more about how I can help you today?"
                }
            },
            
            "node_language_policy": {
                "state_updates": {
                    "response_language": "en",
                    "language_confidence": 0.0,
                    "response_text": "I'll continue in English. How can I help you today?"
                }
            },
            
            "node_governor_spam_casual": {
                "state_updates": {
                    "governor_classification": "business",
                    "governor_confidence": 0.0,
                    "response_text": "How can I help you with your business needs today?"
                }
            },
            
            "node_sales_journey": {
                "state_updates": {
                    "journey": "support",
                    "escalation_required": True,
                    "escalation_reason": "Sales system unavailable",
                    "response_text": "I'm having trouble accessing our product catalog right now. Let me connect you with someone who can help you find what you're looking for."
                }
            },
            
            "node_support_journey": {
                "state_updates": {
                    "escalation_required": True,
                    "escalation_reason": "Support system unavailable",
                    "response_text": "I'm having trouble accessing our support resources. Let me connect you with a human agent who can help answer your questions."
                }
            },
            
            "node_orders_journey": {
                "state_updates": {
                    "escalation_required": True,
                    "escalation_reason": "Order system unavailable",
                    "response_text": "I'm having trouble accessing order information right now. Let me connect you with our support team to check on your order."
                }
            },
            
            "node_preferences_journey": {
                "state_updates": {
                    "response_text": "I'm having trouble updating your preferences right now. Your request has been noted and will be processed manually."
                }
            },
            
            "node_offers_journey": {
                "state_updates": {
                    "journey": "sales",
                    "response_text": "I'm having trouble accessing our current offers. Let me help you find products you're interested in instead."
                }
            },
            
            "node_journey_router": {
                "state_updates": {
                    "journey": "support",
                    "response_text": "I'm not sure how to best help you right now. Let me connect you with someone who can assist you."
                }
            },
            
            "node_response_generator": {
                "state_updates": {
                    "response_text": "I apologize, but I'm having trouble generating a proper response. How can I help you today?"
                }
            }
        }


# Global orchestrator error handler instance
orchestrator_error_handler = OrchestratorErrorHandler()


def with_node_error_handling(node_name: str, component_type: ComponentType = ComponentType.LLM_NODE):
    """
    Decorator for adding error handling to orchestrator nodes.
    
    Args:
        node_name: Name of the node for logging and fallbacks
        component_type: Type of component for error handling strategy
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(self, state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                # Execute the original function
                result = await func(self, state)
                return result
            except Exception as e:
                logger.error(
                    f"Node {node_name} failed: {e}",
                    extra={
                        'tenant_id': state.get('tenant_id', 'unknown'),
                        'conversation_id': state.get('conversation_id', 'unknown'),
                        'request_id': state.get('request_id', 'unknown'),
                        'node_name': node_name,
                        'error': str(e)
                    },
                    exc_info=True
                )
                
                # Return fallback state
                fallback_state = state.copy()
                fallback_state.update({
                    "response_text": "I'm having a brief technical issue. Let me try to help you in a different way.",
                    "journey": "support",
                    "escalation_required": False,
                    "error_context": {
                        "failed_node": node_name,
                        "error_handled": True,
                        "fallback_applied": True
                    }
                })
                return fallback_state
        return wrapper
    return decorator