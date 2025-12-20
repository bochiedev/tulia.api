"""
Tests for LangGraph orchestrator infrastructure.

Tests the core LangGraph setup, node registration, and basic orchestration
functionality for the Tulia AI V2 system.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.langgraph.orchestrator import LangGraphOrchestrator, get_orchestrator, process_conversation_message
from apps.bot.langgraph.nodes import NodeRegistry, get_node_registry, register_default_nodes
from apps.bot.langgraph.routing import ConversationRouter, RouteDecision


class TestConversationStateIntegration:
    """Test ConversationState integration with LangGraph."""
    
    def test_conversation_state_creation(self):
        """Test creating ConversationState for LangGraph processing."""
        state = ConversationStateManager.create_initial_state(
            tenant_id="test_tenant",
            conversation_id="test_conv_123",
            request_id="req_456"
        )
        
        assert state.tenant_id == "test_tenant"
        assert state.conversation_id == "test_conv_123"
        assert state.request_id == "req_456"
        assert state.intent == "unknown"
        assert state.journey == "unknown"
        assert state.turn_count == 0
    
    def test_conversation_state_serialization(self):
        """Test ConversationState serialization for LangGraph."""
        state = ConversationStateManager.create_initial_state(
            tenant_id="test_tenant",
            conversation_id="test_conv_123",
            request_id="req_456"
        )
        
        # Test to_dict conversion
        state_dict = state.to_dict()
        assert isinstance(state_dict, dict)
        assert state_dict["tenant_id"] == "test_tenant"
        assert state_dict["conversation_id"] == "test_conv_123"
        
        # Test from_dict conversion
        restored_state = ConversationState.from_dict(state_dict)
        assert restored_state.tenant_id == state.tenant_id
        assert restored_state.conversation_id == state.conversation_id
        assert restored_state.request_id == state.request_id
    
    def test_conversation_state_validation(self):
        """Test ConversationState validation."""
        state = ConversationStateManager.create_initial_state(
            tenant_id="test_tenant",
            conversation_id="test_conv_123",
            request_id="req_456"
        )
        
        # Valid state should pass validation
        state.validate()
        
        # Invalid intent should fail validation
        state.intent = "invalid_intent"
        with pytest.raises(ValueError, match="Invalid intent"):
            state.validate()


class TestNodeRegistry:
    """Test node registration system."""
    
    def test_node_registry_creation(self):
        """Test creating and using node registry."""
        registry = NodeRegistry()
        # Registry starts with default nodes pre-registered
        assert len(registry.list_nodes()) > 0
        
        # Should have core default nodes
        nodes = registry.list_nodes()
        assert "tenant_get_context" in nodes
        assert "customer_get_or_create" in nodes
        assert "intent_classify" in nodes
    
    def test_global_node_registry(self):
        """Test global node registry access."""
        registry1 = get_node_registry()
        registry2 = get_node_registry()
        assert registry1 is registry2  # Should be singleton
    
    def test_default_nodes_registration(self):
        """Test registering default nodes."""
        registry = NodeRegistry()
        
        # Register default nodes using the correct method signature
        from apps.bot.langgraph.nodes import (
            IntentClassifyNode, LanguagePolicyNode, GovernorNode,
            TenantContextNode, CustomerResolverNode
        )
        
        registry.register_node("intent_classify_test", IntentClassifyNode())
        registry.register_node("language_policy_test", LanguagePolicyNode())
        registry.register_node("governor_spam_casual_test", GovernorNode())
        registry.register_node("tenant_context_test", TenantContextNode())
        registry.register_node("customer_resolver_test", CustomerResolverNode())
        
        nodes = registry.list_nodes()
        assert "intent_classify_test" in nodes
        assert "language_policy_test" in nodes
        assert "governor_spam_casual_test" in nodes
        assert "tenant_context_test" in nodes
        assert "customer_resolver_test" in nodes


class TestConversationRouter:
    """Test conversation routing logic."""
    
    def test_router_creation(self):
        """Test creating conversation router."""
        router = ConversationRouter()
        assert router.INTENT_HIGH_CONFIDENCE == 0.70
        assert router.INTENT_MEDIUM_CONFIDENCE == 0.50
    
    def test_high_confidence_routing(self):
        """Test routing with high confidence intent."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test_tenant",
            conversation_id="test_conv",
            request_id="test_req",
            intent="sales_discovery",
            intent_confidence=0.85,
            governor_classification="business",
            governor_confidence=0.90
        )
        
        decision = router.route_conversation(state)
        assert decision.journey == "sales"
        assert decision.confidence == 0.85
        assert not decision.should_clarify
    
    def test_medium_confidence_routing(self):
        """Test routing with medium confidence intent."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test_tenant",
            conversation_id="test_conv",
            request_id="test_req",
            intent="product_question",
            intent_confidence=0.60,
            governor_classification="business",
            governor_confidence=0.90
        )
        
        decision = router.route_conversation(state)
        assert decision.journey == "unknown"
        assert decision.should_clarify
    
    def test_low_confidence_routing(self):
        """Test routing with low confidence intent."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test_tenant",
            conversation_id="test_conv",
            request_id="test_req",
            intent="unknown",
            intent_confidence=0.30,
            governor_classification="business",
            governor_confidence=0.90
        )
        
        decision = router.route_conversation(state)
        assert decision.journey == "unknown"
        assert not decision.should_clarify
    
    def test_governor_override_casual(self):
        """Test governor override for casual conversation."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test_tenant",
            conversation_id="test_conv",
            request_id="test_req",
            intent="sales_discovery",
            intent_confidence=0.85,
            governor_classification="casual",
            governor_confidence=0.90,
            casual_turns=3,  # Exceeds default limit of 2
            max_chattiness_level=2
        )
        
        decision = router.route_conversation(state)
        assert decision.journey == "governance"
        assert "casual turn limit" in decision.reason
    
    def test_governor_override_spam(self):
        """Test governor override for spam conversation."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test_tenant",
            conversation_id="test_conv",
            request_id="test_req",
            intent="sales_discovery",
            intent_confidence=0.85,
            governor_classification="spam",
            governor_confidence=0.90,
            spam_turns=3  # Exceeds limit of 2
        )
        
        decision = router.route_conversation(state)
        assert decision.journey == "spam_disengage"
        assert "spam turn limit" in decision.reason
    
    def test_governor_override_abuse(self):
        """Test governor override for abuse."""
        router = ConversationRouter()
        
        state = ConversationState(
            tenant_id="test_tenant",
            conversation_id="test_conv",
            request_id="test_req",
            intent="sales_discovery",
            intent_confidence=0.85,
            governor_classification="abuse",
            governor_confidence=0.90
        )
        
        decision = router.route_conversation(state)
        assert decision.journey == "abuse_stop"
        assert "abuse" in decision.reason.lower()


