"""
Tests for scheduled message functionality.
"""
import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase
from apps.messaging.models import ScheduledMessage, Message
from apps.messaging.services import MessagingService
from apps.messaging.tasks import process_scheduled_messages
from apps.tenants.models import Tenant, Customer


@pytest.mark.django_db
class TestScheduledMessageModel:
    """Test ScheduledMessage model and manager."""
    
    def test_create_scheduled_message(self, tenant, customer):
        """Test creating a scheduled message."""
        scheduled_at = timezone.now() + timedelta(hours=1)
        
        msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test scheduled message",
            scheduled_at=scheduled_at,
            message_type='scheduled_promotional'
        )
        
        assert msg.status == 'pending'
        assert msg.tenant == tenant
        assert msg.customer == customer
        assert msg.sent_at is None
    
    def test_for_tenant_manager_method(self, tenant, tenant_b, customer):
        """Test for_tenant manager method filters correctly."""
        scheduled_at = timezone.now() + timedelta(hours=1)
        
        # Create message for tenant A
        msg_a = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Message A",
            scheduled_at=scheduled_at
        )
        
        # Create message for tenant B
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164="+254722000002",
            name="Customer B"
        )
        msg_b = ScheduledMessage.objects.create(
            tenant=tenant_b,
            customer=customer_b,
            content="Message B",
            scheduled_at=scheduled_at
        )
        
        # Verify tenant isolation
        tenant_a_messages = ScheduledMessage.objects.for_tenant(tenant)
        assert tenant_a_messages.count() == 1
        assert msg_a in tenant_a_messages
        assert msg_b not in tenant_a_messages
        
        tenant_b_messages = ScheduledMessage.objects.for_tenant(tenant_b)
        assert tenant_b_messages.count() == 1
        assert msg_b in tenant_b_messages
        assert msg_a not in tenant_b_messages
    
    def test_pending_manager_method(self, tenant, customer):
        """Test pending manager method."""
        scheduled_at = timezone.now() + timedelta(hours=1)
        
        # Create pending message
        pending_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Pending",
            scheduled_at=scheduled_at,
            status='pending'
        )
        
        # Create sent message
        sent_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Sent",
            scheduled_at=scheduled_at,
            status='sent'
        )
        
        pending_messages = ScheduledMessage.objects.pending(tenant=tenant)
        assert pending_messages.count() == 1
        assert pending_msg in pending_messages
        assert sent_msg not in pending_messages
    
    def test_due_for_sending_manager_method(self, tenant, customer):
        """Test due_for_sending manager method."""
        now = timezone.now()
        
        # Create message due now
        due_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Due now",
            scheduled_at=now - timedelta(minutes=1),
            status='pending'
        )
        
        # Create future message
        future_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Future",
            scheduled_at=now + timedelta(hours=1),
            status='pending'
        )
        
        # Create already sent message
        sent_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Sent",
            scheduled_at=now - timedelta(hours=1),
            status='sent'
        )
        
        due_messages = ScheduledMessage.objects.due_for_sending()
        assert due_messages.count() == 1
        assert due_msg in due_messages
        assert future_msg not in due_messages
        assert sent_msg not in due_messages
    
    def test_mark_sent(self, tenant, customer, conversation):
        """Test marking scheduled message as sent."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test",
            scheduled_at=timezone.now()
        )
        
        # Create a message
        message = Message.objects.create(
            conversation=conversation,
            direction='out',
            text="Test",
            message_type='scheduled_promotional'
        )
        
        scheduled_msg.mark_sent(message=message)
        
        assert scheduled_msg.status == 'sent'
        assert scheduled_msg.sent_at is not None
        assert scheduled_msg.message == message
    
    def test_mark_sent_validates_tenant(self, tenant, tenant_b, customer, conversation):
        """Test mark_sent validates message belongs to same tenant."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test",
            scheduled_at=timezone.now()
        )
        
        # Create customer and conversation for tenant B
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164="+254722000002",
            name="Customer B"
        )
        conversation_b = customer_b.conversations.create(
            tenant=tenant_b,
            status='active'
        )
        
        # Create message for tenant B
        message_b = Message.objects.create(
            conversation=conversation_b,
            direction='out',
            text="Test",
            message_type='scheduled_promotional'
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Message must belong to same tenant"):
            scheduled_msg.mark_sent(message=message_b)
    
    def test_mark_failed(self, tenant, customer):
        """Test marking scheduled message as failed."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test",
            scheduled_at=timezone.now()
        )
        
        error_msg = "Failed to send: API error"
        scheduled_msg.mark_failed(error_message=error_msg)
        
        assert scheduled_msg.status == 'failed'
        assert scheduled_msg.failed_at is not None
        assert scheduled_msg.error_message == error_msg
    
    def test_cancel(self, tenant, customer):
        """Test canceling a pending scheduled message."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test",
            scheduled_at=timezone.now() + timedelta(hours=1),
            status='pending'
        )
        
        result = scheduled_msg.cancel()
        
        assert result is True
        assert scheduled_msg.status == 'canceled'
    
    def test_cancel_already_sent(self, tenant, customer):
        """Test canceling an already sent message returns False."""
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test",
            scheduled_at=timezone.now(),
            status='sent'
        )
        
        result = scheduled_msg.cancel()
        
        assert result is False
        assert scheduled_msg.status == 'sent'  # Status unchanged
    
    def test_is_due(self, tenant, customer):
        """Test is_due method."""
        now = timezone.now()
        
        # Due message
        due_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Due",
            scheduled_at=now - timedelta(minutes=1),
            status='pending'
        )
        
        # Future message
        future_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Future",
            scheduled_at=now + timedelta(hours=1),
            status='pending'
        )
        
        # Sent message
        sent_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Sent",
            scheduled_at=now - timedelta(hours=1),
            status='sent'
        )
        
        assert due_msg.is_due() is True
        assert future_msg.is_due() is False
        assert sent_msg.is_due() is False


