"""
RBAC Service for scope resolution and permission management.

Implements:
- Scope resolution with deny-overrides-allow pattern
- Permission grant/deny operations
- Role assignment/removal with audit logging
- Four-eyes validation for sensitive operations
- Caching for performance optimization
"""
from typing import Set, Optional
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from apps.rbac.models import (
    TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)
from apps.core.cache import (
    CacheService, CacheKeys, CacheTTL, TenantCacheInvalidator
)


class RBACService:
    """
    Service for RBAC operations including scope resolution and permission management.
    
    Key features:
    - Aggregates permissions from roles
    - Applies deny-overrides-allow pattern for user permission overrides
    - Caches scope resolution for performance (5-minute TTL)
    - Logs all RBAC changes to audit trail
    - Validates four-eyes approval for sensitive operations
    """
    
    # Cache TTL for scope resolution (5 minutes)
    SCOPE_CACHE_TTL = 300
    
    @classmethod
    def resolve_scopes(cls, tenant_user: TenantUser) -> Set[str]:
        """
        Resolve all permission scopes for a tenant user.
        
        Aggregates permissions from:
        1. All roles assigned to the user
        2. User-level permission overrides (grants)
        3. Applies deny-overrides-allow pattern (UserPermission.granted=False wins)
        
        Results are cached for 5 minutes for performance.
        
        Args:
            tenant_user: TenantUser instance to resolve scopes for
            
        Returns:
            Set of permission codes (e.g., {'catalog:view', 'catalog:edit'})
        """
        # Check cache first using centralized cache service
        cache_key = CacheKeys.format(
            CacheKeys.USER_SCOPES,
            tenant_id=str(tenant_user.tenant_id),
            user_id=str(tenant_user.user_id)
        )
        
        cached_scopes = CacheService.get(cache_key)
        if cached_scopes is not None:
            return cached_scopes
        
        # Start with empty set
        scopes = set()
        
        # Step 1: Aggregate permissions from all assigned roles
        role_permissions = Permission.objects.filter(
            role_permissions__role__user_roles__tenant_user=tenant_user
        ).distinct().values_list('code', flat=True)
        
        scopes.update(role_permissions)
        
        # Step 2: Get user permission overrides
        user_permissions = UserPermission.objects.filter(
            tenant_user=tenant_user
        ).select_related('permission')
        
        # Step 3: Apply deny-overrides-allow pattern
        # First, collect all denies
        denies = set()
        grants = set()
        
        for user_perm in user_permissions:
            if user_perm.granted:
                grants.add(user_perm.permission.code)
            else:
                denies.add(user_perm.permission.code)
        
        # Add explicit grants
        scopes.update(grants)
        
        # Remove all denies (deny wins over role grants and explicit grants)
        scopes -= denies
        
        # Cache the result using centralized cache service
        CacheService.set(cache_key, scopes, CacheTTL.RBAC_SCOPES)
        
        return scopes
    
    @classmethod
    def invalidate_scope_cache(cls, tenant_user: TenantUser):
        """
        Invalidate cached scopes for a tenant user.
        
        Should be called whenever roles or permissions change for the user.
        
        Args:
            tenant_user: TenantUser instance to invalidate cache for
        """
        TenantCacheInvalidator.invalidate_user_scopes(
            str(tenant_user.tenant_id),
            str(tenant_user.user_id)
        )
    
    @classmethod
    @transaction.atomic
    def grant_permission(
        cls,
        tenant_user: TenantUser,
        permission_code: str,
        reason: str = '',
        granted_by: Optional['User'] = None,
        request=None
    ) -> UserPermission:
        """
        Grant a permission to a specific user (user-level override).
        
        Creates or updates a UserPermission record with granted=True.
        Logs the action to audit trail.
        
        Args:
            tenant_user: TenantUser to grant permission to
            permission_code: Permission code (e.g., 'catalog:view')
            reason: Reason for granting permission
            granted_by: User who is granting the permission
            request: Django request object for audit context
            
        Returns:
            UserPermission instance
            
        Raises:
            Permission.DoesNotExist: If permission code doesn't exist
        """
        # Get permission
        permission = Permission.objects.by_code(permission_code)
        if not permission:
            raise Permission.DoesNotExist(
                f"Permission '{permission_code}' does not exist"
            )
        
        # Create or update user permission
        user_perm, created = UserPermission.objects.grant_permission(
            tenant_user=tenant_user,
            permission=permission,
            reason=reason,
            granted_by=granted_by
        )
        
        # Invalidate cache
        cls.invalidate_scope_cache(tenant_user)
        
        # Log to audit trail
        AuditLog.log_action(
            action='permission_granted',
            user=granted_by,
            tenant=tenant_user.tenant,
            target_type='UserPermission',
            target_id=user_perm.id,
            diff={
                'permission': permission_code,
                'granted': True,
                'reason': reason,
                'target_user': tenant_user.user.email,
            },
            metadata={
                'created': created,
            },
            request=request
        )
        
        return user_perm
    
    @classmethod
    @transaction.atomic
    def deny_permission(
        cls,
        tenant_user: TenantUser,
        permission_code: str,
        reason: str = '',
        granted_by: Optional['User'] = None,
        request=None
    ) -> UserPermission:
        """
        Deny a permission to a specific user (user-level override).
        
        Creates or updates a UserPermission record with granted=False.
        This will override any role-based grants (deny wins).
        Logs the action to audit trail.
        
        Args:
            tenant_user: TenantUser to deny permission to
            permission_code: Permission code (e.g., 'catalog:edit')
            reason: Reason for denying permission
            granted_by: User who is denying the permission
            request: Django request object for audit context
            
        Returns:
            UserPermission instance
            
        Raises:
            Permission.DoesNotExist: If permission code doesn't exist
        """
        # Get permission
        permission = Permission.objects.by_code(permission_code)
        if not permission:
            raise Permission.DoesNotExist(
                f"Permission '{permission_code}' does not exist"
            )
        
        # Create or update user permission
        user_perm, created = UserPermission.objects.deny_permission(
            tenant_user=tenant_user,
            permission=permission,
            reason=reason,
            granted_by=granted_by
        )
        
        # Invalidate cache
        cls.invalidate_scope_cache(tenant_user)
        
        # Log to audit trail
        AuditLog.log_action(
            action='permission_denied',
            user=granted_by,
            tenant=tenant_user.tenant,
            target_type='UserPermission',
            target_id=user_perm.id,
            diff={
                'permission': permission_code,
                'granted': False,
                'reason': reason,
                'target_user': tenant_user.user.email,
            },
            metadata={
                'created': created,
            },
            request=request
        )
        
        return user_perm
    
    @classmethod
    def validate_four_eyes(
        cls,
        initiator_user_id,
        approver_user_id
    ) -> bool:
        """
        Validate four-eyes approval pattern.
        
        Ensures that the initiator and approver are different users.
        Used for sensitive operations like withdrawal approvals.
        
        Args:
            initiator_user_id: ID of user who initiated the action
            approver_user_id: ID of user who is approving the action
            
        Returns:
            True if validation passes (different users)
            
        Raises:
            ValueError: If initiator and approver are the same user
        """
        if initiator_user_id == approver_user_id:
            raise ValueError(
                "Four-eyes validation failed: initiator and approver must be different users"
            )
        return True
    
    @classmethod
    @transaction.atomic
    def assign_role(
        cls,
        tenant_user: TenantUser,
        role: Role,
        assigned_by: Optional['User'] = None,
        request=None
    ) -> TenantUserRole:
        """
        Assign a role to a tenant user.
        
        Creates a TenantUserRole record linking the user to the role.
        Invalidates scope cache and logs to audit trail.
        
        Args:
            tenant_user: TenantUser to assign role to
            role: Role to assign
            assigned_by: User who is assigning the role
            request: Django request object for audit context
            
        Returns:
            TenantUserRole instance
            
        Raises:
            ValueError: If role doesn't belong to the same tenant as tenant_user
        """
        # Validate role belongs to same tenant
        if role.tenant_id != tenant_user.tenant_id:
            raise ValueError(
                f"Role '{role.name}' does not belong to tenant '{tenant_user.tenant.name}'"
            )
        
        # Create or get role assignment
        user_role, created = TenantUserRole.objects.get_or_create(
            tenant_user=tenant_user,
            role=role,
            defaults={
                'assigned_by': assigned_by,
            }
        )
        
        # Invalidate cache
        cls.invalidate_scope_cache(tenant_user)
        
        # Log to audit trail
        AuditLog.log_action(
            action='role_assigned',
            user=assigned_by,
            tenant=tenant_user.tenant,
            target_type='TenantUserRole',
            target_id=user_role.id,
            diff={
                'role': role.name,
                'target_user': tenant_user.user.email,
            },
            metadata={
                'created': created,
                'role_id': str(role.id),
            },
            request=request
        )
        
        return user_role
    
    @classmethod
    @transaction.atomic
    def remove_role(
        cls,
        tenant_user: TenantUser,
        role: Role,
        removed_by: Optional['User'] = None,
        request=None
    ) -> bool:
        """
        Remove a role from a tenant user.
        
        Deletes the TenantUserRole record.
        Invalidates scope cache and logs to audit trail.
        
        Args:
            tenant_user: TenantUser to remove role from
            role: Role to remove
            removed_by: User who is removing the role
            request: Django request object for audit context
            
        Returns:
            True if role was removed, False if role wasn't assigned
        """
        # Try to get and delete the role assignment
        try:
            user_role = TenantUserRole.objects.get(
                tenant_user=tenant_user,
                role=role
            )
            user_role_id = user_role.id
            user_role.delete()
            removed = True
        except TenantUserRole.DoesNotExist:
            removed = False
            user_role_id = None
        
        if removed:
            # Invalidate cache
            cls.invalidate_scope_cache(tenant_user)
            
            # Log to audit trail
            AuditLog.log_action(
                action='role_removed',
                user=removed_by,
                tenant=tenant_user.tenant,
                target_type='TenantUserRole',
                target_id=user_role_id,
                diff={
                    'role': role.name,
                    'target_user': tenant_user.user.email,
                },
                metadata={
                    'role_id': str(role.id),
                },
                request=request
            )
        
        return removed
    
    @classmethod
    def has_scope(cls, tenant_user: TenantUser, scope: str) -> bool:
        """
        Check if a tenant user has a specific scope.
        
        Args:
            tenant_user: TenantUser to check
            scope: Permission code to check for
            
        Returns:
            True if user has the scope, False otherwise
        """
        scopes = cls.resolve_scopes(tenant_user)
        return scope in scopes
    
    @classmethod
    def has_all_scopes(cls, tenant_user: TenantUser, scopes: list) -> bool:
        """
        Check if a tenant user has all specified scopes.
        
        Args:
            tenant_user: TenantUser to check
            scopes: List of permission codes to check for
            
        Returns:
            True if user has all scopes, False otherwise
        """
        user_scopes = cls.resolve_scopes(tenant_user)
        return all(scope in user_scopes for scope in scopes)
    
    @classmethod
    def has_any_scope(cls, tenant_user: TenantUser, scopes: list) -> bool:
        """
        Check if a tenant user has any of the specified scopes.
        
        Args:
            tenant_user: TenantUser to check
            scopes: List of permission codes to check for
            
        Returns:
            True if user has at least one scope, False otherwise
        """
        user_scopes = cls.resolve_scopes(tenant_user)
        return any(scope in user_scopes for scope in scopes)
    
    @classmethod
    def get_users_with_scope(cls, tenant, scope: str):
        """
        Get all tenant users who have a specific scope.
        
        Args:
            tenant: Tenant to search within
            scope: Permission code to search for
            
        Returns:
            QuerySet of TenantUser instances
        """
        # Get permission
        permission = Permission.objects.by_code(scope)
        if not permission:
            return TenantUser.objects.none()
        
        # Get users with role that grants this permission
        users_with_role = TenantUser.objects.filter(
            tenant=tenant,
            user_roles__role__role_permissions__permission=permission,
            is_active=True
        ).distinct()
        
        # Get users with explicit grant
        users_with_grant = TenantUser.objects.filter(
            tenant=tenant,
            user_permissions__permission=permission,
            user_permissions__granted=True,
            is_active=True
        ).distinct()
        
        # Get users with explicit deny (to exclude)
        users_with_deny = TenantUser.objects.filter(
            tenant=tenant,
            user_permissions__permission=permission,
            user_permissions__granted=False,
            is_active=True
        ).distinct()
        
        # Combine role-based and explicit grants, then exclude denies
        all_users = (users_with_role | users_with_grant).exclude(
            id__in=users_with_deny.values_list('id', flat=True)
        )
        
        return all_users
    
    @classmethod
    def get_role_permissions(cls, role: Role) -> Set[str]:
        """
        Get all permission codes granted by a role.
        
        Args:
            role: Role to get permissions for
            
        Returns:
            Set of permission codes
        """
        permissions = Permission.objects.filter(
            role_permissions__role=role
        ).values_list('code', flat=True)
        
        return set(permissions)
    
    @classmethod
    @transaction.atomic
    def bulk_assign_roles(
        cls,
        tenant_user: TenantUser,
        role_ids: list,
        assigned_by: Optional['User'] = None,
        request=None
    ) -> list:
        """
        Assign multiple roles to a tenant user at once.
        
        Args:
            tenant_user: TenantUser to assign roles to
            role_ids: List of role IDs to assign
            assigned_by: User who is assigning the roles
            request: Django request object for audit context
            
        Returns:
            List of TenantUserRole instances
        """
        roles = Role.objects.filter(
            id__in=role_ids,
            tenant=tenant_user.tenant
        )
        
        user_roles = []
        for role in roles:
            user_role = cls.assign_role(
                tenant_user=tenant_user,
                role=role,
                assigned_by=assigned_by,
                request=request
            )
            user_roles.append(user_role)
        
        return user_roles
    
    @classmethod
    def get_tenant_user_roles(cls, tenant_user: TenantUser):
        """
        Get all roles assigned to a tenant user.
        
        Args:
            tenant_user: TenantUser to get roles for
            
        Returns:
            QuerySet of Role instances
        """
        return Role.objects.filter(
            user_roles__tenant_user=tenant_user
        ).distinct()
    
    @classmethod
    def get_tenant_user_permission_overrides(cls, tenant_user: TenantUser):
        """
        Get all permission overrides for a tenant user.
        
        Args:
            tenant_user: TenantUser to get overrides for
            
        Returns:
            QuerySet of UserPermission instances
        """
        return UserPermission.objects.filter(
            tenant_user=tenant_user
        ).select_related('permission')
