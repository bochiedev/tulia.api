"""
Subscription service for managing tenant subscriptions.

Handles subscription status checks, feature limit enforcement,
discount application, and free trial logic.
"""
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.db import models
from apps.tenants.models import (
    Tenant, Subscription, SubscriptionTier, 
    SubscriptionDiscount, SubscriptionEvent
)
from apps.core.exceptions import FeatureLimitExceeded, SubscriptionInactive


class SubscriptionService:
    """Service for subscription management and feature enforcement."""
    
    @staticmethod
    def check_subscription_status(tenant):
        """
        Check if tenant has active subscription or valid trial.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            str: Status - 'active', 'trial', 'expired', 'suspended'
        """
        # Check if subscription is waived
        if tenant.subscription_waived:
            return 'active'
        
        # Check for active subscription
        try:
            subscription = tenant.subscription
            if subscription.status == 'active':
                return 'active'
            elif subscription.status == 'suspended':
                return 'suspended'
            elif subscription.status == 'expired':
                return 'expired'
        except Subscription.DoesNotExist:
            pass
        
        # Check for valid free trial
        if tenant.has_valid_trial():
            return 'trial'
        
        # Check if trial has expired
        if tenant.status == 'trial' and tenant.trial_end_date:
            if timezone.now() > tenant.trial_end_date:
                return 'expired'
        
        return 'expired'
    
    @staticmethod
    def is_subscription_active(tenant):
        """
        Check if tenant can use the platform.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            bool: True if subscription is active or trial is valid
        """
        status = SubscriptionService.check_subscription_status(tenant)
        return status in ['active', 'trial']
    
    @staticmethod
    def enforce_feature_limit(tenant, feature_name, current_count=None):
        """
        Check if tenant can use a feature based on their tier limits.
        
        Args:
            tenant: Tenant instance
            feature_name: Feature to check (e.g., 'max_products', 'max_services')
            current_count: Current usage count (if None, will be calculated)
            
        Raises:
            FeatureLimitExceeded: If limit is exceeded
            SubscriptionInactive: If subscription is not active
        """
        # First check if subscription is active
        if not SubscriptionService.is_subscription_active(tenant):
            raise SubscriptionInactive(
                f"Subscription is inactive. Please update your payment method.",
                details={
                    'status': SubscriptionService.check_subscription_status(tenant),
                    'tenant_id': str(tenant.id)
                }
            )
        
        # Get the tier
        tier = tenant.subscription_tier
        if not tier:
            # No tier assigned, allow access (shouldn't happen in production)
            return
        
        # Get the limit for this feature
        limit = getattr(tier, feature_name, None)
        
        # None means unlimited
        if limit is None:
            return
        
        # Calculate current count if not provided
        if current_count is None:
            current_count = SubscriptionService._get_current_count(tenant, feature_name)
        
        # Check if limit is exceeded
        if current_count >= limit:
            raise FeatureLimitExceeded(
                f"Feature limit exceeded for {feature_name}. "
                f"Current: {current_count}, Limit: {limit}. "
                f"Please upgrade your subscription tier.",
                details={
                    'feature': feature_name,
                    'current_count': current_count,
                    'limit': limit,
                    'tier': tier.name,
                    'tenant_id': str(tenant.id)
                }
            )
    
    @staticmethod
    def _get_current_count(tenant, feature_name):
        """
        Get current usage count for a feature.
        
        Args:
            tenant: Tenant instance
            feature_name: Feature name
            
        Returns:
            int: Current count
        """
        if feature_name == 'max_products':
            from apps.catalog.models import Product
            return Product.objects.filter(tenant=tenant, is_active=True).count()
        
        elif feature_name == 'max_services':
            from apps.services.models import Service
            return Service.objects.filter(tenant=tenant, is_active=True).count()
        
        elif feature_name == 'monthly_messages':
            from apps.messaging.models import Message
            from datetime import timedelta
            start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return Message.objects.filter(
                conversation__tenant=tenant,
                direction='out',
                created_at__gte=start_of_month
            ).count()
        
        elif feature_name == 'max_campaign_sends':
            from apps.messaging.models import MessageCampaign
            from datetime import timedelta
            start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return MessageCampaign.objects.filter(
                tenant=tenant,
                created_at__gte=start_of_month
            ).aggregate(
                total=models.Sum('delivery_count')
            )['total'] or 0
        
        return 0
    
    @staticmethod
    def apply_discounts(tenant, base_price):
        """
        Calculate final price after applying all active discounts.
        
        Args:
            tenant: Tenant instance
            base_price: Base subscription price
            
        Returns:
            tuple: (final_price, total_discount, applied_discounts)
        """
        total_discount = Decimal('0')
        applied_discounts = []
        
        # Get all valid discounts for this tenant
        discounts = SubscriptionDiscount.objects.filter(
            tenant=tenant
        ).order_by('-value')  # Apply largest discounts first
        
        for discount in discounts:
            if discount.is_valid():
                discount_amount = discount.calculate_discount(base_price)
                total_discount += discount_amount
                applied_discounts.append({
                    'id': str(discount.id),
                    'type': discount.discount_type,
                    'value': float(discount.value),
                    'amount': float(discount_amount),
                    'code': discount.code
                })
        
        # Ensure final price is not negative
        final_price = max(Decimal('0'), base_price - total_discount)
        
        return final_price, total_discount, applied_discounts
    
    @staticmethod
    def create_free_trial(tenant, duration_days=None):
        """
        Create a free trial for a tenant.
        
        Args:
            tenant: Tenant instance
            duration_days: Trial duration in days (uses default if None)
            
        Returns:
            Tenant: Updated tenant instance
        """
        if duration_days is None:
            duration_days = getattr(settings, 'DEFAULT_TRIAL_DAYS', 14)
        
        from datetime import timedelta
        
        tenant.status = 'trial'
        tenant.trial_start_date = timezone.now()
        tenant.trial_end_date = timezone.now() + timedelta(days=duration_days)
        tenant.save(update_fields=['status', 'trial_start_date', 'trial_end_date'])
        
        return tenant
    
    @staticmethod
    def create_subscription(tenant, tier, billing_cycle='monthly', payment_method_id=None):
        """
        Create a new subscription for a tenant.
        
        Args:
            tenant: Tenant instance
            tier: SubscriptionTier instance
            billing_cycle: 'monthly' or 'yearly'
            payment_method_id: External payment method identifier
            
        Returns:
            Subscription: Created subscription
        """
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        # Calculate next billing date
        if billing_cycle == 'yearly':
            next_billing_date = (timezone.now() + relativedelta(years=1)).date()
        else:
            next_billing_date = (timezone.now() + relativedelta(months=1)).date()
        
        # Create subscription
        subscription = Subscription.objects.create(
            tenant=tenant,
            tier=tier,
            billing_cycle=billing_cycle,
            status='active',
            start_date=timezone.now().date(),
            next_billing_date=next_billing_date,
            payment_method_id=payment_method_id
        )
        
        # Update tenant status and tier
        tenant.status = 'active'
        tenant.subscription_tier = tier
        tenant.save(update_fields=['status', 'subscription_tier'])
        
        # Log event
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='created',
            metadata={
                'tier': tier.name,
                'billing_cycle': billing_cycle,
                'start_date': str(subscription.start_date)
            }
        )
        
        return subscription
    
    @staticmethod
    def change_tier(subscription, new_tier):
        """
        Change subscription tier with payment facilitation handling.
        
        Handles:
        - Wallet auto-creation on upgrade to payment facilitation tier
        - Balance validation on downgrade from payment facilitation tier
        
        Args:
            subscription: Subscription instance
            new_tier: New SubscriptionTier instance
            
        Returns:
            Subscription: Updated subscription
            
        Raises:
            WalletBalanceNotZero: If downgrading with non-zero wallet balance
        """
        from apps.tenants.services.payment_facilitation_service import PaymentFacilitationService
        
        old_tier = subscription.tier
        tenant = subscription.tenant
        
        # Validate tier downgrade if losing payment facilitation
        PaymentFacilitationService.validate_tier_downgrade(tenant, new_tier)
        
        # Update subscription tier
        subscription.tier = new_tier
        subscription.save(update_fields=['tier'])
        
        # Update tenant tier
        tenant.subscription_tier = new_tier
        tenant.save(update_fields=['subscription_tier'])
        
        # Handle tier upgrade (auto-create wallet if needed)
        wallet_result = PaymentFacilitationService.handle_tier_upgrade(tenant, new_tier)
        
        # Log event
        event_metadata = {
            'previous_tier': old_tier.name,
            'new_tier': new_tier.name
        }
        
        if wallet_result['wallet_created']:
            event_metadata['wallet_created'] = True
            event_metadata['wallet_id'] = wallet_result['wallet_id']
        
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='tier_changed',
            metadata=event_metadata
        )
        
        return subscription
    
    @staticmethod
    def cancel_subscription(subscription, reason=None):
        """
        Cancel a subscription.
        
        Args:
            subscription: Subscription instance
            reason: Optional cancellation reason
            
        Returns:
            Subscription: Updated subscription
        """
        subscription.status = 'canceled'
        subscription.canceled_at = timezone.now()
        subscription.save(update_fields=['status', 'canceled_at'])
        
        # Update tenant status
        subscription.tenant.status = 'canceled'
        subscription.tenant.save(update_fields=['status'])
        
        # Log event
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='canceled',
            metadata={
                'reason': reason,
                'canceled_at': str(subscription.canceled_at)
            }
        )
        
        return subscription
    
    @staticmethod
    def suspend_subscription(subscription, reason=None):
        """
        Suspend a subscription (e.g., due to payment failure).
        
        Args:
            subscription: Subscription instance
            reason: Optional suspension reason
            
        Returns:
            Subscription: Updated subscription
        """
        subscription.status = 'suspended'
        subscription.save(update_fields=['status'])
        
        # Update tenant status
        subscription.tenant.status = 'suspended'
        subscription.tenant.save(update_fields=['status'])
        
        # Log event
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='suspended',
            metadata={
                'reason': reason
            }
        )
        
        return subscription
    
    @staticmethod
    def reactivate_subscription(subscription):
        """
        Reactivate a suspended subscription.
        
        Args:
            subscription: Subscription instance
            
        Returns:
            Subscription: Updated subscription
        """
        subscription.status = 'active'
        subscription.save(update_fields=['status'])
        
        # Update tenant status
        subscription.tenant.status = 'active'
        subscription.tenant.save(update_fields=['status'])
        
        # Log event
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type='reactivated',
            metadata={}
        )
        
        return subscription
