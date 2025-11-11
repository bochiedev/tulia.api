"""
Tests for automated messaging tasks and signals.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch, MagicMock
from apps.messaging.tasks import (
    send_payment_confirmation,
    send_shipment_notification,
    send_payment_failed_notification,
    send_booking_confirmation,
    send_24h_appointment_reminders,
    send_2h_appointment_reminders,
    send_reengagement_messages
)
from apps.messaging.models import Message, Conversation, CustomerPreferences
from apps.orders.models import Order
from apps.services.models import Appointment, Service, ServiceVariant
from apps.tenants.models import Tenant, Customer


@pytest.mark.django_db
class TestTransactionalMessageTasks:
    """Test transactional message Celery tasks."""
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_payment_confirmation(self, mock_twilio, tenant, customer, conversation):
        """Test payment confirmation task."""
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Create paid order
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=100.00,
            total=100.00,
            status='paid'
        )
        
        # Run task
        result = send_payment_confirmation(str(order.id))
        
        assert result['status'] == 'sent'
        assert 'message_id' in result
        
        # Verify message was created
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_transactional'
        )
        assert messages.count() == 1
        assert 'Payment confirmed' in messages.first().text
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_shipment_notification(self, mock_twilio, tenant, customer):
        """Test shipment notification task."""
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Create fulfilled order with tracking
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=100.00,
            total=100.00,
            status='fulfilled',
            tracking_number='TRACK123'
        )
        
        # Run task
        result = send_shipment_notification(str(order.id))
        
        assert result['status'] == 'sent'
        
        # Verify message contains tracking number
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_transactional'
        )
        assert messages.count() == 1
        assert 'TRACK123' in messages.first().text
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_booking_confirmation(self, mock_twilio, tenant, customer, service, service_variant):
        """Test booking confirmation task."""
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Create confirmed appointment
        start_dt = timezone.now() + timedelta(days=1)
        end_dt = start_dt + timedelta(minutes=30)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            variant=service_variant,
            start_dt=start_dt,
            end_dt=end_dt,
            status='confirmed'
        )
        
        # Run task
        result = send_booking_confirmation(str(appointment.id))
        
        assert result['status'] == 'sent'
        
        # Verify message was created
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_transactional'
        )
        assert messages.count() == 1
        assert 'Booking confirmed' in messages.first().text
    
    def test_payment_confirmation_skips_non_paid_orders(self, tenant, customer):
        """Test payment confirmation skips orders that aren't paid."""
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=100.00,
            total=100.00,
            status='draft'
        )
        
        result = send_payment_confirmation(str(order.id))
        
        assert result['status'] == 'skipped'
        assert result['reason'] == 'status is draft'
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_payment_failed_notification(self, mock_twilio, tenant, customer):
        """Test payment failed notification task."""
        from apps.tenants.models import TenantWallet, Transaction
        
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Create wallet and failed transaction
        wallet = TenantWallet.objects.create(
            tenant=tenant,
            balance=0,
            currency='USD'
        )
        
        transaction = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='customer_payment',
            amount=100.00,
            status='failed',
            metadata={'customer_id': str(customer.id)}
        )
        
        # Run task with retry URL
        retry_url = "https://example.com/retry/payment"
        result = send_payment_failed_notification(str(transaction.id), retry_url)
        
        assert result['status'] == 'sent'
        assert 'message_id' in result
        
        # Verify message was created
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_transactional'
        )
        assert messages.count() == 1
        assert 'Payment failed' in messages.first().text
        assert retry_url in messages.first().text
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_payment_failed_notification_without_retry_url(self, mock_twilio, tenant, customer):
        """Test payment failed notification without retry URL."""
        from apps.tenants.models import TenantWallet, Transaction
        
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Create wallet and failed transaction
        wallet = TenantWallet.objects.create(
            tenant=tenant,
            balance=0,
            currency='USD'
        )
        
        transaction = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='customer_payment',
            amount=100.00,
            status='failed',
            metadata={'customer_id': str(customer.id)}
        )
        
        # Run task without retry URL
        result = send_payment_failed_notification(str(transaction.id))
        
        assert result['status'] == 'sent'
        
        # Verify message was created
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_transactional'
        )
        assert messages.count() == 1
        assert 'Payment failed' in messages.first().text
        assert 'contact us' in messages.first().text


