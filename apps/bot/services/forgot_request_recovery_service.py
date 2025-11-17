"""
Forgot Request Recovery Service.

Handles detection and recovery of forgotten or unanswered customer requests.
Detects phrases like "did you forget" and retrieves the last unanswered question.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import timedelta
from django.utils import timezone

from apps.messaging.models import Conversation, Message
from apps.bot.models import ConversationContext, AgentInteraction

logger = logging.getLogger(__name__)


class ForgotRequestRecoveryService:
    """
    Service for recovering forgotten or unanswered customer requests.
    
    Detects when customers indicate the agent forgot their request and
    retrieves the last unanswered question to address it properly.
    
    Requirements: 22.4, 22.5
    """
    
    # Phrases that indicate forgotten request
    FORGOT_PHRASES = [
        'did you forget',
        'you forgot',
        'didn\'t answer',
        'ignored my',
        'what about',
        'still waiting',
        'never answered',
        'didn\'t respond',
        'no response',
        'forgot to',
        'missed my',
    ]
    
    # Time window to look back for unanswered questions (in minutes)
    LOOKBACK_WINDOW_MINUTES = 60
    
    # Question indicators
    QUESTION_INDICATORS = ['?', 'how', 'what', 'when', 'where', 'why', 'who', 'can you', 'could you', 'would you']
    
    def __init__(self):
        """Initialize Forgot Request Recovery Service."""
        self.recovery_count = 0
        self.success_count = 0
    
    def detect_forgot_request(self, message_text: str) -> bool:
        """
        Detect if message indicates a forgotten request.
        
        Checks for phrases like:
        - "did you forget"
        - "you didn't answer"
        - "what about my question"
        - etc.
        
        Args:
            message_text: Customer message text
            
        Returns:
            True if forgot request detected, False otherwise
        """
        message_lower = message_text.lower()
        
        for phrase in self.FORGOT_PHRASES:
            if phrase in message_lower:
                logger.info(
                    f"Forgot request detected with phrase: '{phrase}'"
                )
                return True
        
        return False
    
    def retrieve_last_unanswered_question(
        self,
        conversation: Conversation,
        lookback_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the last unanswered question from conversation history.
        
        Searches recent conversation history for customer questions that
        may not have been adequately addressed by the agent.
        
        Args:
            conversation: Conversation instance
            lookback_minutes: How far back to look (default: 60 minutes)
            
        Returns:
            Dict with unanswered question details, or None if not found
        """
        if lookback_minutes is None:
            lookback_minutes = self.LOOKBACK_WINDOW_MINUTES
        
        try:
            # Calculate lookback time
            lookback_time = timezone.now() - timedelta(minutes=lookback_minutes)
            
            # Get recent customer messages (inbound only)
            recent_messages = Message.objects.filter(
                conversation=conversation,
                direction='in',
                created_at__gte=lookback_time
            ).order_by('-created_at')[:20]  # Last 20 messages
            
            # Find questions
            questions = []
            for msg in recent_messages:
                if self._is_question(msg.text):
                    questions.append({
                        'message': msg,
                        'text': msg.text,
                        'created_at': msg.created_at,
                        'time_ago_minutes': (timezone.now() - msg.created_at).total_seconds() / 60
                    })
            
            if not questions:
                logger.debug(
                    f"No questions found in recent history for conversation {conversation.id}"
                )
                return None
            
            # Check if questions were answered
            for question in questions:
                was_answered = self._check_if_answered(
                    conversation=conversation,
                    question_message=question['message']
                )
                
                if not was_answered:
                    logger.info(
                        f"Found unanswered question from {question['time_ago_minutes']:.1f} minutes ago: "
                        f"'{question['text'][:50]}...'"
                    )
                    return question
            
            logger.debug(
                f"All recent questions appear to have been answered for conversation {conversation.id}"
            )
            return None
            
        except Exception as e:
            logger.error(
                f"Error retrieving unanswered question: {e}",
                exc_info=True
            )
            return None
    
    def generate_recovery_response(
        self,
        unanswered_question: Dict[str, Any],
        conversation: Conversation
    ) -> str:
        """
        Generate recovery response for forgotten request.
        
        Creates an apologetic response that:
        1. Acknowledges the oversight
        2. References the specific question
        3. Indicates the agent will now address it
        
        Args:
            unanswered_question: Dict with question details
            conversation: Conversation instance
            
        Returns:
            Recovery response message
        """
        try:
            # Get customer name if available
            customer_name = ""
            if hasattr(conversation.customer, 'name') and conversation.customer.name:
                customer_name = f" {conversation.customer.name}"
            
            # Calculate time ago
            time_ago_minutes = unanswered_question['time_ago_minutes']
            
            if time_ago_minutes < 5:
                time_str = "just now"
            elif time_ago_minutes < 60:
                time_str = f"{int(time_ago_minutes)} minutes ago"
            else:
                time_str = f"{int(time_ago_minutes / 60)} hours ago"
            
            # Build recovery response
            question_text = unanswered_question['text']
            
            response = (
                f"I apologize{customer_name}! 🙏\n\n"
                f"You're right - I didn't properly address your question from {time_str}:\n\n"
                f"\"{question_text}\"\n\n"
                f"Let me help you with that now."
            )
            
            logger.info(
                f"Generated recovery response for conversation {conversation.id}"
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error generating recovery response: {e}",
                exc_info=True
            )
            return "I apologize! Let me help you with your question."
    
    def track_recovery_attempt(
        self,
        conversation: Conversation,
        unanswered_question: Optional[Dict[str, Any]],
        success: bool
    ) -> None:
        """
        Track recovery attempt for analytics.
        
        Records:
        - Whether unanswered question was found
        - Whether recovery was successful
        - Time since original question
        
        Args:
            conversation: Conversation instance
            unanswered_question: Dict with question details (or None)
            success: Whether recovery was successful
        """
        try:
            self.recovery_count += 1
            
            if success:
                self.success_count += 1
            
            # Store in conversation context for future reference
            context = ConversationContext.objects.filter(
                conversation=conversation
            ).first()
            
            if context:
                # Add recovery attempt to key facts
                if unanswered_question:
                    recovery_fact = (
                        f"Recovery: Addressed forgotten question from "
                        f"{unanswered_question['time_ago_minutes']:.1f} minutes ago"
                    )
                else:
                    recovery_fact = "Recovery: Attempted but no unanswered question found"
                
                context.add_key_fact(recovery_fact)
            
            logger.info(
                f"Recovery attempt tracked: success={success}, "
                f"total_attempts={self.recovery_count}, "
                f"success_rate={self.get_success_rate():.2%}"
            )
            
        except Exception as e:
            logger.error(
                f"Error tracking recovery attempt: {e}",
                exc_info=True
            )
    
    def get_success_rate(self) -> float:
        """
        Get recovery success rate.
        
        Returns:
            Success rate as float (0.0 to 1.0)
        """
        if self.recovery_count == 0:
            return 0.0
        
        return self.success_count / self.recovery_count
    
    def _is_question(self, text: str) -> bool:
        """
        Check if text is a question.
        
        Args:
            text: Message text
            
        Returns:
            True if text appears to be a question
        """
        text_lower = text.lower()
        
        # Check for question mark
        if '?' in text:
            return True
        
        # Check for question indicators
        for indicator in self.QUESTION_INDICATORS:
            if text_lower.startswith(indicator) or f" {indicator}" in text_lower:
                return True
        
        return False
    
    def _check_if_answered(
        self,
        conversation: Conversation,
        question_message: Message
    ) -> bool:
        """
        Check if a question was answered by the agent.
        
        Looks for agent responses after the question that:
        1. Were sent within reasonable time
        2. Have reasonable length (not just acknowledgment)
        3. Have high confidence score
        
        Args:
            conversation: Conversation instance
            question_message: Message containing the question
            
        Returns:
            True if question appears to have been answered
        """
        try:
            # Get agent responses after the question
            responses = Message.objects.filter(
                conversation=conversation,
                direction='out',
                created_at__gt=question_message.created_at,
                created_at__lt=question_message.created_at + timedelta(minutes=5)
            ).order_by('created_at')
            
            if not responses.exists():
                logger.debug(
                    f"No agent responses found after question message {question_message.id}"
                )
                return False
            
            # Check if any response is substantial
            for response in responses:
                # Check response length (substantial answer)
                if len(response.text) > 50:
                    # Check if there's a corresponding agent interaction with high confidence
                    interaction = AgentInteraction.objects.filter(
                        conversation=conversation,
                        created_at__gte=question_message.created_at,
                        created_at__lte=response.created_at + timedelta(seconds=30)
                    ).order_by('-confidence_score').first()
                    
                    if interaction and interaction.confidence_score >= 0.7:
                        logger.debug(
                            f"Question appears answered with high confidence "
                            f"(score: {interaction.confidence_score:.2f})"
                        )
                        return True
            
            logger.debug(
                f"Responses found but none appear substantial or confident enough"
            )
            return False
            
        except Exception as e:
            logger.error(
                f"Error checking if question was answered: {e}",
                exc_info=True
            )
            # Assume answered to avoid false positives
            return True


def create_forgot_request_recovery_service() -> ForgotRequestRecoveryService:
    """
    Factory function to create ForgotRequestRecoveryService instance.
    
    Returns:
        ForgotRequestRecoveryService instance
    """
    return ForgotRequestRecoveryService()
