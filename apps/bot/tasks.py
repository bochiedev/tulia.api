"""
Celery tasks for bot AI agent processing.

Handles asynchronous processing of inbound messages using the AI agent service.
All messages are processed through the AI agent - legacy intent classification removed.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db import models

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_inbound_message(self, message_id: str):
    """
    Process inbound message using AI agent.
    
    All messages are processed through the AI-powered agent service.
    Legacy intent classification system has been removed.
    
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
        
    Flow:
        1. Load message and conversation
        2. Check for duplicate processing (deduplication)
        3. Acquire distributed lock for message
        4. Check for message burst (rapid messages within 5 seconds)
        5. If burst detected, queue message and schedule batch processing
        6. If no burst, process message with AI agent
        7. Check if handoff is active (skip bot if yes)
        8. Build comprehensive context from multiple sources
        9. Generate response using LLM with persona and knowledge
        10. Send response via Twilio (text or rich message)
        11. Track interaction for analytics
        12. Release distributed lock
    """
    from apps.messaging.models import Message, Conversation, MessageQueue
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
        
        # Check for message burst (rapid messages within 3 seconds)
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
                
                # Schedule batch processing task (delayed by 3 seconds)
                process_message_burst.apply_async(
                    args=[str(conversation.id)],
                    countdown=3
                )
                
                return {
                    'status': 'queued',
                    'queue_position': queued.queue_position,
                    'reason': 'message_burst_detected'
                }
        
        # Check if there are already queued messages ready for batch processing
        ready_for_batch = MessageQueue.objects.ready_for_batch(
            conversation=conversation,
            delay_seconds=3
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
        
        logger.info(
            f"Processing with AI agent",
            extra={
                'conversation_id': str(conversation.id),
                'tenant_id': str(tenant.id)
            }
        )
        
        # Create Twilio service
        twilio_service = create_twilio_service_for_tenant(tenant)
        
        # Process with AI agent (legacy system removed)
        return _process_with_ai_agent(
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
    Detect if message is part of a rapid burst (within 3 seconds of previous).
    
    Uses the MessageHarmonizationService to detect rapid message patterns.
    
    Args:
        message: Current Message instance
        conversation: Conversation instance
        
    Returns:
        bool: True if burst detected, False otherwise
    """
    from apps.bot.services.message_harmonization_service import create_message_harmonization_service
    
    # Create harmonization service with 3 second wait time
    harmonization_service = create_message_harmonization_service(wait_seconds=3)
    
    # Check if message should be buffered
    should_buffer = harmonization_service.should_buffer_message(
        conversation=conversation,
        message=message
    )
    
    if should_buffer:
        logger.debug(
            f"Message burst detected for harmonization",
            extra={
                'conversation_id': str(conversation.id),
                'message_id': str(message.id)
            }
        )
    
    return should_buffer


def _queue_message_for_burst(message, conversation):
    """
    Queue message for batch processing using MessageHarmonizationService.
    
    Args:
        message: Message instance to queue
        conversation: Conversation instance
        
    Returns:
        MessageQueue: Created queue entry, or None if already queued
    """
    from apps.bot.services.message_harmonization_service import create_message_harmonization_service
    from apps.messaging.models import MessageQueue
    
    # Check if message is already queued
    existing = MessageQueue.objects.filter(message=message).first()
    if existing:
        logger.debug(
            f"Message already queued",
            extra={'message_id': str(message.id)}
        )
        return existing
    
    # Create harmonization service
    harmonization_service = create_message_harmonization_service(wait_seconds=3)
    
    # Buffer the message
    queue_entry = harmonization_service.buffer_message(
        conversation=conversation,
        message=message
    )
    
    logger.info(
        f"Message queued at position {queue_entry.queue_position}",
        extra={
            'message_id': str(message.id),
            'conversation_id': str(conversation.id),
            'queue_position': queue_entry.queue_position
        }
    )
    
    return queue_entry


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


