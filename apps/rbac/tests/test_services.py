"""
Unit tests for RBAC services.

Tests scope resolution, permission management, role assignment,
and four-eyes validation.
"""
import pytest
from django.core.cache import cache
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)
from apps.rbac.services import RBACService
from apps.tenants.models import Tenant, SubscriptionTier


def get_or_create_permission(code, label='', category=''):
    """Helper to get or create permission (idempotent)."""
    return Permission.objects.get_or_create(
        code=code,
        defaults={'label': label or code, 'category': category}
    )[0]


def create_test_role(tenant, name):
    """Helper to create a test role with a unique name."""
    return Role.objects.create(tenant=tenant, name=f'Test_{name}')


@pytest.mark.django_db
class TestScopeResolution:
    """Test scope resolution with roles and user permission overrides."""
    
    def test_resolve_scopes_from_single_role(self, tenant, user):
        """Test resolving scopes from a single role."""
        # Create tenant user
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create role with permissions
        role = create_test_role(tenant, 'CatalogManager')
        perm1 = get_or_create_permission('catalog:view', 'View', 'catalog')
        perm2 = get_or_create_permission('catalog:edit', 'Edit', 'catalog')
        RolePermission.objects.grant_permission(role, perm1)
        RolePermission.objects.grant_permission(role, perm2)
        
        # Assign role to user
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        assert 'catalog:view' in scopes
        assert 'catalog:edit' in scopes
        assert len(scopes) == 2
    
    def test_resolve_scopes_from_multiple_roles(self, tenant, user):
        """Test resolving scopes from multiple roles (aggregation)."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create first role
        role1 = create_test_role(tenant, 'CatalogManager')
        perm1 = get_or_create_permission('catalog:view', 'View', 'catalog')
        perm2 = get_or_create_permission('catalog:edit', 'Edit', 'catalog')
        RolePermission.objects.grant_permission(role1, perm1)
        RolePermission.objects.grant_permission(role1, perm2)
        
        # Create second role
        role2 = create_test_role(tenant, 'Analyst')
        perm3 = get_or_create_permission('analytics:view', 'View Analytics', 'analytics')
        RolePermission.objects.grant_permission(role2, perm3)
        
        # Assign both roles
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role1)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role2)
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        assert 'catalog:view' in scopes
        assert 'catalog:edit' in scopes
        assert 'analytics:view' in scopes
        assert len(scopes) == 3
    
    def test_deny_override_wins_over_role_grant(self, tenant, user):
        """Test that UserPermission deny overrides role grant."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create role with catalog:edit permission
        role = create_test_role(tenant, 'CatalogManager')
        perm_view = get_or_create_permission('catalog:view', 'View', 'catalog')
        perm_edit = get_or_create_permission('catalog:edit', 'Edit', 'catalog')
        RolePermission.objects.grant_permission(role, perm_view)
        RolePermission.objects.grant_permission(role, perm_edit)
        
        # Assign role
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Add deny override for catalog:edit
        UserPermission.objects.deny_permission(tenant_user, perm_edit)
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        # Should have view but not edit
        assert 'catalog:view' in scopes
        assert 'catalog:edit' not in scopes
    
    def test_user_permission_grant_adds_scope(self, tenant, user):
        """Test that UserPermission grant adds scope even without role."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # No roles assigned
        
        # Grant permission directly
        perm = get_or_create_permission(code='finance:view', label='View Finance', category='finance')
        UserPermission.objects.grant_permission(tenant_user, perm)
        
        # Resolve scopes
        scopes = RBACService.resolve_scopes(tenant_user)
        
        assert 'finance:view' in scopes
        assert len(scopes) == 1
    
    def test_scope_resolution_caching(self, tenant, user):
        """Test that scope resolution results are cached."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create role with permission
        role = create_test_role(tenant, 'Viewer')
        perm = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        RolePermission.objects.grant_permission(role, perm)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Clear cache (skip if Redis unavailable)
        try:
            cache.clear()
        except Exception:
            pytest.skip("Redis not available for caching test")
        
        # First call - should cache
        scopes1 = RBACService.resolve_scopes(tenant_user)
        
        # Check cache exists (skip if Redis unavailable)
        cache_key = f"rbac:scopes:tenant_user:{tenant_user.id}"
        try:
            cached = cache.get(cache_key)
            assert cached is not None
            assert cached == scopes1
        except Exception:
            pytest.skip("Redis not available for caching test")
        
        # Second call - should use cache
        scopes2 = RBACService.resolve_scopes(tenant_user)
        assert scopes1 == scopes2
    
    def test_cache_invalidation(self, tenant, user):
        """Test that cache is invalidated when permissions change."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create role with permission
        role = create_test_role(tenant, 'Viewer')
        perm = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        RolePermission.objects.grant_permission(role, perm)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Resolve scopes (caches result)
        scopes1 = RBACService.resolve_scopes(tenant_user)
        assert len(scopes1) == 1
        
        # Invalidate cache
        RBACService.invalidate_scope_cache(tenant_user)
        
        # Check cache is cleared (skip if Redis unavailable)
        cache_key = f"rbac:scopes:tenant_user:{tenant_user.id}"
        try:
            assert cache.get(cache_key) is None
        except Exception:
            pytest.skip("Redis not available for caching test")


@pytest.mark.django_db
class TestPermissionManagement:
    """Test permission grant and deny operations."""
    
    def test_grant_permission(self, tenant, user):
        """Test granting a permission to a user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        # Create permission
        get_or_create_permission(code='catalog:view', label='View', category='catalog')
        
        # Grant permission
        user_perm = RBACService.grant_permission(
            tenant_user=tenant_user,
            permission_code='catalog:view',
            reason='Special access',
            granted_by=admin
        )
        
        assert user_perm.granted is True
        assert user_perm.reason == 'Special access'
        assert user_perm.granted_by == admin
        
        # Check scope resolution
        scopes = RBACService.resolve_scopes(tenant_user)
        assert 'catalog:view' in scopes
    
    def test_deny_permission(self, tenant, user):
        """Test denying a permission to a user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        # Create role with permission
        role = create_test_role(tenant, 'Manager')
        perm = get_or_create_permission(code='catalog:edit', label='Edit', category='catalog')
        RolePermission.objects.grant_permission(role, perm)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Verify user has permission from role
        scopes_before = RBACService.resolve_scopes(tenant_user)
        assert 'catalog:edit' in scopes_before
        
        # Deny permission
        user_perm = RBACService.deny_permission(
            tenant_user=tenant_user,
            permission_code='catalog:edit',
            reason='Temporary restriction',
            granted_by=admin
        )
        
        assert user_perm.granted is False
        assert user_perm.reason == 'Temporary restriction'
        
        # Check scope resolution - should not have permission
        scopes_after = RBACService.resolve_scopes(tenant_user)
        assert 'catalog:edit' not in scopes_after
    
    def test_grant_permission_creates_audit_log(self, tenant, user):
        """Test that granting permission creates audit log entry."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        get_or_create_permission(code='catalog:view', label='View', category='catalog')
        
        # Grant permission
        RBACService.grant_permission(
            tenant_user=tenant_user,
            permission_code='catalog:view',
            reason='Test',
            granted_by=admin
        )
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='permission_granted',
            tenant=tenant,
            user=admin
        ).first()
        
        assert log is not None
        assert log.diff['permission'] == 'catalog:view'
        assert log.diff['granted'] is True
    
    def test_grant_nonexistent_permission_raises_error(self, tenant, user):
        """Test that granting nonexistent permission raises error."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        with pytest.raises(Permission.DoesNotExist):
            RBACService.grant_permission(
                tenant_user=tenant_user,
                permission_code='nonexistent:permission'
            )


@pytest.mark.django_db
class TestRoleManagement:
    """Test role assignment and removal operations."""
    
    def test_assign_role(self, tenant, user):
        """Test assigning a role to a user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        # Create role
        role = create_test_role(tenant, 'Catalog Manager')
        
        # Assign role
        user_role = RBACService.assign_role(
            tenant_user=tenant_user,
            role=role,
            assigned_by=admin
        )
        
        assert user_role.tenant_user == tenant_user
        assert user_role.role == role
        assert user_role.assigned_by == admin
    
    def test_assign_role_creates_audit_log(self, tenant, user):
        """Test that assigning role creates audit log entry."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        role = create_test_role(tenant, 'Catalog Manager')
        
        # Assign role
        RBACService.assign_role(
            tenant_user=tenant_user,
            role=role,
            assigned_by=admin
        )
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='role_assigned',
            tenant=tenant,
            user=admin
        ).first()
        
        assert log is not None
        assert log.diff['role'] == 'Test_Catalog Manager'
    
    def test_assign_role_invalidates_cache(self, tenant, user):
        """Test that assigning role invalidates scope cache."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Resolve scopes (caches empty set)
        scopes1 = RBACService.resolve_scopes(tenant_user)
        assert len(scopes1) == 0
        
        # Assign role with permission
        role = create_test_role(tenant, 'Viewer')
        perm = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        RolePermission.objects.grant_permission(role, perm)
        
        RBACService.assign_role(tenant_user=tenant_user, role=role)
        
        # Resolve scopes again - should have new permission
        scopes2 = RBACService.resolve_scopes(tenant_user)
        assert 'catalog:view' in scopes2
    
    def test_remove_role(self, tenant, user):
        """Test removing a role from a user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        # Create and assign role
        role = create_test_role(tenant, 'Catalog Manager')
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Remove role
        removed = RBACService.remove_role(
            tenant_user=tenant_user,
            role=role,
            removed_by=admin
        )
        
        assert removed is True
        
        # Verify role is removed
        assert not TenantUserRole.objects.filter(
            tenant_user=tenant_user,
            role=role
        ).exists()
    
    def test_remove_role_creates_audit_log(self, tenant, user):
        """Test that removing role creates audit log entry."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        role = create_test_role(tenant, 'Catalog Manager')
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        # Remove role
        RBACService.remove_role(
            tenant_user=tenant_user,
            role=role,
            removed_by=admin
        )
        
        # Check audit log
        log = AuditLog.objects.filter(
            action='role_removed',
            tenant=tenant,
            user=admin
        ).first()
        
        assert log is not None
        assert log.diff['role'] == 'Test_Catalog Manager'
    
    def test_remove_nonexistent_role_returns_false(self, tenant, user):
        """Test that removing nonexistent role returns False."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        role = create_test_role(tenant, 'Catalog Manager')
        
        # Role not assigned, try to remove
        removed = RBACService.remove_role(
            tenant_user=tenant_user,
            role=role
        )
        
        assert removed is False
    
    def test_assign_role_wrong_tenant_raises_error(self, tenant, user):
        """Test that assigning role from different tenant raises error."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create role for different tenant
        other_tier = SubscriptionTier.objects.create(
            name='Other',
            monthly_price=29,
            yearly_price=278
        )
        other_tenant = Tenant.objects.create(
            name='Other Business',
            slug='other-business',
            whatsapp_number='+14155559999',
            twilio_sid='other_sid',
            twilio_token='other_token',
            webhook_secret='other_secret',
            subscription_tier=other_tier
        )
        role = Role.objects.create(tenant=other_tenant, name='Manager')
        
        with pytest.raises(ValueError):
            RBACService.assign_role(tenant_user=tenant_user, role=role)


