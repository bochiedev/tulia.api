"""
Tests for MessageQueue model and manager.

Tests cover:
- Model creation and validation
- Manager query methods
- Status transitions
- Batch processing readiness
- Tenant isolation
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.messaging.models import MessageQueue, Conversation, Message
from apps.tenants.models import Tenant, Customer


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import SubscriptionTier
    tier = SubscriptionTier.objects.create(
        name='Test Tier',
        monthly_price=29.00,
        yearly_price=278.00
    )
    return Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
        whatsapp_number='+1234567890',
        subscription_tier=tier
    )


@pytest.fixture
def customer(tenant):
    """Create test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164='+1234567891',
        name='Test Customer'
    )


@pytest.fixture
def conversation(tenant, customer):
    """Create test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        status='open',
        channel='whatsapp'
    )


@pytest.fixture
def message(conversation):
    """Create test message."""
    return Message.objects.create(
        conversation=conversation,
        direction='in',
        message_type='customer_inbound',
        text='Hello, I need help'
    )


@pytest.mark.django_db
class TestMessageQueueModel:
    """Tests for MessageQueue model."""
    
    def test_create_message_queue(self, conversation, message):
        """Test creating a message queue entry."""
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        assert queue_entry.id is not None
        assert queue_entry.conversation == conversation
        assert queue_entry.message == message
        assert queue_entry.status == 'queued'
        assert queue_entry.queue_position == 1
        assert queue_entry.queued_at is not None
        assert queue_entry.processed_at is None
        assert queue_entry.error_message is None
    
    def test_message_queue_str(self, conversation, message):
        """Test string representation."""
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        str_repr = str(queue_entry)
        assert str(queue_entry.id) in str_repr
        assert str(conversation.id) in str_repr
        assert "Position 1" in str_repr
    
    def test_message_must_belong_to_conversation(self, conversation, message):
        """Test that message must belong to the same conversation."""
        # Create another conversation
        other_conversation = Conversation.objects.create(
            tenant=conversation.tenant,
            customer=conversation.customer,
            status='open',
            channel='whatsapp'
        )
        
        # Try to create queue entry with mismatched conversation
        with pytest.raises(ValueError) as exc_info:
            queue_entry = MessageQueue(
                conversation=other_conversation,
                message=message,
                queue_position=1
            )
            queue_entry.save()
        
        assert "must match" in str(exc_info.value)
    
    def test_unique_queue_position_per_conversation(self, conversation, message):
        """Test that queue position must be unique per conversation."""
        # Create first queue entry
        MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        # Create another message
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Another message'
        )
        
        # Try to create another entry with same position
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            MessageQueue.objects.create(
                conversation=conversation,
                message=message2,
                queue_position=1
            )


@pytest.mark.django_db
class TestMessageQueueManager:
    """Tests for MessageQueue manager methods."""
    
    def test_for_conversation(self, conversation, message):
        """Test getting queued messages for a conversation."""
        # Create multiple queue entries
        queue1 = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Second message'
        )
        queue2 = MessageQueue.objects.create(
            conversation=conversation,
            message=message2,
            queue_position=2
        )
        
        # Get messages for conversation
        queued = MessageQueue.objects.for_conversation(conversation)
        
        assert queued.count() == 2
        assert list(queued) == [queue1, queue2]  # Ordered by position
    
    def test_pending(self, conversation, message):
        """Test getting pending messages."""
        # Create queued message
        queue1 = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1,
            status='queued'
        )
        
        # Create processed message
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Second message'
        )
        queue2 = MessageQueue.objects.create(
            conversation=conversation,
            message=message2,
            queue_position=2,
            status='processed'
        )
        
        # Get pending messages
        pending = MessageQueue.objects.pending()
        
        assert pending.count() == 1
        assert pending.first() == queue1
    
    def test_pending_for_conversation(self, conversation, message):
        """Test getting pending messages for specific conversation."""
        # Create queued message
        queue1 = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1,
            status='queued'
        )
        
        # Create another conversation with queued message
        other_conversation = Conversation.objects.create(
            tenant=conversation.tenant,
            customer=conversation.customer,
            status='open',
            channel='whatsapp'
        )
        message2 = Message.objects.create(
            conversation=other_conversation,
            direction='in',
            message_type='customer_inbound',
            text='Other message'
        )
        MessageQueue.objects.create(
            conversation=other_conversation,
            message=message2,
            queue_position=1,
            status='queued'
        )
        
        # Get pending for specific conversation
        pending = MessageQueue.objects.pending(conversation=conversation)
        
        assert pending.count() == 1
        assert pending.first() == queue1
    
    def test_processing(self, conversation, message):
        """Test getting messages currently being processed."""
        # Create processing message
        queue1 = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1,
            status='processing'
        )
        
        # Create queued message
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Second message'
        )
        MessageQueue.objects.create(
            conversation=conversation,
            message=message2,
            queue_position=2,
            status='queued'
        )
        
        # Get processing messages
        processing = MessageQueue.objects.processing()
        
        assert processing.count() == 1
        assert processing.first() == queue1
    
    def test_ready_for_batch(self, conversation, message):
        """Test getting messages ready for batch processing."""
        # Create old queued message (ready)
        old_time = timezone.now() - timedelta(seconds=10)
        queue1 = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1,
            status='queued'
        )
        MessageQueue.objects.filter(id=queue1.id).update(queued_at=old_time)
        queue1.refresh_from_db()
        
        # Create recent queued message (not ready)
        message2 = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text='Second message'
        )
        queue2 = MessageQueue.objects.create(
            conversation=conversation,
            message=message2,
            queue_position=2,
            status='queued'
        )
        
        # Get ready messages (5 second delay)
        ready = MessageQueue.objects.ready_for_batch(conversation, delay_seconds=5)
        
        assert ready.count() == 1
        assert ready.first() == queue1


@pytest.mark.django_db
class TestMessageQueueStatusTransitions:
    """Tests for status transition methods."""
    
    def test_mark_processing(self, conversation, message):
        """Test marking message as processing."""
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        assert queue_entry.status == 'queued'
        
        queue_entry.mark_processing()
        queue_entry.refresh_from_db()
        
        assert queue_entry.status == 'processing'
    
    def test_mark_processed(self, conversation, message):
        """Test marking message as processed."""
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        queue_entry.mark_processed()
        queue_entry.refresh_from_db()
        
        assert queue_entry.status == 'processed'
        assert queue_entry.processed_at is not None
    
    def test_mark_failed(self, conversation, message):
        """Test marking message as failed."""
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        error_msg = "Processing failed due to timeout"
        queue_entry.mark_failed(error_message=error_msg)
        queue_entry.refresh_from_db()
        
        assert queue_entry.status == 'failed'
        assert queue_entry.processed_at is not None
        assert queue_entry.error_message == error_msg
    
    def test_is_ready_for_batch(self, conversation, message):
        """Test checking if message is ready for batch processing."""
        # Create old queued message
        old_time = timezone.now() - timedelta(seconds=10)
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1,
            status='queued'
        )
        MessageQueue.objects.filter(id=queue_entry.id).update(queued_at=old_time)
        queue_entry.refresh_from_db()
        
        # Should be ready (10 seconds > 5 second delay)
        assert queue_entry.is_ready_for_batch(delay_seconds=5) is True
        
        # Should not be ready with longer delay
        assert queue_entry.is_ready_for_batch(delay_seconds=15) is False
    
    def test_is_ready_for_batch_not_queued(self, conversation, message):
        """Test that non-queued messages are not ready."""
        queue_entry = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1,
            status='processing'
        )
        
        # Not ready because status is not 'queued'
        assert queue_entry.is_ready_for_batch(delay_seconds=0) is False


@pytest.mark.django_db
class TestMessageQueueTenantIsolation:
    """Tests for tenant isolation in message queue."""
    
    def test_queue_entries_isolated_by_tenant(self, tenant, customer, conversation, message):
        """Test that queue entries are isolated by tenant."""
        # Create queue entry for first tenant
        queue1 = MessageQueue.objects.create(
            conversation=conversation,
            message=message,
            queue_position=1
        )
        
        # Create second tenant with conversation
        from apps.tenants.models import SubscriptionTier
        tier = SubscriptionTier.objects.create(
            name='Test Tier 2',
            monthly_price=29.00,
            yearly_price=278.00
        )
        tenant2 = Tenant.objects.create(
            name='Test Tenant 2',
            slug='test-tenant-2',
            whatsapp_number='+1234567892',
            subscription_tier=tier
        )
        customer2 = Customer.objects.create(
            tenant=tenant2,
            phone_e164='+1234567893',
            name='Test Customer 2'
        )
        conversation2 = Conversation.objects.create(
            tenant=tenant2,
            customer=customer2,
            status='open',
            channel='whatsapp'
        )
        message2 = Message.objects.create(
            conversation=conversation2,
            direction='in',
            message_type='customer_inbound',
            text='Hello from tenant 2'
        )
        queue2 = MessageQueue.objects.create(
            conversation=conversation2,
            message=message2,
            queue_position=1
        )
        
        # Verify isolation through conversation relationship
        tenant1_queues = MessageQueue.objects.filter(
            conversation__tenant=tenant
        )
        tenant2_queues = MessageQueue.objects.filter(
            conversation__tenant=tenant2
        )
        
        assert tenant1_queues.count() == 1
        assert tenant1_queues.first() == queue1
        assert tenant2_queues.count() == 1
        assert tenant2_queues.first() == queue2
