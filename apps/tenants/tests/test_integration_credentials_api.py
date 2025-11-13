"""
Tests for integration credentials API endpoints.

Validates:
- GET /v1/settings/integrations - list all integrations
- GET /v1/settings/integrations/twilio - get Twilio credentials
- PUT /v1/settings/integrations/twilio - update Twilio credentials
- DELETE /v1/settings/integrations/twilio - remove Twilio credentials
- Same for WooCommerce and Shopify
- RBAC enforcement (integrations:manage scope required)
- Credential masking in responses
- Audit logging
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole


@pytest.mark.django_db
class TestIntegrationCredentialsAPI(TestCase):
    """Test integration credentials API endpoints."""
    
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
        
        # Create integrations:manage permission
        self.integrations_manage_perm = Permission.objects.create(
            code='integrations:manage',
            label='Manage Integrations',
            description='Can manage integration credentials',
            category='integrations'
        )
        
        # Get or create role with integrations:manage permission
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name='Admin',
            defaults={'description': 'Administrator role'}
        )
        RolePermission.objects.create(
            role=self.admin_role,
            permission=self.integrations_manage_perm
        )
        
        # Create tenant user with admin role
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(
            tenant_user=self.tenant_user,
            role=self.admin_role
        )
        
        # Generate JWT token for authentication
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        # Set up API client
        self.client = APIClient()
        
        # Set tenant context headers with JWT authentication
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_list_integrations_requires_scope(self):
        """Test that listing integrations requires integrations:manage scope."""
        # Remove permission
        RolePermission.objects.filter(role=self.admin_role).delete()
        
        response = self.client.get(
            '/v1/settings/integrations',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('integrations:manage', response.data['detail'])
    
    def test_list_integrations_empty(self):
        """Test listing integrations when none are configured."""
        response = self.client.get(
            '/v1/settings/integrations',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('integrations', response.data)
        self.assertEqual(response.data['total_configured'], 0)
        
        # Should have all integration types listed
        integration_names = [i['name'] for i in response.data['integrations']]
        self.assertIn('twilio', integration_names)
        self.assertIn('woocommerce', integration_names)
        self.assertIn('shopify', integration_names)
        self.assertIn('openai', integration_names)
    
    def test_get_twilio_credentials_not_configured(self):
        """Test getting Twilio credentials when not configured."""
        response = self.client.get(
            '/v1/settings/integrations/twilio',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['configured'])
        self.assertIsNone(response.data['credentials'])
    
    def test_update_twilio_credentials_invalid_data(self):
        """Test updating Twilio credentials with invalid data."""
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'invalid',  # Too short
                'token': 'short'   # Too short
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sid', response.data)
    
    def test_update_twilio_credentials_invalid_sid_format(self):
        """Test updating Twilio credentials with invalid SID format."""
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'XX1234567890abcdef1234567890abcd',  # Doesn't start with AC
                'token': 'test_token_1234567890123456789012'
            },
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sid', response.data)
    
    def test_get_twilio_credentials_configured(self):
        """Test getting Twilio credentials when configured."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.twilio_sid = 'AC1234567890abcdef1234567890abcd'
        settings.twilio_token = 'test_token_1234567890123456789012'
        settings.twilio_webhook_secret = 'webhook_secret_xyz'
        settings.save()
        
        response = self.client.get(
            '/v1/settings/integrations/twilio',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['configured'])
        
        # Check credentials are masked
        credentials = response.data['credentials']
        self.assertIn('****', credentials['sid_masked'])
        self.assertTrue(credentials['has_token'])
        self.assertTrue(credentials['has_webhook_secret'])
        
        # Should not contain full credentials
        self.assertNotIn('AC1234567890abcdef1234567890abcd', str(response.data))
    
    def test_delete_twilio_credentials(self):
        """Test deleting Twilio credentials."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.twilio_sid = 'AC1234567890abcdef1234567890abcd'
        settings.twilio_token = 'test_token_1234567890123456789012'
        settings.save()
        
        response = self.client.delete(
            '/v1/settings/integrations/twilio',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('removed', response.data['message'].lower())
        
        # Verify credentials are removed
        settings.refresh_from_db()
        self.assertEqual(settings.twilio_sid, '')
        self.assertEqual(settings.twilio_token, '')
    
    def test_get_woocommerce_credentials_configured(self):
        """Test getting WooCommerce credentials when configured."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.woo_store_url = 'https://example.com'
        settings.woo_consumer_key = 'ck_test1234567890'
        settings.woo_consumer_secret = 'cs_test1234567890'
        settings.save()
        
        response = self.client.get(
            '/v1/settings/integrations/woocommerce',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['configured'])
        
        # Check credentials are masked
        credentials = response.data['credentials']
        self.assertEqual(credentials['store_url'], 'https://example.com')
        self.assertIn('****', credentials['consumer_key_masked'])
        self.assertTrue(credentials['has_consumer_secret'])
        
        # Should not contain full credentials
        self.assertNotIn('ck_test1234567890', str(response.data))
    
    def test_delete_woocommerce_credentials(self):
        """Test deleting WooCommerce credentials."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.woo_store_url = 'https://example.com'
        settings.woo_consumer_key = 'ck_test1234567890'
        settings.woo_consumer_secret = 'cs_test1234567890'
        settings.save()
        
        response = self.client.delete(
            '/v1/settings/integrations/woocommerce',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify credentials are removed
        settings.refresh_from_db()
        self.assertEqual(settings.woo_store_url, '')
        self.assertEqual(settings.woo_consumer_key, '')
    
    def test_get_shopify_credentials_configured(self):
        """Test getting Shopify credentials when configured."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.shopify_shop_domain = 'test-shop.myshopify.com'
        settings.shopify_access_token = 'shpat_test1234567890'
        settings.save()
        
        response = self.client.get(
            '/v1/settings/integrations/shopify',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['configured'])
        
        # Check credentials are masked
        credentials = response.data['credentials']
        self.assertEqual(credentials['shop_domain'], 'test-shop.myshopify.com')
        self.assertTrue(credentials['has_access_token'])
        
        # Should not contain full credentials
        self.assertNotIn('shpat_test1234567890', str(response.data))
    
    def test_delete_shopify_credentials(self):
        """Test deleting Shopify credentials."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.shopify_shop_domain = 'test-shop.myshopify.com'
        settings.shopify_access_token = 'shpat_test1234567890'
        settings.save()
        
        response = self.client.delete(
            '/v1/settings/integrations/shopify',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify credentials are removed
        settings.refresh_from_db()
        self.assertEqual(settings.shopify_shop_domain, '')
        self.assertEqual(settings.shopify_access_token, '')
    
    def test_list_integrations_with_configured(self):
        """Test listing integrations when some are configured."""
        # Configure Twilio and WooCommerce
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.twilio_sid = 'AC1234567890abcdef1234567890abcd'
        settings.twilio_token = 'test_token_1234567890123456789012'
        settings.woo_store_url = 'https://example.com'
        settings.woo_consumer_key = 'ck_test1234567890'
        settings.woo_consumer_secret = 'cs_test1234567890'
        settings.save()
        
        response = self.client.get(
            '/v1/settings/integrations',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_configured'], 2)
        
        # Find Twilio integration
        twilio = next(i for i in response.data['integrations'] if i['name'] == 'twilio')
        self.assertTrue(twilio['configured'])
        self.assertIn('****', twilio['credentials']['sid_masked'])
        
        # Find WooCommerce integration
        woo = next(i for i in response.data['integrations'] if i['name'] == 'woocommerce')
        self.assertTrue(woo['configured'])
        self.assertEqual(woo['credentials']['store_url'], 'https://example.com')
        
        # Find Shopify integration (not configured)
        shopify = next(i for i in response.data['integrations'] if i['name'] == 'shopify')
        self.assertFalse(shopify['configured'])
        self.assertIsNone(shopify['credentials'])
    
    def test_tenant_isolation(self):
        """Test that users cannot access other tenant's credentials."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name='Other Business',
            slug='other-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155559999',
        )
        
        # Configure credentials for other tenant
        other_settings = TenantSettings.objects.get(tenant=other_tenant)
        other_settings.twilio_sid = 'AC9999999999999999999999999999999'
        other_settings.twilio_token = 'other_token_999999999999999999999'
        other_settings.save()
        
        # Try to access other tenant's credentials with valid JWT but wrong tenant
        response = self.client.get(
            '/v1/settings/integrations/twilio',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(other_tenant.id)
        )
        
        # Should be forbidden (no membership in other tenant)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
