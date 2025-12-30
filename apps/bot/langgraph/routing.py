"""
LangGraph Routing Infrastructure.

This module provides routing logic for the LangGraph orchestration system,
including journey routing and conversation flow control with enhanced
escalation rules and human handoff management.
"""
import logging
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field

from apps.bot.conversation_state import ConversationState, Intent, Journey, GovernorClass
from apps.bot.services.escalation_service import EscalationService, EscalationContext

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """
    Represents a routing decision for conversation flow.
    
    Contains the target journey and reasoning for the routing decision.
    """
    journey: Journey
    reason: str
    confidence: float
    should_clarify: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def target_node(self) -> str:
        """Get target node name for LangGraph routing."""
        if self.journey in ["sales", "support", "orders", "offers", "prefs", "governance", "unknown"]:
            return f"{self.journey}_journey_entry" if self.journey != "unknown" else "unknown_journey_entry"
        else:
            # For governance responses
            return self.journey


class ConversationRouter:
    """
    Router for managing conversation flow through LangGraph nodes.
    
    Implements the routing logic based on intent classification,
    confidence thresholds, and conversation governance rules with
    exact routing conditions as specified in the design.
    
    Enhanced with comprehensive escalation rules and human handoff management.
    """
    
    # Routing thresholds as specified in design (EXACT)
    INTENT_HIGH_CONFIDENCE = 0.70
    INTENT_MEDIUM_CONFIDENCE = 0.50
    LANGUAGE_CONFIDENCE_THRESHOLD = 0.75
    
    def __init__(self):
        """Initialize conversation router with escalation service."""
        self.logger = logging.getLogger(__name__)
        self.escalation_service = EscalationService()
        self._escalation_contexts = {}  # Track escalation context per conversation
    
    def route_conversation(self, state: ConversationState) -> RouteDecision:
        """
        Main routing method that combines all routing logic.
        
        This method orchestrates the complete routing flow with EXACT conditions:
        1. Check governance classification first (can override intent routing)
        2. If business, proceed to intent-based journey routing with exact thresholds
        3. Apply confidence thresholds and escalation checks
        4. Handle clarification requests for medium confidence intents
        
        Args:
            state: Current conversation state
            
        Returns:
            RouteDecision for next node
        """
        # First check governance - this can override intent routing
        governance_decision = self.route_after_governance(state)
        
        # If governance allows business conversation, proceed to journey routing
        if governance_decision.journey == "business":
            return self.route_to_journey(state)
        
        # Otherwise return governance decision (casual/spam/abuse handling)
        return governance_decision
    
    def route_after_governance(self, state: ConversationState) -> RouteDecision:
        """
        Route after governance classification with EXACT routing logic.
        
        Implements exact governance routing:
        - business: proceed to journey routing
        - casual: check chattiness limits, redirect if exceeded
        - spam: allow max 2 turns before disengaging
        - abuse: stop immediately
        
        Args:
            state: Current conversation state
            
        Returns:
            RouteDecision with target node
        """
        classification = state.governor_classification
        confidence = state.governor_confidence
        
        if classification == "casual":
            # Check if we've exceeded casual turn limits
            max_casual = self._get_max_casual_turns(state.max_chattiness_level)
            if state.casual_turns > max_casual:
                return RouteDecision(
                    journey="governance",
                    reason=f"Exceeded casual turn limit ({state.casual_turns}/{max_casual})",
                    confidence=confidence,
                    metadata={
                        "governance_action": "redirect_to_business",
                        "casual_turns": state.casual_turns,
                        "max_allowed": max_casual,
                        "chattiness_level": state.max_chattiness_level
                    }
                )
            else:
                # Within casual limits - allow but still route to governance for friendly response
                return RouteDecision(
                    journey="governance",
                    reason="Casual conversation within limits",
                    confidence=confidence,
                    metadata={
                        "governance_action": "friendly_casual_response",
                        "casual_turns": state.casual_turns,
                        "max_allowed": max_casual
                    }
                )
        
        elif classification == "spam":
            # Allow max 2 spam turns before disengaging
            if state.spam_turns >= 2:
                return RouteDecision(
                    journey="governance", 
                    reason=f"Exceeded spam turn limit ({state.spam_turns}/2)",
                    confidence=confidence,
                    metadata={
                        "governance_action": "disengage",
                        "spam_turns": state.spam_turns
                    }
                )
            else:
                return RouteDecision(
                    journey="governance",
                    reason="Spam detected - warning",
                    confidence=confidence,
                    metadata={
                        "governance_action": "spam_warning",
                        "spam_turns": state.spam_turns
                    }
                )
        
        elif classification == "abuse":
            # Immediate stop for abuse
            return RouteDecision(
                journey="governance",
                reason="Abuse detected - immediate stop",
                confidence=confidence,
                metadata={
                    "governance_action": "abuse_stop"
                }
            )
        
        # Business classification - proceed to journey router
        return RouteDecision(
            journey="business",
            reason="Business conversation - proceed to journey routing",
            confidence=confidence,
            metadata={
                "governance_action": "proceed_to_journey"
            }
        )
    
    def route_to_journey(self, state: ConversationState) -> RouteDecision:
        """
        Route to appropriate journey entry node with EXACT routing conditions.
        
        Implements exact routing thresholds:
        - confidence >= 0.70: route to suggested journey
        - 0.50 <= confidence < 0.70: ask ONE clarifying question then re-classify
        - confidence < 0.50: route to unknown handler
        
        Also checks for escalation triggers before routing.
        
        Args:
            state: Current conversation state
            
        Returns:
            RouteDecision with target journey entry node
        """
        # Check for escalation triggers first
        escalation_decision = self.check_escalation_triggers(state)
        if escalation_decision:
            return escalation_decision
        
        intent = state.intent
        confidence = state.intent_confidence
        
        # High confidence: route to journey
        if confidence >= self.INTENT_HIGH_CONFIDENCE:
            journey = self._intent_to_journey(intent)
            return RouteDecision(
                journey=journey,
                reason=f"High confidence intent: {intent} (confidence: {confidence:.2f})",
                confidence=confidence,
                metadata={
                    "routing_threshold": "high_confidence",
                    "intent": intent,
                    "suggested_journey": journey,
                    "threshold_met": True
                }
            )
        
        # Medium confidence: ask clarifying question
        elif confidence >= self.INTENT_MEDIUM_CONFIDENCE:
            return RouteDecision(
                journey="unknown",
                reason=f"Medium confidence intent: {intent} (confidence: {confidence:.2f}) - needs clarification",
                confidence=confidence,
                should_clarify=True,
                metadata={
                    "routing_threshold": "medium_confidence",
                    "intent": intent,
                    "needs_clarification": True,
                    "clarification_type": "intent_disambiguation",
                    "suggested_journey": self._intent_to_journey(intent)
                }
            )
        
        # Low confidence: route to unknown handler
        else:
            return RouteDecision(
                journey="unknown",
                reason=f"Low confidence intent: {intent} (confidence: {confidence:.2f})",
                confidence=confidence,
                metadata={
                    "routing_threshold": "low_confidence",
                    "intent": intent,
                    "threshold_met": False
                }
            )
    
    def check_escalation_triggers(self, state: ConversationState) -> Optional[RouteDecision]:
        """
        Check for EXACT escalation triggers that require immediate human handoff.
        
        Enhanced implementation using EscalationService for comprehensive
        escalation detection and context tracking.
        
        Escalate immediately if ANY is true:
        - User explicitly asks for human ("agent", "human", "call me")
        - Payment disputes ("I paid but..."), chargebacks, refunds, delivery complaints beyond policy
        - Missing authoritative info after RAG/tool attempts (unclear order lookup)
        - Repeated failures (2 consecutive tool errors OR 3 clarification loops)
        - Sensitive/legal/medical content (tenant policy)
        - User frustration detected + failure to resolve in 2 turns
        
        Args:
            state: Current conversation state
            
        Returns:
            RouteDecision for escalation or None if no escalation needed
        """
        # Get or create escalation context for this conversation
        escalation_context = self._get_escalation_context(state.conversation_id)
        
        # Check escalation triggers using enhanced service
        should_escalate, reason, priority, category = self.escalation_service.check_escalation_triggers(
            state, escalation_context
        )
        
        if should_escalate:
            # Log escalation decision
            self.logger.info(
                f"Escalation triggered for conversation {state.conversation_id}: "
                f"reason={reason}, priority={priority}, category={category}"
            )
            
            # Create escalation log entry
            self._log_escalation_decision(state, reason, escalation_context)
            
            return RouteDecision(
                journey="governance",
                reason=f"Escalation required: {reason}",
                confidence=1.0,
                metadata={
                    "escalation_trigger": reason,
                    "escalation_required": True,
                    "escalation_reason": reason,
                    "escalation_priority": priority,
                    "escalation_category": category,
                    "escalation_context": {
                        "consecutive_tool_errors": escalation_context.consecutive_tool_errors,
                        "clarification_loops": escalation_context.clarification_loops,
                        "turn_count": state.turn_count
                    }
                }
            )
        
        # No escalation triggers found
        return None
    
    def _get_escalation_context(self, conversation_id: str) -> EscalationContext:
        """
        Get or create escalation context for a conversation.
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            EscalationContext for the conversation
        """
        if conversation_id not in self._escalation_contexts:
            self._escalation_contexts[conversation_id] = EscalationContext()
        
        return self._escalation_contexts[conversation_id]
    
    def track_tool_failure(self, conversation_id: str, tool_name: str, error_message: str):
        """
        Track tool failure for escalation decision making.
        
        Args:
            conversation_id: Conversation identifier
            tool_name: Name of the failed tool
            error_message: Error message from tool failure
        """
        escalation_context = self._get_escalation_context(conversation_id)
        self.escalation_service.track_tool_failure(escalation_context, tool_name, error_message)
    
    def track_clarification_loop(self, conversation_id: str):
        """
        Track clarification loop for escalation decision making.
        
        Args:
            conversation_id: Conversation identifier
        """
        escalation_context = self._get_escalation_context(conversation_id)
        self.escalation_service.track_clarification_loop(escalation_context)
    
    def reset_failure_counters(self, conversation_id: str):
        """
        Reset failure counters after successful action.
        
        Args:
            conversation_id: Conversation identifier
        """
        escalation_context = self._get_escalation_context(conversation_id)
        self.escalation_service.reset_failure_counters(escalation_context)
    
    def _log_escalation_decision(
        self, 
        state: ConversationState, 
        reason: str, 
        escalation_context: EscalationContext
    ):
        """
        Log escalation decision for analytics and debugging.
        
        Args:
            state: Current conversation state
            reason: Escalation reason
            escalation_context: Escalation context
        """
        try:
            from apps.bot.models import EscalationLog
            from apps.tenants.models import Customer
            
            # Get customer if available
            customer = None
            if state.customer_id:
                try:
                    customer = Customer.objects.get(id=state.customer_id, tenant_id=state.tenant_id)
                except Customer.DoesNotExist:
                    pass
            
            # Create escalation log
            EscalationLog.objects.create(
                tenant_id=state.tenant_id,
                customer=customer,
                conversation_id=state.conversation_id,
                request_id=state.request_id,
                escalation_trigger=reason,
                escalation_reason=f"Escalation triggered: {reason}",
                journey=state.journey,
                journey_step=getattr(state, f"{state.journey}_step", "unknown"),
                turn_count=state.turn_count,
                intent=state.intent,
                intent_confidence=state.intent_confidence,
                consecutive_tool_errors=escalation_context.consecutive_tool_errors,
                clarification_loops=escalation_context.clarification_loops,
                escalation_successful=True,
                metadata={
                    "escalation_context": {
                        "conversation_summary": escalation_context.conversation_summary,
                        "current_journey": escalation_context.current_journey,
                        "current_step": escalation_context.current_step,
                        "escalation_triggers": escalation_context.escalation_triggers
                    }
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to log escalation decision: {str(e)}")
    
    def cleanup_escalation_context(self, conversation_id: str):
        """
        Clean up escalation context when conversation ends.
        
        Args:
            conversation_id: Conversation identifier
        """
        if conversation_id in self._escalation_contexts:
            del self._escalation_contexts[conversation_id]
    
    def _intent_to_journey(self, intent: Intent) -> Journey:
        """
        Map intent to journey.
        
        Args:
            intent: Detected intent
            
        Returns:
            Corresponding journey
        """
        intent_journey_map = {
            "sales_discovery": "sales",
            "product_question": "sales",
            "support_question": "support",
            "order_status": "orders",
            "discounts_offers": "offers",
            "preferences_consent": "prefs",
            "payment_help": "support",
            "human_request": "governance",
            "spam_casual": "governance",
            "unknown": "unknown"
        }
        
        return intent_journey_map.get(intent, "unknown")
    
    def _get_max_casual_turns(self, chattiness_level: int) -> int:
        """
        Get maximum casual turns based on chattiness level.
        
        Args:
            chattiness_level: Tenant chattiness level (0-3)
            
        Returns:
            Maximum allowed casual turns
        """
        # Chattiness levels as specified in design:
        # Level 0: strictly business (0 casual turns)
        # Level 1: 1 short greeting
        # Level 2: max 2 casual turns (DEFAULT)
        # Level 3: max 4 casual turns
        casual_turn_limits = {
            0: 0,  # Strictly business
            1: 1,  # Minimal friendliness
            2: 2,  # Friendly but bounded (default)
            3: 4   # More friendly
        }
        
        return casual_turn_limits.get(chattiness_level, 2)  # Default to level 2


class JourneyRouter:
    """
    Router for managing flow within specific journeys.
    
    Handles routing within sales, support, orders, and other journey subgraphs.
    """
    
    def __init__(self):
        """Initialize journey router."""
        self.logger = logging.getLogger(__name__)
    
    def route_sales_journey(self, state: ConversationState, current_step: str) -> RouteDecision:
        """
        Route within sales journey based on current step and state.
        
        Args:
            state: Current conversation state
            current_step: Current step in sales journey
            
        Returns:
            RouteDecision for next step
        """
        # Sales journey routing logic (placeholder for now)
        # Will be implemented in Phase 3 - Core Journeys
        
        if current_step == "entry":
            return RouteDecision(
                journey="sales",
                reason="Starting sales journey",
                confidence=1.0
            )
        
        # Default to exit for now
        return RouteDecision(
            journey="unknown",
            reason="Sales journey placeholder",
            confidence=1.0
        )
    
    def route_support_journey(self, state: ConversationState, current_step: str) -> RouteDecision:
        """
        Route within support journey based on current step and state.
        
        Args:
            state: Current conversation state
            current_step: Current step in support journey
            
        Returns:
            RouteDecision for next step
        """
        # Support journey routing logic (placeholder for now)
        # Will be implemented in Phase 3 - Core Journeys
        
        if current_step == "entry":
            return RouteDecision(
                journey="support",
                reason="Starting support journey with knowledge retrieval",
                confidence=1.0
            )
        
        # Default to exit for now
        return RouteDecision(
            journey="unknown",
            reason="Support journey placeholder",
            confidence=1.0
        )