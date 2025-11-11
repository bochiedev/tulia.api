"""
Order signals for triggering automated transactional messages.

Implements:
- Payment confirmation on order paid
- Shipment notification on order fulfilled
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.orders.models import Order

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Order)
def track_order_status_change(sender, instance, **kwargs):
    """
    Track order status changes to trigger appropriate messages.
    
    Stores the previous status in instance._previous_status for comparison
    in post_save signal.
    """
    if instance.pk:
        try:
            previous = Order.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Order.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def send_order_transactional_messages(sender, instance, created, **kwargs):
    """
    Send automated transactional messages when order status changes.
    
    Triggers:
    - Payment confirmation when status changes to "paid"
    - Shipment notification when status changes to "fulfilled"
    """
    from apps.messaging.tasks import send_payment_confirmation, send_shipment_notification
    
    # Skip if this is a new order (no status change yet)
    if created:
        return
    
    # Get previous status
    previous_status = getattr(instance, '_previous_status', None)
    
    # Skip if status hasn't changed
    if previous_status == instance.status:
        return
    
    # Trigger payment confirmation when order becomes paid
    if instance.status == 'paid' and previous_status != 'paid':
        logger.info(
            f"Order {instance.id} status changed to paid, triggering payment confirmation",
            extra={
                'tenant': instance.tenant.slug,
                'order_id': str(instance.id),
                'previous_status': previous_status,
                'new_status': instance.status
            }
        )
        
        # Trigger async task
        send_payment_confirmation.delay(str(instance.id))
    
    # Trigger shipment notification when order becomes fulfilled
    if instance.status == 'fulfilled' and previous_status != 'fulfilled':
        logger.info(
            f"Order {instance.id} status changed to fulfilled, triggering shipment notification",
            extra={
                'tenant': instance.tenant.slug,
                'order_id': str(instance.id),
                'previous_status': previous_status,
                'new_status': instance.status
            }
        )
        
        # Trigger async task
        send_shipment_notification.delay(str(instance.id))