class TestLangGraphOrchestrator:
    """Test LangGraph orchestrator functionality."""
    
    def test_orchestrator_creation(self):
        """Test creating LangGraph orchestrator."""
        orchestrator = LangGraphOrchestrator()
        assert orchestrator is not None
        assert orchestrator._graph is not None
    
    def test_global_orchestrator(self):
        """Test global orchestrator access."""
        orchestrator1 = get_orchestrator()
        orchestrator2 = get_orchestrator()
        assert orchestrator1 is orchestrator2  # Should be singleton
    
    @pytest.mark.asyncio
    async def test_process_message_basic(self):
        """Test basic message processing through orchestrator."""
        # Create a simple test case
        result_state = await process_conversation_message(
            tenant_id="test_tenant",
            conversation_id="test_conv_123",
            request_id="req_456",
            message_text="Hello, I need help with shopping"
        )
        
        # Verify basic state structure
        assert result_state.tenant_id == "test_tenant"
        assert result_state.conversation_id == "test_conv_123"
        assert result_state.request_id == "req_456"
        assert result_state.turn_count == 1  # Should increment turn
        assert result_state.incoming_message == "Hello, I need help with shopping"
        
        # Should have some response (even if placeholder)
        assert result_state.response_text is not None
    
    @pytest.mark.asyncio
    async def test_process_message_with_existing_state(self):
        """Test processing message with existing conversation state."""
        # Create initial state
        existing_state = ConversationStateManager.create_initial_state(
            tenant_id="test_tenant",
            conversation_id="test_conv_123",
            request_id="initial_req"
        )
        existing_state.turn_count = 5
        existing_state.casual_turns = 1
        
        # Process new message
        result_state = await process_conversation_message(
            tenant_id="test_tenant",
            conversation_id="test_conv_123",
            request_id="new_req_456",
            message_text="What products do you have?",
            existing_state=existing_state
        )
        
        # Verify state continuity
        assert result_state.tenant_id == "test_tenant"
        assert result_state.conversation_id == "test_conv_123"
        assert result_state.request_id == "new_req_456"  # Should update request ID
        assert result_state.turn_count == 6  # Should increment from existing
        assert result_state.casual_turns == 1  # Should preserve existing casual turns
    
    def test_route_to_journey_method(self):
        """Test journey routing method."""
        orchestrator = LangGraphOrchestrator()
        
        state_dict = {
            "tenant_id": "test_tenant",
            "conversation_id": "test_conv",
            "request_id": "test_req",
            "intent": "sales_discovery",
            "intent_confidence": 0.85,
            "governor_classification": "business",
            "governor_confidence": 0.90
        }
        
        journey = orchestrator._route_to_journey(state_dict)
        assert journey == "sales"


