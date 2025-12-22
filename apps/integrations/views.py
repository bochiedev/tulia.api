"""
Integration webhook views for external service callbacks.

Handles incoming webhooks from Twilio, WooCommerce, Shopify, etc.
"""
import logging
import traceback
import hashlib
import hmac
import base64
from typing import Optional, Dict, Any
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction

from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation, Message
from apps.integrations.models import WebhookLog
from apps.integrations.services import TwilioService
from apps.core.logging import SecurityLogger

logger = logging.getLogger(__name__)


def verify_twilio_signature(
    url: str,
    params: Dict[str, Any],
    signature: str,
    auth_token: str
) -> bool:
    """
    Verify Twilio webhook signature for security.
    
    Validates that the webhook request came from Twilio by comparing
    the X-Twilio-Signature header with a computed HMAC-SHA1 signature.
    
    This is a critical security measure to prevent webhook spoofing and
    unauthorized message injection.
    
    Args:
        url: Full webhook URL including protocol, domain, and path
        params: POST parameters from the webhook request as a dict
        signature: X-Twilio-Signature header value from the request
        auth_token: Twilio Auth Token for the tenant
        
    Returns:
        bool: True if signature is valid, False otherwise
        
    Security Notes:
        - Uses HMAC-SHA1 with the auth token as the secret key
        - Compares signatures using constant-time comparison to prevent timing attacks
        - Returns False on any exception to fail securely
        
    Example:
        >>> url = request.build_absolute_uri()
        >>> params = dict(request.POST.items())
        >>> signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
        >>> is_valid = verify_twilio_signature(url, params, signature, tenant.settings.twilio_token)
        >>> if not is_valid:
        ...     return HttpResponse('Unauthorized', status=403)
    """
    try:
        # Sort parameters alphabetically and concatenate with URL
        # Format: URL + key1value1 + key2value2 + ...
        sorted_params = sorted(params.items())
        data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
        
        # Compute HMAC-SHA1 signature using auth token as key
        computed_signature = hmac.new(
            auth_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64 encode the computed signature
        computed_signature_b64 = base64.b64encode(computed_signature).decode('utf-8')
        
        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(computed_signature_b64, signature)
        
        if not is_valid:
            logger.warning(
                "Twilio signature verification failed",
                extra={
                    'url': url,
                    'expected_signature': signature[:10] + '...',  # Log only prefix for security
                    'computed_signature': computed_signature_b64[:10] + '...'
                }
            )
            # Log as security event (will be logged separately with more context by caller)
        
        return is_valid
        
    except Exception as e:
        logger.error(
            "Error verifying Twilio signature",
            extra={'url': url, 'error': str(e)},
            exc_info=True
        )
        # Fail securely - return False on any exception
        return False


def resolve_tenant_from_twilio(payload: Dict[str, Any]) -> Optional[Tenant]:
    """
    Resolve tenant from Twilio webhook payload.
    
    Tries two methods:
    1. Match "To" number (WhatsApp business number)
    2. URL path mapping (future enhancement)
    
    Args:
        payload: Twilio webhook payload
        
    Returns:
        Tenant instance or None if not found
    """
    # Method 1: Resolve by "To" number (WhatsApp business number)
    to_number = payload.get('To', '')
    
    # Remove 'whatsapp:' prefix if present
    if to_number.startswith('whatsapp:'):
        to_number = to_number.replace('whatsapp:', '')
    
    tenant = Tenant.objects.by_whatsapp_number(to_number)
    
    if tenant:
        logger.info(
            f"Tenant resolved by WhatsApp number",
            extra={'tenant_id': str(tenant.id), 'whatsapp_number': to_number}
        )
        return tenant
    
    # Method 2: URL path mapping (future enhancement)
    # Could extract tenant slug from URL path if configured
    
    logger.warning(
        f"Failed to resolve tenant from Twilio webhook",
        extra={'to_number': to_number, 'payload': payload}
    )
    return None


def get_or_create_customer(tenant: Tenant, phone_e164: str) -> Customer:
    """
    Get or create customer for tenant and phone number.
    
    Args:
        tenant: Tenant instance
        phone_e164: Customer phone number in E.164 format
        
    Returns:
        Customer instance
    """
    customer = Customer.objects.by_phone(tenant, phone_e164)
    
    if not customer:
        # Create new customer
        customer = Customer.objects.create(
            tenant=tenant,
            phone_e164=phone_e164
        )
        logger.info(
            f"New customer created",
            extra={
                'tenant_id': str(tenant.id),
                'customer_id': str(customer.id),
                'phone': phone_e164
            }
        )
    
    # Update last seen
    customer.update_last_seen()
    
    return customer


def get_or_create_conversation(tenant: Tenant, customer: Customer) -> Conversation:
    """
    Get or create conversation for tenant and customer.
    
    Args:
        tenant: Tenant instance
        customer: Customer instance
        
    Returns:
        Conversation instance
    """
    # Try to find existing open or bot conversation
    conversation = Conversation.objects.filter(
        tenant=tenant,
        customer=customer,
        status__in=['open', 'bot']
    ).first()
    
    if not conversation:
        # Create new conversation
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status='bot',
            channel='whatsapp'
        )
        logger.info(
            f"New conversation created",
            extra={
                'tenant_id': str(tenant.id),
                'customer_id': str(customer.id),
                'conversation_id': str(conversation.id)
            }
        )
    elif conversation.status == 'closed' or conversation.status == 'dormant':
        # Reopen closed/dormant conversation
        conversation.reopen()
        logger.info(
            f"Conversation reopened",
            extra={'conversation_id': str(conversation.id)}
        )
    
    return conversation


