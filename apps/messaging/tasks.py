"""
Celery tasks for messaging operations.
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_scheduled_messages(self):
    """
    Process all scheduled messages that are due for sending.
    
    This task should be run periodically (e.g., every minute via Celery Beat).
    It finds all pending scheduled messages where scheduled_at <= now and sends them.
    
    Returns:
        dict: Summary of processing results
    """
    from apps.messaging.models import ScheduledMessage
    from apps.messaging.services import MessagingService
    
    logger.info("Starting scheduled message processing")
    
    # Get all messages due for sending
    due_messages = ScheduledMessage.objects.due_for_sending()
    total_count = due_messages.count()
    
    if total_count == 0:
        logger.info("No scheduled messages due for sending")
        return {
            'status': 'success',
            'total': 0,
            'sent': 0,
            'failed': 0
        }
    
    logger.info(f"Found {total_count} scheduled messages due for sending")
    
    sent_count = 0
    failed_count = 0
    
    # Process each message
    for scheduled_msg in due_messages:
        try:
            with transaction.atomic():
                # Send the message
                message = MessagingService.send_message(
                    tenant=scheduled_msg.tenant,
                    customer=scheduled_msg.customer,
                    content=scheduled_msg.content,
                    message_type=scheduled_msg.message_type
                )
                
                # Mark as sent
                scheduled_msg.mark_sent(message=message)
                sent_count += 1
                
                logger.info(
                    f"Sent scheduled message {scheduled_msg.id} to customer {scheduled_msg.customer_id}"
                )
                
        except Exception as e:
            # Mark as failed
            error_message = str(e)
            scheduled_msg.mark_failed(error_message=error_message)
            failed_count += 1
            
            logger.error(
                f"Failed to send scheduled message {scheduled_msg.id}: {error_message}",
                exc_info=True
            )
    
    result = {
        'status': 'completed',
        'total': total_count,
        'sent': sent_count,
        'failed': failed_count
    }
    
    logger.info(f"Scheduled message processing completed: {result}")
    return result


@shared_task(bind=True, max_retries=3)
def send_appointment_reminder(self, appointment_id: str, hours_before: int):
    """
    Send appointment reminder to customer.
    
    Args:
        appointment_id: UUID of the appointment
        hours_before: How many hours before appointment (24 or 2)
    
    Returns:
        dict: Result of sending reminder
    """
    from apps.services.models import Appointment
    from apps.messaging.services import MessagingService
    
    try:
        appointment = Appointment.objects.select_related(
            'tenant', 'customer', 'service_variant__service'
        ).get(id=appointment_id)
        
        # Check if appointment is still confirmed
        if appointment.status != 'confirmed':
            logger.info(
                f"Skipping reminder for appointment {appointment_id} - status is {appointment.status}"
            )
            return {'status': 'skipped', 'reason': f'status is {appointment.status}'}
        
        # Generate reminder message
        service_name = appointment.service_variant.service.title
        appointment_time = appointment.start_dt.strftime('%B %d at %I:%M %p')
        
        if hours_before == 24:
            content = (
                f"Reminder: You have an appointment for {service_name} "
                f"tomorrow at {appointment_time}. "
                f"Reply CANCEL if you need to reschedule."
            )
        else:  # 2 hours
            content = (
                f"Your appointment for {service_name} is coming up in 2 hours "
                f"at {appointment_time}. See you soon!"
            )
        
        # Send reminder
        message = MessagingService.send_message(
            tenant=appointment.tenant,
            customer=appointment.customer,
            content=content,
            message_type='reminder_messages',
            metadata={
                'appointment_id': str(appointment.id),
                'reminder_type': f'{hours_before}h_before'
            }
        )
        
        logger.info(
            f"Sent {hours_before}h reminder for appointment {appointment_id}"
        )
        
        return {
            'status': 'sent',
            'message_id': str(message.id),
            'appointment_id': str(appointment.id)
        }
        
    except Appointment.DoesNotExist:
        logger.error(f"Appointment {appointment_id} not found")
        return {'status': 'error', 'reason': 'appointment not found'}
        
    except Exception as e:
        logger.error(
            f"Failed to send reminder for appointment {appointment_id}: {str(e)}",
            exc_info=True
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


# ============================================================================
# Transactional Message Tasks (Requirement 41)
# ============================================================================

@shared_task(bind=True, max_retries=3)
def send_payment_confirmation(self, order_id: str):
    """
    Send payment confirmation message when order is paid.
    
    Triggered when Order status changes to "paid".
    
    Args:
        order_id: UUID of the order
    
    Returns:
        dict: Result of sending confirmation
    """
    from apps.orders.models import Order
    from apps.messaging.services import MessagingService
    
    try:
        order = Order.objects.select_related('tenant', 'customer').get(id=order_id)
        
        # Verify order is paid
        if order.status != 'paid':
            logger.warning(
                f"Skipping payment confirmation for order {order_id} - status is {order.status}"
            )
            return {'status': 'skipped', 'reason': f'status is {order.status}'}
        
        # Generate confirmation message
        content = (
            f"✅ Payment confirmed! Your order #{str(order.id)[:8]} for "
            f"{order.currency} {order.total} has been received. "
            f"We'll notify you when it ships. Thank you for your purchase!"
        )
        
        # Send confirmation (transactional messages skip consent check)
        message = MessagingService.send_message(
            tenant=order.tenant,
            customer=order.customer,
            content=content,
            message_type='automated_transactional',
            skip_consent_check=True,  # Transactional messages always allowed
            skip_rate_limit_check=True  # Don't count against rate limit
        )
        
        logger.info(
            f"Sent payment confirmation for order {order_id}",
            extra={
                'tenant': order.tenant.slug,
                'customer': order.customer.id,
                'order_id': str(order.id),
                'message_id': str(message.id)
            }
        )
        
        return {
            'status': 'sent',
            'message_id': str(message.id),
            'order_id': str(order.id)
        }
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return {'status': 'error', 'reason': 'order not found'}
        
    except Exception as e:
        logger.error(
            f"Failed to send payment confirmation for order {order_id}: {str(e)}",
            exc_info=True
        )
        # Retry with exponential backoff (3 attempts)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_shipment_notification(self, order_id: str):
    """
    Send shipment notification when order is shipped.
    
    Triggered when Order status changes to "shipped" or "fulfilled".
    
    Args:
        order_id: UUID of the order
    
    Returns:
        dict: Result of sending notification
    """
    from apps.orders.models import Order
    from apps.messaging.services import MessagingService
    
    try:
        order = Order.objects.select_related('tenant', 'customer').get(id=order_id)
        
        # Verify order is fulfilled
        if order.status != 'fulfilled':
            logger.warning(
                f"Skipping shipment notification for order {order_id} - status is {order.status}"
            )
            return {'status': 'skipped', 'reason': f'status is {order.status}'}
        
        # Generate shipment message
        if order.tracking_number:
            content = (
                f"📦 Your order #{str(order.id)[:8]} has shipped! "
                f"Tracking number: {order.tracking_number}. "
                f"You should receive it soon. Thank you!"
            )
        else:
            content = (
                f"📦 Your order #{str(order.id)[:8]} has shipped! "
                f"You should receive it soon. Thank you!"
            )
        
        # Send notification (transactional messages skip consent check)
        message = MessagingService.send_message(
            tenant=order.tenant,
            customer=order.customer,
            content=content,
            message_type='automated_transactional',
            skip_consent_check=True,
            skip_rate_limit_check=True
        )
        
        logger.info(
            f"Sent shipment notification for order {order_id}",
            extra={
                'tenant': order.tenant.slug,
                'customer': order.customer.id,
                'order_id': str(order.id),
                'message_id': str(message.id)
            }
        )
        
        return {
            'status': 'sent',
            'message_id': str(message.id),
            'order_id': str(order.id)
        }
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return {'status': 'error', 'reason': 'order not found'}
        
    except Exception as e:
        logger.error(
            f"Failed to send shipment notification for order {order_id}: {str(e)}",
            exc_info=True
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_payment_failed_notification(self, transaction_id: str, retry_url: str = None):
    """
    Send payment failed notification with retry instructions.
    
    Triggered when a payment transaction fails.
    
    Args:
        transaction_id: UUID of the failed transaction
        retry_url: Optional URL for customer to retry payment
    
    Returns:
        dict: Result of sending notification
    """
    from apps.tenants.models import Transaction
    from apps.messaging.services import MessagingService
    
    try:
        transaction = Transaction.objects.select_related(
            'wallet__tenant', 'wallet__tenant__customer_set'
        ).get(id=transaction_id)
        
        tenant = transaction.wallet.tenant
        
        # Get customer from transaction metadata or reference
        customer_id = transaction.metadata.get('customer_id')
        if not customer_id:
            logger.error(f"No customer_id in transaction {transaction_id} metadata")
            return {'status': 'error', 'reason': 'no customer_id in metadata'}
        
        from apps.tenants.models import Customer
        customer = Customer.objects.get(id=customer_id, tenant=tenant)
        
        # Generate failure message
        if retry_url:
            content = (
                f"❌ Payment failed for your order. "
                f"Please update your payment method and try again: {retry_url}"
            )
        else:
            content = (
                f"❌ Payment failed for your order. "
                f"Please contact us to complete your purchase."
            )
        
        # Send notification (transactional messages skip consent check)
        message = MessagingService.send_message(
            tenant=tenant,
            customer=customer,
            content=content,
            message_type='automated_transactional',
            skip_consent_check=True,
            skip_rate_limit_check=True
        )
        
        logger.info(
            f"Sent payment failed notification for transaction {transaction_id}",
            extra={
                'tenant': tenant.slug,
                'customer': customer.id,
                'transaction_id': str(transaction.id),
                'message_id': str(message.id)
            }
        )
        
        return {
            'status': 'sent',
            'message_id': str(message.id),
            'transaction_id': str(transaction.id)
        }
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found")
        return {'status': 'error', 'reason': 'transaction not found'}
        
    except Exception as e:
        logger.error(
            f"Failed to send payment failed notification for transaction {transaction_id}: {str(e)}",
            exc_info=True
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_booking_confirmation(self, appointment_id: str):
    """
    Send booking confirmation when appointment is created/confirmed.
    
    Triggered when Appointment is created with status "confirmed".
    
    Args:
        appointment_id: UUID of the appointment
    
    Returns:
        dict: Result of sending confirmation
    """
    from apps.services.models import Appointment
    from apps.messaging.services import MessagingService
    
    try:
        appointment = Appointment.objects.select_related(
            'tenant', 'customer', 'service', 'variant'
        ).get(id=appointment_id)
        
        # Generate confirmation message
        service_name = appointment.service.title
        if appointment.variant:
            service_name = f"{service_name} - {appointment.variant.title}"
        
        appointment_time = appointment.start_dt.strftime('%B %d, %Y at %I:%M %p')
        duration = appointment.duration_minutes()
        
        content = (
            f"✅ Booking confirmed! Your appointment for {service_name} "
            f"is scheduled for {appointment_time} ({duration} minutes). "
            f"We look forward to seeing you!"
        )
        
        if appointment.notes:
            content += f"\n\nYour notes: {appointment.notes}"
        
        # Send confirmation (transactional messages skip consent check)
        message = MessagingService.send_message(
            tenant=appointment.tenant,
            customer=appointment.customer,
            content=content,
            message_type='automated_transactional',
            skip_consent_check=True,
            skip_rate_limit_check=True
        )
        
        logger.info(
            f"Sent booking confirmation for appointment {appointment_id}",
            extra={
                'tenant': appointment.tenant.slug,
                'customer': appointment.customer.id,
                'appointment_id': str(appointment.id),
                'message_id': str(message.id)
            }
        )
        
        return {
            'status': 'sent',
            'message_id': str(message.id),
            'appointment_id': str(appointment.id)
        }
        
    except Appointment.DoesNotExist:
        logger.error(f"Appointment {appointment_id} not found")
        return {'status': 'error', 'reason': 'appointment not found'}
        
    except Exception as e:
        logger.error(
            f"Failed to send booking confirmation for appointment {appointment_id}: {str(e)}",
            exc_info=True
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))



# ============================================================================
# Appointment Reminder Tasks (Requirement 42)
# ============================================================================

@shared_task(bind=True, max_retries=3)
def send_24h_appointment_reminders(self):
    """
    Send 24-hour appointment reminders for all upcoming appointments.
    
    This task should be run periodically (e.g., every hour via Celery Beat).
    It finds all appointments starting in 23-25 hours and sends reminders.
    
    Returns:
        dict: Summary of reminders sent
    """
    from apps.services.models import Appointment
    from apps.messaging.services import MessagingService, ConsentService
    from datetime import timedelta
    
    logger.info("Starting 24-hour appointment reminder batch")
    
    # Find appointments starting in 23-25 hours
    now = timezone.now()
    start_window = now + timedelta(hours=23)
    end_window = now + timedelta(hours=25)
    
    appointments = Appointment.objects.filter(
        status='confirmed',
        start_dt__gte=start_window,
        start_dt__lt=end_window
    ).select_related('tenant', 'customer', 'service', 'variant')
    
    total_count = appointments.count()
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    
    logger.info(f"Found {total_count} appointments for 24h reminders")
    
    for appointment in appointments:
        try:
            # Check consent for reminder messages
            if not ConsentService.check_consent(
                appointment.tenant,
                appointment.customer,
                'automated_reminder'
            ):
                logger.info(
                    f"Skipping 24h reminder for appointment {appointment.id} - "
                    f"customer has not consented to reminders"
                )
                skipped_count += 1
                continue
            
            # Generate reminder message
            service_name = appointment.service.title
            if appointment.variant:
                service_name = f"{service_name} - {appointment.variant.title}"
            
            appointment_time = appointment.start_dt.strftime('%B %d at %I:%M %p')
            
            content = (
                f"⏰ Reminder: You have an appointment for {service_name} "
                f"tomorrow at {appointment_time}. "
                f"Reply CANCEL if you need to reschedule."
            )
            
            # Send reminder
            message = MessagingService.send_message(
                tenant=appointment.tenant,
                customer=appointment.customer,
                content=content,
                message_type='automated_reminder',
                skip_rate_limit_check=True  # Reminders don't count against rate limit
            )
            
            sent_count += 1
            
            logger.info(
                f"Sent 24h reminder for appointment {appointment.id}",
                extra={
                    'tenant': appointment.tenant.slug,
                    'customer': appointment.customer.id,
                    'appointment_id': str(appointment.id),
                    'message_id': str(message.id)
                }
            )
            
        except Exception as e:
            failed_count += 1
            logger.error(
                f"Failed to send 24h reminder for appointment {appointment.id}: {str(e)}",
                exc_info=True
            )
    
    result = {
        'status': 'completed',
        'total': total_count,
        'sent': sent_count,
        'skipped': skipped_count,
        'failed': failed_count
    }
    
    logger.info(f"24-hour reminder batch completed: {result}")
    return result


@shared_task(bind=True, max_retries=3)
def send_2h_appointment_reminders(self):
    """
    Send 2-hour appointment reminders for all upcoming appointments.
    
    This task should be run periodically (e.g., every 15 minutes via Celery Beat).
    It finds all appointments starting in 1.5-2.5 hours and sends reminders.
    
    Returns:
        dict: Summary of reminders sent
    """
    from apps.services.models import Appointment
    from apps.messaging.services import MessagingService, ConsentService
    from datetime import timedelta
    
    logger.info("Starting 2-hour appointment reminder batch")
    
    # Find appointments starting in 1.5-2.5 hours
    now = timezone.now()
    start_window = now + timedelta(hours=1, minutes=30)
    end_window = now + timedelta(hours=2, minutes=30)
    
    appointments = Appointment.objects.filter(
        status='confirmed',
        start_dt__gte=start_window,
        start_dt__lt=end_window
    ).select_related('tenant', 'customer', 'service', 'variant')
    
    total_count = appointments.count()
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    
    logger.info(f"Found {total_count} appointments for 2h reminders")
    
    for appointment in appointments:
        try:
            # Check consent for reminder messages
            if not ConsentService.check_consent(
                appointment.tenant,
                appointment.customer,
                'automated_reminder'
            ):
                logger.info(
                    f"Skipping 2h reminder for appointment {appointment.id} - "
                    f"customer has not consented to reminders"
                )
                skipped_count += 1
                continue
            
            # Generate reminder message
            service_name = appointment.service.title
            if appointment.variant:
                service_name = f"{service_name} - {appointment.variant.title}"
            
            appointment_time = appointment.start_dt.strftime('%I:%M %p')
            
            content = (
                f"⏰ Your appointment for {service_name} is coming up in 2 hours "
                f"at {appointment_time}. See you soon!"
            )
            
            # Send reminder
            message = MessagingService.send_message(
                tenant=appointment.tenant,
                customer=appointment.customer,
                content=content,
                message_type='automated_reminder',
                skip_rate_limit_check=True  # Reminders don't count against rate limit
            )
            
            sent_count += 1
            
            logger.info(
                f"Sent 2h reminder for appointment {appointment.id}",
                extra={
                    'tenant': appointment.tenant.slug,
                    'customer': appointment.customer.id,
                    'appointment_id': str(appointment.id),
                    'message_id': str(message.id)
                }
            )
            
        except Exception as e:
            failed_count += 1
            logger.error(
                f"Failed to send 2h reminder for appointment {appointment.id}: {str(e)}",
                exc_info=True
            )
    
    result = {
        'status': 'completed',
        'total': total_count,
        'sent': sent_count,
        'skipped': skipped_count,
        'failed': failed_count
    }
    
    logger.info(f"2-hour reminder batch completed: {result}")
    return result


# ============================================================================
# Re-engagement Message Tasks (Requirement 43)
# ============================================================================

@shared_task(bind=True, max_retries=3)
def send_reengagement_messages(self):
    """
    Send re-engagement messages to inactive conversations.
    
    This task should be run daily via Celery Beat.
    It finds conversations inactive for 7 days and sends personalized re-engagement messages.
    Conversations with no response after 14 days are marked as dormant.
    
    Returns:
        dict: Summary of re-engagement messages sent
    """
    from apps.messaging.models import Conversation
    from apps.messaging.services import MessagingService, ConsentService
    from datetime import timedelta
    
    logger.info("Starting re-engagement message batch")
    
    now = timezone.now()
    
    # Find conversations inactive for 7 days (but not yet dormant)
    inactive_cutoff = now - timedelta(days=7)
    dormant_cutoff = now - timedelta(days=14)
    
    # Get conversations that are:
    # 1. Open status
    # 2. Last updated 7+ days ago
    # 3. Not already dormant
    inactive_conversations = Conversation.objects.filter(
        status='open',
        updated_at__lt=inactive_cutoff,
        updated_at__gte=dormant_cutoff
    ).select_related('tenant', 'customer')
    
    total_count = inactive_conversations.count()
    sent_count = 0
    skipped_count = 0
    failed_count = 0
    
    logger.info(f"Found {total_count} inactive conversations for re-engagement")
    
    for conversation in inactive_conversations:
        try:
            # Check consent for promotional messages
            if not ConsentService.check_consent(
                conversation.tenant,
                conversation.customer,
                'automated_reengagement'
            ):
                logger.info(
                    f"Skipping re-engagement for conversation {conversation.id} - "
                    f"customer has not consented to promotional messages"
                )
                skipped_count += 1
                continue
            
            # Generate personalized re-engagement message
            customer_name = conversation.customer.name or "there"
            
            # Customize based on last intent if available
            if conversation.last_intent:
                if 'PRODUCT' in conversation.last_intent:
                    cta = "Check out our new arrivals!"
                elif 'SERVICE' in conversation.last_intent or 'APPOINTMENT' in conversation.last_intent:
                    cta = "Ready to book your next appointment?"
                else:
                    cta = "We have something special for you!"
            else:
                cta = "We'd love to hear from you!"
            
            content = (
                f"Hi {customer_name}! 👋 We noticed it's been a while since we last chatted. "
                f"{cta} Reply anytime if you have questions or need assistance."
            )
            
            # Send re-engagement message
            message = MessagingService.send_message(
                tenant=conversation.tenant,
                customer=conversation.customer,
                content=content,
                message_type='automated_reengagement',
                conversation=conversation
            )
            
            sent_count += 1
            
            logger.info(
                f"Sent re-engagement message for conversation {conversation.id}",
                extra={
                    'tenant': conversation.tenant.slug,
                    'customer': conversation.customer.id,
                    'conversation_id': str(conversation.id),
                    'message_id': str(message.id)
                }
            )
            
        except Exception as e:
            failed_count += 1
            logger.error(
                f"Failed to send re-engagement for conversation {conversation.id}: {str(e)}",
                exc_info=True
            )
    
    # Mark conversations inactive for 14+ days as dormant
    dormant_conversations = Conversation.objects.filter(
        status='open',
        updated_at__lt=dormant_cutoff
    )
    
    dormant_count = dormant_conversations.count()
    if dormant_count > 0:
        dormant_conversations.update(status='dormant')
        logger.info(f"Marked {dormant_count} conversations as dormant")
    
    result = {
        'status': 'completed',
        'total': total_count,
        'sent': sent_count,
        'skipped': skipped_count,
        'failed': failed_count,
        'marked_dormant': dormant_count
    }
    
    logger.info(f"Re-engagement batch completed: {result}")
    return result
