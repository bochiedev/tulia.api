"""
Tests for onboarding API endpoints.

Validates:
- GET /v1/settings/onboarding returns correct status
- POST /v1/settings/onboarding/complete marks steps complete
- RBAC enforcement (integrations:view, integrations:manage, users:manage)
- Completion percentage calculation
- Tenant isolation
"""
import pytest
from django.test import TestCase, RequestFactory
from rest_framework.test import force_authenticate
from rest_framework import status as http_status

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, TenantUserRole
from apps.rbac.services import RBACService
from apps.tenants.services.onboarding_service import OnboardingService
from apps.tenants.views_onboarding import OnboardingStatusView, OnboardingCompleteView


@pytest.mark.django_db
class TestOnboardingAPI(TestCase):
    """Test onboarding API endpoints."""
    
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
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create permissions
        self.perm_integrations_view = Permission.objects.create(
            code='integrations:view',
            label='View Integrations',
            category='integrations'
        )
        self.perm_integrations_manage = Permission.objects.create(
            code='integrations:manage',
            label='Manage Integrations',
            category='integrations'
        )
        self.perm_users_manage = Permission.objects.create(
            code='users:manage',
            label='Manage Users',
            category='users'
        )
        
        # Create role with integrations:view
        self.viewer_role = Role.objects.create(
            tenant=self.tenant,
            name='Viewer',
            is_system=True
        )
        RolePermission.objects.create(
            role=self.viewer_role,
            permission=self.perm_integrations_view
        )
        
        # Create role with integrations:manage
        self.manager_role = Role.objects.create(
            tenant=self.tenant,
            name='Manager',
            is_system=True
        )
        RolePermission.objects.create(
            role=self.manager_role,
            permission=self.perm_integrations_manage
        )
        
        # Request factory for direct view testing
        self.factory = RequestFactory()
        
        # Initialize onboarding status
        settings = TenantSettings.objects.get(tenant=self.tenant)
        settings.initialize_onboarding_status()
    
    def _create_membership_with_scopes(self, scopes):
        """Helper to create tenant membership with specific scopes."""
        # Create membership
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='accepted'
        )
        
        # Assign roles based on scopes
        if 'integrations:view' in scopes:
            TenantUserRole.objects.create(tenant_user=membership, role=self.viewer_role)
        if 'integrations:manage' in scopes:
            TenantUserRole.objects.create(tenant_user=membership, role=self.manager_role)
        
        return membership
    
    def test_get_onboarding_status_success(self):
        """Test GET /v1/settings/onboarding returns status."""
        # Create membership with integrations:view
        membership = self._create_membership_with_scopes(['integrations:view'])
        
        # Create request and mock middleware context
        request = self.factory.get('/v1/settings/onboarding')
        force_authenticate(request, user=self.user)
        request.tenant = self.tenant
        request.membership = membership
        request.scopes = RBACService.resolve_scopes(membership)
        
        # Call view directly
        view = OnboardingStatusView.as_view()
        response = view(request)
        
        # Assert response
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('completed', response.data)
        self.assertIn('completion_percentage', response.data)
        self.assertIn('required_steps', response.data)
        self.assertIn('optional_steps', response.data)
        self.assertIn('pending_steps', response.data)
        
        # Check initial state
        self.assertFalse(response.data['completed'])
        self.assertEqual(response.data['completion_percentage'], 0)
        self.assertEqual(len(response.data['pending_steps']), 3)  # 3 required steps
    
    def test_get_onboarding_status_without_scope(self):
        """Test GET /v1/settings/onboarding requires proper scope."""
        # Create membership without required scopes
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Make request
        response = self.client.get(
            '/v1/settings/onboarding',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        
        # Should return 403
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
    
    def test_mark_step_complete_success(self):
        """Test POST /v1/settings/onboarding/complete marks step complete."""
        # Create membership with integrations:manage
        self._create_membership_with_scopes(['integrations:manage'])
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Mark step complete
        response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'twilio_configured'},
            format='json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        
        # Assert response
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['completed'])  # Not all steps complete
        self.assertEqual(response.data['completion_percentage'], 33)  # 1 of 3 required
        
        # Check step is marked complete
        self.assertTrue(response.data['required_steps']['twilio_configured']['completed'])
        self.assertIsNotNone(response.data['required_steps']['twilio_configured']['completed_at'])
    
    def test_mark_all_steps_complete(self):
        """Test marking all required steps complete."""
        # Create membership with integrations:manage
        self._create_membership_with_scopes(['integrations:manage'])
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Mark all required steps complete
        for step in OnboardingService.REQUIRED_STEPS:
            response = self.client.post(
                '/v1/settings/onboarding/complete',
                {'step': step},
                format='json',
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
                HTTP_X_TENANT_ID=str(self.tenant.id)
            )
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        
        # Final response should show 100% complete
        self.assertTrue(response.data['completed'])
        self.assertEqual(response.data['completion_percentage'], 100)
        self.assertEqual(len(response.data['pending_steps']), 0)
    
    def test_mark_optional_step_complete(self):
        """Test marking optional step complete doesn't affect completion percentage."""
        # Create membership with integrations:manage
        self._create_membership_with_scopes(['integrations:manage'])
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Mark optional step complete
        response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'woocommerce_configured'},
            format='json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        
        # Assert response
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['completion_percentage'], 0)  # Still 0%
        
        # Check optional step is marked complete
        self.assertTrue(response.data['optional_steps']['woocommerce_configured']['completed'])
    
    def test_mark_step_complete_invalid_step(self):
        """Test marking invalid step returns error."""
        # Create membership with integrations:manage
        self._create_membership_with_scopes(['integrations:manage'])
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Try to mark invalid step
        response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'invalid_step'},
            format='json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        
        # Should return 400
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('step', response.data)
    
    def test_mark_step_complete_without_scope(self):
        """Test POST /v1/settings/onboarding/complete requires proper scope."""
        # Create membership without required scopes
        TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Try to mark step complete
        response = self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'twilio_configured'},
            format='json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        
        # Should return 403
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
    
    def test_tenant_isolation(self):
        """Test that onboarding status is tenant-isolated."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name='Test Business 2',
            slug='test-business-2',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155555678',
        )
        
        # Initialize onboarding for tenant2
        settings2 = TenantSettings.objects.get(tenant=tenant2)
        settings2.initialize_onboarding_status()
        
        # Delete any existing membership for this user in tenant1
        TenantUser.objects.filter(tenant=self.tenant, user=self.user).delete()
        
        # Create membership for tenant1 with both view and manage scopes
        self._create_membership_with_scopes(['integrations:view', 'integrations:manage'])
        
        # Authenticate user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Mark step complete for tenant1
        self.client.post(
            '/v1/settings/onboarding/complete',
            {'step': 'twilio_configured'},
            format='json',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        
        # Check tenant1 status
        response1 = self.client.get(
            '/v1/settings/onboarding',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(response1.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response1.data['completion_percentage'], 33)
        
        # Create membership for tenant2
        membership2 = TenantUser.objects.create(
            tenant=tenant2,
            user=self.user,
            is_active=True,
            invite_status='accepted'
        )
        
        # Create role for tenant2
        role2 = Role.objects.create(tenant=tenant2, name='Viewer')
        RolePermission.objects.create(role=role2, permission=self.perm_integrations_view)
        TenantUserRole.objects.create(tenant_user=membership2, role=role2)
        
        # Check tenant2 status (should be 0%)
        response2 = self.client.get(
            '/v1/settings/onboarding',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(tenant2.id)
        )
        self.assertEqual(response2.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response2.data['completion_percentage'], 0)