@shared_task(bind=True, max_retries=2)
def process_message_burst(self, conversation_id: str):
    """
    Process a burst of queued messages together.
    
    This task is triggered when message bursts are detected (multiple messages
    within 3 seconds). It waits for the burst to complete, then processes all
    queued messages together as a single harmonized message.
    
    Uses MessageHarmonizationService to combine messages and AI agent for processing.
    
    Args:
        conversation_id: UUID of the Conversation
        
    Returns:
        dict: Processing result with status and metadata
    """
    from apps.messaging.models import Conversation, MessageQueue
    from apps.bot.services.message_harmonization_service import create_message_harmonization_service
    from apps.bot.services.ai_agent_service import create_ai_agent_service
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
        
        # Create harmonization service
        harmonization_service = create_message_harmonization_service(wait_seconds=3)
        
        # Get harmonized messages ready for processing
        harmonized_messages = harmonization_service.get_harmonized_messages(
            conversation=conversation,
            wait_seconds=3
        )
        
        if not harmonized_messages:
            logger.debug(
                f"No messages ready for batch processing yet",
                extra={'conversation_id': str(conversation_id)}
            )
            return {
                'status': 'no_messages_ready',
                'reason': 'waiting_for_burst_completion'
            }
        
        logger.info(
            f"Processing {len(harmonized_messages)} harmonized messages",
            extra={
                'conversation_id': str(conversation_id),
                'message_count': len(harmonized_messages)
            }
        )
        
        # Mark messages as processing
        harmonization_service.mark_messages_processing(
            conversation=conversation,
            messages=harmonized_messages
        )
        
        # Combine messages into single text
        combined_text = harmonization_service.combine_messages(harmonized_messages)
        
        # Check feature flag for AI agent
        use_ai_agent = _should_use_ai_agent(tenant)
        
        # Create services
        twilio_service = create_twilio_service_for_tenant(tenant)
        
        try:
            # Process with AI agent (legacy system removed)
            ai_agent = create_ai_agent_service()
            
            # Use the first message as the base, but with combined text
            primary_message = harmonized_messages[0]
            primary_message.text = combined_text
            
            # Process with AI agent
            agent_response = ai_agent.process_message(
                message=primary_message,
                conversation=conversation,
                tenant=tenant
            )
            
            # Send response
            if agent_response.use_rich_message and agent_response.rich_message:
                try:
                    if hasattr(twilio_service, 'send_rich_whatsapp_message'):
                        twilio_service.send_rich_whatsapp_message(
                            to=conversation.customer.phone_e164,
                            rich_message=agent_response.rich_message
                        )
                    else:
                        twilio_service.send_whatsapp(
                            to=conversation.customer.phone_e164,
                            body=agent_response.content
                        )
                except Exception:
                    twilio_service.send_whatsapp(
                        to=conversation.customer.phone_e164,
                        body=agent_response.content
                    )
            else:
                twilio_service.send_whatsapp(
                    to=conversation.customer.phone_e164,
                    body=agent_response.content
                )
            
            # Mark messages as processed
            harmonization_service.mark_messages_processed(
                conversation=conversation,
                messages=harmonized_messages
            )
            
            logger.info(
                f"Message burst processed with AI agent",
                extra={
                    'conversation_id': str(conversation_id),
                    'message_count': len(harmonized_messages),
                    'model': agent_response.model_used,
                    'tokens': agent_response.total_tokens
                }
            )
            
            return {
                'status': 'success',
                'system': 'ai_agent',
                'message_count': len(harmonized_messages),
                'model': agent_response.model_used,
                'tokens': agent_response.total_tokens,
                'cost': str(agent_response.estimated_cost)
            }
                
        except Exception as processing_error:
            # Mark messages as failed
            harmonization_service.mark_messages_failed(
                conversation=conversation,
                messages=harmonized_messages,
                error_message=str(processing_error)
            )
            raise processing_error
        
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



