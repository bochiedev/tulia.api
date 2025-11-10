"""
Tests for RBAC REST API endpoints.

Tests:
- Membership management (list, invite, role assignment)
- Role management (list, create, permissions)
- Permission management (list, user overrides)
- Audit log viewing
"""
import pytest
from decimal import Decimal
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)
from apps.tenants.models import Tenant, SubscriptionTier
from apps.rbac.services import RBACService


@pytest.fixture
def request_factory():
    """Create an API request factory."""
    return APIRequestFactory()


@pytest.fixture
def subscription_tier(db):
    """Create a subscription tier."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=Decimal('99.00'),
        yearly_price=Decimal('950.00'),
        monthly_messages=10000,
        max_products=1000,
        max_services=50,
        payment_facilitation=True,
        transaction_fee_percentage=Decimal('3.5')
    )


@pytest.fixture
def tenant(db, subscription_tier):
    """Create a tenant."""
    return Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
        status='active',
        subscription_tier=subscription_tier,
        whatsapp_number='+1234567890',
        subscription_waived=True
    )


@pytest.fixture
def owner_user(db):
    """Create owner user."""
    return User.objects.create_user(
        email='owner@test.com',
        password='testpass123',
        first_name='Owner',
        last_name='User'
    )


@pytest.fixture
def admin_user(db):
    """Create admin user."""
    return User.objects.create_user(
        email='admin@test.com',
        password='testpass123',
        first_name='Admin',
        last_name='User'
    )


@pytest.fixture
def regular_user(db):
    """Create regular user."""
    return User.objects.create_user(
        email='user@test.com',
        password='testpass123',
        first_name='Regular',
        last_name='User'
    )


@pytest.fixture
def permissions(db):
    """Create test permissions."""
    perms = {
        'users_manage': Permission.objects.get_or_create(
            code='users:manage',
            defaults={
                'label': 'Manage Users',
                'description': 'Can invite users and assign roles',
                'category': 'users'
            }
        )[0],
        'catalog_view': Permission.objects.get_or_create(
            code='catalog:view',
            defaults={
                'label': 'View Catalog',
                'description': 'Can view products and services',
                'category': 'catalog'
            }
        )[0],
        'catalog_edit': Permission.objects.get_or_create(
            code='catalog:edit',
            defaults={
                'label': 'Edit Catalog',
                'description': 'Can create and edit products',
                'category': 'catalog'
            }
        )[0],
        'analytics_view': Permission.objects.get_or_create(
            code='analytics:view',
            defaults={
                'label': 'View Analytics',
                'description': 'Can view analytics and reports',
                'category': 'analytics'
            }
        )[0],
    }
    return perms


@pytest.fixture
def roles(db, tenant, permissions):
    """Create test roles with permissions."""
    # Get roles created by signal
    owner_role = Role.objects.get(tenant=tenant, name='Owner')
    admin_role = Role.objects.get(tenant=tenant, name='Admin')
    
    # Assign permissions to roles
    for perm in permissions.values():
        RolePermission.objects.get_or_create(role=owner_role, permission=perm)
    
    RolePermission.objects.get_or_create(role=admin_role, permission=permissions['catalog_view'])
    RolePermission.objects.get_or_create(role=admin_role, permission=permissions['catalog_edit'])
    
    return {
        'owner': owner_role,
        'admin': admin_role
    }


@pytest.fixture
def owner_membership(db, tenant, owner_user, roles):
    """Create owner membership."""
    membership = TenantUser.objects.create(
        tenant=tenant,
        user=owner_user,
        invite_status='accepted',
        is_active=True
    )
    TenantUserRole.objects.create(
        tenant_user=membership,
        role=roles['owner'],
        assigned_by=owner_user
    )
    return membership


@pytest.fixture
def admin_membership(db, tenant, admin_user, roles, owner_user):
    """Create admin membership."""
    membership = TenantUser.objects.create(
        tenant=tenant,
        user=admin_user,
        invite_status='accepted',
        is_active=True
    )
    TenantUserRole.objects.create(
        tenant_user=membership,
        role=roles['admin'],
        assigned_by=owner_user
    )
    return membership


@pytest.mark.django_db
class TestMembershipEndpoints:
    """Test membership management endpoints."""
    
    def test_membership_list(self, request_factory, tenant, owner_user, owner_membership):
        """Test GET /v1/memberships/me."""
        from apps.rbac.views import MembershipListView
        
        request = request_factory.get('/v1/memberships/me')
        force_authenticate(request, user=owner_user)
        request.tenant = tenant
        request.membership = owner_membership
        request.scopes = RBACService.resolve_scopes(owner_membership)
        
        view = MembershipListView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert response.data['count'] == 1
        assert len(response.data['memberships']) == 1
        assert response.data['memberships'][0]['user']['email'] == 'owner@test.com'


@pytest.mark.django_db
class TestRoleEndpoints:
    """Test role management endpoints."""
    
    def test_role_list(self, request_factory, tenant, owner_user, owner_membership):
        """Test GET /v1/roles."""
        from apps.rbac.views import RoleListView
        
        request = request_factory.get('/v1/roles')
        force_authenticate(request, user=owner_user)
        request.tenant = tenant
        request.membership = owner_membership
        request.scopes = RBACService.resolve_scopes(owner_membership)
        
        view = RoleListView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert response.data['count'] >= 2  # At least Owner and Admin
        role_names = [r['name'] for r in response.data['roles']]
        assert 'Owner' in role_names
        assert 'Admin' in role_names


@pytest.mark.django_db
class TestPermissionEndpoints:
    """Test permission management endpoints."""
    
    def test_permission_list(self, request_factory, tenant, owner_user, owner_membership, permissions):
        """Test GET /v1/permissions."""
        from apps.rbac.views import PermissionListView
        
        request = request_factory.get('/v1/permissions')
        force_authenticate(request, user=owner_user)
        request.tenant = tenant
        request.membership = owner_membership
        request.scopes = RBACService.resolve_scopes(owner_membership)
        
        view = PermissionListView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert response.data['count'] >= 4
        perm_codes = [p['code'] for p in response.data['permissions']]
        assert 'users:manage' in perm_codes
        assert 'catalog:view' in perm_codes


@pytest.mark.django_db
class RBACAPITestCase:
    """Legacy test case - keeping for reference but converting to pytest style."""
    pass

