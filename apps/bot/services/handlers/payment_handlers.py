"""
Payment help handlers for the sales orchestration refactor.

These handlers implement deterministic payment flow logic without LLMs.
"""
from typing import Dict, Any
from django.utils import timezone

from apps.bot.services.business_logic_router import BotAction
from apps.bot.services.intent_detection_engine import IntentResult
from apps.bot.models import ConversationContext
from apps.tenants.models import Tenant, Customer
from apps.orders.models import Order
from apps.bot.services.payment_orchestration_service import PaymentOrchestrationService


def handle_payment_help(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle payment help intent.
    Ask for payment method selection.
    
    Requirements: 7.3, 7.4
    """
    # Get order from context
    order_id = context.get_entity('order_id')
    
    if not order_id:
        return BotAction(
            type="TEXT",
            text="Please create an order first before selecting a payment method.",
            new_context={
                'current_flow': 'browsing_products',
                'awaiting_response': False,
            }
        )
    
    # Validate order exists
    try:
        order = Order.objects.get(
            id=order_id,
            tenant=tenant,
            customer=customer
        )
    except Order.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Order not found. Please create a new order.",
            new_context={
                'current_flow': 'browsing_products',
                'awaiting_response': False,
            }
        )
    
    # Check if order is already paid
    if order.status == 'paid':
        return BotAction(
            type="TEXT",
            text="This order has already been paid. Thank you!",
            new_context={
                'current_flow': '',
                'awaiting_response': False,
            }
        )
    
    # Format payment options message
    text = _format_payment_options(order, intent_result.language)
    
    # Build payment method buttons
    buttons = []
    
    # Check tenant configuration for enabled payment methods
    config = getattr(tenant, 'agent_configuration', None)
    
    if config and config.enable_mpesa_stk:
        buttons.append({'id': 'pay_mpesa_stk', 'title': 'M-Pesa STK'})
    
    buttons.append({'id': 'pay_mpesa_manual', 'title': 'M-Pesa Manual'})
    
    if config and config.enable_card_payments:
        buttons.append({'id': 'pay_card', 'title': 'Card Payment'})
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': buttons
        },
        new_context={
            'current_flow': 'payment',
            'awaiting_response': True,
            'last_question': 'payment_method_selection',
            'entities': {
                'order_id': str(order.id),
                'total': float(order.total),
                'currency': order.currency,
            }
        },
        side_effects=['payment_help_requested']
    )


def handle_mpesa_stk_payment(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle M-Pesa STK push payment.
    
    Requirements: 8.1, 8.2, 8.3
    """
    # Get order from context
    order_id = context.get_entity('order_id')
    
    if not order_id:
        return BotAction(
            type="TEXT",
            text="Please create an order first.",
            new_context={'current_flow': 'browsing_products'}
        )
    
    # Get order
    try:
        order = Order.objects.get(id=order_id, tenant=tenant, customer=customer)
    except Order.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Order not found.",
            new_context={'current_flow': 'browsing_products'}
        )
    
    # Get phone number from slots or ask
    phone_number = intent_result.slots.get('phone_number')
    
    if not phone_number:
        # Ask for phone number (Requirement 8.1)
        text = _format_phone_request(order, intent_result.language)
        return BotAction(
            type="TEXT",
            text=text,
            new_context={
                'current_flow': 'payment',
                'awaiting_response': True,
                'last_question': 'mpesa_phone_number',
                'entities': {
                    'order_id': str(order.id),
                    'payment_method': 'mpesa_stk',
                }
            }
        )
    
    # Initiate STK push (Requirement 8.2, 8.3)
    try:
        payment_service = PaymentOrchestrationService()
        payment_request = payment_service.initiate_mpesa_stk(
            order=order,
            phone_number=phone_number,
            tenant=tenant
        )
        
        text = _format_stk_initiated(order, phone_number, intent_result.language)
        
        return BotAction(
            type="TEXT",
            text=text,
            new_context={
                'current_flow': 'payment_pending',
                'awaiting_response': False,
                'entities': {
                    'order_id': str(order.id),
                    'payment_request_id': str(payment_request.id),
                }
            },
            side_effects=['mpesa_stk_initiated']
        )
        
    except Exception as e:
        return BotAction(
            type="TEXT",
            text=f"Sorry, we couldn't initiate the payment. Please try again or use a different payment method. Error: {str(e)}",
            new_context={
                'current_flow': 'payment',
                'awaiting_response': True,
                'last_question': 'payment_method_selection',
            },
            side_effects=['mpesa_stk_failed']
        )


