"""
Customer payment preference management service.

Handles:
- Saving customer payment preferences per tenant
- Managing saved payment methods
- Provider selection with fallback
- Payment method validation
"""
import logging
from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone

from apps.tenants.models import Customer, Tenant
from apps.core.exceptions import TuliaException

logger = logging.getLogger(__name__)


class PaymentPreferenceError(TuliaException):
    """Raised when payment preference operation fails."""
    pass


class CustomerPaymentService:
    """Service for managing customer payment preferences."""
    
    SUPPORTED_PROVIDERS = ['mpesa', 'paystack', 'pesapal', 'stripe']
    
    @staticmethod
    def get_payment_preferences(customer: Customer) -> Dict:
        """
        Get customer payment preferences.
        
        Args:
            customer: Customer instance
            
        Returns:
            dict: {
                'preferred_provider': str or None,
                'saved_methods': list,
                'available_providers': list
            }
        """
        preferences = customer.payment_preferences or {}
        
        # Get available providers for this tenant
        available_providers = CustomerPaymentService._get_available_providers(customer.tenant)
        
        return {
            'preferred_provider': preferences.get('preferred_provider'),
            'saved_methods': preferences.get('saved_methods', []),
            'available_providers': available_providers
        }
    
    @staticmethod
    def _get_available_providers(tenant: Tenant) -> List[str]:
        """
        Get list of configured payment providers for tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            list: Available provider names
        """
        from apps.integrations.services.payment_service import PaymentService
        
        available = []
        settings_obj = getattr(tenant, 'settings', None)
        
        if not settings_obj:
            return available
        
        # Check M-Pesa
        if settings_obj.metadata.get('mpesa_shortcode'):
            available.append(PaymentService.PROVIDER_MPESA)
        
        # Check Paystack
        if settings_obj.metadata.get('paystack_public_key'):
            available.append(PaymentService.PROVIDER_PAYSTACK)
        
        # Check Pesapal
        if settings_obj.metadata.get('pesapal_consumer_key'):
            available.append(PaymentService.PROVIDER_PESAPAL)
        
        # Check Stripe
        if settings_obj.stripe_customer_id:
            available.append(PaymentService.PROVIDER_STRIPE)
        
        return available
    
    @classmethod
    @transaction.atomic
    def set_preferred_provider(cls, customer: Customer, provider: str) -> Customer:
        """
        Set customer's preferred payment provider.
        
        Args:
            customer: Customer instance
            provider: Provider name (mpesa, paystack, pesapal, stripe)
            
        Returns:
            Customer: Updated customer instance
            
        Raises:
            PaymentPreferenceError: If provider is invalid or not available
        """
        # Validate provider
        if provider not in cls.SUPPORTED_PROVIDERS:
            raise PaymentPreferenceError(
                f"Invalid provider: {provider}. Must be one of {cls.SUPPORTED_PROVIDERS}"
            )
        
        # Check if provider is available for this tenant
        available_providers = cls._get_available_providers(customer.tenant)
        if provider not in available_providers:
            raise PaymentPreferenceError(
                f"Provider {provider} is not configured for this tenant"
            )
        
        # Update preferences
        if not customer.payment_preferences:
            customer.payment_preferences = {}
        
        customer.payment_preferences['preferred_provider'] = provider
        customer.save(update_fields=['payment_preferences', 'updated_at'])
        
        logger.info(
            f"Customer preferred provider updated",
            extra={
                'customer_id': str(customer.id),
                'tenant_id': str(customer.tenant_id),
                'provider': provider
            }
        )
        
        return customer
    
    @classmethod
    @transaction.atomic
    def save_payment_method(cls, customer: Customer, provider: str, 
                           method_details: Dict) -> Customer:
        """
        Save a payment method for future use.
        
        Args:
            customer: Customer instance
            provider: Provider name
            method_details: Provider-specific method details
                For M-Pesa: {'phone_number': '254712345678'}
                For Paystack: {'authorization_code': 'AUTH_xxx', 'last4': '1234', 'bank': 'Access Bank'}
                For Pesapal: {'payment_method': 'card', 'last4': '1234'}
                For Stripe: {'payment_method_id': 'pm_xxx', 'last4': '1234', 'brand': 'visa'}
            
        Returns:
            Customer: Updated customer instance
            
        Raises:
            PaymentPreferenceError: If validation fails
        """
        # Validate provider
        if provider not in cls.SUPPORTED_PROVIDERS:
            raise PaymentPreferenceError(f"Invalid provider: {provider}")
        
        # Validate method details
        cls._validate_method_details(provider, method_details)
        
        # Initialize preferences if needed
        if not customer.payment_preferences:
            customer.payment_preferences = {}
        
        if 'saved_methods' not in customer.payment_preferences:
            customer.payment_preferences['saved_methods'] = []
        
        # Check if method already exists
        saved_methods = customer.payment_preferences['saved_methods']
        method_id = cls._get_method_id(provider, method_details)
        
        # Remove existing method with same ID
        saved_methods = [
            m for m in saved_methods 
            if cls._get_method_id(m['provider'], m['details']) != method_id
        ]
        
        # Add new method
        saved_methods.append({
            'provider': provider,
            'details': method_details,
            'saved_at': timezone.now().isoformat(),
            'is_default': len(saved_methods) == 0  # First method is default
        })
        
        customer.payment_preferences['saved_methods'] = saved_methods
        customer.save(update_fields=['payment_preferences', 'updated_at'])
        
        logger.info(
            f"Payment method saved",
            extra={
                'customer_id': str(customer.id),
                'tenant_id': str(customer.tenant_id),
                'provider': provider
            }
        )
        
        return customer
    
    @staticmethod
    def _validate_method_details(provider: str, details: Dict):
        """Validate payment method details for provider."""
        if provider == 'mpesa':
            if 'phone_number' not in details:
                raise PaymentPreferenceError("M-Pesa method requires phone_number")
        elif provider == 'paystack':
            if 'authorization_code' not in details:
                raise PaymentPreferenceError("Paystack method requires authorization_code")
        elif provider == 'pesapal':
            if 'payment_method' not in details:
                raise PaymentPreferenceError("Pesapal method requires payment_method")
        elif provider == 'stripe':
            if 'payment_method_id' not in details:
                raise PaymentPreferenceError("Stripe method requires payment_method_id")
    
    @staticmethod
    def _get_method_id(provider: str, details: Dict) -> str:
        """Get unique identifier for payment method."""
        if provider == 'mpesa':
            return f"mpesa_{details.get('phone_number')}"
        elif provider == 'paystack':
            return f"paystack_{details.get('authorization_code')}"
        elif provider == 'pesapal':
            return f"pesapal_{details.get('payment_method')}_{details.get('last4', '')}"
        elif provider == 'stripe':
            return f"stripe_{details.get('payment_method_id')}"
        return f"{provider}_unknown"
    
    @classmethod
    @transaction.atomic
    def remove_payment_method(cls, customer: Customer, method_id: str) -> Customer:
        """
        Remove a saved payment method.
        
        Args:
            customer: Customer instance
            method_id: Method identifier (from _get_method_id)
            
        Returns:
            Customer: Updated customer instance
        """
        if not customer.payment_preferences:
            return customer
        
        saved_methods = customer.payment_preferences.get('saved_methods', [])
        
        # Filter out the method
        new_methods = [
            m for m in saved_methods
            if cls._get_method_id(m['provider'], m['details']) != method_id
        ]
        
        if len(new_methods) == len(saved_methods):
            raise PaymentPreferenceError(f"Payment method {method_id} not found")
        
        # If removed method was default, set first remaining as default
        if new_methods and not any(m.get('is_default') for m in new_methods):
            new_methods[0]['is_default'] = True
        
        customer.payment_preferences['saved_methods'] = new_methods
        customer.save(update_fields=['payment_preferences', 'updated_at'])
        
        logger.info(
            f"Payment method removed",
            extra={
                'customer_id': str(customer.id),
                'tenant_id': str(customer.tenant_id),
                'method_id': method_id
            }
        )
        
        return customer
    
    @classmethod
    @transaction.atomic
    def set_default_method(cls, customer: Customer, method_id: str) -> Customer:
        """
        Set a saved payment method as default.
        
        Args:
            customer: Customer instance
            method_id: Method identifier
            
        Returns:
            Customer: Updated customer instance
        """
        if not customer.payment_preferences:
            raise PaymentPreferenceError("No saved payment methods")
        
        saved_methods = customer.payment_preferences.get('saved_methods', [])
        
        found = False
        for method in saved_methods:
            current_id = cls._get_method_id(method['provider'], method['details'])
            method['is_default'] = (current_id == method_id)
            if current_id == method_id:
                found = True
        
        if not found:
            raise PaymentPreferenceError(f"Payment method {method_id} not found")
        
        customer.payment_preferences['saved_methods'] = saved_methods
        customer.save(update_fields=['payment_preferences', 'updated_at'])
        
        logger.info(
            f"Default payment method updated",
            extra={
                'customer_id': str(customer.id),
                'tenant_id': str(customer.tenant_id),
                'method_id': method_id
            }
        )
        
        return customer
    
    @staticmethod
    def get_checkout_options(customer: Customer, amount: float) -> Dict:
        """
        Get payment options for checkout with customer preferences.
        
        Args:
            customer: Customer instance
            amount: Payment amount
            
        Returns:
            dict: {
                'preferred_provider': str or None,
                'preferred_method': dict or None,
                'available_providers': list,
                'saved_methods': list,
                'can_change_provider': bool
            }
        """
        preferences = CustomerPaymentService.get_payment_preferences(customer)
        
        # Get default saved method
        default_method = None
        for method in preferences['saved_methods']:
            if method.get('is_default'):
                default_method = method
                break
        
        return {
            'preferred_provider': preferences['preferred_provider'],
            'preferred_method': default_method,
            'available_providers': preferences['available_providers'],
            'saved_methods': preferences['saved_methods'],
            'can_change_provider': True,  # Always allow changing
            'amount': amount
        }
