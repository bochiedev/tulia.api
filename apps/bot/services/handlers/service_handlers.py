"""
Service browsing and appointment booking handlers for the sales orchestration refactor.

These handlers implement deterministic service booking logic without LLMs.
"""
from typing import Dict, Any
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models

from apps.services.models import Service, Appointment, AvailabilityWindow
from apps.bot.services.business_logic_router import BotAction
from apps.bot.services.intent_detection_engine import IntentResult
from apps.bot.models import ConversationContext
from apps.tenants.models import Tenant, Customer


def handle_browse_services(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Show services from database.
    NO LLM calls.
    
    Requirements: 10.1
    """
    # Query database (tenant-scoped)
    services = Service.objects.filter(
        tenant=tenant,
        is_active=True,
        deleted_at__isnull=True
    )[:10]
    
    if not services.exists():
        return BotAction(
            type="TEXT",
            text="We don't have any services available at the moment. Would you like to speak with someone from our team?",
            new_context={
                'current_flow': 'empty_services',
                'awaiting_response': True,
            }
        )
    
    # Format services intro
    text = _format_services_intro(len(services), intent_result.language)
    
    # Serialize services for display
    service_list = []
    for i, service in enumerate(services, 1):
        price = service.get_price()
        service_list.append({
            'id': str(service.id),
            'position': i,
            'title': service.title,
            'price': float(price) if price else None,
            'currency': service.currency,
            'description': service.description[:100] if service.description else '',
        })
    
    return BotAction(
        type="LIST",
        text=text,
        rich_payload={
            'services': service_list
        },
        new_context={
            'last_menu': {
                'type': 'services',
                'items': [{'id': s['id'], 'position': s['position']} for s in service_list],
                'timestamp': timezone.now().isoformat(),
            },
            'last_menu_timestamp': timezone.now(),
            'current_flow': 'browsing_services',
            'awaiting_response': False,
        }
    )


def handle_service_details(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Show service details.
    NO LLM calls.
    
    Requirements: 10.2
    """
    # Get service from slots or context
    service_id = intent_result.slots.get('service_id')
    selected_item = intent_result.slots.get('selected_item')
    
    if not service_id and selected_item:
        service_id = selected_item.get('id')
    
    if not service_id:
        return BotAction(
            type="TEXT",
            text="Which service would you like to know more about?",
            new_context={
                'current_flow': 'browsing_services',
                'awaiting_response': True,
            }
        )
    
    # Query service (tenant-scoped)
    try:
        service = Service.objects.get(
            id=service_id,
            tenant=tenant,
            is_active=True,
            deleted_at__isnull=True
        )
    except Service.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Sorry, that service is no longer available.",
            new_context={'current_flow': 'browsing_services'}
        )
    
    # Format service details
    text = _format_service_details(service, intent_result.language)
    
    # Update context
    context.last_service_viewed = service
    context.save(update_fields=['last_service_viewed'])
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': f'book_{service.id}', 'title': 'Book Now'},
                {'id': 'browse_more_services', 'title': 'Browse More'},
            ]
        },
        new_context={
            'current_flow': 'service_details',
            'awaiting_response': True,
            'last_question': 'book_or_browse',
            'entities': {
                'service_id': str(service.id),
                'service_name': service.title,
            }
        }
    )


