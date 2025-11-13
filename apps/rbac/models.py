"""
RBAC models for multi-tenant admin access control.

Implements:
- Global User identity (can work across multiple tenants)
- TenantUser association with invite tracking
- Permission (global canonical permissions)
- Role (per-tenant role definitions)
- RolePermission (maps permissions to roles)
- UserPermission (per-user overrides with grant/deny)
- AuditLog (comprehensive audit trail)
"""
import logging
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.postgres.fields import ArrayField
from apps.core.models import BaseModel
from apps.core.fields import EncryptedCharField

logger = logging.getLogger(__name__)


class UserManager(models.Manager):
    """
    Manager for User queries.
    
    Compatible with Django's authentication system and admin interface.
    """
    
    def active(self):
        """Return only active users."""
        return self.filter(is_active=True)
    
    def by_email(self, email):
        """Find user by email."""
        return self.filter(email=email).first()
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create a new user with hashed password.
        
        This method is compatible with Django's authentication system.
        """
        if not email:
            raise ValueError('Email address is required')
        
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_superuser', False)
        
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create a superuser with admin access.
        
        This method is required for Django's createsuperuser command.
        """
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)
        
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(email, password, **extra_fields)
    
    def normalize_email(cls, email):
        """
        Normalize the email address by lowercasing the domain part.
        """
        email = email or ''
        try:
            email_name, domain_part = email.strip().rsplit('@', 1)
        except ValueError:
            pass
        else:
            email = email_name + '@' + domain_part.lower()
        return email
    
    def get_by_natural_key(self, email):
        """
        Get user by natural key (email).
        
        This method is required for Django's authentication system.
        """
        return self.get(**{self.model.USERNAME_FIELD: email})


class User(BaseModel):
    """
    Global user identity - can belong to multiple tenants.
    
    A single person can work across multiple tenants with different roles.
    Authentication happens at the User level, authorization at the TenantUser level.
    
    This is the AUTH_USER_MODEL for the entire application, including Django admin.
    """
    
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="User email address (unique globally)"
    )
    phone = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted phone number"
    )
    password_hash = models.CharField(
        max_length=255,
        help_text="Hashed password",
        db_column='password_hash'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether user account is active"
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Platform administrator (use sparingly in production)"
    )
    
    # Django admin compatibility
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already the USERNAME_FIELD
    
    # Two-Factor Authentication
    two_factor_enabled = models.BooleanField(
        default=False,
        help_text="Whether 2FA is enabled"
    )
    two_factor_secret = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted 2FA secret"
    )
    
    # Activity Tracking
    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last login timestamp"
    )
    
    # Email Verification
    email_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether email has been verified"
    )
    email_verification_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Email verification token"
    )
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When verification email was sent"
    )
    
    # Profile
    first_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="User first name"
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="User last name"
    )
    
    # Custom manager
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['email_verified', 'is_active']),
            models.Index(fields=['email_verification_token']),
        ]
    
    def __str__(self):
        return self.email
    
    @property
    def password(self):
        """
        Alias for password_hash to maintain Django admin compatibility.
        Django admin expects a 'password' field.
        """
        return self.password_hash
    
    @password.setter
    def password(self, value):
        """
        Set password_hash when password is assigned.
        Allows Django admin to work with password field.
        """
        self.password_hash = value
    
    def check_password(self, raw_password):
        """Check if provided password matches stored hash."""
        return check_password(raw_password, self.password_hash)
    
    def set_password(self, raw_password):
        """Set user password (hashes automatically)."""
        self.password_hash = make_password(raw_password)
    
    def get_full_name(self):
        """Return full name or email if name not set."""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email
    
    def update_last_login(self):
        """Update last_login_at to current time."""
        from django.utils import timezone
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])
    
    @property
    def is_authenticated(self):
        """
        Always return True for User instances.
        This is required for Django authentication compatibility.
        """
        return True
    
    @property
    def is_anonymous(self):
        """
        Always return False for User instances.
        This is required for Django authentication compatibility.
        """
        return False
    
    @property
    def is_staff(self):
        """
        Return True if user is a superuser.
        This is required for Django admin access.
        """
        return self.is_superuser
    
    def has_perm(self, perm, obj=None):
        """
        Check if user has a specific permission.
        Superusers have all permissions (required for Django admin).
        """
        return self.is_superuser
    
    def has_perms(self, perm_list, obj=None):
        """
        Check if user has all permissions in the list.
        Superusers have all permissions (required for Django admin).
        """
        return self.is_superuser
    
    def has_module_perms(self, app_label):
        """
        Check if user has permissions to view the app in admin.
        Superusers have access to all modules (required for Django admin).
        """
        return self.is_superuser
    
    def get_user_permissions(self, obj=None):
        """
        Return empty set - permissions are handled via RBAC for tenants.
        Django admin uses is_superuser check instead.
        """
        return set()
    
    def get_group_permissions(self, obj=None):
        """
        Return empty set - we don't use Django's group permissions.
        """
        return set()
    
    def get_all_permissions(self, obj=None):
        """
        Return empty set - permissions are handled via RBAC for tenants.
        Django admin uses is_superuser check instead.
        """
        return set()
    
    def natural_key(self):
        """
        Return the natural key for this user (email).
        
        This method is required for Django's serialization system.
        """
        return (self.email,)


