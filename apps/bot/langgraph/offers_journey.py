"""
Offers Journey subgraph implementation for LangGraph orchestration.

This module implements the complete offers and coupons journey workflow:
- offers_get_applicable tool integration
- offers_answer LLM node for explaining offers without invention
- order_apply_coupon tool for coupon application
- Integration with payment flow for discounted orders
"""
import logging
from typing import Dict, Any, Optional, List
import json

from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.nodes import LLMNode
from apps.bot.services.llm_router import LLMRouter
from apps.bot.tools.registry import get_tool

logger = logging.getLogger(__name__)


class OffersAnswerNode(LLMNode):
    """
    Offers answer node with strict grounding to tool output.
    
    Explains applicable offers clearly and briefly using only tool output.
    Never invents offers or discount information.
    """
    
    def __init__(self):
        """Initialize offers answer node."""
        system_prompt = """You are a helpful assistant that explains available offers and discounts to customers.

STRICT GROUNDING RULES:
- You MUST only use information from the provided offers data
- You MUST NOT invent, assume, or hallucinate any offers, discounts, or coupon codes
- If no offers are available, clearly state that
- You MUST be accurate about discount amounts, terms, and conditions
- You MUST cite the exact offer names and details provided

RESPONSE GUIDELINES:
- Explain offers clearly and briefly in conversational language
- Use natural, friendly tone appropriate for WhatsApp
- Keep responses concise but informative
- Include relevant details like discount amounts and terms
- If customer asked for a coupon code, prompt them to share the code or confirm applying the best eligible offer
- Present offers in order of value to customer (best deals first)

OFFER PRESENTATION:
- List each applicable offer with clear benefits
- Include discount percentage or amount
- Mention any terms or conditions briefly
- Use bullet points or numbered lists for multiple offers
- End with clear next steps for the customer

COUPON CODE HANDLING:
- If customer mentions a specific coupon code, ask them to share it
- If customer asks about codes in general, explain available offers instead
- Offer to apply the best available discount automatically

You respond with natural language text only. No JSON or structured output."""
        
        super().__init__("offers_answer", system_prompt)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for offers answer generation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"User message: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Customer ID: {state.customer_id}"
        ]
        
        # Add offers data if available
        if hasattr(state, 'available_offers') and state.available_offers:
            context_parts.append("\nAVAILABLE OFFERS:")
            offers_json = json.dumps(state.available_offers, indent=2)
            context_parts.append(offers_json)
        else:
            context_parts.append("\nAVAILABLE OFFERS: No applicable offers found")
        
        # Add order context if available
        if state.order_id:
            context_parts.append(f"\nOrder ID: {state.order_id}")
            if state.order_totals:
                context_parts.append(f"Order total: KES {state.order_totals.get('total', 0)}")
        
        # Add conversation context
        if state.turn_count > 1:
            context_parts.append(f"\nConversation turn: {state.turn_count}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for offers answer generation.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Offers answer result
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                return {
                    "answer": "I'm having trouble accessing our offers system right now. Please try again in a moment, or I can help you proceed with your order at the current price.",
                    "needs_coupon_application": False
                }
            
            # Get provider for text generation
            provider_name, model_name = llm_router._select_model('offers_answer')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make LLM call for natural language response
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=300,
                temperature=0.3  # Slightly higher for natural conversation
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'offers_answer', response.input_tokens)
            
            # Analyze response for coupon application needs
            answer_text = response.content.strip()
            needs_coupon = self._analyze_coupon_need(answer_text, state)
            
            return {
                "answer": answer_text,
                "needs_coupon_application": needs_coupon
            }
            
        except Exception as e:
            logger.error(
                f"Offers answer LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to simple offers presentation
            return self._generate_fallback_answer(state)
    
    def _analyze_coupon_need(self, answer_text: str, state: ConversationState) -> bool:
        """
        Analyze if the answer indicates coupon application is needed.
        
        Args:
            answer_text: Generated answer text
            state: Current conversation state
            
        Returns:
            True if coupon application is needed
        """
        # Check for coupon application phrases
        coupon_phrases = [
            "apply",
            "use this offer",
            "activate",
            "redeem",
            "get this discount",
            "claim"
        ]
        
        answer_lower = answer_text.lower()
        for phrase in coupon_phrases:
            if phrase in answer_lower:
                return True
        
        # Check if user message indicates they want to apply an offer
        if state.incoming_message:
            user_message_lower = state.incoming_message.lower()
            apply_keywords = ["apply", "use", "yes", "ok", "sure", "activate", "redeem"]
            if any(keyword in user_message_lower for keyword in apply_keywords):
                return True
        
        return False
    
    def _generate_fallback_answer(self, state: ConversationState) -> Dict[str, Any]:
        """
        Generate fallback answer when LLM fails.
        
        Args:
            state: Current conversation state
            
        Returns:
            Fallback offers answer
        """
        # Check if we have offers data
        if hasattr(state, 'available_offers') and state.available_offers:
            offers = state.available_offers
            if len(offers) == 1:
                offer = offers[0]
                discount_text = f"{offer.get('discount_percent', 0)}%" if offer.get('discount_percent') else f"KES {offer.get('discount_amount', 0)}"
                answer = f"Great news! You have 1 available offer: {offer.get('name', 'Special Discount')} - {discount_text} off. Would you like me to apply this discount to your order?"
                return {
                    "answer": answer,
                    "needs_coupon_application": True
                }
            else:
                answer = f"You have {len(offers)} available offers:\n"
                for i, offer in enumerate(offers[:3], 1):  # Limit to 3 offers
                    discount_text = f"{offer.get('discount_percent', 0)}%" if offer.get('discount_percent') else f"KES {offer.get('discount_amount', 0)}"
                    answer += f"{i}. {offer.get('name', 'Special Offer')} - {discount_text} off\n"
                answer += "\nWhich offer would you like me to apply?"
                return {
                    "answer": answer,
                    "needs_coupon_application": False
                }
        else:
            return {
                "answer": "I don't see any applicable offers for your order right now. Would you like to proceed with payment, or do you have a coupon code you'd like me to try?",
                "needs_coupon_application": False
            }


async def offers_journey_entry(state: ConversationState) -> ConversationState:
    """
    Entry point for offers journey subgraph.
    
    Implements the complete offers workflow:
    1. offers_get_applicable tool
    2. offers_answer LLM node
    3. order_apply_coupon tool (if needed)
    4. Integration with payment flow
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated conversation state
    """
    logger.info(
        f"Starting offers journey for tenant {state.tenant_id}, conversation {state.conversation_id}"
    )
    
    # Step 1: Get applicable offers
    state = await _step_get_applicable_offers(state)
    if state.response_text and "error" in state.response_text.lower():
        return state
    
    # Step 2: Generate offers answer
    state = await _step_offers_answer(state)
    if state.response_text and "error" in state.response_text.lower():
        return state
    
    # Step 3: Handle coupon application if needed
    if hasattr(state, 'needs_coupon_application') and state.needs_coupon_application:
        state = await _step_apply_coupon(state)
    
    # Update journey status
    state.journey = 'offers'
    
    return state


async def _step_get_applicable_offers(state: ConversationState) -> ConversationState:
    """Get applicable offers using offers_get_applicable tool."""
    offers_tool = get_tool("offers_get_applicable")
    if not offers_tool:
        state.response_text = "I'm having trouble accessing our offers system right now. Would you like to proceed with your order at the current price?"
        return state
    
    # Determine what to check offers for
    params = {
        "tenant_id": state.tenant_id,
        "request_id": state.request_id,
        "conversation_id": state.conversation_id
    }
    
    # Add customer_id if available
    if state.customer_id:
        params["customer_id"] = state.customer_id
    
    # Add order_id if available
    if state.order_id:
        params["order_id"] = state.order_id
    
    # Execute offers tool
    try:
        offers_result = offers_tool.execute(**params)
        
        if offers_result.success and offers_result.data:
            # Store offers in state
            state.available_offers = offers_result.data.get("offers", [])
            
            # Also store automatic discounts if available
            if "automatic_discounts" in offers_result.data:
                state.automatic_discounts = offers_result.data["automatic_discounts"]
            
            logger.info(
                f"Retrieved {len(state.available_offers)} offers for tenant {state.tenant_id}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "offers_count": len(state.available_offers)
                }
            )
        else:
            # No offers available
            state.available_offers = []
            logger.info(
                f"No offers available for tenant {state.tenant_id}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id
                }
            )
    
    except Exception as e:
        logger.error(
            f"Failed to get applicable offers: {e}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id
            },
            exc_info=True
        )
        state.response_text = "I'm having trouble accessing our offers system right now. Would you like to proceed with your order at the current price?"
        return state
    
    return state


