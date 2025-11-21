"""
Status checking handlers for the sales orchestration refactor.

These handlers implement deterministic status checking logic without LLMs.
"""
from typing import Dict, Any
from django.utils import timezone

from apps.orders.models import Order
from apps.services.models import Appointment
from apps.bot.services.business_logic_router import BotAction
from apps.bot.services.intent_detection_engine import IntentResult
from apps.bot.models import ConversationContext
from apps.tenants.models import Tenant, Customer


def handle_check_order_status(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle order status check.
    NO LLM calls.
    
    Requirements: 11.1, 11.2, 11.3
    """
    # Query orders for customer (tenant-scoped)
    orders = Order.objects.filter(
        tenant=tenant,
        customer=customer
    ).order_by('-created_at')[:5]
    
    if not orders.exists():
        # No orders found (Requirement 11.5)
        text = _format_no_orders(intent_result.language)
        return BotAction(
            type="BUTTONS",
            text=text,
            rich_payload={
                'buttons': [
                    {'id': 'browse_products', 'title': 'Browse Products'},
                    {'id': 'request_human', 'title': 'Talk to Someone'},
                ]
            },
            new_context={
                'current_flow': '',
                'awaiting_response': False,
            }
        )
    
    # Display most recent order (Requirement 11.2)
    most_recent = orders[0]
    text = _format_order_status(most_recent, intent_result.language)
    
    return BotAction(
        type="TEXT",
        text=text,
        new_context={
            'current_flow': 'checking_order',
            'awaiting_response': False,
            'entities': {
                'order_id': str(most_recent.id),
            }
        },
        side_effects=['order_status_checked']
    )


def handle_check_appointment_status(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle appointment status check.
    NO LLM calls.
    
    Requirements: 11.3, 11.4, 11.5
    """
    # Query upcoming appointments for customer (tenant-scoped)
    appointments = Appointment.objects.filter(
        tenant=tenant,
        customer=customer,
        start_dt__gte=timezone.now()
    ).order_by('start_dt')[:5]
    
    if not appointments.exists():
        # No appointments found (Requirement 11.5)
        text = _format_no_appointments(intent_result.language)
        return BotAction(
            type="BUTTONS",
            text=text,
            rich_payload={
                'buttons': [
                    {'id': 'browse_services', 'title': 'Browse Services'},
                    {'id': 'request_human', 'title': 'Talk to Someone'},
                ]
            },
            new_context={
                'current_flow': '',
                'awaiting_response': False,
            }
        )
    
    # Display upcoming appointments (Requirement 11.4)
    text = _format_appointments_status(appointments, intent_result.language)
    
    return BotAction(
        type="TEXT",
        text=text,
        new_context={
            'current_flow': 'checking_appointment',
            'awaiting_response': False,
        },
        side_effects=['appointment_status_checked']
    )


def _format_no_orders(language: list) -> str:
    """Format message when no orders found."""
    if 'sw' in language or 'sheng' in language:
        return """📦 Hauna Orders

Bado haujawahi kuorder chochote. Unataka kuona bidhaa zetu?"""
    
    return """📦 No Orders Found

You haven't placed any orders yet. Would you like to browse our products?"""


def _format_no_appointments(language: list) -> str:
    """Format message when no appointments found."""
    if 'sw' in language or 'sheng' in language:
        return """📅 Hauna Appointments

Hauna appointments za usoni. Unataka kubook service?"""
    
    return """📅 No Appointments Found

You don't have any upcoming appointments. Would you like to book a service?"""


def _format_order_status(order: Order, language: list) -> str:
    """Format order status message."""
    status_emoji = {
        'draft': '📝',
        'placed': '📦',
        'paid': '✅',
        'fulfilled': '🚚',
        'canceled': '❌',
    }
    
    emoji = status_emoji.get(order.status, '📦')
    
    # Format items
    items_text = []
    for item in order.items[:3]:  # Show first 3 items
        items_text.append(f"  • {item.get('product_name', 'Item')} x{item.get('quantity', 1)}")
    
    if len(order.items) > 3:
        items_text.append(f"  • ... and {len(order.items) - 3} more")
    
    items_str = "\n".join(items_text)
    
    if 'sw' in language or 'sheng' in language:
        status_names = {
            'draft': 'Draft',
            'placed': 'Imewekwa',
            'paid': 'Imelipwa',
            'fulfilled': 'Imetumwa',
            'canceled': 'Imefutwa',
        }
        status_name = status_names.get(order.status, order.status)
        
        return f"""{emoji} Order Status

📋 Order #{order.id}
📊 Status: {status_name}
💰 Jumla: {order.currency} {order.total}

📦 Items:
{items_str}

📅 Tarehe: {order.created_at.strftime('%B %d, %Y')}"""
    
    return f"""{emoji} Order Status

📋 Order #{order.id}
📊 Status: {order.status.title()}
💰 Total: {order.currency} {order.total}

📦 Items:
{items_str}

📅 Date: {order.created_at.strftime('%B %d, %Y')}"""


def _format_appointments_status(appointments, language: list) -> str:
    """Format appointments status message."""
    status_emoji = {
        'pending': '⏳',
        'confirmed': '✅',
        'done': '✔️',
        'canceled': '❌',
        'no_show': '❌',
    }
    
    if 'sw' in language or 'sheng' in language:
        lines = ["📅 Appointments Zako za Usoni\n"]
        
        for apt in appointments:
            emoji = status_emoji.get(apt.status, '📅')
            status_names = {
                'pending': 'Inasubiri',
                'confirmed': 'Confirmed',
                'done': 'Imekamilika',
                'canceled': 'Imefutwa',
                'no_show': 'Hukuonekana',
            }
            status_name = status_names.get(apt.status, apt.status)
            
            lines.append(f"""{emoji} {apt.service.title}
📅 {apt.start_dt.strftime('%B %d, %Y')}
🕐 {apt.start_dt.strftime('%I:%M %p')}
📊 {status_name}
""")
        
        return "\n".join(lines)
    
    lines = ["📅 Your Upcoming Appointments\n"]
    
    for apt in appointments:
        emoji = status_emoji.get(apt.status, '📅')
        
        lines.append(f"""{emoji} {apt.service.title}
📅 {apt.start_dt.strftime('%B %d, %Y')}
🕐 {apt.start_dt.strftime('%I:%M %p')}
📊 {apt.status.title()}
""")
    
    return "\n".join(lines)