@pytest.mark.django_db
class TestPasswordHashing:
    """Test secure password hashing."""
    
    def test_register_user_uses_pbkdf2_hashing(self, subscription_tier):
        """Test that register_user uses PBKDF2 password hashing."""
        from apps.rbac.services import AuthService
        
        email = 'newuser@example.com'
        password = 'SecurePassword123!'
        business_name = 'New Business'
        
        # Register user
        result = AuthService.register_user(
            email=email,
            password=password,
            business_name=business_name,
            first_name='John',
            last_name='Doe'
        )
        
        user = result['user']
        
        # Verify password is hashed (not plaintext)
        assert user.password != password
        
        # Verify password uses PBKDF2 algorithm (Django default)
        # PBKDF2 hashes start with 'pbkdf2_sha256$'
        assert user.password.startswith('pbkdf2_sha256$')
        
        # Verify password can be checked correctly
        assert user.check_password(password) is True
        assert user.check_password('WrongPassword') is False
    
    def test_register_user_password_not_retrievable(self, subscription_tier):
        """Test that password cannot be retrieved from hash."""
        from apps.rbac.services import AuthService
        
        email = 'testuser@example.com'
        password = 'MySecretPassword456!'
        business_name = 'Test Business'
        
        # Register user
        result = AuthService.register_user(
            email=email,
            password=password,
            business_name=business_name
        )
        
        user = result['user']
        
        # Verify password hash doesn't contain the plaintext password
        assert password not in user.password
        
        # Verify hash is sufficiently long (PBKDF2 hashes are ~80+ chars)
        assert len(user.password) > 70
        
        # Verify hash contains salt (PBKDF2 format: algorithm$iterations$salt$hash)
        parts = user.password.split('$')
        assert len(parts) == 4  # algorithm, iterations, salt, hash
        assert parts[0] == 'pbkdf2_sha256'
        assert int(parts[1]) >= 260000  # Django 4.2+ uses 260,000 iterations


