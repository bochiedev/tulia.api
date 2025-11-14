"""
Integration webhook views for external service callbacks.

Handles incoming webhooks from Twilio, WooCommerce, Shopify, etc.
"""
import logging
import traceback
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

logger = logging.getLogger(__name__)


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
                # Fallback to Tenant model
                twilio_sid = tenant.twilio_sid
                twilio_token = tenant.twilio_token
        except AttributeError:
            # Fallback to Tenant model
            twilio_sid = tenant.twilio_sid
            twilio_token = tenant.twilio_token
        
        twilio_service = TwilioService(
            account_sid=twilio_sid,
            auth_token=twilio_token,
            from_number=tenant.whatsapp_number
        )
        
        # Verify signature using auth_token (not webhook_secret)
        # Pass None to use the auth_token from the TwilioService instance
        if not twilio_service.verify_signature(full_url, payload, signature):
            webhook_log.mark_unauthorized('Twilio signature verification failed')
            logger.warning(
                f"Twilio signature verification failed",
                extra={'tenant_id': str(tenant.id), 'url': full_url}
            )
            return HttpResponse('Unauthorized', status=401)
        
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
        
        # Find message by provider_msg_id
        try:
            message = Message.objects.get(provider_msg_id=message_sid)
            
            # Update message status
            message.provider_status = message_status
            
            if message_status == 'delivered':
                message.mark_delivered()
            elif message_status == 'read':
                message.mark_read()
            elif message_status in ['failed', 'undelivered']:
                error_message = payload.get('ErrorMessage', 'Delivery failed')
                message.mark_failed(error_message)
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
        
        return HttpResponse('OK', status=200)
    
    except Exception as e:
        logger.error(
            f"Error processing Twilio status callback",
            exc_info=True
        )
        return HttpResponse('Internal error', status=200)
