"""
Tests for LangGraph orchestration infrastructure.

Tests the core LangGraph orchestration system including:
- Message processing through the graph
- Intent classification nodes
- Language policy nodes
- Conversation governance nodes
- Journey routing
"""
import pytest
from unittest.mock import AsyncMock, patch
from dataclasses import asdict

from apps.bot.langgraph.orchestrator import LangGraphOrchestrator, process_conversation_message
from apps.bot.conversation_state import ConversationState, ConversationStateManager
from apps.bot.langgraph.llm_nodes import IntentClassificationNode, LanguagePolicyNode, ConversationGovernorNode


@pytest.mark.asyncio
class TestLangGraphOrchestration:
    """Test LangGraph orchestration infrastructure."""
    
    async def test_orchestrator_initialization(self):
        """Test that orchestrator initializes properly."""
        orchestrator = LangGraphOrchestrator()
        
        # Check that graph is compiled
        assert orchestrator._graph is not None
        
        # Check that node registry is initialized
        assert orchestrator.node_registry is not None
        
        # Check that router is initialized
        assert orchestrator.router is not None
    
    @patch('apps.bot.services.llm.base.LLMProvider.generate')
    @patch('apps.bot.services.llm_router.LLMRouter._check_budget')
    @patch('apps.bot.services.llm_router.LLMRouter._get_provider')
    @patch('apps.tenants.models.Tenant.objects.aget')
    async def test_intent_classification_node(self, mock_tenant_get, mock_get_provider, mock_check_budget, mock_generate):
        """Test intent classification node execution."""
        # Mock dependencies
        from apps.bot.services.llm.base import LLMResponse
        from decimal import Decimal
        from apps.tenants.models import Tenant
        
        # Mock tenant - return actual tenant instance
        mock_tenant = Tenant(id="test-tenant")
        mock_tenant_get.return_value = mock_tenant
        
        # Mock budget check
        mock_check_budget.return_value = True
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_get_provider.return_value = mock_provider
        
        # Mock LLM response
        mock_llm_response = LLMResponse(
            content='{"intent": "sales_discovery", "confidence": 0.8, "notes": "User asking about products", "suggested_journey": "sales"}',
            model="test-model",
            provider="test-provider",
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
            estimated_cost=Decimal("0.001"),
            finish_reason="stop",
            metadata={}
        )
        mock_generate.return_value = mock_llm_response
        
        # Create test state
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "What products do you have?"
        
        # Execute intent classification
        node = IntentClassificationNode()
        result_state = await node.execute(state)
        
        # Verify results
        assert result_state.intent == "sales_discovery"
        assert result_state.intent_confidence == 0.8
        assert result_state.journey == "sales"
        
        # Verify LLM was called
        mock_generate.assert_called_once()
    
    async def test_language_policy_node(self):
        """Test language policy node heuristic detection and threshold logic."""
        import uuid
        
        # Test heuristic detection directly
        node = LanguagePolicyNode()
        
        # Test explicit language requests
        assert node._detect_language_heuristic("Speak Swahili please") == "sw"
        assert node._detect_language_heuristic("In English please") == "en"
        assert node._detect_language_heuristic("Niaje msee, uko poa?") == "mixed"
        assert node._detect_language_heuristic("Habari, nina hitaji msaada") == "mixed"
        
        # Test threshold logic directly
        tenant_id = str(uuid.uuid4())
        state = ConversationStateManager.create_initial_state(
            tenant_id=tenant_id,
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Test high confidence, allowed language -> switch
        mock_result = {"response_language": "sw", "confidence": 0.8, "should_ask_language_question": False}
        state.allowed_languages = ["en", "sw"]
        state.default_language = "en"
        updated_state = node._update_state_from_llm_result(state, mock_result)
        assert updated_state.response_language == "sw"
        
        # Test low confidence -> use default
        mock_result = {"response_language": "sw", "confidence": 0.6, "should_ask_language_question": False}
        updated_state = node._update_state_from_llm_result(state, mock_result)
        assert updated_state.response_language == "en"  # Should use default
        
        # Test customer preference override
        state.customer_language_pref = "sw"
        state.allowed_languages = ["en", "sw", "sheng"]
        mock_result = {"response_language": "en", "confidence": 0.8, "should_ask_language_question": False}
        updated_state = node._update_state_from_llm_result(state, mock_result)
        assert updated_state.response_language == "sw"  # Customer preference should override
    
    async def test_conversation_governor_node(self):
        """Test conversation governor node execution with heuristic classification."""
        # Create test state
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "I need help with my order"
        
        # Execute conversation governance (will use heuristic classification)
        node = ConversationGovernorNode()
        result_state = await node.execute(state)
        
        # Verify results - should classify as business using heuristics
        assert result_state.governor_classification == "business"
        assert result_state.governor_confidence > 0.0
    
    async def test_conversation_governor_heuristic_classification(self):
        """Test conversation governor heuristic classification logic."""
        node = ConversationGovernorNode()
        
        # Test business classification
        business_messages = [
            "I need help with my order",
            "What products do you have?",
            "How much does this cost?",
            "I want to buy something",
            "Payment failed",
            "Track my delivery"
        ]
        
        for message in business_messages:
            state = ConversationStateManager.create_initial_state(
                tenant_id="test-tenant",
                conversation_id="test-conv", 
                request_id="test-req"
            )
            classification = node._classify_governance_heuristic(message, state)
            assert classification == "business", f"Message '{message}' should be classified as business"
        
        # Test casual classification
        casual_messages = [
            "Hello",
            "Hi there",
            "How are you?",
            "Good morning",
            "Thanks"
        ]
        
        for message in casual_messages:
            state = ConversationStateManager.create_initial_state(
                tenant_id="test-tenant",
                conversation_id="test-conv",
                request_id="test-req"
            )
            classification = node._classify_governance_heuristic(message, state)
            assert classification == "casual", f"Message '{message}' should be classified as casual"
        
        # Test spam classification
        spam_messages = [
            "test",
            "123",
            "asdf",
            "a",
            "!!!"
        ]
        
        for message in spam_messages:
            state = ConversationStateManager.create_initial_state(
                tenant_id="test-tenant",
                conversation_id="test-conv",
                request_id="test-req"
            )
            classification = node._classify_governance_heuristic(message, state)
            assert classification == "spam", f"Message '{message}' should be classified as spam"
        
        # Test abuse classification
        abuse_messages = [
            "fuck you",
            "you're stupid",
            "damn this"
        ]
        
        for message in abuse_messages:
            state = ConversationStateManager.create_initial_state(
                tenant_id="test-tenant",
                conversation_id="test-conv",
                request_id="test-req"
            )
            classification = node._classify_governance_heuristic(message, state)
            assert classification == "abuse", f"Message '{message}' should be classified as abuse"
    
    async def test_conversation_governor_chattiness_levels(self):
        """Test conversation governor chattiness level enforcement."""
        node = ConversationGovernorNode()
        
        # Test Level 0 (strictly business)
        assert node._get_max_casual_turns(0) == 0
        
        # Test Level 1 (1 short greeting)
        assert node._get_max_casual_turns(1) == 1
        
        # Test Level 2 (max 2 casual turns - DEFAULT)
        assert node._get_max_casual_turns(2) == 2
        
        # Test Level 3 (max 4 casual turns)
        assert node._get_max_casual_turns(3) == 4
        
        # Test default fallback
        assert node._get_max_casual_turns(99) == 2
    
    async def test_conversation_governor_routing_logic(self):
        """Test conversation governor EXACT routing logic."""
        node = ConversationGovernorNode()
        
        # Test business routing
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        action = node._get_recommended_action("business", state)
        assert action == "proceed"
        
        # Test casual routing within limits
        state.casual_turns = 1
        state.max_chattiness_level = 2  # Allows 2 casual turns
        action = node._get_recommended_action("casual", state)
        assert action == "proceed"  # Still within limit
        
        # Test casual routing exceeding limits
        state.casual_turns = 3  # Exceeds limit of 2
        action = node._get_recommended_action("casual", state)
        assert action == "redirect"
        
        # Test spam routing - first turn
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.spam_turns = 1
        action = node._get_recommended_action("spam", state)
        assert action == "limit"
        
        # Test spam routing - second turn (should disengage)
        state.spam_turns = 2
        action = node._get_recommended_action("spam", state)
        assert action == "stop"
        
        # Test abuse routing
        action = node._get_recommended_action("abuse", state)
        assert action == "stop"
    
    @patch('apps.bot.services.llm.base.LLMProvider.generate')
    @patch('apps.bot.services.llm_router.LLMRouter._check_budget')
    @patch('apps.bot.services.llm_router.LLMRouter._get_provider')
    @patch('apps.tenants.models.Tenant.objects.aget')
    async def test_casual_conversation_governance(self, mock_tenant_get, mock_get_provider, mock_check_budget, mock_generate):
        """Test governance handling of casual conversation."""
        # Mock dependencies
        from apps.bot.services.llm.base import LLMResponse
        from decimal import Decimal
        from apps.tenants.models import Tenant
        
        # Mock tenant - return actual tenant instance
        mock_tenant = Tenant(id="test-tenant")
        mock_tenant_get.return_value = mock_tenant
        
        # Mock budget check
        mock_check_budget.return_value = True
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_get_provider.return_value = mock_provider
        
        # Mock LLM response for casual classification
        mock_llm_response = LLMResponse(
            content='{"classification": "casual", "confidence": 0.8, "recommended_action": "redirect"}',
            model="test-model",
            provider="test-provider",
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
            estimated_cost=Decimal("0.001"),
            finish_reason="stop",
            metadata={}
        )
        mock_generate.return_value = mock_llm_response
        
        # Create test state with some casual turns
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "How's your day going?"
        state.casual_turns = 1
        state.max_chattiness_level = 2  # Allow 2 casual turns
        
        # Execute conversation governance
        node = ConversationGovernorNode()
        result_state = await node.execute(state)
        
        # Verify casual classification
        assert result_state.governor_classification == "casual"
        assert result_state.governor_confidence == 0.8
        # Should increment casual turns
        assert result_state.casual_turns == 2
    
    @patch('apps.bot.services.llm.base.LLMProvider.generate')
    @patch('apps.bot.services.llm_router.LLMRouter._check_budget')
    @patch('apps.bot.services.llm_router.LLMRouter._get_provider')
    @patch('apps.tenants.models.Tenant.objects.aget')
    async def test_spam_conversation_governance(self, mock_tenant_get, mock_get_provider, mock_check_budget, mock_generate):
        """Test governance handling of spam conversation."""
        # Mock dependencies
        from apps.bot.services.llm.base import LLMResponse
        from decimal import Decimal
        from apps.tenants.models import Tenant
        
        # Mock tenant - return actual tenant instance
        mock_tenant = Tenant(id="test-tenant")
        mock_tenant_get.return_value = mock_tenant
        
        # Mock budget check
        mock_check_budget.return_value = True
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_get_provider.return_value = mock_provider
        
        # Mock LLM response for spam classification
        mock_llm_response = LLMResponse(
            content='{"classification": "spam", "confidence": 0.9, "recommended_action": "limit"}',
            model="test-model",
            provider="test-provider",
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
            estimated_cost=Decimal("0.001"),
            finish_reason="stop",
            metadata={}
        )
        mock_generate.return_value = mock_llm_response
        
        # Create test state with spam turns
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "asdfasdf random text"
        state.spam_turns = 1
        
        # Execute conversation governance
        node = ConversationGovernorNode()
        result_state = await node.execute(state)
        
        # Verify spam classification
        assert result_state.governor_classification == "spam"
        assert result_state.governor_confidence == 0.9
        # Should increment spam turns
        assert result_state.spam_turns == 2
    
    @patch('apps.bot.langgraph.orchestrator.LangGraphOrchestrator.process_message')
    async def test_process_conversation_message(self, mock_process):
        """Test the main conversation message processing function."""
        # Mock the orchestrator process_message method
        expected_state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        expected_state.response_text = "Test response"
        mock_process.return_value = expected_state
        
        # Call the main processing function
        result = await process_conversation_message(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            message_text="Hello"
        )
        
        # Verify result
        assert result.response_text == "Test response"
        mock_process.assert_called_once()
    
    def test_conversation_state_validation(self):
        """Test conversation state validation."""
        # Test valid state
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.validate()  # Should not raise
        
        # Test invalid intent
        state.intent = "invalid_intent"
        with pytest.raises(ValueError, match="Invalid intent"):
            state.validate()
        
        # Test invalid confidence
        state.intent = "sales_discovery"
        state.intent_confidence = 1.5  # Invalid confidence > 1.0
        with pytest.raises(ValueError, match="intent_confidence must be between"):
            state.validate()
    
    def test_conversation_state_serialization(self):
        """Test conversation state serialization/deserialization."""
        # Create test state
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.intent = "sales_discovery"
        state.intent_confidence = 0.8
        state.response_text = "Test response"
        
        # Serialize to dict
        state_dict = state.to_dict()
        assert state_dict["tenant_id"] == "test-tenant"
        assert state_dict["intent"] == "sales_discovery"
        assert state_dict["intent_confidence"] == 0.8
        
        # Deserialize from dict
        restored_state = ConversationState.from_dict(state_dict)
        assert restored_state.tenant_id == "test-tenant"
        assert restored_state.intent == "sales_discovery"
        assert restored_state.intent_confidence == 0.8
        
        # Test JSON serialization
        json_str = state.to_json()
        restored_from_json = ConversationState.from_json(json_str)
        assert restored_from_json.tenant_id == "test-tenant"
        assert restored_from_json.intent == "sales_discovery"


@pytest.mark.asyncio
class TestLangGraphRouting:
    """Test LangGraph routing logic."""
    
    def test_intent_to_journey_mapping(self):
        """Test intent to journey mapping."""
        from apps.bot.langgraph.routing import ConversationRouter
        
        router = ConversationRouter()
        
        # Test sales intents
        assert router._intent_to_journey("sales_discovery") == "sales"
        assert router._intent_to_journey("product_question") == "sales"
        
        # Test support intents
        assert router._intent_to_journey("support_question") == "support"
        assert router._intent_to_journey("payment_help") == "support"
        
        # Test other intents
        assert router._intent_to_journey("order_status") == "orders"
        assert router._intent_to_journey("discounts_offers") == "offers"
        assert router._intent_to_journey("preferences_consent") == "prefs"
        assert router._intent_to_journey("human_request") == "governance"
        assert router._intent_to_journey("unknown") == "unknown"
    
    def test_chattiness_level_limits(self):
        """Test chattiness level to casual turn limits mapping."""
        from apps.bot.langgraph.routing import ConversationRouter
        
        router = ConversationRouter()
        
        # Test chattiness levels
        assert router._get_max_casual_turns(0) == 0  # Strictly business
        assert router._get_max_casual_turns(1) == 1  # Minimal friendliness
        assert router._get_max_casual_turns(2) == 2  # Default friendly
        assert router._get_max_casual_turns(3) == 4  # More friendly
        
        # Test default fallback
        assert router._get_max_casual_turns(99) == 2  # Unknown level defaults to 2
    
    def test_route_after_governance_business(self):
        """Test routing after business governance classification."""
        from apps.bot.langgraph.routing import ConversationRouter
        
        router = ConversationRouter()
        
        # Create test state with business classification
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.governor_classification = "business"
        state.governor_confidence = 0.9
        
        # Route after governance
        decision = router.route_after_governance(state)
        
        # Should proceed to journey routing (indicated by "unknown" journey)
        assert decision.journey == "unknown"
        assert "proceed to journey routing" in decision.reason
    
    def test_route_after_governance_casual_within_limits(self):
        """Test routing after casual governance classification within limits."""
        from apps.bot.langgraph.routing import ConversationRouter
        
        router = ConversationRouter()
        
        # Create test state with casual classification within limits
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.governor_classification = "casual"
        state.governor_confidence = 0.8
        state.casual_turns = 1
        state.max_chattiness_level = 2  # Allows 2 casual turns
        
        # Route after governance
        decision = router.route_after_governance(state)
        
        # Should allow casual conversation
        assert decision.journey == "governance"
        assert "within limits" in decision.reason
        assert decision.metadata.get("casual_response") is True
    
    def test_route_after_governance_casual_exceeded_limits(self):
        """Test routing after casual governance classification exceeding limits."""
        from apps.bot.langgraph.routing import ConversationRouter
        
        router = ConversationRouter()
        
        # Create test state with casual classification exceeding limits
        state = ConversationStateManager.create_initial_state(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.governor_classification = "casual"
        state.governor_confidence = 0.8
        state.casual_turns = 2
        state.max_chattiness_level = 2  # Allows 2 casual turns, but we're at the limit
        
        # Route after governance
        decision = router.route_after_governance(state)
        
        # Should redirect to business
        assert decision.journey == "governance"
        assert "Exceeded casual turn limit" in decision.reason