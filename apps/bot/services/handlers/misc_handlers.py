"""
Miscellaneous intent handlers for the sales orchestration refactor.

These handlers implement simple intent responses without LLMs.
"""
from apps.bot.services.business_logic_router import BotAction
from apps.bot.services.intent_detection_engine import IntentResult
from apps.bot.models import ConversationContext
from apps.tenants.models import Tenant, Customer


def handle_greet(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle greeting intent."""
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = f"Habari! Karibu {tenant.name}. Tunaweza kukusaidia vipi leo?"
    else:
        text = f"Hello! Welcome to {tenant.name}. How can I help you today?"
    
    return BotAction(
        type="TEXT",
        text=text,
        new_context={
            'current_flow': '',
            'awaiting_response': False,
        }
    )


def handle_small_talk(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle small talk intent."""
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = "Niko hapa kukusaidia na shopping. Unataka kuona products au services?"
    else:
        text = "I'm here to help you with your shopping. Would you like to see our products or services?"
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'browse_products', 'title': 'Products'},
                {'id': 'browse_services', 'title': 'Services'},
            ]
        },
        new_context={
            'current_flow': '',
            'awaiting_response': False,
        }
    )


def handle_request_human(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle human handoff request."""
    # Tag conversation for handoff (Requirement 17.5)
    conversation = context.conversation
    conversation.mark_handoff()
    
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = "Sawa, nitakuunganisha na mtu kutoka kwa team yetu. Watakujibu hivi karibuni."
    else:
        text = "Sure, let me connect you with someone from our team. They'll be with you shortly."
    
    return BotAction(
        type="HANDOFF",
        text=text,
        new_context={
            'current_flow': 'handoff',
            'awaiting_response': False,
        },
        side_effects=['handoff_triggered']
    )


def handle_unknown(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """Handle unknown intent."""
    if 'sw' in intent_result.language or 'sheng' in intent_result.language:
        text = "Samahani, sijaelewa vizuri. Unataka kuona products, services, au kuongea na mtu?"
    else:
        text = "I'm not sure I understand. Would you like to browse our products, services, or speak with someone from our team?"
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'browse_products', 'title': 'Products'},
                {'id': 'browse_services', 'title': 'Services'},
                {'id': 'request_human', 'title': 'Talk to Someone'},
            ]
        },
        new_context={
            'current_flow': '',
            'awaiting_response': True,
            'last_question': 'clarification_needed',
        }
    )
