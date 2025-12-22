"""
Orders Journey subgraph implementation for LangGraph orchestration.

This module implements the complete orders journey workflow for order status
checking, order lookup by reference and customer, and handling multiple orders
with disambiguation.
"""
import logging
from typing import Dict, Any, Optional, List
import json
from dataclasses import asdict

from apps.bot.langgraph.nodes import LLMNode, ToolNode
from apps.bot.conversation_state import ConversationState
from apps.bot.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class OrderStatusResponseNode(LLMNode):
    """
    Order status response LLM node for status summaries.
    
    Formats order status information into clear, customer-friendly summaries
    with relevant details and next steps.
    """
    
    def __init__(self):
        """Initialize order status response node."""
        system_prompt = """You are a customer service assistant helping customers check their order status.

Your role is to format order status information into clear, helpful responses.

FORMATTING RULES:
- Use conversational, friendly tone
- Include order reference number prominently
- Clearly state current order status
- Provide relevant details (items, total, delivery info)
- Mention expected next steps or timelines
- Offer help with any issues

ORDER STATUS TYPES:
- pending: Order received, awaiting payment or processing
- processing: Order is being prepared
- shipped: Order has been dispatched
- delivered: Order has been delivered
- cancelled: Order was cancelled
- failed: Order failed (payment or other issue)

PRESENTATION GUIDELINES:
- Start with order reference for easy identification
- Use clear status language customers understand
- Include item count and total amount
- Mention delivery address if relevant
- Provide tracking info if available
- Suggest next actions (track delivery, contact support, etc.)
- For multiple orders, present in reverse chronological order (newest first)
- Keep each order summary concise but complete

MULTIPLE ORDERS HANDLING:
- If showing multiple orders, number them clearly
- Highlight the most recent order
- Offer to provide details on specific orders
- Suggest filtering if too many orders

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "response_text": "formatted order status response with clear information",
    "orders_count": number,
    "primary_order_id": "uuid of main order being discussed",
    "requires_disambiguation": true|false,
    "disambiguation_question": "question to ask if multiple orders need clarification",
    "suggested_actions": ["track_delivery", "contact_support", "reorder", "cancel"]
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "response_text": {"type": "string"},
                "orders_count": {"type": "integer"},
                "primary_order_id": {"type": "string"},
                "requires_disambiguation": {"type": "boolean"},
                "disambiguation_question": {"type": "string"},
                "suggested_actions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["response_text", "orders_count", "requires_disambiguation"]
        }
        
        super().__init__("order_status_response", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for order status response formatting.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer message: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Customer language: {state.response_language}"
        ]
        
        # Add order data from state
        if hasattr(state, 'order_lookup_results') and state.order_lookup_results:
            orders = state.order_lookup_results
            
            if isinstance(orders, dict) and 'orders' in orders:
                # Multiple orders
                orders_list = orders['orders']
                context_parts.append(f"Number of orders found: {len(orders_list)}")
                
                for i, order in enumerate(orders_list[:5], 1):  # Limit to 5 for context
                    order_info = self._format_order_for_context(order, i)
                    context_parts.append(order_info)
                    
            elif isinstance(orders, dict):
                # Single order
                context_parts.append("Single order found:")
                order_info = self._format_order_for_context(orders, 1)
                context_parts.append(order_info)
        else:
            context_parts.append("No order data available")
        
        return "\n".join(context_parts)
    
    def _format_order_for_context(self, order: Dict[str, Any], position: int) -> str:
        """
        Format order data for LLM context.
        
        Args:
            order: Order data dictionary
            position: Position in list
            
        Returns:
            Formatted order string
        """
        order_ref = order.get('order_reference', 'Unknown')
        status = order.get('status', 'unknown')
        total = order.get('total', 0)
        currency = order.get('currency', 'KES')
        items_count = len(order.get('items', []))
        created_at = order.get('created_at', '')
        
        order_str = f"Order {position}: {order_ref}"
        order_str += f" | Status: {status}"
        order_str += f" | Total: {currency} {total:,.0f}"
        order_str += f" | Items: {items_count}"
        if created_at:
            order_str += f" | Date: {created_at[:10]}"
        
        return order_str
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for order status response formatting.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Order status response result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to simple formatting
                return self._format_order_status_simple(state)
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('order_status_formatting')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=400,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'order_status_formatting', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                required_fields = ["response_text", "orders_count", "requires_disambiguation"]
                if not all(key in result for key in required_fields):
                    raise ValueError("Missing required fields in LLM response")
                
                # Ensure suggested_actions is a list
                if "suggested_actions" not in result:
                    result["suggested_actions"] = []
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse order status response LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to simple formatting
                return self._format_order_status_simple(state)
            
        except Exception as e:
            logger.error(
                f"Order status response LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to simple formatting
            return self._format_order_status_simple(state)
    
    def _format_order_status_simple(self, state: ConversationState) -> Dict[str, Any]:
        """
        Simple fallback formatting for order status.
        
        Args:
            state: Current conversation state
            
        Returns:
            Simple formatted result
        """
        if not hasattr(state, 'order_lookup_results') or not state.order_lookup_results:
            return {
                "response_text": "I couldn't find any orders. Could you provide your order reference number or the phone number you used to place the order?",
                "orders_count": 0,
                "requires_disambiguation": False,
                "suggested_actions": []
            }
        
        orders_data = state.order_lookup_results
        
        # Handle single order
        if isinstance(orders_data, dict) and 'order_id' in orders_data:
            response_text = self._format_single_order_simple(orders_data)
            return {
                "response_text": response_text,
                "orders_count": 1,
                "primary_order_id": orders_data.get('order_id', ''),
                "requires_disambiguation": False,
                "suggested_actions": self._get_suggested_actions(orders_data.get('status', ''))
            }
        
        # Handle multiple orders
        elif isinstance(orders_data, dict) and 'orders' in orders_data:
            orders_list = orders_data['orders']
            
            if len(orders_list) == 0:
                return {
                    "response_text": "I couldn't find any orders for you. Could you check your order reference number?",
                    "orders_count": 0,
                    "requires_disambiguation": False,
                    "suggested_actions": []
                }
            
            elif len(orders_list) == 1:
                response_text = self._format_single_order_simple(orders_list[0])
                return {
                    "response_text": response_text,
                    "orders_count": 1,
                    "primary_order_id": orders_list[0].get('order_id', ''),
                    "requires_disambiguation": False,
                    "suggested_actions": self._get_suggested_actions(orders_list[0].get('status', ''))
                }
            
            else:
                # Multiple orders - need disambiguation
                response_lines = [f"I found {len(orders_list)} orders for you:\n"]
                
                for i, order in enumerate(orders_list[:5], 1):
                    order_ref = order.get('order_reference', 'Unknown')
                    status = order.get('status', 'unknown')
                    total = order.get('total', 0)
                    currency = order.get('currency', 'KES')
                    created_at = order.get('created_at', '')[:10]
                    
                    line = f"{i}. Order {order_ref} - {status.title()}"
                    line += f" | {currency} {total:,.0f}"
                    line += f" | {created_at}"
                    response_lines.append(line)
                
                response_lines.append("\nWhich order would you like to know more about? Reply with the number or order reference.")
                
                return {
                    "response_text": "\n".join(response_lines),
                    "orders_count": len(orders_list),
                    "primary_order_id": orders_list[0].get('order_id', ''),
                    "requires_disambiguation": True,
                    "disambiguation_question": "Which order would you like details on?",
                    "suggested_actions": []
                }
        
        # Fallback
        return {
            "response_text": "I'm having trouble retrieving your order information. Could you provide your order reference number?",
            "orders_count": 0,
            "requires_disambiguation": False,
            "suggested_actions": []
        }
    
    def _format_single_order_simple(self, order: Dict[str, Any]) -> str:
        """
        Format a single order for simple response.
        
        Args:
            order: Order data dictionary
            
        Returns:
            Formatted order status text
        """
        order_ref = order.get('order_reference', 'Unknown')
        status = order.get('status', 'unknown')
        total = order.get('total', 0)
        currency = order.get('currency', 'KES')
        items = order.get('items', [])
        created_at = order.get('created_at', '')[:10]
        
        # Build response
        lines = [f"📦 Order {order_ref}"]
        lines.append(f"Status: {self._format_status_friendly(status)}")
        lines.append(f"Total: {currency} {total:,.0f}")
        lines.append(f"Date: {created_at}")
        
        # Add items summary
        if items:
            lines.append(f"\nItems ({len(items)}):")
            for item in items[:3]:  # Show first 3 items
                item_name = item.get('name', 'Unknown item')
                quantity = item.get('quantity', 1)
                lines.append(f"  • {item_name} (x{quantity})")
            
            if len(items) > 3:
                lines.append(f"  ... and {len(items) - 3} more items")
        
        # Add delivery address if available
        delivery_address = order.get('delivery_address', {})
        if delivery_address and isinstance(delivery_address, dict):
            city = delivery_address.get('city', '')
            if city:
                lines.append(f"\nDelivery to: {city}")
        
        # Add status-specific message
        status_message = self._get_status_message(status)
        if status_message:
            lines.append(f"\n{status_message}")
        
        return "\n".join(lines)
    
    def _format_status_friendly(self, status: str) -> str:
        """
        Format status into customer-friendly text.
        
        Args:
            status: Order status code
            
        Returns:
            Friendly status text
        """
        status_map = {
            'pending': '⏳ Pending',
            'processing': '📦 Processing',
            'shipped': '🚚 Shipped',
            'delivered': '✅ Delivered',
            'cancelled': '❌ Cancelled',
            'failed': '⚠️ Failed'
        }
        return status_map.get(status.lower(), status.title())
    
    def _get_status_message(self, status: str) -> str:
        """
        Get status-specific message for customer.
        
        Args:
            status: Order status code
            
        Returns:
            Status-specific message
        """
        messages = {
            'pending': 'Your order is awaiting payment confirmation.',
            'processing': 'Your order is being prepared for shipment.',
            'shipped': 'Your order is on its way!',
            'delivered': 'Your order has been delivered. Enjoy!',
            'cancelled': 'This order was cancelled.',
            'failed': 'There was an issue with this order. Please contact support.'
        }
        return messages.get(status.lower(), '')
    
    def _get_suggested_actions(self, status: str) -> List[str]:
        """
        Get suggested actions based on order status.
        
        Args:
            status: Order status code
            
        Returns:
            List of suggested action codes
        """
        actions_map = {
            'pending': ['contact_support'],
            'processing': ['track_delivery'],
            'shipped': ['track_delivery'],
            'delivered': ['reorder'],
            'cancelled': ['reorder', 'contact_support'],
            'failed': ['contact_support', 'reorder']
        }
        return actions_map.get(status.lower(), [])
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from order status response result.
        
        Args:
            state: Current conversation state
            result: LLM response result
            
        Returns:
            Updated conversation state
        """
        # Set response text
        state.response_text = result["response_text"]
        
        # Store disambiguation info if needed
        if result.get("requires_disambiguation", False):
            state.orders_step = "awaiting_disambiguation"
            state.disambiguation_question = result.get("disambiguation_question", "")
        else:
            state.orders_step = "completed"
        
        # Store primary order ID for follow-up
        if result.get("primary_order_id"):
            state.primary_order_id = result["primary_order_id"]
        
        logger.info(
            f"Order status response generated: {result['orders_count']} orders",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "orders_count": result["orders_count"],
                "requires_disambiguation": result.get("requires_disambiguation", False),
                "suggested_actions": result.get("suggested_actions", [])
            }
        )
        
        return state


