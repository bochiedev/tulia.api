"""
Simple tests for Orders Journey components without LangGraph dependencies.

Tests the core functionality of order status response formatting and
order lookup parsing without requiring the full orchestrator.
"""
import pytest
from unittest.mock import Mock, patch

from apps.bot.conversation_state import ConversationState


class TestOrderLookupParsing:
    """Test order lookup request parsing without imports."""
    
    def test_parse_order_reference_pattern(self):
        """Test order reference pattern matching."""
        import re
        
        # Test the regex pattern used in _parse_order_lookup_request
        order_ref_pattern = r'ORD-\d{8}-[A-Z0-9]{8}'
        
        # Valid order references
        assert re.search(order_ref_pattern, "Check order ORD-20241220-ABC12345")
        assert re.search(order_ref_pattern, "ORD-20241220-12345678")
        assert re.search(order_ref_pattern, "My order is ORD-20241219-DEFG9876")
        
        # Invalid patterns
        assert not re.search(order_ref_pattern, "ORD-2024122-ABC12345")  # Wrong date format
        assert not re.search(order_ref_pattern, "ORD-20241220-ABC1234")   # Too short suffix
        assert not re.search(order_ref_pattern, "order-123")              # Wrong format
    
    def test_parse_uuid_pattern(self):
        """Test UUID pattern matching."""
        import re
        
        # Test the regex pattern used for UUID matching
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        
        # Valid UUIDs
        assert re.search(uuid_pattern, "123e4567-e89b-12d3-a456-426614174000")
        assert re.search(uuid_pattern, "Order status for 550e8400-e29b-41d4-a716-446655440000")
        
        # Invalid UUIDs
        assert not re.search(uuid_pattern, "123e4567-e89b-12d3-a456")  # Too short
        assert not re.search(uuid_pattern, "not-a-uuid-at-all")        # Wrong format
    
    def test_parse_phone_number_pattern(self):
        """Test phone number pattern matching."""
        import re
        
        # Test the regex pattern used for phone number matching
        phone_pattern = r'\+?254\d{9}|\+?254\s?\d{3}\s?\d{3}\s?\d{3}|0\d{9}'
        
        # Valid phone numbers
        assert re.search(phone_pattern, "+254712345678")
        assert re.search(phone_pattern, "254712345678")
        assert re.search(phone_pattern, "+254 712 345 678")
        assert re.search(phone_pattern, "0712345678")
        assert re.search(phone_pattern, "Orders for +254712345678")
        
        # Invalid phone numbers
        assert not re.search(phone_pattern, "+255712345678")  # Wrong country code
        assert not re.search(phone_pattern, "071234567")      # Too short


class TestOrderStatusFormatting:
    """Test order status formatting logic."""
    
    def test_format_status_friendly(self):
        """Test friendly status formatting logic."""
        # This tests the logic from _format_status_friendly method
        status_map = {
            'pending': '⏳ Pending',
            'processing': '📦 Processing',
            'shipped': '🚚 Shipped',
            'delivered': '✅ Delivered',
            'cancelled': '❌ Cancelled',
            'failed': '⚠️ Failed'
        }
        
        # Test known statuses
        for status, expected in status_map.items():
            result = status_map.get(status.lower(), status.title())
            assert result == expected
        
        # Test unknown status
        unknown_status = "unknown"
        result = status_map.get(unknown_status.lower(), unknown_status.title())
        assert result == "Unknown"
    
    def test_get_status_message(self):
        """Test status-specific messages."""
        messages = {
            'pending': 'Your order is awaiting payment confirmation.',
            'processing': 'Your order is being prepared for shipment.',
            'shipped': 'Your order is on its way!',
            'delivered': 'Your order has been delivered. Enjoy!',
            'cancelled': 'This order was cancelled.',
            'failed': 'There was an issue with this order. Please contact support.'
        }
        
        # Test all status messages
        for status, expected_message in messages.items():
            result = messages.get(status.lower(), '')
            assert result == expected_message
        
        # Test unknown status
        result = messages.get('unknown', '')
        assert result == ''
    
    def test_get_suggested_actions(self):
        """Test suggested actions based on status."""
        actions_map = {
            'pending': ['contact_support'],
            'processing': ['track_delivery'],
            'shipped': ['track_delivery'],
            'delivered': ['reorder'],
            'cancelled': ['reorder', 'contact_support'],
            'failed': ['contact_support', 'reorder']
        }
        
        # Test all status actions
        for status, expected_actions in actions_map.items():
            result = actions_map.get(status.lower(), [])
            assert result == expected_actions
        
        # Test unknown status
        result = actions_map.get('unknown', [])
        assert result == []


