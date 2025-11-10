"""
Service intent handlers for browsing services and booking appointments.

Handles customer intents related to:
- Browsing services
- Viewing service details
- Checking availability
- Booking appointments
- Rescheduling appointments
- Canceling appointments
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError
import dateparser

logger = logging.getLogger(__name__)


class ServiceHandlerError(Exception):
    """Base exception for service handler errors."""
    pass


class ServiceIntentHandler:
    """
    Handler for service-related customer intents.
    
    Processes classified intents and generates appropriate responses
    by querying services and managing bookings.
    """
    
    def __init__(self, tenant, conversation, twilio_service):
        """
        Initialize service handler.
        
        Args:
            tenant: Tenant model instance
            conversation: Conversation model instance
            twilio_service: TwilioService instance for sending messages
        """
        self.tenant = tenant
        self.conversation = conversation
        self.customer = conversation.customer
        self.twilio_service = twilio_service
    
    def handle_browse_services(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle BROWSE_SERVICES intent.
        
        Args:
            slots: Extracted slots (may include service_query for filtering)
            
        Returns:
            dict: Response with service list
        """
        from apps.services.models import Service
        
        # Get active services for tenant
        services = Service.objects.for_tenant_active(self.tenant)
        
        # Apply search filter if query provided
        query = slots.get('service_query')
        if query:
            services = services.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Limit to first 10 services
        services = services[:10]
        
        if not services.exists():
            if query:
                message = f"Sorry, I couldn't find any services matching '{query}'.\n\n"
                message += "Try browsing all services or search for something else."
            else:
                message = "We don't have any services available at the moment.\n\n"
                message += "Please check back later!"
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format service list
        if query:
            message = f"Here are services matching '{query}':\n\n"
        else:
            message = "Here are our available services:\n\n"
        
        for idx, service in enumerate(services, 1):
            message += f"{idx}. *{service.title}*\n"
            
            price = service.get_price()
            if price:
                message += f"   {service.currency} {price:.2f}\n"
            
            if service.description:
                # Truncate description to 100 chars
                desc = service.description[:100]
                if len(service.description) > 100:
                    desc += "..."
                message += f"   {desc}\n"
            
            # Show variants if available
            variants = service.variants.all()[:3]
            if variants.exists():
                message += f"   Options: "
                variant_names = [v.title for v in variants]
                message += ", ".join(variant_names)
                if service.variants.count() > 3:
                    message += f" (+{service.variants.count() - 3} more)"
                message += "\n"
            
            message += "\n"
        
        message += "Reply with a service name to see more details or check availability!"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'service_count': len(services),
                'query': query
            }
        }
    
    def handle_service_details(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle SERVICE_DETAILS intent.
        
        Args:
            slots: Extracted slots with service_query or service_id
            
        Returns:
            dict: Response with service details
        """
        from apps.services.models import Service
        
        service_id = slots.get('service_id')
        service_query = slots.get('service_query')
        
        # Find service
        if service_id:
            try:
                service = Service.objects.get(id=service_id, tenant=self.tenant)
            except Service.DoesNotExist:
                return {
                    'message': "Sorry, I couldn't find that service. Please try browsing our services.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
        elif service_query:
            services = Service.objects.for_tenant_active(self.tenant).filter(
                title__icontains=service_query
            )[:1]
            
            if not services.exists():
                return {
                    'message': f"Sorry, I couldn't find a service matching '{service_query}'.\n\nTry browsing all services or search for something else.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
            
            service = services[0]
        else:
            return {
                'message': "Which service would you like to know more about?",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format service details
        message = f"*{service.title}*\n\n"
        
        if service.description:
            message += f"{service.description}\n\n"
        
        # Show pricing
        base_price = service.get_price()
        if base_price:
            message += f"💰 Starting from: {service.currency} {base_price:.2f}\n\n"
        
        # Show variants
        variants = service.variants.all()
        if variants.exists():
            message += "*Available Options:*\n"
            for variant in variants:
                price = variant.get_price()
                price_str = f"{service.currency} {price:.2f}" if price else "Price on request"
                message += f"• {variant.title} ({variant.duration_minutes} min) - {price_str}\n"
            message += "\n"
        
        message += "Would you like to check availability and book an appointment?"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'service_id': str(service.id),
                'service_title': service.title
            }
        }
    
    def handle_check_availability(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle CHECK_AVAILABILITY intent.
        
        Args:
            slots: Extracted slots with service_id, date, time_range
            
        Returns:
            dict: Response with available slots
        """
        from apps.services.models import Service
        from apps.services.services.booking_service import BookingService
        
        service_id = slots.get('service_id')
        date_str = slots.get('date')
        time_range = slots.get('time_range', 'all')
        
        if not service_id:
            return {
                'message': "Which service would you like to check availability for?",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Get service
        try:
            service = Service.objects.get(id=service_id, tenant=self.tenant, is_active=True)
        except Service.DoesNotExist:
            return {
                'message': "Sorry, I couldn't find that service.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Parse date
        if date_str:
            parsed_date = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
            if not parsed_date:
                return {
                    'message': f"I couldn't understand the date '{date_str}'. Please try again with a format like 'tomorrow', 'next Monday', or '2025-11-15'.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
            target_date = parsed_date.date()
        else:
            # Default to tomorrow
            target_date = (timezone.now() + timedelta(days=1)).date()
        
        # Set time range
        from_dt = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        to_dt = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))
        
        # Adjust for time_range filter
        if time_range == 'morning':
            from_dt = from_dt.replace(hour=6)
            to_dt = to_dt.replace(hour=12)
        elif time_range == 'afternoon':
            from_dt = from_dt.replace(hour=12)
            to_dt = to_dt.replace(hour=18)
        elif time_range == 'evening':
            from_dt = from_dt.replace(hour=18)
            to_dt = to_dt.replace(hour=23)
        
        # Find availability
        booking_service = BookingService(self.tenant)
        try:
            slots = booking_service.find_availability(
                service_id=str(service.id),
                from_dt=from_dt,
                to_dt=to_dt
            )
        except Exception as e:
            logger.error(f"Error finding availability: {str(e)}", exc_info=True)
            return {
                'message': "Sorry, I encountered an error checking availability. Please try again.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        if not slots:
            message = f"Sorry, no availability found for {service.title} on {target_date.strftime('%B %d, %Y')}.\n\n"
            message += "Would you like to check a different date?"
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format available slots (show up to 5)
        message = f"*Available slots for {service.title}*\n"
        message += f"📅 {target_date.strftime('%A, %B %d, %Y')}\n\n"
        
        for idx, slot in enumerate(slots[:5], 1):
            start_time = slot['start_dt'].strftime('%I:%M %p')
            end_time = slot['end_dt'].strftime('%I:%M %p')
            message += f"{idx}. {start_time} - {end_time}"
            
            if slot['capacity_left'] < slot['window_capacity']:
                message += f" ({slot['capacity_left']} spots left)"
            
            message += "\n"
        
        if len(slots) > 5:
            message += f"\n...and {len(slots) - 5} more slots available\n"
        
        message += "\nReply with a time to book your appointment!"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'service_id': str(service.id),
                'date': target_date.isoformat(),
                'slot_count': len(slots)
            }
        }
    
    def handle_book_appointment(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle BOOK_APPOINTMENT intent.
        
        Args:
            slots: Extracted slots with service_id, variant_id, date, time, notes
            
        Returns:
            dict: Response with booking confirmation
        """
        from apps.services.models import Service, ServiceVariant
        from apps.services.services.booking_service import BookingService
        
        service_id = slots.get('service_id')
        variant_id = slots.get('variant_id')
        date_str = slots.get('date')
        time_str = slots.get('time')
        notes = slots.get('notes')
        
        if not service_id:
            return {
                'message': "Which service would you like to book?",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Get service
        try:
            service = Service.objects.get(id=service_id, tenant=self.tenant, is_active=True)
        except Service.DoesNotExist:
            return {
                'message': "Sorry, I couldn't find that service.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Get variant if specified
        variant = None
        if variant_id:
            try:
                variant = ServiceVariant.objects.get(id=variant_id, service=service)
            except ServiceVariant.DoesNotExist:
                return {
                    'message': "Sorry, that service option is not available.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
        
        # Parse date and time
        if not date_str or not time_str:
            return {
                'message': "Please specify both the date and time for your appointment.\n\nFor example: 'Book a haircut for tomorrow at 2pm'",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Parse datetime
        datetime_str = f"{date_str} {time_str}"
        parsed_dt = dateparser.parse(datetime_str, settings={'PREFER_DATES_FROM': 'future'})
        
        if not parsed_dt:
            return {
                'message': f"I couldn't understand the date and time '{datetime_str}'. Please try again.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Make timezone-aware
        start_dt = timezone.make_aware(parsed_dt) if timezone.is_naive(parsed_dt) else parsed_dt
        
        # Calculate end time based on duration
        duration_minutes = variant.duration_minutes if variant else 60
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        # Create appointment
        booking_service = BookingService(self.tenant)
        try:
            appointment = booking_service.create_appointment(
                customer_id=str(self.customer.id),
                service_id=str(service.id),
                start_dt=start_dt,
                end_dt=end_dt,
                variant_id=str(variant.id) if variant else None,
                notes=notes,
                status='confirmed'
            )
        except ValidationError as e:
            # Slot unavailable, propose alternatives
            alternatives = booking_service.propose_alternatives(
                service_id=str(service.id),
                requested_dt=start_dt,
                variant_id=str(variant.id) if variant else None
            )
            
            if alternatives:
                message = f"Sorry, that time slot is not available. Here are some alternatives:\n\n"
                for idx, alt in enumerate(alternatives, 1):
                    alt_time = alt['start_dt'].strftime('%A, %B %d at %I:%M %p')
                    message += f"{idx}. {alt_time}\n"
                message += "\nWould you like to book one of these times?"
            else:
                message = "Sorry, that time slot is not available and I couldn't find any alternatives nearby. Please check availability for a different date."
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response'
            }
        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}", exc_info=True)
            return {
                'message': "Sorry, I encountered an error booking your appointment. Please try again.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format confirmation
        variant_title = f" - {variant.title}" if variant else ""
        message = f"✅ *Appointment Confirmed!*\n\n"
        message += f"📋 Service: {service.title}{variant_title}\n"
        message += f"📅 Date: {start_dt.strftime('%A, %B %d, %Y')}\n"
        message += f"🕐 Time: {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
        
        if notes:
            message += f"📝 Notes: {notes}\n"
        
        message += f"\n*Appointment ID:* {appointment.id}\n\n"
        message += "We look forward to seeing you! 🎉\n\n"
        message += "You'll receive a reminder before your appointment."
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'appointment_id': str(appointment.id),
                'service_id': str(service.id),
                'start_dt': start_dt.isoformat()
            }
        }
    
    def handle_cancel_appointment(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle CANCEL_APPOINTMENT intent.
        
        Args:
            slots: Extracted slots with appointment_id or appointment reference
            
        Returns:
            dict: Response with cancellation confirmation
        """
        from apps.services.models import Appointment
        from apps.services.services.booking_service import BookingService
        
        appointment_id = slots.get('appointment_id')
        
        if not appointment_id:
            # Try to find customer's upcoming appointments
            upcoming = Appointment.objects.for_customer(self.customer).upcoming()[:5]
            
            if not upcoming.exists():
                return {
                    'message': "You don't have any upcoming appointments to cancel.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
            
            # Show appointments for selection
            message = "Which appointment would you like to cancel?\n\n"
            for idx, apt in enumerate(upcoming, 1):
                message += f"{idx}. {apt.service.title}\n"
                message += f"   {apt.start_dt.strftime('%A, %B %d at %I:%M %p')}\n\n"
            
            message += "Reply with the appointment number or ID."
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Cancel appointment
        booking_service = BookingService(self.tenant)
        try:
            appointment = booking_service.cancel_appointment(appointment_id)
        except Appointment.DoesNotExist:
            return {
                'message': "Sorry, I couldn't find that appointment.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        except ValidationError as e:
            return {
                'message': f"Sorry, I couldn't cancel that appointment: {str(e)}",
                'action': 'send',
                'message_type': 'bot_response'
            }
        except Exception as e:
            logger.error(f"Error canceling appointment: {str(e)}", exc_info=True)
            return {
                'message': "Sorry, I encountered an error canceling your appointment. Please try again.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format confirmation
        message = f"✅ *Appointment Canceled*\n\n"
        message += f"Your appointment for {appointment.service.title} on "
        message += f"{appointment.start_dt.strftime('%A, %B %d at %I:%M %p')} has been canceled.\n\n"
        message += "Feel free to book another time that works better for you!"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'appointment_id': str(appointment.id),
                'canceled_at': timezone.now().isoformat()
            }
        }
    
    def send_response(self, response: Dict[str, Any]):
        """
        Send response message via Twilio.
        
        Args:
            response: Response dict from handler
        """
        if response['action'] == 'send':
            try:
                result = self.twilio_service.send_whatsapp(
                    to=self.customer.phone_e164,
                    body=response['message']
                )
                
                # Create message record
                from apps.messaging.models import Message
                Message.objects.create(
                    conversation=self.conversation,
                    direction='out',
                    message_type=response.get('message_type', 'bot_response'),
                    text=response['message'],
                    provider_msg_id=result['sid'],
                    payload=response.get('metadata', {})
                )
                
                logger.info(
                    f"Service handler response sent",
                    extra={
                        'conversation_id': str(self.conversation.id),
                        'message_sid': result['sid']
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to send service handler response",
                    extra={'conversation_id': str(self.conversation.id)},
                    exc_info=True
                )
                raise ServiceHandlerError(f"Failed to send response: {str(e)}")


def create_service_handler(tenant, conversation, twilio_service) -> ServiceIntentHandler:
    """
    Factory function to create ServiceIntentHandler instance.
    
    Args:
        tenant: Tenant model instance
        conversation: Conversation model instance
        twilio_service: TwilioService instance
        
    Returns:
        ServiceIntentHandler: Configured handler instance
    """
    return ServiceIntentHandler(tenant, conversation, twilio_service)