@shared_task(bind=True, max_retries=2)
def process_document(self, document_id: str):
    """
    Process uploaded document: extract text, chunk, embed, and index.
    
    This task orchestrates the complete document processing pipeline:
    1. Extract text from PDF/TXT file
    2. Chunk text into smaller pieces
    3. Generate embeddings for each chunk
    4. Index chunks in vector store
    5. Update document status
    
    Args:
        document_id: UUID of the Document to process
    
    Returns:
        Dict with processing statistics
    """
    from apps.bot.models import Document, DocumentChunk
    from apps.bot.services.text_extraction_service import TextExtractionService
    from apps.bot.services.chunking_service import ChunkingService
    from apps.bot.services.embedding_service import EmbeddingService
    from apps.bot.services.vector_store import PineconeVectorStore
    from django.core.files.storage import default_storage
    import time
    import uuid
    
    start_time = time.time()
    
    try:
        # Load document
        document = Document.objects.get(id=document_id)
        tenant = document.tenant
        
        logger.info(f"Starting document processing: {document_id}")
        
        # Update status to processing
        document.status = 'processing'
        document.processing_progress = 0
        document.save(update_fields=['status', 'processing_progress'])
        
        # Get file path
        file_path = default_storage.path(document.file_path)
        
        # Step 1: Extract text (20% progress)
        logger.info(f"Extracting text from {document.file_name}")
        extraction_result = TextExtractionService.extract(
            file_path=file_path,
            file_type=document.file_type
        )
        
        document.processing_progress = 20
        document.save(update_fields=['processing_progress'])
        
        # Step 2: Chunk text (40% progress)
        logger.info(f"Chunking text from {document.file_name}")
        chunking_service = ChunkingService.create_default()
        
        if 'pages' in extraction_result:
            chunks = chunking_service.chunk_pages(extraction_result['pages'])
        else:
            chunks = chunking_service.chunk_text(
                extraction_result['text'],
                metadata=extraction_result.get('metadata', {})
            )
        
        if not chunks:
            raise ValueError("No chunks generated from document")
        
        document.processing_progress = 40
        document.save(update_fields=['processing_progress'])
        
        # Step 3: Generate embeddings (70% progress)
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        embedding_service = EmbeddingService.create_for_tenant(tenant)
        
        # Batch embed chunks (max 100 at a time)
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [chunk['content'] for chunk in batch]
            
            embeddings = embedding_service.embed_batch(
                batch_texts,
                use_cache=False
            )
            all_embeddings.extend(embeddings)
            
            # Update progress
            progress = 40 + int((i / len(chunks)) * 30)
            document.processing_progress = progress
            document.save(update_fields=['processing_progress'])
        
        document.processing_progress = 70
        document.save(update_fields=['processing_progress'])
        
        # Step 4: Index in vector store (90% progress)
        logger.info(f"Indexing {len(chunks)} chunks in vector store")
        vector_store = PineconeVectorStore.create_from_settings()
        namespace = f"tenant_{tenant.id}"
        
        # Create document chunks and prepare vectors
        vectors = []
        total_tokens = 0
        
        for i, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
            # Create vector ID
            vector_id = f"doc_{document.id}_chunk_{i}"
            
            # Create DocumentChunk record
            chunk_obj = DocumentChunk.objects.create(
                document=document,
                tenant=tenant,
                chunk_index=i,
                content=chunk['content'],
                token_count=chunk['token_count'],
                page_number=chunk['metadata'].get('page_number'),
                section=chunk['metadata'].get('section'),
                embedding_model=embedding['model'],
                vector_id=vector_id
            )
            
            total_tokens += chunk['token_count']
            
            # Prepare vector for upsert
            vectors.append({
                'id': vector_id,
                'values': embedding['embedding'],
                'metadata': {
                    'tenant_id': str(tenant.id),
                    'document_id': str(document.id),
                    'chunk_id': str(chunk_obj.id),
                    'chunk_index': i,
                    'page_number': chunk['metadata'].get('page_number'),
                    'file_name': document.file_name,
                }
            })
        
        # Upsert vectors to Pinecone
        vector_store.upsert(vectors, namespace=namespace)
        
        document.processing_progress = 90
        document.save(update_fields=['processing_progress'])
        
        # Step 5: Update document status (100% progress)
        document.status = 'completed'
        document.processing_progress = 100
        document.chunk_count = len(chunks)
        document.total_tokens = total_tokens
        document.processed_at = timezone.now()
        document.save(update_fields=[
            'status',
            'processing_progress',
            'chunk_count',
            'total_tokens',
            'processed_at'
        ])
        
        processing_time = time.time() - start_time
        
        logger.info(
            f"Document processing complete: {document_id} - "
            f"{len(chunks)} chunks, {total_tokens} tokens, "
            f"{processing_time:.2f}s"
        )
        
        return {
            'status': 'success',
            'document_id': str(document.id),
            'chunk_count': len(chunks),
            'total_tokens': total_tokens,
            'processing_time': processing_time
        }
        
    except Document.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        return {'status': 'error', 'error': 'Document not found'}
        
    except Exception as e:
        logger.error(
            f"Error processing document {document_id}: {e}",
            exc_info=True
        )
        
        # Update document status to failed
        try:
            document = Document.objects.get(id=document_id)
            document.status = 'failed'
            document.error_message = str(e)
            document.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
        
        # Retry if not max retries
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'error', 'error': str(e)}
