"""
LangGraph Orchestrator - Core state machine for conversation management.

This module implements the central LangGraph orchestrator that manages
all conversation flows through structured state transitions.
"""
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import asdict

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig

from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.langgraph.nodes import NodeRegistry
from apps.bot.langgraph.routing import RouteDecision, ConversationRouter

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """
    Central LangGraph orchestrator for conversation management.
    
    This class implements the core state machine that processes all WhatsApp
    messages through structured LangGraph nodes, maintaining explicit state
    and ensuring predictable behavior.
    """
    
    def __init__(self):
        """Initialize the orchestrator with node registry and routing."""
        # Register default nodes first to ensure LLM nodes are available
        from apps.bot.langgraph.nodes import register_default_nodes
        register_default_nodes()
        
        self.node_registry = NodeRegistry()
        self.router = ConversationRouter()
        self._graph: Optional[CompiledStateGraph] = None
        self._setup_graph()
    
    def _setup_graph(self) -> None:
        """
        Set up the LangGraph state machine with nodes and routing.
        
        Creates a basic conversation flow graph for Phase 2 infrastructure.
        """
        # Create state graph with dict schema instead of ConversationState
        workflow = StateGraph(dict)
        
        # Entry nodes
        workflow.add_node("webhook_entry", self._webhook_entry_node)
        workflow.add_node("tenant_resolver", self._tenant_resolver_node)
        workflow.add_node("customer_resolver", self._customer_resolver_node)
        
        # Classification nodes
        workflow.add_node("intent_classify", self._intent_classify_node)
        workflow.add_node("language_policy", self._language_policy_node)
        workflow.add_node("governor_spam_casual", self._governor_node)
        
        # Journey router
        workflow.add_node("journey_router", self._journey_router_node)
        
        # Journey subgraphs (placeholders for now)
        workflow.add_node("sales_journey", self._sales_journey_node)
        workflow.add_node("support_journey", self._support_journey_node)
        workflow.add_node("orders_journey", self._orders_journey_node)
        workflow.add_node("offers_journey", self._offers_journey_node)
        workflow.add_node("preferences_journey", self._preferences_journey_node)
        workflow.add_node("governance_response", self._governance_response_node)
        workflow.add_node("unknown_handler", self._unknown_handler_node)
        
        # Response generation and exit
        workflow.add_node("response_generator", self._response_generator_node)
        workflow.add_node("state_persistence", self._state_persistence_node)
        
        # Set entry point
        workflow.set_entry_point("webhook_entry")
        
        # Define flow edges
        workflow.add_edge("webhook_entry", "tenant_resolver")
        workflow.add_edge("tenant_resolver", "customer_resolver")
        workflow.add_edge("customer_resolver", "intent_classify")
        workflow.add_edge("intent_classify", "language_policy")
        workflow.add_edge("language_policy", "governor_spam_casual")
        workflow.add_edge("governor_spam_casual", "journey_router")
        
        # Journey routing edges (conditional) - updated for exact routing conditions
        workflow.add_conditional_edges(
            "journey_router",
            self._route_to_journey,
            {
                "sales": "sales_journey",
                "support": "support_journey", 
                "orders": "orders_journey",
                "offers": "offers_journey",
                "prefs": "preferences_journey",
                "governance": "governance_response",
                "unknown": "unknown_handler",
                "business": "journey_router"  # Re-route business classification back to journey router
            }
        )
        
        # All journeys lead to response generation
        for journey_node in [
            "sales_journey", "support_journey", "orders_journey", 
            "offers_journey", "preferences_journey", "governance_response", 
            "unknown_handler"
        ]:
            workflow.add_edge(journey_node, "response_generator")
        
        workflow.add_edge("response_generator", "state_persistence")
        workflow.add_edge("state_persistence", END)
        
        # Compile the graph
        self._graph = workflow.compile()
        logger.info("LangGraph orchestrator initialized successfully")
    
    async def process_message(
        self, 
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        message_text: str,
        phone_e164: Optional[str] = None,
        customer_id: Optional[str] = None,
        existing_state: Optional[ConversationState] = None
    ) -> ConversationState:
        """
        Process incoming WhatsApp message through LangGraph orchestration.
        
        Args:
            tenant_id: Tenant identifier
            conversation_id: Conversation identifier  
            request_id: Request identifier for tracing
            message_text: Incoming message text
            phone_e164: Customer phone number
            customer_id: Optional existing customer ID
            existing_state: Optional existing conversation state
            
        Returns:
            Updated ConversationState after processing
            
        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If graph execution fails
        """
        if not self._graph:
            raise RuntimeError("LangGraph not initialized")
        
        # Create or update conversation state
        if existing_state:
            state = existing_state
            state.request_id = request_id
        else:
            state = ConversationStateManager.create_initial_state(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                customer_id=customer_id,
                phone_e164=phone_e164
            )
        
        # Add incoming message context
        state.incoming_message = message_text
        
        try:
            # Execute the graph
            config = RunnableConfig(
                configurable={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "request_id": request_id
                }
            )
            
            # Convert state to dict for LangGraph processing
            state_dict = asdict(state)
            
            # Run the graph
            result = await self._graph.ainvoke(state_dict, config=config)
            
            # Convert result back to ConversationState
            updated_state = ConversationState.from_dict(result)
            updated_state.validate()
            
            logger.info(
                f"Message processed successfully",
                extra={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "request_id": request_id,
                    "intent": updated_state.intent,
                    "journey": updated_state.journey
                }
            )
            
            return updated_state
            
        except Exception as e:
            logger.error(
                f"Graph execution failed: {e}",
                extra={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "request_id": request_id
                },
                exc_info=True
            )
            raise RuntimeError(f"Graph execution failed: {e}")
    
    def _route_to_journey(self, state: Dict[str, Any]) -> str:
        """
        Route conversation to appropriate journey based on classification with EXACT routing conditions.
        
        Implements exact routing thresholds:
        - confidence >= 0.70: route to suggested journey
        - 0.50 <= confidence < 0.70: ask ONE clarifying question then re-classify
        - confidence < 0.50: route to unknown handler
        
        Also handles governance routing and escalation triggers.
        
        Args:
            state: Current conversation state
            
        Returns:
            Journey name for routing
        """
        conv_state = ConversationState.from_dict(state)
        route_decision = self.router.route_conversation(conv_state)
        
        # Handle clarification requests for medium confidence
        if route_decision.should_clarify:
            # Set flag for clarification in next response
            state["needs_clarification"] = True
            state["clarification_reason"] = route_decision.reason
            state["clarification_metadata"] = route_decision.metadata
        
        # Handle escalation requirements
        if route_decision.metadata.get("escalation_required", False):
            state["escalation_required"] = True
            state["escalation_reason"] = route_decision.metadata.get("escalation_trigger", route_decision.reason)
            state["escalation_metadata"] = route_decision.metadata
        
        # Update journey transition in state
        state["journey"] = route_decision.journey
        state["routing_decision"] = route_decision.reason
        state["routing_confidence"] = route_decision.confidence
        state["routing_metadata"] = route_decision.metadata
        
        logger.info(
            f"Journey routing decision: {route_decision.journey}",
            extra={
                "tenant_id": conv_state.tenant_id,
                "conversation_id": conv_state.conversation_id,
                "request_id": conv_state.request_id,
                "intent": conv_state.intent,
                "intent_confidence": conv_state.intent_confidence,
                "governor_classification": conv_state.governor_classification,
                "route_journey": route_decision.journey,
                "route_reason": route_decision.reason,
                "route_confidence": route_decision.confidence,
                "should_clarify": route_decision.should_clarify,
                "escalation_required": route_decision.metadata.get("escalation_required", False),
                "routing_metadata": route_decision.metadata
            }
        )
        
        return route_decision.journey
    
    # Node implementations (placeholders for now)
    
    async def _webhook_entry_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Entry point for webhook processing."""
        logger.debug("Processing webhook entry")
        # Increment turn count at the start of processing
        state["turn_count"] = state.get("turn_count", 0) + 1
        return state
    
    async def _tenant_resolver_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve tenant context using tenant_get_context tool."""
        # TODO: Implement tenant_get_context tool call
        logger.debug(f"Resolving tenant context for tenant_id: {state.get('tenant_id')}")
        return state
    
    async def _customer_resolver_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve customer using customer_get_or_create tool."""
        # TODO: Implement customer_get_or_create tool call
        logger.debug(f"Resolving customer for tenant_id: {state.get('tenant_id')}")
        return state
    
    async def _intent_classify_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Classify user intent with confidence scoring and routing logic."""
        from apps.bot.langgraph.llm_nodes import IntentClassificationNode
        
        # Convert dict state to ConversationState for node processing
        conv_state = ConversationState.from_dict(state)
        
        # Create and execute intent classification node
        intent_node = IntentClassificationNode()
        
        try:
            # Execute the intent classification
            updated_state = await intent_node.execute(conv_state)
            
            # Convert back to dict for LangGraph
            return asdict(updated_state)
            
        except Exception as e:
            logger.error(
                f"Intent classification node failed: {e}",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id
                },
                exc_info=True
            )
            
            # Fallback to unknown intent
            conv_state.update_intent("unknown", 0.0)
            conv_state.journey = "unknown"
            return asdict(conv_state)
    
    async def _language_policy_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Determine response language based on detection confidence."""
        from apps.bot.langgraph.llm_nodes import LanguagePolicyNode
        
        # Convert dict state to ConversationState for node processing
        conv_state = ConversationState.from_dict(state)
        
        # Create and execute language policy node
        language_node = LanguagePolicyNode()
        
        try:
            # Execute the language policy determination
            updated_state = await language_node.execute(conv_state)
            
            # Convert back to dict for LangGraph
            return asdict(updated_state)
            
        except Exception as e:
            logger.error(
                f"Language policy node failed: {e}",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id
                },
                exc_info=True
            )
            
            # Fallback to tenant default language
            conv_state.update_language(conv_state.default_language, 0.5)
            return asdict(conv_state)
    
    async def _governor_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply conversation governance (spam/casual detection) with EXACT routing logic."""
        from apps.bot.langgraph.llm_nodes import ConversationGovernorNode
        
        # Convert dict state to ConversationState for node processing
        conv_state = ConversationState.from_dict(state)
        
        # Create and execute conversation governor node
        governor_node = ConversationGovernorNode()
        
        try:
            # Execute the conversation governance
            updated_state = await governor_node.execute(conv_state)
            
            # Convert back to dict for LangGraph
            return asdict(updated_state)
            
        except Exception as e:
            logger.error(
                f"Conversation governor node failed: {e}",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id
                },
                exc_info=True
            )
            
            # Fallback to business classification
            conv_state.update_governor("business", 0.5)
            return asdict(conv_state)
    
    async def _journey_router_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route to appropriate journey based on classification with journey transition logic.
        
        Implements journey transition tracking and state updates for observability.
        """
        conv_state = ConversationState.from_dict(state)
        
        # Store previous journey for transition tracking
        previous_journey = conv_state.journey
        
        # Get routing decision
        route_decision = self.router.route_conversation(conv_state)
        
        # Update state with routing decision and journey transition
        state["journey"] = route_decision.journey
        state["previous_journey"] = previous_journey
        state["journey_transition_reason"] = route_decision.reason
        state["journey_transition_confidence"] = route_decision.confidence
        state["journey_transition_metadata"] = route_decision.metadata
        
        # Track journey transitions for analytics
        if previous_journey != route_decision.journey:
            logger.info(
                f"Journey transition: {previous_journey} -> {route_decision.journey}",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id,
                    "previous_journey": previous_journey,
                    "new_journey": route_decision.journey,
                    "transition_reason": route_decision.reason,
                    "transition_confidence": route_decision.confidence,
                    "intent": conv_state.intent,
                    "intent_confidence": conv_state.intent_confidence,
                    "governor_classification": conv_state.governor_classification,
                    "turn_count": conv_state.turn_count,
                    "metadata": route_decision.metadata
                }
            )
        
        # Handle special routing cases
        if route_decision.should_clarify:
            state["needs_clarification"] = True
            state["clarification_reason"] = route_decision.reason
            state["clarification_metadata"] = route_decision.metadata
        
        if route_decision.metadata.get("escalation_required", False):
            state["escalation_required"] = True
            state["escalation_reason"] = route_decision.metadata.get("escalation_trigger", route_decision.reason)
            state["escalation_metadata"] = route_decision.metadata
        
        return state
    
    # Journey node placeholders
    
    async def _sales_journey_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle sales journey workflow."""
        from apps.bot.langgraph.sales_journey import execute_sales_journey_node
        
        logger.debug("Processing sales journey")
        
        try:
            # Execute sales journey subgraph
            updated_state = await execute_sales_journey_node(state)
            return updated_state
            
        except Exception as e:
            logger.error(
                f"Sales journey execution failed: {e}",
                extra={
                    "tenant_id": state.get("tenant_id"),
                    "conversation_id": state.get("conversation_id"),
                    "request_id": state.get("request_id")
                },
                exc_info=True
            )
            
            # Fallback response
            state["response_text"] = "I'm having trouble processing your request right now. Let me connect you with someone who can help."
            state["escalation_required"] = True
            state["escalation_reason"] = "Sales journey execution error"
            return state
    
    async def _support_journey_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle support journey workflow."""
        # TODO: Implement support journey subgraph
        logger.debug("Processing support journey")
        state["response_text"] = "Support journey processing (placeholder)"
        return state
    
    async def _orders_journey_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle orders journey workflow."""
        # TODO: Implement orders journey subgraph
        logger.debug("Processing orders journey")
        state["response_text"] = "Orders journey processing (placeholder)"
        return state
    
    async def _offers_journey_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle offers journey workflow."""
        # TODO: Implement offers journey subgraph
        logger.debug("Processing offers journey")
        state["response_text"] = "Offers journey processing (placeholder)"
        return state
    
    async def _preferences_journey_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle preferences journey workflow."""
        # TODO: Implement preferences journey subgraph
        logger.debug("Processing preferences journey")
        state["response_text"] = "Preferences journey processing (placeholder)"
        return state
    
    async def _governance_response_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle governance responses (casual/spam redirect, escalation) with EXACT responses.
        
        Implements exact governance actions based on routing metadata:
        - redirect_to_business: Redirect casual conversation to business
        - friendly_casual_response: Allow casual within limits
        - spam_warning: Warn about spam behavior
        - disengage: Disengage from spam conversation
        - abuse_stop: Stop conversation due to abuse
        - escalation: Handle human handoff
        """
        conv_state = ConversationState.from_dict(state)
        
        classification = conv_state.governor_classification
        casual_turns = conv_state.casual_turns
        spam_turns = conv_state.spam_turns
        max_chattiness_level = conv_state.max_chattiness_level
        
        # Get governance action from routing metadata
        routing_metadata = state.get("routing_metadata", {})
        governance_action = routing_metadata.get("governance_action", "redirect_to_business")
        
        # Generate appropriate governance response based on action
        if governance_action == "redirect_to_business":
            # Exceeded casual limit - redirect to business
            if max_chattiness_level == 0:
                response = "I'm here to help with your shopping needs. What can I assist you with today?"
            else:
                response = "Thanks for the chat! How can I help you with our products or services today?"
        
        elif governance_action == "friendly_casual_response":
            # Within casual limit - acknowledge and gently guide
            if casual_turns == 1:
                response = "Hello! I'm here to help you with shopping. What are you looking for today?"
            else:
                response = "Nice to chat! Is there anything I can help you find or any questions about our products?"
        
        elif governance_action == "spam_warning":
            # First spam warning
            response = "I'd be happy to help you find what you're looking for. What products or services can I assist you with?"
        
        elif governance_action == "disengage":
            # Disengage after 2 spam turns
            response = "I'm here to help with your shopping needs. Please let me know if you have any questions about our products or services."
        
        elif governance_action == "abuse_stop":
            # Stop immediately for abuse
            response = "I'm unable to continue this conversation. If you need assistance, please contact our support team."
            # Set escalation for abuse
            conv_state.set_escalation("Abusive content detected")
        
        elif governance_action in ["escalation", "proceed_to_journey"]:
            # Handle escalation or unexpected governance routing
            if state.get("escalation_required", False):
                escalation_reason = state.get("escalation_reason", "Escalation required")
                response = "Let me connect you with someone who can better assist you. Please hold on."
                conv_state.set_escalation(escalation_reason)
            else:
                # Fallback for unexpected governance routing
                response = "How can I help you today?"
        
        else:
            # Default business redirect
            response = "How can I help you with your shopping needs today?"
        
        state["response_text"] = response
        
        logger.info(
            f"Governance response generated: {governance_action}",
            extra={
                "tenant_id": conv_state.tenant_id,
                "conversation_id": conv_state.conversation_id,
                "request_id": conv_state.request_id,
                "classification": classification,
                "governance_action": governance_action,
                "casual_turns": casual_turns,
                "spam_turns": spam_turns,
                "max_chattiness_level": max_chattiness_level,
                "response_length": len(response),
                "escalation_required": conv_state.escalation_required,
                "routing_metadata": routing_metadata
            }
        )
        
        return state
    
    def _get_max_casual_turns(self, chattiness_level: int) -> int:
        """
        Get maximum casual turns allowed for chattiness level.
        
        EXACT levels as specified:
        - Level 0: 0 casual turns (strictly business)
        - Level 1: 1 casual turn (1 short greeting)
        - Level 2: 2 casual turns (DEFAULT)
        - Level 3: 4 casual turns
        
        Args:
            chattiness_level: Tenant's max chattiness level (0-3)
            
        Returns:
            Maximum casual turns allowed
        """
        level_map = {
            0: 0,  # Strictly business
            1: 1,  # 1 short greeting
            2: 2,  # Max 2 casual turns (DEFAULT)
            3: 4   # Max 4 casual turns
        }
        return level_map.get(chattiness_level, 2)  # Default to level 2
    
    async def _unknown_handler_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle unknown intent with clarification or fallback response.
        
        Implements exact clarification logic:
        - For medium confidence intents: ask ONE clarifying question
        - For low confidence intents: provide general help message
        - Handle escalation if required
        """
        conv_state = ConversationState.from_dict(state)
        
        # Check if escalation is required first
        if state.get("escalation_required", False):
            escalation_reason = state.get("escalation_reason", "Unknown escalation trigger")
            escalation_metadata = state.get("escalation_metadata", {})
            
            # Set escalation in conversation state
            conv_state.set_escalation(escalation_reason)
            
            # Generate escalation message
            if escalation_metadata.get("escalation_trigger") == "explicit_human_request":
                response = "I'll connect you with a human agent right away. Please hold on while I transfer you to someone who can assist you personally."
            elif escalation_metadata.get("escalation_trigger") == "payment_dispute":
                response = "I understand you're having a payment or delivery issue. Let me connect you with our support team who can help resolve this for you."
            elif escalation_metadata.get("escalation_trigger") == "sensitive_content":
                response = "I'll connect you with a specialist who can better assist you with this matter. Please hold on."
            elif escalation_metadata.get("escalation_trigger") == "user_frustration":
                response = "I can see you're frustrated, and I want to make sure you get the help you need. Let me connect you with a human agent."
            else:
                response = "Let me connect you with a human agent who can better assist you."
            
            state["response_text"] = response
            
            logger.info(
                f"Escalation triggered in unknown handler: {escalation_reason}",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id,
                    "escalation_trigger": escalation_metadata.get("escalation_trigger"),
                    "escalation_metadata": escalation_metadata
                }
            )
            
            return state
        
        # Check if this is a medium confidence intent that needs clarification
        if state.get("needs_clarification", False):
            # Generate ONE clarifying question based on the intent
            clarification_response = self._generate_clarification_question(conv_state, state.get("clarification_metadata", {}))
            state["response_text"] = clarification_response
            
            # Clear clarification flag
            state["needs_clarification"] = False
            
            logger.info(
                f"Asking clarification question for medium confidence intent",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id,
                    "intent": conv_state.intent,
                    "confidence": conv_state.intent_confidence,
                    "clarification_reason": state.get("clarification_reason", ""),
                    "clarification_metadata": state.get("clarification_metadata", {})
                }
            )
        else:
            # Standard unknown intent handling
            logger.debug("Processing unknown intent")
            state["response_text"] = self._generate_unknown_intent_response(conv_state)
        
        return state
    
    def _generate_clarification_question(self, state: ConversationState, metadata: Dict[str, Any] = None) -> str:
        """
        Generate a clarifying question based on the detected intent with enhanced context.
        
        Args:
            state: Current conversation state
            metadata: Additional routing metadata
            
        Returns:
            Clarifying question text
        """
        intent = state.intent
        metadata = metadata or {}
        
        # Intent-specific clarification questions with enhanced context
        clarification_questions = {
            "sales_discovery": "Are you looking to browse our products or do you have something specific in mind?",
            "product_question": "Which product would you like to know more about? You can describe it or give me the name.",
            "support_question": "What can I help you with today? Are you having an issue with a product, service, or order?",
            "order_status": "Are you checking on an existing order? If so, could you share your order number or the phone number used for the order?",
            "discounts_offers": "Are you looking for current promotions, or do you have a specific coupon code you'd like to use?",
            "preferences_consent": "Would you like to update your language preferences, marketing settings, or notification preferences?",
            "payment_help": "Are you having trouble with a payment, need help with payment methods, or checking a transaction status?",
            "human_request": "I'd be happy to connect you with a human agent. What would you like assistance with so I can direct you to the right person?",
            "spam_casual": "How can I help you with your shopping needs today?",
            "unknown": "I'm not sure how I can help with that. Could you tell me what you're looking for today?"
        }
        
        # Get base clarification question
        base_question = clarification_questions.get(intent, clarification_questions["unknown"])
        
        # Add context based on metadata if available
        if metadata.get("clarification_type") == "intent_disambiguation":
            suggested_journey = metadata.get("suggested_journey")
            if suggested_journey == "sales":
                base_question += " I can help you find products, check availability, or place an order."
            elif suggested_journey == "support":
                base_question += " I can help with product questions, troubleshooting, or account issues."
            elif suggested_journey == "orders":
                base_question += " I can help you track orders, check delivery status, or handle order changes."
        
        return base_question
    
    def _generate_unknown_intent_response(self, state: ConversationState) -> str:
        """
        Generate response for truly unknown intents.
        
        Args:
            state: Current conversation state
            
        Returns:
            Unknown intent response text
        """
        # Personalize based on bot name if available
        bot_name = state.bot_name or "I"
        
        # Generate contextual unknown response
        if state.turn_count == 1:
            # First interaction - be welcoming
            return f"Hello! {bot_name}'m here to help you with shopping, orders, and support. What can I assist you with today?"
        else:
            # Subsequent interactions - be helpful
            return f"I'm not sure how I can help with that. {bot_name} can assist with finding products, checking orders, answering questions, or connecting you with support. What would you like to do?"
    
    async def _response_generator_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final response with WhatsApp formatting."""
        # TODO: Implement response generation logic
        logger.debug("Generating response")
        # Response should already be set by journey nodes
        return state
    
    async def _state_persistence_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Persist conversation state to database."""
        # TODO: Implement state persistence
        logger.debug("Persisting conversation state")
        return state


# Global orchestrator instance
_orchestrator_instance: Optional[LangGraphOrchestrator] = None


def get_orchestrator() -> LangGraphOrchestrator:
    """
    Get the global LangGraph orchestrator instance.
    
    Returns:
        LangGraphOrchestrator instance
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = LangGraphOrchestrator()
    return _orchestrator_instance


async def process_conversation_message(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    message_text: str,
    phone_e164: Optional[str] = None,
    customer_id: Optional[str] = None,
    existing_state: Optional[ConversationState] = None
) -> ConversationState:
    """
    Process a conversation message through the LangGraph orchestrator.
    
    This is the main entry point for processing WhatsApp messages through
    the LangGraph-based conversation system.
    
    Args:
        tenant_id: Tenant identifier
        conversation_id: Conversation identifier
        request_id: Request identifier for tracing
        message_text: Incoming message text
        phone_e164: Customer phone number
        customer_id: Optional existing customer ID
        existing_state: Optional existing conversation state
        
    Returns:
        Updated ConversationState after processing
    """
    orchestrator = get_orchestrator()
    return await orchestrator.process_message(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        request_id=request_id,
        message_text=message_text,
        phone_e164=phone_e164,
        customer_id=customer_id,
        existing_state=existing_state
    )