@pytest.mark.django_db
class TestAppointmentReminderTasks:
    """Test appointment reminder Celery tasks."""
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_24h_reminders(self, mock_twilio, tenant, customer, service, service_variant):
        """Test 24-hour reminder batch task."""
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Set up customer consent
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer,
            reminder_messages=True
        )
        
        # Create appointment in 24 hours
        start_dt = timezone.now() + timedelta(hours=24)
        end_dt = start_dt + timedelta(minutes=30)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            variant=service_variant,
            start_dt=start_dt,
            end_dt=end_dt,
            status='confirmed'
        )
        
        # Run task
        result = send_24h_appointment_reminders()
        
        assert result['status'] == 'completed'
        assert result['sent'] >= 1
        
        # Verify reminder message was sent
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_reminder'
        )
        assert messages.count() >= 1
        assert 'tomorrow' in messages.first().text.lower()
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_2h_reminders(self, mock_twilio, tenant, customer, service, service_variant):
        """Test 2-hour reminder batch task."""
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Set up customer consent
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer,
            reminder_messages=True
        )
        
        # Create appointment in 2 hours
        start_dt = timezone.now() + timedelta(hours=2)
        end_dt = start_dt + timedelta(minutes=30)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            variant=service_variant,
            start_dt=start_dt,
            end_dt=end_dt,
            status='confirmed'
        )
        
        # Run task
        result = send_2h_appointment_reminders()
        
        assert result['status'] == 'completed'
        assert result['sent'] >= 1
        
        # Verify reminder message was sent
        messages = Message.objects.filter(
            conversation__customer=customer,
            message_type='automated_reminder'
        )
        assert messages.count() >= 1
        assert '2 hours' in messages.first().text
    
    def test_reminders_skip_without_consent(self, tenant, customer, service, service_variant):
        """Test reminders are skipped if customer hasn't consented."""
        # Set up customer without reminder consent
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer,
            reminder_messages=False
        )
        
        # Create appointment in 24 hours
        start_dt = timezone.now() + timedelta(hours=24)
        end_dt = start_dt + timedelta(minutes=30)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            variant=service_variant,
            start_dt=start_dt,
            end_dt=end_dt,
            status='confirmed'
        )
        
        # Run task
        result = send_24h_appointment_reminders()
        
        # Should be skipped due to consent
        assert result['skipped'] >= 1


@pytest.mark.django_db
class TestReengagementTask:
    """Test re-engagement message Celery task."""
    
    @patch('apps.messaging.services.messaging_service.create_twilio_service_for_tenant')
    def test_send_reengagement_messages(self, mock_twilio, tenant, customer):
        """Test re-engagement message batch task."""
        # Mock Twilio service
        mock_service = MagicMock()
        mock_service.send_whatsapp.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_twilio.return_value = mock_service
        
        # Set up customer consent for promotional messages
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer,
            promotional_messages=True
        )
        
        # Create inactive conversation (8 days old)
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status='open',
            last_intent='BROWSE_PRODUCTS'
        )
        # Manually set updated_at to 8 days ago
        eight_days_ago = timezone.now() - timedelta(days=8)
        Conversation.objects.filter(id=conversation.id).update(updated_at=eight_days_ago)
        
        # Run task
        result = send_reengagement_messages()
        
        assert result['status'] == 'completed'
        assert result['sent'] >= 1
        
        # Verify re-engagement message was sent
        messages = Message.objects.filter(
            conversation=conversation,
            message_type='automated_reengagement'
        )
        assert messages.count() >= 1
    
    def test_reengagement_marks_dormant(self, tenant, customer):
        """Test conversations inactive for 14+ days are marked dormant."""
        # Create conversation inactive for 15 days
        conversation = Conversation.objects.create(
            tenant=tenant,
            customer=customer,
            status='open'
        )
        fifteen_days_ago = timezone.now() - timedelta(days=15)
        Conversation.objects.filter(id=conversation.id).update(updated_at=fifteen_days_ago)
        
        # Run task
        result = send_reengagement_messages()
        
        # Verify conversation was marked dormant
        conversation.refresh_from_db()
        assert conversation.status == 'dormant'
        assert result['marked_dormant'] >= 1


@pytest.mark.django_db
class TestOrderSignals:
    """Test order status change signals trigger messages."""
    
    @patch('apps.messaging.tasks.send_payment_confirmation.delay')
    def test_order_paid_triggers_confirmation(self, mock_task, tenant, customer):
        """Test order status change to paid triggers confirmation task."""
        # Create order
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=100.00,
            total=100.00,
            status='draft'
        )
        
        # Change status to paid
        order.status = 'paid'
        order.save()
        
        # Verify task was triggered
        mock_task.assert_called_once_with(str(order.id))
    
    @patch('apps.messaging.tasks.send_shipment_notification.delay')
    def test_order_fulfilled_triggers_notification(self, mock_task, tenant, customer):
        """Test order status change to fulfilled triggers shipment notification."""
        # Create paid order
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=100.00,
            total=100.00,
            status='paid'
        )
        
        # Change status to fulfilled
        order.status = 'fulfilled'
        order.tracking_number = 'TRACK123'
        order.save()
        
        # Verify task was triggered
        mock_task.assert_called_once_with(str(order.id))


