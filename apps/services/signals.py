"""
Service/Appointment signals for triggering automated messages.

Implements:
- Booking confirmation on appointment creation
- Appointment reminder scheduling (24h and 2h before)
- Reminder cancellation when appointment is canceled
"""
import logging
from datetime import timedelta
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from apps.services.models import Appointment

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Appointment)
def track_appointment_status_change(sender, instance, **kwargs):
    """
    Track appointment status changes to handle reminder cancellation.
    
    Stores the previous status in instance._previous_status for comparison
    in post_save signal.
    """
    if instance.pk:
        try:
            previous = Appointment.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Appointment.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Appointment)
def send_appointment_messages(sender, instance, created, **kwargs):
    """
    Send automated messages and schedule reminders for appointments.
    
    Triggers:
    - Booking confirmation when appointment is created with status "confirmed"
    - Schedule 24h and 2h reminders for confirmed appointments
    - Cancel reminders if appointment is canceled
    """
    from apps.messaging.tasks import send_booking_confirmation
    from apps.messaging.models import ScheduledMessage
    
    # Get previous status
    previous_status = getattr(instance, '_previous_status', None)
    
    # Handle new confirmed appointments
    if created and instance.status == 'confirmed':
        logger.info(
            f"Appointment {instance.id} created with confirmed status, "
            f"triggering booking confirmation",
            extra={
                'tenant': instance.tenant.slug,
                'appointment_id': str(instance.id),
                'customer_id': str(instance.customer.id),
                'start_dt': instance.start_dt.isoformat()
            }
        )
        
        # Send booking confirmation immediately
        send_booking_confirmation.delay(str(instance.id))
        
        # Schedule reminders
        schedule_appointment_reminders(instance)
    
    # Handle status change to confirmed (from pending)
    elif not created and instance.status == 'confirmed' and previous_status != 'confirmed':
        logger.info(
            f"Appointment {instance.id} status changed to confirmed, "
            f"triggering booking confirmation",
            extra={
                'tenant': instance.tenant.slug,
                'appointment_id': str(instance.id),
                'previous_status': previous_status,
                'new_status': instance.status
            }
        )
        
        # Send booking confirmation
        send_booking_confirmation.delay(str(instance.id))
        
        # Schedule reminders
        schedule_appointment_reminders(instance)
    
    # Handle appointment cancellation - cancel pending reminders
    elif not created and instance.status == 'canceled' and previous_status != 'canceled':
        logger.info(
            f"Appointment {instance.id} canceled, canceling pending reminders",
            extra={
                'tenant': instance.tenant.slug,
                'appointment_id': str(instance.id),
                'previous_status': previous_status
            }
        )
        
        # Cancel any pending scheduled reminders for this appointment
        canceled_count = ScheduledMessage.objects.filter(
            tenant=instance.tenant,
            customer=instance.customer,
            status='pending',
            metadata__appointment_id=str(instance.id)
        ).update(status='canceled')
        
        if canceled_count > 0:
            logger.info(
                f"Canceled {canceled_count} pending reminders for appointment {instance.id}"
            )


def schedule_appointment_reminders(appointment):
    """
    Schedule 24h and 2h reminders for an appointment.
    
    Only schedules reminders if the appointment is in the future and
    the reminder time hasn't passed yet.
    
    Args:
        appointment: Appointment instance to schedule reminders for
    """
    from apps.messaging.services import MessagingService
    
    now = timezone.now()
    
    # Calculate reminder times
    reminder_24h = appointment.start_dt - timedelta(hours=24)
    reminder_2h = appointment.start_dt - timedelta(hours=2)
    
    # Schedule 24h reminder if it's in the future
    if reminder_24h > now:
        try:
            service_name = appointment.service.title
            if appointment.variant:
                service_name = f"{service_name} - {appointment.variant.title}"
            
            appointment_time = appointment.start_dt.strftime('%B %d at %I:%M %p')
            
            content = (
                f"⏰ Reminder: You have an appointment for {service_name} "
                f"tomorrow at {appointment_time}. "
                f"Reply CANCEL if you need to reschedule."
            )
            
            scheduled_msg = MessagingService.schedule_message(
                tenant=appointment.tenant,
                scheduled_at=reminder_24h,
                content=content,
                customer=appointment.customer,
                message_type='automated_reminder',
                metadata={
                    'appointment_id': str(appointment.id),
                    'reminder_type': '24h_before'
                }
            )
            
            logger.info(
                f"Scheduled 24h reminder for appointment {appointment.id} at {reminder_24h}",
                extra={
                    'tenant': appointment.tenant.slug,
                    'appointment_id': str(appointment.id),
                    'scheduled_message_id': str(scheduled_msg.id),
                    'scheduled_at': reminder_24h.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to schedule 24h reminder for appointment {appointment.id}: {str(e)}",
                exc_info=True
            )
    
    # Schedule 2h reminder if it's in the future
    if reminder_2h > now:
        try:
            service_name = appointment.service.title
            if appointment.variant:
                service_name = f"{service_name} - {appointment.variant.title}"
            
            appointment_time = appointment.start_dt.strftime('%I:%M %p')
            
            content = (
                f"⏰ Your appointment for {service_name} is coming up in 2 hours "
                f"at {appointment_time}. See you soon!"
            )
            
            scheduled_msg = MessagingService.schedule_message(
                tenant=appointment.tenant,
                scheduled_at=reminder_2h,
                content=content,
                customer=appointment.customer,
                message_type='automated_reminder',
                metadata={
                    'appointment_id': str(appointment.id),
                    'reminder_type': '2h_before'
                }
            )
            
            logger.info(
                f"Scheduled 2h reminder for appointment {appointment.id} at {reminder_2h}",
                extra={
                    'tenant': appointment.tenant.slug,
                    'appointment_id': str(appointment.id),
                    'scheduled_message_id': str(scheduled_msg.id),
                    'scheduled_at': reminder_2h.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to schedule 2h reminder for appointment {appointment.id}: {str(e)}",
                exc_info=True
            )
