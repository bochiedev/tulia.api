"""
Tests for offers journey implementation.

This module tests the complete offers and coupons journey workflow including:
- OffersAnswerNode functionality
- offers_journey_entry workflow
- Integration with offers_get_applicable and order_apply_coupon tools
- Error handling and fallback scenarios
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.offers_journey import (
    OffersAnswerNode,
    offers_journey_entry,
    _step_get_applicable_offers,
    _step_offers_answer,
    _step_apply_coupon,
    _extract_coupon_code
)
from apps.bot.tools.base import ToolResponse


class TestOffersAnswerNode:
    """Test the OffersAnswerNode LLM node."""
    
    def test_node_creation(self):
        """Test that OffersAnswerNode can be created successfully."""
        node = OffersAnswerNode()
        assert node.name == "offers_answer"
        assert node.system_prompt is not None
        assert "STRICT GROUNDING RULES" in node.system_prompt
        assert "MUST NOT invent" in node.system_prompt
    
    def test_prepare_llm_input_with_offers(self):
        """Test LLM input preparation with available offers."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            customer_id="test-customer",
            incoming_message="Do you have any discounts?",
            order_id="test-order"
        )
        
        # Add offers to state
        state.available_offers = [
            {
                "id": "offer1",
                "name": "New Customer Discount",
                "discount_percent": 10,
                "code": "NEWCUST10"
            },
            {
                "id": "offer2", 
                "name": "Free Shipping",
                "discount_amount": 200,
                "code": "FREESHIP"
            }
        ]
        
        state.order_totals = {"total": 5000}
        
        input_text = node._prepare_llm_input(state)
        
        assert "Do you have any discounts?" in input_text
        assert "test-customer" in input_text
        assert "test-order" in input_text
        assert "KES 5000" in input_text
        assert "AVAILABLE OFFERS:" in input_text
        assert "New Customer Discount" in input_text
        assert "Free Shipping" in input_text
    
    def test_prepare_llm_input_no_offers(self):
        """Test LLM input preparation with no available offers."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="Any deals available?"
        )
        
        input_text = node._prepare_llm_input(state)
        
        assert "Any deals available?" in input_text
        assert "AVAILABLE OFFERS: No applicable offers found" in input_text
    
    def test_analyze_coupon_need_positive(self):
        """Test coupon need analysis when application is needed."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="Yes, apply the discount"
        )
        
        # Test with answer indicating application
        answer_text = "Great! I'll apply this 10% discount to your order."
        needs_coupon = node._analyze_coupon_need(answer_text, state)
        assert needs_coupon is True
        
        # Test with user message indicating application
        state.incoming_message = "use the first offer"
        answer_text = "Here are your available offers..."
        needs_coupon = node._analyze_coupon_need(answer_text, state)
        assert needs_coupon is True
    
    def test_analyze_coupon_need_negative(self):
        """Test coupon need analysis when no application is needed."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="What offers do you have?"
        )
        
        answer_text = "Here are the available offers for your order."
        needs_coupon = node._analyze_coupon_need(answer_text, state)
        assert needs_coupon is False
    
    def test_generate_fallback_answer_single_offer(self):
        """Test fallback answer generation with single offer."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        state.available_offers = [
            {
                "name": "Student Discount",
                "discount_percent": 15
            }
        ]
        
        result = node._generate_fallback_answer(state)
        
        assert "Student Discount" in result["answer"]
        assert "15%" in result["answer"]
        assert result["needs_coupon_application"] is True
    
    def test_generate_fallback_answer_multiple_offers(self):
        """Test fallback answer generation with multiple offers."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        state.available_offers = [
            {"name": "Bulk Discount", "discount_percent": 20},
            {"name": "Loyalty Reward", "discount_amount": 500},
            {"name": "Flash Sale", "discount_percent": 10}
        ]
        
        result = node._generate_fallback_answer(state)
        
        assert "3 available offers" in result["answer"]
        assert "Bulk Discount" in result["answer"]
        assert "Loyalty Reward" in result["answer"]
        assert "Flash Sale" in result["answer"]
        assert result["needs_coupon_application"] is False
    
    def test_generate_fallback_answer_no_offers(self):
        """Test fallback answer generation with no offers."""
        node = OffersAnswerNode()
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        result = node._generate_fallback_answer(state)
        
        assert "don't see any applicable offers" in result["answer"]
        assert "coupon code" in result["answer"]
        assert result["needs_coupon_application"] is False


class TestOffersJourneyWorkflow:
    """Test the complete offers journey workflow."""
    
    @pytest.mark.asyncio
    async def test_offers_journey_entry_success(self):
        """Test successful offers journey execution."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            customer_id="test-customer",
            order_id="test-order",
            incoming_message="Do you have any discounts?"
        )
        
        # Mock the step functions
        with patch('apps.bot.langgraph.offers_journey._step_get_applicable_offers') as mock_get_offers, \
             patch('apps.bot.langgraph.offers_journey._step_offers_answer') as mock_offers_answer, \
             patch('apps.bot.langgraph.offers_journey._step_apply_coupon') as mock_apply_coupon:
            
            # Setup mocks
            mock_get_offers.return_value = state
            
            state.response_text = "Here are your available offers..."
            state.needs_coupon_application = False
            mock_offers_answer.return_value = state
            
            # Execute journey
            result_state = await offers_journey_entry(state)
            
            # Verify calls
            mock_get_offers.assert_called_once_with(state)
            mock_offers_answer.assert_called_once_with(state)
            mock_apply_coupon.assert_not_called()  # Not needed
            
            # Verify result
            assert result_state.journey == "offers"
    
    @pytest.mark.asyncio
    async def test_offers_journey_with_coupon_application(self):
        """Test offers journey with coupon application."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            customer_id="test-customer",
            order_id="test-order",
            incoming_message="Apply the first discount"
        )
        
        with patch('apps.bot.langgraph.offers_journey._step_get_applicable_offers') as mock_get_offers, \
             patch('apps.bot.langgraph.offers_journey._step_offers_answer') as mock_offers_answer, \
             patch('apps.bot.langgraph.offers_journey._step_apply_coupon') as mock_apply_coupon:
            
            # Setup mocks
            mock_get_offers.return_value = state
            
            state.response_text = "I'll apply the discount for you."
            state.needs_coupon_application = True
            mock_offers_answer.return_value = state
            mock_apply_coupon.return_value = state
            
            # Execute journey
            result_state = await offers_journey_entry(state)
            
            # Verify coupon application was called
            mock_apply_coupon.assert_called_once_with(state)
            assert result_state.journey == "offers"
    
    @pytest.mark.asyncio
    async def test_step_get_applicable_offers_success(self):
        """Test successful offers retrieval."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            customer_id="test-customer",
            order_id="test-order"
        )
        
        # Mock offers tool
        mock_tool = Mock()
        mock_tool.execute.return_value = ToolResponse(
            success=True,
            data={
                "offers": [
                    {"id": "offer1", "name": "Test Offer", "discount_percent": 10}
                ],
                "automatic_discounts": [
                    {"id": "auto1", "name": "Auto Discount", "discount_amount": 100}
                ]
            }
        )
        
        with patch('apps.bot.langgraph.offers_journey.get_tool', return_value=mock_tool):
            result_state = await _step_get_applicable_offers(state)
            
            # Verify tool was called with correct parameters
            mock_tool.execute.assert_called_once_with(
                tenant_id="test-tenant",
                request_id="test-req",
                conversation_id="test-conv",
                customer_id="test-customer",
                order_id="test-order"
            )
            
            # Verify state was updated
            assert len(result_state.available_offers) == 1
            assert result_state.available_offers[0]["name"] == "Test Offer"
            assert len(result_state.automatic_discounts) == 1
    
    @pytest.mark.asyncio
    async def test_step_get_applicable_offers_no_tool(self):
        """Test offers retrieval when tool is not available."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        with patch('apps.bot.langgraph.offers_journey.get_tool', return_value=None):
            result_state = await _step_get_applicable_offers(state)
            
            assert "trouble accessing our offers system" in result_state.response_text
    
    @pytest.mark.asyncio
    async def test_step_offers_answer_success(self):
        """Test successful offers answer generation."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="What discounts are available?"
        )
        
        state.available_offers = [
            {"name": "Test Offer", "discount_percent": 15}
        ]
        
        # Mock the OffersAnswerNode
        with patch('apps.bot.langgraph.offers_journey.OffersAnswerNode') as mock_node_class:
            mock_node = Mock()
            mock_node.execute = AsyncMock(return_value={
                "answer": "You have a 15% Test Offer available!",
                "needs_coupon_application": True
            })
            mock_node_class.return_value = mock_node
            
            result_state = await _step_offers_answer(state)
            
            assert result_state.response_text == "You have a 15% Test Offer available!"
            assert result_state.needs_coupon_application is True
    
    @pytest.mark.asyncio
    async def test_step_apply_coupon_success(self):
        """Test successful coupon application."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            order_id="test-order",
            incoming_message="Apply code SAVE20",
            response_text="I'll apply the discount."
        )
        
        state.available_offers = [
            {"code": "SAVE20", "name": "Save 20%"}
        ]
        
        # Mock coupon tool
        mock_tool = Mock()
        mock_tool.execute.return_value = ToolResponse(
            success=True,
            data={
                "updated_totals": {"total": 4000},
                "discount_applied": 1000
            }
        )
        
        with patch('apps.bot.langgraph.offers_journey.get_tool', return_value=mock_tool):
            result_state = await _step_apply_coupon(state)
            
            # Verify tool was called
            mock_tool.execute.assert_called_once_with(
                tenant_id="test-tenant",
                request_id="test-req",
                conversation_id="test-conv",
                order_id="test-order",
                coupon_code="SAVE20"
            )
            
            # Verify state was updated
            assert result_state.order_totals["total"] == 4000
            assert "saved KES 1000" in result_state.response_text
            assert "KES 4000" in result_state.response_text
    
    @pytest.mark.asyncio
    async def test_step_apply_coupon_no_order(self):
        """Test coupon application without order."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            response_text="Apply discount"
        )
        
        result_state = await _step_apply_coupon(state)
        
        assert "need to create your order first" in result_state.response_text
    
    @pytest.mark.asyncio
    async def test_step_apply_coupon_tool_failure(self):
        """Test coupon application when tool fails."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            order_id="test-order",
            incoming_message="Apply INVALID",
            response_text="Applying discount..."
        )
        
        # Mock failed coupon tool
        mock_tool = Mock()
        mock_tool.execute.return_value = ToolResponse(
            success=False,
            error="Invalid coupon code"
        )
        
        with patch('apps.bot.langgraph.offers_journey.get_tool', return_value=mock_tool):
            result_state = await _step_apply_coupon(state)
            
            assert "Invalid coupon code" in result_state.response_text


class TestCouponCodeExtraction:
    """Test coupon code extraction from user messages."""
    
    def test_extract_coupon_code_with_prefix(self):
        """Test extracting coupon code with 'code' or 'coupon' prefix."""
        assert _extract_coupon_code("Use code SAVE20") == "SAVE20"
        assert _extract_coupon_code("Apply coupon DISCOUNT15") == "DISCOUNT15"
        assert _extract_coupon_code("I have code ABC123") == "ABC123"
    
    def test_extract_coupon_code_standalone(self):
        """Test extracting standalone coupon codes."""
        assert _extract_coupon_code("FREESHIP") == "FREESHIP"
        assert _extract_coupon_code("Apply WELCOME10 please") == "WELCOME10"
        assert _extract_coupon_code("Use STUDENT5") == "STUDENT5"
    
    def test_extract_coupon_code_none(self):
        """Test when no coupon code is found."""
        assert _extract_coupon_code("Do you have any discounts?") is None
        assert _extract_coupon_code("Apply discount") is None
        assert _extract_coupon_code("") is None
        assert _extract_coupon_code("ABC") is None  # Too short
    
    def test_extract_coupon_code_case_insensitive(self):
        """Test case insensitive extraction."""
        assert _extract_coupon_code("use code save20") == "SAVE20"
        assert _extract_coupon_code("apply coupon discount15") == "DISCOUNT15"


@pytest.mark.integration
class TestOffersJourneyIntegration:
    """Integration tests for offers journey with actual tools."""
    
    @pytest.mark.asyncio
    async def test_full_offers_workflow(self):
        """Test complete offers workflow from start to finish."""
        # This would be an integration test with actual tools
        # For now, we'll skip it as it requires full tool setup
        pytest.skip("Integration test requires full tool setup")
    
    @pytest.mark.asyncio
    async def test_offers_journey_in_sales_flow(self):
        """Test offers journey integration with sales journey."""
        # This would test the integration between sales and offers journeys
        pytest.skip("Integration test requires full sales journey setup")