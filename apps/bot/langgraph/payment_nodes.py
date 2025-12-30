"""
Payment processing LLM nodes for LangGraph orchestration.

This module implements payment-specific LLM nodes for routing payment methods
and handling payment confirmations.
"""
import logging
from typing import Dict, Any
import json

from apps.bot.langgraph.nodes import LLMNode
from apps.bot.conversation_state import ConversationState
from apps.bot.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class PaymentRouterPromptNode(LLMNode):
    """
    Payment router prompt LLM node for method selection.
    
    Routes payment flow based on enabled methods and user preferences,
    with amount confirmation before all payment initiations.
    """
    
    def __init__(self):
        """Initialize payment router prompt node."""
        system_prompt = """You are a payment assistant helping customers complete their purchase securely.

Your role is to guide customers through payment method selection and confirmation.

PAYMENT METHOD ROUTING:
- MPESA STK Push: Direct phone prompt (fastest, most convenient)
- MPESA C2B: Manual payment with paybill/till number (alternative if STK fails)
- Card Payment (PesaPal): Hosted card payment page (for card users)

DECISION RULES:
- If only one method available: recommend that method
- If multiple methods: ask customer preference
- Always confirm the exact amount before initiating payment
- Provide clear instructions for each payment method
- Handle payment method preferences from previous interactions

AMOUNT CONFIRMATION (CRITICAL):
- ALWAYS confirm the total amount with the customer before initiating payment
- Show currency and amount clearly
- Ask explicit confirmation: "Confirm payment of KES X?"
- Never initiate payment without explicit confirmation

SECURITY GUIDELINES:
- Never ask for card details directly (use hosted payment page)
- Never store or transmit sensitive payment information
- Provide clear payment status updates
- Handle payment failures gracefully with alternatives

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "action": "confirm_amount|select_method|initiate_stk|initiate_c2b|initiate_card|clarify",
    "selected_method": "mpesa_stk|mpesa_c2b|card|null",
    "amount_confirmed": true|false,
    "confirmation_message": "message to show customer",
    "next_step": "description of what happens next",
    "reasoning": "brief explanation of decision"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["confirm_amount", "select_method", "initiate_stk", "initiate_c2b", "initiate_card", "clarify"]
                },
                "selected_method": {
                    "type": "string",
                    "enum": ["mpesa_stk", "mpesa_c2b", "card", None]
                },
                "amount_confirmed": {"type": "boolean"},
                "confirmation_message": {"type": "string"},
                "next_step": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["action", "amount_confirmed", "confirmation_message", "reasoning"]
        }
        
        super().__init__("payment_router_prompt", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for payment routing.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer message: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}"
        ]
        
        # Add order details
        if state.order_id and state.order_totals:
            total = state.order_totals.get('total', 0)
            currency = state.order_totals.get('currency', 'KES')
            context_parts.append(f"Order total: {currency} {total:,.0f}")
            context_parts.append(f"Order ID: {state.order_id}")
        
        # Add available payment methods
        if hasattr(state, 'available_payment_methods') and state.available_payment_methods:
            methods = [m.get('name', 'Unknown') for m in state.available_payment_methods]
            context_parts.append(f"Available payment methods: {', '.join(methods)}")
        
        # Add payment confirmation status
        if hasattr(state, 'payment_amount_confirmed'):
            context_parts.append(f"Amount already confirmed: {state.payment_amount_confirmed}")
        
        # Add selected payment method if any
        if hasattr(state, 'selected_payment_method'):
            context_parts.append(f"Selected method: {state.selected_payment_method}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for payment routing decision.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Payment routing result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)

            await llm_router._ensure_config_loaded()

            await llm_router._ensure_config_loaded()
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to heuristic routing
                return self._route_payment_heuristic(state)
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('payment_routing')
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
                max_tokens=250,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'payment_routing', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                required_fields = ["action", "amount_confirmed", "confirmation_message", "reasoning"]
                if not all(key in result for key in required_fields):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate action
                valid_actions = ["confirm_amount", "select_method", "initiate_stk", "initiate_c2b", "initiate_card", "clarify"]
                if result["action"] not in valid_actions:
                    result["action"] = "clarify"
                    result["reasoning"] = "Invalid action from LLM"
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse payment router LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to heuristic routing
                return self._route_payment_heuristic(state)
            
        except Exception as e:
            logger.error(
                f"Payment router LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to heuristic routing
            return self._route_payment_heuristic(state)
    
    def _route_payment_heuristic(self, state: ConversationState) -> Dict[str, Any]:
        """
        Heuristic payment routing as fallback.
        
        Args:
            state: Current conversation state
            
        Returns:
            Routing decision
        """
        message_lower = (state.incoming_message or "").lower().strip()
        
        # Check if amount is confirmed
        amount_confirmed = getattr(state, 'payment_amount_confirmed', False)
        
        # Get order total
        total = 0
        currency = 'KES'
        if state.order_totals:
            total = state.order_totals.get('total', 0)
            currency = state.order_totals.get('currency', 'KES')
        
        # Check for confirmation keywords
        confirmation_keywords = ['yes', 'confirm', 'proceed', 'ok', 'sure', 'correct']
        is_confirming = any(keyword in message_lower for keyword in confirmation_keywords)
        
        # If amount not confirmed yet, ask for confirmation
        if not amount_confirmed:
            return {
                "action": "confirm_amount",
                "selected_method": None,
                "amount_confirmed": False,
                "confirmation_message": f"Please confirm: You will pay {currency} {total:,.0f}. Is this correct?",
                "next_step": "Wait for customer confirmation",
                "reasoning": "Amount confirmation required before payment"
            }
        
        # Amount is confirmed, check for method selection
        available_methods = getattr(state, 'available_payment_methods', [])
        
        if not available_methods:
            return {
                "action": "clarify",
                "selected_method": None,
                "amount_confirmed": True,
                "confirmation_message": "No payment methods are currently available. Please contact support.",
                "next_step": "Escalate to support",
                "reasoning": "No payment methods available"
            }
        
        # Check for method selection in message
        if 'stk' in message_lower or 'push' in message_lower or '1' in message_lower:
            # Check if STK is available
            stk_available = any(m.get('type') == 'mpesa_stk' for m in available_methods)
            if stk_available:
                return {
                    "action": "initiate_stk",
                    "selected_method": "mpesa_stk",
                    "amount_confirmed": True,
                    "confirmation_message": f"Initiating M-PESA STK Push for {currency} {total:,.0f}. Please check your phone...",
                    "next_step": "Initiate STK push payment",
                    "reasoning": "Customer selected STK push method"
                }
        
        if 'c2b' in message_lower or 'paybill' in message_lower or '2' in message_lower:
            # Check if C2B is available
            c2b_available = any(m.get('type') == 'mpesa_c2b' for m in available_methods)
            if c2b_available:
                return {
                    "action": "initiate_c2b",
                    "selected_method": "mpesa_c2b",
                    "amount_confirmed": True,
                    "confirmation_message": f"Generating M-PESA C2B payment instructions for {currency} {total:,.0f}...",
                    "next_step": "Provide C2B payment instructions",
                    "reasoning": "Customer selected C2B method"
                }
        
        if 'card' in message_lower or 'pesapal' in message_lower or '3' in message_lower:
            # Check if card is available
            card_available = any(m.get('type') == 'card' for m in available_methods)
            if card_available:
                return {
                    "action": "initiate_card",
                    "selected_method": "card",
                    "amount_confirmed": True,
                    "confirmation_message": f"Creating secure card payment link for {currency} {total:,.0f}...",
                    "next_step": "Create PesaPal checkout",
                    "reasoning": "Customer selected card payment"
                }
        
        # If only one method available, recommend it
        if len(available_methods) == 1:
            method = available_methods[0]
            method_type = method.get('type', 'unknown')
            method_name = method.get('name', 'Payment')
            
            if method_type == 'mpesa_stk':
                action = "initiate_stk"
                selected = "mpesa_stk"
            elif method_type == 'mpesa_c2b':
                action = "initiate_c2b"
                selected = "mpesa_c2b"
            elif method_type == 'card':
                action = "initiate_card"
                selected = "card"
            else:
                action = "clarify"
                selected = None
            
            return {
                "action": action,
                "selected_method": selected,
                "amount_confirmed": True,
                "confirmation_message": f"Processing payment via {method_name} for {currency} {total:,.0f}...",
                "next_step": f"Initiate {method_name} payment",
                "reasoning": "Only one payment method available"
            }
        
        # Multiple methods available - ask for selection
        return {
            "action": "select_method",
            "selected_method": None,
            "amount_confirmed": True,
            "confirmation_message": "Please select your preferred payment method by replying with the number (1, 2, or 3).",
            "next_step": "Wait for method selection",
            "reasoning": "Multiple payment methods available - need customer selection"
        }
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from payment routing result.
        
        Args:
            state: Current conversation state
            result: LLM routing result
            
        Returns:
            Updated conversation state
        """
        action = result["action"]
        
        # Update amount confirmation status
        state.payment_amount_confirmed = result.get("amount_confirmed", False)
        
        # Update selected payment method
        if result.get("selected_method"):
            state.selected_payment_method = result["selected_method"]
        
        # Set response text
        state.response_text = result.get("confirmation_message", "Processing your payment...")
        
        # Update payment step based on action
        if action == "confirm_amount":
            state.payment_step = "awaiting_amount_confirmation"
        elif action == "select_method":
            state.payment_step = "awaiting_method_selection"
        elif action in ["initiate_stk", "initiate_c2b", "initiate_card"]:
            state.payment_step = f"initiate_{result.get('selected_method', 'unknown')}"
        else:
            state.payment_step = "clarification_needed"
        
        logger.info(
            f"Payment routing: {action}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "action": action,
                "selected_method": result.get("selected_method"),
                "amount_confirmed": result.get("amount_confirmed", False),
                "reasoning": result.get("reasoning", "")
            }
        )
        
        return state
