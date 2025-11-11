"""
Tests for ScheduledMessage model.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from apps.messaging.models import ScheduledMessage, Message, MessageTemplate
from apps.tenants.models import Tenant, SubscriptionTier


@pytest.mark.django_db
class TestScheduledMessageModel:
    """Test ScheduledMessage model functionality."""
    
    def test_create_scheduled_message(self, tenant, customer):
        """Test creating a scheduled message."""
        scheduled_at = timezone.now() + timedelta(hours=1)
        
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test scheduled message",
            scheduled_at=scheduled_at,
            message_type='scheduled_promotional'
        )
        
        assert scheduled_msg.tenant == tenant
        assert scheduled_msg.customer == customer
        assert scheduled_msg.status == 'pending'
        assert scheduled_msg.content == "Test scheduled message"
    
    def test_scheduled_message_tenant_isolation(self, tenant, customer):
        """Test that scheduled messages are tenant-scoped."""
        # Create scheduled message for tenant A
        scheduled_msg_a = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Message for tenant A",
            scheduled_at=timezone.now() + timedelta(hours=1)
        )
        
        # Create another tenant
        tier = SubscriptionTier.objects.first()
        tenant_b = Tenant.objects.create(
            name='Tenant B',
            slug='tenant-b',
            whatsapp_number='+14155559999',
            twilio_sid='test_sid_b',
            twilio_token='test_token_b',
            webhook_secret='test_secret_b',
            subscription_tier=tier
        )
        
        # Query for tenant B should not return tenant A's messages
        tenant_b_messages = ScheduledMessage.objects.for_tenant(tenant_b)
        assert scheduled_msg_a not in tenant_b_messages
        
        # Query for tenant A should return the message
        tenant_a_messages = ScheduledMessage.objects.for_tenant(tenant)
        assert scheduled_msg_a in tenant_a_messages
    
    def test_pending_manager_method(self, tenant, customer):
        """Test pending() manager method."""
        # Create pending message
        pending_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Pending message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        # Create sent message
        sent_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Sent message",
            scheduled_at=timezone.now() - timedelta(hours=1),
            status='sent'
        )
        
        # pending() should only return pending messages
        pending_messages = ScheduledMessage.objects.pending(tenant)
        assert pending_msg in pending_messages
        assert sent_msg not in pending_messages
    
    def test_due_for_sending_manager_method(self, tenant, customer):
        """Test due_for_sending() manager method."""
        # Create message due now
        due_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Due message",
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending'
        )
        
        # Create message due in future
        future_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Future message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        # due_for_sending() should only return messages with scheduled_at <= now
        due_messages = ScheduledMessage.objects.due_for_sending()
        assert due_msg in due_messages
        assert future_msg not in due_messages
    
    def test_mark_sent(self, tenant, customer):
        """Test mark_sent() method."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        # Mark as sent
        scheduled_msg.mark_sent()
        
        assert scheduled_msg.status == 'sent'
        assert scheduled_msg.sent_at is not None
    
    def test_mark_failed(self, tenant, customer):
        """Test mark_failed() method."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        # Mark as failed
        error_msg = "Twilio API error"
        scheduled_msg.mark_failed(error_msg)
        
        assert scheduled_msg.status == 'failed'
        assert scheduled_msg.failed_at is not None
        assert scheduled_msg.error_message == error_msg
    
    def test_cancel_pending_message(self, tenant, customer):
        """Test cancel() method on pending message."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        # Cancel should succeed
        result = scheduled_msg.cancel()
        
        assert result is True
        assert scheduled_msg.status == 'canceled'
    
    def test_cancel_sent_message_fails(self, tenant, customer):
        """Test that cancel() fails on already sent message."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test message",
            scheduled_at=timezone.now() - timedelta(hours=1),
            status='sent'
        )
        
        # Cancel should fail
        result = scheduled_msg.cancel()
        
        assert result is False
        assert scheduled_msg.status == 'sent'  # Status unchanged
    
    def test_is_due_method(self, tenant, customer):
        """Test is_due() method."""
        # Create message due now
        due_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Due message",
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending'
        )
        
        # Create message due in future
        future_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Future message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        assert due_msg.is_due() is True
        assert future_msg.is_due() is False
    
    def test_broadcast_message_no_customer(self, tenant):
        """Test creating broadcast message without customer."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=None,  # Broadcast message
            content="Broadcast message",
            scheduled_at=timezone.now() + timedelta(hours=1),
            recipient_criteria={'tags': ['vip']},
            message_type='scheduled_promotional'
        )
        
        assert scheduled_msg.customer is None
        assert scheduled_msg.recipient_criteria == {'tags': ['vip']}
    
    def test_for_customer_manager_method(self, tenant, customer):
        """Test for_customer() manager method."""
        # Create message for customer A
        msg_a = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Message for customer A",
            scheduled_at=timezone.now() + timedelta(hours=1)
        )
        
        # Create another customer
        from apps.rbac.models import User
        customer_b = tenant.customers.create(
            phone_e164='+14155558888',
            name='Customer B'
        )
        
        # Create message for customer B
        msg_b = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer_b,
            content="Message for customer B",
            scheduled_at=timezone.now() + timedelta(hours=1)
        )
        
        # for_customer should only return messages for that customer
        customer_a_messages = ScheduledMessage.objects.for_customer(tenant, customer)
        assert msg_a in customer_a_messages
        assert msg_b not in customer_a_messages


# Fixtures
@pytest.fixture
def subscription_tier():
    """Create a subscription tier for testing."""
    return SubscriptionTier.objects.create(
        name='Starter',
        monthly_price=29.00,
        yearly_price=278.00,
        monthly_messages=1000,
        max_products=100,
        max_services=10
    )


@pytest.fixture
def tenant(subscription_tier):
    """Create a tenant for testing."""
    return Tenant.objects.create(
        name='Test Business',
        slug='test-business',
        whatsapp_number='+14155551234',
        twilio_sid='test_sid',
        twilio_token='test_token',
        webhook_secret='test_secret',
        subscription_tier=subscription_tier
    )


@pytest.fixture
def customer(tenant):
    """Create a customer for testing."""
    return tenant.customers.create(
        phone_e164='+14155557777',
        name='Test Customer'
    )