class TenantUserManager(models.Manager):
    """Manager for TenantUser queries."""
    
    def for_tenant(self, tenant):
        """Get all tenant users for a specific tenant."""
        return self.filter(tenant=tenant, is_active=True)
    
    def for_user(self, user):
        """Get all tenant memberships for a specific user."""
        return self.filter(user=user, is_active=True)
    
    def get_membership(self, tenant, user):
        """Get specific tenant-user membership."""
        return self.filter(tenant=tenant, user=user, is_active=True).first()
    
    def pending_invites(self):
        """Get all pending invitations."""
        return self.filter(invite_status='pending', is_active=True)
    
    def accepted(self):
        """Get all accepted memberships."""
        return self.filter(invite_status='accepted', is_active=True)


class TenantUser(BaseModel):
    """
    Association between User and Tenant with invite tracking.
    
    Represents a user's membership in a specific tenant.
    A user can have multiple TenantUser records (one per tenant).
    """
    
    INVITE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('revoked', 'Revoked'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_users',
        db_index=True,
        help_text="Tenant this membership belongs to"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tenant_memberships',
        db_index=True,
        help_text="User who is a member"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether membership is active"
    )
    invite_status = models.CharField(
        max_length=20,
        choices=INVITE_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Invitation status"
    )
    
    # Invitation Tracking
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitations_sent',
        help_text="User who sent the invitation"
    )
    invited_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When invitation was sent"
    )
    joined_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user accepted invitation"
    )
    
    # Activity Tracking
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Last activity timestamp in this tenant"
    )
    
    # Custom manager
    objects = TenantUserManager()
    
    class Meta:
        db_table = 'tenant_users'
        unique_together = [('tenant', 'user')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['invite_status', 'is_active']),
            models.Index(fields=['tenant', 'last_seen_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} @ {self.tenant.name}"
    
    def accept_invitation(self):
        """Accept pending invitation."""
        if self.invite_status == 'pending':
            from django.utils import timezone
            self.invite_status = 'accepted'
            self.joined_at = timezone.now()
            self.save(update_fields=['invite_status', 'joined_at'])
    
    def revoke_invitation(self):
        """Revoke invitation or membership."""
        self.invite_status = 'revoked'
        self.is_active = False
        self.save(update_fields=['invite_status', 'is_active'])
    
    def update_last_seen(self):
        """Update last_seen_at to current time."""
        from django.utils import timezone
        self.last_seen_at = timezone.now()
        self.save(update_fields=['last_seen_at'])


class PermissionManager(models.Manager):
    """Manager for Permission queries."""
    
    def by_code(self, code):
        """Find permission by code."""
        return self.filter(code=code).first()
    
    def by_category(self, category):
        """Get all permissions in a category."""
        return self.filter(category=category)
    
    def get_or_create_permission(self, code, label, description='', category=''):
        """Get or create permission (idempotent)."""
        permission, created = self.get_or_create(
            code=code,
            defaults={
                'label': label,
                'description': description,
                'category': category,
            }
        )
        return permission, created


class Permission(BaseModel):
    """
    Global permission definitions - shared across all tenants.
    
    Canonical permissions are seeded during deployment and define
    all available access controls in the system.
    """
    
    code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique permission code (e.g., 'catalog:view')"
    )
    label = models.CharField(
        max_length=255,
        help_text="Human-readable label (e.g., 'View Catalog')"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of what this permission grants"
    )
    category = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Permission category (e.g., 'catalog', 'finance', 'users')"
    )
    
    # Custom manager
    objects = PermissionManager()
    
    class Meta:
        db_table = 'permissions'
        ordering = ['category', 'code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.label}"


class RoleManager(models.Manager):
    """Manager for Role queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get all roles for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def system_roles(self, tenant):
        """Get system-seeded roles for a tenant."""
        return self.filter(tenant=tenant, is_system=True)
    
    def custom_roles(self, tenant):
        """Get custom (non-system) roles for a tenant."""
        return self.filter(tenant=tenant, is_system=False)
    
    def by_name(self, tenant, name):
        """Find role by tenant and name."""
        return self.filter(tenant=tenant, name=name).first()
    
    def get_or_create_role(self, tenant, name, description='', is_system=False):
        """Get or create role (idempotent)."""
        role, created = self.get_or_create(
            tenant=tenant,
            name=name,
            defaults={
                'description': description,
                'is_system': is_system,
            }
        )
        return role, created


class Role(BaseModel):
    """
    Per-tenant role definitions.
    
    Each tenant has its own set of roles. System roles are seeded
    automatically (Owner, Admin, etc.), but tenants can create custom roles.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='roles',
        db_index=True,
        help_text="Tenant this role belongs to"
    )
    name = models.CharField(
        max_length=100,
        help_text="Role name (e.g., 'Owner', 'Catalog Manager')"
    )
    description = models.TextField(
        blank=True,
        help_text="Role description"
    )
    is_system = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this is a system-seeded role"
    )
    
    # Custom manager
    objects = RoleManager()
    
    class Meta:
        db_table = 'roles'
        unique_together = [('tenant', 'name')]
        ordering = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_system']),
            models.Index(fields=['tenant', 'name']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.name}"
    
    def get_permissions(self):
        """Get all permissions granted by this role."""
        return Permission.objects.filter(
            role_permissions__role=self
        ).distinct()
    
    def has_permission(self, permission_code):
        """Check if role has a specific permission."""
        return self.role_permissions.filter(
            permission__code=permission_code
        ).exists()