@pytest.mark.django_db
class TestScheduledMessageService:
    """Test MessagingService.schedule_message method."""
    
    def test_schedule_message(self, tenant, customer):
        """Test scheduling a message."""
        scheduled_at = timezone.now() + timedelta(hours=1)
        
        # Use transactional message type to skip quiet hours check
        scheduled_msg = MessagingService.schedule_message(
            tenant=tenant,
            customer=customer,
            content="Test scheduled message",
            scheduled_at=scheduled_at,
            message_type='automated_transactional'
        )
        
        assert scheduled_msg.id is not None
        assert scheduled_msg.tenant == tenant
        assert scheduled_msg.customer == customer
        assert scheduled_msg.content == "Test scheduled message"
        assert scheduled_msg.status == 'pending'
    
    def test_schedule_message_validates_future_time(self, tenant, customer):
        """Test scheduling a message validates scheduled_at is in future."""
        past_time = timezone.now() - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="scheduled_at must be in the future"):
            MessagingService.schedule_message(
                tenant=tenant,
                customer=customer,
                content="Test",
                scheduled_at=past_time
            )


@pytest.mark.django_db
class TestScheduledMessageTask:
    """Test process_scheduled_messages Celery task."""
    
    def test_process_no_due_messages(self):
        """Test task when no messages are due."""
        result = process_scheduled_messages()
        
        assert result['status'] == 'success'
        assert result['total'] == 0
        assert result['sent'] == 0
        assert result['failed'] == 0
    
    def test_process_due_messages(self, tenant, customer, monkeypatch):
        """Test task processes due messages."""
        # Mock TwilioService to avoid actual API calls
        from apps.integrations.services.twilio_service import TwilioService
        from apps.messaging.models import CustomerPreferences
        
        def mock_send_whatsapp(*args, **kwargs):
            return {'sid': 'SM123', 'status': 'queued'}
        
        monkeypatch.setattr(
            TwilioService,
            'send_whatsapp',
            mock_send_whatsapp
        )
        
        # Set up customer consent for promotional messages
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer,
            promotional_messages=True
        )
        
        # Create due messages
        now = timezone.now()
        msg1 = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Message 1",
            scheduled_at=now - timedelta(minutes=5),
            status='pending',
            message_type='scheduled_promotional'
        )
        msg2 = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Message 2",
            scheduled_at=now - timedelta(minutes=1),
            status='pending',
            message_type='scheduled_promotional'
        )
        
        # Run task
        result = process_scheduled_messages()
        
        assert result['status'] == 'completed'
        assert result['total'] == 2
        assert result['sent'] == 2
        assert result['failed'] == 0
        
        # Verify messages were marked as sent
        msg1.refresh_from_db()
        msg2.refresh_from_db()
        assert msg1.status == 'sent'
        assert msg2.status == 'sent'
        assert msg1.sent_at is not None
        assert msg2.sent_at is not None
    
    def test_process_handles_failures(self, tenant, customer, monkeypatch):
        """Test task handles sending failures gracefully."""
        # Mock TwilioService to raise an error
        from apps.integrations.services.twilio_service import TwilioService
        from apps.messaging.models import CustomerPreferences
        
        def mock_send_error(*args, **kwargs):
            raise Exception("API error")
        
        monkeypatch.setattr(
            TwilioService,
            'send_whatsapp',
            mock_send_error
        )
        
        # Set up customer consent
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer,
            promotional_messages=True
        )
        
        # Create due message
        msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content="Test",
            scheduled_at=timezone.now() - timedelta(minutes=1),
            status='pending',
            message_type='scheduled_promotional'
        )
        
        # Run task
        result = process_scheduled_messages()
        
        assert result['status'] == 'completed'
        assert result['total'] == 1
        assert result['sent'] == 0
        assert result['failed'] == 1
        
        # Verify message was marked as failed
        msg.refresh_from_db()
        assert msg.status == 'failed'
        assert msg.failed_at is not None
        assert 'API error' in msg.error_message


# Fixtures
@pytest.fixture
def tenant():
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        status="active"
    )


@pytest.fixture
def tenant_b():
    """Create a second test tenant."""
    return Tenant.objects.create(
        name="Test Tenant B",
        slug="test-tenant-b",
        whatsapp_number="+254722999999",
        status="active"
    )


@pytest.fixture
def customer(tenant):
    """Create a test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+254722000001",
        name="Test Customer"
    )


@pytest.fixture
def conversation(tenant, customer):
    """Create a test conversation."""
    return customer.conversations.create(
        tenant=tenant,
        status='active'
    )
