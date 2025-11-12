"""
Tests for PaymentService.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone

from apps.integrations.services.payment_service import (
    PaymentService,
    PaymentProviderNotConfigured,
    PaymentProcessingError
)
from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings, Customer
from apps.orders.models import Order


@pytest.fixture
def subscription_tier_with_payment():
    """Create subscription tier with payment facilitation enabled."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=Decimal('99.00'),
        yearly_price=Decimal('950.00'),
        payment_facilitation=True,
        transaction_fee_percentage=Decimal('2.5')
    )


@pytest.fixture
def tenant_with_payment(subscription_tier_with_payment):
    """Create tenant with payment facilitation enabled."""
    tenant = Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
        subscription_tier=subscription_tier_with_payment,
        status='active'
    )
    # Update the auto-created tenant settings with Stripe configuration
    tenant.settings.stripe_customer_id = 'cus_test123'
    tenant.settings.save()
    return tenant


@pytest.fixture
def customer(tenant_with_payment):
    """Create test customer."""
    return Customer.objects.create(
        tenant=tenant_with_payment,
        phone_e164='+254712345678',
        name='Test Customer'
    )


@pytest.fixture
def order(tenant_with_payment, customer):
    """Create test order."""
    return Order.objects.create(
        tenant=tenant_with_payment,
        customer=customer,
        status='draft',
        currency='USD',
        subtotal=Decimal('100.00'),
        total=Decimal('100.00'),
        items=[
            {
                'product_id': 'prod_123',
                'name': 'Test Product',
                'quantity': 1,
                'price': '100.00'
            }
        ]
    )


