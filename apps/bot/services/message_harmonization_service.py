"""
Message Harmonization Service for handling rapid message bursts.

This service detects when customers send multiple messages in rapid succession
(within 3 seconds) and combines them into a single conversational turn for
coherent AI processing.

Implements Requirements 4.1, 4.2, 4.3, 4.4, 4.5 from conversational-commerce-ux-enhancement spec.
"""
import logging
from typing import List, Optional, Tuple
from datetime import timedelta
from django.utils import timezone
from django.db import transaction, models

from apps.messaging.models import Message, Conversation, MessageQueue
from apps.bot.models import ConversationContext

logger = logging.getLogger(__name__)


class MessageHarmonizationService:
    """
    Service for detecting and harmonizing rapid message bursts.
    
    When customers send multiple messages within 3 seconds, this service:
    1. Detects the burst pattern
    2. Buffers messages in the queue
    3. Waits for the burst to complete (3 seconds of silence)
    4. Combines all messages into a single text
    5. Processes them together for one coherent response
    
    This prevents fragmented responses and provides better UX.
    """
    
    DEFAULT_WAIT_SECONDS = 3
    MAX_BUFFER_SIZE = 10  # Prevent infinite buffering
    
    def __init__(self, wait_seconds: int = DEFAULT_WAIT_SECONDS):
        """
        Initialize Message Harmonization Service.
        
        Args:
            wait_seconds: Seconds to wait before processing buffered messages
        """
        self.wait_seconds = wait_seconds
    
    def should_buffer_message(
        self,
        conversation: Conversation,
        message: Message
    ) -> bool:
        """
        Check if message should be buffered for harmonization.
        
        A message should be buffered if:
        1. There's a recent message (within wait_seconds)
        2. The buffer hasn't exceeded max size
        3. Conversation is not in handoff mode
        
        Args:
            conversation: Conversation instance
            message: New message to check
            
        Returns:
            True if message should be buffered, False otherwise
        """
        # Don't buffer if conversation is in handoff mode
        if conversation.status == 'handoff':
            logger.debug(
                f"Conversation {conversation.id} in handoff mode, not buffering"
            )
            return False
        
        # Check if there are already queued messages
        queued_count = MessageQueue.objects.filter(
            conversation=conversation,
            status='queued'
        ).count()
        
        # Don't buffer if we've hit max buffer size
        if queued_count >= self.MAX_BUFFER_SIZE:
            logger.warning(
                f"Conversation {conversation.id} hit max buffer size ({self.MAX_BUFFER_SIZE}), "
                f"processing immediately"
            )
            return False
        
        # Check for recent messages relative to this message's timestamp
        cutoff_time = message.created_at - timedelta(seconds=self.wait_seconds)
        
        # Look for recent messages that were created within the wait window
        recent_messages = Message.objects.filter(
            conversation=conversation,
            direction='in',
            created_at__gte=cutoff_time,
            created_at__lt=message.created_at  # Must be before this message
        ).exists()
        
        should_buffer = recent_messages
        
        if should_buffer:
            logger.info(
                f"Message {message.id} should be buffered (recent activity detected)"
            )
        
        return should_buffer
    
    def buffer_message(
        self,
        conversation: Conversation,
        message: Message
    ) -> MessageQueue:
        """
        Add message to buffer queue.
        
        Args:
            conversation: Conversation instance
            message: Message to buffer
            
        Returns:
            MessageQueue entry created
        """
        with transaction.atomic():
            # Get next queue position (tenant-scoped)
            max_position = MessageQueue.objects.filter(
                conversation=conversation,
                conversation__tenant=conversation.tenant  # Explicit tenant scoping
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
            
            # Update conversation context with last message time
            context, _ = ConversationContext.objects.get_or_create(
                conversation=conversation
            )
            context.last_interaction = timezone.now()
            
            # Store message buffer metadata in extracted_entities
            if 'message_buffer' not in context.extracted_entities:
                context.extracted_entities['message_buffer'] = []
            
            context.extracted_entities['message_buffer'].append({
                'message_id': str(message.id),
                'queued_at': timezone.now().isoformat(),
                'position': next_position
            })
            context.save(update_fields=['last_interaction', 'extracted_entities'])
            
            logger.info(
                f"Message {message.id} buffered at position {next_position} "
                f"for conversation {conversation.id}"
            )
            
            return queue_entry
    
    def get_harmonized_messages(
        self,
        conversation: Conversation,
        wait_seconds: Optional[int] = None
    ) -> List[Message]:
        """
        Get all messages ready for harmonized processing.
        
        Returns messages that have been queued for at least wait_seconds
        and are still in queued status.
        
        Args:
            conversation: Conversation instance
            wait_seconds: Optional override for wait time
            
        Returns:
            List of Message instances ready for processing
        """
        if wait_seconds is None:
            wait_seconds = self.wait_seconds
        
        # Get ready queue entries
        ready_entries = MessageQueue.objects.ready_for_batch(
            conversation=conversation,
            delay_seconds=wait_seconds
        )
        
        if not ready_entries.exists():
            return []
        
        # Extract messages
        messages = [entry.message for entry in ready_entries]
        
        logger.info(
            f"Retrieved {len(messages)} harmonized messages for conversation {conversation.id}"
        )
        
        return messages
    
    def combine_messages(
        self,
        messages: List[Message]
    ) -> str:
        """
        Combine multiple messages into single text.
        
        Messages are combined with newlines to preserve structure
        while treating them as a single conversational turn.
        
        Args:
            messages: List of Message instances to combine
            
        Returns:
            Combined message text
        """
        if not messages:
            return ""
        
        if len(messages) == 1:
            return messages[0].text
        
        # Combine messages with newlines
        combined_text = "\n".join(msg.text for msg in messages)
        
        logger.info(
            f"Combined {len(messages)} messages into single text "
            f"({len(combined_text)} characters)"
        )
        
        return combined_text
    
    def mark_messages_processing(
        self,
        conversation: Conversation,
        messages: List[Message]
    ) -> None:
        """
        Mark queued messages as currently being processed.
        
        Args:
            conversation: Conversation instance
            messages: List of messages being processed
        """
        message_ids = [msg.id for msg in messages]
        
        MessageQueue.objects.filter(
            conversation=conversation,
            message__id__in=message_ids,
            status='queued'
        ).update(status='processing')
        
        logger.info(
            f"Marked {len(messages)} messages as processing for conversation {conversation.id}"
        )
    
    def mark_messages_processed(
        self,
        conversation: Conversation,
        messages: List[Message]
    ) -> None:
        """
        Mark queued messages as successfully processed.
        
        Args:
            conversation: Conversation instance
            messages: List of messages that were processed
        """
        message_ids = [msg.id for msg in messages]
        
        MessageQueue.objects.filter(
            conversation=conversation,
            message__id__in=message_ids,
            status='processing'
        ).update(
            status='processed',
            processed_at=timezone.now()
        )
        
        # Clear message buffer from context
        try:
            context = ConversationContext.objects.get(conversation=conversation)
            if 'message_buffer' in context.extracted_entities:
                context.extracted_entities['message_buffer'] = []
                context.save(update_fields=['extracted_entities'])
        except ConversationContext.DoesNotExist:
            pass
        
        logger.info(
            f"Marked {len(messages)} messages as processed for conversation {conversation.id}"
        )
    
    def mark_messages_failed(
        self,
        conversation: Conversation,
        messages: List[Message],
        error_message: str
    ) -> None:
        """
        Mark queued messages as failed.
        
        Args:
            conversation: Conversation instance
            messages: List of messages that failed
            error_message: Error description
        """
        message_ids = [msg.id for msg in messages]
        
        MessageQueue.objects.filter(
            conversation=conversation,
            message__id__in=message_ids,
            status='processing'
        ).update(
            status='failed',
            processed_at=timezone.now(),
            error_message=error_message
        )
        
        logger.error(
            f"Marked {len(messages)} messages as failed for conversation {conversation.id}: "
            f"{error_message}"
        )
    
    def should_show_typing_indicator(
        self,
        conversation: Conversation
    ) -> bool:
        """
        Check if typing indicator should be shown.
        
        Typing indicator should be shown when:
        1. Messages are queued
        2. We're waiting for the burst to complete
        
        Args:
            conversation: Conversation instance
            
        Returns:
            True if typing indicator should be shown
        """
        queued_count = MessageQueue.objects.filter(
            conversation=conversation,
            status='queued'
        ).count()
        
        return queued_count > 0
    
    def get_buffer_stats(
        self,
        conversation: Conversation
    ) -> dict:
        """
        Get statistics about current message buffer.
        
        Args:
            conversation: Conversation instance
            
        Returns:
            Dictionary with buffer statistics
        """
        queued = MessageQueue.objects.filter(
            conversation=conversation,
            status='queued'
        )
        
        if not queued.exists():
            return {
                'queued_count': 0,
                'oldest_queued_at': None,
                'wait_time_seconds': 0,
                'ready_for_processing': False
            }
        
        oldest = queued.order_by('queued_at').first()
        wait_time = (timezone.now() - oldest.queued_at).total_seconds()
        
        return {
            'queued_count': queued.count(),
            'oldest_queued_at': oldest.queued_at,
            'wait_time_seconds': wait_time,
            'ready_for_processing': wait_time >= self.wait_seconds
        }


def create_message_harmonization_service(
    wait_seconds: int = MessageHarmonizationService.DEFAULT_WAIT_SECONDS
) -> MessageHarmonizationService:
    """
    Factory function to create MessageHarmonizationService instance.
    
    Args:
        wait_seconds: Seconds to wait before processing buffered messages
        
    Returns:
        MessageHarmonizationService instance
    """
    return MessageHarmonizationService(wait_seconds=wait_seconds)
