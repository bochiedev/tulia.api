"""
Conversation History Service for managing full conversation history.

Provides methods to retrieve complete conversation history with intelligent
summarization for very long conversations.
"""
import logging
from typing import List, Optional, Dict, Any
from django.db.models import Q

from apps.messaging.models import Message, Conversation
from apps.bot.models import ConversationContext
from apps.bot.services.conversation_summary_service import ConversationSummaryService

logger = logging.getLogger(__name__)


class ConversationHistoryService:
    """
    Service for managing conversation history retrieval and summarization.
    
    Ensures full conversation memory is available while managing context
    window size through intelligent summarization.
    """
    
    # Thresholds for summarization
    SUMMARIZATION_THRESHOLD = 50  # Messages before summarization kicks in
    RECENT_MESSAGES_COUNT = 20  # Number of recent messages to keep in full
    
    def __init__(self, summary_service: Optional[ConversationSummaryService] = None):
        """
        Initialize Conversation History Service.
        
        Args:
            summary_service: Optional ConversationSummaryService instance
        """
        self.summary_service = summary_service or ConversationSummaryService()
    
    def get_full_history(
        self,
        conversation: Conversation,
        include_system_messages: bool = False,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """
        Get complete conversation history with optional pagination.
        
        Retrieves ALL messages from the conversation, not just recent ones.
        This ensures the bot can answer questions like "what have we talked about".
        
        Optimized with select_related for better query performance.
        
        Args:
            conversation: Conversation instance
            include_system_messages: Whether to include system messages
            limit: Optional maximum number of messages to return
            offset: Number of messages to skip (for pagination)
            
        Returns:
            List of Message instances ordered chronologically
        """
        query = Message.objects.filter(conversation=conversation).select_related(
            'conversation', 'conversation__tenant', 'conversation__customer'
        )
        
        if not include_system_messages:
            # Exclude system messages if they exist
            query = query.exclude(
                Q(text__startswith='[System]') | 
                Q(text__startswith='[AUTO]')
            )
        
        query = query.order_by('created_at')
        
        # Apply pagination if requested
        if limit is not None:
            query = query[offset:offset + limit]
        
        messages = list(query)
        
        logger.info(
            f"Retrieved history for conversation {conversation.id}: "
            f"{len(messages)} messages (limit={limit}, offset={offset})"
        )
        
        return messages
    
    def get_history_page(
        self,
        conversation: Conversation,
        page: int = 1,
        page_size: int = 50,
        include_system_messages: bool = False
    ) -> Dict[str, Any]:
        """
        Get paginated conversation history.
        
        Args:
            conversation: Conversation instance
            page: Page number (1-indexed)
            page_size: Number of messages per page
            include_system_messages: Whether to include system messages
            
        Returns:
            Dictionary with 'messages', 'page', 'page_size', 'total_messages', 'total_pages'
        """
        # Get total count
        query = Message.objects.filter(conversation=conversation)
        if not include_system_messages:
            query = query.exclude(
                Q(text__startswith='[System]') | 
                Q(text__startswith='[AUTO]')
            )
        
        total_messages = query.count()
        total_pages = (total_messages + page_size - 1) // page_size
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get messages for this page
        messages = self.get_full_history(
            conversation=conversation,
            include_system_messages=include_system_messages,
            limit=page_size,
            offset=offset
        )
        
        return {
            'messages': messages,
            'page': page,
            'page_size': page_size,
            'total_messages': total_messages,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }
    
    def get_history_with_summary(
        self,
        conversation: Conversation,
        recent_count: int = 20
    ) -> Dict[str, Any]:
        """
        Get conversation history with summary for old messages.
        
        For long conversations, returns:
        - Summary of old messages (beyond recent_count)
        - Full text of recent messages
        
        This balances context completeness with token efficiency.
        
        Args:
            conversation: Conversation instance
            recent_count: Number of recent messages to return in full
            
        Returns:
            Dictionary with 'summary' and 'recent_messages' keys
        """
        all_messages = self.get_full_history(conversation)
        total_count = len(all_messages)
        
        result = {
            'summary': None,
            'recent_messages': [],
            'total_messages': total_count,
            'summarized_count': 0
        }
        
        # If conversation is short, return all messages
        if total_count <= recent_count:
            result['recent_messages'] = all_messages
            logger.debug(
                f"Conversation {conversation.id} has {total_count} messages, "
                "no summarization needed"
            )
            return result
        
        # Split into old and recent
        old_messages = all_messages[:total_count - recent_count]
        recent_messages = all_messages[total_count - recent_count:]
        
        result['recent_messages'] = recent_messages
        result['summarized_count'] = len(old_messages)
        
        # Generate or retrieve summary for old messages
        summary = self._get_or_generate_summary(conversation, old_messages)
        result['summary'] = summary
        
        logger.info(
            f"Conversation {conversation.id}: summarized {len(old_messages)} messages, "
            f"returning {len(recent_messages)} recent messages"
        )
        
        return result
    
    def ensure_summary_exists(
        self,
        conversation: Conversation,
        force_regenerate: bool = False
    ) -> bool:
        """
        Ensure conversation has a summary if it's long enough.
        
        Generates summary for conversations exceeding the threshold.
        
        Args:
            conversation: Conversation instance
            force_regenerate: Force regeneration even if summary exists
            
        Returns:
            True if summary was created/updated, False otherwise
        """
        message_count = Message.objects.filter(conversation=conversation).count()
        
        # Check if conversation is long enough for summarization
        if message_count < self.SUMMARIZATION_THRESHOLD:
            logger.debug(
                f"Conversation {conversation.id} has {message_count} messages, "
                f"below threshold of {self.SUMMARIZATION_THRESHOLD}"
            )
            return False
        
        # Get or create context
        context, created = ConversationContext.objects.get_or_create(
            conversation=conversation
        )
        
        # Check if summary already exists
        if context.conversation_summary and not force_regenerate:
            logger.debug(
                f"Summary already exists for conversation {conversation.id}"
            )
            return False
        
        # Generate summary
        logger.info(
            f"Generating summary for conversation {conversation.id} "
            f"with {message_count} messages"
        )
        
        return self.summary_service.update_context_summary(
            conversation,
            force=force_regenerate
        )
    
    def get_conversation_topics(
        self,
        conversation: Conversation
    ) -> List[str]:
        """
        Extract main topics discussed in conversation.
        
        Analyzes conversation history to identify key topics.
        
        Args:
            conversation: Conversation instance
            
        Returns:
            List of topic strings
        """
        topics = []
        
        # Get context if it exists
        try:
            context = ConversationContext.objects.get(conversation=conversation)
            
            # Extract topics from current_topic and key_facts
            if context.current_topic:
                topics.append(context.current_topic)
            
            # Extract topics from key facts
            for fact in context.key_facts:
                if isinstance(fact, str) and len(fact) < 100:
                    topics.append(fact)
            
            # Extract from extracted entities
            if context.extracted_entities:
                for key, value in context.extracted_entities.items():
                    if isinstance(value, str) and len(value) < 50:
                        topics.append(f"{key}: {value}")
        
        except ConversationContext.DoesNotExist:
            pass
        
        # Deduplicate and limit
        topics = list(dict.fromkeys(topics))[:10]
        
        logger.debug(
            f"Extracted {len(topics)} topics from conversation {conversation.id}"
        )
        
        return topics
    
    def _get_or_generate_summary(
        self,
        conversation: Conversation,
        messages: List[Message]
    ) -> Optional[str]:
        """
        Get existing summary or generate new one.
        
        Args:
            conversation: Conversation instance
            messages: Messages to summarize
            
        Returns:
            Summary text or None
        """
        # Try to get existing summary from context
        try:
            context = ConversationContext.objects.get(conversation=conversation)
            if context.conversation_summary:
                logger.debug(
                    f"Using existing summary for conversation {conversation.id}"
                )
                return context.conversation_summary
        except ConversationContext.DoesNotExist:
            pass
        
        # Generate new summary
        logger.info(
            f"Generating new summary for {len(messages)} messages "
            f"in conversation {conversation.id}"
        )
        
        summary = self.summary_service.generate_summary(messages)
        
        # Store summary in context
        if summary:
            context, created = ConversationContext.objects.get_or_create(
                conversation=conversation
            )
            context.conversation_summary = summary
            context.save(update_fields=['conversation_summary'])
            
            logger.info(
                f"Stored summary for conversation {conversation.id}: "
                f"{len(summary)} characters"
            )
        
        return summary


def create_conversation_history_service(
    summary_service: Optional[ConversationSummaryService] = None
) -> ConversationHistoryService:
    """
    Factory function to create ConversationHistoryService instance.
    
    Args:
        summary_service: Optional ConversationSummaryService instance
        
    Returns:
        ConversationHistoryService instance
    """
    return ConversationHistoryService(summary_service=summary_service)
