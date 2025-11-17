"""
RBAC and Authentication services.

Implements:
- RBACService: scope resolution, permission management, four-eyes validation
- AuthService: JWT authentication, user registration, email verification
"""
import secrets
from typing import Set, Optional, Dict, Any
from datetime import datetime, timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import jwt

from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission, 
    UserPermission, TenantUserRole, AuditLog, PasswordResetToken
)


class RBACService:
    """
    Service for RBAC operations: scope resolution, permission management, four-eyes validation.
    """
    
    SCOPE_CACHE_TTL = 300  # 5 minutes
    
    @classmethod
    def resolve_scopes(cls, tenant_user: TenantUser) -> Set[str]:
        """
        Resolve all permission scopes for a tenant user.
        
        Aggregates permissions from:
        1. All roles assigned to the user
        2. User-level permission overrides (grants)
        3. User-level permission denials (denies win over grants)
        
        Results are cached for 5 minutes.
        
        Args:
            tenant_user: TenantUser instance
            
        Returns:
            Set of permission codes (e.g., {'catalog:view', 'orders:edit'})
        """
        cache_key = f"scopes:tenant_user:{tenant_user.id}"
        cached_scopes = cache.get(cache_key)
        
        if cached_scopes is not None:
            return set(cached_scopes)
        
        # Start with empty set
        scopes = set()
        
        # 1. Aggregate permissions from all roles
        role_permissions = Permission.objects.filter(
            role_permissions__role__user_roles__tenant_user=tenant_user
        ).distinct()
        
        for perm in role_permissions:
            scopes.add(perm.code)
        
        # 2. Apply user-level grants first
        user_grants = UserPermission.objects.filter(
            tenant_user=tenant_user,
            granted=True
        ).select_related('permission')
        
        for grant in user_grants:
            scopes.add(grant.permission.code)
        
        # 3. Apply user-level denies (deny wins over everything)
        user_denies = UserPermission.objects.filter(
            tenant_user=tenant_user,
            granted=False
        ).select_related('permission')
        
        for deny in user_denies:
            # Remove from scopes (deny wins)
            scopes.discard(deny.permission.code)
        
        # Cache the result
        cache.set(cache_key, list(scopes), cls.SCOPE_CACHE_TTL)
        
        return scopes
    
    @classmethod
    def invalidate_scope_cache(cls, tenant_user: TenantUser):
        """Invalidate cached scopes for a tenant user."""
        cache_key = f"scopes:tenant_user:{tenant_user.id}"
        cache.delete(cache_key)
    
    @classmethod
    def has_scope(cls, tenant_user: TenantUser, scope: str) -> bool:
        """Check if tenant user has a specific scope."""
        scopes = cls.resolve_scopes(tenant_user)
        return scope in scopes
    
    @classmethod
    def has_all_scopes(cls, tenant_user: TenantUser, required_scopes) -> bool:
        """Check if tenant user has all required scopes."""
        scopes = cls.resolve_scopes(tenant_user)
        # Convert to set if it's a list
        if isinstance(required_scopes, list):
            required_scopes = set(required_scopes)
        return required_scopes.issubset(scopes)
    
    @classmethod
    def has_any_scope(cls, tenant_user: TenantUser, required_scopes) -> bool:
        """Check if tenant user has any of the required scopes."""
        scopes = cls.resolve_scopes(tenant_user)
        # Convert to set if it's a list
        if isinstance(required_scopes, list):
            required_scopes = set(required_scopes)
        return bool(required_scopes.intersection(scopes))
    
    @classmethod
    def get_role_permissions(cls, role: Role) -> Set[str]:
        """Get all permission codes for a role."""
        return set(
            Permission.objects.filter(
                role_permissions__role=role
            ).values_list('code', flat=True)
        )
    
    @classmethod
    def get_tenant_user_roles(cls, tenant_user: TenantUser):
        """Get all roles for a tenant user."""
        return Role.objects.filter(
            user_roles__tenant_user=tenant_user
        ).distinct()
    
    @classmethod
    def bulk_assign_roles(cls, tenant_user: TenantUser, role_ids: list,
                         assigned_by: Optional[User] = None):
        """
        Assign multiple roles to a tenant user at once.
        
        Args:
            tenant_user: TenantUser to assign roles to
            role_ids: List of role IDs to assign
            assigned_by: User who assigned the roles
            
        Returns:
            List of TenantUserRole instances
        """
        roles = Role.objects.filter(
            id__in=role_ids,
            tenant=tenant_user.tenant
        )
        
        user_roles = []
        for role in roles:
            user_role = cls.assign_role(tenant_user, role, assigned_by)
            user_roles.append(user_role)
        
        return user_roles
    
    @classmethod
    def grant_permission(cls, tenant_user: TenantUser, permission_code: str, 
                        reason: str = '', granted_by: Optional[User] = None) -> UserPermission:
        """
        Grant a permission to a user (user-level override).
        
        Args:
            tenant_user: TenantUser to grant permission to
            permission_code: Permission code (e.g., 'catalog:view')
            reason: Reason for granting
            granted_by: User who granted the permission
            
        Returns:
            UserPermission instance
            
        Raises:
            Permission.DoesNotExist: If permission code doesn't exist
        """
        permission = Permission.objects.by_code(permission_code)
        if not permission:
            raise Permission.DoesNotExist(f"Permission '{permission_code}' does not exist")
        
        user_permission, created = UserPermission.objects.grant_permission(
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
            target_id=user_permission.id,
            diff={
                'permission': permission_code,
                'granted': True,
            },
            metadata={
                'target_user_email': tenant_user.user.email,
                'permission_code': permission_code,
                'reason': reason,
            }
        )
        
        return user_permission
    
    @classmethod
    def deny_permission(cls, tenant_user: TenantUser, permission_code: str,
                       reason: str = '', granted_by: Optional[User] = None) -> UserPermission:
        """
        Deny a permission to a user (user-level override).
        
        Deny overrides always win over role grants.
        
        Args:
            tenant_user: TenantUser to deny permission to
            permission_code: Permission code (e.g., 'catalog:edit')
            reason: Reason for denying
            granted_by: User who denied the permission
            
        Returns:
            UserPermission instance
            
        Raises:
            Permission.DoesNotExist: If permission code doesn't exist
        """
        permission = Permission.objects.by_code(permission_code)
        if not permission:
            raise Permission.DoesNotExist(f"Permission '{permission_code}' does not exist")
        
        user_permission, created = UserPermission.objects.deny_permission(
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
            target_id=user_permission.id,
            diff={
                'permission': permission_code,
                'granted': False,
            },
            metadata={
                'target_user_email': tenant_user.user.email,
                'permission_code': permission_code,
                'reason': reason,
            }
        )
        
        return user_permission
    
    @classmethod
    def assign_role(cls, tenant_user: TenantUser, role: Role, 
                   assigned_by: Optional[User] = None) -> TenantUserRole:
        """
        Assign a role to a tenant user.
        
        Args:
            tenant_user: TenantUser to assign role to
            role: Role to assign
            assigned_by: User who assigned the role
            
        Returns:
            TenantUserRole instance
        """
        if role.tenant != tenant_user.tenant:
            raise ValueError("Role must belong to the same tenant as the user")
        
        tenant_user_role, created = TenantUserRole.objects.get_or_create(
            tenant_user=tenant_user,
            role=role,
            defaults={'assigned_by': assigned_by}
        )
        
        # Invalidate cache
        cls.invalidate_scope_cache(tenant_user)
        
        # Log to audit trail
        if created:
            AuditLog.log_action(
                action='role_assigned',
                user=assigned_by,
                tenant=tenant_user.tenant,
                target_type='TenantUserRole',
                target_id=tenant_user_role.id,
                diff={
                    'role': role.name,
                    'action': 'assigned',
                },
                metadata={
                    'target_user_email': tenant_user.user.email,
                    'role_name': role.name,
                }
            )
        
        return tenant_user_role
    
    @classmethod
    def remove_role(cls, tenant_user: TenantUser, role: Role,
                   removed_by: Optional[User] = None) -> bool:
        """
        Remove a role from a tenant user.
        
        Args:
            tenant_user: TenantUser to remove role from
            role: Role to remove
            removed_by: User who removed the role
            
        Returns:
            True if role was removed, False if it didn't exist
        """
        result = TenantUserRole.objects.filter(
            tenant_user=tenant_user,
            role=role
        ).delete()
        # delete() returns (count, {model: count}) when items exist, or just int when empty
        deleted_count = result[0] if isinstance(result, tuple) else result
        
        if deleted_count > 0:
            # Invalidate cache
            cls.invalidate_scope_cache(tenant_user)
            
            # Log to audit trail
            AuditLog.log_action(
                action='role_removed',
                user=removed_by,
                tenant=tenant_user.tenant,
                target_type='TenantUserRole',
                diff={
                    'role': role.name,
                    'action': 'removed',
                },
                metadata={
                    'target_user_email': tenant_user.user.email,
                    'role_name': role.name,
                }
            )
            return True
        
        return False
    
    @classmethod
    def validate_four_eyes(cls, initiator=None, approver=None, initiator_user_id=None, approver_user_id=None):
        """
        Validate four-eyes principle: initiator and approver must be different users.
        
        Args:
            initiator: User instance or user ID (UUID) - deprecated, use initiator_user_id
            approver: User instance or user ID (UUID) - deprecated, use approver_user_id
            initiator_user_id: User ID (UUID) of the initiator
            approver_user_id: User ID (UUID) of the approver
            
        Returns:
            bool: True if validation passes
            
        Raises:
            ValueError: If initiator and approver are the same user
        """
        # Support both old and new parameter names for backward compatibility
        if initiator_user_id is None:
            initiator_user_id = initiator.id if hasattr(initiator, 'id') else initiator
        if approver_user_id is None:
            approver_user_id = approver.id if hasattr(approver, 'id') else approver
        
        if initiator_user_id == approver_user_id:
            raise ValueError("Four-eyes validation failed: initiator and approver must be different users")
        
        return True


