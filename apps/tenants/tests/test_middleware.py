"""
Tests for tenant middleware.
"""
import pytest
import hashlib
from django.test import TestCase, RequestFactory
from django.utils import timezone
from datetime import timedelta
from unittest.mock import Mock
from apps.tenants.models import Tenant, SubscriptionTier
from apps.tenants.middleware import TenantContextMiddleware
from apps.rbac.models import User, TenantUser, Permission, Role, RolePermission, TenantUserRole


@pytest.mark.django_db
class TestTenantContextMiddleware(TestCase):
    """Test TenantContextMiddleware."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = TenantContextMiddleware(get_response=lambda r: None)
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        # Create active tenant
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
            twilio_sid='test_sid',
            twilio_token='test_token',
            webhook_secret='test_secret',
        )
        
        # Generate API key
        self.api_key = 'test-api-key-12345'
        api_key_hash = hashlib.sha256(self.api_key.encode('utf-8')).hexdigest()
        self.tenant.api_keys = [
            {
                'key_hash': api_key_hash,
                'name': 'Test Key',
                'created_at': timezone.now().isoformat(),
            }
        ]
        self.tenant.save()
    
    def test_public_path_bypass(self):
        """Test that public paths bypass authentication."""
        request = self.factory.get('/v1/health')
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertIsNone(request.tenant)
    
    def test_missing_headers(self):
        """Test error when headers are missing."""
        request = self.factory.get('/v1/products')
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('MISSING_CREDENTIALS', response.content.decode())
    
    def test_invalid_tenant_id(self):
        """Test error with invalid tenant ID."""
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID='00000000-0000-0000-0000-000000000000',
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('INVALID_TENANT', response.content.decode())
    
    def test_invalid_api_key(self):
        """Test error with invalid API key."""
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY='wrong-api-key',
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('INVALID_API_KEY', response.content.decode())
    
    def test_valid_authentication(self):
        """Test successful authentication."""
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.tenant)
    
    def test_inactive_subscription(self):
        """Test error when subscription is inactive."""
        self.tenant.status = 'suspended'
        self.tenant.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('SUBSCRIPTION_INACTIVE', response.content.decode())
    
    def test_valid_trial(self):
        """Test authentication with valid trial."""
        self.tenant.status = 'trial'
        self.tenant.trial_start_date = timezone.now()
        self.tenant.trial_end_date = timezone.now() + timedelta(days=14)
        self.tenant.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.tenant)
    
    def test_expired_trial(self):
        """Test error when trial is expired."""
        self.tenant.status = 'trial'
        self.tenant.trial_start_date = timezone.now() - timedelta(days=20)
        self.tenant.trial_end_date = timezone.now() - timedelta(days=6)
        self.tenant.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
    
    def test_waived_subscription(self):
        """Test authentication with waived subscription."""
        self.tenant.status = 'suspended'
        self.tenant.subscription_waived = True
        self.tenant.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.tenant)


@pytest.mark.django_db
class TestTenantContextMiddlewareRBAC(TestCase):
    """Test RBAC enhancements to TenantContextMiddleware."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = TenantContextMiddleware(get_response=lambda r: None)
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
        )
        
        # Create active tenant
        self.tenant = Tenant.objects.create(
            name='RBAC Test Business',
            slug='rbac-test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155559999',
            twilio_sid='test_sid_rbac',
            twilio_token='test_token_rbac',
            webhook_secret='test_secret_rbac',
        )
        
        # Generate API key
        self.api_key = 'rbac-test-api-key-12345'
        api_key_hash = hashlib.sha256(self.api_key.encode('utf-8')).hexdigest()
        self.tenant.api_keys = [
            {
                'key_hash': api_key_hash,
                'name': 'RBAC Test Key',
                'created_at': timezone.now().isoformat(),
            }
        ]
        self.tenant.save()
        
        # Create user
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123'
        )
        
        # Get or create permissions (they may already exist from seed_permissions)
        self.catalog_view, _ = Permission.objects.get_or_create(
            code='catalog:view',
            defaults={
                'label': 'View Catalog',
                'category': 'catalog'
            }
        )
        self.catalog_edit, _ = Permission.objects.get_or_create(
            code='catalog:edit',
            defaults={
                'label': 'Edit Catalog',
                'category': 'catalog'
            }
        )
        
        # Get or create role (it may already exist from tenant creation signal)
        self.catalog_manager_role, role_created = Role.objects.get_or_create(
            tenant=self.tenant,
            name='Catalog Manager',
            defaults={
                'description': 'Can view and edit catalog'
            }
        )
        
        # Assign permissions to role (only if not already assigned)
        RolePermission.objects.get_or_create(
            role=self.catalog_manager_role,
            permission=self.catalog_view
        )
        RolePermission.objects.get_or_create(
            role=self.catalog_manager_role,
            permission=self.catalog_edit
        )
    
    def test_request_id_injection(self):
        """Test that request_id is injected into request."""
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertTrue(hasattr(request, 'request_id'))
        self.assertIsNotNone(request.request_id)
    
    def test_custom_request_id_preserved(self):
        """Test that custom X-Request-ID header is preserved."""
        custom_request_id = 'custom-request-id-12345'
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
            HTTP_X_REQUEST_ID=custom_request_id,
        )
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.request_id, custom_request_id)
    
    def test_no_authenticated_user(self):
        """Test that middleware handles requests without authenticated user."""
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=self.api_key,
        )
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.tenant)
        self.assertIsNone(request.membership)
        self.assertEqual(request.scopes, set())
    
    def test_authenticated_user_without_membership(self):
        """Test that authenticated user without membership gets 403."""
        # Generate JWT token for user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('FORBIDDEN', response.content.decode())
        self.assertIn('do not have access', response.content.decode())
    
    def test_authenticated_user_with_pending_invitation(self):
        """Test that user with pending invitation gets 403."""
        # Create pending membership
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='pending',
            is_active=True
        )
        
        # Generate JWT token for user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('FORBIDDEN', response.content.decode())
        self.assertIn('pending', response.content.decode())
    
    def test_authenticated_user_with_accepted_membership_no_roles(self):
        """Test that user with accepted membership but no roles has empty scopes."""
        # Create accepted membership
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='accepted',
            joined_at=timezone.now(),
            is_active=True
        )
        
        # Generate JWT token for user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.membership, membership)
        self.assertEqual(request.scopes, set())
    
    def test_authenticated_user_with_role_scopes_resolved(self):
        """Test that user with role has scopes properly resolved."""
        # Create accepted membership
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='accepted',
            joined_at=timezone.now(),
            is_active=True
        )
        
        # Assign role to user
        TenantUserRole.objects.create(
            tenant_user=membership,
            role=self.catalog_manager_role
        )
        
        # Generate JWT token for user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.membership, membership)
        self.assertIn('catalog:view', request.scopes)
        self.assertIn('catalog:edit', request.scopes)
        self.assertEqual(len(request.scopes), 2)
    
    def test_last_seen_at_updated(self):
        """Test that last_seen_at is updated on successful request."""
        # Create accepted membership
        old_timestamp = timezone.now() - timedelta(hours=1)
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='accepted',
            joined_at=timezone.now(),
            last_seen_at=old_timestamp,
            is_active=True
        )
        
        # Generate JWT token for user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        
        # Refresh membership from database
        membership.refresh_from_db()
        
        # Check that last_seen_at was updated
        self.assertIsNotNone(membership.last_seen_at)
        self.assertGreater(membership.last_seen_at, old_timestamp)
    
    def test_public_path_sets_empty_rbac_context(self):
        """Test that public paths set empty membership and scopes."""
        request = self.factory.get('/v1/health')
        request.user = self.user
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertIsNone(request.tenant)
        self.assertIsNone(request.membership)
        self.assertEqual(request.scopes, set())
    
    def test_cross_tenant_access_blocked(self):
        """Test that user cannot access tenant they're not a member of."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name='Other Business',
            slug='other-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155558888',
            twilio_sid='other_sid',
            twilio_token='other_token',
            webhook_secret='other_secret',
        )
        
        # Create membership in first tenant only
        membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='accepted',
            joined_at=timezone.now(),
            is_active=True
        )
        
        # Generate JWT token for user
        from apps.rbac.services import AuthService
        jwt_token = AuthService.generate_jwt(self.user)
        
        # Try to access other tenant
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {jwt_token}',
            HTTP_X_TENANT_ID=str(other_tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('FORBIDDEN', response.content.decode())



@pytest.mark.django_db
class TestTenantContextMiddlewareJWT(TestCase):
    """Test JWT authentication in TenantContextMiddleware."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = TenantContextMiddleware(get_response=lambda r: None)
        
        # Create subscription tier
        self.tier = SubscriptionTier.objects.create(
            name='Professional',
            monthly_price=199.00,
            yearly_price=1900.00,
        )
        
        # Create active tenant
        self.tenant = Tenant.objects.create(
            name='JWT Test Business',
            slug='jwt-test-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155557777',
            twilio_sid='test_sid_jwt',
            twilio_token='test_token_jwt',
            webhook_secret='test_secret_jwt',
        )
        
        # Create user
        self.user = User.objects.create_user(
            email='jwtuser@example.com',
            password='jwtpass123',
            first_name='JWT',
            last_name='User'
        )
        
        # Create accepted membership
        self.membership = TenantUser.objects.create(
            tenant=self.tenant,
            user=self.user,
            invite_status='accepted',
            joined_at=timezone.now(),
            is_active=True
        )
        
        # Create permissions and role
        self.catalog_view, _ = Permission.objects.get_or_create(
            code='catalog:view',
            defaults={
                'label': 'View Catalog',
                'category': 'catalog'
            }
        )
        
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name='Viewer',
            defaults={
                'description': 'Can view catalog'
            }
        )
        
        RolePermission.objects.get_or_create(
            role=self.role,
            permission=self.catalog_view
        )
        
        TenantUserRole.objects.get_or_create(
            tenant_user=self.membership,
            role=self.role
        )
        
        # Generate JWT token
        from apps.rbac.services import AuthService
        self.jwt_token = AuthService.generate_jwt(self.user)
    
    def test_jwt_authentication_success(self):
        """Test successful JWT authentication."""
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.membership, self.membership)
        self.assertIn('catalog:view', request.scopes)
    
    def test_jwt_authentication_invalid_token(self):
        """Test JWT authentication with invalid token."""
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION='Bearer invalid-token-12345',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('INVALID_TOKEN', response.content.decode())
    
    def test_jwt_authentication_expired_token(self):
        """Test JWT authentication with expired token."""
        import jwt
        from django.conf import settings
        from datetime import datetime, timedelta
        
        # Create expired token
        payload = {
            'user_id': str(self.user.id),
            'email': self.user.email,
            'exp': datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            'iat': datetime.utcnow() - timedelta(hours=2),
        }
        
        expired_token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {expired_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('INVALID_TOKEN', response.content.decode())
    
    def test_jwt_authentication_missing_tenant_id(self):
        """Test JWT authentication without X-TENANT-ID header."""
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('MISSING_TENANT_ID', response.content.decode())
    
    def test_jwt_authentication_without_membership(self):
        """Test JWT authentication for user without tenant membership."""
        # Create another user without membership
        other_user = User.objects.create_user(
            email='notenantuser@example.com',
            password='pass123'
        )
        
        from apps.rbac.services import AuthService
        other_token = AuthService.generate_jwt(other_user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {other_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('FORBIDDEN', response.content.decode())
        self.assertIn('do not have access', response.content.decode())
    
    def test_jwt_authentication_with_pending_membership(self):
        """Test JWT authentication with pending membership."""
        # Create user with pending membership
        pending_user = User.objects.create_user(
            email='pendinguser@example.com',
            password='pass123'
        )
        
        TenantUser.objects.create(
            tenant=self.tenant,
            user=pending_user,
            invite_status='pending',
            is_active=True
        )
        
        from apps.rbac.services import AuthService
        pending_token = AuthService.generate_jwt(pending_user)
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {pending_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('FORBIDDEN', response.content.decode())
        self.assertIn('pending', response.content.decode())
    
    def test_jwt_authentication_inactive_user(self):
        """Test JWT authentication with inactive user."""
        # Deactivate user
        self.user.is_active = False
        self.user.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertIn('INVALID_TOKEN', response.content.decode())
    
    def test_jwt_vs_api_key_authentication(self):
        """Test that JWT authentication takes precedence over API key."""
        # Generate API key for tenant
        api_key = 'test-api-key-jwt-12345'
        api_key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        self.tenant.api_keys = [
            {
                'key_hash': api_key_hash,
                'name': 'Test Key',
                'created_at': timezone.now().isoformat(),
            }
        ]
        self.tenant.save()
        
        # Request with both JWT and API key
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=api_key,
        )
        
        response = self.middleware.process_request(request)
        
        # Should use JWT authentication
        self.assertIsNone(response)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.membership, self.membership)
    
    def test_api_key_fallback_when_no_jwt(self):
        """Test that API key authentication works when no JWT provided."""
        # Generate API key for tenant
        api_key = 'test-api-key-fallback-12345'
        api_key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        self.tenant.api_keys = [
            {
                'key_hash': api_key_hash,
                'name': 'Fallback Key',
                'created_at': timezone.now().isoformat(),
            }
        ]
        self.tenant.save()
        
        # Request with only API key
        request = self.factory.get(
            '/v1/products',
            HTTP_X_TENANT_ID=str(self.tenant.id),
            HTTP_X_TENANT_API_KEY=api_key,
        )
        
        response = self.middleware.process_request(request)
        
        # Should use API key authentication
        self.assertIsNone(response)
        self.assertIsNone(request.user)  # API key auth doesn't set user
        self.assertEqual(request.tenant, self.tenant)
        self.assertIsNone(request.membership)
        self.assertEqual(request.scopes, set())
    
    def test_jwt_authentication_updates_last_seen(self):
        """Test that JWT authentication updates last_seen_at."""
        old_timestamp = timezone.now() - timedelta(hours=2)
        self.membership.last_seen_at = old_timestamp
        self.membership.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        
        # Refresh membership from database
        self.membership.refresh_from_db()
        
        # Check that last_seen_at was updated
        self.assertIsNotNone(self.membership.last_seen_at)
        self.assertGreater(self.membership.last_seen_at, old_timestamp)
    
    def test_jwt_authentication_cross_tenant_blocked(self):
        """Test that JWT user cannot access tenant they're not a member of."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name='Other JWT Business',
            slug='other-jwt-business',
            status='active',
            subscription_tier=self.tier,
            whatsapp_number='+14155556666',
            twilio_sid='other_jwt_sid',
            twilio_token='other_jwt_token',
            webhook_secret='other_jwt_secret',
        )
        
        # Try to access other tenant with JWT
        request = self.factory.get(
            '/v1/products',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
            HTTP_X_TENANT_ID=str(other_tenant.id),
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertIn('FORBIDDEN', response.content.decode())
        self.assertIn('do not have access', response.content.decode())
    
    def test_jwt_public_path_bypass(self):
        """Test that JWT authentication is bypassed for public paths."""
        request = self.factory.get(
            '/v1/auth/login',
            HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}',
        )
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertIsNone(request.tenant)
        self.assertIsNone(request.membership)
        self.assertEqual(request.scopes, set())