class RolePermissionManager(models.Manager):
    """Manager for RolePermission queries."""
    
    def for_role(self, role):
        """Get all permissions for a role."""
        return self.filter(role=role)
    
    def for_permission(self, permission):
        """Get all roles that have a permission."""
        return self.filter(permission=permission)
    
    def for_tenant(self, tenant):
        """Get all role permissions for a specific tenant."""
        return self.filter(role__tenant=tenant)
    
    def grant_permission(self, role, permission):
        """Grant permission to role (idempotent)."""
        role_permission, created = self.get_or_create(
            role=role,
            permission=permission
        )
        return role_permission, created
    
    def revoke_permission(self, role, permission):
        """Revoke permission from role."""
        return self.filter(role=role, permission=permission).delete()


class RolePermission(BaseModel):
    """
    Maps permissions to roles.
    
    Defines which permissions are granted by each role.
    """
    
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions',
        db_index=True,
        help_text="Role that grants this permission"
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions',
        db_index=True,
        help_text="Permission being granted"
    )
    
    # Custom manager
    objects = RolePermissionManager()
    
    class Meta:
        db_table = 'role_permissions'
        unique_together = [('role', 'permission')]
        ordering = ['role', 'permission']
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['permission']),
        ]
    
    def __str__(self):
        return f"{self.role.name} -> {self.permission.code}"


class TenantUserRole(BaseModel):
    """
    Maps roles to tenant users.
    
    A tenant user can have multiple roles, and permissions are aggregated.
    """
    
    tenant_user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name='user_roles',
        db_index=True,
        help_text="Tenant user who has this role"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles',
        db_index=True,
        help_text="Role assigned to the user"
    )
    
    # Audit fields
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='role_assignments_made',
        help_text="User who assigned this role"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When role was assigned"
    )
    
    class Meta:
        db_table = 'tenant_user_roles'
        unique_together = [('tenant_user', 'role')]
        ordering = ['tenant_user', 'role']
        indexes = [
            models.Index(fields=['tenant_user']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.tenant_user.user.email} -> {self.role.name}"
    
    def clean(self):
        """Validate that tenant_user and role belong to same tenant."""
        super().clean()
        if self.tenant_user_id and self.role_id:
            if self.tenant_user.tenant_id != self.role.tenant_id:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    "TenantUser and Role must belong to the same tenant"
                )
    
    def save(self, *args, **kwargs):
        """Validate before saving."""
        self.full_clean()
        super().save(*args, **kwargs)


