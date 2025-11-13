"""
Tests for customer payment preference service.
"""
import pytest
from decimal import Decimal
from django.utils import timezone

from apps.tenants.models import Tenant, Customer, TenantSettings
from apps.tenants.services.customer_payment_service import (
    CustomerPaymentService,
    PaymentPreferenceError
)
from apps.rbac.models import User


@pytest.mark.django_db
class TestCustomerPaymentService:
    """Test customer payment preference management."""
    
    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        return Tenant.objects.create(
            name="Test Business",
            slug="test-business",
            whatsapp_number="+254712345678",
            status='active'
        )
    
    @pytest.fixture
    def tenant_with_providers(self, tenant):
        """Create tenant with configured payment providers."""
        settings = TenantSettings.objects.create(
            tenant=tenant,
            metadata={
                'mpesa_shortcode': '174379',
                'paystack_public_key': 'pk_test_xxx',
                'pesapal_consumer_key': 'consumer_key_xxx'
            }
        )
        return tenant
    
    @pytest.fixture
    def customer(self, tenant):
        """Create test customer."""
        return Customer.objects.create(
            tenant=tenant,
            phone_e164='+254712345678',
            name='Test Customer'
        )
    
    def test_get_payment_preferences_empty(self, customer):
        """Test getting preferences for customer with no preferences."""
        prefs = CustomerPaymentService.get_payment_preferences(customer)
        
        assert prefs['preferred_provider'] is None
        assert prefs['saved_methods'] == []
        assert isinstance(prefs['available_providers'], list)
    
    def test_get_available_providers(self, tenant_with_providers):
        """Test getting available providers for tenant."""
        customer = Customer.objects.create(
            tenant=tenant_with_providers,
            phone_e164='+254712345679',
            name='Test Customer 2'
        )
        
        prefs = CustomerPaymentService.get_payment_preferences(customer)
        
        assert 'mpesa' in prefs['available_providers']
        assert 'paystack' in prefs['available_providers']
        assert 'pesapal' in prefs['available_providers']
    
    def test_set_preferred_provider(self, customer, tenant_with_providers):
        """Test setting preferred payment provider."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        updated = CustomerPaymentService.set_preferred_provider(customer, 'mpesa')
        
        assert updated.payment_preferences['preferred_provider'] == 'mpesa'
    
    def test_set_preferred_provider_invalid(self, customer):
        """Test setting invalid provider."""
        with pytest.raises(PaymentPreferenceError, match="Invalid provider"):
            CustomerPaymentService.set_preferred_provider(customer, 'invalid')
    
    def test_set_preferred_provider_not_configured(self, customer):
        """Test setting provider that's not configured for tenant."""
        with pytest.raises(PaymentPreferenceError, match="not configured"):
            CustomerPaymentService.set_preferred_provider(customer, 'mpesa')
    
    def test_save_payment_method_mpesa(self, customer, tenant_with_providers):
        """Test saving M-Pesa payment method."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        method_details = {'phone_number': '254712345678'}
        updated = CustomerPaymentService.save_payment_method(
            customer, 'mpesa', method_details
        )
        
        assert len(updated.payment_preferences['saved_methods']) == 1
        saved = updated.payment_preferences['saved_methods'][0]
        assert saved['provider'] == 'mpesa'
        assert saved['details'] == method_details
        assert saved['is_default'] is True
    
    def test_save_payment_method_paystack(self, customer, tenant_with_providers):
        """Test saving Paystack payment method."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        method_details = {
            'authorization_code': 'AUTH_xxx',
            'last4': '1234',
            'bank': 'Access Bank'
        }
        updated = CustomerPaymentService.save_payment_method(
            customer, 'paystack', method_details
        )
        
        assert len(updated.payment_preferences['saved_methods']) == 1
        saved = updated.payment_preferences['saved_methods'][0]
        assert saved['provider'] == 'paystack'
        assert saved['details']['authorization_code'] == 'AUTH_xxx'
    
    def test_save_multiple_payment_methods(self, customer, tenant_with_providers):
        """Test saving multiple payment methods."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        # Save M-Pesa
        CustomerPaymentService.save_payment_method(
            customer, 'mpesa', {'phone_number': '254712345678'}
        )
        
        # Save Paystack
        updated = CustomerPaymentService.save_payment_method(
            customer, 'paystack', {
                'authorization_code': 'AUTH_xxx',
                'last4': '1234',
                'bank': 'Access Bank'
            }
        )
        
        assert len(updated.payment_preferences['saved_methods']) == 2
        # First method should still be default
        assert updated.payment_preferences['saved_methods'][0]['is_default'] is True
        assert updated.payment_preferences['saved_methods'][1]['is_default'] is False
    
    def test_save_payment_method_invalid_details(self, customer, tenant_with_providers):
        """Test saving payment method with invalid details."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        with pytest.raises(PaymentPreferenceError, match="requires phone_number"):
            CustomerPaymentService.save_payment_method(
                customer, 'mpesa', {}
            )
    
    def test_remove_payment_method(self, customer, tenant_with_providers):
        """Test removing a saved payment method."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        # Save method
        CustomerPaymentService.save_payment_method(
            customer, 'mpesa', {'phone_number': '254712345678'}
        )
        
        # Get method ID
        method_id = 'mpesa_254712345678'
        
        # Remove method
        updated = CustomerPaymentService.remove_payment_method(customer, method_id)
        
        assert len(updated.payment_preferences['saved_methods']) == 0
    
    def test_remove_payment_method_not_found(self, customer):
        """Test removing non-existent payment method."""
        with pytest.raises(PaymentPreferenceError, match="not found"):
            CustomerPaymentService.remove_payment_method(customer, 'invalid_id')
    
    def test_set_default_method(self, customer, tenant_with_providers):
        """Test setting default payment method."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        # Save two methods
        CustomerPaymentService.save_payment_method(
            customer, 'mpesa', {'phone_number': '254712345678'}
        )
        CustomerPaymentService.save_payment_method(
            customer, 'paystack', {
                'authorization_code': 'AUTH_xxx',
                'last4': '1234',
                'bank': 'Access Bank'
            }
        )
        
        # Set second method as default
        method_id = 'paystack_AUTH_xxx'
        updated = CustomerPaymentService.set_default_method(customer, method_id)
        
        # Check defaults
        methods = updated.payment_preferences['saved_methods']
        assert methods[0]['is_default'] is False
        assert methods[1]['is_default'] is True
    
    def test_get_checkout_options(self, customer, tenant_with_providers):
        """Test getting checkout options with preferences."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        # Set preferences
        CustomerPaymentService.set_preferred_provider(customer, 'mpesa')
        CustomerPaymentService.save_payment_method(
            customer, 'mpesa', {'phone_number': '254712345678'}
        )
        
        options = CustomerPaymentService.get_checkout_options(customer, 100.0)
        
        assert options['preferred_provider'] == 'mpesa'
        assert options['preferred_method'] is not None
        assert options['preferred_method']['provider'] == 'mpesa'
        assert len(options['available_providers']) > 0
        assert options['can_change_provider'] is True
        assert options['amount'] == 100.0
    
    def test_update_existing_method(self, customer, tenant_with_providers):
        """Test updating an existing payment method."""
        customer.tenant = tenant_with_providers
        customer.save()
        
        # Save method
        CustomerPaymentService.save_payment_method(
            customer, 'mpesa', {'phone_number': '254712345678'}
        )
        
        # Update same method (should replace)
        updated = CustomerPaymentService.save_payment_method(
            customer, 'mpesa', {'phone_number': '254712345678'}
        )
        
        # Should still have only one method
        assert len(updated.payment_preferences['saved_methods']) == 1