def handle_button_click(
    tenant,
    conversation: Conversation,
    customer,
    button_payload: str,
    button_text: str,
    message: Message
):
    """
    Handle button click from WhatsApp interactive message.
    
    Processes different types of button clicks:
    - Feedback buttons (helpful/not_helpful)
    - Action buttons (buy, book, details)
    - Navigation buttons (next, previous)
    
    Args:
        tenant: Tenant instance
        conversation: Conversation instance
        customer: Customer instance
        button_payload: Button ID/payload from Twilio
        button_text: Button text displayed to user
        message: Message instance
    """
    logger.info(
        f"Button click received: payload={button_payload}, text={button_text}",
        extra={
            'tenant_id': str(tenant.id),
            'conversation_id': str(conversation.id),
            'customer_id': str(customer.id)
        }
    )
    
    try:
        # Handle feedback buttons
        if button_payload.startswith('feedback_'):
            handle_feedback_button(
                tenant=tenant,
                conversation=conversation,
                customer=customer,
                button_payload=button_payload,
                button_text=button_text
            )
        
        # Handle product action buttons
        elif button_payload.startswith('buy_product_') or button_payload.startswith('product_details_'):
            handle_product_action_button(
                tenant=tenant,
                conversation=conversation,
                button_payload=button_payload,
                button_text=button_text
            )
        
        # Handle service action buttons
        elif button_payload.startswith('book_service_') or button_payload.startswith('service_details_'):
            handle_service_action_button(
                tenant=tenant,
                conversation=conversation,
                button_payload=button_payload,
                button_text=button_text
            )
        
        # Handle navigation buttons
        elif button_payload.startswith('browse_'):
            handle_browse_button(
                tenant=tenant,
                conversation=conversation,
                button_payload=button_payload
            )
        
        else:
            logger.warning(f"Unknown button payload: {button_payload}")
    
    except Exception as e:
        logger.error(
            f"Error handling button click: {e}",
            exc_info=True,
            extra={
                'button_payload': button_payload,
                'tenant_id': str(tenant.id)
            }
        )