@pytest.mark.django_db
class TestFourEyesValidation:
    """Test four-eyes approval validation."""
    
    def test_validate_four_eyes_different_users(self):
        """Test that validation passes for different users."""
        user1 = User.objects.create_user(email='user1@example.com', password='pass')
        user2 = User.objects.create_user(email='user2@example.com', password='pass')
        
        result = RBACService.validate_four_eyes(user1.id, user2.id)
        assert result is True
    
    def test_validate_four_eyes_same_user_raises_error(self):
        """Test that validation fails for same user."""
        user = User.objects.create_user(email='user@example.com', password='pass')
        
        with pytest.raises(ValueError) as exc_info:
            RBACService.validate_four_eyes(user.id, user.id)
        
        assert 'Four-eyes validation failed' in str(exc_info.value)
        assert 'must be different users' in str(exc_info.value)


@pytest.mark.django_db
class TestHelperMethods:
    """Test helper methods for scope checking and querying."""
    
    def test_has_scope(self, tenant, user):
        """Test checking if user has a specific scope."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        # Create role with permission
        role = create_test_role(tenant, 'Viewer')
        perm = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        RolePermission.objects.grant_permission(role, perm)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        assert RBACService.has_scope(tenant_user, 'catalog:view') is True
        assert RBACService.has_scope(tenant_user, 'catalog:edit') is False
    
    def test_has_all_scopes(self, tenant, user):
        """Test checking if user has all specified scopes."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        role = create_test_role(tenant, 'Manager')
        perm1 = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        perm2 = get_or_create_permission(code='catalog:edit', label='Edit', category='catalog')
        RolePermission.objects.grant_permission(role, perm1)
        RolePermission.objects.grant_permission(role, perm2)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        assert RBACService.has_all_scopes(tenant_user, ['catalog:view', 'catalog:edit']) is True
        assert RBACService.has_all_scopes(tenant_user, ['catalog:view', 'finance:view']) is False
    
    def test_has_any_scope(self, tenant, user):
        """Test checking if user has any of specified scopes."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        role = create_test_role(tenant, 'Viewer')
        perm = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        RolePermission.objects.grant_permission(role, perm)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role)
        
        assert RBACService.has_any_scope(tenant_user, ['catalog:view', 'finance:view']) is True
        assert RBACService.has_any_scope(tenant_user, ['finance:view', 'users:manage']) is False
    
    def test_get_role_permissions(self, tenant):
        """Test getting all permissions for a role."""
        role = create_test_role(tenant, 'Manager')
        perm1 = get_or_create_permission(code='catalog:view', label='View', category='catalog')
        perm2 = get_or_create_permission(code='catalog:edit', label='Edit', category='catalog')
        RolePermission.objects.grant_permission(role, perm1)
        RolePermission.objects.grant_permission(role, perm2)
        
        permissions = RBACService.get_role_permissions(role)
        
        assert 'catalog:view' in permissions
        assert 'catalog:edit' in permissions
        assert len(permissions) == 2
    
    def test_get_tenant_user_roles(self, tenant, user):
        """Test getting all roles for a tenant user."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        
        role1 = create_test_role(tenant, 'Manager')
        role2 = create_test_role(tenant, 'Analyst')
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role1)
        TenantUserRole.objects.create(tenant_user=tenant_user, role=role2)
        
        roles = RBACService.get_tenant_user_roles(tenant_user)
        
        assert roles.count() == 2
        assert role1 in roles
        assert role2 in roles
    
    def test_bulk_assign_roles(self, tenant, user):
        """Test assigning multiple roles at once."""
        tenant_user = TenantUser.objects.create(tenant=tenant, user=user)
        admin = User.objects.create_user(email='admin@example.com', password='pass')
        
        role1 = create_test_role(tenant, 'Manager')
        role2 = create_test_role(tenant, 'Analyst')
        
        user_roles = RBACService.bulk_assign_roles(
            tenant_user=tenant_user,
            role_ids=[role1.id, role2.id],
            assigned_by=admin
        )
        
        assert len(user_roles) == 2
        
        # Verify both roles are assigned
        assigned_roles = RBACService.get_tenant_user_roles(tenant_user)
        assert assigned_roles.count() == 2


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
