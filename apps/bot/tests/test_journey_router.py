"""
Tests for journey router with exact routing conditions.

Tests the journey router implementation to ensure it follows the exact
routing thresholds and conditions specified in the design.
"""
import pytest
from unittest.mock import Mock, patch
from apps.bot.langgraph.routing import ConversationRouter, RouteDecision
from apps.bot.conversation_state import ConversationState


class TestJourneyRouter:
    """Test journey router with exact routing conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = ConversationRouter()
    
    def create_test_state(self, **kwargs):
        """Create test conversation state with defaults."""
        defaults = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "unknown",
            "intent_confidence": 0.5,
            "governor_classification": "business",
            "governor_confidence": 0.8,
            "max_chattiness_level": 2,
            "casual_turns": 0,
            "spam_turns": 0,
            "incoming_message": "test message"
        }
        defaults.update(kwargs)
        return ConversationState(**defaults)
    
    def test_high_confidence_intent_routing(self):
        """Test routing for high confidence intents (>= 0.70)."""
        # Test sales intent with high confidence
        state = self.create_test_state(
            intent="sales_discovery",
            intent_confidence=0.85
        )
        
        decision = self.router.route_to_journey(state)
        
        assert decision.journey == "sales"
        assert decision.confidence == 0.85
        assert "High confidence intent" in decision.reason
        assert decision.metadata["routing_threshold"] == "high_confidence"
        assert decision.metadata["threshold_met"] is True
        assert not decision.should_clarify
    
    def test_medium_confidence_intent_clarification(self):
        """Test clarification for medium confidence intents (0.50-0.70)."""
        # Test product question with medium confidence
        state = self.create_test_state(
            intent="product_question",
            intent_confidence=0.65
        )
        
        decision = self.router.route_to_journey(state)
        
        assert decision.journey == "unknown"
        assert decision.confidence == 0.65
        assert "Medium confidence intent" in decision.reason
        assert "needs clarification" in decision.reason
        assert decision.metadata["routing_threshold"] == "medium_confidence"
        assert decision.metadata["needs_clarification"] is True
        assert decision.should_clarify is True
    
    def test_low_confidence_intent_unknown(self):
        """Test routing for low confidence intents (< 0.50)."""
        # Test unknown intent with low confidence
        state = self.create_test_state(
            intent="unknown",
            intent_confidence=0.25
        )
        
        decision = self.router.route_to_journey(state)
        
        assert decision.journey == "unknown"
        assert decision.confidence == 0.25
        assert "Low confidence intent" in decision.reason
        assert decision.metadata["routing_threshold"] == "low_confidence"
        assert decision.metadata["threshold_met"] is False
        assert not decision.should_clarify
    
    def test_intent_to_journey_mapping(self):
        """Test exact intent to journey mapping."""
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
        
        for intent, expected_journey in intent_journey_map.items():
            actual_journey = self.router._intent_to_journey(intent)
            assert actual_journey == expected_journey, f"Intent {intent} should map to {expected_journey}, got {actual_journey}"
    
    def test_governance_casual_within_limits(self):
        """Test casual conversation within chattiness limits."""
        # Test casual with 1 turn, level 2 (allows 2 turns)
        state = self.create_test_state(
            governor_classification="casual",
            casual_turns=1,
            max_chattiness_level=2
        )
        
        decision = self.router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "within limits" in decision.reason
        assert decision.metadata["governance_action"] == "friendly_casual_response"
        assert decision.metadata["casual_turns"] == 1
        assert decision.metadata["max_allowed"] == 2
    
    def test_governance_casual_exceeds_limits(self):
        """Test casual conversation exceeding chattiness limits."""
        # Test casual with 3 turns, level 2 (allows 2 turns)
        state = self.create_test_state(
            governor_classification="casual",
            casual_turns=3,
            max_chattiness_level=2
        )
        
        decision = self.router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "Exceeded casual turn limit" in decision.reason
        assert decision.metadata["governance_action"] == "redirect_to_business"
        assert decision.metadata["casual_turns"] == 3
        assert decision.metadata["max_allowed"] == 2
    
    def test_governance_spam_warning(self):
        """Test spam detection with warning (first spam turn)."""
        state = self.create_test_state(
            governor_classification="spam",
            spam_turns=1
        )
        
        decision = self.router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "Spam detected - warning" in decision.reason
        assert decision.metadata["governance_action"] == "spam_warning"
        assert decision.metadata["spam_turns"] == 1
    
    def test_governance_spam_disengage(self):
        """Test spam disengagement after 2 turns."""
        state = self.create_test_state(
            governor_classification="spam",
            spam_turns=2
        )
        
        decision = self.router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "Exceeded spam turn limit" in decision.reason
        assert decision.metadata["governance_action"] == "disengage"
        assert decision.metadata["spam_turns"] == 2
    
    def test_governance_abuse_immediate_stop(self):
        """Test immediate stop for abuse classification."""
        state = self.create_test_state(
            governor_classification="abuse"
        )
        
        decision = self.router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "Abuse detected - immediate stop" in decision.reason
        assert decision.metadata["governance_action"] == "abuse_stop"
    
    def test_governance_business_proceed(self):
        """Test business classification proceeding to journey routing."""
        state = self.create_test_state(
            governor_classification="business"
        )
        
        decision = self.router.route_after_governance(state)
        
        assert decision.journey == "business"
        assert "Business conversation - proceed to journey routing" in decision.reason
        assert decision.metadata["governance_action"] == "proceed_to_journey"
    
    def test_escalation_explicit_human_request(self):
        """Test escalation for explicit human requests."""
        state = self.create_test_state(
            incoming_message="I want to speak to a human agent"
        )
        
        escalation_decision = self.router.check_escalation_triggers(state)
        
        assert escalation_decision is not None
        assert escalation_decision.journey == "governance"
        assert "Explicit human request detected" in escalation_decision.reason
        assert escalation_decision.metadata["escalation_trigger"] == "explicit_human_request"
        assert escalation_decision.metadata["escalation_required"] is True
    
    def test_escalation_payment_dispute(self):
        """Test escalation for payment disputes."""
        state = self.create_test_state(
            incoming_message="I paid but never received my order"
        )
        
        escalation_decision = self.router.check_escalation_triggers(state)
        
        assert escalation_decision is not None
        assert escalation_decision.journey == "governance"
        assert "Payment dispute or delivery complaint detected" in escalation_decision.reason
        assert escalation_decision.metadata["escalation_trigger"] == "payment_dispute"
        assert escalation_decision.metadata["escalation_required"] is True
    
    def test_escalation_sensitive_content(self):
        """Test escalation for sensitive/legal content."""
        state = self.create_test_state(
            incoming_message="I need legal advice about this"
        )
        
        escalation_decision = self.router.check_escalation_triggers(state)
        
        assert escalation_decision is not None
        assert escalation_decision.journey == "governance"
        assert "Sensitive/legal/medical content detected" in escalation_decision.reason
        assert escalation_decision.metadata["escalation_trigger"] == "sensitive_content"
        assert escalation_decision.metadata["escalation_required"] is True
    
    def test_escalation_user_frustration(self):
        """Test escalation for user frustration with multiple turns."""
        state = self.create_test_state(
            incoming_message="This is frustrating and not helping",
            turn_count=4
        )
        
        escalation_decision = self.router.check_escalation_triggers(state)
        
        assert escalation_decision is not None
        assert escalation_decision.journey == "governance"
        assert "User frustration detected with multiple turns" in escalation_decision.reason
        assert escalation_decision.metadata["escalation_trigger"] == "user_frustration"
        assert escalation_decision.metadata["escalation_required"] is True
    
    def test_no_escalation_needed(self):
        """Test no escalation for normal business messages."""
        state = self.create_test_state(
            incoming_message="I want to buy a product"
        )
        
        escalation_decision = self.router.check_escalation_triggers(state)
        
        assert escalation_decision is None
    
    def test_chattiness_level_limits(self):
        """Test exact chattiness level limits."""
        # Test all chattiness levels
        expected_limits = {
            0: 0,  # Strictly business
            1: 1,  # 1 short greeting
            2: 2,  # Max 2 casual turns (DEFAULT)
            3: 4   # Max 4 casual turns
        }
        
        for level, expected_limit in expected_limits.items():
            actual_limit = self.router._get_max_casual_turns(level)
            assert actual_limit == expected_limit, f"Chattiness level {level} should allow {expected_limit} turns, got {actual_limit}"
    
    def test_full_routing_flow_high_confidence(self):
        """Test complete routing flow for high confidence business intent."""
        state = self.create_test_state(
            intent="sales_discovery",
            intent_confidence=0.85,
            governor_classification="business"
        )
        
        decision = self.router.route_conversation(state)
        
        assert decision.journey == "sales"
        assert decision.confidence == 0.85
        assert "High confidence intent" in decision.reason
        assert not decision.should_clarify
    
    def test_full_routing_flow_governance_override(self):
        """Test governance overriding intent routing."""
        state = self.create_test_state(
            intent="sales_discovery",
            intent_confidence=0.85,  # High confidence
            governor_classification="spam",  # But spam classification
            spam_turns=2
        )
        
        decision = self.router.route_conversation(state)
        
        # Governance should override intent routing
        assert decision.journey == "governance"
        assert "Exceeded spam turn limit" in decision.reason
        assert decision.metadata["governance_action"] == "disengage"
    
    def test_full_routing_flow_escalation_override(self):
        """Test escalation overriding normal routing."""
        state = self.create_test_state(
            intent="sales_discovery",
            intent_confidence=0.85,
            governor_classification="business",
            incoming_message="I want to speak to a human"
        )
        
        decision = self.router.route_conversation(state)
        
        # Escalation should override normal routing
        assert decision.journey == "governance"
        assert "Explicit human request detected" in decision.reason
        assert decision.metadata["escalation_required"] is True


if __name__ == "__main__":
    pytest.main([__file__])