class UserPermissionManager(models.Manager):
    """Manager for UserPermission queries."""
    
    def for_tenant_user(self, tenant_user):
        """Get all permission overrides for a tenant user."""
        return self.filter(tenant_user=tenant_user)
    
    def for_tenant(self, tenant):
        """Get all user permission overrides for a specific tenant."""
        return self.filter(tenant_user__tenant=tenant)
    
    def grants(self, tenant_user):
        """Get granted permissions for a tenant user."""
        return self.filter(tenant_user=tenant_user, granted=True)
    
    def denies(self, tenant_user):
        """Get denied permissions for a tenant user."""
        return self.filter(tenant_user=tenant_user, granted=False)
    
    def grant_permission(self, tenant_user, permission, reason='', granted_by=None):
        """Grant permission to user (idempotent)."""
        user_permission, created = self.update_or_create(
            tenant_user=tenant_user,
            permission=permission,
            defaults={
                'granted': True,
                'reason': reason,
                'granted_by': granted_by,
            }
        )
        # Invalidate scope cache
        from django.core.cache import cache
        cache_key = f"scopes:tenant_user:{tenant_user.id}"
        cache.delete(cache_key)
        
        return user_permission, created
    
    def deny_permission(self, tenant_user, permission, reason='', granted_by=None):
        """Deny permission to user (idempotent)."""
        user_permission, created = self.update_or_create(
            tenant_user=tenant_user,
            permission=permission,
            defaults={
                'granted': False,
                'reason': reason,
                'granted_by': granted_by,
            }
        )
        # Invalidate scope cache
        from django.core.cache import cache
        cache_key = f"scopes:tenant_user:{tenant_user.id}"
        cache.delete(cache_key)
        
        return user_permission, created


class UserPermission(BaseModel):
    """
    Per-user permission overrides (grant or deny).
    
    Allows granting or denying specific permissions to individual users,
    overriding their role-based permissions. Deny overrides always win.
    """
    
    tenant_user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name='user_permissions',
        db_index=True,
        help_text="Tenant user this override applies to"
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='user_permissions',
        db_index=True,
        help_text="Permission being granted or denied"
    )
    granted = models.BooleanField(
        help_text="True = grant, False = deny (deny wins over role grants)"
    )
    
    # Audit fields
    reason = models.TextField(
        blank=True,
        help_text="Reason for this override"
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permission_overrides_made',
        help_text="User who created this override"
    )
    
    # Custom manager
    objects = UserPermissionManager()
    
    class Meta:
        db_table = 'user_permissions'
        unique_together = [('tenant_user', 'permission')]
        ordering = ['tenant_user', 'permission']
        indexes = [
            models.Index(fields=['tenant_user', 'granted']),
            models.Index(fields=['permission']),
        ]
    
    def __str__(self):
        action = "GRANT" if self.granted else "DENY"
        return f"{action} {self.permission.code} to {self.tenant_user.user.email}"


class PasswordResetTokenManager(models.Manager):
    """Manager for PasswordResetToken queries."""
    
    def for_user(self, user):
        """Get all password reset tokens for a user."""
        return self.filter(user=user)
    
    def valid_tokens(self):
        """Get all valid (non-expired, unused) tokens."""
        from django.utils import timezone
        return self.filter(
            expires_at__gt=timezone.now(),
            used=False
        )
    
    def get_valid_token(self, token):
        """Get a valid token by token string."""
        from django.utils import timezone
        return self.filter(
            token=token,
            expires_at__gt=timezone.now(),
            used=False
        ).first()


