"""
LangGraph Routing Infrastructure.

This module provides routing logic for the LangGraph orchestration system,
including journey routing and conversation flow control.
"""
import logging
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field

from apps.bot.conversation_state import ConversationState, Intent, Journey, GovernorClass

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
    """
    
    # Routing thresholds as specified in design (EXACT)
    INTENT_HIGH_CONFIDENCE = 0.70
    INTENT_MEDIUM_CONFIDENCE = 0.50
    LANGUAGE_CONFIDENCE_THRESHOLD = 0.75
    
    def __init__(self):
        """Initialize conversation router."""
        self.logger = logging.getLogger(__name__)
    
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
        message = (state.incoming_message or "").lower()
        
        # 1. Explicit human request
        human_keywords = ['agent', 'human', 'person', 'call me', 'speak to someone', 'representative', 'manager', 'supervisor']
        if any(keyword in message for keyword in human_keywords):
            return RouteDecision(
                journey="governance",
                reason="Explicit human request detected",
                confidence=1.0,
                metadata={
                    "escalation_trigger": "explicit_human_request",
                    "escalation_required": True,
                    "keywords_found": [kw for kw in human_keywords if kw in message]
                }
            )
        
        # 2. Payment disputes and complaints
        payment_dispute_keywords = [
            'i paid but', 'already paid', 'charged twice', 'wrong amount', 'refund',
            'chargeback', 'dispute', 'fraud', 'unauthorized', 'delivery problem',
            'never received', 'damaged', 'broken on arrival', 'wrong item'
        ]
        if any(keyword in message for keyword in payment_dispute_keywords):
            return RouteDecision(
                journey="governance",
                reason="Payment dispute or delivery complaint detected",
                confidence=0.9,
                metadata={
                    "escalation_trigger": "payment_dispute",
                    "escalation_required": True,
                    "keywords_found": [kw for kw in payment_dispute_keywords if kw in message]
                }
            )
        
        # 3. Check if escalation is already flagged in state
        if state.escalation_required:
            return RouteDecision(
                journey="governance",
                reason=f"Escalation already required: {state.escalation_reason}",
                confidence=1.0,
                metadata={
                    "escalation_trigger": "state_flagged",
                    "escalation_required": True,
                    "escalation_reason": state.escalation_reason
                }
            )
        
        # 4. Sensitive/legal/medical content (basic detection)
        sensitive_keywords = [
            'legal', 'lawyer', 'attorney', 'court', 'sue', 'lawsuit',
            'medical', 'doctor', 'hospital', 'emergency', 'urgent',
            'death', 'died', 'suicide', 'depression', 'mental health'
        ]
        if any(keyword in message for keyword in sensitive_keywords):
            return RouteDecision(
                journey="governance",
                reason="Sensitive/legal/medical content detected",
                confidence=0.8,
                metadata={
                    "escalation_trigger": "sensitive_content",
                    "escalation_required": True,
                    "keywords_found": [kw for kw in sensitive_keywords if kw in message]
                }
            )
        
        # 5. User frustration indicators
        frustration_keywords = [
            'frustrated', 'angry', 'upset', 'terrible', 'awful', 'horrible',
            'useless', 'stupid', 'waste of time', 'not helping', 'doesnt work',
            'fed up', 'sick of', 'enough', 'ridiculous'
        ]
        if any(keyword in message for keyword in frustration_keywords):
            # Check if we've had multiple turns without resolution
            if state.turn_count >= 3:
                return RouteDecision(
                    journey="governance",
                    reason="User frustration detected with multiple turns",
                    confidence=0.7,
                    metadata={
                        "escalation_trigger": "user_frustration",
                        "escalation_required": True,
                        "turn_count": state.turn_count,
                        "keywords_found": [kw for kw in frustration_keywords if kw in message]
                    }
                )
        
        # No escalation triggers found
        return None
    
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