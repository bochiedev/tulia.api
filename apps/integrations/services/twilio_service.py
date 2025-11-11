"""
Twilio integration service for WhatsApp messaging.

Handles sending and receiving WhatsApp messages via Twilio API,
including signature verification for webhook security.
"""
import hashlib
import hmac
import base64
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings

logger = logging.getLogger(__name__)


class TwilioServiceError(Exception):
    """Base exception for Twilio service errors."""
    pass


class TwilioService:
    """
    Service for interacting with Twilio WhatsApp API.
    
    Provides methods for:
    - Sending WhatsApp messages
    - Sending template messages
    - Verifying webhook signatures
    - Handling delivery status callbacks
    """
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        """
        Initialize Twilio service with credentials.
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: WhatsApp sender number (e.g., whatsapp:+14155238886)
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number if from_number.startswith('whatsapp:') else f'whatsapp:{from_number}'
        self.client = Client(account_sid, auth_token)
    
    def send_whatsapp(
        self,
        to: str,
        body: str,
        media_url: Optional[str] = None,
        status_callback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message via Twilio.
        
        Args:
            to: Recipient phone number in E.164 format
            body: Message text content
            media_url: Optional URL for media attachment
            status_callback: Optional URL for delivery status callbacks
            
        Returns:
            dict: Message details including SID and status
            
        Raises:
            TwilioServiceError: If message sending fails
            
        Example:
            >>> service = TwilioService(sid, token, '+14155238886')
            >>> result = service.send_whatsapp('+1234567890', 'Hello!')
            >>> print(result['sid'])
        """
        try:
            # Format recipient number
            to_number = to if to.startswith('whatsapp:') else f'whatsapp:{to}'
            
            # Prepare message parameters
            message_params = {
                'from_': self.from_number,
                'to': to_number,
                'body': body
            }
            
            if media_url:
                message_params['media_url'] = [media_url]
            
            if status_callback:
                message_params['status_callback'] = status_callback
            
            # Send message
            message = self.client.messages.create(**message_params)
            
            logger.info(
                f"WhatsApp message sent successfully",
                extra={
                    'message_sid': message.sid,
                    'to': to,
                    'status': message.status
                }
            )
            
            return {
                'sid': message.sid,
                'status': message.status,
                'to': to,
                'from': self.from_number,
                'body': body,
                'date_created': message.date_created.isoformat() if message.date_created else None,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
        except TwilioRestException as e:
            logger.error(
                f"Twilio API error sending WhatsApp message",
                extra={
                    'error_code': e.code,
                    'error_message': str(e),
                    'to': to
                },
                exc_info=True
            )
            raise TwilioServiceError(f"Failed to send WhatsApp message: {e.msg}") from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error sending WhatsApp message",
                extra={'to': to},
                exc_info=True
            )
            raise TwilioServiceError(f"Unexpected error: {str(e)}") from e
    
    def send_template(
        self,
        to: str,
        template_sid: str,
        variables: Optional[Dict[str, str]] = None,
        status_callback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp template message via Twilio.
        
        Template messages are pre-approved by WhatsApp and can be sent
        outside the 24-hour messaging window.
        
        Args:
            to: Recipient phone number in E.164 format
            template_sid: Twilio Content Template SID
            variables: Optional template variables for personalization
            status_callback: Optional URL for delivery status callbacks
            
        Returns:
            dict: Message details including SID and status
            
        Raises:
            TwilioServiceError: If template message sending fails
            
        Example:
            >>> service = TwilioService(sid, token, '+14155238886')
            >>> result = service.send_template(
            ...     '+1234567890',
            ...     'HX1234567890abcdef',
            ...     {'1': 'John', '2': '2025-11-15'}
            ... )
        """
        try:
            # Format recipient number
            to_number = to if to.startswith('whatsapp:') else f'whatsapp:{to}'
            
            # Prepare message parameters
            message_params = {
                'from_': self.from_number,
                'to': to_number,
                'content_sid': template_sid
            }
            
            # Add template variables if provided
            if variables:
                message_params['content_variables'] = variables
            
            if status_callback:
                message_params['status_callback'] = status_callback
            
            # Send template message
            message = self.client.messages.create(**message_params)
            
            logger.info(
                f"WhatsApp template message sent successfully",
                extra={
                    'message_sid': message.sid,
                    'to': to,
                    'template_sid': template_sid,
                    'status': message.status
                }
            )
            
            return {
                'sid': message.sid,
                'status': message.status,
                'to': to,
                'from': self.from_number,
                'template_sid': template_sid,
                'date_created': message.date_created.isoformat() if message.date_created else None,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
        except TwilioRestException as e:
            logger.error(
                f"Twilio API error sending template message",
                extra={
                    'error_code': e.code,
                    'error_message': str(e),
                    'to': to,
                    'template_sid': template_sid
                },
                exc_info=True
            )
            raise TwilioServiceError(f"Failed to send template message: {e.msg}") from e
        
        except Exception as e:
            logger.error(
                f"Unexpected error sending template message",
                extra={'to': to, 'template_sid': template_sid},
                exc_info=True
            )
            raise TwilioServiceError(f"Unexpected error: {str(e)}") from e
    
    def verify_signature(
        self,
        url: str,
        params: Dict[str, Any],
        signature: str,
        auth_token: Optional[str] = None
    ) -> bool:
        """
        Verify Twilio webhook signature for security.
        
        Validates that the webhook request came from Twilio by comparing
        the X-Twilio-Signature header with a computed signature.
        
        Args:
            url: Full webhook URL including protocol and domain
            params: POST parameters from the webhook request
            signature: X-Twilio-Signature header value
            auth_token: Optional auth token (uses instance token if not provided)
            
        Returns:
            bool: True if signature is valid, False otherwise
            
        Example:
            >>> service = TwilioService(sid, token, '+14155238886')
            >>> is_valid = service.verify_signature(
            ...     'https://example.com/webhooks/twilio',
            ...     request.POST.dict(),
            ...     request.META.get('HTTP_X_TWILIO_SIGNATURE')
            ... )
        """
        try:
            token = auth_token or self.auth_token
            
            # Sort parameters and create query string
            sorted_params = sorted(params.items())
            data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
            
            # Compute HMAC-SHA1 signature
            computed_signature = hmac.new(
                token.encode('utf-8'),
                data.encode('utf-8'),
                hashlib.sha1
            ).digest()
            
            # Base64 encode the signature
            computed_signature_b64 = base64.b64encode(computed_signature).decode('utf-8')
            
            # Compare signatures
            is_valid = hmac.compare_digest(computed_signature_b64, signature)
            
            if not is_valid:
                logger.warning(
                    f"Twilio signature verification failed",
                    extra={
                        'url': url,
                        'expected_signature': signature,
                        'computed_signature': computed_signature_b64
                    }
                )
            
            return is_valid
            
        except Exception as e:
            logger.error(
                f"Error verifying Twilio signature",
                extra={'url': url},
                exc_info=True
            )
            return False
    
    def handle_status_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Twilio delivery status callback.
        
        Extracts relevant status information from Twilio's status callback
        webhook payload.
        
        Args:
            payload: Webhook payload from Twilio status callback
            
        Returns:
            dict: Parsed status information
            
        Example:
            >>> service = TwilioService(sid, token, '+14155238886')
            >>> status = service.handle_status_callback(request.POST.dict())
            >>> print(status['message_status'])
        """
        return {
            'message_sid': payload.get('MessageSid'),
            'message_status': payload.get('MessageStatus'),
            'to': payload.get('To'),
            'from': payload.get('From'),
            'error_code': payload.get('ErrorCode'),
            'error_message': payload.get('ErrorMessage'),
            'timestamp': payload.get('Timestamp')
        }
    
    @staticmethod
    def format_phone_number(phone: str, include_whatsapp_prefix: bool = True) -> str:
        """
        Format phone number for Twilio WhatsApp API.
        
        Args:
            phone: Phone number in E.164 format (e.g., +1234567890)
            include_whatsapp_prefix: Whether to add 'whatsapp:' prefix
            
        Returns:
            str: Formatted phone number
        """
        # Ensure E.164 format
        if not phone.startswith('+'):
            phone = f'+{phone}'
        
        # Add WhatsApp prefix if requested
        if include_whatsapp_prefix and not phone.startswith('whatsapp:'):
            phone = f'whatsapp:{phone}'
        
        return phone
    
    def retry_send_whatsapp(
        self,
        to: str,
        body: str,
        max_retries: int = 3,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message with automatic retry logic.
        
        Retries failed sends up to max_retries times with exponential backoff.
        
        Args:
            to: Recipient phone number
            body: Message text
            max_retries: Maximum number of retry attempts
            media_url: Optional media URL
            
        Returns:
            dict: Message details from successful send
            
        Raises:
            TwilioServiceError: If all retry attempts fail
        """
        import time
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return self.send_whatsapp(to, body, media_url)
            
            except TwilioServiceError as e:
                last_error = e
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 5s, 15s
                    wait_time = (2 ** attempt) * 1
                    logger.warning(
                        f"WhatsApp send failed, retrying in {wait_time}s",
                        extra={
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'to': to
                        }
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"WhatsApp send failed after {max_retries} attempts",
                        extra={'to': to}
                    )
        
        raise last_error


def create_twilio_service_for_tenant(tenant) -> TwilioService:
    """
    Factory function to create TwilioService instance for a tenant.
    
    Args:
        tenant: Tenant model instance
        
    Returns:
        TwilioService: Configured service instance
        
    Example:
        >>> from apps.tenants.models import Tenant
        >>> tenant = Tenant.objects.get(slug='acme-corp')
        >>> service = create_twilio_service_for_tenant(tenant)
        >>> service.send_whatsapp('+1234567890', 'Hello!')
    """
    # Try to get credentials from TenantSettings first, fallback to Tenant model
    try:
        settings = tenant.settings
        if settings.has_twilio_configured():
            return TwilioService(
                account_sid=settings.twilio_sid,
                auth_token=settings.twilio_token,
                from_number=tenant.whatsapp_number
            )
    except AttributeError:
        pass
    
    # Fallback to Tenant model (for backward compatibility)
    return TwilioService(
        account_sid=tenant.twilio_sid,
        auth_token=tenant.twilio_token,
        from_number=tenant.whatsapp_number
    )