@pytest.mark.django_db
class TestAppointmentSignals:
    """Test appointment signals trigger messages and reminders."""
    
    @patch('apps.messaging.tasks.send_booking_confirmation.delay')
    @patch('apps.messaging.services.messaging_service.MessagingService.schedule_message')
    def test_appointment_confirmed_triggers_messages(
        self, mock_schedule, mock_task, tenant, customer, service, service_variant
    ):
        """Test confirmed appointment triggers confirmation and schedules reminders."""
        # Create confirmed appointment
        start_dt = timezone.now() + timedelta(days=2)
        end_dt = start_dt + timedelta(minutes=30)
        
        appointment = Appointment.objects.create(
            tenant=tenant,
            customer=customer,
            service=service,
            variant=service_variant,
            start_dt=start_dt,
            end_dt=end_dt,
            status='confirmed'
        )
        
        # Verify confirmation task was triggered
        mock_task.assert_called_once_with(str(appointment.id))
        
        # Verify reminders were scheduled (24h and 2h)
        assert mock_schedule.call_count == 2


# Fixtures
@pytest.fixture
def tenant():
    """Create a test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        whatsapp_number="+254722000000",
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
def service(tenant):
    """Create a test service."""
    return Service.objects.create(
        tenant=tenant,
        title="Test Service",
        base_price=50.00,
        is_active=True
    )


@pytest.fixture
def service_variant(service):
    """Create a test service variant."""
    return ServiceVariant.objects.create(
        service=service,
        title="30-minute session",
        duration_minutes=30,
        price=50.00
    )


@pytest.fixture
def conversation(tenant, customer):
    """Create a test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        status='open'
    )



@pytest.mark.django_db
class TestWalletServiceIntegration:
    """Test wallet service integration with payment failure notifications."""
    
    @patch('apps.messaging.tasks.send_payment_failed_notification.delay')
    def test_fail_payment_transaction_triggers_notification(self, mock_task, tenant, customer):
        """Test failing a payment transaction triggers customer notification."""
        from apps.tenants.models import TenantWallet, Transaction
        from apps.tenants.services.wallet_service import WalletService
        
        # Create wallet and transaction
        wallet = TenantWallet.objects.create(
            tenant=tenant,
            balance=0,
            currency='USD'
        )
        
        transaction = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='customer_payment',
            amount=100.00,
            status='pending',
            metadata={'customer_id': str(customer.id)}
        )
        
        # Fail the transaction with notification
        retry_url = "https://example.com/retry/payment"
        result = WalletService.fail_payment_transaction(
            str(transaction.id),
            reason='Card declined',
            retry_url=retry_url,
            notify_customer=True
        )
        
        # Verify transaction was failed
        assert result['transaction'].status == 'failed'
        assert result['transaction'].metadata['failure_reason'] == 'Card declined'
        assert result['transaction'].metadata['retry_url'] == retry_url
        
        # Verify notification task was triggered
        assert result['notification_sent'] is True
        mock_task.assert_called_once_with(str(transaction.id), retry_url=retry_url)
    
    def test_fail_payment_transaction_without_notification(self, tenant, customer):
        """Test failing a payment transaction without customer notification."""
        from apps.tenants.models import TenantWallet, Transaction
        from apps.tenants.services.wallet_service import WalletService
        
        # Create wallet and transaction
        wallet = TenantWallet.objects.create(
            tenant=tenant,
            balance=0,
            currency='USD'
        )
        
        transaction = Transaction.objects.create(
            tenant=tenant,
            wallet=wallet,
            transaction_type='customer_payment',
            amount=100.00,
            status='pending',
            metadata={'customer_id': str(customer.id)}
        )
        
        # Fail the transaction without notification
        result = WalletService.fail_payment_transaction(
            str(transaction.id),
            reason='Internal error',
            notify_customer=False
        )
        
        # Verify transaction was failed
        assert result['transaction'].status == 'failed'
        assert result['notification_sent'] is False
        assert 'notification_task_id' not in result
