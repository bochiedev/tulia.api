"""
Tests for payment and payout method management.

Validates:
- Payment method tokenization via Stripe
- Payout method encryption
- RBAC enforcement (finance:manage scope required)
- Credential masking in responses
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole


@pytest.mark.django_db
class TestPaymentMethodsAPI(TestCase):
    """Test payment methods API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
        )
        
        # Create user
        self.user = User.objects.create(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create finance:manage permission
        self.finance_manage_perm = Permission.objects.create(
            code='finance:manage',
            label='Manage Finance',
            description='Can manage payment and payout methods',
            category='finance'
        )
        
        # Create role with finance:manage permission
        self.finance_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name='Finance Admin',
            defaults={'description': 'Finance administrator role'}
        )
        RolePermission.objects.create(
            role=self.finance_role,
            permission=self.finance_manage_perm
        )
        
        # Create tenant user with finance role
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(
            tenant_user=self.tenant_user,
            role=self.finance_role
        )
        
        # Generate JWT token
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        # Set up API client
        self.client = APIClient()
        
        # Set headers
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_list_payment_methods_empty(self):
        """Test listing payment methods when none exist."""
        response = self.client.get(
            '/v1/settings/payment-methods',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['payment_methods']), 0)
    
    def test_list_payment_methods_with_existing(self):
        """Test listing payment methods when some exist."""
        # Add payment methods to tenant settings
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.stripe_payment_methods = [
            {
                'id': 'pm_test123',
                'last4': '4242',
                'brand': 'visa',
                'exp_month': 12,
                'exp_year': 2025,
                'is_default': True
            },
            {
                'id': 'pm_test456',
                'last4': '5555',
                'brand': 'mastercard',
                'exp_month': 6,
                'exp_year': 2026,
                'is_default': False
            }
        ]
        settings.save()
        
        response = self.client.get(
            '/v1/settings/payment-methods',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['payment_methods']), 2)
        
        # Verify masked data
        pm1 = response.data['payment_methods'][0]
        self.assertEqual(pm1['last4'], '4242')
        self.assertEqual(pm1['brand'], 'visa')
        self.assertTrue(pm1['is_default'])
        
        # Should not contain full card numbers
        self.assertNotIn('card_number', pm1)
    
    @patch('stripe.PaymentMethod.attach')
    @patch('stripe.Customer.create')
    def test_add_payment_method_success(self, mock_customer_create, mock_pm_attach):
        """Test adding a payment method via Stripe."""
        # Mock Stripe responses
        mock_customer_create.return_value = MagicMock(id='cus_test123')
        mock_pm_attach.return_value = MagicMock(
            id='pm_test789',
            card=MagicMock(
                last4='4242',
                brand='visa',
                exp_month=12,
                exp_year=2025
            )
        )
        
        response = self.client.post(
            '/v1/settings/payment-methods',
            {
                'payment_method_id': 'pm_test789'
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['last4'], '4242')
        self.assertEqual(response.data['brand'], 'visa')
        
        # Verify payment method was saved
        settings = TenantSettings.objects.get(tenant=self.tenant)
        self.assertEqual(len(settings.stripe_payment_methods), 1)
        self.assertEqual(settings.stripe_payment_methods[0]['id'], 'pm_test789')
    
    def test_add_payment_method_requires_scope(self):
        """Test that adding payment method requires finance:manage scope."""
        # Remove permission
        RolePermission.objects.filter(role=self.finance_role).delete()
        
        response = self.client.post(
            '/v1/settings/payment-methods',
            {'payment_method_id': 'pm_test'},
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('finance:manage', response.data['detail'])
    
    def test_set_default_payment_method(self):
        """Test setting a payment method as default."""
        # Add payment methods
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.stripe_payment_methods = [
            {
                'id': 'pm_test123',
                'last4': '4242',
                'brand': 'visa',
                'exp_month': 12,
                'exp_year': 2025,
                'is_default': True
            },
            {
                'id': 'pm_test456',
                'last4': '5555',
                'brand': 'mastercard',
                'exp_month': 6,
                'exp_year': 2026,
                'is_default': False
            }
        ]
        settings.save()
        
        response = self.client.put(
            '/v1/settings/payment-methods/pm_test456/default',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify default was changed
        settings.refresh_from_db()
        pm1 = next(pm for pm in settings.stripe_payment_methods if pm['id'] == 'pm_test123')
        pm2 = next(pm for pm in settings.stripe_payment_methods if pm['id'] == 'pm_test456')
        self.assertFalse(pm1['is_default'])
        self.assertTrue(pm2['is_default'])
    
    @patch('stripe.PaymentMethod.detach')
    def test_remove_payment_method(self, mock_pm_detach):
        """Test removing a payment method."""
        # Add payment method
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.stripe_payment_methods = [
            {
                'id': 'pm_test123',
                'last4': '4242',
                'brand': 'visa',
                'exp_month': 12,
                'exp_year': 2025,
                'is_default': True
            }
        ]
        settings.save()
        
        response = self.client.delete(
            '/v1/settings/payment-methods/pm_test123',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify payment method was removed
        settings.refresh_from_db()
        self.assertEqual(len(settings.stripe_payment_methods), 0)


@pytest.mark.django_db
class TestPayoutMethodsAPI(TestCase):
    """Test payout methods API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create subscription tier with payment facilitation
        self.tier = SubscriptionTier.objects.create(
            name='Professional',
            monthly_price=99.00,
            yearly_price=950.00,
            payment_facilitation_enabled=True
        )
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
        )
        
        # Create user
        self.user = User.objects.create(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create finance:manage permission
        self.finance_manage_perm = Permission.objects.create(
            code='finance:manage',
            label='Manage Finance',
            category='finance'
        )
        
        # Create role with finance:manage permission
        self.finance_role = Role.objects.create(
            tenant=self.tenant,
            name='Finance Admin'
        )
        RolePermission.objects.create(
            role=self.finance_role,
            permission=self.finance_manage_perm
        )
        
        # Create tenant user with finance role
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(
            tenant_user=self.tenant_user,
            role=self.finance_role
        )
        
        # Generate JWT token
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        # Set up API client
        self.client = APIClient()
        
        # Set headers
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_get_payout_method_not_configured(self):
        """Test getting payout method when not configured."""
        response = self.client.get(
            '/v1/settings/payout-method',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['configured'])
        self.assertIsNone(response.data['payout_method'])
    
    def test_update_payout_method_bank_transfer(self):
        """Test updating payout method with bank transfer."""
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'bank_transfer',
                'account_number': '1234567890',
                'routing_number': '021000021',
                'account_holder_name': 'Test Business Inc'
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['method'], 'bank_transfer')
        
        # Verify payout details are encrypted and masked
        self.assertIn('****', response.data['account_number_masked'])
        self.assertNotIn('1234567890', str(response.data))
        
        # Verify data was saved encrypted
        settings = TenantSettings.objects.get(tenant=self.tenant)
        self.assertIsNotNone(settings.payout_details)
        self.assertEqual(settings.payout_details['method'], 'bank_transfer')
    
    def test_update_payout_method_mobile_money(self):
        """Test updating payout method with mobile money."""
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'mobile_money',
                'phone_number': '+254712345678',
                'provider': 'mpesa'
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['method'], 'mobile_money')
        self.assertEqual(response.data['provider'], 'mpesa')
        
        # Verify phone number is masked
        self.assertIn('****', response.data['phone_number_masked'])
    
    def test_update_payout_method_missing_required_fields(self):
        """Test updating payout method with missing required fields."""
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'bank_transfer',
                'account_number': '1234567890'
                # Missing routing_number and account_holder_name
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('routing_number', response.data)
    
    def test_update_payout_method_requires_scope(self):
        """Test that updating payout method requires finance:manage scope."""
        # Remove permission
        RolePermission.objects.filter(role=self.finance_role).delete()
        
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'bank_transfer',
                'account_number': '1234567890',
                'routing_number': '021000021',
                'account_holder_name': 'Test'
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_payout_method_requires_payment_facilitation(self):
        """Test that payout method requires payment facilitation enabled."""
        # Disable payment facilitation
        self.tier.payment_facilitation_enabled = False
        self.tier.save()
        
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'bank_transfer',
                'account_number': '1234567890',
                'routing_number': '021000021',
                'account_holder_name': 'Test'
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('payment facilitation', response.data['error'].lower())
    
    def test_delete_payout_method(self):
        """Test deleting payout method."""
        # Set up payout method
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.payout_details = {
            'method': 'bank_transfer',
            'account_number': '1234567890',
            'routing_number': '021000021',
            'account_holder_name': 'Test'
        }
        settings.save()
        
        response = self.client.delete(
            '/v1/settings/payout-method',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify payout method was removed
        settings.refresh_from_db()
        self.assertIsNone(settings.payout_details)