class AuthService:
    """
    Service for authentication operations: JWT, registration, email verification, password reset.
    """
    
    @classmethod
    def generate_jwt(cls, user: User) -> str:
        """
        Generate JWT token for a user.
        
        Args:
            user: User instance
            
        Returns:
            JWT token string
        """
        payload = {
            'user_id': str(user.id),
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(hours=getattr(settings, 'JWT_EXPIRATION_HOURS', 24)),
            'iat': datetime.utcnow(),
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=getattr(settings, 'JWT_ALGORITHM', 'HS256')
        )
        
        return token
    
    @classmethod
    def validate_jwt(cls, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and return payload.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload dict or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[getattr(settings, 'JWT_ALGORITHM', 'HS256')]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @classmethod
    def get_user_from_jwt(cls, token: str) -> Optional[User]:
        """
        Extract and return user from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            User instance or None if invalid
        """
        payload = cls.validate_jwt(token)
        if not payload:
            return None
        
        user_id = payload.get('user_id')
        if not user_id:
            return None
        
        try:
            user = User.objects.get(id=user_id, is_active=True)
            return user
        except User.DoesNotExist:
            return None
    
    @classmethod
    @transaction.atomic
    def register_user(cls, email: str, password: str, business_name: str,
                     first_name: str = '', last_name: str = '') -> Dict[str, Any]:
        """
        Register a new user with tenant and assign Owner role.
        
        Creates:
        - User
        - Tenant
        - TenantUser (with Owner role)
        - TenantSettings
        
        Args:
            email: User email
            password: User password (will be hashed)
            business_name: Business/tenant name
            first_name: User first name (optional)
            last_name: User last name (optional)
            
        Returns:
            Dict with user, tenant, token, and verification_token
        """
        from apps.tenants.models import Tenant, TenantSettings
        from django.utils.text import slugify
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            raise ValueError(f"User with email '{email}' already exists")
        
        # Generate email verification token
        verification_token = secrets.token_urlsafe(32)
        
        # Create user without saving to database yet
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            email_verified=False,
            email_verification_token=verification_token,
            email_verification_sent_at=timezone.now(),
        )
        # Set password BEFORE saving to ensure proper hashing
        user.set_password(password)  # Properly hash password using Django's PBKDF2
        user.save()  # Now save with properly hashed password
        
        # Create tenant
        tenant_slug = slugify(business_name)
        # Ensure unique slug
        base_slug = tenant_slug
        counter = 1
        while Tenant.objects.filter(slug=tenant_slug).exists():
            tenant_slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Generate placeholder WhatsApp number (will be configured later during onboarding)
        # Format: +999{tenant_id_first_8_chars}
        import uuid
        temp_id = str(uuid.uuid4()).replace('-', '')[:12]
        placeholder_number = f"+999{temp_id}"
        
        tenant = Tenant.objects.create(
            name=business_name,
            slug=tenant_slug,
            status='trial',
            whatsapp_number=placeholder_number,
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=getattr(settings, 'DEFAULT_TRIAL_DAYS', 14)),
        )
        
        # TenantSettings is created automatically by signal
        
        # Create tenant user membership
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted',
            joined_at=timezone.now(),
        )
        
        # Assign Owner role (will be created by signal if not exists)
        owner_role = Role.objects.by_name(tenant, 'Owner')
        if owner_role:
            RBACService.assign_role(tenant_user, owner_role, assigned_by=user)
        
        # Generate JWT token
        token = cls.generate_jwt(user)
        
        # Log registration
        AuditLog.log_action(
            action='user_registered',
            user=user,
            tenant=tenant,
            target_type='User',
            target_id=user.id,
            metadata={
                'email': email,
                'business_name': business_name,
            }
        )
        
        return {
            'user': user,
            'tenant': tenant,
            'token': token,
            'verification_token': verification_token,
        }
    
    @classmethod
    def verify_email(cls, token: str) -> bool:
        """
        Verify user email with verification token.
        
        Args:
            token: Email verification token
            
        Returns:
            True if verification successful, False otherwise
        """
        try:
            user = User.objects.get(
                email_verification_token=token,
                email_verified=False,
                is_active=True,
            )
            
            # Check if token is not too old (24 hours)
            if user.email_verification_sent_at:
                age = timezone.now() - user.email_verification_sent_at
                if age.total_seconds() > 24 * 3600:
                    return False
            
            # Mark email as verified
            user.email_verified = True
            user.email_verification_token = None
            user.save(update_fields=['email_verified', 'email_verification_token'])
            
            # Log verification
            AuditLog.log_action(
                action='email_verified',
                user=user,
                target_type='User',
                target_id=user.id,
                metadata={'email': user.email}
            )
            
            return True
            
        except User.DoesNotExist:
            return False
    
    @classmethod
    def resend_verification_email(cls, email: str) -> Optional[str]:
        """
        Resend verification email to user.
        
        Args:
            email: User email
            
        Returns:
            New verification token or None if user not found
        """
        try:
            user = User.objects.get(email=email, email_verified=False, is_active=True)
            
            # Generate new token
            verification_token = secrets.token_urlsafe(32)
            user.email_verification_token = verification_token
            user.email_verification_sent_at = timezone.now()
            user.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
            
            return verification_token
            
        except User.DoesNotExist:
            return None
    
    @classmethod
    def request_password_reset(cls, email: str) -> Optional[str]:
        """
        Request password reset for a user.
        
        Args:
            email: User email
            
        Returns:
            Reset token or None if user not found
        """
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Create password reset token
            reset_token = PasswordResetToken.create_token(user)
            
            # Log password reset request
            AuditLog.log_action(
                action='password_reset_requested',
                user=user,
                target_type='User',
                target_id=user.id,
                metadata={'email': email}
            )
            
            return reset_token.token
            
        except User.DoesNotExist:
            return None
    
    @classmethod
    def reset_password(cls, token: str, new_password: str) -> bool:
        """
        Reset user password with reset token.
        
        Args:
            token: Password reset token
            new_password: New password
            
        Returns:
            True if reset successful, False otherwise
        """
        reset_token = PasswordResetToken.objects.get_valid_token(token)
        if not reset_token:
            return False
        
        # Update user password
        user = reset_token.user
        user.set_password(new_password)
        user.save(update_fields=['password_hash'])
        
        # Mark token as used
        reset_token.mark_as_used()
        
        # Log password reset
        AuditLog.log_action(
            action='password_reset_completed',
            user=user,
            target_type='User',
            target_id=user.id,
            metadata={'email': user.email}
        )
        
        return True
    
    @classmethod
    def login(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user and return JWT token.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Dict with user and token, or None if authentication failed
        """
        try:
            user = User.objects.get(email=email, is_active=True)
            
            if not user.check_password(password):
                return None
            
            # Update last login
            user.update_last_login()
            
            # Generate JWT token
            token = cls.generate_jwt(user)
            
            # Log login
            AuditLog.log_action(
                action='user_login',
                user=user,
                target_type='User',
                target_id=user.id,
                metadata={'email': email}
            )
            
            return {
                'user': user,
                'token': token,
            }
            
        except User.DoesNotExist:
            return None