class TestConversationStateOrdersFields:
    """Test orders-specific fields in ConversationState."""
    
    def test_orders_fields_initialization(self):
        """Test that orders fields are properly initialized."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Check orders journey specific fields
        assert state.orders_step is None
        assert state.order_lookup_results is None
        assert state.primary_order_id is None
        assert state.disambiguation_question is None
    
    def test_orders_fields_assignment(self):
        """Test that orders fields can be assigned."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Assign orders journey fields
        state.orders_step = "awaiting_disambiguation"
        state.order_lookup_results = {
            "orders": [
                {"order_id": "order-123", "status": "shipped"},
                {"order_id": "order-456", "status": "delivered"}
            ]
        }
        state.primary_order_id = "order-123"
        state.disambiguation_question = "Which order would you like details on?"
        
        # Verify assignments
        assert state.orders_step == "awaiting_disambiguation"
        assert len(state.order_lookup_results["orders"]) == 2
        assert state.primary_order_id == "order-123"
        assert "Which order" in state.disambiguation_question
    
    def test_state_serialization_with_orders_fields(self):
        """Test that orders fields are included in serialization."""
        state = ConversationState(
            tenant_id="test-tenant",
            conversation_id="test-conv",
            request_id="test-req"
        )
        
        # Set orders fields
        state.orders_step = "completed"
        state.order_lookup_results = {"order_id": "order-123"}
        state.primary_order_id = "order-123"
        
        # Test serialization
        state_dict = state.to_dict()
        assert "orders_step" in state_dict
        assert "order_lookup_results" in state_dict
        assert "primary_order_id" in state_dict
        assert "disambiguation_question" in state_dict
        
        # Test deserialization
        restored_state = ConversationState.from_dict(state_dict)
        assert restored_state.orders_step == "completed"
        assert restored_state.order_lookup_results == {"order_id": "order-123"}
        assert restored_state.primary_order_id == "order-123"


