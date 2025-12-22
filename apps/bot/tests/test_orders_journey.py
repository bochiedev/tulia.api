"""
Tests for Orders Journey implementation.

Tests the orders journey subgraph functionality including order status lookup,
response formatting, and disambiguation handling.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.orders_journey import (
    OrderStatusResponseNode,
    execute_orders_journey_node,
    _parse_order_lookup_request
)
from apps.bot.tools.base import ToolResponse


@pytest.mark.django_db
class TestOrderStatusResponseNode:
    """Test OrderStatusResponseNode LLM node."""
    
    def test_init(self):
        """Test node initialization."""
        node = OrderStatusResponseNode()
        assert node.node_name == "order_status_response"
        assert node.system_prompt is not None
        assert node.output_schema is not None
    
    def test_prepare_llm_input_single_order(self):
        """Test LLM input preparation for single order."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="check my order ORD-20241220-ABC12345"
        )
        
        # Mock order lookup results
        state.order_lookup_results = {
            "order_id": "order-123",
            "order_reference": "ORD-20241220-ABC12345",
            "status": "shipped",
            "total": 1500.0,
            "currency": "KES",
            "items": [{"name": "Test Product", "quantity": 1}],
            "created_at": "2024-12-20T10:00:00Z"
        }
        
        node = OrderStatusResponseNode()
        input_text = node._prepare_llm_input(state)
        
        assert "check my order ORD-20241220-ABC12345" in input_text
        assert "Single order found:" in input_text
        assert "ORD-20241220-ABC12345" in input_text
        assert "shipped" in input_text
    
    def test_prepare_llm_input_multiple_orders(self):
        """Test LLM input preparation for multiple orders."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="show my orders"
        )
        
        # Mock multiple order lookup results
        state.order_lookup_results = {
            "orders": [
                {
                    "order_id": "order-123",
                    "order_reference": "ORD-20241220-ABC12345",
                    "status": "shipped",
                    "total": 1500.0,
                    "currency": "KES",
                    "items": [{"name": "Test Product 1", "quantity": 1}],
                    "created_at": "2024-12-20T10:00:00Z"
                },
                {
                    "order_id": "order-456",
                    "order_reference": "ORD-20241219-DEF67890",
                    "status": "delivered",
                    "total": 2500.0,
                    "currency": "KES",
                    "items": [{"name": "Test Product 2", "quantity": 2}],
                    "created_at": "2024-12-19T15:30:00Z"
                }
            ],
            "count": 2
        }
        
        node = OrderStatusResponseNode()
        input_text = node._prepare_llm_input(state)
        
        assert "show my orders" in input_text
        assert "Number of orders found: 2" in input_text
        assert "ORD-20241220-ABC12345" in input_text
        assert "ORD-20241219-DEF67890" in input_text
    
    def test_format_order_status_simple_single_order(self):
        """Test simple formatting for single order."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Mock single order
        state.order_lookup_results = {
            "order_id": "order-123",
            "order_reference": "ORD-20241220-ABC12345",
            "status": "shipped",
            "total": 1500.0,
            "currency": "KES",
            "items": [
                {"name": "Test Product", "quantity": 1, "unit_price": 1500.0}
            ],
            "created_at": "2024-12-20T10:00:00Z",
            "delivery_address": {"city": "Nairobi"}
        }
        
        node = OrderStatusResponseNode()
        result = node._format_order_status_simple(state)
        
        assert result["orders_count"] == 1
        assert result["requires_disambiguation"] is False
        assert "ORD-20241220-ABC12345" in result["response_text"]
        assert "🚚 Shipped" in result["response_text"]
        assert "KES 1,500" in result["response_text"]
        assert "Test Product" in result["response_text"]
        assert "Nairobi" in result["response_text"]
    
    def test_format_order_status_simple_multiple_orders(self):
        """Test simple formatting for multiple orders requiring disambiguation."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Mock multiple orders
        state.order_lookup_results = {
            "orders": [
                {
                    "order_id": "order-123",
                    "order_reference": "ORD-20241220-ABC12345",
                    "status": "shipped",
                    "total": 1500.0,
                    "currency": "KES",
                    "created_at": "2024-12-20T10:00:00Z"
                },
                {
                    "order_id": "order-456",
                    "order_reference": "ORD-20241219-DEF67890",
                    "status": "delivered",
                    "total": 2500.0,
                    "currency": "KES",
                    "created_at": "2024-12-19T15:30:00Z"
                }
            ],
            "count": 2
        }
        
        node = OrderStatusResponseNode()
        result = node._format_order_status_simple(state)
        
        assert result["orders_count"] == 2
        assert result["requires_disambiguation"] is True
        assert "I found 2 orders" in result["response_text"]
        assert "ORD-20241220-ABC12345" in result["response_text"]
        assert "ORD-20241219-DEF67890" in result["response_text"]
        assert "Which order would you like" in result["response_text"]
    
    def test_format_status_friendly(self):
        """Test friendly status formatting."""
        node = OrderStatusResponseNode()
        
        assert node._format_status_friendly("pending") == "⏳ Pending"
        assert node._format_status_friendly("processing") == "📦 Processing"
        assert node._format_status_friendly("shipped") == "🚚 Shipped"
        assert node._format_status_friendly("delivered") == "✅ Delivered"
        assert node._format_status_friendly("cancelled") == "❌ Cancelled"
        assert node._format_status_friendly("failed") == "⚠️ Failed"
        assert node._format_status_friendly("unknown") == "Unknown"
    
    def test_get_suggested_actions(self):
        """Test suggested actions based on status."""
        node = OrderStatusResponseNode()
        
        assert node._get_suggested_actions("pending") == ["contact_support"]
        assert node._get_suggested_actions("processing") == ["track_delivery"]
        assert node._get_suggested_actions("shipped") == ["track_delivery"]
        assert node._get_suggested_actions("delivered") == ["reorder"]
        assert "contact_support" in node._get_suggested_actions("cancelled")
        assert "contact_support" in node._get_suggested_actions("failed")


class TestOrderLookupParsing:
    """Test order lookup request parsing."""
    
    def test_parse_order_reference(self):
        """Test parsing order reference from message."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="Check order ORD-20241220-ABC12345"
        )
        
        result = _parse_order_lookup_request(state)
        assert result == {"order_reference": "ORD-20241220-ABC12345"}
    
    def test_parse_uuid_order_id(self):
        """Test parsing UUID order ID from message."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="Order status for 123e4567-e89b-12d3-a456-426614174000"
        )
        
        result = _parse_order_lookup_request(state)
        assert result == {"order_id": "123e4567-e89b-12d3-a456-426614174000"}
    
    def test_parse_phone_number(self):
        """Test parsing phone number for customer lookup."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            customer_id="customer-123",
            incoming_message="Orders for +254712345678"
        )
        
        result = _parse_order_lookup_request(state)
        assert result == {"customer_id": "customer-123"}
    
    def test_parse_my_orders(self):
        """Test parsing 'my orders' request."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            customer_id="customer-123",
            incoming_message="show my orders"
        )
        
        result = _parse_order_lookup_request(state)
        assert result == {"customer_id": "customer-123"}
    
    def test_parse_disambiguation_selection(self):
        """Test parsing number selection for disambiguation."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="2"
        )
        
        # Mock previous order lookup results
        state.order_lookup_results = {
            "orders": [
                {"order_id": "order-123"},
                {"order_id": "order-456"},
                {"order_id": "order-789"}
            ]
        }
        
        result = _parse_order_lookup_request(state)
        assert result == {"order_id": "order-456"}  # Second order (index 1)
    
    def test_parse_insufficient_info(self):
        """Test parsing when insufficient information provided."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req",
            incoming_message="hello"
        )
        
        result = _parse_order_lookup_request(state)
        assert result is None


@pytest.mark.asyncio
class TestOrdersJourneyExecution:
    """Test orders journey execution."""
    
    async def test_execute_orders_journey_insufficient_info(self):
        """Test execution when insufficient order info provided."""
        state_dict = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "incoming_message": "hello",
            "turn_count": 1
        }
        
        result = await execute_orders_journey_node(state_dict)
        
        assert "Please provide your order reference number" in result["response_text"]
        assert result.get("orders_step") == "awaiting_order_info"
    
    @patch('apps.bot.tools.registry.get_tool_registry')
    async def test_execute_orders_journey_tool_not_found(self, mock_registry):
        """Test execution when order tool not found."""
        # Mock tool registry without order_get_status tool
        mock_registry.return_value.get_tool.return_value = None
        
        state_dict = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "customer_id": "customer-123",
            "incoming_message": "my orders",
            "turn_count": 1
        }
        
        result = await execute_orders_journey_node(state_dict)
        
        assert "trouble accessing order information" in result["response_text"]
        assert result.get("escalation_required") is True
    
    @patch('apps.bot.tools.registry.get_tool_registry')
    async def test_execute_orders_journey_tool_failure(self, mock_registry):
        """Test execution when order tool fails."""
        # Mock tool that returns failure
        mock_tool = Mock()
        mock_tool.execute.return_value = ToolResponse(
            success=False,
            error="Order not found",
            error_code="ORDER_NOT_FOUND"
        )
        mock_registry.return_value.get_tool.return_value = mock_tool
        
        state_dict = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "incoming_message": "ORD-20241220-ABC12345",
            "turn_count": 1
        }
        
        result = await execute_orders_journey_node(state_dict)
        
        assert "couldn't find an order with that reference" in result["response_text"]
        assert result.get("orders_step") == "error"
    
    @patch('apps.bot.langgraph.orders_journey.OrderStatusResponseNode')
    @patch('apps.bot.tools.registry.get_tool_registry')
    async def test_execute_orders_journey_success(self, mock_registry, mock_node_class):
        """Test successful orders journey execution."""
        # Mock successful tool response
        mock_tool = Mock()
        mock_tool.execute.return_value = ToolResponse(
            success=True,
            data={
                "order_id": "order-123",
                "order_reference": "ORD-20241220-ABC12345",
                "status": "shipped",
                "total": 1500.0
            }
        )
        mock_registry.return_value.get_tool.return_value = mock_tool
        
        # Mock LLM node
        mock_node = Mock()
        mock_node.execute = AsyncMock()
        
        async def mock_execute(state):
            state.response_text = "Your order ORD-20241220-ABC12345 is shipped"
            state.orders_step = "completed"
            return state
        
        mock_node.execute.side_effect = mock_execute
        mock_node_class.return_value = mock_node
        
        state_dict = {
            "tenant_id": "test-tenant",
            "conversation_id": "test-conv",
            "request_id": "test-req",
            "incoming_message": "ORD-20241220-ABC12345",
            "turn_count": 1
        }
        
        result = await execute_orders_journey_node(state_dict)
        
        assert "Your order ORD-20241220-ABC12345 is shipped" in result["response_text"]
        assert result.get("orders_step") == "completed"
        assert "order_lookup_results" in result
        
        # Verify tool was called with correct parameters
        mock_tool.execute.assert_called_once()
        call_args = mock_tool.execute.call_args[1]
        assert call_args["tenant_id"] == "test-tenant"
        assert call_args["order_reference"] == "ORD-20241220-ABC12345"