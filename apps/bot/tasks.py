"""
Celery tasks for bot intent processing.

Handles asynchronous processing of inbound messages, intent classification,
and routing to appropriate handlers.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_inbound_message(self, message_id: str):
    """
    Process inbound message: classify intent and route to handler.
    
    Args:
        message_id: UUID of the Message to process
        
    Flow:
        1. Load message and conversation
        2. Check if handoff is active (skip bot if yes)
        3. Classify intent using IntentService
        4. Route to appropriate handler based on intent
        5. Send response via Twilio
        6. Create IntentEvent for tracking
    """
    from apps.messaging.models import Message, Conversation
    from apps.bot.services.intent_service import create_intent_service
    from apps.bot.services.product_handlers import create_product_handler
    from apps.bot.services.service_handlers import create_service_handler
    from apps.bot.services.handoff_handler import create_handoff_handler
    from apps.bot.services.consent_handlers import create_consent_handler
    from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
    
    try:
        # Load message
        message = Message.objects.select_related(
            'conversation',
            'conversation__tenant',
            'conversation__customer'
        ).get(id=message_id)
        
        conversation = message.conversation
        tenant = conversation.tenant
        
        logger.info(
            f"Processing inbound message",
            extra={
                'message_id': str(message_id),
                'conversation_id': str(conversation.id),
                'tenant_id': str(tenant.id)
            }
        )
        
        # Check if conversation is in handoff mode
        if conversation.status == 'handoff':
            logger.info(
                f"Conversation in handoff mode, skipping bot processing",
                extra={'conversation_id': str(conversation.id)}
            )
            return {
                'status': 'skipped',
                'reason': 'handoff_active'
            }
        
        # Create services
        intent_service = create_intent_service()
        twilio_service = create_twilio_service_for_tenant(tenant)
        
        # Build conversation context
        context = _build_conversation_context(conversation)
        
        # Classify intent
        classification = intent_service.classify_intent(
            message_text=message.text,
            conversation_context=context
        )
        
        # Create intent event for tracking
        intent_event = intent_service.create_intent_event(
            conversation=conversation,
            message_text=message.text,
            classification_result=classification
        )
        
        logger.info(
            f"Intent classified: {classification['intent_name']} "
            f"(confidence: {classification['confidence_score']:.2f})",
            extra={
                'intent': classification['intent_name'],
                'confidence': classification['confidence_score'],
                'intent_event_id': str(intent_event.id)
            }
        )
        
        # Handle low confidence
        if intent_service.is_low_confidence(classification['confidence_score']):
            low_confidence_count = getattr(conversation, 'low_confidence_count', 0)
            
            action = intent_service.handle_low_confidence(
                conversation=conversation,
                message_text=message.text,
                confidence_score=classification['confidence_score'],
                attempt_count=low_confidence_count
            )
            
            if action['action'] == 'handoff':
                # Auto-handoff triggered
                handoff_handler = create_handoff_handler(tenant, conversation, twilio_service)
                response = handoff_handler.handle_automatic_handoff(low_confidence_count)
                handoff_handler.send_response(response)
                
                return {
                    'status': 'handoff',
                    'reason': 'low_confidence',
                    'attempt_count': low_confidence_count
                }
            
            else:
                # Ask for clarification
                twilio_service.send_whatsapp(
                    to=conversation.customer.phone_e164,
                    body=action['message']
                )
                
                return {
                    'status': 'clarification_requested',
                    'attempt_count': low_confidence_count
                }
        
        # Route to appropriate handler based on intent
        intent_name = classification['intent_name']
        slots = classification['slots']
        
        response = None
        
        # Product intents
        if intent_name in intent_service.PRODUCT_INTENTS:
            handler = create_product_handler(tenant, conversation, twilio_service)
            response = _handle_product_intent(handler, intent_name, slots)
        
        # Service intents
        elif intent_name in intent_service.SERVICE_INTENTS:
            handler = create_service_handler(tenant, conversation, twilio_service)
            response = _handle_service_intent(handler, intent_name, slots)
        
        # Consent intents
        elif intent_name in intent_service.CONSENT_INTENTS:
            handler = create_consent_handler(tenant, conversation, twilio_service)
            response = _handle_consent_intent(handler, intent_name, slots)
        
        # Support intents
        elif intent_name in intent_service.SUPPORT_INTENTS:
            if intent_name == 'HUMAN_HANDOFF':
                handler = create_handoff_handler(tenant, conversation, twilio_service)
                response = handler.handle_human_handoff(slots, reason='customer_requested')
            else:
                # OTHER intent - generic fallback
                response = {
                    'message': "I'm not sure how to help with that. You can:\n"
                               "• Browse products\n"
                               "• Book appointments\n"
                               "• Ask for human assistance",
                    'action': 'send'
                }
        
        # Send response
        if response and response.get('action') == 'send':
            twilio_service.send_whatsapp(
                to=conversation.customer.phone_e164,
                body=response['message']
            )
            
            logger.info(
                f"Response sent successfully",
                extra={
                    'conversation_id': str(conversation.id),
                    'intent': intent_name
                }
            )
        
        return {
            'status': 'success',
            'intent': intent_name,
            'confidence': classification['confidence_score']
        }
    
    except Message.DoesNotExist:
        logger.error(f"Message not found: {message_id}")
        return {
            'status': 'error',
            'error': 'message_not_found'
        }
    
    except Exception as e:
        logger.error(
            f"Error processing inbound message",
            extra={'message_id': str(message_id)},
            exc_info=True
        )
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for message processing",
                extra={'message_id': str(message_id)}
            )
            return {
                'status': 'failed',
                'error': str(e)
            }


def _build_conversation_context(conversation) -> dict:
    """Build context for intent classification."""
    from apps.bot.models import IntentEvent
    
    context = {}
    
    # Get last intent
    last_intent_event = IntentEvent.objects.filter(
        conversation=conversation
    ).order_by('-created_at').first()
    
    if last_intent_event:
        context['last_intent'] = last_intent_event.intent_name
    
    # Add customer name if available
    if hasattr(conversation.customer, 'name') and conversation.customer.name:
        context['customer_name'] = conversation.customer.name
    
    return context


def _handle_product_intent(handler, intent_name: str, slots: dict) -> dict:
    """Route product intent to appropriate handler method."""
    intent_method_map = {
        'GREETING': 'handle_greeting',
        'BROWSE_PRODUCTS': 'handle_browse_products',
        'PRODUCT_DETAILS': 'handle_product_details',
        'PRICE_CHECK': 'handle_price_check',
        'STOCK_CHECK': 'handle_stock_check',
        'ADD_TO_CART': 'handle_add_to_cart',
        'CHECKOUT_LINK': 'handle_checkout_link',
    }
    
    method_name = intent_method_map.get(intent_name)
    if method_name and hasattr(handler, method_name):
        method = getattr(handler, method_name)
        return method(slots)
    
    return {
        'message': "I can help you browse products, check prices, or complete your order.",
        'action': 'send'
    }


def _handle_service_intent(handler, intent_name: str, slots: dict) -> dict:
    """Route service intent to appropriate handler method."""
    intent_method_map = {
        'BROWSE_SERVICES': 'handle_browse_services',
        'SERVICE_DETAILS': 'handle_service_details',
        'CHECK_AVAILABILITY': 'handle_check_availability',
        'BOOK_APPOINTMENT': 'handle_book_appointment',
        'RESCHEDULE_APPOINTMENT': 'handle_reschedule_appointment',
        'CANCEL_APPOINTMENT': 'handle_cancel_appointment',
    }
    
    method_name = intent_method_map.get(intent_name)
    if method_name and hasattr(handler, method_name):
        method = getattr(handler, method_name)
        return method(slots)
    
    return {
        'message': "I can help you browse services, check availability, or book appointments.",
        'action': 'send'
    }


def _handle_consent_intent(handler, intent_name: str, slots: dict) -> dict:
    """Route consent intent to appropriate handler method."""
    intent_method_map = {
        'OPT_IN_PROMOTIONS': 'handle_opt_in_promotions',
        'OPT_OUT_PROMOTIONS': 'handle_opt_out_promotions',
        'STOP_ALL': 'handle_stop_all',
        'START_ALL': 'handle_start_all',
    }
    
    method_name = intent_method_map.get(intent_name)
    if method_name and hasattr(handler, method_name):
        method = getattr(handler, method_name)
        return method(slots)
    
    return {
        'message': "I can help you manage your message preferences.",
        'action': 'send'
    }
