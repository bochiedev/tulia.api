"""
Unit tests for RBAC models.

Tests core functionality of User, TenantUser, Permission, Role,
RolePermission, UserPermission, and AuditLog models.
"""
import pytest
from django.utils import timezone
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)
from apps.tenants.models import Tenant, SubscriptionTier


@pytest.mark.django_db
class TestUserModel:
    """Test User model functionality."""
    
    def test_create_user(self):
        """Test creating a user with hashed password."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        assert user.email == 'test@example.com'
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.password_hash != 'testpass123'  # Should be hashed
        assert user.check_password('testpass123') is True
        assert user.check_password('wrongpass') is False
    
    def test_user_str(self):
        """Test user string representation."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        assert str(user) == 'test@example.com'
    
    def test_get_full_name(self):
        """Test get_full_name method."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        assert user.get_full_name() == 'John Doe'
        
        # Test with no name
        user2 = User.objects.create_user(
            email='test2@example.com',
            password='testpass123'
        )
        assert user2.get_full_name() == 'test2@example.com'
    
    def test_update_last_login(self):
        """Test updating last login timestamp."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        assert user.last_login_at is None
        user.update_last_login()
        assert user.last_login_at is not None


@pytest.mark.django_db
class TestTenantUserModel:
    """Test TenantUser model functionality."""
    
    def test_create_tenant_user(self, tenant, user):
        """Test creating a tenant user membership."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='pending'
        )
        
        assert tenant_user.tenant == tenant
        assert tenant_user.user == user
        assert tenant_user.is_active is True
        assert tenant_user.invite_status == 'pending'
        assert tenant_user.joined_at is None
    
    def test_accept_invitation(self, tenant, user):
        """Test accepting an invitation."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='pending'
        )
        
        tenant_user.accept_invitation()
        assert tenant_user.invite_status == 'accepted'
        assert tenant_user.joined_at is not None
    
    def test_revoke_invitation(self, tenant, user):
        """Test revoking an invitation."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='pending'
        )
        
        tenant_user.revoke_invitation()
        assert tenant_user.invite_status == 'revoked'
        assert tenant_user.is_active is False
    
    def test_update_last_seen(self, tenant, user):
        """Test updating last seen timestamp."""
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user
        )
        
        assert tenant_user.last_seen_at is None
        tenant_user.update_last_seen()
        assert tenant_user.last_seen_at is not None


@pytest.mark.django_db
class TestPermissionModel:
    """Test Permission model functionality."""
    
    def test_create_permission(self):
        """Test creating a permission."""
        permission = Permission.objects.create(
            code='catalog:view',
            label='View Catalog',
            description='Allows viewing product catalog',
            category='catalog'
        )
        
        assert permission.code == 'catalog:view'
        assert permission.label == 'View Catalog'
        assert permission.category == 'catalog'
    
    def test_permission_unique_code(self):
        """Test that permission codes must be unique."""
        Permission.objects.create(
            code='catalog:view',
            label='View Catalog',
            category='catalog'
        )
        
        with pytest.raises(Exception):  # IntegrityError
            Permission.objects.create(
                code='catalog:view',
                label='View Catalog 2',
                category='catalog'
            )
    
    def test_get_or_create_permission(self):
        """Test idempotent permission creation."""
        perm1, created1 = Permission.objects.get_or_create_permission(
            code='catalog:view',
            label='View Catalog',
            category='catalog'
        )
        assert created1 is True
        
        perm2, created2 = Permission.objects.get_or_create_permission(
            code='catalog:view',
            label='View Catalog',
            category='catalog'
        )
        assert created2 is False
        assert perm1.id == perm2.id


@pytest.mark.django_db
class TestRoleModel:
    """Test Role model functionality."""
    
    def test_create_role(self, tenant):
        """Test creating a role."""
        role = Role.objects.create(
            tenant=tenant,
            name='Owner',
            description='Full access to all features',
            is_system=True
        )
        
        assert role.tenant == tenant
        assert role.name == 'Owner'
        assert role.is_system is True
    
    def test_role_unique_per_tenant(self, tenant):
        """Test that role names must be unique per tenant."""
        Role.objects.create(
            tenant=tenant,
            name='Owner'
        )
        
        with pytest.raises(Exception):  # IntegrityError
            Role.objects.create(
                tenant=tenant,
                name='Owner'
            )
    
    def test_get_or_create_role(self, tenant):
        """Test idempotent role creation."""
        role1, created1 = Role.objects.get_or_create_role(
            tenant=tenant,
            name='Owner',
            description='Full access',
            is_system=True
        )
        assert created1 is True
        
        role2, created2 = Role.objects.get_or_create_role(
            tenant=tenant,
            name='Owner',
            description='Full access',
            is_system=True
        )
        assert created2 is False
        assert role1.id == role2.id


@pytest.mark.django_db
class TestRolePermissionModel:
    """Test RolePermission model functionality."""
    
    def test_grant_permission_to_role(self, tenant):
        """Test granting a permission to a role."""
        role = Role.objects.create(tenant=tenant, name='Owner')
        permission = Permission.objects.create(
            code='catalog:view',
            label='View Catalog',
            category='catalog'
        )
        
        role_perm, created = RolePermission.objects.grant_permission(role, permission)
        assert created is True
        assert role_perm.role == role
        assert role_perm.permission == permission
    
    def test_role_has_permission(self, tenant):
        """Test checking if role has a permission."""
        role = Role.objects.create(tenant=tenant, name='Owner')
        permission = Permission.objects.create(
            code='catalog:view',
            label='View Catalog',
            category='catalog'
        )
        
        assert role.has_permission('catalog:view') is False
        
        RolePermission.objects.grant_permission(role, permission)
        assert role.has_permission('catalog:view') is True
    
    def test_get_role_permissions(self, tenant):
        """Test getting all permissions for a role."""
        role = Role.objects.create(tenant=tenant, name='Owner')
        perm1 = Permission.objects.create(code='catalog:view', label='View', category='catalog')
        perm2 = Permission.objects.create(code='catalog:edit', label='Edit', category='catalog')
        
        RolePermission.objects.grant_permission(role, perm1)
        RolePermission.objects.grant_permission(role, perm2)
        
        permissions = role.get_permissions()
        assert permissions.count() == 2
        assert perm1 in permissions
        assert perm2 in permissions


@pytest.mark.django_db
class TestUserPermissionModel:
    """Test UserPermission model functionality."""
    
    def test_grant_permission_to_user(self, tenant, user):
        """Test granting a permission to a user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        permission = Permission.objects.create(
            code='catalog:view',
            label='View Catalog',
            category='catalog'
        )
        
        user_perm, created = UserPermission.objects.grant_permission(
            tenant_user, permission, reason='Special access'
        )
        assert created is True
        assert user_perm.granted is True
        assert user_perm.reason == 'Special access'
    
    def test_deny_permission_to_user(self, tenant, user):
        """Test denying a permission to a user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        permission = Permission.objects.create(
            code='catalog:edit',
            label='Edit Catalog',
            category='catalog'
        )
        
        user_perm, created = UserPermission.objects.deny_permission(
            tenant_user, permission, reason='Temporary restriction'
        )
        assert created is True
        assert user_perm.granted is False
        assert user_perm.reason == 'Temporary restriction'


@pytest.mark.django_db
class TestAuditLogModel:
    """Test AuditLog model functionality."""
    
    def test_create_audit_log(self, tenant, user):
        """Test creating an audit log entry."""
        log = AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action='role_assigned',
            target_type='Role',
            target_id='12345678-1234-1234-1234-123456789012',
            diff={'role': 'Owner'},
            metadata={'reason': 'Initial setup'}
        )
        
        assert log.tenant == tenant
        assert log.user == user
        assert log.action == 'role_assigned'
        assert log.target_type == 'Role'
    
    def test_log_action_convenience_method(self, tenant, user):
        """Test the log_action convenience method."""
        log = AuditLog.log_action(
            action='permission_granted',
            user=user,
            tenant=tenant,
            target_type='Permission',
            diff={'permission': 'catalog:view'},
            metadata={'reason': 'Test'}
        )
        
        assert log.action == 'permission_granted'
        assert log.user == user
        assert log.tenant == tenant


# Fixtures
@pytest.fixture
def subscription_tier():
    """Create a subscription tier for testing."""
    return SubscriptionTier.objects.create(
        name='Starter',
        monthly_price=29.00,
        yearly_price=278.00,
        monthly_messages=1000,
        max_products=100,
        max_services=10
    )


@pytest.fixture
def tenant(subscription_tier):
    """Create a tenant for testing."""
    return Tenant.objects.create(
        name='Test Business',
        slug='test-business',
        whatsapp_number='+14155551234',
        twilio_sid='test_sid',
        twilio_token='test_token',
        webhook_secret='test_secret',
        subscription_tier=subscription_tier
    )


@pytest.fixture
def user():
    """Create a user for testing."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123'
    )
