"""
Human handoff handler for escalating conversations to human agents.

Handles customer requests for human assistance and automatic handoff
when the bot cannot understand customer intent.
"""
import logging
from typing import Dict, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


class HandoffHandlerError(Exception):
    """Base exception for handoff handler errors."""
    pass


class HandoffHandler:
    """
    Handler for human handoff intent.
    
    Manages the transition from bot to human agent handling,
    updates conversation status, and sends appropriate messages.
    """
    
    def __init__(self, tenant, conversation, twilio_service):
        """
        Initialize handoff handler.
        
        Args:
            tenant: Tenant model instance
            conversation: Conversation model instance
            twilio_service: TwilioService instance for sending messages
        """
        self.tenant = tenant
        self.conversation = conversation
        self.customer = conversation.customer
        self.twilio_service = twilio_service
    
    def handle_human_handoff(self, slots: Dict[str, Any], reason: str = 'customer_requested') -> Dict[str, Any]:
        """
        Handle HUMAN_HANDOFF intent.
        
        Updates conversation status to 'handoff' and sends confirmation
        message to customer.
        
        Args:
            slots: Extracted slots from intent classification
            reason: Reason for handoff (customer_requested, low_confidence, error)
            
        Returns:
            dict: Response with handoff confirmation message
        """
        # Mark conversation for handoff
        self.conversation.mark_handoff()
        
        logger.info(
            f"Conversation handed off to human agent",
            extra={
                'conversation_id': str(self.conversation.id),
                'tenant_id': str(self.tenant.id),
                'customer_id': str(self.customer.id),
                'reason': reason
            }
        )
        
        # Generate appropriate message based on reason
        if reason == 'customer_requested':
            message = "I understand you'd like to speak with someone from our team. 👤\n\n"
            message += "I'm connecting you with a team member who will assist you shortly.\n\n"
            message += "Thank you for your patience!"
        
        elif reason == 'low_confidence':
            message = "I'm having trouble understanding your request. 🤔\n\n"
            message += "Let me connect you with a team member who can better assist you.\n\n"
            message += "Someone will be with you shortly!"
        
        elif reason == 'error':
            message = "I encountered an issue processing your request. 😔\n\n"
            message += "I'm connecting you with a team member who can help.\n\n"
            message += "Thank you for your patience!"
        
        else:
            message = "I'm connecting you with a team member who can assist you.\n\n"
            message += "Someone will be with you shortly!"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'handoff_reason': reason,
                'handoff_at': timezone.now().isoformat()
            }
        }
    
    def handle_automatic_handoff(self, low_confidence_count: int) -> Dict[str, Any]:
        """
        Handle automatic handoff after consecutive low-confidence intents.
        
        Args:
            low_confidence_count: Number of consecutive low-confidence attempts
            
        Returns:
            dict: Response with handoff message
        """
        return self.handle_human_handoff(
            slots={},
            reason='low_confidence'
        )
    
    def is_handoff_active(self) -> bool:
        """
        Check if conversation is currently in handoff status.
        
        Returns:
            bool: True if conversation is in handoff status
        """
        return self.conversation.status == 'handoff'
    
    def prevent_bot_processing(self) -> Dict[str, Any]:
        """
        Generate response when bot processing is prevented due to handoff.
        
        Returns:
            dict: Response indicating conversation is with human agent
        """
        message = "Your conversation is currently being handled by our team. 👤\n\n"
        message += "A team member will respond to you shortly."
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'handoff_active': True
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
                    f"Handoff handler response sent",
                    extra={
                        'conversation_id': str(self.conversation.id),
                        'message_sid': result['sid']
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to send handoff handler response",
                    extra={'conversation_id': str(self.conversation.id)},
                    exc_info=True
                )
                raise HandoffHandlerError(f"Failed to send response: {str(e)}")


def create_handoff_handler(tenant, conversation, twilio_service) -> HandoffHandler:
    """
    Factory function to create HandoffHandler instance.
    
    Args:
        tenant: Tenant model instance
        conversation: Conversation model instance
        twilio_service: TwilioService instance
        
    Returns:
        HandoffHandler: Configured handler instance
    """
    return HandoffHandler(tenant, conversation, twilio_service)
