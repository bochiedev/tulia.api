"""
Tests for TenantService.

Tests tenant lifecycle operations including:
- Tenant creation with Owner role assignment
- User tenant membership management
- Tenant access validation
- User invitations
- Soft deletion
"""
import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.tenants.models import Tenant, TenantSettings
from apps.tenants.services import TenantService
from apps.rbac.models import User, TenantUser, Role, Permission, AuditLog
from apps.rbac.services import RBACService


@pytest.mark.django_db
class TestTenantService:
    """Test tenant service functionality."""
    
    @pytest.fixture(autouse=True)
    def seed_permissions(self):
        """Seed canonical permissions for testing."""
        permissions_data = [
            ('catalog:view', 'View Catalog', 'catalog'),
            ('catalog:edit', 'Edit Catalog', 'catalog'),
            ('services:view', 'View Services', 'services'),
            ('services:edit', 'Edit Services', 'services'),
            ('availability:edit', 'Edit Availability', 'services'),
            ('conversations:view', 'View Conversations', 'conversations'),
            ('handoff:perform', 'Perform Handoff', 'conversations'),
            ('orders:view', 'View Orders', 'orders'),
            ('orders:edit', 'Edit Orders', 'orders'),
            ('appointments:view', 'View Appointments', 'appointments'),
            ('appointments:edit', 'Edit Appointments', 'appointments'),
            ('analytics:view', 'View Analytics', 'analytics'),
            ('finance:view', 'View Finance', 'finance'),
            ('finance:withdraw:initiate', 'Initiate Withdrawal', 'finance'),
            ('finance:withdraw:approve', 'Approve Withdrawal', 'finance'),
            ('finance:reconcile', 'Reconcile Finance', 'finance'),
            ('integrations:manage', 'Manage Integrations', 'integrations'),
            ('users:manage', 'Manage Users', 'users'),
        ]
        
        for code, label, category in permissions_data:
            Permission.objects.get_or_create_permission(
                code=code,
                label=label,
                category=category
            )
    
    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            email='owner@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Owner'
        )
    
    @pytest.fixture
    def other_user(self):
        """Create another test user."""
        return User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            first_name='Other',
            last_name='User'
        )
    
    @pytest.fixture
    def tenant(self, user):
        """Create a test tenant with owner."""
        return TenantService.create_tenant(
            user=user,
            name='Test Business',
            whatsapp_number='+1234567890'
        )
    
    def test_create_tenant_success(self, user):
        """Test successful tenant creation."""
        tenant = TenantService.create_tenant(
            user=user,
            name='My Business',
            whatsapp_number='+1234567890'
        )
        
        # Verify tenant created
        assert tenant.name == 'My Business'
        assert tenant.slug == 'my-business'
        assert tenant.status == 'trial'
        assert tenant.whatsapp_number == '+1234567890'
        assert tenant.trial_start_date is not None
        assert tenant.trial_end_date is not None
        
        # Verify TenantSettings created
        assert hasattr(tenant, 'settings')
        assert tenant.settings.tenant == tenant
        
        # Verify onboarding status initialized
        tenant.settings.refresh_from_db()
        onboarding = tenant.settings.integrations_status.get('onboarding', {})
        assert onboarding.get('status') == 'incomplete', f"Got: {onboarding}"
        assert 'steps' in onboarding
        
        # Verify TenantUser created
        tenant_user = TenantUser.objects.get(tenant=tenant, user=user)
        assert tenant_user.invite_status == 'accepted'
        assert tenant_user.joined_at is not None
        
        # Verify Owner role assigned
        owner_role = Role.objects.by_name(tenant, 'Owner')
        assert owner_role is not None
        assert tenant_user.user_roles.filter(role=owner_role).exists()
        
        # Verify audit log created
        audit_log = AuditLog.objects.filter(
            action='tenant_created',
            tenant=tenant,
            user=user
        ).first()
        assert audit_log is not None
    
    def test_create_tenant_auto_slug(self, user):
        """Test tenant creation with auto-generated slug."""
        tenant = TenantService.create_tenant(
            user=user,
            name='Test Business'
        )
        
        assert tenant.slug == 'test-business'
    
    def test_create_tenant_unique_slug(self, user):
        """Test tenant creation with duplicate name generates unique slug."""
        # Create first tenant
        tenant1 = TenantService.create_tenant(
            user=user,
            name='Test Business'
        )
        
        # Create second tenant with same name
        tenant2 = TenantService.create_tenant(
            user=user,
            name='Test Business'
        )
        
        assert tenant1.slug == 'test-business'
        assert tenant2.slug == 'test-business-1'
    
    def test_create_tenant_placeholder_whatsapp(self, user):
        """Test tenant creation without WhatsApp number generates placeholder."""
        tenant = TenantService.create_tenant(
            user=user,
            name='Test Business'
        )
        
        # Verify placeholder format
        assert tenant.whatsapp_number.startswith('+999')
        assert len(tenant.whatsapp_number) == 16  # +999 + 12 digits
    
    def test_get_user_tenants(self, user, tenant):
        """Test getting user's tenants."""
        # Create another tenant
        tenant2 = TenantService.create_tenant(
            user=user,
            name='Second Business'
        )
        
        # Get user's tenants
        tenants = TenantService.get_user_tenants(user)
        
        assert tenants.count() == 2
        assert tenant in tenants
        assert tenant2 in tenants
    
    def test_get_user_tenants_excludes_deleted(self, user, tenant):
        """Test that deleted tenants are excluded from user's tenant list."""
        # Soft delete tenant
        tenant.deleted_at = timezone.now()
        tenant.save()
        
        # Get user's tenants
        tenants = TenantService.get_user_tenants(user)
        
        assert tenants.count() == 0
    
    def test_get_user_tenants_excludes_inactive_membership(self, user, tenant):
        """Test that inactive memberships are excluded."""
        # Deactivate membership
        tenant_user = TenantUser.objects.get(tenant=tenant, user=user)
        tenant_user.is_active = False
        tenant_user.save()
        
        # Get user's tenants
        tenants = TenantService.get_user_tenants(user)
        
        assert tenants.count() == 0
    
    def test_validate_tenant_access_success(self, user, tenant):
        """Test successful tenant access validation."""
        tenant_user = TenantService.validate_tenant_access(user, tenant)
        
        assert tenant_user.tenant == tenant
        assert tenant_user.user == user
        assert tenant_user.is_active is True
    
    def test_validate_tenant_access_no_membership(self, other_user, tenant):
        """Test tenant access validation fails without membership."""
        with pytest.raises(PermissionDenied, match="does not have access"):
            TenantService.validate_tenant_access(other_user, tenant)
    
    def test_validate_tenant_access_deleted_tenant(self, user, tenant):
        """Test tenant access validation fails for deleted tenant."""
        # Soft delete tenant
        tenant.deleted_at = timezone.now()
        tenant.save()
        
        with pytest.raises(PermissionDenied, match="Tenant not found"):
            TenantService.validate_tenant_access(user, tenant)
    
    def test_validate_tenant_access_updates_last_seen(self, user, tenant):
        """Test that validating access updates last_seen_at."""
        import time
        tenant_user = TenantUser.objects.get(tenant=tenant, user=user)
        original_last_seen = tenant_user.last_seen_at
        
        # Wait a moment to ensure timestamp difference
        time.sleep(0.01)
        
        # Validate access
        TenantService.validate_tenant_access(user, tenant)
        
        # Refresh from database
        tenant_user.refresh_from_db()
        
        # Verify last_seen_at was updated
        if original_last_seen:
            assert tenant_user.last_seen_at > original_last_seen
        else:
            assert tenant_user.last_seen_at is not None
    
    def test_invite_user_new_user(self, user, tenant):
        """Test inviting a new user who doesn't exist yet."""
        # Invite new user
        tenant_user = TenantService.invite_user(
            tenant=tenant,
            email='newuser@example.com',
            role_names=['Admin'],
            invited_by=user
        )
        
        # Verify user created
        new_user = User.objects.by_email('newuser@example.com')
        assert new_user is not None
        assert new_user.email_verified is False
        
        # Verify tenant user created
        assert tenant_user.tenant == tenant
        assert tenant_user.user == new_user
        assert tenant_user.invite_status == 'pending'
        assert tenant_user.invited_by == user
        
        # Verify role assigned
        admin_role = Role.objects.by_name(tenant, 'Admin')
        assert tenant_user.user_roles.filter(role=admin_role).exists()
        
        # Verify audit log
        audit_log = AuditLog.objects.filter(
            action='user_invited',
            tenant=tenant,
            user=user
        ).first()
        assert audit_log is not None
    
    def test_invite_user_existing_user(self, user, tenant, other_user):
        """Test inviting an existing user."""
        # Invite existing user
        tenant_user = TenantService.invite_user(
            tenant=tenant,
            email=other_user.email,
            role_names=['Catalog Manager'],
            invited_by=user
        )
        
        # Verify tenant user created
        assert tenant_user.user == other_user
        assert tenant_user.invite_status == 'pending'
        
        # Verify role assigned
        catalog_role = Role.objects.by_name(tenant, 'Catalog Manager')
        assert tenant_user.user_roles.filter(role=catalog_role).exists()
    
    def test_invite_user_multiple_roles(self, user, tenant):
        """Test inviting user with multiple roles."""
        tenant_user = TenantService.invite_user(
            tenant=tenant,
            email='multi@example.com',
            role_names=['Admin', 'Catalog Manager'],
            invited_by=user
        )
        
        # Verify both roles assigned
        admin_role = Role.objects.by_name(tenant, 'Admin')
        catalog_role = Role.objects.by_name(tenant, 'Catalog Manager')
        
        assert tenant_user.user_roles.filter(role=admin_role).exists()
        assert tenant_user.user_roles.filter(role=catalog_role).exists()
    
    def test_invite_user_already_member(self, user, tenant, other_user):
        """Test inviting user who is already a member."""
        # First invitation
        TenantService.invite_user(
            tenant=tenant,
            email=other_user.email,
            role_names=['Admin'],
            invited_by=user
        )
        
        # Accept invitation
        tenant_user = TenantUser.objects.get(tenant=tenant, user=other_user)
        tenant_user.accept_invitation()
        
        # Try to invite again
        with pytest.raises(ValueError, match="already a member"):
            TenantService.invite_user(
                tenant=tenant,
                email=other_user.email,
                role_names=['Admin'],
                invited_by=user
            )
    
    def test_invite_user_invalid_role(self, user, tenant):
        """Test inviting user with invalid role name."""
        with pytest.raises(ValueError, match="does not exist"):
            TenantService.invite_user(
                tenant=tenant,
                email='test@example.com',
                role_names=['InvalidRole'],
                invited_by=user
            )
    
    def test_invite_user_without_permission(self, user, tenant, other_user):
        """Test that user without users:manage cannot invite."""
        # Create a user without users:manage scope
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=other_user,
            invite_status='accepted',
            joined_at=timezone.now()
        )
        
        # Try to invite (should fail)
        with pytest.raises(PermissionDenied, match="don't have permission to invite"):
            TenantService.invite_user(
                tenant=tenant,
                email='newuser@example.com',
                role_names=['Admin'],
                invited_by=other_user
            )
    
    def test_soft_delete_tenant_success(self, user, tenant):
        """Test successful tenant soft deletion."""
        # Soft delete tenant
        TenantService.soft_delete_tenant(tenant, user)
        
        # Refresh from database
        tenant.refresh_from_db()
        
        # Verify tenant soft deleted
        assert tenant.deleted_at is not None
        assert tenant.status == 'canceled'
        
        # Verify API keys revoked
        assert tenant.api_keys == []
        
        # Verify tenant users deactivated
        tenant_user = TenantUser.objects.get(tenant=tenant, user=user)
        assert tenant_user.is_active is False
        
        # Verify audit log
        audit_log = AuditLog.objects.filter(
            action='tenant_deleted',
            tenant=tenant,
            user=user
        ).first()
        assert audit_log is not None
    
    def test_soft_delete_tenant_without_permission(self, user, tenant, other_user):
        """Test that user without users:manage cannot delete tenant."""
        # Create a user without users:manage scope
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=other_user,
            invite_status='accepted',
            joined_at=timezone.now()
        )
        
        # Try to delete (should fail)
        with pytest.raises(PermissionDenied, match="don't have permission to delete"):
            TenantService.soft_delete_tenant(tenant, other_user)
    
    def test_soft_delete_tenant_without_owner_role(self, user, tenant, other_user):
        """Test that non-Owner cannot delete tenant even with users:manage."""
        # Create admin user with users:manage scope
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=other_user,
            invite_status='accepted',
            joined_at=timezone.now()
        )
        
        # Assign Admin role (has users:manage but not Owner)
        admin_role = Role.objects.by_name(tenant, 'Admin')
        if admin_role:
            RBACService.assign_role(tenant_user, admin_role, assigned_by=user)
        
        # Try to delete (should fail)
        with pytest.raises(PermissionDenied, match="Only tenant Owners"):
            TenantService.soft_delete_tenant(tenant, other_user)