def handle_book_appointment(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle appointment booking.
    NO LLM calls.
    
    Requirements: 10.3, 10.4, 10.5
    """
    # Get service from context
    service_id = context.get_entity('service_id')
    
    if not service_id:
        return BotAction(
            type="TEXT",
            text="Please select a service first.",
            new_context={'current_flow': 'browsing_services'}
        )
    
    # Get service
    try:
        service = Service.objects.get(id=service_id, tenant=tenant, is_active=True)
    except Service.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Service not found.",
            new_context={'current_flow': 'browsing_services'}
        )
    
    # Extract date/time from slots
    date_str = intent_result.slots.get('date')
    time_str = intent_result.slots.get('time')
    
    if not date_str or not time_str:
        # Ask for date and time
        text = _format_datetime_request(service, intent_result.language)
        return BotAction(
            type="TEXT",
            text=text,
            new_context={
                'current_flow': 'booking',
                'awaiting_response': True,
                'last_question': 'appointment_datetime',
                'entities': {
                    'service_id': str(service.id),
                }
            }
        )
    
    # Parse date and time
    try:
        requested_dt = _parse_datetime(date_str, time_str)
    except ValueError:
        return BotAction(
            type="TEXT",
            text="Sorry, I couldn't understand that date/time. Please try again (e.g., 'tomorrow at 2pm').",
            new_context={
                'current_flow': 'booking',
                'awaiting_response': True,
                'last_question': 'appointment_datetime',
            }
        )
    
    # Check availability (Requirement 10.3)
    is_available, message = _check_availability(service, requested_dt, tenant)
    
    if not is_available:
        return BotAction(
            type="TEXT",
            text=message,
            new_context={
                'current_flow': 'booking',
                'awaiting_response': True,
                'last_question': 'appointment_datetime',
            }
        )
    
    # Calculate end time (assume 60 minutes if no variant)
    duration_minutes = 60
    end_dt = requested_dt + timedelta(minutes=duration_minutes)
    
    # Create appointment with PENDING_CONFIRMATION status (Requirement 10.4)
    appointment = Appointment.objects.create(
        tenant=tenant,
        customer=customer,
        service=service,
        start_dt=requested_dt,
        end_dt=end_dt,
        status='pending',
        metadata={
            'created_via': 'bot',
            'conversation_id': str(context.conversation.id),
        }
    )
    
    # Ask for confirmation (Requirement 10.5)
    text = _format_appointment_confirmation(appointment, intent_result.language)
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'confirm_appointment', 'title': 'Confirm'},
                {'id': 'cancel_appointment', 'title': 'Cancel'},
            ]
        },
        new_context={
            'current_flow': 'appointment_confirmation',
            'awaiting_response': True,
            'last_question': 'confirm_appointment',
            'entities': {
                'appointment_id': str(appointment.id),
                'service_id': str(service.id),
            }
        },
        side_effects=['appointment_created']
    )


def _format_services_intro(count: int, language: list) -> str:
    """Format introduction message for services."""
    if 'sw' in language or 'sheng' in language:
        return f"Hizi ni services zetu ({count}):"
    return f"Here are our services ({count}):"


def _format_service_details(service: Service, language: list) -> str:
    """Format service details message."""
    price = service.get_price()
    price_str = f"{service.currency} {price}" if price else "Contact us"
    
    details = [
        f"💼 {service.title}",
        f"💰 {price_str}",
    ]
    
    if service.description:
        details.append(f"\n{service.description[:200]}")
    
    if 'sw' in language or 'sheng' in language:
        details.append("\nUnataka kubook?")
    else:
        details.append("\nWould you like to book this service?")
    
    return "\n".join(details)


def _format_datetime_request(service: Service, language: list) -> str:
    """Format date/time request message."""
    if 'sw' in language or 'sheng' in language:
        return f"""📅 Chagua siku na saa ya appointment

💼 Service: {service.title}

Mfano: "kesho saa 2" au "Monday at 10am\""""
    
    return f"""📅 Choose date and time for your appointment

💼 Service: {service.title}

Example: "tomorrow at 2pm" or "Monday at 10am\""""


def _format_appointment_confirmation(appointment: Appointment, language: list) -> str:
    """Format appointment confirmation message."""
    if 'sw' in language or 'sheng' in language:
        return f"""✅ Appointment Imetengenezwa!

📋 Appointment #{appointment.id}
💼 {appointment.service.title}
📅 {appointment.start_dt.strftime('%B %d, %Y')}
🕐 {appointment.start_dt.strftime('%I:%M %p')}

Confirm appointment?"""
    
    return f"""✅ Appointment Created!

📋 Appointment #{appointment.id}
💼 {appointment.service.title}
📅 {appointment.start_dt.strftime('%B %d, %Y')}
🕐 {appointment.start_dt.strftime('%I:%M %p')}

Confirm appointment?"""


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    """Parse date and time strings into datetime."""
    # Simple parsing - can be enhanced
    now = timezone.now()
    
    # Parse date
    if 'today' in date_str.lower() or 'leo' in date_str.lower():
        target_date = now.date()
    elif 'tomorrow' in date_str.lower() or 'kesho' in date_str.lower():
        target_date = (now + timedelta(days=1)).date()
    else:
        # Try to parse as date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Invalid date format")
    
    # Parse time (simple)
    try:
        # Try HH:MM format
        time_obj = datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        # Default to 10:00 AM
        time_obj = datetime.strptime('10:00', '%H:%M').time()
    
    return timezone.make_aware(datetime.combine(target_date, time_obj))


def _check_availability(service: Service, requested_dt: datetime, tenant: Tenant) -> tuple:
    """Check if service is available at requested time."""
    # Check business hours
    config = getattr(tenant, 'agent_configuration', None)
    if config:
        start_time = config.business_hours_start
        end_time = config.business_hours_end
        
        if not (start_time <= requested_dt.time() <= end_time):
            return False, f"Sorry, we're only available between {start_time} and {end_time}."
    
    # Check for overlapping appointments
    duration = timedelta(minutes=60)
    end_dt = requested_dt + duration
    
    overlapping = Appointment.objects.overlapping(service, requested_dt, end_dt)
    
    if overlapping.exists():
        return False, "Sorry, that time slot is already booked. Please choose another time."
    
    return True, "Available"
