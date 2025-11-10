"""
Tests for SubscriptionService.
"""
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from apps.tenants.models import (
    Tenant, SubscriptionTier, Subscription, 
    SubscriptionDiscount, SubscriptionEvent
)
from apps.tenants.services import SubscriptionService
from apps.core.exceptions import FeatureLimitExceeded, SubscriptionInactive


@pytest.mark.django_db
class TestSubscriptionService:
    """Test subscription service functionality."""
    
    @pytest.fixture
    def tier(self):
        """Create a test subscription tier."""
        return SubscriptionTier.objects.create(
            name='Test Tier',
            monthly_price=Decimal('99.00'),
            yearly_price=Decimal('950.00'),
            monthly_messages=1000,
            max_products=100,
            max_services=10,
            payment_facilitation=True,
            transaction_fee_percentage=Decimal('3.50')
        )
    
    @pytest.fixture
    def tenant(self, tier):
        """Create a test tenant."""
        return Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            twilio_sid='test_sid',
            twilio_token='test_token',
            webhook_secret='test_secret',
            subscription_tier=tier,
            status='active'
        )
    
    def test_check_subscription_status_active(self, tenant):
        """Test checking active subscription status."""
        # Create active subscription
        Subscription.objects.create(
            tenant=tenant,
            tier=tenant.subscription_tier,
            billing_cycle='monthly',
            status='active',
            start_date=timezone.now().date(),
            next_billing_date=(timezone.now() + timedelta(days=30)).date()
        )
        
        status = SubscriptionService.check_subscription_status(tenant)
        assert status == 'active'
    
    def test_check_subscription_status_trial(self, tenant):
        """Test checking trial subscription status."""
        tenant.status = 'trial'
        tenant.trial_start_date = timezone.now()
        tenant.trial_end_date = timezone.now() + timedelta(days=14)
        tenant.save()
        
        status = SubscriptionService.check_subscription_status(tenant)
        assert status == 'trial'
    
    def test_check_subscription_status_expired(self, tenant):
        """Test checking expired subscription status."""
        tenant.status = 'trial'
        tenant.trial_start_date = timezone.now() - timedelta(days=20)
        tenant.trial_end_date = timezone.now() - timedelta(days=5)
        tenant.save()
        
        status = SubscriptionService.check_subscription_status(tenant)
        assert status == 'expired'
    
    def test_check_subscription_status_waived(self, tenant):
        """Test checking waived subscription status."""
        tenant.subscription_waived = True
        tenant.save()
        
        status = SubscriptionService.check_subscription_status(tenant)
        assert status == 'active'
    
    def test_is_subscription_active(self, tenant):
        """Test checking if subscription is active."""
        # Create active subscription
        Subscription.objects.create(
            tenant=tenant,
            tier=tenant.subscription_tier,
            billing_cycle='monthly',
            status='active',
            start_date=timezone.now().date(),
            next_billing_date=(timezone.now() + timedelta(days=30)).date()
        )
        
        assert SubscriptionService.is_subscription_active(tenant) is True
    
    def test_is_subscription_inactive(self, tenant):
        """Test checking if subscription is inactive."""
        tenant.status = 'suspended'
        tenant.save()
        
        assert SubscriptionService.is_subscription_active(tenant) is False
    
    def test_apply_discounts_percentage(self, tenant):
        """Test applying percentage discount."""
        base_price = Decimal('100.00')
        
        # Create 20% discount
        SubscriptionDiscount.objects.create(
            tenant=tenant,
            discount_type='percentage',
            value=Decimal('20.00')
        )
        
        final_price, total_discount, applied = SubscriptionService.apply_discounts(
            tenant, base_price
        )
        
        assert final_price == Decimal('80.00')
        assert total_discount == Decimal('20.00')
        assert len(applied) == 1
        assert applied[0]['type'] == 'percentage'
    
    def test_apply_discounts_fixed_amount(self, tenant):
        """Test applying fixed amount discount."""
        base_price = Decimal('100.00')
        
        # Create $15 discount
        SubscriptionDiscount.objects.create(
            tenant=tenant,
            discount_type='fixed_amount',
            value=Decimal('15.00')
        )
        
        final_price, total_discount, applied = SubscriptionService.apply_discounts(
            tenant, base_price
        )
        
        assert final_price == Decimal('85.00')
        assert total_discount == Decimal('15.00')
        assert len(applied) == 1
    
    def test_apply_discounts_multiple(self, tenant):
        """Test applying multiple discounts."""
        base_price = Decimal('100.00')
        
        # Create two discounts
        SubscriptionDiscount.objects.create(
            tenant=tenant,
            discount_type='percentage',
            value=Decimal('10.00')
        )
        SubscriptionDiscount.objects.create(
            tenant=tenant,
            discount_type='fixed_amount',
            value=Decimal('5.00')
        )
        
        final_price, total_discount, applied = SubscriptionService.apply_discounts(
            tenant, base_price
        )
        
        assert final_price == Decimal('85.00')
        assert total_discount == Decimal('15.00')
        assert len(applied) == 2
    
    def test_apply_discounts_expired(self, tenant):
        """Test that expired discounts are not applied."""
        base_price = Decimal('100.00')
        
        # Create expired discount
        SubscriptionDiscount.objects.create(
            tenant=tenant,
            discount_type='percentage',
            value=Decimal('20.00'),
            expiry_date=(timezone.now() - timedelta(days=1)).date()
        )
        
        final_price, total_discount, applied = SubscriptionService.apply_discounts(
            tenant, base_price
        )
        
        assert final_price == base_price
        assert total_discount == Decimal('0')
        assert len(applied) == 0
    
    def test_create_free_trial(self, tenant):
        """Test creating a free trial."""
        tenant.status = 'active'
        tenant.save()
        
        updated_tenant = SubscriptionService.create_free_trial(tenant, duration_days=14)
        
        assert updated_tenant.status == 'trial'
        assert updated_tenant.trial_start_date is not None
        assert updated_tenant.trial_end_date is not None
        assert updated_tenant.has_valid_trial()
    
    def test_create_subscription(self, tenant, tier):
        """Test creating a subscription."""
        subscription = SubscriptionService.create_subscription(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly'
        )
        
        assert subscription.tenant == tenant
        assert subscription.tier == tier
        assert subscription.status == 'active'
        assert subscription.billing_cycle == 'monthly'
        
        # Check event was logged
        events = SubscriptionEvent.objects.filter(subscription=subscription)
        assert events.count() == 1
        assert events.first().event_type == 'created'
    
    def test_change_tier(self, tenant, tier):
        """Test changing subscription tier."""
        # Create subscription
        subscription = SubscriptionService.create_subscription(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly'
        )
        
        # Create new tier
        new_tier = SubscriptionTier.objects.create(
            name='Premium Tier',
            monthly_price=Decimal('199.00'),
            yearly_price=Decimal('1900.00')
        )
        
        # Change tier
        updated_subscription = SubscriptionService.change_tier(subscription, new_tier)
        
        assert updated_subscription.tier == new_tier
        
        # Check event was logged
        events = SubscriptionEvent.objects.filter(
            subscription=subscription,
            event_type='tier_changed'
        )
        assert events.count() == 1
    
    def test_cancel_subscription(self, tenant, tier):
        """Test canceling a subscription."""
        # Create subscription
        subscription = SubscriptionService.create_subscription(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly'
        )
        
        # Cancel subscription
        canceled = SubscriptionService.cancel_subscription(
            subscription,
            reason='Customer request'
        )
        
        assert canceled.status == 'canceled'
        assert canceled.canceled_at is not None
        
        # Check event was logged
        events = SubscriptionEvent.objects.filter(
            subscription=subscription,
            event_type='canceled'
        )
        assert events.count() == 1
    
    def test_suspend_subscription(self, tenant, tier):
        """Test suspending a subscription."""
        # Create subscription
        subscription = SubscriptionService.create_subscription(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly'
        )
        
        # Suspend subscription
        suspended = SubscriptionService.suspend_subscription(
            subscription,
            reason='Payment failed'
        )
        
        assert suspended.status == 'suspended'
        
        # Check event was logged
        events = SubscriptionEvent.objects.filter(
            subscription=subscription,
            event_type='suspended'
        )
        assert events.count() == 1
    
    def test_reactivate_subscription(self, tenant, tier):
        """Test reactivating a suspended subscription."""
        # Create and suspend subscription
        subscription = SubscriptionService.create_subscription(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly'
        )
        SubscriptionService.suspend_subscription(subscription)
        
        # Reactivate subscription
        reactivated = SubscriptionService.reactivate_subscription(subscription)
        
        assert reactivated.status == 'active'
        
        # Check event was logged
        events = SubscriptionEvent.objects.filter(
            subscription=subscription,
            event_type='reactivated'
        )
        assert events.count() == 1
