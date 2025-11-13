"""
Tenant management service.

Handles tenant lifecycle operations including:
- Tenant creation with Owner role assignment
- User tenant membership management
- Tenant access validation
- User invitations
- Soft deletion with cascading
"""
from typing import List, Optional
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import PermissionDenied
import uuid

from apps.tenants.models import Tenant, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission, AuditLog
from apps.rbac.services import RBACService


class TenantService:
    """
    Service for tenant lifecycle and membership management.
    
    Provides methods for:
    - Creating tenants with automatic Owner role assignment
    - Listing user's tenants
    - Validating tenant access
    - Inviting users to tenants
    - Soft deleting tenants
    """
    
    @staticmethod
    def _seed_owner_role(tenant: Tenant):
        """
        Seed Owner role for a tenant with all permissions.
        
        This is called automatically during tenant creation to ensure
        the Owner role exists before assigning it to the creator.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Role instance
        """
        # Get or create Owner role
        owner_role, created = Role.objects.get_or_create_role(
            tenant=tenant,
            name='Owner',
            description='Full access to all tenant features and settings',
            is_system=True
        )
        
        if created:
            # Assign all permissions to Owner role
            all_permissions = Permission.objects.all()
            for permission in all_permissions:
                RolePermission.objects.grant_permission(owner_role, permission)
        
        return owner_role
    
    @classmethod
    @transaction.atomic
    def create_tenant(cls, user: User, name: str, slug: Optional[str] = None,
                     whatsapp_number: Optional[str] = None) -> Tenant:
        """
        Create new tenant with user as Owner.
        
        Automatically creates:
        - Tenant record (trial status)
        - TenantSettings with defaults
        - TenantUser with Owner role
        - Onboarding status tracking
        
        Args:
            user: User who will be the Owner
            name: Business/tenant name
            slug: URL-friendly identifier (auto-generated if not provided)
            whatsapp_number: WhatsApp business number (optional, can be configured later)
            
        Returns:
            Tenant instance
            
        Raises:
            ValueError: If slug already exists or name is invalid
        """
        # Generate slug if not provided
        if not slug:
            slug = slugify(name)
        
        # Ensure unique slug
        base_slug = slug
        counter = 1
        while Tenant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Generate placeholder WhatsApp number if not provided
        if not whatsapp_number:
            # Format: +999{random_12_digits}
            temp_id = str(uuid.uuid4()).replace('-', '')[:12]
            whatsapp_number = f"+999{temp_id}"
        
        # Create tenant
        from datetime import timedelta
        from django.conf import settings
        
        tenant = Tenant.objects.create(
            name=name,
            slug=slug,
            status='trial',
            whatsapp_number=whatsapp_number,
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(
                days=getattr(settings, 'DEFAULT_TRIAL_DAYS', 14)
            ),
        )
        
        # TenantSettings is created automatically by signal
        # Initialize onboarding status
        settings_obj = TenantSettings.objects.get(tenant=tenant)
        onboarding_status = {
            'status': 'incomplete',
            'steps': {
                'twilio_configured': {'completed': False, 'completed_at': None},
                'payment_method_added': {'completed': False, 'completed_at': None},
                'business_settings_configured': {'completed': False, 'completed_at': None},
                'woocommerce_configured': {'completed': False, 'completed_at': None},
                'shopify_configured': {'completed': False, 'completed_at': None},
                'payout_method_configured': {'completed': False, 'completed_at': None},
            }
        }
        settings_obj.integrations_status['onboarding'] = onboarding_status
        settings_obj.save(update_fields=['integrations_status'])
        
        # Seed Owner role with all permissions
        owner_role = cls._seed_owner_role(tenant)
        
        # Create tenant user membership
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted',
            joined_at=timezone.now(),
        )
        
        # Assign Owner role
        RBACService.assign_role(tenant_user, owner_role, assigned_by=user)
        
        # Log tenant creation
        AuditLog.log_action(
            action='tenant_created',
            user=user,
            tenant=tenant,
            target_type='Tenant',
            target_id=tenant.id,
            metadata={
                'tenant_name': name,
                'tenant_slug': slug,
                'owner_email': user.email,
            }
        )
        
        return tenant
    
    @classmethod
    def get_user_tenants(cls, user: User):
        """
        Get all tenants where user has membership.
        
        Returns tenants with active TenantUser membership,
        ordered by most recently accessed.
        
        Args:
            user: User instance
            
        Returns:
            QuerySet of Tenant instances
        """
        return Tenant.objects.filter(
            tenant_users__user=user,
            tenant_users__is_active=True,
            deleted_at__isnull=True
        ).select_related(
            'subscription_tier'
        ).prefetch_related(
            'tenant_users__user_roles__role'
        ).distinct().order_by('-tenant_users__last_seen_at')
    
    @classmethod
    def validate_tenant_access(cls, user: User, tenant: Tenant) -> TenantUser:
        """
        Validate user has access to tenant.
        
        Checks that:
        1. User has active TenantUser membership
        2. Tenant is not soft-deleted
        
        Args:
            user: User instance
            tenant: Tenant instance
            
        Returns:
            TenantUser instance if access is valid
            
        Raises:
            PermissionDenied: If user doesn't have access
        """
        # Check if tenant is soft-deleted
        if tenant.deleted_at is not None:
            raise PermissionDenied("Tenant not found")
        
        # Get tenant user membership
        tenant_user = TenantUser.objects.get_membership(tenant, user)
        
        if not tenant_user:
            raise PermissionDenied(
                f"User {user.email} does not have access to tenant {tenant.name}"
            )
        
        # Update last seen
        tenant_user.update_last_seen()
        
        return tenant_user
    
    @classmethod
    @transaction.atomic
    def invite_user(cls, tenant: Tenant, email: str, role_names: List[str],
                   invited_by: User) -> TenantUser:
        """
        Invite user to tenant with specified roles.
        
        If user doesn't exist, creates a new user account with pending status.
        If user exists, creates TenantUser membership with pending invitation.
        
        Args:
            tenant: Tenant to invite user to
            email: Email address of user to invite
            role_names: List of role names to assign (e.g., ['Admin', 'Catalog Manager'])
            invited_by: User who is sending the invitation
            
        Returns:
            TenantUser instance
            
        Raises:
            ValueError: If any role name is invalid
            PermissionDenied: If invited_by doesn't have users:manage scope
        """
        # Validate that invited_by has permission
        inviter_membership = cls.validate_tenant_access(invited_by, tenant)
        if not RBACService.has_scope(inviter_membership, 'users:manage'):
            raise PermissionDenied("You don't have permission to invite users")
        
        # Get or create user
        user = User.objects.by_email(email)
        if not user:
            # Create new user with random password (they'll need to reset it)
            import secrets
            random_password = secrets.token_urlsafe(32)
            user = User.objects.create_user(
                email=email,
                password=random_password,
                is_active=True,
                email_verified=False,
            )
        
        # Check if user already has membership
        existing_membership = TenantUser.objects.get_membership(tenant, user)
        if existing_membership:
            if existing_membership.invite_status == 'accepted':
                raise ValueError(f"User {email} is already a member of {tenant.name}")
            elif existing_membership.invite_status == 'pending':
                # Update existing pending invitation
                tenant_user = existing_membership
            else:
                # Revoked - create new invitation
                existing_membership.is_active = False
                existing_membership.save(update_fields=['is_active'])
                tenant_user = TenantUser.objects.create(
                    tenant=tenant,
                    user=user,
                    invite_status='pending',
                    invited_by=invited_by,
                )
        else:
            # Create new invitation
            tenant_user = TenantUser.objects.create(
                tenant=tenant,
                user=user,
                invite_status='pending',
                invited_by=invited_by,
            )
        
        # Assign roles
        for role_name in role_names:
            role = Role.objects.by_name(tenant, role_name)
            if not role:
                raise ValueError(f"Role '{role_name}' does not exist in tenant {tenant.name}")
            
            RBACService.assign_role(tenant_user, role, assigned_by=invited_by)
        
        # Log invitation
        AuditLog.log_action(
            action='user_invited',
            user=invited_by,
            tenant=tenant,
            target_type='TenantUser',
            target_id=tenant_user.id,
            metadata={
                'invited_email': email,
                'roles': role_names,
                'invited_by_email': invited_by.email,
            }
        )
        
        return tenant_user
    
    @classmethod
    @transaction.atomic
    def soft_delete_tenant(cls, tenant: Tenant, user: User):
        """
        Soft delete tenant and cascade to related records.
        
        Marks tenant and all related records as deleted by setting deleted_at timestamp.
        Revokes all API keys and invalidates active sessions.
        
        Requires:
        - users:manage scope
        - Owner role
        
        Args:
            tenant: Tenant to delete
            user: User performing the deletion
            
        Raises:
            PermissionDenied: If user doesn't have required permissions
        """
        # Validate access and permissions
        tenant_user = cls.validate_tenant_access(user, tenant)
        
        # Check users:manage scope
        if not RBACService.has_scope(tenant_user, 'users:manage'):
            raise PermissionDenied("You don't have permission to delete tenants")
        
        # Check Owner role
        owner_role = Role.objects.by_name(tenant, 'Owner')
        if owner_role:
            has_owner_role = tenant_user.user_roles.filter(role=owner_role).exists()
            if not has_owner_role:
                raise PermissionDenied("Only tenant Owners can delete tenants")
        
        # Soft delete tenant
        tenant.deleted_at = timezone.now()
        tenant.status = 'canceled'
        tenant.save(update_fields=['deleted_at', 'status', 'updated_at'])
        
        # Revoke all API keys
        tenant.api_keys = []
        tenant.save(update_fields=['api_keys'])
        
        # Soft delete all tenant users
        TenantUser.objects.filter(tenant=tenant).update(
            is_active=False,
            updated_at=timezone.now()
        )
        
        # Soft delete related records (if they have deleted_at field)
        # Note: This is handled by BaseModel's soft delete behavior
        # The middleware will filter out deleted records automatically
        
        # Log deletion
        AuditLog.log_action(
            action='tenant_deleted',
            user=user,
            tenant=tenant,
            target_type='Tenant',
            target_id=tenant.id,
            metadata={
                'tenant_name': tenant.name,
                'tenant_slug': tenant.slug,
                'deleted_by_email': user.email,
            }
        )