def handle_feedback_button(
    tenant,
    conversation: Conversation,
    customer,
    button_payload: str,
    button_text: str
):
    """
    Handle feedback button click (helpful/not_helpful).
    
    Creates InteractionFeedback record and sends confirmation message.
    
    Args:
        tenant: Tenant instance
        conversation: Conversation instance
        customer: Customer instance
        button_payload: Button payload (e.g., 'feedback_helpful_123')
        button_text: Button text
    """
    from apps.bot.models_feedback import InteractionFeedback
    from apps.bot.models import AgentInteraction
    
    # Parse interaction ID from payload
    # Format: feedback_{rating}_{interaction_id}
    parts = button_payload.split('_')
    if len(parts) < 3:
        logger.error(f"Invalid feedback button payload: {button_payload}")
        return
    
    rating_type = parts[1]  # 'helpful' or 'not' (from 'not_helpful')
    interaction_id = parts[-1]  # Last part is the ID
    
    # Determine rating
    if rating_type == 'helpful':
        rating = 'helpful'
    elif rating_type == 'not':
        rating = 'not_helpful'
    elif rating_type == 'comment':
        # Handle comment button - prompt for text feedback
        send_feedback_prompt(tenant, conversation)
        return
    else:
        logger.error(f"Unknown rating type: {rating_type}")
        return
    
    try:
        # Get agent interaction
        interaction = AgentInteraction.objects.get(
            id=interaction_id,
            conversation=conversation,
            tenant=tenant
        )
        
        # Check if feedback already exists
        existing_feedback = InteractionFeedback.objects.filter(
            agent_interaction=interaction,
            tenant=tenant
        ).first()
        
        if existing_feedback:
            # Update existing feedback
            existing_feedback.rating = rating
            existing_feedback.save()
            logger.info(f"Updated feedback for interaction {interaction_id}: {rating}")
        else:
            # Create new feedback
            InteractionFeedback.objects.create(
                tenant=tenant,
                agent_interaction=interaction,
                conversation=conversation,
                customer=customer,
                rating=rating,
                feedback_source='whatsapp_button'
            )
            logger.info(f"Created feedback for interaction {interaction_id}: {rating}")
        
        # Send confirmation message
        from apps.integrations.services import TwilioService
        
        # Get Twilio credentials
        try:
            settings = tenant.settings
            if settings.has_twilio_configured():
                twilio_sid = settings.twilio_sid
                twilio_token = settings.twilio_token
            else:
                raise ValueError("Twilio credentials not configured")
        except (AttributeError, ValueError):
            raise ValueError("Twilio credentials not configured")
        
        twilio_service = TwilioService(
            account_sid=twilio_sid,
            auth_token=twilio_token,
            from_number=tenant.whatsapp_number
        )
        
        # Send confirmation
        confirmation_messages = {
            'helpful': "Thank you for your feedback! 😊 I'm glad I could help.",
            'not_helpful': "Thank you for your feedback. I'll try to do better. Would you like to speak with a human agent?"
        }
        
        twilio_service.send_whatsapp(
            to=customer.phone_e164,
            body=confirmation_messages.get(rating, "Thank you for your feedback!")
        )
        
    except AgentInteraction.DoesNotExist:
        logger.error(f"Agent interaction not found: {interaction_id}")
    except Exception as e:
        logger.error(f"Error handling feedback button: {e}", exc_info=True)


def send_feedback_prompt(tenant, conversation: Conversation):
    """
    Send a prompt asking for detailed feedback.
    
    Args:
        tenant: Tenant instance
        conversation: Conversation instance
    """
    # TODO: Implement detailed feedback collection
    pass


def handle_product_action_button(tenant, conversation: Conversation, button_payload: str, button_text: str):
    """Handle product action button clicks."""
    # TODO: Implement product action handling
    logger.info(f"Product action button clicked: {button_payload}")


def handle_service_action_button(tenant, conversation: Conversation, button_payload: str, button_text: str):
    """Handle service action button clicks."""
    # TODO: Implement service action handling
    logger.info(f"Service action button clicked: {button_payload}")


def handle_browse_button(tenant, conversation: Conversation, button_payload: str):
    """Handle browse navigation button clicks."""
    # TODO: Implement browse navigation handling
    logger.info(f"Browse button clicked: {button_payload}")


