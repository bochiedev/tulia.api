"""
Context Restoration Service for returning customers.

Handles detection of returning customers after pauses and restores
relevant context from previous sessions with appropriate acknowledgment.
"""
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import timedelta
from django.utils import timezone

from apps.messaging.models import Conversation, Message
from apps.bot.models import ConversationContext

logger = logging.getLogger(__name__)


class ContextRestorationService:
    """
    Service for restoring context when customers return after pauses.
    
    Detects when a customer returns after a pause (context expired but
    key facts preserved) and offers to restore the previous conversation
    context or start fresh.
    
    Requirements: 22.2, 22.3, 22.4
    """
    
    # Pause detection thresholds
    SHORT_PAUSE_MINUTES = 30  # Context expired but recent
    LONG_PAUSE_HOURS = 24  # Significant time gap
    
    def __init__(self):
        """Initialize Context Restoration Service."""
        pass
    
    def detect_returning_customer(
        self,
        conversation: Conversation,
        current_message: Message
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if customer is returning after a pause.
        
        Checks:
        1. Is there an expired context with key facts?
        2. How long has it been since last interaction?
        3. Is the current message a continuation or new topic?
        
        Args:
            conversation: Conversation instance
            current_message: Current message from customer
            
        Returns:
            Tuple of (is_returning, pause_type)
            - is_returning: True if customer is returning after pause
            - pause_type: 'short' (30min-24hr), 'long' (>24hr), or None
        """
        try:
            # Get conversation context
            context = ConversationContext.objects.filter(
                conversation=conversation
            ).first()
            
            if not context:
                logger.debug(
                    f"No context found for conversation {conversation.id}, "
                    f"not a returning customer"
                )
                return False, None
            
            # Check if context has expired
            if not context.is_expired():
                logger.debug(
                    f"Context not expired for conversation {conversation.id}, "
                    f"not a returning customer"
                )
                return False, None
            
            # Check if there are key facts to restore
            if not context.key_facts or len(context.key_facts) == 0:
                logger.debug(
                    f"No key facts to restore for conversation {conversation.id}"
                )
                return False, None
            
            # Calculate time since last interaction
            time_since_last = timezone.now() - context.last_interaction
            
            # Determine pause type
            if time_since_last <= timedelta(hours=24):
                pause_type = 'short'
            else:
                pause_type = 'long'
            
            logger.info(
                f"Returning customer detected for conversation {conversation.id}, "
                f"pause_type={pause_type}, time_since_last={time_since_last}, "
                f"key_facts_count={len(context.key_facts)}"
            )
            
            return True, pause_type
            
        except Exception as e:
            logger.error(
                f"Error detecting returning customer: {e}",
                exc_info=True
            )
            return False, None
    
    def restore_context(
        self,
        conversation: Conversation,
        acknowledge: bool = True
    ) -> Dict[str, Any]:
        """
        Restore context for returning customer.
        
        Restores the previous conversation context including:
        - Current topic
        - Pending actions
        - Extracted entities
        - Last viewed items
        - Key facts
        
        Args:
            conversation: Conversation instance
            acknowledge: Whether to generate acknowledgment message
            
        Returns:
            Dict with restoration details and optional acknowledgment
        """
        try:
            # Get conversation context
            context = ConversationContext.objects.filter(
                conversation=conversation
            ).first()
            
            if not context:
                logger.warning(
                    f"No context to restore for conversation {conversation.id}"
                )
                return {
                    'restored': False,
                    'reason': 'no_context_found'
                }
            
            # Build restoration summary
            restoration_summary = {
                'key_facts': context.key_facts.copy() if context.key_facts else [],
                'last_interaction': context.last_interaction,
                'time_since_last': (timezone.now() - context.last_interaction).total_seconds() / 60,  # minutes
            }
            
            # Extend context expiration (reactivate)
            context.extend_expiration(minutes=30)
            
            # Generate acknowledgment message if requested
            acknowledgment = None
            if acknowledge:
                acknowledgment = self._generate_acknowledgment(
                    context=context,
                    restoration_summary=restoration_summary
                )
            
            logger.info(
                f"Context restored for conversation {conversation.id}, "
                f"key_facts_count={len(restoration_summary['key_facts'])}"
            )
            
            return {
                'restored': True,
                'restoration_summary': restoration_summary,
                'acknowledgment': acknowledgment,
                'context_id': str(context.id)
            }
            
        except Exception as e:
            logger.error(
                f"Error restoring context for conversation {conversation.id}: {e}",
                exc_info=True
            )
            return {
                'restored': False,
                'reason': 'error',
                'error': str(e)
            }
    
    def generate_restoration_greeting(
        self,
        conversation: Conversation,
        pause_type: str
    ) -> str:
        """
        Generate greeting for returning customer.
        
        Creates a personalized greeting that:
        1. Acknowledges the previous conversation
        2. References the previous topic if available
        3. Offers to continue or start fresh
        
        Args:
            conversation: Conversation instance
            pause_type: Type of pause ('short' or 'long')
            
        Returns:
            Greeting message string
        """
        try:
            # Get conversation context
            context = ConversationContext.objects.filter(
                conversation=conversation
            ).first()
            
            if not context:
                return "Welcome back! How can I help you today?"
            
            # Get customer name if available
            customer_name = ""
            if hasattr(conversation.customer, 'name') and conversation.customer.name:
                customer_name = f" {conversation.customer.name}"
            
            # Build greeting based on pause type and context
            if pause_type == 'short':
                # Short pause - acknowledge recent conversation
                if context.key_facts and len(context.key_facts) > 0:
                    # Reference the previous topic
                    first_fact = context.key_facts[0]
                    greeting = (
                        f"Welcome back{customer_name}! 👋\n\n"
                        f"I remember we were discussing: {first_fact}\n\n"
                        f"Would you like to continue where we left off, or is there something new I can help you with?"
                    )
                else:
                    greeting = (
                        f"Welcome back{customer_name}! 👋\n\n"
                        f"How can I help you today?"
                    )
            
            else:  # long pause
                # Long pause - acknowledge but don't assume continuation
                if context.key_facts and len(context.key_facts) > 0:
                    greeting = (
                        f"Welcome back{customer_name}! 👋\n\n"
                        f"It's been a while since we last chatted. "
                        f"I still have some notes from our previous conversation if you'd like to continue, "
                        f"or we can start fresh. How can I help you today?"
                    )
                else:
                    greeting = (
                        f"Welcome back{customer_name}! 👋\n\n"
                        f"How can I help you today?"
                    )
            
            logger.debug(
                f"Generated restoration greeting for conversation {conversation.id}, "
                f"pause_type={pause_type}"
            )
            
            return greeting
            
        except Exception as e:
            logger.error(
                f"Error generating restoration greeting: {e}",
                exc_info=True
            )
            return "Welcome back! How can I help you today?"
    
    def should_offer_continuation(
        self,
        conversation: Conversation,
        current_message_text: str
    ) -> bool:
        """
        Determine if we should offer to continue previous conversation.
        
        Analyzes the current message to see if it's likely a continuation
        of the previous topic or a new inquiry.
        
        Args:
            conversation: Conversation instance
            current_message_text: Text of current message
            
        Returns:
            True if should offer continuation, False otherwise
        """
        try:
            # Get conversation context
            context = ConversationContext.objects.filter(
                conversation=conversation
            ).first()
            
            if not context or not context.key_facts:
                return False
            
            # Check if message contains continuation indicators
            continuation_phrases = [
                'continue', 'still', 'about that', 'regarding',
                'the same', 'as before', 'previous', 'earlier'
            ]
            
            message_lower = current_message_text.lower()
            
            for phrase in continuation_phrases:
                if phrase in message_lower:
                    logger.debug(
                        f"Continuation phrase '{phrase}' detected in message"
                    )
                    return True
            
            # Check if message is very short (likely continuation)
            if len(current_message_text.split()) <= 3:
                logger.debug(
                    f"Short message detected, likely continuation"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                f"Error determining continuation offer: {e}",
                exc_info=True
            )
            return False
    
    def _generate_acknowledgment(
        self,
        context: ConversationContext,
        restoration_summary: Dict[str, Any]
    ) -> str:
        """
        Generate acknowledgment message for context restoration.
        
        Args:
            context: ConversationContext instance
            restoration_summary: Summary of restored context
            
        Returns:
            Acknowledgment message string
        """
        # Calculate time since last interaction
        minutes_since = restoration_summary['time_since_last']
        
        if minutes_since < 60:
            time_str = f"{int(minutes_since)} minutes"
        elif minutes_since < 1440:  # 24 hours
            time_str = f"{int(minutes_since / 60)} hours"
        else:
            time_str = f"{int(minutes_since / 1440)} days"
        
        # Build acknowledgment
        if context.key_facts and len(context.key_facts) > 0:
            acknowledgment = (
                f"I've restored our previous conversation from {time_str} ago. "
                f"I remember: {context.key_facts[0]}"
            )
        else:
            acknowledgment = (
                f"I've restored our previous conversation from {time_str} ago."
            )
        
        return acknowledgment


def create_context_restoration_service() -> ContextRestorationService:
    """
    Factory function to create ContextRestorationService instance.
    
    Returns:
        ContextRestorationService instance
    """
    return ContextRestorationService()
