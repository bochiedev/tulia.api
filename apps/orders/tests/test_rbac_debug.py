"""
Debug test to verify RBAC scope resolution.
"""
import pytest
import hashlib
from decimal import Decimal
from django.utils import timezone

from apps.tenants.models import Tenant, SubscriptionTier
from apps.rbac.models import User, TenantUser, Permission, Role, RolePermission, TenantUserRole
from apps.rbac.services import RBACService


@pytest.fixture
def subscription_tier(db):
    """Create a subscription tier."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=Decimal('99.00'),
        yearly_price=Decimal('950.00'),
        max_products=1000
    )


@pytest.fixture
def tenant(db, subscription_tier):
    """Create a tenant with valid API key."""
    test_api_key = 'test-key'
    api_key_hash = hashlib.sha256(test_api_key.encode('utf-8')).hexdigest()
    
    return Tenant.objects.create(
        name='Test Business',
        slug='test-business',
        whatsapp_number='+1234567890',
        twilio_sid='test_sid',
        twilio_token='test_token',
        webhook_secret='test_secret',
        subscription_tier=subscription_tier,
        status='active',
        subscription_waived=True,
        api_keys=[{
            'key_hash': api_key_hash,
            'name': 'Test Key',
            'created_at': timezone.now().isoformat()
        }]
    )


@pytest.fixture
def user(db):
    """Create a user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def orders_view_permission(db):
    """Create orders:view permission."""
    return Permission.objects.get_or_create(
        code='orders:view',
        defaults={
            'label': 'View Orders',
            'description': 'View orders',
            'category': 'orders'
        }
    )[0]


@pytest.fixture
def viewer_membership(db, tenant, user, orders_view_permission):
    """Create a tenant membership with orders:view permission."""
    membership = TenantUser.objects.create(
        tenant=tenant,
        user=user,
        invite_status='accepted',
        joined_at=timezone.now()
    )
    
    role = Role.objects.create(
        tenant=tenant,
        name='Viewer',
        description='Can view orders'
    )
    RolePermission.objects.create(role=role, permission=orders_view_permission)
    TenantUserRole.objects.create(tenant_user=membership, role=role)
    
    return membership


@pytest.mark.django_db
class TestRBACDebug:
    """Debug RBAC scope resolution."""
    
    def test_scope_resolution(self, tenant, user, viewer_membership, orders_view_permission):
        """Test that scopes are resolved correctly."""
        # Verify the data is set up correctly
        assert viewer_membership.tenant == tenant
        assert viewer_membership.user == user
        assert viewer_membership.invite_status == 'accepted'
        
        # Check role assignment
        user_roles = TenantUserRole.objects.filter(tenant_user=viewer_membership)
        print(f"\nUser roles count: {user_roles.count()}")
        for ur in user_roles:
            print(f"  - Role: {ur.role.name}")
        
        # Check role permissions
        for ur in user_roles:
            role_perms = RolePermission.objects.filter(role=ur.role)
            print(f"\nRole '{ur.role.name}' permissions count: {role_perms.count()}")
            for rp in role_perms:
                print(f"  - Permission: {rp.permission.code}")
        
        # Test the query used in resolve_scopes
        role_permissions = Permission.objects.filter(
            role_permissions__role__user_roles__tenant_user=viewer_membership
        ).distinct().values_list('code', flat=True)
        
        print(f"\nQuery result: {list(role_permissions)}")
        
        # Now test RBACService.resolve_scopes
        scopes = RBACService.resolve_scopes(viewer_membership)
        print(f"\nResolved scopes: {scopes}")
        
        assert 'orders:view' in scopes, f"Expected 'orders:view' in scopes, got: {scopes}"