class PasswordResetToken(BaseModel):
    """
    Password reset tokens for forgot password flow.
    
    Tokens expire after 24 hours and can only be used once.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        help_text="User this token belongs to"
    )
    token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique reset token"
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Token expiration time (24 hours from creation)"
    )
    used = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether token has been used"
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When token was used"
    )
    
    # Custom manager
    objects = PasswordResetTokenManager()
    
    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token', 'expires_at', 'used']),
            models.Index(fields=['user', 'expires_at']),
        ]
    
    def __str__(self):
        return f"Password reset token for {self.user.email}"
    
    def is_valid(self):
        """Check if token is still valid (not expired and not used)."""
        from django.utils import timezone
        return not self.used and timezone.now() < self.expires_at
    
    def mark_as_used(self):
        """Mark token as used."""
        from django.utils import timezone
        self.used = True
        self.used_at = timezone.now()
        self.save(update_fields=['used', 'used_at'])
    
    @classmethod
    def create_token(cls, user):
        """
        Create a new password reset token for a user.
        
        Args:
            user: User instance
            
        Returns:
            PasswordResetToken instance
        """
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Set expiration to 24 hours from now
        expires_at = timezone.now() + timedelta(hours=24)
        
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )


class AuditLogManager(models.Manager):
    """Manager for AuditLog queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get audit logs for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_user(self, user):
        """Get audit logs for a specific user."""
        return self.filter(user=user)
    
    def by_action(self, action):
        """Get audit logs for a specific action."""
        return self.filter(action=action)
    
    def by_target(self, target_type, target_id=None):
        """Get audit logs for a specific target type and optionally target ID."""
        qs = self.filter(target_type=target_type)
        if target_id:
            qs = qs.filter(target_id=target_id)
        return qs
    
    def by_request(self, request_id):
        """Get all audit logs for a specific request."""
        return self.filter(request_id=request_id)
    
    def recent(self, days=30):
        """Get audit logs from the last N days."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class AuditLog(BaseModel):
    """
    Comprehensive audit trail for RBAC and sensitive operations.
    
    Logs all RBAC changes (role assignments, permission overrides) and
    sensitive actions (withdrawals, catalog changes, etc.) for compliance.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_index=True,
        help_text="Tenant this action belongs to (null for platform-level)"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_index=True,
        help_text="User who performed the action (null for system actions)"
    )
    
    # Action Details
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Action performed (e.g., 'role_assigned', 'permission_denied', 'product_created')"
    )
    target_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of target entity (e.g., 'Role', 'Product', 'Withdrawal')"
    )
    target_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of target entity"
    )
    
    # Change Tracking
    diff = models.JSONField(
        default=dict,
        blank=True,
        help_text="Before/after changes in JSON format"
    )
    
    # Request Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    request_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Request ID for tracing"
    )
    
    # Additional Context
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context metadata"
    )
    
    # Custom manager
    objects = AuditLogManager()
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['request_id']),
            models.Index(fields=['tenant', 'action', 'created_at']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else 'System'
        tenant_str = self.tenant.name if self.tenant else 'Platform'
        return f"{tenant_str} - {user_str} - {self.action}"
    
    @classmethod
    def log_action(cls, action, user=None, tenant=None, target_type=None, 
                   target_id=None, diff=None, metadata=None, request=None):
        """
        Convenience method to create audit log entry.
        
        Args:
            action: Action being performed
            user: User performing the action
            tenant: Tenant context
            target_type: Type of target entity
            target_id: ID of target entity
            diff: Before/after changes
            metadata: Additional context
            request: Django request object (for IP, user agent, request ID)
        
        Returns:
            AuditLog instance
        """
        # Handle AnonymousUser (API key authentication) - set user to None
        if user and not user.is_authenticated:
            user = None
        
        log_data = {
            'action': action,
            'user': user,
            'tenant': tenant,
            'target_type': target_type,
            'target_id': target_id,
            'diff': diff or {},
            'metadata': metadata or {},
        }
        
        # Extract request context if provided
        if request:
            log_data['ip_address'] = cls._get_client_ip(request)
            log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            log_data['request_id'] = getattr(request, 'request_id', None)
        
        try:
            return cls.objects.create(**log_data)
        except Exception as e:
            # Fail silently - audit logging should not break the main operation
            logger.error(
                f"Failed to create audit log: {str(e)}",
                extra={'action': action, 'tenant_id': tenant.id if tenant else None},
                exc_info=True
            )
            return None
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
