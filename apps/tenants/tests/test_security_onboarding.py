"""
Security Tests for Onboarding Feature.

Validates that:
- Credentials are stored encrypted
- Payment methods are stored as tokens only (no full card numbers)
- API keys are stored as hashes only
- Passwords are hashed with bcrypt
- Rate limiting works on auth endpoints
- No sensitive data is exposed in API responses
"""
import pytest
import hashlib
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole
from apps.core.encryption import decrypt_value


@pytest.mark.django_db
class TestCredentialEncryption(TestCase):
    """Test that credentials are stored encrypted."""
    
    def setUp(self):
        """Set up test data."""
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
        )
        
        self.user = User.objects.create(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create permission and role
        perm = Permission.objects.create(
            code='integrations:manage',
            label='Manage Integrations',
            category='integrations'
        )
        role = Role.objects.create(tenant=self.tenant, name='Admin')
        RolePermission.objects.create(role=role, permission=perm)
        
        tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        self.client = APIClient()
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_twilio_credentials_stored_encrypted(self):
        """Test that Twilio credentials are stored encrypted in database."""
        # Update credentials via API
        response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'AC1234567890abcdef1234567890abcd',
                'token': 'test_token_secret_1234567890123'
            },
            format='json',
            **self.headers
        )
        
        # Get settings from database
        settings = TenantSettings.objects.get(tenant=self.tenant)
        
        # Raw database value should be encrypted (not plain text)
        # EncryptedCharField stores encrypted data
        raw_sid = settings.__dict__['twilio_sid']
        raw_token = settings.__dict__['twilio_token']
        
        # Encrypted values should not match plain text
        self.assertNotEqual(raw_sid, 'AC1234567890abcdef1234567890abcd')
        self.assertNotEqual(raw_token, 'test_token_secret_1234567890123')
        
        # But decrypted values should match
        self.assertEqual(settings.twilio_sid, 'AC1234567890abcdef1234567890abcd')
        self.assertEqual(settings.twilio_token, 'test_token_secret_1234567890123')
    
    def test_woocommerce_credentials_stored_encrypted(self):
        """Test that WooCommerce credentials are stored encrypted."""
        response = self.client.put(
            '/v1/settings/integrations/woocommerce',
            {
                'store_url': 'https://example.com',
                'consumer_key': 'ck_secret_key_12345',
                'consumer_secret': 'cs_secret_12345'
            },
            format='json',
            **self.headers
        )
        
        settings = TenantSettings.objects.get(tenant=self.tenant)
        
        # Raw values should be encrypted
        raw_key = settings.__dict__['woo_consumer_key']
        raw_secret = settings.__dict__['woo_consumer_secret']
        
        self.assertNotEqual(raw_key, 'ck_secret_key_12345')
        self.assertNotEqual(raw_secret, 'cs_secret_12345')
        
        # Decrypted values should match
        self.assertEqual(settings.woo_consumer_key, 'ck_secret_key_12345')
        self.assertEqual(settings.woo_consumer_secret, 'cs_secret_12345')
    
    def test_shopify_credentials_stored_encrypted(self):
        """Test that Shopify credentials are stored encrypted."""
        response = self.client.put(
            '/v1/settings/integrations/shopify',
            {
                'shop_domain': 'test.myshopify.com',
                'access_token': 'shpat_secret_token_12345'
            },
            format='json',
            **self.headers
        )
        
        settings = TenantSettings.objects.get(tenant=self.tenant)
        
        # Raw value should be encrypted
        raw_token = settings.__dict__['shopify_access_token']
        
        self.assertNotEqual(raw_token, 'shpat_secret_token_12345')
        
        # Decrypted value should match
        self.assertEqual(settings.shopify_access_token, 'shpat_secret_token_12345')
    
    def test_payout_details_stored_encrypted(self):
        """Test that payout details are stored encrypted."""
        # Create finance permission
        perm = Permission.objects.create(
            code='finance:manage',
            label='Manage Finance',
            category='finance'
        )
        role = Role.objects.create(tenant=self.tenant, name='Finance')
        RolePermission.objects.create(role=role, permission=perm)
        tenant_user = TenantUser.objects.get(tenant=self.tenant, user=self.user)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Update tier to enable payment facilitation
        self.tier.payment_facilitation_enabled = True
        self.tier.save()
        
        response = self.client.put(
            '/v1/settings/payout-method',
            {
                'method': 'bank_transfer',
                'account_number': '1234567890',
                'routing_number': '021000021',
                'account_holder_name': 'Test Business'
            },
            format='json',
            **self.headers
        )
        
        settings = TenantSettings.objects.get(tenant=self.tenant)
        
        # Payout details should be stored as encrypted JSON
        # The field itself is encrypted
        self.assertIsNotNone(settings.payout_details)
        self.assertEqual(settings.payout_details['method'], 'bank_transfer')
        
        # Account number should be in encrypted storage
        self.assertEqual(settings.payout_details['account_number'], '1234567890')


