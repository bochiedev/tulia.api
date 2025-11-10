"""
Celery tasks for subscription billing and management.

Handles recurring billing, payment retries, and notifications.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from celery import shared_task
from apps.tenants.models import (
    Subscription, SubscriptionEvent, Tenant
)
from apps.tenants.services import SubscriptionService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_billing(self, subscription_id):
    """
    Process recurring billing for a subscription.
    
    Args:
        subscription_id: UUID of the subscription
        
    Returns:
        dict: Result with status and details
    """
    try:
        subscription = Subscription.objects.select_related('tenant', 'tier').get(
            id=subscription_id
        )
    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {'status': 'error', 'message': 'Subscription not found'}
    
    logger.info(
        f"Processing billing for subscription {subscription_id} "
        f"(tenant: {subscription.tenant.name})"
    )
    
    # Calculate price with discounts
    base_price = subscription.calculate_price()
    final_price, total_discount, applied_discounts = SubscriptionService.apply_discounts(
        subscription.tenant, base_price
    )
    
    # Attempt to charge payment method
    # TODO: Integrate with actual payment gateway (Stripe, PayPal, etc.)
    payment_success = _charge_payment_method(
        subscription.payment_method_id,
        final_price,
        subscription.tenant.contact_email,
        {
            'subscription_id': str(subscription.id),
            'tenant_id': str(subscription.tenant.id),
            'tier': subscription.tier.name,
            'billing_cycle': subscription.billing_cycle
        }
    )
    
    if payment_success:
        # Payment succeeded - update subscription
        from dateutil.relativedelta import relativedelta
        
        if subscription.billing_cycle == 'yearly':
            subscription.next_billing_date = (
                timezone.now() + relativedelta(years=1)
            ).date()
        else:
            subscription.next_billing_date = (
                timezone.now() + relativedelta(months=1)
            ).date()
        
        subscription.save(update_fields=['next_billing_date'])
        
        # Log success event
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='payment_succeeded',
            metadata={
                'amount': float(final_price),
                'base_price': float(base_price),
                'discount': float(total_discount),
                'next_billing_date': str(subscription.next_billing_date)
            }
        )
        
        # Increment discount usage counts
        for discount_info in applied_discounts:
            from apps.tenants.models import SubscriptionDiscount
            try:
                discount = SubscriptionDiscount.objects.get(id=discount_info['id'])
                discount.usage_count += 1
                discount.save(update_fields=['usage_count'])
            except SubscriptionDiscount.DoesNotExist:
                pass
        
        logger.info(
            f"Billing successful for subscription {subscription_id}. "
            f"Amount: ${final_price}"
        )
        
        return {
            'status': 'success',
            'amount': float(final_price),
            'next_billing_date': str(subscription.next_billing_date)
        }
    
    else:
        # Payment failed - log event and schedule retry
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='payment_failed',
            metadata={
                'amount': float(final_price),
                'retry_count': self.request.retries
            }
        )
        
        logger.warning(
            f"Billing failed for subscription {subscription_id}. "
            f"Retry {self.request.retries + 1}/3"
        )
        
        # Schedule retry with exponential backoff
        if self.request.retries < 2:
            # Retry after 1 day, then 3 days, then 3 days (total 7 days)
            retry_delays = [86400, 259200, 259200]  # seconds
            retry_delay = retry_delays[self.request.retries]
            
            # Send notification about failed payment
            _send_payment_failure_notification(
                subscription.tenant,
                retry_count=self.request.retries + 1,
                next_retry_hours=retry_delay // 3600
            )
            
            raise self.retry(countdown=retry_delay)
        else:
            # Final retry failed - suspend subscription
            logger.error(
                f"All billing retries failed for subscription {subscription_id}. "
                f"Suspending subscription."
            )
            
            SubscriptionService.suspend_subscription(
                subscription,
                reason="Payment failed after 3 attempts"
            )
            
            # Send final notification
            _send_subscription_suspended_notification(subscription.tenant)
            
            return {
                'status': 'failed',
                'message': 'Payment failed after 3 attempts. Subscription suspended.'
            }


@shared_task
def check_upcoming_renewals():
    """
    Check for subscriptions due for renewal and send reminders.
    
    Sends reminders at 7 days and 3 days before renewal.
    """
    from datetime import date
    
    today = date.today()
    seven_days = today + timedelta(days=7)
    three_days = today + timedelta(days=3)
    
    # 7-day reminders
    subscriptions_7d = Subscription.objects.filter(
        status='active',
        next_billing_date=seven_days
    ).select_related('tenant', 'tier')
    
    for subscription in subscriptions_7d:
        _send_renewal_reminder(
            subscription.tenant,
            days_until_renewal=7,
            amount=subscription.calculate_price()
        )
        logger.info(
            f"Sent 7-day renewal reminder to {subscription.tenant.name}"
        )
    
    # 3-day reminders
    subscriptions_3d = Subscription.objects.filter(
        status='active',
        next_billing_date=three_days
    ).select_related('tenant', 'tier')
    
    for subscription in subscriptions_3d:
        _send_renewal_reminder(
            subscription.tenant,
            days_until_renewal=3,
            amount=subscription.calculate_price()
        )
        logger.info(
            f"Sent 3-day renewal reminder to {subscription.tenant.name}"
        )
    
    return {
        'reminders_7d': subscriptions_7d.count(),
        'reminders_3d': subscriptions_3d.count()
    }


@shared_task
def check_trial_expirations():
    """
    Check for trials expiring soon and send notifications.
    
    Sends notifications at 3 days before trial expiration.
    """
    from datetime import date
    
    three_days_from_now = timezone.now() + timedelta(days=3)
    
    tenants = Tenant.objects.filter(
        status='trial',
        trial_end_date__date=three_days_from_now.date()
    )
    
    for tenant in tenants:
        _send_trial_expiring_notification(tenant, days_remaining=3)
        logger.info(f"Sent trial expiration reminder to {tenant.name}")
    
    return {'notifications_sent': tenants.count()}


@shared_task
def process_due_subscriptions():
    """
    Process all subscriptions due for billing today.
    
    This task should run daily (e.g., at 2 AM).
    """
    from datetime import date
    
    today = date.today()
    
    due_subscriptions = Subscription.objects.filter(
        status='active',
        next_billing_date=today
    ).select_related('tenant', 'tier')
    
    logger.info(f"Found {due_subscriptions.count()} subscriptions due for billing")
    
    for subscription in due_subscriptions:
        # Queue individual billing task
        process_billing.delay(str(subscription.id))
    
    return {
        'subscriptions_queued': due_subscriptions.count(),
        'date': str(today)
    }


# Helper functions for payment and notifications

def _charge_payment_method(payment_method_id, amount, customer_email, metadata):
    """
    Charge a payment method.
    
    TODO: Integrate with actual payment gateway (Stripe, PayPal, etc.)
    
    Args:
        payment_method_id: Payment method identifier
        amount: Amount to charge
        customer_email: Customer email
        metadata: Additional metadata
        
    Returns:
        bool: True if payment succeeded, False otherwise
    """
    # Stub implementation - always succeeds for now
    # In production, this would call Stripe, PayPal, etc.
    logger.info(
        f"[STUB] Charging ${amount} to payment method {payment_method_id} "
        f"for {customer_email}"
    )
    return True


def _send_renewal_reminder(tenant, days_until_renewal, amount):
    """
    Send renewal reminder email to tenant.
    
    Args:
        tenant: Tenant instance
        days_until_renewal: Days until renewal
        amount: Renewal amount
    """
    # TODO: Implement email sending
    logger.info(
        f"[STUB] Sending renewal reminder to {tenant.contact_email}: "
        f"{days_until_renewal} days until renewal, amount: ${amount}"
    )


def _send_payment_failure_notification(tenant, retry_count, next_retry_hours):
    """
    Send payment failure notification to tenant.
    
    Args:
        tenant: Tenant instance
        retry_count: Current retry attempt
        next_retry_hours: Hours until next retry
    """
    # TODO: Implement email sending
    logger.info(
        f"[STUB] Sending payment failure notification to {tenant.contact_email}: "
        f"Retry {retry_count}/3, next retry in {next_retry_hours} hours"
    )


def _send_subscription_suspended_notification(tenant):
    """
    Send subscription suspended notification to tenant.
    
    Args:
        tenant: Tenant instance
    """
    # TODO: Implement email sending
    logger.info(
        f"[STUB] Sending subscription suspended notification to {tenant.contact_email}"
    )


def _send_trial_expiring_notification(tenant, days_remaining):
    """
    Send trial expiring notification to tenant.
    
    Args:
        tenant: Tenant instance
        days_remaining: Days remaining in trial
    """
    # TODO: Implement email sending
    logger.info(
        f"[STUB] Sending trial expiring notification to {tenant.contact_email}: "
        f"{days_remaining} days remaining"
    )