def handle_mpesa_manual_payment(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle M-Pesa manual payment (Paybill/Till).
    
    Requirements: 7.3, 7.4
    """
    # Get order from context
    order_id = context.get_entity('order_id')
    
    if not order_id:
        return BotAction(
            type="TEXT",
            text="Please create an order first.",
            new_context={'current_flow': 'browsing_products'}
        )
    
    # Get order
    try:
        order = Order.objects.get(id=order_id, tenant=tenant, customer=customer)
    except Order.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Order not found.",
            new_context={'current_flow': 'browsing_products'}
        )
    
    # Get tenant M-Pesa details from settings
    tenant_settings = getattr(tenant, 'settings', None)
    paybill = getattr(tenant_settings, 'mpesa_paybill', None) if tenant_settings else None
    till = getattr(tenant_settings, 'mpesa_till', None) if tenant_settings else None
    
    # Format manual payment instructions
    text = _format_manual_payment_instructions(
        order=order,
        paybill=paybill,
        till=till,
        language=intent_result.language
    )
    
    return BotAction(
        type="TEXT",
        text=text,
        new_context={
            'current_flow': 'payment_pending',
            'awaiting_response': False,
            'entities': {
                'order_id': str(order.id),
                'payment_method': 'mpesa_manual',
            }
        },
        side_effects=['mpesa_manual_instructions_sent']
    )


def handle_card_payment(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle card payment.
    
    Requirements: 9.1, 9.2, 9.3
    """
    # Get order from context
    order_id = context.get_entity('order_id')
    
    if not order_id:
        return BotAction(
            type="TEXT",
            text="Please create an order first.",
            new_context={'current_flow': 'browsing_products'}
        )
    
    # Get order
    try:
        order = Order.objects.get(id=order_id, tenant=tenant, customer=customer)
    except Order.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Order not found.",
            new_context={'current_flow': 'browsing_products'}
        )
    
    # Determine provider (default to paystack)
    provider = 'paystack'
    
    # Generate payment link (Requirement 9.1, 9.2)
    try:
        payment_service = PaymentOrchestrationService()
        payment_request, payment_link = payment_service.initiate_card_payment(
            order=order,
            provider=provider,
            tenant=tenant
        )
        
        # Format message with payment link (Requirement 9.3)
        text = _format_card_payment_link(order, payment_link, intent_result.language)
        
        return BotAction(
            type="TEXT",
            text=text,
            new_context={
                'current_flow': 'payment_pending',
                'awaiting_response': False,
                'entities': {
                    'order_id': str(order.id),
                    'payment_request_id': str(payment_request.id),
                    'payment_link': payment_link,
                }
            },
            side_effects=['card_payment_link_sent']
        )
        
    except Exception as e:
        return BotAction(
            type="TEXT",
            text=f"Sorry, we couldn't generate the payment link. Please try again or use a different payment method. Error: {str(e)}",
            new_context={
                'current_flow': 'payment',
                'awaiting_response': True,
                'last_question': 'payment_method_selection',
            },
            side_effects=['card_payment_failed']
        )


# Helper functions for message formatting

def _format_payment_options(order: Order, language: list) -> str:
    """Format payment options message."""
    if 'sw' in language or 'sheng' in language:
        return f"""💳 Chagua Njia ya Malipo

📋 Order #{order.id}
💰 Jumla: {order.currency} {order.total}

Chagua jinsi unataka kulipa:"""
    
    return f"""💳 Choose Payment Method

📋 Order #{order.id}
💰 Total: {order.currency} {order.total}

How would you like to pay?"""


def _format_phone_request(order: Order, language: list) -> str:
    """Format phone number request message."""
    if 'sw' in language or 'sheng' in language:
        return f"""📱 Tafadhali weka namba ya simu ya M-Pesa

💰 Jumla: {order.currency} {order.total}

Mfano: 0712345678 au +254712345678"""
    
    return f"""📱 Please enter your M-Pesa phone number

💰 Total: {order.currency} {order.total}

Example: 0712345678 or +254712345678"""


def _format_stk_initiated(order: Order, phone_number: str, language: list) -> str:
    """Format STK push initiated message."""
    if 'sw' in language or 'sheng' in language:
        return f"""✅ STK Push Imetumwa!

📱 Angalia simu yako {phone_number}
💰 Jumla: {order.currency} {order.total}

Weka PIN yako ya M-Pesa kukamilisha malipo."""
    
    return f"""✅ STK Push Sent!

📱 Check your phone {phone_number}
💰 Total: {order.currency} {order.total}

Enter your M-Pesa PIN to complete the payment."""


def _format_manual_payment_instructions(
    order: Order,
    paybill: str,
    till: str,
    language: list
) -> str:
    """Format manual M-Pesa payment instructions."""
    if 'sw' in language or 'sheng' in language:
        instructions = f"""💳 Maelekezo ya Malipo ya M-Pesa

📋 Order #{order.id}
💰 Jumla: {order.currency} {order.total}

"""
        if paybill:
            instructions += f"""📞 Paybill: {paybill}
📝 Account: {order.id}

"""
        elif till:
            instructions += f"""📞 Till Number: {till}

"""
        
        instructions += """Baada ya kulipa, tutakupelekea confirmation."""
        return instructions
    
    instructions = f"""💳 M-Pesa Payment Instructions

📋 Order #{order.id}
💰 Total: {order.currency} {order.total}

"""
    if paybill:
        instructions += f"""📞 Paybill: {paybill}
📝 Account: {order.id}

"""
    elif till:
        instructions += f"""📞 Till Number: {till}

"""
    
    instructions += """After payment, we'll send you a confirmation."""
    return instructions


def _format_card_payment_link(order: Order, payment_link: str, language: list) -> str:
    """Format card payment link message."""
    if 'sw' in language or 'sheng' in language:
        return f"""💳 Lipa kwa Kadi

📋 Order #{order.id}
💰 Jumla: {order.currency} {order.total}

Bonyeza link hii kulipa:
{payment_link}

Tutakupelekea confirmation baada ya malipo."""
    
    return f"""💳 Pay with Card

📋 Order #{order.id}
💰 Total: {order.currency} {order.total}

Click this link to pay:
{payment_link}

We'll send you a confirmation after payment."""
