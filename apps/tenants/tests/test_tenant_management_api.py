"""
Tests for Tenant Management API endpoints.

Tests:
- List user's tenants
- Create new tenant
- Get tenant details
- Update tenant info
- Delete tenant
- Manage tenant members
"""
import pytest
from rest_framework.test import APIClient
from django.urls import reverse

from apps.tenants.models import Tenant
from apps.tenants.services import TenantService
from apps.rbac.models import User, TenantUser, Role, Permission
from apps.rbac.services import RBACService


@pytest.mark.django_db
class TestTenantManagementAPI:
    """Test tenant management API endpoints."""
    
    @pytest.fixture(autouse=True)
    def seed_permissions(self):
        """Seed canonical permissions for testing."""
        permissions_data = [
            ('catalog:view', 'View Catalog', 'catalog'),
            ('catalog:edit', 'Edit Catalog', 'catalog'),
            ('users:manage', 'Manage Users', 'users'),
            ('integrations:manage', 'Manage Integrations', 'integrations'),
            ('finance:view', 'View Finance', 'finance'),
        ]
        
        for code, label, category in permissions_data:
            Permission.objects.get_or_create_permission(
                code=code,
                label=label,
                category=category
            )
    
    @pytest.fixture
    def client(self):
        """Create API client."""
        return APIClient()
    
    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            email='owner@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Owner',
            email_verified=True
        )
    
    @pytest.fixture
    def other_user(self):
        """Create another test user."""
        return User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            first_name='Other',
            last_name='User',
            email_verified=True
        )
    
    @pytest.fixture
    def tenant(self, user):
        """Create a test tenant with owner."""
        return TenantService.create_tenant(
            user=user,
            name='Test Business',
            whatsapp_number='+1234567890'
        )
    
    @pytest.fixture
    def second_tenant(self, user):
        """Create a second test tenant."""
        return TenantService.create_tenant(
            user=user,
            name='Second Business',
            whatsapp_number='+9876543210'
        )
    
    def _get_jwt_token(self, user):
        """Helper to generate JWT token for user."""
        from apps.rbac.services import AuthService
        return AuthService.generate_jwt(user)
    
    def test_list_tenants_success(self, client, user, tenant, second_tenant):
        """Test listing user's tenants."""
        token = self._get_jwt_token(user)
        
        # Make request with JWT token
        response = client.get(
            '/v1/tenants',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        # Verify response
        assert response.status_code == 200
        assert len(response.data) == 2
        
        # Verify tenant data
        tenant_names = [t['name'] for t in response.data]
        assert 'Test Business' in tenant_names
        assert 'Second Business' in tenant_names
        
        # Verify role is included
        for tenant_data in response.data:
            assert tenant_data['role'] == 'Owner'
            assert 'onboarding_status' in tenant_data
    
    def test_list_tenants_unauthenticated(self, client):
        """Test listing tenants without authentication."""
        response = client.get('/v1/tenants')
        assert response.status_code == 401
    
    def test_create_tenant_success(self, client, user):
        """Test creating a new tenant."""
        token = self._get_jwt_token(user)
        
        # Make request
        data = {
            'name': 'New Business',
            'slug': 'new-business',
            'whatsapp_number': '+1111111111'
        }
        response = client.post(
            '/v1/tenants/create',
            data,
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.data['name'] == 'New Business'
        assert response.data['slug'] == 'new-business'
        assert response.data['status'] == 'trial'
        assert response.data['role'] == 'Owner'
        
        # Verify tenant created in database
        tenant = Tenant.objects.get(slug='new-business')
        assert tenant.name == 'New Business'
        
        # Verify user is Owner
        tenant_user = TenantUser.objects.get_membership(tenant, user)
        assert tenant_user is not None
        assert tenant_user.invite_status == 'accepted'
    
    def test_create_tenant_auto_slug(self, client, user):
        """Test creating tenant with auto-generated slug."""
        token = self._get_jwt_token(user)
        
        # Make request without slug
        data = {
            'name': 'Auto Slug Business'
        }
        response = client.post(
            '/v1/tenants/create',
            data,
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.data['slug'] == 'auto-slug-business'
    
    def test_create_tenant_duplicate_slug(self, client, user, tenant):
        """Test creating tenant with duplicate slug."""
        token = self._get_jwt_token(user)
        
        # Make request with existing slug
        data = {
            'name': 'Duplicate',
            'slug': tenant.slug
        }
        response = client.post(
            '/v1/tenants/create',
            data,
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        # Verify error
        assert response.status_code == 400
        assert 'slug' in response.data['details']
    
    def test_get_tenant_detail_success(self, client, user, tenant):
        """Test getting tenant details."""
        token = self._get_jwt_token(user)
        
        # Make request
        response = client.get(
            f'/v1/tenants/{tenant.id}',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.data['id'] == str(tenant.id)
        assert response.data['name'] == tenant.name
        assert response.data['role'] == 'Owner'
        assert 'roles' in response.data
        assert 'onboarding_status' in response.data
    
    def test_get_tenant_detail_no_access(self, client, user, other_user):
        """Test getting tenant details without access."""
        # Create tenant for other user
        other_tenant = TenantService.create_tenant(
            user=other_user,
            name='Other Business',
            whatsapp_number='+9999999999'
        )
        
        token = self._get_jwt_token(user)
        
        # Make request
        response = client.get(
            f'/v1/tenants/{other_tenant.id}',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        # Verify forbidden
        assert response.status_code == 403
    
    def test_update_tenant_success(self, client, user, tenant):
        """Test updating tenant information."""
        # Authenticate
        client.force_authenticate(user=user)
        
        # Get tenant user for headers
        tenant_user = TenantUser.objects.get_membership(tenant, user)
        
        # Make request with tenant context
        data = {
            'name': 'Updated Business Name',
            'contact_email': 'contact@updated.com',
            'timezone': 'America/New_York'
        }
        response = client.put(
            f'/v1/tenants/{tenant.id}/update',
            data,
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.data['name'] == 'Updated Business Name'
        assert response.data['contact_email'] == 'contact@updated.com'
        assert response.data['timezone'] == 'America/New_York'
        
        # Verify database updated
        tenant.refresh_from_db()
        assert tenant.name == 'Updated Business Name'
        assert tenant.contact_email == 'contact@updated.com'
    
    def test_update_tenant_without_scope(self, client, user, tenant, other_user):
        """Test updating tenant without users:manage scope."""
        # Invite other user without users:manage scope
        TenantService.invite_user(
            tenant=tenant,
            email=other_user.email,
            role_names=['Analyst'],  # Analyst doesn't have users:manage
            invited_by=user
        )
        
        # Accept invitation
        tenant_user = TenantUser.objects.get_membership(tenant, other_user)
        tenant_user.accept_invitation()
        
        # Authenticate as other user
        client.force_authenticate(user=other_user)
        
        # Make request
        data = {'name': 'Should Fail'}
        response = client.put(
            f'/v1/tenants/{tenant.id}/update',
            data,
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Verify forbidden
        assert response.status_code == 403
    
    def test_delete_tenant_success(self, client, user, tenant):
        """Test deleting tenant."""
        # Authenticate
        client.force_authenticate(user=user)
        
        # Make request
        response = client.delete(
            f'/v1/tenants/{tenant.id}/delete',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Verify response
        assert response.status_code == 204
        
        # Verify tenant soft deleted
        tenant.refresh_from_db()
        assert tenant.deleted_at is not None
        assert tenant.status == 'canceled'
    
    def test_list_members_success(self, client, user, tenant, other_user):
        """Test listing tenant members."""
        # Invite other user
        TenantService.invite_user(
            tenant=tenant,
            email=other_user.email,
            role_names=['Admin'],
            invited_by=user
        )
        
        # Authenticate
        client.force_authenticate(user=user)
        
        # Make request
        response = client.get(f'/v1/tenants/{tenant.id}/members')
        
        # Verify response
        assert response.status_code == 200
        assert len(response.data) == 2  # Owner + invited user
        
        # Verify member data
        emails = [m['email'] for m in response.data]
        assert user.email in emails
        assert other_user.email in emails
    
    def test_invite_member_success(self, client, user, tenant):
        """Test inviting a member to tenant."""
        # Authenticate
        client.force_authenticate(user=user)
        
        # Make request
        data = {
            'email': 'newmember@example.com',
            'roles': ['Admin', 'Catalog Manager']
        }
        response = client.post(
            f'/v1/tenants/{tenant.id}/members/invite',
            data,
            format='json',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Verify response
        assert response.status_code == 201
        assert response.data['email'] == 'newmember@example.com'
        assert 'Admin' in response.data['roles']
        assert 'Catalog Manager' in response.data['roles']
    
    def test_remove_member_success(self, client, user, tenant, other_user):
        """Test removing a member from tenant."""
        # Invite other user
        TenantService.invite_user(
            tenant=tenant,
            email=other_user.email,
            role_names=['Admin'],
            invited_by=user
        )
        
        # Authenticate
        client.force_authenticate(user=user)
        
        # Make request
        response = client.delete(
            f'/v1/tenants/{tenant.id}/members/{other_user.id}',
            HTTP_X_TENANT_ID=str(tenant.id)
        )
        
        # Verify response
        assert response.status_code == 204
        
        # Verify membership deactivated
        tenant_user = TenantUser.objects.filter(
            tenant=tenant,
            user=other_user
        ).first()
        assert tenant_user.is_active is False
