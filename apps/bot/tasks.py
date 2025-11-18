"""
Celery tasks for bot intent processing.

Handles asynchronous processing of inbound messages, intent classification,
and routing to appropriate handlers.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db import models

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_inbound_message(self, message_id: str):
    """
    Process inbound message using AI agent or legacy intent service.
    
    This task supports both the new AI-powered agent and the legacy intent
    classification system. The system used is determined by a feature flag
    in TenantSettings.
    
    Supports message burst detection and queueing:
    - If messages arrive within 5 seconds, they are queued
    - Queued messages are batch processed together
    - This prevents duplicate intent processing and provides coherent responses
    
    Implements request deduplication:
    - Uses distributed locks to prevent concurrent processing
    - Detects duplicate messages based on content fingerprint
    - Automatically skips messages already being processed
    
    Args:
        message_id: UUID of the Message to process
        
    Flow (AI Agent):
        1. Load message and conversation
        2. Check for duplicate processing (deduplication)
        3. Acquire distributed lock for message
        4. Check feature flag for AI agent enablement
        5. Check for message burst (rapid messages within 5 seconds)
        6. If burst detected, queue message and schedule batch processing
        7. If no burst, process message with AI agent
        8. Check if handoff is active (skip bot if yes)
        9. Build comprehensive context from multiple sources
        10. Generate response using LLM with persona and knowledge
        11. Send response via Twilio (text or rich message)
        12. Track interaction for analytics
        13. Release distributed lock
        
    Flow (Legacy):
        1-6. Same as AI Agent
        7. Classify intent using IntentService
        8. Route to appropriate handler based on intent
        9. Send response via Twilio
        10. Create IntentEvent for tracking
        11. Release distributed lock
    """
    from apps.messaging.models import Message, Conversation, MessageQueue
    from apps.bot.services.intent_service import create_intent_service
    from apps.bot.services.product_handlers import create_product_handler
    from apps.bot.services.service_handlers import create_service_handler
    from apps.bot.services.handoff_handler import create_handoff_handler
    from apps.bot.services.consent_handlers import create_consent_handler
    from apps.bot.services.multi_intent_processor import create_multi_intent_processor
    from apps.bot.services.ai_agent_service import create_ai_agent_service
    from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
    from apps.bot.services.message_deduplication import MessageDeduplicationService, MessageLockError
    from datetime import timedelta
    from django.db import transaction
    
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
        
        # Check for duplicate processing
        if MessageDeduplicationService.is_duplicate(
            message_id=str(message.id),
            conversation_id=str(conversation.id),
            message_text=message.text
        ):
            logger.warning(
                f"Skipping duplicate message processing",
                extra={
                    'message_id': str(message_id),
                    'conversation_id': str(conversation.id)
                }
            )
            return {
                'status': 'skipped',
                'reason': 'duplicate_message',
                'message_id': str(message_id)
            }
        
        # Acquire distributed lock for message processing
        try:
            with MessageDeduplicationService.acquire_lock(
                message_id=str(message.id),
                conversation_id=str(conversation.id),
                message_text=message.text,
                worker_id=self.request.id  # Celery task ID
            ):
                # Process message within lock context
                return _process_message_with_lock(
                    message=message,
                    conversation=conversation,
                    tenant=tenant,
                    task_instance=self
                )
        
        except MessageLockError as e:
            logger.error(
                f"Failed to acquire lock for message processing: {e}",
                extra={
                    'message_id': str(message_id),
                    'conversation_id': str(conversation.id)
                }
            )
            return {
                'status': 'failed',
                'reason': 'lock_acquisition_failed',
                'message_id': str(message_id),
                'error': str(e)
            }
    
    except Message.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        return {
            'status': 'failed',
            'reason': 'message_not_found',
            'message_id': str(message_id)
        }
    
    except Exception as e:
        logger.error(
            f"Error processing message {message_id}: {e}",
            exc_info=True
        )
        # Retry on transient errors
        raise self.retry(exc=e, countdown=60)


def _process_message_with_lock(message, conversation, tenant, task_instance):
    """
    Process message within distributed lock context.
    
    This function contains the actual message processing logic,
    separated out to be called within the lock context manager.
    
    Args:
        message: Message instance
        conversation: Conversation instance
        tenant: Tenant instance
        task_instance: Celery task instance for retries
        
    Returns:
        Dictionary with processing result
    """
    from apps.messaging.models import MessageQueue
    from apps.bot.services.intent_service import create_intent_service
    from apps.bot.services.product_handlers import create_product_handler
    from apps.bot.services.service_handlers import create_service_handler
    from apps.bot.services.handoff_handler import create_handoff_handler
    from apps.bot.services.consent_handlers import create_consent_handler
    from apps.bot.services.multi_intent_processor import create_multi_intent_processor
    from apps.bot.services.ai_agent_service import create_ai_agent_service
    from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
    from datetime import timedelta
    from django.db import transaction
    
    try:
        
        # Check for returning customer and restore context if needed
        from apps.bot.services.context_restoration_service import create_context_restoration_service
        
        restoration_service = create_context_restoration_service()
        is_returning, pause_type = restoration_service.detect_returning_customer(
            conversation=conversation,
            current_message=message
        )
        
        if is_returning:
            logger.info(
                f"Returning customer detected, pause_type={pause_type}",
                extra={
                    'conversation_id': str(conversation.id),
                    'pause_type': pause_type
                }
            )
            
            # Restore context
            restoration_result = restoration_service.restore_context(
                conversation=conversation,
                acknowledge=True
            )
            
            if restoration_result['restored']:
                # Generate restoration greeting
                greeting = restoration_service.generate_restoration_greeting(
                    conversation=conversation,
                    pause_type=pause_type
                )
                
                # Send greeting to customer
                from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
                twilio_service = create_twilio_service_for_tenant(tenant)
                twilio_service.send_whatsapp(
                    to=conversation.customer.phone_e164,
                    body=greeting
                )
                
                logger.info(
                    f"Context restored and greeting sent for returning customer",
                    extra={
                        'conversation_id': str(conversation.id),
                        'key_facts_count': len(restoration_result['restoration_summary']['key_facts'])
                    }
                )
        
        # Check for forgot request recovery
        from apps.bot.services.forgot_request_recovery_service import create_forgot_request_recovery_service
        
        recovery_service = create_forgot_request_recovery_service()
        forgot_detected = recovery_service.detect_forgot_request(message.text)
        
        if forgot_detected:
            logger.info(
                f"Forgot request detected, attempting recovery",
                extra={'conversation_id': str(conversation.id)}
            )
            
            # Retrieve last unanswered question
            unanswered_question = recovery_service.retrieve_last_unanswered_question(
                conversation=conversation
            )
            
            if unanswered_question:
                # Generate recovery response
                recovery_response = recovery_service.generate_recovery_response(
                    unanswered_question=unanswered_question,
                    conversation=conversation
                )
                
                # Send recovery response
                from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
                twilio_service = create_twilio_service_for_tenant(tenant)
                twilio_service.send_whatsapp(
                    to=conversation.customer.phone_e164,
                    body=recovery_response
                )
                
                # Track recovery attempt
                recovery_service.track_recovery_attempt(
                    conversation=conversation,
                    unanswered_question=unanswered_question,
                    success=True
                )
                
                logger.info(
                    f"Forgot request recovery successful, "
                    f"retrieved question from {unanswered_question['time_ago_minutes']:.1f} minutes ago",
                    extra={'conversation_id': str(conversation.id)}
                )
                
                # Now process the original unanswered question
                # Update message text to be the unanswered question for processing
                message.text = unanswered_question['text']
                message.save(update_fields=['text'])
                
            else:
                # No unanswered question found
                logger.warning(
                    f"Forgot request detected but no unanswered question found",
                    extra={'conversation_id': str(conversation.id)}
                )
                
                # Track failed recovery
                recovery_service.track_recovery_attempt(
                    conversation=conversation,
                    unanswered_question=None,
                    success=False
                )
                
                # Send apologetic response
                from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
                twilio_service = create_twilio_service_for_tenant(tenant)
                twilio_service.send_whatsapp(
                    to=conversation.customer.phone_e164,
                    body="I apologize if I missed something! Could you please remind me what you were asking about?"
                )
                
                return {
                    'status': 'recovery_failed',
                    'reason': 'no_unanswered_question_found'
                }
        
        # Check for message burst (rapid messages within 5 seconds)
        burst_detected = _detect_message_burst(message, conversation)
        
        if burst_detected:
            # Queue message for batch processing
            queued = _queue_message_for_burst(message, conversation)
            
            if queued:
                logger.info(
                    f"Message queued for burst processing",
                    extra={
                        'message_id': str(message_id),
                        'conversation_id': str(conversation.id),
                        'queue_position': queued.queue_position
                    }
                )
                
                # Schedule batch processing task (delayed by 5 seconds)
                process_message_burst.apply_async(
                    args=[str(conversation.id)],
                    countdown=5
                )
                
                return {
                    'status': 'queued',
                    'queue_position': queued.queue_position,
                    'reason': 'message_burst_detected'
                }
        
        # Check if there are already queued messages ready for batch processing
        ready_for_batch = MessageQueue.objects.ready_for_batch(
            conversation=conversation,
            delay_seconds=5
        ).exists()
        
        if ready_for_batch:
            # Process as batch instead of individual message
            logger.info(
                f"Queued messages ready for batch processing",
                extra={'conversation_id': str(conversation.id)}
            )
            
            # Trigger batch processing
            return process_message_burst(str(conversation.id))
        
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
        
        # Check feature flag for AI agent
        use_ai_agent = _should_use_ai_agent(tenant)
        
        logger.info(
            f"Processing with {'AI agent' if use_ai_agent else 'legacy intent service'}",
            extra={
                'conversation_id': str(conversation.id),
                'tenant_id': str(tenant.id),
                'use_ai_agent': use_ai_agent
            }
        )
        
        # Create Twilio service
        twilio_service = create_twilio_service_for_tenant(tenant)
        
        if use_ai_agent:
            # === NEW AI AGENT FLOW ===
            return _process_with_ai_agent(
                message=message,
                conversation=conversation,
                tenant=tenant,
                twilio_service=twilio_service
            )
        else:
            # === LEGACY INTENT SERVICE FLOW ===
            return _process_with_legacy_intent_service(
                message=message,
                conversation=conversation,
                tenant=tenant,
                twilio_service=twilio_service
            )
    
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


def _detect_message_burst(message, conversation) -> bool:
    """
    Detect if message is part of a rapid burst (within 5 seconds of previous).
    
    Args:
        message: Current Message instance
        conversation: Conversation instance
        
    Returns:
        bool: True if burst detected, False otherwise
    """
    from apps.messaging.models import Message
    from datetime import timedelta
    
    # Get the previous inbound message in this conversation
    previous_message = Message.objects.filter(
        conversation=conversation,
        direction='in',
        created_at__lt=message.created_at
    ).order_by('-created_at').first()
    
    if not previous_message:
        return False
    
    # Check if within 5 seconds
    time_diff = message.created_at - previous_message.created_at
    is_burst = time_diff <= timedelta(seconds=5)
    
    if is_burst:
        logger.debug(
            f"Message burst detected: {time_diff.total_seconds():.2f}s since last message",
            extra={
                'conversation_id': str(conversation.id),
                'current_message_id': str(message.id),
                'previous_message_id': str(previous_message.id)
            }
        )
    
    return is_burst


def _queue_message_for_burst(message, conversation):
    """
    Queue message for batch processing.
    
    Args:
        message: Message instance to queue
        conversation: Conversation instance
        
    Returns:
        MessageQueue: Created queue entry, or None if already queued
    """
    from apps.messaging.models import MessageQueue
    from django.db import transaction
    
    # Check if message is already queued
    existing = MessageQueue.objects.filter(message=message).first()
    if existing:
        logger.debug(
            f"Message already queued",
            extra={'message_id': str(message.id)}
        )
        return existing
    
    # Get next queue position
    with transaction.atomic():
        max_position = MessageQueue.objects.filter(
            conversation=conversation,
            status='queued'
        ).aggregate(
            max_pos=models.Max('queue_position')
        )['max_pos']
        
        next_position = (max_position or 0) + 1
        
        # Create queue entry
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            status='queued',
            queue_position=next_position
        )
        
        logger.info(
            f"Message queued at position {next_position}",
            extra={
                'message_id': str(message.id),
                'conversation_id': str(conversation.id),
                'queue_position': next_position
            }
        )
        
        return queue_entry


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


@shared_task
def generate_conversation_summaries():
    """
    Periodic task to generate summaries for long conversations.
    
    Runs periodically (e.g., every hour) to:
    1. Find conversations with many messages but no summary
    2. Generate summaries using ConversationSummaryService
    3. Store summaries in ConversationContext
    
    This helps maintain context window efficiency for active conversations.
    """
    from apps.messaging.models import Conversation, Message
    from apps.bot.models import ConversationContext
    from apps.bot.services.conversation_summary_service import create_conversation_summary_service
    from django.db.models import Count, Q
    
    logger.info("Starting periodic conversation summary generation")
    
    summary_service = create_conversation_summary_service()
    
    # Find conversations that need summaries
    # Criteria: Active conversations with 20+ messages and no summary
    conversations_needing_summary = Conversation.objects.filter(
        status__in=['open', 'bot']
    ).annotate(
        message_count=Count('messages')
    ).filter(
        message_count__gte=20
    ).filter(
        Q(context__isnull=True) | Q(context__conversation_summary='')
    )[:50]  # Limit to 50 per run to avoid overload
    
    summary_count = 0
    error_count = 0
    
    for conversation in conversations_needing_summary:
        try:
            success = summary_service.update_context_summary(
                conversation=conversation,
                force=False
            )
            
            if success:
                summary_count += 1
                logger.info(
                    f"Generated summary for conversation {conversation.id}",
                    extra={
                        'conversation_id': str(conversation.id),
                        'tenant_id': str(conversation.tenant_id)
                    }
                )
            
        except Exception as e:
            error_count += 1
            logger.error(
                f"Failed to generate summary for conversation {conversation.id}: {e}",
                extra={
                    'conversation_id': str(conversation.id),
                    'error': str(e)
                }
            )
    
    logger.info(
        f"Conversation summary generation complete: "
        f"{summary_count} summaries generated, {error_count} errors"
    )
    
    return {
        'summaries_generated': summary_count,
        'errors': error_count,
        'conversations_processed': len(conversations_needing_summary)
    }


@shared_task
def cleanup_expired_contexts():
    """
    Periodic task to clean up expired conversation contexts.
    
    Runs periodically (e.g., every 30 minutes) to:
    1. Find contexts that have expired (30 minutes of inactivity)
    2. Clear context state while preserving key facts
    3. Log cleanup statistics
    
    Context expiration policy:
    - Contexts expire after 30 minutes of inactivity
    - Key facts are preserved even after expiration
    - Expired contexts are cleared but not deleted
    - This maintains privacy while enabling context restoration
    
    This helps maintain database efficiency and privacy.
    
    Requirements: 22.1, 22.2, 22.3
    """
    from apps.bot.models import ConversationContext
    from django.utils import timezone
    
    logger.info("Starting expired context cleanup")
    
    # Find expired contexts (30 minutes of inactivity)
    expired_contexts = ConversationContext.objects.filter(
        context_expires_at__lte=timezone.now()
    ).select_related('conversation')
    
    cleanup_count = 0
    key_facts_preserved_count = 0
    error_count = 0
    
    for context in expired_contexts:
        try:
            # Count key facts before clearing
            key_facts_count = len(context.key_facts)
            
            # Clear context but preserve key facts
            context.clear_context(preserve_key_facts=True)
            cleanup_count += 1
            
            if key_facts_count > 0:
                key_facts_preserved_count += 1
            
            logger.debug(
                f"Cleaned expired context for conversation {context.conversation_id}, "
                f"preserved {key_facts_count} key facts",
                extra={
                    'conversation_id': str(context.conversation_id),
                    'key_facts_preserved': key_facts_count
                }
            )
            
        except Exception as e:
            error_count += 1
            logger.error(
                f"Failed to clean context {context.id}: {e}",
                extra={'context_id': str(context.id)},
                exc_info=True
            )
    
    logger.info(
        f"Expired context cleanup complete: {cleanup_count} contexts cleaned, "
        f"{key_facts_preserved_count} had key facts preserved, {error_count} errors"
    )
    
    return {
        'contexts_cleaned': cleanup_count,
        'key_facts_preserved': key_facts_preserved_count,
        'errors': error_count
    }


def _should_use_ai_agent(tenant) -> bool:
    """
    Check if AI agent should be used for this tenant.
    
    Checks the feature flag in TenantSettings. Defaults to False
    if settings don't exist or flag is not set.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        bool: True if AI agent should be used
    """
    try:
        # Get tenant settings
        if not hasattr(tenant, 'settings'):
            logger.debug(f"Tenant {tenant.id} has no settings, using legacy system")
            return False
        
        # Check feature flag
        use_ai_agent = tenant.settings.is_feature_enabled('ai_agent_enabled')
        
        logger.debug(
            f"AI agent feature flag for tenant {tenant.id}: {use_ai_agent}"
        )
        
        return use_ai_agent
        
    except Exception as e:
        logger.error(
            f"Error checking AI agent feature flag for tenant {tenant.id}: {e}",
            exc_info=True
        )
        # Default to legacy system on error
        return False


def _process_with_ai_agent(
    message,
    conversation,
    tenant,
    twilio_service
) -> dict:
    """
    Process message using the new AI agent service.
    
    Args:
        message: Message instance
        conversation: Conversation instance
        tenant: Tenant instance
        twilio_service: TwilioService instance
        
    Returns:
        dict: Processing result with status and metadata
    """
    from apps.bot.services.ai_agent_service import create_ai_agent_service
    
    try:
        # Create AI agent service
        ai_agent = create_ai_agent_service()
        
        # Process message with AI agent
        agent_response = ai_agent.process_message(
            message=message,
            conversation=conversation,
            tenant=tenant
        )
        
        logger.info(
            f"AI agent generated response: model={agent_response.model_used}, "
            f"tokens={agent_response.total_tokens}, cost=${agent_response.estimated_cost}, "
            f"handoff={agent_response.should_handoff}",
            extra={
                'conversation_id': str(conversation.id),
                'message_id': str(message.id),
                'model': agent_response.model_used,
                'tokens': agent_response.total_tokens,
                'cost': str(agent_response.estimated_cost),
                'handoff': agent_response.should_handoff
            }
        )
        
        # Check if handoff was triggered
        if agent_response.should_handoff:
            logger.info(
                f"AI agent triggered handoff: {agent_response.handoff_reason}",
                extra={
                    'conversation_id': str(conversation.id),
                    'reason': agent_response.handoff_reason
                }
            )
            
            # Send handoff message
            twilio_service.send_whatsapp(
                to=conversation.customer.phone_e164,
                body=agent_response.content
            )
            
            return {
                'status': 'handoff',
                'reason': agent_response.handoff_reason,
                'model': agent_response.model_used,
                'tokens': agent_response.total_tokens,
                'cost': str(agent_response.estimated_cost)
            }
        
        # Send response (rich message or text)
        if agent_response.use_rich_message and agent_response.rich_message:
            # Send rich WhatsApp message
            logger.info(
                f"Sending rich message: type={agent_response.rich_message.message_type}",
                extra={
                    'conversation_id': str(conversation.id),
                    'message_type': agent_response.rich_message.message_type
                }
            )
            
            try:
                # Check if Twilio service has rich message support
                if hasattr(twilio_service, 'send_rich_whatsapp_message'):
                    twilio_service.send_rich_whatsapp_message(
                        to=conversation.customer.phone_e164,
                        rich_message=agent_response.rich_message
                    )
                else:
                    # Fallback to text if method doesn't exist
                    logger.warning(
                        f"Twilio service doesn't support rich messages, falling back to text",
                        extra={'conversation_id': str(conversation.id)}
                    )
                    twilio_service.send_whatsapp(
                        to=conversation.customer.phone_e164,
                        body=agent_response.content
                    )
            except Exception as rich_error:
                # Fallback to text if rich message fails
                logger.warning(
                    f"Rich message send failed, falling back to text: {rich_error}",
                    extra={'conversation_id': str(conversation.id)}
                )
                twilio_service.send_whatsapp(
                    to=conversation.customer.phone_e164,
                    body=agent_response.content
                )
        else:
            # Send text message
            twilio_service.send_whatsapp(
                to=conversation.customer.phone_e164,
                body=agent_response.content
            )
        
        logger.info(
            f"AI agent response sent successfully",
            extra={
                'conversation_id': str(conversation.id),
                'message_id': str(message.id)
            }
        )
        
        return {
            'status': 'success',
            'system': 'ai_agent',
            'model': agent_response.model_used,
            'provider': agent_response.provider,
            'confidence': agent_response.confidence_score,
            'tokens': agent_response.total_tokens,
            'cost': str(agent_response.estimated_cost),
            'rich_message': agent_response.use_rich_message,
            'processing_time_ms': agent_response.processing_time_ms
        }
        
    except Exception as e:
        logger.error(
            f"Error processing with AI agent: {e}",
            extra={
                'conversation_id': str(conversation.id),
                'message_id': str(message.id)
            },
            exc_info=True
        )
        
        # Send fallback message to customer
        try:
            twilio_service.send_whatsapp(
                to=conversation.customer.phone_e164,
                body="I apologize, but I'm having trouble processing your message right now. "
                     "Please try again or type 'help' for assistance."
            )
        except Exception as send_error:
            logger.error(f"Failed to send fallback message: {send_error}")
        
        return {
            'status': 'error',
            'system': 'ai_agent',
            'error': str(e)
        }


def _process_with_legacy_intent_service(
    message,
    conversation,
    tenant,
    twilio_service
) -> dict:
    """
    Process message using the legacy intent classification service.
    
    This is the original implementation that uses IntentService for
    classification and routes to specific handlers.
    
    Args:
        message: Message instance
        conversation: Conversation instance
        tenant: Tenant instance
        twilio_service: TwilioService instance
        
    Returns:
        dict: Processing result with status and metadata
    """
    from apps.bot.services.intent_service import create_intent_service
    from apps.bot.services.product_handlers import create_product_handler
    from apps.bot.services.service_handlers import create_service_handler
    from apps.bot.services.handoff_handler import create_handoff_handler
    from apps.bot.services.consent_handlers import create_consent_handler
    
    try:
        # Create services
        intent_service = create_intent_service()
        
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
                    'system': 'legacy',
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
                    'system': 'legacy',
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
            'system': 'legacy',
            'intent': intent_name,
            'confidence': classification['confidence_score']
        }
        
    except Exception as e:
        logger.error(
            f"Error processing with legacy intent service: {e}",
            extra={
                'conversation_id': str(conversation.id),
                'message_id': str(message.id)
            },
            exc_info=True
        )
        
        return {
            'status': 'error',
            'system': 'legacy',
            'error': str(e)
        }


@shared_task(bind=True, max_retries=2)
def process_message_burst(self, conversation_id: str):
    """
    Process a burst of queued messages together.
    
    This task is triggered when message bursts are detected (multiple messages
    within 5 seconds). It waits for the burst to complete, then processes all
    queued messages together using the MultiIntentProcessor.
    
    Args:
        conversation_id: UUID of the Conversation
        
    Returns:
        dict: Processing result with status and metadata
    """
    from apps.messaging.models import Conversation, MessageQueue
    from apps.bot.services.multi_intent_processor import create_multi_intent_processor
    from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
    
    try:
        # Load conversation
        conversation = Conversation.objects.select_related(
            'tenant',
            'customer'
        ).get(id=conversation_id)
        
        tenant = conversation.tenant
        
        logger.info(
            f"Processing message burst for conversation",
            extra={
                'conversation_id': str(conversation_id),
                'tenant_id': str(tenant.id)
            }
        )
        
        # Check if conversation is in handoff mode
        if conversation.status == 'handoff':
            logger.info(
                f"Conversation in handoff mode, skipping burst processing",
                extra={'conversation_id': str(conversation_id)}
            )
            
            # Mark queued messages as processed (skipped)
            MessageQueue.objects.filter(
                conversation=conversation,
                status='queued'
            ).update(status='processed')
            
            return {
                'status': 'skipped',
                'reason': 'handoff_active'
            }
        
        # Check if there are queued messages ready for processing
        ready_messages = MessageQueue.objects.ready_for_batch(
            conversation=conversation,
            delay_seconds=5
        )
        
        if not ready_messages.exists():
            logger.debug(
                f"No messages ready for batch processing yet",
                extra={'conversation_id': str(conversation_id)}
            )
            return {
                'status': 'no_messages_ready',
                'reason': 'waiting_for_burst_completion'
            }
        
        # Create services
        multi_intent_processor = create_multi_intent_processor(tenant)
        twilio_service = create_twilio_service_for_tenant(tenant)
        
        # Process message burst
        result = multi_intent_processor.process_message_burst(
            conversation=conversation,
            delay_seconds=5
        )
        
        if not result:
            logger.warning(
                f"No result from message burst processing",
                extra={'conversation_id': str(conversation_id)}
            )
            return {
                'status': 'no_result',
                'reason': 'burst_processing_returned_none'
            }
        
        # Send response
        twilio_service.send_whatsapp(
            to=conversation.customer.phone_e164,
            body=result['response']
        )
        
        logger.info(
            f"Message burst processed and response sent",
            extra={
                'conversation_id': str(conversation_id),
                'message_count': result['message_count'],
                'intents_addressed': len(result['intents_addressed'])
            }
        )
        
        return {
            'status': 'success',
            'message_count': result['message_count'],
            'intents_addressed': len(result['intents_addressed']),
            'response_length': len(result['response'])
        }
        
    except Conversation.DoesNotExist:
        logger.error(f"Conversation not found: {conversation_id}")
        return {
            'status': 'error',
            'error': 'conversation_not_found'
        }
    
    except Exception as e:
        logger.error(
            f"Error processing message burst",
            extra={'conversation_id': str(conversation_id)},
            exc_info=True
        )
        
        # Mark queued messages as failed
        try:
            MessageQueue.objects.filter(
                conversation_id=conversation_id,
                status__in=['queued', 'processing']
            ).update(
                status='failed',
                error_message=str(e)
            )
        except Exception as cleanup_error:
            logger.error(
                f"Failed to mark messages as failed: {cleanup_error}",
                extra={'conversation_id': str(conversation_id)}
            )
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for message burst processing",
                extra={'conversation_id': str(conversation_id)}
            )
            return {
                'status': 'failed',
                'error': str(e)
            }


@shared_task
def analyze_products_batch(tenant_id: str, product_ids: list = None):
    """
    Background task to analyze products using AI.
    
    Analyzes products to extract:
    - Key features
    - Use cases
    - Target audience
    - Semantic embeddings
    - AI categories and tags
    
    Args:
        tenant_id: Tenant UUID
        product_ids: Optional list of specific product IDs to analyze
    
    Requirements: 25.1, 25.4
    """
    from apps.tenants.models import Tenant
    from apps.catalog.models import Product
    from apps.bot.services.product_intelligence import ProductIntelligenceService
    
    logger.info(f"Starting product analysis batch for tenant {tenant_id}")
    
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        
        # Get products to analyze
        if product_ids:
            products = Product.objects.filter(
                tenant=tenant,
                id__in=product_ids,
                is_active=True
            )
        else:
            # Analyze products that haven't been analyzed or need refresh
            from datetime import timedelta
            from django.utils import timezone
            from apps.bot.models import ProductAnalysis
            
            analyzed_product_ids = ProductAnalysis.objects.filter(
                product__tenant=tenant,
                analyzed_at__gte=timezone.now() - timedelta(hours=24)
            ).values_list('product_id', flat=True)
            
            products = Product.objects.filter(
                tenant=tenant,
                is_active=True
            ).exclude(id__in=analyzed_product_ids)[:50]  # Batch of 50
        
        analyzed_count = 0
        error_count = 0
        
        for product in products:
            try:
                ProductIntelligenceService.analyze_product(product)
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing product {product.id}: {e}")
                error_count += 1
        
        logger.info(
            f"Product analysis batch complete: {analyzed_count} analyzed, "
            f"{error_count} errors"
        )
        
        return {
            'status': 'success',
            'analyzed_count': analyzed_count,
            'error_count': error_count,
        }
        
    except Tenant.DoesNotExist:
        logger.error(f"Tenant not found: {tenant_id}")
        return {'status': 'error', 'error': 'tenant_not_found'}
    
    except Exception as e:
        logger.error(f"Error in product analysis batch: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task
def cleanup_expired_browse_sessions():
    """
    Periodic task to clean up expired browse sessions.
    
    Runs periodically to deactivate browse sessions that have expired.
    
    Requirements: 23.1, 23.2
    """
    from apps.bot.services.catalog_browser import CatalogBrowserService
    
    logger.info("Starting expired browse session cleanup")
    
    try:
        expired_count = CatalogBrowserService.cleanup_expired_sessions()
        
        logger.info(f"Browse session cleanup complete: {expired_count} deactivated")
        
        return {
            'status': 'success',
            'expired_count': expired_count,
        }
        
    except Exception as e:
        logger.error(f"Error in browse session cleanup: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task
def cleanup_expired_reference_contexts():
    """
    Periodic task to clean up expired reference contexts.
    
    Runs periodically to delete reference contexts that have expired.
    
    Requirements: 24.1, 24.5
    """
    from apps.bot.services.reference_context_manager import ReferenceContextManager
    
    logger.info("Starting expired reference context cleanup")
    
    try:
        deleted_count = ReferenceContextManager.cleanup_expired_contexts()
        
        logger.info(f"Reference context cleanup complete: {deleted_count} deleted")
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
        }
        
    except Exception as e:
        logger.error(f"Error in reference context cleanup: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}



@shared_task
def cleanup_expired_browse_sessions():
    """
    Clean up expired browse sessions.
    
    This task should be run periodically (e.g., every 15 minutes) to
    deactivate browse sessions that have expired.
    
    Returns:
        Number of sessions cleaned up
    """
    from apps.bot.services.catalog_browser_service import CatalogBrowserService
    
    try:
        count = CatalogBrowserService.cleanup_expired_sessions()
        logger.info(f"Cleaned up {count} expired browse sessions")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up browse sessions: {e}", exc_info=True)
        raise
