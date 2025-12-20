"""
Tests for LangGraph infrastructure setup.

This module tests the core LangGraph orchestration infrastructure
to ensure proper setup and basic functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from django.test import TestCase

from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.langgraph.orchestrator import LangGraphOrchestrator
from apps.bot.langgraph.nodes import NodeRegistry, BaseNode, ToolNode, LLMNode
from apps.bot.langgraph.routing import ConversationRouter, RouteDecision


class TestConversationStateInfrastructure(TestCase):
    """Test ConversationState infrastructure."""
    
    def test_conversation_state_creation(self):
        """Test ConversationState can be created with required fields."""
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        assert state.tenant_id == "test-tenant"
        assert state.conversation_id == "test-conv"
        assert state.request_id == "test-req"
        assert state.intent == "unknown"
        assert state.journey == "unknown"
        assert state.turn_count == 0
    
    def test_conversation_state_validation(self):
        """Test ConversationState validation."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Should not raise exception
        state.validate()
        
        # Test invalid intent
        state.intent = "invalid_intent"
        with pytest.raises(ValueError, match="Invalid intent"):
            state.validate()
    
    def test_conversation_state_serialization(self):
        """Test ConversationState serialization/deserialization."""
        original_state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            intent="sales_discovery",
            intent_confidence=0.8
        )
        
        # Serialize to JSON
        json_str = original_state.to_json()
        
        # Deserialize from JSON
        restored_state = ConversationState.from_json(json_str)
        
        assert restored_state.tenant_id == original_state.tenant_id
        assert restored_state.conversation_id == original_state.conversation_id
        assert restored_state.intent == original_state.intent
        assert restored_state.intent_confidence == original_state.intent_confidence
    
    def test_conversation_state_updates(self):
        """Test ConversationState update methods."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Test intent update
        state.update_intent("sales_discovery", 0.9)
        assert state.intent == "sales_discovery"
        assert state.intent_confidence == 0.9
        
        # Test language update
        state.update_language("sw", 0.8)
        assert state.response_language == "sw"
        assert state.language_confidence == 0.8
        
        # Test governor update
        state.update_governor("casual", 0.7)
        assert state.governor_classification == "casual"
        assert state.governor_confidence == 0.7
        
        # Test turn increments
        state.increment_turn()
        assert state.turn_count == 1
        
        state.increment_casual_turns()
        assert state.casual_turns == 1
        
        # Test escalation
        state.set_escalation("Test reason", "ticket-123")
        assert state.escalation_required is True
        assert state.escalation_reason == "Test reason"
        assert state.handoff_ticket_id == "ticket-123"


class TestNodeRegistry(TestCase):
    """Test NodeRegistry functionality."""
    
    def test_node_registry_initialization(self):
        """Test NodeRegistry initializes with default nodes."""
        registry = NodeRegistry()
        
        # Should have default nodes
        nodes = registry.list_nodes()
        assert len(nodes) > 0
        
        # Should have key tool nodes
        assert "tenant_get_context" in nodes
        assert "customer_get_or_create" in nodes
        assert "catalog_search" in nodes
        
        # Should have placeholder LLM nodes
        assert "intent_classify" in nodes
        assert "language_policy" in nodes
        assert "governor_spam_casual" in nodes
    
    def test_node_registration(self):
        """Test custom node registration."""
        registry = NodeRegistry()
        
        # Create mock node
        mock_node = Mock(spec=BaseNode)
        mock_node.name = "test_node"
        
        # Register node
        registry.register_node("test_node", mock_node)
        
        # Verify registration
        assert "test_node" in registry.list_nodes()
        assert registry.get_node("test_node") == mock_node
    
    def test_node_retrieval(self):
        """Test node retrieval from registry."""
        registry = NodeRegistry()
        
        # Get existing node
        node = registry.get_node("tenant_get_context")
        assert node is not None
        assert isinstance(node, ToolNode)
        
        # Get non-existent node
        node = registry.get_node("non_existent")
        assert node is None


class TestConversationRouter(TestCase):
    """Test ConversationRouter functionality."""
    
    def test_intent_routing_high_confidence(self):
        """Test intent routing with high confidence."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            intent="sales_discovery",
            intent_confidence=0.8
        )
        
        decision = router.route_to_journey(state)
        
        assert decision.journey == "sales"
        assert decision.confidence == 0.8
        assert "confidence" in decision.reason.lower()
    
    def test_intent_routing_medium_confidence(self):
        """Test intent routing with medium confidence."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            intent="sales_discovery",
            intent_confidence=0.6
        )
        
        decision = router.route_to_journey(state)
        
        assert decision.journey == "unknown"
        assert decision.should_clarify == True
        assert "confidence" in decision.reason.lower()
    
    def test_intent_routing_low_confidence(self):
        """Test intent routing with low confidence."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            intent="unknown",
            intent_confidence=0.3
        )
        
        decision = router.route_to_journey(state)
        
        assert decision.journey == "unknown"
        assert "confidence" in decision.reason.lower()
    
    def test_governance_routing_business(self):
        """Test governance routing for business conversation."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            governor_classification="business",
            governor_confidence=0.9
        )
        
        decision = router.route_after_governance(state)
        
        assert decision.journey == "business"
        assert "Business conversation" in decision.reason
    
    def test_governance_routing_casual(self):
        """Test governance routing for casual conversation."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            governor_classification="casual",
            governor_confidence=0.8,
            max_chattiness_level=2,
            casual_turns=0
        )
        
        decision = router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "Casual conversation" in decision.reason
    
    def test_governance_routing_spam(self):
        """Test governance routing for spam conversation."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            governor_classification="spam",
            governor_confidence=0.9,
            spam_turns=2
        )
        
        decision = router.route_after_governance(state)
        
        assert decision.journey == "governance"
        assert "spam" in decision.reason.lower()


class TestLangGraphOrchestrator(TestCase):
    """Test LangGraphOrchestrator functionality."""
    
    def test_orchestrator_initialization(self):
        """Test LangGraphOrchestrator initializes properly."""
        orchestrator = LangGraphOrchestrator()
        
        # Should have compiled graph
        assert orchestrator._graph is not None
        
        # Should have node registry
        assert orchestrator.node_registry is not None
        
        # Should have router
        assert orchestrator.router is not None
    
    @pytest.mark.asyncio
    async def test_message_processing_basic(self):
        """Test basic message processing through orchestrator."""
        orchestrator = LangGraphOrchestrator()
        
        # Process a simple message
        final_state = await orchestrator.process_message(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            message="Hello, I want to buy something",
            phone_e164="+254700000000"
        )
        
        # Should have processed the message
        assert final_state.tenant_id == "test-tenant"
        assert final_state.conversation_id == "test-conv"
        assert final_state.turn_count == 1
        assert final_state.response_text is not None
        
        # Should have some classification (even if placeholder)
        assert final_state.intent in [
            "sales_discovery", "product_question", "support_question", "order_status",
            "discounts_offers", "preferences_consent", "payment_help",
            "human_request", "spam_casual", "unknown"
        ]
    
    @pytest.mark.asyncio
    async def test_message_processing_error_handling(self):
        """Test error handling in message processing."""
        orchestrator = LangGraphOrchestrator()
        
        # Test with invalid data (should handle gracefully)
        final_state = await orchestrator.process_message(
            tenant_id="",  # Invalid tenant_id
            conversation_id="test-conv",
            message="Test message"
        )
        
        # Should have escalation set for the error
        assert final_state.escalation_required is True
        assert "error" in final_state.escalation_reason.lower()


class TestRouteDecision(TestCase):
    """Test RouteDecision functionality."""
    
    def test_route_decision_creation(self):
        """Test RouteDecision creation."""
        decision = RouteDecision(
            target_node="test_node",
            reason="Test routing",
            confidence=0.8,
            metadata={"key": "value"}
        )
        
        assert decision.target_node == "test_node"
        assert decision.reason == "Test routing"
        assert decision.confidence == 0.8
        assert decision.metadata["key"] == "value"
    
    def test_route_decision_default_metadata(self):
        """Test RouteDecision with default metadata."""
        decision = RouteDecision(
            target_node="test_node",
            reason="Test routing"
        )
        
        assert decision.metadata == {}
        assert decision.confidence == 1.0