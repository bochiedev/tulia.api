"""
Business Logic Router for the sales orchestration refactor.

This service maps intents to deterministic handler functions that execute
business logic without using LLMs.

Design principles:
- Deterministic routing (no LLM calls)
- Pure Python business logic
- Database queries only
- Structured BotAction outputs
- Graceful error handling
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
import logging

from apps.messaging.models import Conversation
from apps.bot.models import ConversationContext
from apps.bot.services.intent_detection_engine import Intent, IntentResult
from apps.tenants.models import Tenant, Customer

logger = logging.getLogger(__name__)


@dataclass
class BotAction:
    """Structured output from business logic handlers."""
    type: str  # "TEXT", "LIST", "BUTTONS", "PRODUCT_CARDS", "HANDOFF"
    text: Optional[str] = None
    rich_payload: Optional[Dict[str, Any]] = None
    new_context: Optional[Dict[str, Any]] = None
    side_effects: List[str] = field(default_factory=list)  # ["order_created", "payment_initiated"]


class BusinessLogicRouter:
    """
    Route intents to deterministic handler functions.
    
    Maps each intent to a handler function that:
    - Queries database directly (tenant-scoped)
    - Returns structured BotAction
    - Updates ConversationContext
    - Handles errors gracefully
    
    NO LLM calls inside handlers.
    """
    
    def __init__(self):
        """Initialize the business logic router."""
        # Intent-to-handler mapping
        self.INTENT_HANDLERS: Dict[Intent, Callable] = {
            Intent.GREET: self.handle_greet,
            Intent.BROWSE_PRODUCTS: self.handle_browse_products,
            Intent.BROWSE_SERVICES: self.handle_browse_services,
            Intent.PRODUCT_DETAILS: self.handle_product_details,
            Intent.SERVICE_DETAILS: self.handle_service_details,
            Intent.PLACE_ORDER: self.handle_place_order,
            Intent.BOOK_APPOINTMENT: self.handle_book_appointment,
            Intent.CHECK_ORDER_STATUS: self.handle_check_order_status,
            Intent.CHECK_APPOINTMENT_STATUS: self.handle_check_appointment_status,
            Intent.ASK_DELIVERY_FEES: self.handle_delivery_fees,
            Intent.ASK_RETURN_POLICY: self.handle_return_policy,
            Intent.PAYMENT_HELP: self.handle_payment_help,
            Intent.REQUEST_HUMAN: self.handle_request_human,
            Intent.GENERAL_FAQ: self.handle_general_faq,
            Intent.SMALL_TALK: self.handle_small_talk,
            Intent.UNKNOWN: self.handle_unknown,
        }
    
    def route(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """
        Route intent to appropriate handler.
        
        Args:
            intent_result: Detected intent with slots
            context: Conversation context
            tenant: Tenant for scoping
            customer: Customer making the request
        
        Returns:
            BotAction with response and context updates
        """
        handler = self.INTENT_HANDLERS.get(intent_result.intent)
        
        if not handler:
            logger.warning(f"No handler for intent: {intent_result.intent}")
            return self.handle_unknown(intent_result, context, tenant, customer)
        
        try:
            return handler(intent_result, context, tenant, customer)
        except Exception as e:
            logger.error(
                f"Error in handler for intent {intent_result.intent}: {str(e)}",
                exc_info=True,
                extra={
                    'tenant_id': tenant.id,
                    'customer_id': customer.id,
                    'intent': intent_result.intent.value,
                }
            )
            return self._handle_error(intent_result, context, tenant, customer, e)
    
    def _handle_error(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer,
        error: Exception
    ) -> BotAction:
        """Handle errors gracefully with fallback message."""
        return BotAction(
            type="TEXT",
            text="Sorry, I'm experiencing technical difficulties. Let me connect you with our team.",
            new_context={
                'current_flow': 'error',
                'awaiting_response': False,
            },
            side_effects=['error_occurred', 'handoff_triggered']
        )
    
    # Handler function signatures
    # These will be implemented in subsequent tasks
    
    def handle_greet(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle greeting intent."""
        from apps.bot.services.handlers.misc_handlers import handle_greet as _handle_greet
        return _handle_greet(intent_result, context, tenant, customer)
    
    def handle_browse_products(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle product browsing intent."""
        from apps.bot.services.handlers.product_handlers import handle_browse_products as _handle_browse_products
        return _handle_browse_products(intent_result, context, tenant, customer)
    
    def handle_browse_services(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle service browsing intent."""
        from apps.bot.services.handlers.service_handlers import handle_browse_services as _handle_browse_services
        return _handle_browse_services(intent_result, context, tenant, customer)
    
    def handle_product_details(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle product details intent."""
        from apps.bot.services.handlers.product_handlers import handle_product_details as _handle_product_details
        return _handle_product_details(intent_result, context, tenant, customer)
    
    def handle_service_details(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle service details intent."""
        from apps.bot.services.handlers.service_handlers import handle_service_details as _handle_service_details
        return _handle_service_details(intent_result, context, tenant, customer)
    
    def handle_place_order(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle place order intent."""
        from apps.bot.services.handlers.product_handlers import handle_place_order as _handle_place_order
        return _handle_place_order(intent_result, context, tenant, customer)
    
    def handle_book_appointment(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle appointment booking intent."""
        from apps.bot.services.handlers.service_handlers import handle_book_appointment as _handle_book_appointment
        return _handle_book_appointment(intent_result, context, tenant, customer)
    
    def handle_check_order_status(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle order status check intent."""
        from apps.bot.services.handlers.status_handlers import handle_check_order_status as _handle_check_order_status
        return _handle_check_order_status(intent_result, context, tenant, customer)
    
    def handle_check_appointment_status(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle appointment status check intent."""
        from apps.bot.services.handlers.status_handlers import handle_check_appointment_status as _handle_check_appointment_status
        return _handle_check_appointment_status(intent_result, context, tenant, customer)
    
    def handle_delivery_fees(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle delivery fees inquiry."""
        from apps.bot.services.handlers.faq_handlers import handle_delivery_fees as _handle_delivery_fees
        return _handle_delivery_fees(intent_result, context, tenant, customer)
    
    def handle_return_policy(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle return policy inquiry."""
        from apps.bot.services.handlers.faq_handlers import handle_return_policy as _handle_return_policy
        return _handle_return_policy(intent_result, context, tenant, customer)
    
    def handle_payment_help(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle payment help intent."""
        from apps.bot.services.handlers.payment_handlers import handle_payment_help as _handle_payment_help
        return _handle_payment_help(intent_result, context, tenant, customer)
    
    def handle_request_human(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle human handoff request."""
        from apps.bot.services.handlers.misc_handlers import handle_request_human as _handle_request_human
        return _handle_request_human(intent_result, context, tenant, customer)
    
    def handle_general_faq(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle general FAQ intent."""
        from apps.bot.services.handlers.faq_handlers import handle_general_faq as _handle_general_faq
        return _handle_general_faq(intent_result, context, tenant, customer)
    
    def handle_small_talk(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle small talk intent."""
        from apps.bot.services.handlers.misc_handlers import handle_small_talk as _handle_small_talk
        return _handle_small_talk(intent_result, context, tenant, customer)
    
    def handle_unknown(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """Handle unknown intent."""
        from apps.bot.services.handlers.misc_handlers import handle_unknown as _handle_unknown
        return _handle_unknown(intent_result, context, tenant, customer)
