"""
LangGraph Node Registry and Base Node Implementations.

This module provides the node registry system and base node implementations
for the LangGraph orchestration system.
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod

from apps.bot.conversation_state import ConversationState
from apps.bot.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """
    Base class for all LangGraph nodes.
    
    Provides common functionality for node execution, error handling,
    and state management.
    """
    
    def __init__(self, name: str):
        """
        Initialize base node.
        
        Args:
            name: Node name for identification
        """
        self.name = name
        self.tool_registry = ToolRegistry()
    
    @abstractmethod
    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the node logic.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        pass
    
    def _log_execution(self, state: ConversationState, action: str) -> None:
        """
        Log node execution for observability.
        
        Args:
            state: Current conversation state
            action: Action being performed
        """
        logger.info(
            f"Node {self.name} {action}",
            extra={
                'tenant_id': state.tenant_id,
                'conversation_id': state.conversation_id,
                'request_id': state.request_id,
                'journey': state.journey,
                'intent': state.intent
            }
        )
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle node execution errors.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with error handling
        """
        logger.error(
            f"Node {self.name} error: {error}",
            extra={
                'tenant_id': state.tenant_id,
                'conversation_id': state.conversation_id,
                'request_id': state.request_id,
                'error': str(error)
            },
            exc_info=True
        )
        
        # Set escalation for node errors
        state.set_escalation(f"System error in {self.name}: {str(error)}")
        return state


