"""
Conversation Summary Service for generating summaries of long conversation histories.

Uses LLM to generate concise summaries that preserve key information while
reducing context window usage.
"""
import logging
from typing import List, Optional
from django.conf import settings
from openai import OpenAI

from apps.messaging.models import Message, Conversation
from apps.bot.models import ConversationContext

logger = logging.getLogger(__name__)


class ConversationSummaryService:
    """
    Service for generating conversation summaries using LLM.
    
    Summarizes long conversation histories to preserve key information
    while reducing token usage in context windows.
    """
    
    # Model configuration
    SUMMARY_MODEL = 'gpt-4o-mini'  # Cost-effective model for summaries
    SUMMARY_MAX_TOKENS = 500  # Maximum tokens for summary
    
    # Summary prompt template
    SUMMARY_PROMPT = """You are a helpful assistant that summarizes customer service conversations.

Summarize the following conversation between a customer and a business assistant. Focus on:
1. Key topics discussed
2. Customer needs and preferences
3. Products or services mentioned
4. Any pending actions or requests
5. Important facts to remember

Keep the summary concise (under 200 words) but preserve all important information.

Conversation:
{conversation_text}

Summary:"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Conversation Summary Service.
        
        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            logger.warning("OpenAI API key not configured, summary generation will fail")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
    
    def generate_summary(
        self,
        messages: List[Message],
        max_messages: Optional[int] = None
    ) -> Optional[str]:
        """
        Generate summary of conversation messages.
        
        Args:
            messages: List of Message instances to summarize
            max_messages: Optional limit on number of messages to include
            
        Returns:
            Summary text, or None on error
        """
        if not self.client:
            logger.error("OpenAI client not initialized, cannot generate summary")
            return None
        
        if not messages:
            logger.warning("No messages provided for summary")
            return None
        
        # Limit messages if specified
        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]
            logger.debug(f"Limited summary to last {max_messages} messages")
        
        try:
            # Format conversation text
            conversation_text = self._format_conversation(messages)
            
            # Generate summary using LLM
            prompt = self.SUMMARY_PROMPT.format(conversation_text=conversation_text)
            
            response = self.client.chat.completions.create(
                model=self.SUMMARY_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.SUMMARY_MAX_TOKENS,
                temperature=0.3  # Lower temperature for more focused summaries
            )
            
            summary = response.choices[0].message.content.strip()
            
            logger.info(
                f"Generated summary: {len(messages)} messages -> "
                f"{len(summary)} characters"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate conversation summary: {e}")
            return None
    
    def update_context_summary(
        self,
        conversation: Conversation,
        force: bool = False
    ) -> bool:
        """
        Update conversation context with generated summary.
        
        Generates summary from conversation history and stores it in
        ConversationContext for future use.
        
        Args:
            conversation: Conversation instance
            force: Force regeneration even if summary exists
            
        Returns:
            True if summary was updated, False otherwise
        """
        try:
            # Get or create context
            context, created = ConversationContext.objects.get_or_create(
                conversation=conversation
            )
            
            # Check if summary already exists and force is False
            if context.conversation_summary and not force:
                logger.debug(
                    f"Summary already exists for conversation {conversation.id}, "
                    "skipping (use force=True to regenerate)"
                )
                return False
            
            # Get conversation messages
            messages = Message.objects.filter(
                conversation=conversation
            ).order_by('created_at')
            
            if not messages.exists():
                logger.warning(f"No messages found for conversation {conversation.id}")
                return False
            
            # Generate summary
            summary = self.generate_summary(list(messages))
            
            if not summary:
                logger.error(f"Failed to generate summary for conversation {conversation.id}")
                return False
            
            # Update context
            context.conversation_summary = summary
            context.save(update_fields=['conversation_summary'])
            
            logger.info(
                f"Updated summary for conversation {conversation.id}: "
                f"{len(summary)} characters"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update context summary: {e}")
            return False
    
    def summarize_old_messages(
        self,
        conversation: Conversation,
        cutoff_message_count: int = 20
    ) -> Optional[str]:
        """
        Summarize old messages beyond a cutoff point.
        
        Useful for maintaining context while keeping recent messages
        in full detail.
        
        Args:
            conversation: Conversation instance
            cutoff_message_count: Number of recent messages to exclude from summary
            
        Returns:
            Summary of old messages, or None if not enough messages
        """
        # Get all messages
        all_messages = Message.objects.filter(
            conversation=conversation
        ).order_by('created_at')
        
        total_count = all_messages.count()
        
        # Check if we have enough messages to summarize
        if total_count <= cutoff_message_count:
            logger.debug(
                f"Not enough messages to summarize: {total_count} <= {cutoff_message_count}"
            )
            return None
        
        # Get old messages (everything except recent ones)
        old_messages = list(all_messages[:total_count - cutoff_message_count])
        
        logger.info(
            f"Summarizing {len(old_messages)} old messages "
            f"(keeping {cutoff_message_count} recent)"
        )
        
        # Generate summary
        return self.generate_summary(old_messages)
    
    def _format_conversation(self, messages: List[Message]) -> str:
        """
        Format messages into conversation text.
        
        Args:
            messages: List of Message instances
            
        Returns:
            Formatted conversation text
        """
        lines = []
        
        for msg in messages:
            # Determine speaker
            if msg.direction == 'in':
                speaker = "Customer"
            else:
                speaker = "Assistant"
            
            # Format message
            lines.append(f"{speaker}: {msg.text}")
        
        return "\n".join(lines)


def create_conversation_summary_service(
    api_key: Optional[str] = None
) -> ConversationSummaryService:
    """
    Factory function to create ConversationSummaryService instance.
    
    Args:
        api_key: Optional OpenAI API key (defaults to settings)
        
    Returns:
        ConversationSummaryService instance
    """
    return ConversationSummaryService(api_key=api_key)
