"""
Tests for RBAC signals.

Tests automatic role seeding when tenants are created and
Owner role assignment to creating users.
"""
import pytest
from django.utils import timezone
from apps.tenants.models import Tenant, SubscriptionTier
from apps.rbac.models import User, TenantUser, Role, TenantUserRole, AuditLog


@pytest.fixture(scope='function')
@pytest.mark.django_db
def seed_permissions(db):
    """Seed canonical permissions before tests."""
    from apps.rbac.management.commands.seed_permissions import Command
    command = Command()
    command.handle()


@pytest.mark.django_db
class TestTenantRoleSeeding:
    """Test automatic role seeding on tenant creation."""
    
    def test_roles_seeded_on_tenant_creation(self, seed_permissions):
        """Test that default roles are automatically created when a tenant is created."""
        # Create a subscription tier first
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
            monthly_messages=1000,
            max_products=100,
            max_services=10
        )
        
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            twilio_sid='test_sid',
            twilio_token='test_token',
            webhook_secret='test_secret',
            subscription_tier=tier
        )
        
        # Verify that all 6 default roles were created
        roles = Role.objects.filter(tenant=tenant)
        assert roles.count() == 6
        
        # Verify specific roles exist
        role_names = set(roles.values_list('name', flat=True))
        expected_roles = {'Owner', 'Admin', 'Finance Admin', 'Catalog Manager', 'Support Lead', 'Analyst'}
        assert role_names == expected_roles
        
        # Verify all roles are marked as system roles
        assert all(role.is_system for role in roles)
    
    def test_owner_role_has_all_permissions(self, seed_permissions):
        """Test that the Owner role has all permissions."""
        from apps.rbac.models import Permission
        
        # Create a subscription tier
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            monthly_messages=10000,
            max_products=1000,
            max_services=50
        )
        
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Another Business',
            slug='another-business',
            whatsapp_number='+1234567891',
            twilio_sid='test_sid_2',
            twilio_token='test_token_2',
            webhook_secret='test_secret_2',
            subscription_tier=tier
        )
        
        # Get the Owner role
        owner_role = Role.objects.get(tenant=tenant, name='Owner')
        
        # Get all permissions assigned to Owner
        owner_permissions = owner_role.role_permissions.all()
        
        # Get total canonical permissions
        total_permissions = Permission.objects.count()
        
        # Owner should have all canonical permissions
        assert owner_permissions.count() == total_permissions
        assert owner_permissions.count() > 0
    
    def test_audit_log_created_on_seeding(self, seed_permissions):
        """Test that an audit log entry is created when roles are seeded."""
        # Create a subscription tier
        tier = SubscriptionTier.objects.create(
            name='Enterprise',
            monthly_price=299.00,
            yearly_price=2870.00,
            payment_facilitation=True
        )
        
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Enterprise Business',
            slug='enterprise-business',
            whatsapp_number='+1234567892',
            twilio_sid='test_sid_3',
            twilio_token='test_token_3',
            webhook_secret='test_secret_3',
            subscription_tier=tier
        )
        
        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(
            tenant=tenant,
            action='tenant_roles_seeded'
        )
        assert audit_logs.count() == 1
        
        # Verify audit log metadata
        audit_log = audit_logs.first()
        assert audit_log.target_type == 'Tenant'
        assert audit_log.target_id == tenant.id
        assert 'roles_created' in audit_log.metadata
        assert 'total_roles' in audit_log.metadata
        assert audit_log.metadata['total_roles'] == 6
    
    def test_owner_role_assigned_to_creating_user(self, seed_permissions):
        """Test that Owner role is assigned to the creating user if specified."""
        # Create a user
        user = User.objects.create(
            email='owner@example.com',
            password_hash='hashed_password',
            is_active=True
        )
        
        # Create a subscription tier
        tier = SubscriptionTier.objects.create(
            name='Starter Plus',
            monthly_price=49.00,
            yearly_price=470.00,
            monthly_messages=5000,
            max_products=500,
            max_services=25
        )
        
        # Create a tenant with the creating user attribute set BEFORE save
        tenant = Tenant(
            name='Owner Business',
            slug='owner-business',
            whatsapp_number='+1234567893',
            twilio_sid='test_sid_4',
            twilio_token='test_token_4',
            webhook_secret='test_secret_4',
            subscription_tier=tier
        )
        tenant._created_by_user = user
        tenant.save()
        
        # Verify TenantUser membership was created
        tenant_user = TenantUser.objects.filter(tenant=tenant, user=user).first()
        assert tenant_user is not None
        assert tenant_user.invite_status == 'accepted'
        assert tenant_user.is_active is True
        
        # Verify Owner role was assigned
        owner_role = Role.objects.get(tenant=tenant, name='Owner')
        role_assignment = TenantUserRole.objects.filter(
            tenant_user=tenant_user,
            role=owner_role
        ).first()
        assert role_assignment is not None
        
        # Verify audit log for Owner assignment
        audit_logs = AuditLog.objects.filter(
            tenant=tenant,
            action='owner_role_assigned'
        )
        assert audit_logs.count() == 1
        
        audit_log = audit_logs.first()
        assert audit_log.target_type == 'TenantUser'
        assert audit_log.target_id == tenant_user.id
        assert audit_log.metadata['user_email'] == user.email
        assert audit_log.metadata['role'] == 'Owner'
    
    def test_signal_idempotent_on_update(self, seed_permissions):
        """Test that signal doesn't run on tenant updates."""
        # Create a subscription tier
        tier = SubscriptionTier.objects.create(
            name='Basic',
            monthly_price=19.00,
            yearly_price=182.00,
            monthly_messages=500,
            max_products=50,
            max_services=5
        )
        
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Update Test Business',
            slug='update-test-business',
            whatsapp_number='+1234567894',
            twilio_sid='test_sid_5',
            twilio_token='test_token_5',
            webhook_secret='test_secret_5',
            subscription_tier=tier
        )
        
        # Count initial roles and audit logs
        initial_role_count = Role.objects.filter(tenant=tenant).count()
        initial_audit_count = AuditLog.objects.filter(
            tenant=tenant,
            action='tenant_roles_seeded'
        ).count()
        
        # Update the tenant
        tenant.name = 'Updated Business Name'
        tenant.save()
        
        # Verify no additional roles or audit logs were created
        final_role_count = Role.objects.filter(tenant=tenant).count()
        final_audit_count = AuditLog.objects.filter(
            tenant=tenant,
            action='tenant_roles_seeded'
        ).count()
        
        assert final_role_count == initial_role_count
        assert final_audit_count == initial_audit_count