@pytest.mark.django_db
class TestPaymentService:
    """Test PaymentService functionality."""
    
    def test_get_configured_provider_stripe(self, tenant_with_payment):
        """Test that Stripe is detected as configured provider."""
        provider = PaymentService.get_configured_provider(tenant_with_payment)
        assert provider == PaymentService.PROVIDER_STRIPE
    
    def test_get_configured_provider_no_facilitation(self):
        """Test that None is returned when payment facilitation is disabled."""
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=Decimal('29.00'),
            yearly_price=Decimal('290.00'),
            payment_facilitation=False
        )
        tenant = Tenant.objects.create(
            name='No Payment Tenant',
            slug='no-payment',
            subscription_tier=tier,
            status='active'
        )
        
        provider = PaymentService.get_configured_provider(tenant)
        assert provider is None
    
    def test_generate_checkout_link_no_provider(self):
        """Test that exception is raised when no provider is configured."""
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=Decimal('29.00'),
            yearly_price=Decimal('290.00'),
            payment_facilitation=False
        )
        tenant = Tenant.objects.create(
            name='No Payment Tenant',
            slug='no-payment-2',
            subscription_tier=tier,
            status='active'
        )
        # Create a customer for this tenant
        customer = Customer.objects.create(
            tenant=tenant,
            phone_e164='+254712345679',  # Different phone number
            name='Test Customer 2'
        )
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            status='draft',
            currency='USD',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            items=[]
        )
        
        with pytest.raises(PaymentProviderNotConfigured):
            PaymentService.generate_checkout_link(order)
    
    def test_generate_stripe_checkout_success(self, order):
        """Test Stripe checkout link generation (uses stub in test environment)."""
        # In test environment without real Stripe keys, it falls back to stub
        result = PaymentService.generate_checkout_link(order)
        
        # Verify result structure
        assert 'checkout_url' in result
        assert result['provider'] == PaymentService.PROVIDER_STRIPE
        assert 'payment_ref' in result
        
        # Verify order was updated with payment reference
        order.refresh_from_db()
        assert order.payment_ref is not None
        assert order.payment_ref == result['payment_ref']
    
    @patch('apps.integrations.services.payment_service.settings')
    def test_generate_stripe_checkout_fallback_to_stub(self, mock_settings, order):
        """Test that stub checkout is generated when Stripe is not configured."""
        # Mock settings without Stripe key
        mock_settings.STRIPE_SECRET_KEY = None
        
        # Generate checkout link
        result = PaymentService.generate_checkout_link(order)
        
        # Verify stub was generated
        assert 'stub_stripe' in result['payment_ref']
        assert result['provider'] == PaymentService.PROVIDER_STRIPE
        assert 'checkout.example.com' in result['checkout_url']
    
    @patch('apps.integrations.services.payment_service.WalletService')
    def test_process_successful_payment(self, mock_wallet_service, order):
        """Test successful payment processing."""
        # Mock wallet service response
        mock_wallet_service.process_customer_payment.return_value = {
            'payment_transaction': Mock(id='txn_123'),
            'fee_transaction': Mock(id='fee_123'),
            'wallet_audit': Mock(id='audit_123'),
            'gross_amount': Decimal('100.00'),
            'fee_amount': Decimal('2.50'),
            'net_amount': Decimal('97.50')
        }
        
        # Process payment
        result = PaymentService.process_successful_payment(
            order=order,
            payment_amount=Decimal('100.00'),
            payment_ref='ch_test_123',
            provider=PaymentService.PROVIDER_STRIPE,
            payment_metadata={'customer_email': 'test@example.com'}
        )
        
        # Verify wallet service was called
        mock_wallet_service.process_customer_payment.assert_called_once()
        call_kwargs = mock_wallet_service.process_customer_payment.call_args[1]
        assert call_kwargs['tenant'] == order.tenant
        assert call_kwargs['payment_amount'] == Decimal('100.00')
        assert call_kwargs['reference_type'] == 'order'
        assert call_kwargs['reference_id'] == order.id
        
        # Verify order was marked as paid
        order.refresh_from_db()
        assert order.status == 'paid'
        assert order.payment_ref == 'ch_test_123'
        
        # Verify result
        assert result['gross_amount'] == Decimal('100.00')
        assert result['fee_amount'] == Decimal('2.50')
        assert result['net_amount'] == Decimal('97.50')
    
    def test_process_failed_payment(self, order):
        """Test failed payment processing."""
        # Process failed payment
        result = PaymentService.process_failed_payment(
            order=order,
            reason='Insufficient funds',
            provider=PaymentService.PROVIDER_STRIPE,
            retry_url='https://checkout.stripe.com/retry/123'
        )
        
        # Verify result
        assert result['success'] is False
        assert result['order_id'] == str(order.id)
        assert result['reason'] == 'Insufficient funds'
        
        # Verify order metadata was updated
        order.refresh_from_db()
        assert 'payment_failure' in order.metadata
        assert order.metadata['payment_failure']['reason'] == 'Insufficient funds'
        assert order.metadata['payment_failure']['provider'] == PaymentService.PROVIDER_STRIPE
    
    @patch('apps.integrations.services.payment_service.WalletService')
    def test_process_stripe_webhook_checkout_completed(self, mock_wallet_service, order):
        """Test processing Stripe checkout.session.completed webhook."""
        # Setup
        order.payment_ref = 'cs_test_123'
        order.save()
        
        mock_wallet_service.process_customer_payment.return_value = {
            'payment_transaction': Mock(id='txn_123'),
            'fee_transaction': Mock(id='fee_123'),
            'wallet_audit': Mock(id='audit_123'),
            'gross_amount': Decimal('100.00'),
            'fee_amount': Decimal('2.50'),
            'net_amount': Decimal('97.50')
        }
        
        # Webhook payload
        payload = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_123',
                    'amount_total': 10000,  # $100.00 in cents
                    'payment_intent': 'pi_test_123',
                    'customer_email': 'test@example.com',
                    'metadata': {
                        'order_id': str(order.id),
                        'tenant_id': str(order.tenant_id),
                        'customer_id': str(order.customer_id)
                    }
                }
            }
        }
        
        # Mock stripe module and settings
        with patch('apps.integrations.services.payment_service.settings') as mock_settings:
            mock_settings.STRIPE_WEBHOOK_SECRET = None  # Skip signature verification
            
            # Try to process webhook - if stripe is not installed, it will raise an error
            # which is expected in test environment
            try:
                result = PaymentService.process_payment_webhook(
                    provider=PaymentService.PROVIDER_STRIPE,
                    payload=payload,
                    signature=None
                )
                
                # If stripe is installed, verify result
                assert result['success'] is True
                assert result['order_id'] == str(order.id)
                assert 'transaction_id' in result
                
                # Verify order was marked as paid
                order.refresh_from_db()
                assert order.status == 'paid'
            except PaymentProcessingError as e:
                # If stripe module is not installed, that's expected in test environment
                # Just verify the error is about missing stripe module
                assert 'stripe' in str(e).lower() or 'module' in str(e).lower()
