"""
Integration tests for LangGraph orchestrator with journey router.

Tests the complete orchestration flow including journey routing,
governance, and escalation handling.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.bot.langgraph.orchestrator import LangGraphOrchestrator
from apps.bot.conversation_state import ConversationState


class TestOrchestratorIntegration:
    """Test orchestrator integration with journey router."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = LangGraphOrchestrator()
    
    @pytest.mark.asyncio
    async def test_route_to_journey_high_confidence(self):
        """Test routing to journey with high confidence intent."""
        # Create test state with high confidence sales intent
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "sales_discovery",
            "intent_confidence": 0.85,
            "governor_classification": "business",
            "governor_confidence": 0.9,
            "incoming_message": "I want to buy something"
        }
        
        # Test routing decision
        journey = self.orchestrator._route_to_journey(state)
        
        # Should route to sales journey
        assert journey == "sales"
        assert state["journey"] == "sales"
        assert state["routing_decision"] == "High confidence intent: sales_discovery (confidence: 0.85)"
        assert state["routing_confidence"] == 0.85
        assert state["routing_metadata"]["routing_threshold"] == "high_confidence"
        assert state["routing_metadata"]["threshold_met"] is True
        assert not state.get("needs_clarification", False)
    
    @pytest.mark.asyncio
    async def test_route_to_journey_medium_confidence_clarification(self):
        """Test clarification for medium confidence intent."""
        # Create test state with medium confidence intent
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "product_question",
            "intent_confidence": 0.65,
            "governor_classification": "business",
            "governor_confidence": 0.8,
            "incoming_message": "tell me about it"
        }
        
        # Test routing decision
        journey = self.orchestrator._route_to_journey(state)
        
        # Should route to unknown for clarification
        assert journey == "unknown"
        assert state["journey"] == "unknown"
        assert "Medium confidence intent" in state["routing_decision"]
        assert "needs clarification" in state["routing_decision"]
        assert state["needs_clarification"] is True
        assert state["routing_metadata"]["needs_clarification"] is True
        assert state["routing_metadata"]["routing_threshold"] == "medium_confidence"
    
    @pytest.mark.asyncio
    async def test_route_governance_override(self):
        """Test governance overriding intent routing."""
        # Create test state with high confidence intent but spam classification
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "sales_discovery",
            "intent_confidence": 0.85,  # High confidence
            "governor_classification": "spam",  # But spam
            "governor_confidence": 0.9,
            "spam_turns": 2,  # Exceeded limit
            "incoming_message": "test test test"
        }
        
        # Test routing decision
        journey = self.orchestrator._route_to_journey(state)
        
        # Governance should override intent routing
        assert journey == "governance"
        assert state["journey"] == "governance"
        assert "Exceeded spam turn limit" in state["routing_decision"]
        assert state["routing_metadata"]["governance_action"] == "disengage"
    
    @pytest.mark.asyncio
    async def test_route_escalation_override(self):
        """Test escalation overriding normal routing."""
        # Create test state with escalation trigger
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "sales_discovery",
            "intent_confidence": 0.85,
            "governor_classification": "business",
            "governor_confidence": 0.9,
            "incoming_message": "I want to speak to a human agent"
        }
        
        # Test routing decision
        journey = self.orchestrator._route_to_journey(state)
        
        # Escalation should override normal routing
        assert journey == "governance"
        assert state["journey"] == "governance"
        assert "Explicit human request detected" in state["routing_decision"]
        assert state["escalation_required"] is True
        assert state["escalation_reason"] == "explicit_human_request"
        assert state["routing_metadata"]["escalation_required"] is True
    
    @pytest.mark.asyncio
    async def test_journey_transition_tracking(self):
        """Test journey transition tracking and logging."""
        # Create test state with journey transition
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "support_question",
            "intent_confidence": 0.75,
            "governor_classification": "business",
            "governor_confidence": 0.8,
            "journey": "unknown",  # Previous journey
            "incoming_message": "I need help with my order"
        }
        
        # Mock the journey router node
        updated_state = await self.orchestrator._journey_router_node(state)
        
        # Should track journey transition
        assert updated_state["journey"] == "support"
        assert updated_state["previous_journey"] == "unknown"
        assert updated_state["journey_transition_reason"] is not None
        assert updated_state["journey_transition_confidence"] is not None
        assert updated_state["journey_transition_metadata"] is not None
    
    @pytest.mark.asyncio
    async def test_unknown_handler_clarification(self):
        """Test unknown handler with clarification request."""
        # Create test state needing clarification
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "intent": "product_question",
            "intent_confidence": 0.65,
            "needs_clarification": True,
            "clarification_reason": "Medium confidence intent",
            "clarification_metadata": {
                "clarification_type": "intent_disambiguation",
                "suggested_journey": "sales"
            },
            "incoming_message": "tell me about it"
        }
        
        # Test unknown handler
        updated_state = await self.orchestrator._unknown_handler_node(state)
        
        # Should generate clarification question
        assert "response_text" in updated_state
        assert "Which product would you like to know more about" in updated_state["response_text"]
        assert updated_state["needs_clarification"] is False
    
    @pytest.mark.asyncio
    async def test_unknown_handler_escalation(self):
        """Test unknown handler with escalation."""
        # Create test state with escalation
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "escalation_required": True,
            "escalation_reason": "explicit_human_request",
            "escalation_metadata": {
                "escalation_trigger": "explicit_human_request"
            },
            "incoming_message": "I want to speak to a human"
        }
        
        # Test unknown handler
        updated_state = await self.orchestrator._unknown_handler_node(state)
        
        # Should generate escalation message
        assert "response_text" in updated_state
        assert "connect you with a human agent" in updated_state["response_text"]
    
    @pytest.mark.asyncio
    async def test_governance_response_actions(self):
        """Test governance response with different actions."""
        # Test redirect to business action
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "governor_classification": "casual",
            "casual_turns": 3,
            "max_chattiness_level": 2,
            "routing_metadata": {
                "governance_action": "redirect_to_business"
            }
        }
        
        updated_state = await self.orchestrator._governance_response_node(state)
        
        # Should generate business redirect response
        assert "response_text" in updated_state
        assert "help you with our products or services" in updated_state["response_text"]
    
    @pytest.mark.asyncio
    async def test_governance_response_escalation(self):
        """Test governance response with escalation."""
        # Test escalation in governance
        state = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "governor_classification": "abuse",
            "escalation_required": True,
            "escalation_reason": "Abusive content detected",
            "routing_metadata": {
                "governance_action": "abuse_stop"
            }
        }
        
        updated_state = await self.orchestrator._governance_response_node(state)
        
        # Should generate stop message
        assert "response_text" in updated_state
        assert "unable to continue this conversation" in updated_state["response_text"]


if __name__ == "__main__":
    pytest.main([__file__])