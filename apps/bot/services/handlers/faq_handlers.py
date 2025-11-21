"""
FAQ and policy handlers for the sales orchestration refactor.

These handlers will integrate with RAG Pipeline (to be fully implemented).
For now, they provide basic responses.
"""
from apps.bot.services.business_logic_router import BotAction
from apps.bot.services.intent_detection_engine import IntentResult
from apps.bot.models import ConversationContext
from apps.tenants.models import Tenant, Customer


def handle_general_faq(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle general FAQ intent. TODO: Integrate with RAG Pipeline (Task 11)."""
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = "Samahani, sijui jibu la swali lako. Unataka kuongea na mtu kutoka kwa team yetu?"
    else:
        text = "I'm not sure about that. Would you like to speak with someone from our team?"
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'request_human', 'title': 'Talk to Someone'},
                {'id': 'browse_products', 'title': 'Browse Products'},
            ]
        },
        new_context={'current_flow': 'faq'}
    )


def handle_return_policy(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle return policy inquiry. TODO: Integrate with RAG Pipeline (Task 11)."""
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = "Kwa maelezo kamili kuhusu return policy, tafadhali ongea na team yetu."
    else:
        text = "For detailed information about our return policy, please speak with our team."
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'request_human', 'title': 'Talk to Someone'},
            ]
        },
        new_context={'current_flow': 'faq'}
    )


def handle_delivery_fees(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle delivery fees inquiry. TODO: Integrate with RAG Pipeline (Task 11)."""
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = "Kwa maelezo kuhusu delivery fees, tafadhali ongea na team yetu."
    else:
        text = "For information about delivery fees, please speak with our team."
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'request_human', 'title': 'Talk to Someone'},
            ]
        },
        new_context={'current_flow': 'faq'}
    )
