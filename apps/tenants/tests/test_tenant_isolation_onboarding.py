"""
Tenant Isolation Tests for Onboarding Feature.

Validates that:
- Users cannot access other tenant's settings
- API keys from one tenant cannot access another tenant's data
- No cross-tenant data leakage in any endpoint
- Middleware properly enforces tenant context
"""
import pytest
import hashlib
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole


@pytest.mark.django_db
class TestTenantIsolationOnboarding(TestCase):
    """Test tenant isolation across all onboarding endpoints."""
    
    def setUp(self):
        """Set up test data with two tenants."""
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Professional',
            monthly_price=99.00,
            yearly_price=950.00,
            payment_facilitation_enabled=True
        )
        
        # Create two tenants
        self.tenant1 = Tenant.objects.create(
            name='Tenant 1',
            slug='tenant-1',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551111',
        )
        
        self.tenant2 = Tenant.objects.create(
            name='Tenant 2',
            slug='tenant-2',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155552222',
        )
        
        # Create user who is member of tenant1 only
        self.user = User.objects.create(
            email='user@example.com',
            first_name='Test',
            last_name='User',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create permissions
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
        
        # Create role with all permissions for tenant1
        self.role1 = Role.objects.create(
            tenant=self.tenant1,
            name='Admin'
        )
        RolePermission.objects.create(role=self.role1, permission=self.perm_integrations_manage)
        RolePermission.objects.create(role=self.role1, permission=self.perm_finance_manage)
        RolePermission.objects.create(role=self.role1, permission=self.perm_users_manage)
        
        # Create tenant user for tenant1
        self.tenant_user1 = TenantUser.objects.create(
            tenant=self.tenant1,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(
            tenant_user=self.tenant_user1,
            role=self.role1
        )
        
        # Set up credentials for both tenants
        settings1 = TenantSettings.objects.get(tenant=self.tenant1)
        settings1.twilio_sid = 'AC1111111111111111111111111111111'
        settings1.twilio_token = 'token_tenant1'
        settings1.woo_store_url = 'https://tenant1.com'
        settings1.woo_consumer_key = 'ck_tenant1'
        settings1.stripe_payment_methods = [
            {
                'id': 'pm_tenant1',
                'last4': '1111',
                'brand': 'visa',
                'exp_month': 12,
                'exp_year': 2025,
                'is_default': True
            }
        ]
        settings1.payout_details = {
            'method': 'bank_transfer',
            'account_number': '1111111111'
        }
        settings1.save()
        
        settings2 = TenantSettings.objects.get(tenant=self.tenant2)
        settings2.twilio_sid = 'AC2222222222222222222222222222222'
        settings2.twilio_token = 'token_tenant2'
        settings2.woo_store_url = 'https://tenant2.com'
        settings2.woo_consumer_key = 'ck_tenant2'
        settings2.stripe_payment_methods = [
            {
                'id': 'pm_tenant2',
                'last4': '2222',
                'brand': 'mastercard',
                'exp_month': 6,
                'exp_year': 2026,
                'is_default': True
            }
        ]
        settings2.payout_details = {
            'method': 'mobile_money',
            'phone_number': '+254722222222'
        }
        settings2.save()
        
        # Generate JWT token
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        # Set up API client
        self.client = APIClient()
    
    # Integration Credentials Isolation Tests
    
    def test_cannot_access_other_tenant_twilio_credentials(self):
        """Test that user cannot access another tenant's Twilio credentials."""
        # Try to access tenant2's credentials with tenant1 membership
        response = self.client.get(
            '/v1/settings/integrations/twilio',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        # Should be forbidden (no membership in tenant2)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cannot_update_other_tenant_credentials(self):
        """Test that user cannot update another tenant's credentials."""
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'AC9999999999999999999999999999999',
                'token': 'malicious_token'
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2's credentials were not changed
        settings2 = TenantSettings.objects.get(tenant=self.tenant2)
        self.assertEqual(settings2.twilio_sid, 'AC2222222222222222222222222222222')
    
    def test_cannot_delete_other_tenant_credentials(self):
        """Test that user cannot delete another tenant's credentials."""
        response = self.client.delete(
            '/v1/settings/integrations/twilio',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2's credentials still exist
        settings2 = TenantSettings.objects.get(tenant=self.tenant2)
        self.assertNotEqual(settings2.twilio_sid, '')
    
    def test_list_integrations_only_shows_own_tenant(self):
        """Test that listing integrations only shows current tenant's data."""
        response = self.client.get(
            '/v1/settings/integrations',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant1.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Find Twilio integration
        twilio = next(i for i in response.data['integrations'] if i['name'] == 'twilio')
        
        # Should show tenant1's data, not tenant2's
        self.assertIn('****1111', twilio['credentials']['sid_masked'])
        self.assertNotIn('2222', str(response.data))
    
    # Payment Methods Isolation Tests
    
    def test_cannot_access_other_tenant_payment_methods(self):
        """Test that user cannot access another tenant's payment methods."""
        response = self.client.get(
            '/v1/settings/payment-methods',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cannot_remove_other_tenant_payment_method(self):
        """Test that user cannot remove another tenant's payment method."""
        response = self.client.delete(
            '/v1/settings/payment-methods/pm_tenant2',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2's payment method still exists
        settings2 = TenantSettings.objects.get(tenant=self.tenant2)
        self.assertEqual(len(settings2.stripe_payment_methods), 1)
    
    def test_list_payment_methods_only_shows_own_tenant(self):
        """Test that listing payment methods only shows current tenant's data."""
        response = self.client.get(
            '/v1/settings/payment-methods',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant1.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should show tenant1's payment method
        self.assertEqual(len(response.data['payment_methods']), 1)
        self.assertEqual(response.data['payment_methods'][0]['last4'], '1111')
        
        # Should not show tenant2's payment method
        self.assertNotIn('2222', str(response.data))
    
    # Payout Methods Isolation Tests
    
    def test_cannot_access_other_tenant_payout_method(self):
        """Test that user cannot access another tenant's payout method."""
        response = self.client.get(
            '/v1/settings/payout-method',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cannot_update_other_tenant_payout_method(self):
        """Test that user cannot update another tenant's payout method."""
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'bank_transfer',
                'account_number': '9999999999',
                'routing_number': '021000021',
                'account_holder_name': 'Malicious'
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2's payout method was not changed
        settings2 = TenantSettings.objects.get(tenant=self.tenant2)
        self.assertEqual(settings2.payout_details['method'], 'mobile_money')
    
    def test_get_payout_method_only_shows_own_tenant(self):
        """Test that getting payout method only shows current tenant's data."""
        response = self.client.get(
            '/v1/settings/payout-method',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant1.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should show tenant1's payout method
        self.assertEqual(response.data['method'], 'bank_transfer')
        self.assertIn('****1111', response.data['account_number_masked'])
        
        # Should not show tenant2's data
        self.assertNotIn('mobile_money', str(response.data))
        self.assertNotIn('254', str(response.data))
    
    # API Keys Isolation Tests
    
    def test_cannot_access_other_tenant_api_keys(self):
        """Test that user cannot access another tenant's API keys."""
        response = self.client.get(
            '/v1/settings/api-keys',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cannot_generate_api_key_for_other_tenant(self):
        """Test that user cannot generate API key for another tenant."""
        response = self.client.post(
            '/v1/settings/api-keys',
            {'name': 'Malicious Key'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify no key was added to tenant2
        self.tenant2.refresh_from_db()
        # Tenant2 may have initial key from signal, but should not have 'Malicious Key'
        if self.tenant2.api_keys:
            for key in self.tenant2.api_keys:
                self.assertNotEqual(key.get('name'), 'Malicious Key')
    
    def test_cannot_revoke_other_tenant_api_key(self):
        """Test that user cannot revoke another tenant's API key."""
        # Add API key to tenant2
        self.tenant2.api_keys = [
            {
                'id': 'key-tenant2',
                'key_hash': 'hash2',
                'key_preview': 'tenant2key',
                'name': 'Tenant 2 Key',
                'created_at': '2024-01-01T00:00:00Z',
                'created_by_email': 'admin@tenant2.com'
            }
        ]
        self.tenant2.save()
        
        response = self.client.delete(
            '/v1/settings/api-keys/key-tenant2',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2's key still exists
        self.tenant2.refresh_from_db()
        self.assertEqual(len(self.tenant2.api_keys), 1)
    
    # Onboarding Status Isolation Tests
    
    def test_cannot_access_other_tenant_onboarding_status(self):
        """Test that user cannot access another tenant's onboarding status."""
        response = self.client.get(
            '/v1/settings/onboarding',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cannot_mark_other_tenant_onboarding_complete(self):
        """Test that user cannot mark another tenant's onboarding steps complete."""
        response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'twilio_configured'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # Tenant Management Isolation Tests
    
    def test_cannot_update_other_tenant_info(self):
        """Test that user cannot update another tenant's information."""
        response = self.client.put(
            f'/v1/tenants/{self.tenant2.id}/update',
            {'name': 'Hacked Tenant'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2's name was not changed
        self.tenant2.refresh_from_db()
        self.assertEqual(self.tenant2.name, 'Tenant 2')
    
    def test_cannot_delete_other_tenant(self):
        """Test that user cannot delete another tenant."""
        response = self.client.delete(
            f'/v1/tenants/{self.tenant2.id}/delete',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify tenant2 was not deleted
        self.tenant2.refresh_from_db()
        self.assertIsNone(self.tenant2.deleted_at)
    
    def test_list_tenants_only_shows_own_memberships(self):
        """Test that listing tenants only shows tenants where user has membership."""
        response = self.client.get(
            '/v1/tenants',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only show tenant1
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.tenant1.id))
        self.assertEqual(response.data[0]['name'], 'Tenant 1')
        
        # Should not show tenant2
        tenant_ids = [t['id'] for t in response.data]
        self.assertNotIn(str(self.tenant2.id), tenant_ids)
    
    # API Key Authentication Isolation Tests
    
    def test_api_key_from_one_tenant_cannot_access_another(self):
        """Test that API key from tenant1 cannot access tenant2's data."""
        # Generate API key for tenant1
        plain_key = 'test_key_tenant1_1234567890123456'
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        self.tenant1.api_keys = [
            {
                'id': 'key-tenant1',
                'key_hash': key_hash,
                'key_preview': 'test_key',
                'name': 'Tenant 1 Key',
                'created_at': '2024-01-01T00:00:00Z',
                'created_by_email': 'admin@tenant1.com'
            }
        ]
        self.tenant1.save()
        
        # Try to access tenant2's data using tenant1's API key
        response = self.client.get(
            '/v1/settings/integrations',
            HTTP_X_TENANT_ID=str(self.tenant2.id),
            HTTP_X_TENANT_API_KEY=plain_key
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # Business Settings Isolation Tests
    
    def test_cannot_access_other_tenant_business_settings(self):
        """Test that user cannot access another tenant's business settings."""
        response = self.client.get(
            '/v1/settings/business',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_cannot_update_other_tenant_business_settings(self):
        """Test that user cannot update another tenant's business settings."""
        response = self.client.put(
            '/v1/settings/business',
            {
                'timezone': 'America/New_York',
                'business_hours': {'monday': {'open': '09:00', 'close': '17:00'}}
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant2.id)
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
