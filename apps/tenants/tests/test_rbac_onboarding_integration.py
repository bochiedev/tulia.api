"""
RBAC Integration Tests for Onboarding Feature.

Tests that all onboarding endpoints properly enforce RBAC scopes:
- integrations:manage for credential management
- finance:manage for payment/payout methods
- users:manage for tenant deletion
- Proper 403 responses without required scopes
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole


@pytest.mark.django_db
class TestRBACIntegrationOnboarding(TestCase):
    """Test RBAC enforcement across onboarding endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create subscription tier
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
        
        # Create all permissions
        self.perm_integrations_manage = Permission.objects.create(
            code='integrations:manage',
            label='Manage Integrations',
            category='integrations'
        )
        self.perm_finance_manage = Permission.objects.create(
            code='finance:manage',
            label='Manage Finance',
            category='finance'
        )
        self.perm_users_manage = Permission.objects.create(
            code='users:manage',
            label='Manage Users',
            category='users'
        )
        
        # Create tenant user (no roles initially)
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
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
    
    def _assign_permission(self, permission):
        """Helper to assign a permission to the user."""
        role = Role.objects.create(
            tenant=self.tenant,
            name=f'Role for {permission.code}'
        )
        RolePermission.objects.create(
            role=role,
            permission=permission
        )
        TenantUserRole.objects.create(
            tenant_user=self.tenant_user,
            role=role
        )
    
    def _clear_permissions(self):
        """Helper to clear all user permissions."""
        TenantUserRole.objects.filter(tenant_user=self.tenant_user).delete()
    
    # Integration Credentials Tests
    
    def test_twilio_credentials_requires_integrations_manage(self):
        """Test that Twilio credential endpoints require integrations:manage."""
        # Without scope - should fail
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'AC1234567890abcdef1234567890abcd',
                'token': 'test_token_1234567890123456789012'
            },
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('integrations:manage', response.data['detail'])
        
        # With scope - should succeed
        self._assign_permission(self.perm_integrations_manage)
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'AC1234567890abcdef1234567890abcd',
                'token': 'test_token_1234567890123456789012'
            },
            format='json',
            **self.headers
        )
        # May fail validation but should not be 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_woocommerce_credentials_requires_integrations_manage(self):
        """Test that WooCommerce credential endpoints require integrations:manage."""
        # Without scope
        response = self.client.put(
            '/v1/settings/integrations/woocommerce',
            {
                'store_url': 'https://example.com',
                'consumer_key': 'ck_test',
                'consumer_secret': 'cs_test'
            },
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_integrations_manage)
        response = self.client.put(
            '/v1/settings/integrations/woocommerce',
            {
                'store_url': 'https://example.com',
                'consumer_key': 'ck_test',
                'consumer_secret': 'cs_test'
            },
            format='json',
            **self.headers
        )
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_shopify_credentials_requires_integrations_manage(self):
        """Test that Shopify credential endpoints require integrations:manage."""
        # Without scope
        response = self.client.put(
            '/v1/settings/integrations/shopify',
            {
                'shop_domain': 'test.myshopify.com',
                'access_token': 'shpat_test'
            },
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_integrations_manage)
        response = self.client.put(
            '/v1/settings/integrations/shopify',
            {
                'shop_domain': 'test.myshopify.com',
                'access_token': 'shpat_test'
            },
            format='json',
            **self.headers
        )
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_credentials_requires_integrations_manage(self):
        """Test that deleting credentials requires integrations:manage."""
        # Set up credentials first
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.twilio_sid = 'AC1234567890abcdef1234567890abcd'
        settings.twilio_token = 'test_token'
        settings.save()
        
        # Without scope
        self._clear_permissions()
        response = self.client.delete(
            '/v1/settings/integrations/twilio',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_integrations_manage)
        response = self.client.delete(
            '/v1/settings/integrations/twilio',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Payment Methods Tests
    
    def test_payment_methods_require_finance_manage(self):
        """Test that payment method endpoints require finance:manage."""
        # List - without scope
        response = self.client.get(
            '/v1/settings/payment-methods',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('finance:manage', response.data['detail'])
        
        # List - with scope
        self._assign_permission(self.perm_finance_manage)
        response = self.client.get(
            '/v1/settings/payment-methods',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_add_payment_method_requires_finance_manage(self):
        """Test that adding payment method requires finance:manage."""
        # Without scope
        self._clear_permissions()
        response = self.client.post(
            '/v1/settings/payment-methods',
            {'payment_method_id': 'pm_test'},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_finance_manage)
        response = self.client.post(
            '/v1/settings/payment-methods',
            {'payment_method_id': 'pm_test'},
            format='json',
            **self.headers
        )
        # May fail for other reasons but not 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_remove_payment_method_requires_finance_manage(self):
        """Test that removing payment method requires finance:manage."""
        # Set up payment method
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
        
        # Without scope
        self._clear_permissions()
        response = self.client.delete(
            '/v1/settings/payment-methods/pm_test123',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_finance_manage)
        response = self.client.delete(
            '/v1/settings/payment-methods/pm_test123',
            **self.headers
        )
        # May fail for other reasons but not 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # Payout Methods Tests
    
    def test_payout_method_requires_finance_manage(self):
        """Test that payout method endpoints require finance:manage."""
        # Get - without scope
        response = self.client.get(
            '/v1/settings/payout-method',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Get - with scope
        self._assign_permission(self.perm_finance_manage)
        response = self.client.get(
            '/v1/settings/payout-method',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_update_payout_method_requires_finance_manage(self):
        """Test that updating payout method requires finance:manage."""
        # Without scope
        self._clear_permissions()
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
        
        # With scope
        self._assign_permission(self.perm_finance_manage)
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
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # Tenant Management Tests
    
    def test_tenant_deletion_requires_users_manage(self):
        """Test that tenant deletion requires users:manage scope."""
        # Without scope
        response = self.client.delete(
            f'/v1/tenants/{self.tenant.id}/delete',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_users_manage)
        response = self.client.delete(
            f'/v1/tenants/{self.tenant.id}/delete',
            **self.headers
        )
        # Should succeed or fail for other reasons, not 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_tenant_update_requires_users_manage(self):
        """Test that tenant update requires users:manage scope."""
        # Without scope
        response = self.client.put(
            f'/v1/tenants/{self.tenant.id}/update',
            {'name': 'Updated Name'},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_users_manage)
        response = self.client.put(
            f'/v1/tenants/{self.tenant.id}/update',
            {'name': 'Updated Name'},
            format='json',
            **self.headers
        )
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # API Keys Tests
    
    def test_api_keys_require_users_manage(self):
        """Test that API key endpoints require users:manage scope."""
        # List - without scope
        response = self.client.get(
            '/v1/settings/api-keys',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # List - with scope
        self._assign_permission(self.perm_users_manage)
        response = self.client.get(
            '/v1/settings/api-keys',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_generate_api_key_requires_users_manage(self):
        """Test that generating API key requires users:manage scope."""
        # Without scope
        self._clear_permissions()
        response = self.client.post(
            '/v1/settings/api-keys',
            {'name': 'Test Key'},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_users_manage)
        response = self.client.post(
            '/v1/settings/api-keys',
            {'name': 'Test Key'},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_revoke_api_key_requires_users_manage(self):
        """Test that revoking API key requires users:manage scope."""
        # Set up API key
        self.tenant.api_keys = [
            {
                'id': 'key-test',
                'key_hash': 'hash123',
                'key_preview': 'abcd1234',
                'name': 'Test Key',
                'created_at': '2024-01-01T00:00:00Z',
                'created_by_email': 'test@example.com'
            }
        ]
        self.tenant.save()
        
        # Without scope
        self._clear_permissions()
        response = self.client.delete(
            '/v1/settings/api-keys/key-test',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # With scope
        self._assign_permission(self.perm_users_manage)
        response = self.client.delete(
            '/v1/settings/api-keys/key-test',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Cross-Scope Tests
    
    def test_wrong_scope_returns_403(self):
        """Test that having wrong scope still returns 403."""
        # User has finance:manage but tries to access integrations
        self._assign_permission(self.perm_finance_manage)
        
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'AC1234567890abcdef1234567890abcd',
                'token': 'test_token'
            },
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('integrations:manage', response.data['detail'])
    
    def test_multiple_scopes_work_correctly(self):
        """Test that user with multiple scopes can access all endpoints."""
        # Assign all permissions
        self._assign_permission(self.perm_integrations_manage)
        self._assign_permission(self.perm_finance_manage)
        self._assign_permission(self.perm_users_manage)
        
        # Should be able to access all endpoints
        response1 = self.client.get('/v1/settings/integrations', **self.headers)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        response2 = self.client.get('/v1/settings/payment-methods', **self.headers)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        response3 = self.client.get('/v1/settings/api-keys', **self.headers)
        self.assertEqual(response3.status_code, status.HTTP_200_OK)