class TestIntegrationBasic:
    """Basic integration tests for LangGraph infrastructure."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_message_flow(self):
        """Test complete message flow through LangGraph system."""
        # This tests the basic infrastructure without requiring
        # full LLM implementations or tool integrations
        
        result_state = await process_conversation_message(
            tenant_id="integration_test_tenant",
            conversation_id="integration_test_conv",
            request_id="integration_test_req",
            message_text="I want to buy something",
            phone_e164="+254700000000"
        )
        
        # Verify the message was processed through the system
        assert result_state is not None
        assert result_state.tenant_id == "integration_test_tenant"
        assert result_state.conversation_id == "integration_test_conv"
        assert result_state.request_id == "integration_test_req"
        assert result_state.phone_e164 == "+254700000000"
        
        # Should have processed through classification (even with placeholders)
        assert result_state.intent in [
            "sales_discovery", "product_question", "support_question", "order_status",
            "discounts_offers", "preferences_consent", "payment_help",
            "human_request", "spam_casual", "unknown"
        ]
        
        assert result_state.journey in [
            "sales", "support", "orders", "offers", "prefs", "governance", "unknown"
        ]
        
        # Should have some response
        assert result_state.response_text is not None
        assert len(result_state.response_text) > 0
    
    def test_conversation_state_schema_compatibility(self):
        """Test that ConversationState works with LangGraph state schema."""
        # Create state
        state = ConversationStateManager.create_initial_state(
            tenant_id="schema_test_tenant",
            conversation_id="schema_test_conv",
            request_id="schema_test_req"
        )
        
        # Convert to dict (LangGraph format)
        state_dict = state.to_dict()
        
        # Verify all required fields are present
        required_fields = [
            "tenant_id", "conversation_id", "request_id",
            "intent", "journey", "response_language", "governor_classification"
        ]
        
        for field in required_fields:
            assert field in state_dict, f"Required field {field} missing from state dict"
        
        # Convert back to ConversationState
        restored_state = ConversationState.from_dict(state_dict)
        restored_state.validate()
        
        # Should be equivalent
        assert restored_state.tenant_id == state.tenant_id
        assert restored_state.conversation_id == state.conversation_id
        assert restored_state.request_id == state.request_id