class ToolNode(BaseNode):
    """
    Node that executes a specific tool from the tool registry.
    
    Provides integration between LangGraph nodes and the tool contract system.
    """
    
    def __init__(self, name: str, tool_name: str):
        """
        Initialize tool node.
        
        Args:
            name: Node name
            tool_name: Name of tool to execute
        """
        super().__init__(name)
        self.tool_name = tool_name
    
    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the tool and update state.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        self._log_execution(state, f"executing tool {self.tool_name}")
        
        try:
            # Get tool from registry
            tool = self.tool_registry.get_tool(self.tool_name)
            if not tool:
                raise ValueError(f"Tool {self.tool_name} not found in registry")
            
            # Prepare tool parameters from state
            tool_params = self._prepare_tool_params(state)
            
            # Execute tool
            result = await tool.execute(**tool_params)
            
            # Update state with tool result
            updated_state = self._update_state_from_result(state, result)
            
            self._log_execution(updated_state, f"completed tool {self.tool_name}")
            return updated_state
            
        except Exception as e:
            return self._handle_error(state, e)
    
    def _prepare_tool_params(self, state: ConversationState) -> Dict[str, Any]:
        """
        Prepare tool parameters from conversation state.
        
        Args:
            state: Current conversation state
            
        Returns:
            Dictionary of tool parameters
        """
        # Base parameters required by all tools
        params = {
            'tenant_id': state.tenant_id,
            'request_id': state.request_id,
            'conversation_id': state.conversation_id
        }
        
        # Add tool-specific parameters based on tool name
        if self.tool_name == 'customer_get_or_create' and state.phone_e164:
            params['phone_e164'] = state.phone_e164
        elif self.tool_name == 'catalog_search' and state.last_catalog_query:
            params['query'] = state.last_catalog_query
            params['filters'] = state.last_catalog_filters
        elif self.tool_name == 'order_create' and state.cart:
            params['items'] = state.cart
        elif self.tool_name == 'kb_retrieve' and state.last_catalog_query:
            params['query'] = state.last_catalog_query
        
        return params
    
    def _update_state_from_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update conversation state from tool execution result.
        
        Args:
            state: Current conversation state
            result: Tool execution result
            
        Returns:
            Updated conversation state
        """
        # Update state based on tool type and result
        if self.tool_name == 'tenant_get_context':
            if 'bot_name' in result:
                state.bot_name = result['bot_name']
            if 'tone_style' in result:
                state.tone_style = result['tone_style']
            if 'default_language' in result:
                state.default_language = result['default_language']
            if 'allowed_languages' in result:
                state.allowed_languages = result['allowed_languages']
            if 'max_chattiness_level' in result:
                state.max_chattiness_level = result['max_chattiness_level']
        
        elif self.tool_name == 'customer_get_or_create':
            if 'customer_id' in result:
                state.customer_id = result['customer_id']
            if 'language_preference' in result:
                state.customer_language_pref = result['language_preference']
            if 'marketing_opt_in' in result:
                state.marketing_opt_in = result['marketing_opt_in']
        
        elif self.tool_name == 'catalog_search':
            if 'results' in result:
                state.last_catalog_results = result['results']
            if 'total_matches' in result:
                state.catalog_total_matches_estimate = result['total_matches']
        
        elif self.tool_name == 'order_create':
            if 'order_id' in result:
                state.order_id = result['order_id']
            if 'totals' in result:
                state.order_totals = result['totals']
        
        elif self.tool_name == 'kb_retrieve':
            if 'snippets' in result:
                state.kb_snippets = result['snippets']
        
        return state


class LLMNode(BaseNode):
    """
    Base class for LLM-powered nodes.
    
    Provides common functionality for LLM calls with structured output.
    """
    
    def __init__(self, name: str, system_prompt: str, output_schema: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM node.
        
        Args:
            name: Node name
            system_prompt: System prompt for LLM
            output_schema: Optional JSON schema for structured output
        """
        super().__init__(name)
        self.system_prompt = system_prompt
        self.output_schema = output_schema
    
    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute LLM call and update state.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        self._log_execution(state, "executing LLM call")
        
        try:
            # Prepare LLM input from state
            llm_input = self._prepare_llm_input(state)
            
            # Execute LLM call (placeholder - will be implemented in specific nodes)
            result = await self._call_llm(llm_input, state)
            
            # Update state with LLM result
            updated_state = self._update_state_from_llm_result(state, result)
            
            self._log_execution(updated_state, "completed LLM call")
            return updated_state
            
        except Exception as e:
            return self._handle_error(state, e)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for LLM from conversation state.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input string for LLM
        """
        # Base implementation - override in specific nodes
        return f"User message for {state.conversation_id}"
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Make LLM call with structured output.
        
        Args:
            input_text: Input text for LLM
            state: Current conversation state
            
        Returns:
            LLM response as dictionary
        """
        # Placeholder implementation - will be replaced with actual LLM calls
        # in specific node implementations
        return {"placeholder": "result"}
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update conversation state from LLM result.
        
        Args:
            state: Current conversation state
            result: LLM result dictionary
            
        Returns:
            Updated conversation state
        """
        # Base implementation - override in specific nodes
        return state


class NodeRegistry:
    """
    Registry for managing LangGraph nodes.
    
    Provides centralized registration and retrieval of nodes for the
    LangGraph orchestration system.
    """
    
    def __init__(self):
        """Initialize node registry."""
        self._nodes: Dict[str, BaseNode] = {}
        self._setup_default_nodes()
    
    def register_node(self, name: str, node: BaseNode) -> None:
        """
        Register a node in the registry.
        
        Args:
            name: Node name
            node: Node instance
        """
        self._nodes[name] = node
        logger.info(f"Registered node: {name}")
    
    def get_node(self, name: str) -> Optional[BaseNode]:
        """
        Get a node from the registry.
        
        Args:
            name: Node name
            
        Returns:
            Node instance or None if not found
        """
        return self._nodes.get(name)
    
    def list_nodes(self) -> List[str]:
        """
        List all registered node names.
        
        Returns:
            List of node names
        """
        return list(self._nodes.keys())
    
    def _setup_default_nodes(self) -> None:
        """Set up default nodes for the orchestration system."""
        # Tool nodes for backend integration
        self.register_node("tenant_get_context", ToolNode("tenant_get_context", "tenant_get_context"))
        self.register_node("customer_get_or_create", ToolNode("customer_get_or_create", "customer_get_or_create"))
        self.register_node("catalog_search", ToolNode("catalog_search", "catalog_search"))
        self.register_node("order_create", ToolNode("order_create", "order_create"))
        self.register_node("order_get_status", ToolNode("order_get_status", "order_get_status"))
        self.register_node("kb_retrieve", ToolNode("kb_retrieve", "kb_retrieve"))
        self.register_node("handoff_create_ticket", ToolNode("handoff_create_ticket", "handoff_create_ticket"))
        
        # Register LLM nodes
        try:
            # Import actual LLM nodes
            from apps.bot.langgraph.llm_nodes import IntentClassificationNode, LanguagePolicyNode, ConversationGovernorNode
            from apps.bot.langgraph.support_journey import SupportRagAnswerNode, HandoffMessageNode
            from apps.bot.langgraph.payment_nodes import PaymentRouterPromptNode
            from apps.bot.langgraph.offers_journey import OffersAnswerNode
            
            # Register core LLM nodes with actual implementations
            self.register_node("intent_classify", IntentClassificationNode())
            self.register_node("language_policy", LanguagePolicyNode())
            self.register_node("governor_spam_casual", ConversationGovernorNode())
            
            # Register support journey LLM nodes
            self.register_node("support_rag_answer", SupportRagAnswerNode())
            self.register_node("handoff_message", HandoffMessageNode())
            
            # Register payment LLM nodes
            self.register_node("payment_router_prompt", PaymentRouterPromptNode())
            
            # Register offers journey LLM nodes
            self.register_node("offers_answer", OffersAnswerNode())
            
        except ImportError as e:
            logger.warning(f"Could not import LLM nodes: {e}. Using placeholder nodes.")
            # Fallback to placeholder nodes if imports fail
            self.register_node("intent_classify", PlaceholderLLMNode("intent_classify", "Intent classification"))
            self.register_node("language_policy", PlaceholderLLMNode("language_policy", "Language policy"))
            self.register_node("governor_spam_casual", PlaceholderLLMNode("governor_spam_casual", "Conversation governor"))
            self.register_node("support_rag_answer", PlaceholderLLMNode("support_rag_answer", "Support RAG answer"))
            self.register_node("handoff_message", PlaceholderLLMNode("handoff_message", "Handoff message"))
            self.register_node("payment_router_prompt", PlaceholderLLMNode("payment_router_prompt", "Payment router prompt"))
            self.register_node("offers_answer", PlaceholderLLMNode("offers_answer", "Offers answer"))


class PlaceholderLLMNode(LLMNode):
    """
    Placeholder LLM node for initial infrastructure setup.
    
    Provides basic functionality until actual LLM nodes are implemented
    in later tasks.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize placeholder LLM node.
        
        Args:
            name: Node name
            description: Node description
        """
        super().__init__(name, f"Placeholder system prompt for {description}")
        self.description = description
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Placeholder LLM call that returns default values.
        
        Args:
            input_text: Input text for LLM
            state: Current conversation state
            
        Returns:
            Default LLM response
        """
        # Return appropriate defaults based on node type
        if self.name == "intent_classify":
            return {
                "intent": "unknown",
                "confidence": 0.5,
                "notes": "Placeholder classification",
                "suggested_journey": "unknown"
            }
        elif self.name == "language_policy":
            return {
                "response_language": state.default_language,
                "confidence": 0.8,
                "should_ask_language_question": False
            }
        elif self.name == "governor_spam_casual":
            return {
                "classification": "business",
                "confidence": 0.8,
                "recommended_action": "proceed"
            }
        else:
            return {"placeholder": True, "description": self.description}
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from placeholder LLM result.
        
        Args:
            state: Current conversation state
            result: LLM result dictionary
            
        Returns:
            Updated conversation state
        """
        if self.name == "intent_classify":
            state.update_intent(result.get("intent", "unknown"), result.get("confidence", 0.5))
            state.journey = result.get("suggested_journey", "unknown")
        
        elif self.name == "language_policy":
            state.update_language(
                result.get("response_language", state.default_language),
                result.get("confidence", 0.8)
            )
        
        elif self.name == "governor_spam_casual":
            state.update_governor(
                result.get("classification", "business"),
                result.get("confidence", 0.8)
            )
        
        return state


# Global node registry instance
_node_registry: Optional[NodeRegistry] = None


def get_node_registry() -> NodeRegistry:
    """
    Get the global node registry instance.
    
    Returns:
        NodeRegistry instance
    """
    global _node_registry
    if _node_registry is None:
        _node_registry = NodeRegistry()
    return _node_registry


def register_node(node) -> None:
    """
    Register a node in the global registry.
    
    Args:
        node: Node instance to register
    """
    registry = get_node_registry()
    registry.register_node(node)


# Specific node implementations for testing
class IntentClassifyNode(PlaceholderLLMNode):
    """Intent classification node."""
    def __init__(self):
        super().__init__("intent_classify", "Intent classification")


class LanguagePolicyNode(PlaceholderLLMNode):
    """Language policy node."""
    def __init__(self):
        super().__init__("language_policy", "Language policy")


class GovernorNode(PlaceholderLLMNode):
    """Conversation governor node."""
    def __init__(self):
        super().__init__("governor_spam_casual", "Conversation governor")


class TenantContextNode(ToolNode):
    """Tenant context resolution node."""
    def __init__(self):
        super().__init__("tenant_context", "tenant_get_context")


class CustomerResolverNode(ToolNode):
    """Customer resolver node."""
    def __init__(self):
        super().__init__("customer_resolver", "customer_get_or_create")


def register_default_nodes():
    """Register default nodes in the global registry."""
    registry = get_node_registry()
    
    # Import actual LLM nodes
    from apps.bot.langgraph.llm_nodes import IntentClassificationNode, LanguagePolicyNode, ConversationGovernorNode
    
    # Register core LLM nodes with actual implementations
    registry.register_node("intent_classify", IntentClassificationNode())
    registry.register_node("language_policy", LanguagePolicyNode())
    registry.register_node("governor_spam_casual", ConversationGovernorNode())
    
    # Register tool nodes
    registry.register_node("tenant_context", TenantContextNode())
    registry.register_node("customer_resolver", CustomerResolverNode())
    
    logger.info("Default nodes registered successfully")