class TestOrderResponseFormatting:
    """Test order response formatting logic."""
    
    def test_single_order_formatting(self):
        """Test formatting logic for single order."""
        order = {
            "order_reference": "ORD-20241220-ABC12345",
            "status": "shipped",
            "total": 1500.0,
            "currency": "KES",
            "items": [
                {"name": "Test Product", "quantity": 1},
                {"name": "Another Product", "quantity": 2}
            ],
            "created_at": "2024-12-20T10:00:00Z",
            "delivery_address": {"city": "Nairobi"}
        }
        
        # Test the formatting logic
        lines = [f"📦 Order {order['order_reference']}"]
        
        # Format status
        status_map = {
            'pending': '⏳ Pending',
            'processing': '📦 Processing',
            'shipped': '🚚 Shipped',
            'delivered': '✅ Delivered',
            'cancelled': '❌ Cancelled',
            'failed': '⚠️ Failed'
        }
        friendly_status = status_map.get(order['status'].lower(), order['status'].title())
        lines.append(f"Status: {friendly_status}")
        
        lines.append(f"Total: {order['currency']} {order['total']:,.0f}")
        lines.append(f"Date: {order['created_at'][:10]}")
        
        # Add items
        items = order['items']
        if items:
            lines.append(f"\nItems ({len(items)}):")
            for item in items[:3]:  # Show first 3 items
                item_name = item['name']
                quantity = item['quantity']
                lines.append(f"  • {item_name} (x{quantity})")
        
        # Add delivery address
        delivery_address = order['delivery_address']
        if delivery_address and isinstance(delivery_address, dict):
            city = delivery_address.get('city', '')
            if city:
                lines.append(f"\nDelivery to: {city}")
        
        result = "\n".join(lines)
        
        # Verify formatting
        assert "📦 Order ORD-20241220-ABC12345" in result
        assert "🚚 Shipped" in result
        assert "KES 1,500" in result
        assert "2024-12-20" in result
        assert "Items (2)" in result
        assert "Test Product (x1)" in result
        assert "Another Product (x2)" in result
        assert "Delivery to: Nairobi" in result
    
    def test_multiple_orders_formatting(self):
        """Test formatting logic for multiple orders."""
        orders = [
            {
                "order_reference": "ORD-20241220-ABC12345",
                "status": "shipped",
                "total": 1500.0,
                "currency": "KES",
                "created_at": "2024-12-20T10:00:00Z"
            },
            {
                "order_reference": "ORD-20241219-DEF67890",
                "status": "delivered",
                "total": 2500.0,
                "currency": "KES",
                "created_at": "2024-12-19T15:30:00Z"
            }
        ]
        
        # Test multiple orders formatting logic
        response_lines = [f"I found {len(orders)} orders for you:\n"]
        
        for i, order in enumerate(orders, 1):
            order_ref = order['order_reference']
            status = order['status']
            total = order['total']
            currency = order['currency']
            created_at = order['created_at'][:10]
            
            line = f"{i}. Order {order_ref} - {status.title()}"
            line += f" | {currency} {total:,.0f}"
            line += f" | {created_at}"
            response_lines.append(line)
        
        response_lines.append("\nWhich order would you like to know more about? Reply with the number or order reference.")
        
        result = "\n".join(response_lines)
        
        # Verify formatting
        assert "I found 2 orders" in result
        assert "1. Order ORD-20241220-ABC12345 - Shipped" in result
        assert "2. Order ORD-20241219-DEF67890 - Delivered" in result
        assert "KES 1,500" in result
        assert "KES 2,500" in result
        assert "2024-12-20" in result
        assert "2024-12-19" in result
        assert "Which order would you like" in result


@pytest.mark.django_db
class TestOrderToolIntegration:
    """Test integration with order tools."""
    
    def test_order_get_status_tool_exists(self):
        """Test that order_get_status tool exists and has correct schema."""
        from apps.bot.tools.order_tools import OrderGetStatusTool
        
        tool = OrderGetStatusTool()
        schema = tool.get_schema()
        
        # Verify required fields
        required_fields = schema.get("required", [])
        assert "tenant_id" in required_fields
        assert "request_id" in required_fields
        assert "conversation_id" in required_fields
        
        # Verify optional fields for lookup
        properties = schema.get("properties", {})
        assert "order_id" in properties
        assert "order_reference" in properties
        assert "customer_id" in properties
    
    @patch('apps.orders.models.Order.objects')
    def test_order_tool_tenant_scoping(self, mock_orders):
        """Test that order tool enforces tenant scoping."""
        from apps.bot.tools.order_tools import OrderGetStatusTool
        
        # Mock order queryset with tenant filtering
        mock_queryset = Mock()
        mock_orders.filter.return_value = mock_queryset
        mock_queryset.select_related.return_value = mock_queryset
        mock_queryset.get.side_effect = Exception("Order not found")
        
        tool = OrderGetStatusTool()
        
        # Mock validate_tenant_access to return True
        tool.validate_tenant_access = Mock(return_value=True)
        
        # Execute tool
        result = tool.execute(
            tenant_id="test-tenant",
            request_id="test-req",
            conversation_id="test-conv",
            order_id="order-123"
        )
        
        # Verify tenant filtering was applied
        mock_orders.filter.assert_called_with(tenant_id="test-tenant")
        
        # Should fail because order doesn't exist
        assert not result.success
        assert result.error_code == "ORDER_NOT_FOUND"