"""
Consent intent handlers for customer communication preferences.

Handles customer intents related to:
- Opting in to promotional messages
- Opting out of promotional messages
- Stopping all non-essential messages (STOP, UNSUBSCRIBE)
- Resuming all messages (START)
"""
import logging
from typing import Dict, Any
from apps.messaging.services import ConsentService

logger = logging.getLogger(__name__)


class ConsentHandlerError(Exception):
    """Base exception for consent handler errors."""
    pass


class ConsentIntentHandler:
    """
    Handler for consent-related customer intents.
    
    Processes classified consent intents and updates customer preferences
    with appropriate confirmation messages.
    """
    
    def __init__(self, tenant, conversation, twilio_service):
        """
        Initialize consent handler.
        
        Args:
            tenant: Tenant model instance
            conversation: Conversation model instance
            twilio_service: TwilioService instance for sending messages
        """
        self.tenant = tenant
        self.conversation = conversation
        self.customer = conversation.customer
        self.twilio_service = twilio_service
    
    def handle_opt_in_promotions(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle OPT_IN_PROMOTIONS intent.
        
        Customer wants to receive promotional messages.
        Keywords: "start promotions", "yes to offers", "send me deals"
        
        Args:
            slots: Extracted slots from intent classification
            
        Returns:
            dict: Response with confirmation message
        """
        try:
            # Update consent preference
            prefs, event = ConsentService.update_consent(
                tenant=self.tenant,
                customer=self.customer,
                consent_type='promotional_messages',
                value=True,
                source='customer_initiated',
                reason='Customer opted in via WhatsApp message'
            )
            
            # Build confirmation message
            message = "✅ Great! You're now subscribed to promotional messages.\n\n"
            message += "You'll receive:\n"
            message += "• Special offers and discounts\n"
            message += "• New product announcements\n"
            message += "• Exclusive deals\n\n"
            message += "You can opt out anytime by replying 'stop promotions'."
            
            logger.info(
                f"Customer {self.customer.id} opted in to promotions",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                }
            )
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response',
                'consent_updated': True,
                'consent_type': 'promotional_messages',
                'consent_value': True
            }
            
        except Exception as e:
            logger.error(
                f"Error handling opt-in promotions",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                },
                exc_info=True
            )
            raise ConsentHandlerError(f"Failed to opt in to promotions: {str(e)}")
    
    def handle_opt_out_promotions(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle OPT_OUT_PROMOTIONS intent.
        
        Customer wants to stop receiving promotional messages.
        Keywords: "stop promotions", "no more offers", "unsubscribe from deals"
        
        Args:
            slots: Extracted slots from intent classification
            
        Returns:
            dict: Response with confirmation message
        """
        try:
            # Update consent preference
            prefs, event = ConsentService.update_consent(
                tenant=self.tenant,
                customer=self.customer,
                consent_type='promotional_messages',
                value=False,
                source='customer_initiated',
                reason='Customer opted out via WhatsApp message'
            )
            
            # Build confirmation message
            message = "✅ You've been unsubscribed from promotional messages.\n\n"
            message += "You will no longer receive:\n"
            message += "• Special offers and discounts\n"
            message += "• Marketing campaigns\n\n"
            message += "You'll still receive:\n"
            message += "• Order confirmations\n"
            message += "• Appointment reminders\n"
            message += "• Important account updates\n\n"
            message += "To resume promotional messages, reply 'start promotions'."
            
            logger.info(
                f"Customer {self.customer.id} opted out of promotions",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                }
            )
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response',
                'consent_updated': True,
                'consent_type': 'promotional_messages',
                'consent_value': False
            }
            
        except Exception as e:
            logger.error(
                f"Error handling opt-out promotions",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                },
                exc_info=True
            )
            raise ConsentHandlerError(f"Failed to opt out of promotions: {str(e)}")
    
    def handle_stop_all(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle STOP_ALL intent.
        
        Customer wants to stop all non-essential messages.
        Keywords: "STOP", "UNSUBSCRIBE"
        
        This opts out of promotional and reminder messages but keeps
        transactional messages (order updates, payment confirmations).
        
        Args:
            slots: Extracted slots from intent classification
            
        Returns:
            dict: Response with confirmation message
        """
        try:
            # Opt out of all optional message types
            prefs = ConsentService.opt_out_all(
                tenant=self.tenant,
                customer=self.customer,
                source='customer_initiated',
                reason='Customer sent STOP/UNSUBSCRIBE command'
            )
            
            # Build confirmation message
            message = "✅ You have been unsubscribed from promotional and reminder messages.\n\n"
            message += "You will no longer receive:\n"
            message += "• Promotional offers\n"
            message += "• Appointment reminders\n"
            message += "• Marketing campaigns\n\n"
            message += "You'll still receive essential messages:\n"
            message += "• Order confirmations\n"
            message += "• Payment updates\n"
            message += "• Important account notifications\n\n"
            message += "To resume messages, reply 'START'."
            
            logger.info(
                f"Customer {self.customer.id} stopped all optional messages",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                }
            )
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response',
                'consent_updated': True,
                'consent_type': 'all_optional',
                'consent_value': False
            }
            
        except Exception as e:
            logger.error(
                f"Error handling stop all",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                },
                exc_info=True
            )
            raise ConsentHandlerError(f"Failed to stop all messages: {str(e)}")
    
    def handle_start_all(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle START_ALL intent.
        
        Customer wants to resume all messages after opting out.
        Keyword: "START"
        
        This opts back in to promotional and reminder messages.
        
        Args:
            slots: Extracted slots from intent classification
            
        Returns:
            dict: Response with confirmation message
        """
        try:
            # Opt in to all message types
            prefs = ConsentService.opt_in_all(
                tenant=self.tenant,
                customer=self.customer,
                source='customer_initiated',
                reason='Customer sent START command'
            )
            
            # Build confirmation message
            message = "✅ Welcome back! You're now subscribed to all messages.\n\n"
            message += "You'll receive:\n"
            message += "• Order confirmations and updates\n"
            message += "• Appointment reminders\n"
            message += "• Promotional offers and deals\n"
            message += "• Marketing campaigns\n\n"
            message += "You can manage your preferences anytime:\n"
            message += "• Reply 'stop promotions' to opt out of marketing\n"
            message += "• Reply 'STOP' to opt out of all optional messages"
            
            logger.info(
                f"Customer {self.customer.id} resumed all messages",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                }
            )
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response',
                'consent_updated': True,
                'consent_type': 'all_optional',
                'consent_value': True
            }
            
        except Exception as e:
            logger.error(
                f"Error handling start all",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'customer_id': str(self.customer.id)
                },
                exc_info=True
            )
            raise ConsentHandlerError(f"Failed to start all messages: {str(e)}")
    
    def route_intent(self, intent_name: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route consent intent to appropriate handler.
        
        Args:
            intent_name: Classified intent name
            slots: Extracted slots
            
        Returns:
            dict: Handler response
            
        Raises:
            ConsentHandlerError: If intent is not supported
        """
        handlers = {
            'OPT_IN_PROMOTIONS': self.handle_opt_in_promotions,
            'OPT_OUT_PROMOTIONS': self.handle_opt_out_promotions,
            'STOP_ALL': self.handle_stop_all,
            'START_ALL': self.handle_start_all,
        }
        
        handler = handlers.get(intent_name)
        if not handler:
            raise ConsentHandlerError(f"Unsupported consent intent: {intent_name}")
        
        return handler(slots)


def create_consent_handler(tenant, conversation, twilio_service) -> ConsentIntentHandler:
    """
    Factory function to create ConsentIntentHandler instance.
    
    Args:
        tenant: Tenant model instance
        conversation: Conversation model instance
        twilio_service: TwilioService instance
        
    Returns:
        ConsentIntentHandler: Configured handler instance
    """
    return ConsentIntentHandler(tenant, conversation, twilio_service)