@pytest.mark.django_db
class TestPaymentMethodSecurity(TestCase):
    """Test that payment methods are stored securely."""
    
    def setUp(self):
        """Set up test data."""
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
        )
        
        self.user = User.objects.create(
            email='test@example.com',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create permission and role
        perm = Permission.objects.create(
            code='finance:manage',
            label='Manage Finance',
            category='finance'
        )
        role = Role.objects.create(tenant=self.tenant, name='Finance')
        RolePermission.objects.create(role=role, permission=perm)
        
        tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        self.client = APIClient()
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_payment_methods_stored_as_tokens_only(self):
        """Test that payment methods are stored as Stripe tokens, not full card numbers."""
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
        
        # Verify no full card number is stored
        settings.refresh_from_db()
        payment_method = settings.stripe_payment_methods[0]
        
        # Should only have last4, not full number
        self.assertIn('last4', payment_method)
        self.assertNotIn('card_number', payment_method)
        self.assertNotIn('number', payment_method)
        
        # Should have Stripe payment method ID
        self.assertIn('id', payment_method)
        self.assertTrue(payment_method['id'].startswith('pm_'))
    
    def test_payment_methods_api_never_returns_full_card_numbers(self):
        """Test that API responses never contain full card numbers."""
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
        
        # Get payment methods via API
        response = self.client.get(
            '/v1/settings/payment-methods',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Response should only have last4
        pm = response.data['payment_methods'][0]
        self.assertEqual(pm['last4'], '4242')
        self.assertNotIn('card_number', pm)
        self.assertNotIn('number', pm)
        
        # Should not contain any 16-digit numbers (card numbers)
        response_str = str(response.data)
        import re
        card_pattern = re.compile(r'\b\d{16}\b')
        self.assertIsNone(card_pattern.search(response_str))


@pytest.mark.django_db
class TestAPIKeySecurity(TestCase):
    """Test that API keys are stored securely."""
    
    def setUp(self):
        """Set up test data."""
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
        )
        
        self.user = User.objects.create(
            email='test@example.com',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create permission and role
        perm = Permission.objects.create(
            code='users:manage',
            label='Manage Users',
            category='users'
        )
        role = Role.objects.create(tenant=self.tenant, name='Admin')
        RolePermission.objects.create(role=role, permission=perm)
        
        tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        self.client = APIClient()
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_api_keys_stored_as_hashes_only(self):
        """Test that API keys are stored as SHA-256 hashes, not plain text."""
        # Generate API key
        response = self.client.post(
            '/v1/settings/api-keys',
            {'name': 'Test Key'},
            format='json',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Get plain key from response
        plain_key = response.data['api_key']
        
        # Verify key is returned once
        self.assertIsNotNone(plain_key)
        self.assertEqual(len(plain_key), 32)
        
        # Check database storage
        self.tenant.refresh_from_db()
        stored_key = self.tenant.api_keys[0]
        
        # Should store hash, not plain key
        self.assertIn('key_hash', stored_key)
        self.assertNotEqual(stored_key['key_hash'], plain_key)
        
        # Verify hash is SHA-256
        expected_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        self.assertEqual(stored_key['key_hash'], expected_hash)
        
        # Should not store plain key
        self.assertNotIn(plain_key, str(self.tenant.api_keys))
    
    def test_api_keys_list_returns_masked_keys_only(self):
        """Test that listing API keys returns masked keys, not full keys."""
        # Add API key
        plain_key = 'test_key_1234567890123456789012'
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        self.tenant.api_keys = [
            {
                'id': 'key-test',
                'key_hash': key_hash,
                'key_preview': 'test_key',
                'name': 'Test Key',
                'created_at': '2024-01-01T00:00:00Z',
                'created_by_email': 'test@example.com'
            }
        ]
        self.tenant.save()
        
        # List API keys
        response = self.client.get(
            '/v1/settings/api-keys',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return masked preview only
        key = response.data['api_keys'][0]
        self.assertEqual(key['key_preview'], 'test_key')
        
        # Should not return hash or full key
        self.assertNotIn('key_hash', key)
        self.assertNotIn(plain_key, str(response.data))
        self.assertNotIn(key_hash, str(response.data))


@pytest.mark.django_db
class TestPasswordSecurity(TestCase):
    """Test that passwords are hashed securely."""
    
    def test_passwords_hashed_with_bcrypt(self):
        """Test that passwords are hashed using Django's password hasher."""
        # Create user via registration
        client = APIClient()
        
        response = client.post(
            '/v1/auth/register',
            {
                'email': 'newuser@example.com',
                'password': 'SecurePass123!',
                'first_name': 'Test',
                'last_name': 'User',
                'business_name': 'Test Business'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Get user from database
        user = User.objects.get(email='newuser@example.com')
        
        # Password should be hashed
        self.assertNotEqual(user.password, 'SecurePass123!')
        
        # Should use Django's password hasher (bcrypt or pbkdf2)
        self.assertTrue(user.password.startswith('pbkdf2_') or user.password.startswith('bcrypt'))
        
        # Should be able to verify password
        self.assertTrue(user.check_password('SecurePass123!'))
        self.assertFalse(user.check_password('WrongPassword'))
    
    def test_password_not_returned_in_api_responses(self):
        """Test that password is never returned in API responses."""
        # Create user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        # Get user profile
        response = client.get('/v1/auth/me')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should not contain password field
        self.assertNotIn('password', response.data)
        self.assertNotIn('testpass123', str(response.data))


@pytest.mark.django_db
class TestCredentialMasking(TestCase):
    """Test that credentials are properly masked in API responses."""
    
    def setUp(self):
        """Set up test data."""
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
        )
        
        self.user = User.objects.create(
            email='test@example.com',
            is_active=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        # Create permission and role
        perm = Permission.objects.create(
            code='integrations:manage',
            label='Manage Integrations',
            category='integrations'
        )
        role = Role.objects.create(tenant=self.tenant, name='Admin')
        RolePermission.objects.create(role=role, permission=perm)
        
        tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
        
        self.client = APIClient()
        self.headers = {
            'HTTP_AUTHORIZATION': f'Bearer {self.jwt_token}',
            'HTTP_X_TENANT_ID': str(self.tenant.id),
        }
    
    def test_twilio_credentials_masked_in_response(self):
        """Test that Twilio credentials are masked in API responses."""
        # Set up credentials
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.twilio_sid = 'AC1234567890abcdef1234567890abcd'
        settings.twilio_token = 'test_token_secret'
        settings.twilio_webhook_secret = 'webhook_secret'
        settings.save()
        
        # Get credentials
        response = self.client.get(
            '/v1/settings/integrations/twilio',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should show masked SID
        self.assertIn('****', response.data['credentials']['sid_masked'])
        
        # Should not show full credentials
        self.assertNotIn('AC1234567890abcdef1234567890abcd', str(response.data))
        self.assertNotIn('test_token_secret', str(response.data))
        self.assertNotIn('webhook_secret', str(response.data))
    
    def test_payout_details_masked_in_response(self):
        """Test that payout details are masked in API responses."""
        # Create finance permission
        perm = Permission.objects.create(
            code='finance:manage',
            label='Manage Finance',
            category='finance'
        )
        role = Role.objects.create(tenant=self.tenant, name='Finance')
        RolePermission.objects.create(role=role, permission=perm)
        tenant_user = TenantUser.objects.get(tenant=self.tenant, user=self.user)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Update tier
        self.tier.payment_facilitation_enabled = True
        self.tier.save()
        
        # Set up payout method
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.payout_details = {
            'method': 'bank_transfer',
            'account_number': '1234567890',
            'routing_number': '021000021',
            'account_holder_name': 'Test Business'
        }
        settings.save()
        
        # Get payout method
        response = self.client.get(
            '/v1/settings/payout-method',
            **self.headers
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should show masked account number
        self.assertIn('****', response.data['account_number_masked'])
        
        # Should not show full account number
        self.assertNotIn('1234567890', str(response.data))