async def _step_offers_answer(state: ConversationState) -> ConversationState:
    """Generate offers answer using OffersAnswerNode."""
    offers_answer_node = OffersAnswerNode()
    
    try:
        # Execute offers answer node
        result = await offers_answer_node.execute(state)
        
        # Update state with answer
        state.response_text = result.get("answer", "I'm having trouble explaining the available offers right now.")
        state.needs_coupon_application = result.get("needs_coupon_application", False)
        
        logger.info(
            f"Generated offers answer for tenant {state.tenant_id}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "needs_coupon": state.needs_coupon_application
            }
        )
        
    except Exception as e:
        logger.error(
            f"Failed to generate offers answer: {e}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id
            },
            exc_info=True
        )
        state.response_text = "I'm having trouble explaining the available offers right now. Would you like to proceed with your order?"
    
    return state


async def _step_apply_coupon(state: ConversationState) -> ConversationState:
    """Apply coupon using order_apply_coupon tool if user wants to apply an offer."""
    if not state.order_id:
        # Can't apply coupon without an order
        state.response_text += "\n\nI need to create your order first before applying any discounts."
        return state
    
    # Check if user specified which offer to apply
    coupon_code = _extract_coupon_code(state.incoming_message or "")
    
    if not coupon_code and hasattr(state, 'available_offers') and state.available_offers:
        # Use the best available offer (first one, as they should be sorted by value)
        best_offer = state.available_offers[0]
        coupon_code = best_offer.get('code') or best_offer.get('id')
    
    if not coupon_code:
        # No specific coupon to apply
        return state
    
    # Apply coupon using tool
    coupon_tool = get_tool("order_apply_coupon")
    if not coupon_tool:
        state.response_text += "\n\nI'm having trouble applying the discount right now. Please try again in a moment."
        return state
    
    try:
        coupon_result = coupon_tool.execute(
            tenant_id=state.tenant_id,
            request_id=state.request_id,
            conversation_id=state.conversation_id,
            order_id=state.order_id,
            coupon_code=coupon_code
        )
        
        if coupon_result.success and coupon_result.data:
            # Update order totals
            state.order_totals = coupon_result.data.get("updated_totals", state.order_totals)
            
            # Add success message
            discount_amount = coupon_result.data.get("discount_applied", 0)
            state.response_text += f"\n\n✅ Discount applied! You saved KES {discount_amount}."
            
            # Update to show new total
            if state.order_totals:
                new_total = state.order_totals.get("total", 0)
                state.response_text += f" Your new total is KES {new_total}."
            
            logger.info(
                f"Applied coupon {coupon_code} to order {state.order_id}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "order_id": state.order_id,
                    "discount_amount": discount_amount
                }
            )
        else:
            # Coupon application failed
            error_msg = coupon_result.error or "The coupon could not be applied"
            state.response_text += f"\n\n❌ {error_msg}"
            
    except Exception as e:
        logger.error(
            f"Failed to apply coupon: {e}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "order_id": state.order_id,
                "coupon_code": coupon_code
            },
            exc_info=True
        )
        state.response_text += "\n\nI'm having trouble applying the discount right now. Please try again in a moment."
    
    return state


def _extract_coupon_code(message: str) -> Optional[str]:
    """
    Extract coupon code from user message.
    
    Args:
        message: User message
        
    Returns:
        Extracted coupon code or None
    """
    if not message:
        return None
    
    # Look for common coupon code patterns
    import re
    
    # Pattern 1: "code ABC123" or "coupon XYZ789"
    code_match = re.search(r'\b(?:code|coupon)\s+([A-Z0-9]{3,})\b', message.upper())
    if code_match:
        return code_match.group(1)
    
    # Pattern 2: Standalone alphanumeric codes (4+ characters, not common words)
    words = message.upper().split()
    for word in words:
        # Must be 4+ characters, alphanumeric, and not common words
        if (len(word) >= 4 and 
            word.isalnum() and 
            word not in ['HAVE', 'APPLY', 'CODE', 'COUPON', 'DISCOUNT', 'OFFER', 'SAVE', 'FREE', 'DEAL']):
            return word
    
    return None