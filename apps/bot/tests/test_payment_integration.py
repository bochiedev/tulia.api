"""
Unit tests for payment processing integration.

Tests the integration between payment tools, payment router prompt node,
and sales journey payment processing.
"""
import pytest
from unittest.mock import Mock, patch
from apps.bot.langgraph.payment_nodes import PaymentRouterPromptNode
from apps.bot.conversation_state import ConversationState


class TestPaymentRouterPromptNode:
    """Test payment router prompt node functionality."""
    
    def test_node_creation(self):
        """Test payment router prompt node can be created."""
        node = PaymentRouterPromptNode()
        assert node.name == "payment_router_prompt"
        assert node.system_prompt is not None
        assert node.output_schema is not None
    
    def test_input_preparation(self):
        """Test LLM input preparation."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "I want to pay with M-PESA"
        state.order_id = "test-order"
        state.order_totals = {"total": 1000, "currency": "KES"}
        state.available_payment_methods = [
            {"name": "M-PESA STK Push", "type": "mpesa_stk"}
        ]
        
        input_text = node._prepare_llm_input(state)
        
        assert "I want to pay with M-PESA" in input_text
        assert "KES 1,000" in input_text
        assert "M-PESA STK Push" in input_text
    
    def test_heuristic_amount_confirmation(self):
        """Test heuristic routing requires amount confirmation first."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "I want to pay"
        state.order_totals = {"total": 1500, "currency": "KES"}
        state.available_payment_methods = [
            {"name": "M-PESA STK Push", "type": "mpesa_stk"}
        ]
        # Amount not confirmed yet
        state.payment_amount_confirmed = False
        
        result = node._route_payment_heuristic(state)
        
        assert result["action"] == "confirm_amount"
        assert result["amount_confirmed"] is False
        assert "KES 1,500" in result["confirmation_message"]
        assert "confirm" in result["confirmation_message"].lower()
    
    def test_heuristic_method_selection(self):
        """Test heuristic routing with multiple payment methods."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "yes, that's correct"
        state.order_totals = {"total": 2000, "currency": "KES"}
        state.available_payment_methods = [
            {"name": "M-PESA STK Push", "type": "mpesa_stk"},
            {"name": "M-PESA C2B", "type": "mpesa_c2b"},
            {"name": "Card Payment", "type": "card"}
        ]
        # Amount already confirmed
        state.payment_amount_confirmed = True
        
        result = node._route_payment_heuristic(state)
        
        assert result["action"] == "select_method"
        assert result["amount_confirmed"] is True
        assert "select" in result["confirmation_message"].lower()
    
    def test_heuristic_stk_selection(self):
        """Test heuristic routing with STK push selection."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "1"  # Select first option (STK)
        state.order_totals = {"total": 500, "currency": "KES"}
        state.available_payment_methods = [
            {"name": "M-PESA STK Push", "type": "mpesa_stk"},
            {"name": "Card Payment", "type": "card"}
        ]
        state.payment_amount_confirmed = True
        
        result = node._route_payment_heuristic(state)
        
        assert result["action"] == "initiate_stk"
        assert result["selected_method"] == "mpesa_stk"
        assert result["amount_confirmed"] is True
        assert "stk" in result["confirmation_message"].lower()
    
    def test_heuristic_single_method(self):
        """Test heuristic routing with single payment method."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        state.incoming_message = "proceed with payment"
        state.order_totals = {"total": 750, "currency": "KES"}
        state.available_payment_methods = [
            {"name": "M-PESA STK Push", "type": "mpesa_stk"}
        ]
        state.payment_amount_confirmed = True
        
        result = node._route_payment_heuristic(state)
        
        assert result["action"] == "initiate_stk"
        assert result["selected_method"] == "mpesa_stk"
        assert result["amount_confirmed"] is True
    
    def test_state_update_amount_confirmation(self):
        """Test state update for amount confirmation."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        result = {
            "action": "confirm_amount",
            "amount_confirmed": False,
            "confirmation_message": "Please confirm the amount",
            "reasoning": "Amount confirmation required"
        }
        
        updated_state = node._update_state_from_llm_result(state, result)
        
        assert updated_state.payment_amount_confirmed is False
        assert updated_state.payment_step == "awaiting_amount_confirmation"
        assert updated_state.response_text == "Please confirm the amount"
    
    def test_state_update_method_selection(self):
        """Test state update for method selection."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        result = {
            "action": "select_method",
            "amount_confirmed": True,
            "confirmation_message": "Please select payment method",
            "reasoning": "Multiple methods available"
        }
        
        updated_state = node._update_state_from_llm_result(state, result)
        
        assert updated_state.payment_amount_confirmed is True
        assert updated_state.payment_step == "awaiting_method_selection"
        assert updated_state.response_text == "Please select payment method"
    
    def test_state_update_payment_initiation(self):
        """Test state update for payment initiation."""
        node = PaymentRouterPromptNode()
        
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        result = {
            "action": "initiate_stk",
            "selected_method": "mpesa_stk",
            "amount_confirmed": True,
            "confirmation_message": "Initiating STK push...",
            "reasoning": "STK push selected"
        }
        
        updated_state = node._update_state_from_llm_result(state, result)
        
        assert updated_state.payment_amount_confirmed is True
        assert updated_state.selected_payment_method == "mpesa_stk"
        assert updated_state.payment_step == "initiate_mpesa_stk"
        assert updated_state.response_text == "Initiating STK push..."


class TestPaymentToolsIntegration:
    """Test payment tools are properly registered and accessible."""
    
    def test_payment_tools_registered(self):
        """Test that all payment tools are registered."""
        from apps.bot.tools.registry import get_tool
        
        payment_tools = [
            "payment_get_methods",
            "payment_get_c2b_instructions", 
            "payment_initiate_stk_push",
            "payment_create_pesapal_checkout"
        ]
        
        for tool_name in payment_tools:
            tool = get_tool(tool_name)
            assert tool is not None, f"Payment tool {tool_name} not registered"
    
    def test_payment_node_registered(self):
        """Test that payment router prompt node is registered."""
        from apps.bot.langgraph.nodes import get_node_registry
        
        registry = get_node_registry()
        node = registry.get_node("payment_router_prompt")
        
        assert node is not None
        assert isinstance(node, PaymentRouterPromptNode)