"""
Celery tasks for sales orchestration refactor.

This module implements the new deterministic, sales-oriented message processing pipeline.

Design principles:
- Intent detection using rules first, LLM as fallback
- Deterministic business logic handlers (no LLM in handlers)
- Context-aware conversation management
- Multi-language support
- Cost-optimized LLM usage
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_inbound_message_sales(self, message_id: str):
    """
    Process inbound message using sales orchestration pipeline.
    
    Flow:
    1. Load message and conversation
    2. Check for message deduplication
    3. Load conversation context
    4. Detect intent (rules first, LLM fallback)
    5. Route to business logic handler
    6. Format response
    7. Send via Twilio
    8. Update context
    9. Log analytics
    
    Args:
        message_id: UUID of the Message to process
        
    Returns:
        Dict with processing result
    """
    from apps.messaging.models import Message
    from apps.bot.services.message_deduplication import MessageDeduplicationService, MessageLockError
    
    try:
        # Load message with related objects
        message = Message.objects.select_related(
            'conversation',
            'conversation__tenant',
            'conversation__customer'
        ).get(id=message_id)
        
        conversation = message.conversation
        tenant = conversation.tenant
        customer = conversation.customer
        
        logger.info(
            f"[Sales] Processing message: tenant={tenant.id}, "
            f"conversation={conversation.id}, message={message.id}"
        )
        
        # Check for duplicate processing
        if MessageDeduplicationService.is_duplicate(
            message_id=str(message.id),
            conversation_id=str(conversation.id),
            message_text=message.body
        ):
            logger.warning(f"[Sales] Skipping duplicate message: {message.id}")
            return {
                'status': 'skipped',
                'reason': 'duplicate',
                'message_id': str(message.id)
            }
        
        # Acquire distributed lock
        try:
            with MessageDeduplicationService.acquire_lock(
                message_id=str(message.id),
                conversation_id=str(conversation.id),
                message_text=message.body,
                worker_id=self.request.id
            ):
                # Process within lock
                return _process_sales_message(
                    message=message,
                    conversation=conversation,
                    tenant=tenant,
                    customer=customer,
                    task_instance=self
                )
        
        except MessageLockError as e:
            logger.error(f"[Sales] Failed to acquire lock: {e}")
            return {
                'status': 'failed',
                'reason': 'lock_failed',
                'message_id': str(message.id)
            }
    
    except Message.DoesNotExist:
        logger.error(f"[Sales] Message not found: {message_id}")
        return {
            'status': 'failed',
            'reason': 'message_not_found',
            'message_id': str(message_id)
        }
    
    except Exception as e:
        logger.error(f"[Sales] Error processing message: {e}", exc_info=True)
        # Retry on transient errors
        raise self.retry(exc=e, countdown=60)


def _process_sales_message(message, conversation, tenant, customer, task_instance):
    """
    Process message using sales orchestration pipeline.
    
    Args:
        message: Message instance
        conversation: Conversation instance
        tenant: Tenant instance
        customer: Customer instance
        task_instance: Celery task instance
        
    Returns:
        Dict with processing result
    """
    import time
    from apps.bot.models import ConversationContext, AgentConfiguration
    from apps.bot.services.intent_detection_engine import IntentDetectionEngine
    from apps.bot.services.business_logic_router import BusinessLogicRouter
    from apps.bot.services.conversation_context_manager import ConversationContextManager
    from apps.bot.services.whatsapp_message_formatter import WhatsAppMessageFormatter
    from apps.bot.services.business_hours_service import BusinessHoursService
    from apps.bot.services.language_service import LanguageService
    from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
    
    start_time = time.time()
    
    try:
        # Get agent configuration
        try:
            config = AgentConfiguration.objects.get(tenant=tenant)
        except AgentConfiguration.DoesNotExist:
            config = None
        
        # Check business hours and quiet hours
        hours_service = BusinessHoursService()
        
        if config and hours_service.is_within_quiet_hours(config):
            # Send quiet hours message
            language_service = LanguageService()
            language = language_service.detect_language(message.body)
            
            quiet_message = hours_service.get_quiet_hours_message(config, language)
            
            # Send message
            twilio_service = create_twilio_service_for_tenant(tenant)
            twilio_service.send_whatsapp(
                to=customer.phone_e164,
                body=quiet_message
            )
            
            logger.info(f"[Sales] Sent quiet hours message")
            
            return {
                'status': 'success',
                'action': 'quiet_hours_message',
                'message_id': str(message.id)
            }
        
        # Load or create conversation context
        context_manager = ConversationContextManager()
        context = context_manager.load_or_create(conversation)
        
        # Check if human handoff is active
        if hasattr(conversation, 'needs_human') and conversation.needs_human:
            logger.info(f"[Sales] Skipping bot - human handoff active")
            return {
                'status': 'skipped',
                'reason': 'human_handoff_active',
                'message_id': str(message.id)
            }
        
        # Detect intent
        intent_engine = IntentDetectionEngine()
        intent_result = intent_engine.detect_intent(message, context, tenant)
        
        logger.info(
            f"[Sales] Intent detected: {intent_result.intent.value}, "
            f"confidence={intent_result.confidence:.2f}, "
            f"method={intent_result.method}"
        )
        
        # Route to business logic handler
        router = BusinessLogicRouter()
        bot_action = router.route(intent_result, context, tenant, customer)
        
        logger.info(f"[Sales] Handler returned action: {bot_action.type}")
        
        # Update conversation context
        if bot_action.new_context:
            context_manager.update_from_action(context, bot_action)
        
        # Update language in context
        language_service = LanguageService()
        if intent_result.language:
            language_service.update_context_language(context, intent_result.language)
        
        # Format response
        formatter = WhatsAppMessageFormatter()
        messages = formatter.format_action(bot_action, intent_result.language)
        
        # Send messages via Twilio
        twilio_service = create_twilio_service_for_tenant(tenant)
        
        for msg in messages:
            if msg['type'] == 'text':
                twilio_service.send_whatsapp(
                    to=customer.phone_e164,
                    body=msg['body']
                )
            elif msg['type'] == 'list':
                # Send list message (Twilio format)
                twilio_service.send_whatsapp_list(
                    to=customer.phone_e164,
                    body=msg.get('body', ''),
                    button_text=msg.get('button_text', 'View'),
                    sections=msg.get('sections', [])
                )
            elif msg['type'] == 'buttons':
                # Send button message (Twilio format)
                twilio_service.send_whatsapp_buttons(
                    to=customer.phone_e164,
                    body=msg.get('body', ''),
                    buttons=msg.get('buttons', [])
                )
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"[Sales] Message processed successfully in {response_time_ms}ms: "
            f"intent={intent_result.intent.value}, action={bot_action.type}"
        )
        
        # Log analytics
        from apps.bot.services.sales_analytics_service import SalesAnalyticsService
        analytics = SalesAnalyticsService()
        analytics.log_handler_response_time(
            tenant=tenant,
            handler_name=intent_result.intent.value,
            response_time_ms=response_time_ms,
            success=True
        )
        
        return {
            'status': 'success',
            'message_id': str(message.id),
            'intent': intent_result.intent.value,
            'action_type': bot_action.type,
            'response_time_ms': response_time_ms,
            'method': intent_result.method
        }
    
    except Exception as e:
        logger.error(f"[Sales] Error in message processing: {e}", exc_info=True)
        
        # Log error
        from apps.bot.services.sales_analytics_service import SalesAnalyticsService
        analytics = SalesAnalyticsService()
        analytics.log_error(
            tenant=tenant,
            error_type='message_processing_error',
            error_message=str(e),
            context={
                'message_id': str(message.id),
                'conversation_id': str(conversation.id)
            }
        )
        
        # Send fallback message to customer
        try:
            from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
            twilio_service = create_twilio_service_for_tenant(tenant)
            
            fallback_message = (
                "I'm having trouble processing your message right now. "
                "Let me connect you with someone from our team."
            )
            
            twilio_service.send_whatsapp(
                to=customer.phone_e164,
                body=fallback_message
            )
            
            # Tag for human handoff
            conversation.needs_human = True
            conversation.save(update_fields=['needs_human'])
            
        except Exception as send_error:
            logger.error(f"[Sales] Failed to send fallback message: {send_error}")
        
        raise


__all__ = ['process_inbound_message_sales']
