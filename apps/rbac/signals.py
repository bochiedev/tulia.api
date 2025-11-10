"""
RBAC signals for automatic role seeding and audit logging.

Automatically seeds default roles when a new tenant is created and
assigns the Owner role to the creating user if specified.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction


@receiver(post_save, sender='tenants.Tenant')
def seed_roles_on_tenant_creation(sender, instance, created, **kwargs):
    """
    Automatically seed default roles when a new tenant is created.
    
    This signal:
    1. Seeds the six default roles (Owner, Admin, Finance Admin, etc.)
    2. Assigns the Owner role to the creating user if specified
    3. Logs the seeding completion to the audit log
    
    Requirements: 58.1, 59.4
    """
    if not created:
        # Only run for new tenants
        return
    
    # Import here to avoid circular imports
    from apps.rbac.models import Permission, Role, RolePermission, AuditLog
    from apps.rbac.management.commands.seed_tenant_roles import Command
    
    # Use transaction to ensure atomicity
    with transaction.atomic():
        # Get the command instance to access role definitions
        command = Command()
        
        # Get all permissions for "ALL" marker
        all_permissions = list(Permission.objects.all())
        
        # Check if admin can approve withdrawals (from settings)
        from django.conf import settings
        admin_can_approve = getattr(settings, 'RBAC_ADMIN_CAN_APPROVE', False)
        
        roles_created = []
        
        # Seed each default role
        for role_name, role_config in command.DEFAULT_ROLES.items():
            # Get or create role
            role, role_created = Role.objects.get_or_create_role(
                tenant=instance,
                name=role_name,
                description=role_config['description'],
                is_system=True
            )
            
            if role_created:
                roles_created.append(role_name)
            
            # Get permissions for this role
            if role_config['permissions'] == 'ALL':
                permissions = all_permissions
            else:
                permission_codes = role_config['permissions']
                
                # Add finance:withdraw:approve to Admin if setting is enabled
                if role_name == 'Admin' and admin_can_approve:
                    if 'finance:withdraw:approve' not in permission_codes:
                        permission_codes = permission_codes + ['finance:withdraw:approve']
                
                permissions = Permission.objects.filter(code__in=permission_codes)
            
            # Sync role permissions
            _sync_role_permissions(role, permissions)
        
        # Log the seeding completion
        AuditLog.log_action(
            action='tenant_roles_seeded',
            user=None,  # System action
            tenant=instance,
            target_type='Tenant',
            target_id=instance.id,
            metadata={
                'roles_created': roles_created,
                'total_roles': len(command.DEFAULT_ROLES),
                'trigger': 'post_save_signal'
            }
        )
        
        # Assign Owner role to creating user if specified
        # This is handled by checking if the tenant has a 'created_by' attribute
        # which should be set before saving the tenant
        if hasattr(instance, '_created_by_user') and instance._created_by_user:
            _assign_owner_role(instance, instance._created_by_user)


def _sync_role_permissions(role, permissions):
    """
    Sync permissions for a role (idempotent).
    
    Ensures the role has exactly the specified permissions.
    Adds missing permissions and removes extra ones.
    """
    from apps.rbac.models import RolePermission, Permission
    
    # Get current permission IDs for this role
    current_perm_ids = set(
        RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
    )
    
    # Get target permission IDs
    target_perm_ids = set(p.id for p in permissions)
    
    # Add missing permissions
    to_add = target_perm_ids - current_perm_ids
    for perm_id in to_add:
        permission = Permission.objects.get(id=perm_id)
        RolePermission.objects.grant_permission(role, permission)
    
    # Remove extra permissions
    to_remove = current_perm_ids - target_perm_ids
    if to_remove:
        RolePermission.objects.filter(
            role=role,
            permission_id__in=to_remove
        ).delete()


def _assign_owner_role(tenant, user):
    """
    Assign the Owner role to a user for a tenant.
    
    Creates a TenantUser membership if it doesn't exist and assigns
    the Owner role. Logs the assignment to the audit log.
    
    Args:
        tenant: Tenant instance
        user: User instance to assign Owner role to
    """
    from apps.rbac.models import TenantUser, Role, TenantUserRole, AuditLog
    from django.utils import timezone
    
    # Get or create TenantUser membership
    tenant_user, created = TenantUser.objects.get_or_create(
        tenant=tenant,
        user=user,
        defaults={
            'invite_status': 'accepted',
            'joined_at': timezone.now(),
            'is_active': True,
        }
    )
    
    # If membership already existed, ensure it's accepted
    if not created and tenant_user.invite_status == 'pending':
        tenant_user.accept_invitation()
    
    # Get the Owner role for this tenant
    try:
        owner_role = Role.objects.get(tenant=tenant, name='Owner')
    except Role.DoesNotExist:
        # This shouldn't happen since we just seeded roles, but handle gracefully
        return
    
    # Assign Owner role if not already assigned
    role_assignment, role_created = TenantUserRole.objects.get_or_create(
        tenant_user=tenant_user,
        role=owner_role,
        defaults={
            'assigned_by': None,  # System assignment
        }
    )
    
    if role_created:
        # Log the Owner role assignment
        AuditLog.log_action(
            action='owner_role_assigned',
            user=None,  # System action
            tenant=tenant,
            target_type='TenantUser',
            target_id=tenant_user.id,
            metadata={
                'user_email': user.email,
                'role': 'Owner',
                'trigger': 'tenant_creation'
            }
        )