async def execute_orders_journey_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the orders journey subgraph.
    
    This function orchestrates the complete orders journey workflow:
    1. Parse order lookup request (order ID, reference, or customer)
    2. Call order_get_status tool
    3. Format response with order_status_response LLM node
    4. Handle multiple orders with disambiguation
    
    Args:
        state: Current conversation state dictionary
        
    Returns:
        Updated conversation state dictionary
    """
    # Convert dict state to ConversationState
    conv_state = ConversationState.from_dict(state)
    
    logger.info(
        f"Starting orders journey",
        extra={
            "tenant_id": conv_state.tenant_id,
            "conversation_id": conv_state.conversation_id,
            "request_id": conv_state.request_id,
            "incoming_message": conv_state.incoming_message
        }
    )
    
    try:
        # Step 1: Parse order lookup request
        order_lookup_params = _parse_order_lookup_request(conv_state)
        
        if not order_lookup_params:
            # Need more information
            conv_state.response_text = "I can help you check your order status. Please provide your order reference number or the phone number you used to place the order."
            conv_state.orders_step = "awaiting_order_info"
            return asdict(conv_state)
        
        # Step 2: Call order_get_status tool
        from apps.bot.tools.registry import get_tool_registry
        tool_registry = get_tool_registry()
        order_tool = tool_registry.get_tool("order_get_status")
        
        if not order_tool:
            logger.error("order_get_status tool not found in registry")
            conv_state.response_text = "I'm having trouble accessing order information right now. Please try again in a moment."
            conv_state.set_escalation("order_get_status tool not available")
            return asdict(conv_state)
        
        # Execute tool with tenant scoping
        tool_params = {
            "tenant_id": conv_state.tenant_id,
            "request_id": conv_state.request_id,
            "conversation_id": conv_state.conversation_id,
            **order_lookup_params
        }
        
        tool_response = order_tool.execute(**tool_params)
        
        if not tool_response.success:
            # Tool execution failed
            error_code = tool_response.error_code
            error_message = tool_response.error
            
            logger.warning(
                f"Order lookup failed: {error_code} - {error_message}",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id,
                    "error_code": error_code,
                    "lookup_params": order_lookup_params
                }
            )
            
            # Generate appropriate error response
            if error_code == "ORDER_NOT_FOUND":
                conv_state.response_text = "I couldn't find an order with that reference. Could you double-check the order number or provide the phone number you used?"
            elif error_code == "CUSTOMER_NOT_FOUND":
                conv_state.response_text = "I couldn't find any orders for that phone number. Please verify the number or provide your order reference."
            else:
                conv_state.response_text = "I'm having trouble retrieving your order information. Please try again or contact support."
                conv_state.set_escalation(f"Order lookup error: {error_code}")
            
            conv_state.orders_step = "error"
            return asdict(conv_state)
        
        # Store order lookup results in state
        conv_state.order_lookup_results = tool_response.data
        
        # Step 3: Format response with order_status_response LLM node
        order_status_node = OrderStatusResponseNode()
        conv_state = await order_status_node.execute(conv_state)
        
        # Step 4: Handle disambiguation if needed
        if hasattr(conv_state, 'orders_step') and conv_state.orders_step == "awaiting_disambiguation":
            # Multiple orders found - customer needs to specify which one
            logger.info(
                f"Multiple orders found - awaiting disambiguation",
                extra={
                    "tenant_id": conv_state.tenant_id,
                    "conversation_id": conv_state.conversation_id,
                    "request_id": conv_state.request_id,
                    "orders_count": len(conv_state.order_lookup_results.get('orders', []))
                }
            )
        
        logger.info(
            f"Orders journey completed successfully",
            extra={
                "tenant_id": conv_state.tenant_id,
                "conversation_id": conv_state.conversation_id,
                "request_id": conv_state.request_id,
                "orders_step": getattr(conv_state, 'orders_step', 'completed')
            }
        )
        
        # Convert back to dict for LangGraph
        from dataclasses import asdict
        return asdict(conv_state)
        
    except Exception as e:
        logger.error(
            f"Orders journey execution failed: {e}",
            extra={
                "tenant_id": conv_state.tenant_id,
                "conversation_id": conv_state.conversation_id,
                "request_id": conv_state.request_id
            },
            exc_info=True
        )
        
        # Fallback error response
        conv_state.response_text = "I'm having trouble processing your order request. Let me connect you with someone who can help."
        conv_state.set_escalation(f"Orders journey error: {str(e)}")
        
        from dataclasses import asdict
        return asdict(conv_state)


def _parse_order_lookup_request(state: ConversationState) -> Optional[Dict[str, Any]]:
    """
    Parse order lookup request from customer message.
    
    Extracts order ID, order reference, or customer ID from the message.
    
    Args:
        state: Current conversation state
        
    Returns:
        Dictionary with lookup parameters or None if insufficient info
    """
    message = (state.incoming_message or "").strip()
    
    if not message:
        return None
    
    # Check if this is a disambiguation response (number selection)
    if message.isdigit() and hasattr(state, 'order_lookup_results'):
        # Customer selected an order by number
        selection = int(message)
        orders_data = state.order_lookup_results
        
        if isinstance(orders_data, dict) and 'orders' in orders_data:
            orders_list = orders_data['orders']
            if 1 <= selection <= len(orders_list):
                selected_order = orders_list[selection - 1]
                return {"order_id": selected_order.get('order_id')}
    
    # Check for order reference pattern (ORD-YYYYMMDD-XXXXXXXX)
    import re
    order_ref_pattern = r'ORD-\d{8}-[A-Z0-9]{8}'
    order_ref_match = re.search(order_ref_pattern, message.upper())
    
    if order_ref_match:
        return {"order_reference": order_ref_match.group(0)}
    
    # Check for UUID pattern (order ID)
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    uuid_match = re.search(uuid_pattern, message.lower())
    
    if uuid_match:
        return {"order_id": uuid_match.group(0)}
    
    # Check for phone number pattern (for customer lookup)
    phone_pattern = r'\+?254\d{9}|\+?254\s?\d{3}\s?\d{3}\s?\d{3}|0\d{9}'
    phone_match = re.search(phone_pattern, message)
    
    if phone_match:
        # Extract and normalize phone number
        phone = phone_match.group(0).replace(' ', '')
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone
        
        # Need to look up customer by phone
        # For now, use customer_id from state if available
        if state.customer_id:
            return {"customer_id": state.customer_id}
    
    # Check if customer_id is available in state for general order lookup
    if state.customer_id:
        # Customer asking about "my orders" or similar
        my_orders_keywords = ['my order', 'my orders', 'order status', 'check order', 'track order']
        if any(keyword in message.lower() for keyword in my_orders_keywords):
            return {"customer_id": state.customer_id}
    
    # Insufficient information
    return None