@csrf_exempt
@require_http_methods(["POST"])
def twilio_webhook(request):
    """
    Handle incoming Twilio WhatsApp webhook.
    
    Process flow:
    1. Create webhook log entry
    2. Resolve tenant from "To" number
    3. Verify Twilio signature
    4. Check subscription status
    5. Get or create customer and conversation
    6. Store inbound message
    7. Trigger intent processing (future task)
    
    Returns:
        HttpResponse with 200 status for successful processing
        HttpResponse with 404 if tenant not found
        HttpResponse with 401 if signature verification fails
        HttpResponse with 503 if subscription inactive
    """
    start_time = timezone.now()
    webhook_log = None
    
    try:
        # Parse webhook payload
        payload = dict(request.POST.items())
        
        # Extract key fields
        from_number = payload.get('From', '').replace('whatsapp:', '')
        to_number = payload.get('To', '').replace('whatsapp:', '')
        message_body = payload.get('Body', '')
        message_sid = payload.get('MessageSid', '')
        
        # Check if this is a button response
        button_payload = payload.get('ButtonPayload', '')
        button_text = payload.get('ButtonText', '')
        
        logger.info(
            f"Twilio webhook received",
            extra={
                'from': from_number,
                'to': to_number,
                'message_sid': message_sid
            }
        )
        
        # Step 1: Create webhook log entry (before processing)
        webhook_log = WebhookLog.objects.create(
            provider='twilio',
            event='message.received',
            payload=payload,
            headers={
                'X-Twilio-Signature': request.META.get('HTTP_X_TWILIO_SIGNATURE', ''),
                'User-Agent': request.META.get('HTTP_USER_AGENT', ''),
            },
            status='success',  # Will update if errors occur
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        # Step 2: Resolve tenant
        tenant = resolve_tenant_from_twilio(payload)
        
        if not tenant:
            webhook_log.tenant = None
            webhook_log.mark_error('Tenant not found')
            return HttpResponse('Tenant not found', status=404)
        
        webhook_log.tenant = tenant
        webhook_log.save(update_fields=['tenant'])
        
        # Step 3: Verify Twilio signature
        signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
        full_url = request.build_absolute_uri()
        
        # Get Twilio credentials from TenantSettings (preferred) or Tenant model (fallback)
        try:
            settings = tenant.settings
            if settings.has_twilio_configured():
                twilio_sid = settings.twilio_sid
                twilio_token = settings.twilio_token
            else:
                raise ValueError("Twilio credentials not configured")
        except (AttributeError, ValueError):
            webhook_log.mark_failed('Twilio credentials not configured')
            return HttpResponse('Twilio not configured', status=500)
        
        # Verify signature using the helper function
        if not verify_twilio_signature(full_url, payload, signature, twilio_token):
            webhook_log.mark_unauthorized('Twilio signature verification failed')
            
            # Log as critical security event
            SecurityLogger.log_invalid_webhook_signature(
                provider='twilio',
                tenant_id=str(tenant.id),
                ip_address=request.META.get('REMOTE_ADDR'),
                url=full_url,
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            logger.warning(
                "Twilio signature verification failed",
                extra={'tenant_id': str(tenant.id), 'url': full_url}
            )
            return HttpResponse('Unauthorized', status=403)
        
        # Create TwilioService instance for sending messages
        twilio_service = TwilioService(
            account_sid=twilio_sid,
            auth_token=twilio_token,
            from_number=tenant.whatsapp_number
        )
        
        # Step 4: Check subscription status
        if not tenant.is_active():
            webhook_log.mark_subscription_inactive()
            
            # Send automated message to customer
            try:
                twilio_service.send_whatsapp(
                    to=from_number,
                    body="This business is temporarily unavailable. Please try again later."
                )
            except Exception as e:
                logger.error(
                    f"Failed to send subscription inactive message",
                    extra={'tenant_id': str(tenant.id)},
                    exc_info=True
                )
            
            return HttpResponse('Subscription inactive', status=503)
        
        # Step 5: Get or create customer and conversation
        with transaction.atomic():
            customer = get_or_create_customer(tenant, from_number)
            conversation = get_or_create_conversation(tenant, customer)
            
            # Step 6: Store inbound message
            message = Message.objects.create(
                conversation=conversation,
                direction='in',
                message_type='customer_inbound',
                text=message_body,
                payload=payload,
                provider_msg_id=message_sid
            )
            
            logger.info(
                f"Inbound message stored",
                extra={
                    'tenant_id': str(tenant.id),
                    'customer_id': str(customer.id),
                    'conversation_id': str(conversation.id),
                    'message_id': str(message.id)
                }
            )
        
        # Handle button clicks (feedback, actions, etc.)
        if button_payload:
            handle_button_click(
                tenant=tenant,
                conversation=conversation,
                customer=customer,
                button_payload=button_payload,
                button_text=button_text,
                message=message
            )
        
        # Step 7: Trigger intent processing
        from apps.bot.tasks import process_inbound_message
        process_inbound_message.delay(str(message.id))
        
        logger.info(
            f"Intent processing task enqueued",
            extra={'message_id': str(message.id)}
        )
        
        # Mark webhook as successfully processed
        processing_time = int((timezone.now() - start_time).total_seconds() * 1000)
        webhook_log.mark_success(processing_time)
        
        # Return 200 to acknowledge receipt
        return HttpResponse('OK', status=200)
    
    except Exception as e:
        error_message = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(
            f"Error processing Twilio webhook",
            extra={'error': error_message},
            exc_info=True
        )
        
        if webhook_log:
            processing_time = int((timezone.now() - start_time).total_seconds() * 1000)
            webhook_log.mark_error(error_message, error_traceback, processing_time)
        
        # Return 200 to prevent Twilio retries for application errors
        # Twilio will retry on 5xx errors, but we've logged the issue
        return HttpResponse('Internal error', status=200)


@csrf_exempt
@require_http_methods(["POST"])
def twilio_status_callback(request):
    """
    Handle Twilio message status callbacks.
    
    Updates message delivery status based on Twilio callbacks.
    
    Status values:
    - queued: Message queued for delivery
    - sent: Message sent to carrier
    - delivered: Message delivered to recipient
    - read: Message read by recipient (if supported)
    - failed: Message delivery failed
    - undelivered: Message could not be delivered
    
    Security:
    - Verifies Twilio signature to prevent spoofing
    - Returns 403 for invalid signatures
    """
    try:
        payload = dict(request.POST.items())
        message_sid = payload.get('MessageSid')
        message_status = payload.get('MessageStatus')
        
        logger.info(
            f"Twilio status callback received",
            extra={
                'message_sid': message_sid,
                'status': message_status
            }
        )
        
        # Find message by provider_msg_id to get tenant for signature verification
        try:
            message = Message.objects.select_related(
                'conversation__tenant',
                'conversation__tenant__settings'
            ).get(provider_msg_id=message_sid)
            
            tenant = message.conversation.tenant
            
            # Verify Twilio signature
            signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
            full_url = request.build_absolute_uri()
            
            # Get Twilio credentials from TenantSettings
            try:
                settings = tenant.settings
                if settings.has_twilio_configured():
                    twilio_token = settings.twilio_token
                else:
                    raise ValueError("Twilio credentials not configured")
            except (AttributeError, ValueError):
                logger.error(f"Twilio credentials not configured for tenant {tenant.id}")
                return HttpResponse('Twilio not configured', status=500)
            
            # Verify signature using the helper function
            if not verify_twilio_signature(full_url, payload, signature, twilio_token):
                # Log as critical security event
                SecurityLogger.log_invalid_webhook_signature(
                    provider='twilio',
                    tenant_id=str(tenant.id),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    url=full_url,
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
                
                logger.warning(
                    "Twilio status callback signature verification failed",
                    extra={
                        'tenant_id': str(tenant.id),
                        'message_sid': message_sid,
                        'url': full_url
                    }
                )
                return HttpResponse('Unauthorized', status=403)
            
            # Update message status
            message.provider_status = message_status
            
            if message_status == 'delivered':
                message.mark_delivered()
                message.provider_status = message_status
                message.save(update_fields=['provider_status'])
            elif message_status == 'read':
                message.mark_read()
                message.provider_status = message_status
                message.save(update_fields=['provider_status'])
            elif message_status in ['failed', 'undelivered']:
                error_message = payload.get('ErrorMessage', 'Delivery failed')
                message.mark_failed(error_message)
                message.provider_status = message_status
                message.save(update_fields=['provider_status'])
            else:
                message.save(update_fields=['provider_status'])
            
            logger.info(
                f"Message status updated",
                extra={
                    'message_id': str(message.id),
                    'status': message_status
                }
            )
        
        except Message.DoesNotExist:
            logger.warning(
                f"Message not found for status callback",
                extra={'message_sid': message_sid}
            )
            # Return 404 for unknown messages to prevent information disclosure
            return HttpResponse('Message not found', status=404)
        
        return HttpResponse('OK', status=200)
    
    except Exception as e:
        logger.error(
            f"Error processing Twilio status callback",
            exc_info=True
        )
        return HttpResponse('Internal error', status=200)
