"""
Integration Tests for Complete Onboarding Flows.

Tests end-to-end user journeys:
- Registration → Login → Create Tenant → Add Settings
- Multi-tenant flow with context switching
- Complete onboarding flow from start to finish
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission


@pytest.mark.django_db
class TestCompleteOnboardingFlow(TestCase):
    """Test complete onboarding flow from registration to configuration."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
    
    def test_complete_onboarding_flow(self):
        """Test complete flow: register → login → configure settings → complete onboarding."""
        
        # Step 1: Register new user
        register_response = self.client.post(
            '/v1/auth/register',
            {
                'email': 'newuser@example.com',
                'password': 'SecurePass123!',
                'first_name': 'John',
                'last_name': 'Doe',
                'business_name': 'Acme Corp'
            },
            format='json'
        )
        
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', register_response.data)
        self.assertIn('tenant', register_response.data)
        
        jwt_token = register_response.data['token']
        tenant_id = register_response.data['tenant']['id']
        
        # Verify user was created
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.first_name, 'John')
        
        # Verify tenant was created
        tenant = Tenant.objects.get(id=tenant_id)
        self.assertEqual(tenant.name, 'Acme Corp')
        self.assertEqual(tenant.status, 'trial')
        
        # Verify user is Owner
        tenant_user = TenantUser.objects.get(tenant=tenant, user=user)
        self.assertEqual(tenant_user.invite_status, 'accepted')
        
        # Step 2: Check onboarding status (should be 0%)
        onboarding_response = self.client.get(
            '/v1/settings/onboarding',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(onboarding_response.status_code, status.HTTP_200_OK)
        self.assertFalse(onboarding_response.data['completed'])
        self.assertEqual(onboarding_response.data['completion_percentage'], 0)
        self.assertEqual(len(onboarding_response.data['pending_steps']), 3)
        
        # Step 3: Configure Twilio credentials
        twilio_response = self.client.put(
            '/v1/settings/integrations/twilio',
            {
                'sid': 'AC1234567890abcdef1234567890abcd',
                'token': 'test_token_1234567890123456789012'
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        # May fail validation but should not be 403
        self.assertNotEqual(twilio_response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Mark Twilio step complete
        complete_response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'twilio_configured'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_response.data['completion_percentage'], 33)
        
        # Step 4: Add payment method (mock Stripe)
        with patch('stripe.Customer.create') as mock_customer, \
             patch('stripe.PaymentMethod.attach') as mock_attach:
            
            mock_customer.return_value = MagicMock(id='cus_test123')
            mock_attach.return_value = MagicMock(
                id='pm_test123',
                card=MagicMock(
                    last4='4242',
                    brand='visa',
                    exp_month=12,
                    exp_year=2025
                )
            )
            
            payment_response = self.client.post(
                '/v1/settings/payment-methods',
                {'payment_method_id': 'pm_test123'},
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
                HTTP_X_TENANT_ID=tenant_id
            )
            
            self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED)
        
        # Mark payment method step complete
        complete_response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'payment_method_added'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_response.data['completion_percentage'], 67)
        
        # Step 5: Configure business settings
        business_response = self.client.put(
            '/v1/settings/business',
            {
                'timezone': 'America/New_York',
                'business_hours': {
                    'monday': {'open': '09:00', 'close': '17:00'},
                    'tuesday': {'open': '09:00', 'close': '17:00'}
                }
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertNotEqual(business_response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Mark business settings step complete
        complete_response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'business_settings_configured'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertTrue(complete_response.data['completed'])
        self.assertEqual(complete_response.data['completion_percentage'], 100)
        
        # Step 6: Verify onboarding is complete
        final_status = self.client.get(
            '/v1/settings/onboarding',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(final_status.status_code, status.HTTP_200_OK)
        self.assertTrue(final_status.data['completed'])
        self.assertEqual(len(final_status.data['pending_steps']), 0)


@pytest.mark.django_db
class TestMultiTenantFlow(TestCase):
    """Test multi-tenant flow with context switching."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Professional',
            monthly_price=99.00,
            yearly_price=950.00,
        )
    
    def test_multi_tenant_context_switching(self):
        """Test user managing multiple tenants with context switching."""
        
        # Step 1: Register and create first tenant
        register_response = self.client.post(
            '/v1/auth/register',
            {
                'email': 'multiuser@example.com',
                'password': 'SecurePass123!',
                'first_name': 'Multi',
                'last_name': 'Tenant',
                'business_name': 'First Business'
            },
            format='json'
        )
        
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        jwt_token = register_response.data['token']
        tenant1_id = register_response.data['tenant']['id']
        
        # Step 2: Create second tenant
        create_tenant_response = self.client.post(
            '/v1/tenants/create',
            {
                'name': 'Second Business',
                'slug': 'second-business'
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}'
        )
        
        self.assertEqual(create_tenant_response.status_code, status.HTTP_201_CREATED)
        tenant2_id = create_tenant_response.data['id']
        
        # Step 3: List tenants (should show both)
        list_response = self.client.get(
            '/v1/tenants',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}'
        )
        
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 2)
        
        tenant_names = [t['name'] for t in list_response.data]
        self.assertIn('First Business', tenant_names)
        self.assertIn('Second Business', tenant_names)
        
        # Step 4: Configure settings for tenant1
        tenant1 = Tenant.objects.get(id=tenant1_id)
        settings1 = TenantSettings.objects.get(tenant=tenant1)
        settings1.twilio_sid = 'AC1111111111111111111111111111111'
        settings1.save()
        
        # Step 5: Configure settings for tenant2
        tenant2 = Tenant.objects.get(id=tenant2_id)
        settings2 = TenantSettings.objects.get(tenant=tenant2)
        settings2.twilio_sid = 'AC2222222222222222222222222222222'
        settings2.save()
        
        # Step 6: Access tenant1's settings
        tenant1_settings = self.client.get(
            '/v1/settings/integrations/twilio',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant1_id
        )
        
        self.assertEqual(tenant1_settings.status_code, status.HTTP_200_OK)
        self.assertIn('****1111', tenant1_settings.data['credentials']['sid_masked'])
        
        # Step 7: Switch context to tenant2
        tenant2_settings = self.client.get(
            '/v1/settings/integrations/twilio',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant2_id
        )
        
        self.assertEqual(tenant2_settings.status_code, status.HTTP_200_OK)
        self.assertIn('****2222', tenant2_settings.data['credentials']['sid_masked'])
        
        # Step 8: Verify no cross-tenant data leakage
        self.assertNotIn('1111', str(tenant2_settings.data))
        self.assertNotIn('2222', str(tenant1_settings.data))


@pytest.mark.django_db
class TestRegistrationToLoginFlow(TestCase):
    """Test registration to login flow."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
    
    def test_register_then_login_flow(self):
        """Test registering a new user then logging in."""
        
        # Step 1: Register
        register_response = self.client.post(
            '/v1/auth/register',
            {
                'email': 'logintest@example.com',
                'password': 'SecurePass123!',
                'first_name': 'Login',
                'last_name': 'Test',
                'business_name': 'Test Corp'
            },
            format='json'
        )
        
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        first_token = register_response.data['token']
        tenant_id = register_response.data['tenant']['id']
        
        # Step 2: Login with same credentials
        login_response = self.client.post(
            '/v1/auth/login',
            {
                'email': 'logintest@example.com',
                'password': 'SecurePass123!'
            },
            format='json'
        )
        
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('token', login_response.data)
        second_token = login_response.data['token']
        
        # Tokens should be different (new session)
        self.assertNotEqual(first_token, second_token)
        
        # Step 3: Use new token to access tenant
        tenant_response = self.client.get(
            '/v1/tenants',
            HTTP_AUTHORIZATION=f'Bearer {second_token}'
        )
        
        self.assertEqual(tenant_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(tenant_response.data), 1)
        self.assertEqual(tenant_response.data[0]['id'], tenant_id)
        
        # Step 4: Login with wrong password
        wrong_login = self.client.post(
            '/v1/auth/login',
            {
                'email': 'logintest@example.com',
                'password': 'WrongPassword'
            },
            format='json'
        )
        
        self.assertEqual(wrong_login.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestAPIKeyFlow(TestCase):
    """Test API key generation and usage flow."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
    
    def test_generate_and_use_api_key_flow(self):
        """Test generating an API key and using it for authentication."""
        
        # Step 1: Register user
        register_response = self.client.post(
            '/v1/auth/register',
            {
                'email': 'apiuser@example.com',
                'password': 'SecurePass123!',
                'first_name': 'API',
                'last_name': 'User',
                'business_name': 'API Corp'
            },
            format='json'
        )
        
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        jwt_token = register_response.data['token']
        tenant_id = register_response.data['tenant']['id']
        
        # Step 2: Generate API key
        generate_response = self.client.post(
            '/v1/settings/api-keys',
            {'name': 'Production Key'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(generate_response.status_code, status.HTTP_201_CREATED)
        api_key = generate_response.data['api_key']
        key_id = generate_response.data['key_id']
        
        # Verify key was returned
        self.assertIsNotNone(api_key)
        self.assertEqual(len(api_key), 32)
        
        # Step 3: List API keys (should show masked)
        list_response = self.client.get(
            '/v1/settings/api-keys',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        # May have initial key from signal + new key
        self.assertGreaterEqual(list_response.data['total'], 1)
        
        # Find our key
        our_key = next((k for k in list_response.data['api_keys'] if k['name'] == 'Production Key'), None)
        self.assertIsNotNone(our_key)
        self.assertNotIn(api_key, str(list_response.data))  # Full key not shown
        
        # Step 4: Use API key to access endpoint (if API key auth is implemented)
        # This would test middleware API key validation
        # For now, just verify the key exists in tenant
        tenant = Tenant.objects.get(id=tenant_id)
        key_exists = any(k['id'] == key_id for k in tenant.api_keys)
        self.assertTrue(key_exists)
        
        # Step 5: Revoke API key
        revoke_response = self.client.delete(
            f'/v1/settings/api-keys/{key_id}',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=tenant_id
        )
        
        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)
        
        # Verify key was removed
        tenant.refresh_from_db()
        key_exists = any(k['id'] == key_id for k in tenant.api_keys)
        self.assertFalse(key_exists)


@pytest.mark.django_db
class TestPasswordResetFlow(TestCase):
    """Test password reset flow."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
    
    def test_complete_password_reset_flow(self):
        """Test complete password reset flow."""
        
        # Step 1: Register user
        register_response = self.client.post(
            '/v1/auth/register',
            {
                'email': 'resetuser@example.com',
                'password': 'OldPassword123!',
                'first_name': 'Reset',
                'last_name': 'User',
                'business_name': 'Reset Corp'
            },
            format='json'
        )
        
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        
        # Step 2: Request password reset
        forgot_response = self.client.post(
            '/v1/auth/forgot-password',
            {'email': 'resetuser@example.com'},
            format='json'
        )
        
        self.assertEqual(forgot_response.status_code, status.HTTP_200_OK)
        
        # Step 3: Get reset token from database
        from apps.rbac.models import PasswordResetToken
        user = User.objects.get(email='resetuser@example.com')
        reset_token = PasswordResetToken.objects.filter(user=user, used=False).first()
        
        self.assertIsNotNone(reset_token)
        
        # Step 4: Reset password with token
        reset_response = self.client.post(
            '/v1/auth/reset-password',
            {
                'token': reset_token.token,
                'new_password': 'NewPassword123!'
            },
            format='json'
        )
        
        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        
        # Step 5: Verify old password doesn't work
        old_login = self.client.post(
            '/v1/auth/login',
            {
                'email': 'resetuser@example.com',
                'password': 'OldPassword123!'
            },
            format='json'
        )
        
        self.assertEqual(old_login.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Step 6: Verify new password works
        new_login = self.client.post(
            '/v1/auth/login',
            {
                'email': 'resetuser@example.com',
                'password': 'NewPassword123!'
            },
            format='json'
        )
        
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.assertIn('token', new_login.data)
