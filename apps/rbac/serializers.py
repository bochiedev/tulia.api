"""
RBAC serializers for REST API endpoints.

Provides serialization for:
- Authentication (registration, login, email verification, password reset)
- User and TenantUser (memberships)
- Roles and role assignments
- Permissions and permission overrides
- Audit logs
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)


# ===== AUTHENTICATION SERIALIZERS =====

class RegistrationSerializer(serializers.Serializer):
    """Serializer for user registration."""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    first_name = serializers.CharField(required=True, max_length=100)
    last_name = serializers.CharField(required=True, max_length=100)
    business_name = serializers.CharField(required=True, max_length=255)
    
    def validate_email(self, value):
        """Validate email format and uniqueness."""
        from apps.core.validators import InputValidator
        
        # Validate email format
        if not InputValidator.validate_email(value):
            raise serializers.ValidationError(
                "Please enter a valid email address."
            )
        
        # Check uniqueness
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value.lower()
    
    def validate_password(self, value):
        """Validate password strength."""
        from apps.core.validators import InputValidator
        
        # Use Django's built-in password validation
        validate_password(value)
        
        # Additional custom validation
        strength_check = InputValidator.validate_password_strength(value)
        if not strength_check['valid']:
            raise serializers.ValidationError(
                strength_check['errors'][0] if strength_check['errors'] else "Password does not meet requirements."
            )
        
        return value
    
    def validate_business_name(self, value):
        """Validate business name is not empty."""
        if not value.strip():
            raise serializers.ValidationError(
                "Business name cannot be empty."
            )
        return value.strip()


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_email(self, value):
        """Normalize email to lowercase."""
        return value.lower()


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification."""
    
    token = serializers.CharField(required=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting password reset."""
    
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Normalize email to lowercase."""
        return value.lower()


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for resetting password with token."""
    
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_new_password(self, value):
        """Validate password strength."""
        validate_password(value)
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for user profile (GET /v1/auth/me).
    
    Returns complete user information including:
    - Basic profile (name, email, phone)
    - Account status (active, verified, 2FA)
    - All tenant memberships with roles and permissions
    - Activity timestamps
    """
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    tenants = serializers.SerializerMethodField()
    total_tenants = serializers.SerializerMethodField()
    pending_invites = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'is_active', 'is_superuser', 'email_verified', 
            'two_factor_enabled', 'last_login_at', 'created_at', 
            'updated_at', 'tenants', 'total_tenants', 'pending_invites'
        ]
        read_only_fields = [
            'id', 'email', 'is_active', 'is_superuser', 'email_verified',
            'two_factor_enabled', 'last_login_at', 'created_at', 'updated_at', 
            'tenants', 'total_tenants', 'pending_invites'
        ]
    
    def get_total_tenants(self, obj):
        """Get count of active tenant memberships."""
        from apps.rbac.models import TenantUser
        from django.contrib.auth.models import AnonymousUser
        
        # Handle AnonymousUser
        if isinstance(obj, AnonymousUser) or not obj or not hasattr(obj, 'id'):
            return 0
        
        return TenantUser.objects.filter(
            user=obj,
            is_active=True,
            invite_status='accepted'
        ).count()
    
    def get_pending_invites(self, obj):
        """
        Get pending tenant invitations for this user.
        
        Returns list of tenants the user has been invited to but hasn't accepted yet.
        """
        from apps.rbac.models import TenantUser
        from django.contrib.auth.models import AnonymousUser
        
        # Handle AnonymousUser
        if isinstance(obj, AnonymousUser) or not obj or not hasattr(obj, 'id'):
            return []
        
        try:
            pending = TenantUser.objects.filter(
                user=obj,
                is_active=True,
                invite_status='pending'
            ).select_related('tenant', 'invited_by').order_by('-invited_at')
            
            invites_data = []
            for invite in pending:
                invites_data.append({
                    'id': str(invite.id),
                    'tenant': {
                        'id': str(invite.tenant.id),
                        'name': invite.tenant.name,
                        'slug': invite.tenant.slug,
                    },
                    'invited_by': {
                        'email': invite.invited_by.email if invite.invited_by else None,
                        'name': invite.invited_by.get_full_name() if invite.invited_by else None,
                    },
                    'invited_at': invite.invited_at.isoformat() if invite.invited_at else None,
                })
            
            return invites_data
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting pending invites: {str(e)}", exc_info=True)
            return []
    
    def get_tenants(self, obj):
        """
        Get all active tenants the user belongs to with comprehensive details.
        
        Returns only accepted memberships for active tenants with:
        - Tenant basic info (id, name, slug, status)
        - User's roles in that tenant
        - User's effective permissions/scopes
        - Membership metadata (joined date, last seen)
        """
        from apps.rbac.models import TenantUser
        from django.contrib.auth.models import AnonymousUser
        
        # Handle AnonymousUser
        if isinstance(obj, AnonymousUser) or not obj or not hasattr(obj, 'id'):
            return []
        
        try:
            # SECURITY: Only return active, accepted memberships
            memberships = TenantUser.objects.filter(
                user=obj,
                is_active=True,
                invite_status='accepted'
            ).select_related('tenant').prefetch_related(
                'user_roles__role',
                'user_roles__role__role_permissions__permission'
            ).order_by('-created_at')
            
            tenants_data = []
            for membership in memberships:
                try:
                    # Get detailed role information
                    roles_info = []
                    for user_role in membership.user_roles.all():
                        role = user_role.role
                        roles_info.append({
                            'id': str(role.id),
                            'name': role.name,
                            'description': role.description,
                            'is_system': role.is_system,
                        })
                    
                    # Get effective scopes/permissions
                    from apps.rbac.services import RBACService
                    scopes = RBACService.resolve_scopes(membership)
                    
                    # Get tenant settings info (if available)
                    tenant_info = {
                        'id': str(membership.tenant.id),
                        'name': membership.tenant.name,
                        'slug': membership.tenant.slug,
                        'status': membership.tenant.status,
                    }
                    
                    # Add subscription info if available
                    if hasattr(membership.tenant, 'subscription'):
                        try:
                            subscription = membership.tenant.subscription
                            tenant_info['subscription'] = {
                                'tier': subscription.tier,
                                'status': subscription.status,
                                'trial_ends_at': subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
                            }
                        except Exception:
                            pass
                    
                    tenants_data.append({
                        'membership_id': str(membership.id),
                        'tenant': tenant_info,
                        'roles': roles_info,
                        'scopes': sorted(list(scopes)),
                        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
                        'last_seen_at': membership.last_seen_at.isoformat() if membership.last_seen_at else None,
                    })
                except Exception as e:
                    # Log error but continue processing other memberships
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Error processing tenant membership {membership.id}: {str(e)}",
                        exc_info=True
                    )
                    # Add basic tenant info without roles/scopes
                    tenants_data.append({
                        'membership_id': str(membership.id),
                        'tenant': {
                            'id': str(membership.tenant.id),
                            'name': membership.tenant.name,
                            'slug': membership.tenant.slug,
                            'status': membership.tenant.status,
                        },
                        'roles': [],
                        'scopes': [],
                        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
                        'last_seen_at': membership.last_seen_at.isoformat() if membership.last_seen_at else None,
                    })
            
            return tenants_data
        except Exception as e:
            # Return empty list on error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting user tenants: {str(e)}", exc_info=True)
            return []


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile (PUT /v1/auth/me)."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']


# ===== USER SERIALIZERS =====

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'two_factor_enabled', 'last_login_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_login_at', 'created_at', 'updated_at'
        ]


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model."""
    
    class Meta:
        model = Permission
        fields = [
            'id', 'code', 'label', 'description', 'category',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model."""
    
    permission_count = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'is_system',
            'permission_count', 'permissions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_system', 'created_at', 'updated_at']
    
    def get_permission_count(self, obj):
        """Get count of permissions for this role."""
        return obj.role_permissions.count()
    
    def get_permissions(self, obj):
        """Get list of permission codes for this role."""
        # Only include permissions if explicitly requested
        if self.context.get('include_permissions', False):
            return list(
                obj.role_permissions.values_list('permission__code', flat=True)
            )
        return None


class RoleDetailSerializer(RoleSerializer):
    """Detailed serializer for Role with full permission list."""
    
    permissions = PermissionSerializer(
        source='get_permissions',
        many=True,
        read_only=True
    )
    
    class Meta(RoleSerializer.Meta):
        fields = RoleSerializer.Meta.fields


class RoleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating roles."""
    
    class Meta:
        model = Role
        fields = ['name', 'description']
    
    def validate_name(self, value):
        """Validate role name is unique within tenant."""
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError(
                "Tenant context is required for role creation"
            )
        if Role.objects.filter(tenant=tenant, name=value).exists():
            raise serializers.ValidationError(
                f"Role with name '{value}' already exists for this tenant"
            )
        return value


class TenantUserRoleSerializer(serializers.ModelSerializer):
    """Serializer for TenantUserRole (role assignments)."""
    
    role = RoleSerializer(read_only=True)
    role_id = serializers.UUIDField(write_only=True)
    assigned_by_email = serializers.EmailField(
        source='assigned_by.email',
        read_only=True
    )
    
    class Meta:
        model = TenantUserRole
        fields = [
            'id', 'role', 'role_id', 'assigned_by_email',
            'assigned_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'role', 'assigned_by_email', 'assigned_at', 'created_at'
        ]


class UserPermissionSerializer(serializers.ModelSerializer):
    """Serializer for UserPermission (permission overrides)."""
    
    permission = PermissionSerializer(read_only=True)
    permission_code = serializers.CharField(write_only=True)
    granted_by_email = serializers.EmailField(
        source='granted_by.email',
        read_only=True
    )
    
    class Meta:
        model = UserPermission
        fields = [
            'id', 'permission', 'permission_code', 'granted',
            'reason', 'granted_by_email', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'permission', 'granted_by_email', 'created_at', 'updated_at'
        ]
    
    def validate_permission_code(self, value):
        """Validate permission code exists."""
        if not Permission.objects.filter(code=value).exists():
            raise serializers.ValidationError(
                f"Permission '{value}' does not exist"
            )
        return value


class TenantUserSerializer(serializers.ModelSerializer):
    """Serializer for TenantUser (membership)."""
    
    user = UserSerializer(read_only=True)
    tenant_id = serializers.UUIDField(source='tenant.id', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    roles = serializers.SerializerMethodField()
    invited_by_email = serializers.EmailField(
        source='invited_by.email',
        read_only=True
    )
    
    class Meta:
        model = TenantUser
        fields = [
            'id', 'user', 'tenant_id', 'tenant_name',
            'is_active', 'invite_status', 'roles',
            'invited_by_email', 'invited_at', 'joined_at',
            'last_seen_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'tenant_id', 'tenant_name',
            'invited_by_email', 'invited_at', 'joined_at',
            'last_seen_at', 'created_at', 'updated_at'
        ]
    
    def get_roles(self, obj):
        """Get list of role names for this membership."""
        return list(
            obj.user_roles.values_list('role__name', flat=True)
        )


class MembershipDetailSerializer(TenantUserSerializer):
    """Detailed serializer for membership with full role details."""
    
    roles = TenantUserRoleSerializer(
        source='user_roles',
        many=True,
        read_only=True
    )


class InviteMemberSerializer(serializers.Serializer):
    """Serializer for inviting a new member to a tenant."""
    
    email = serializers.EmailField(required=True)
    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="List of role IDs to assign to the invited user"
    )
    
    def validate_email(self, value):
        """Validate email format."""
        return value.lower()
    
    def validate_role_ids(self, value):
        """Validate all role IDs exist for the tenant."""
        if not value:
            return value
        
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError(
                "Tenant context is required for role validation"
            )
        
        existing_roles = Role.objects.filter(
            tenant=tenant,
            id__in=value
        ).count()
        if existing_roles != len(value):
            raise serializers.ValidationError(
                "One or more role IDs are invalid for this tenant"
            )
        return value


class AssignRolesSerializer(serializers.Serializer):
    """Serializer for assigning roles to a user."""
    
    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        allow_empty=False,
        help_text="List of role IDs to assign"
    )
    
    def validate_role_ids(self, value):
        """Validate all role IDs exist for the tenant."""
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError(
                "Tenant context is required for role validation"
            )
        
        existing_roles = Role.objects.filter(
            tenant=tenant,
            id__in=value
        ).count()
        if existing_roles != len(value):
            raise serializers.ValidationError(
                "One or more role IDs are invalid for this tenant"
            )
        return value


class RolePermissionSerializer(serializers.Serializer):
    """Serializer for adding permissions to a role."""
    
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False,
        help_text="List of permission codes to add to the role"
    )
    
    def validate_permission_codes(self, value):
        """Validate all permission codes exist."""
        existing_perms = Permission.objects.filter(code__in=value).count()
        if existing_perms != len(value):
            raise serializers.ValidationError(
                "One or more permission codes are invalid"
            )
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'tenant_name', 'user_email', 'action',
            'target_type', 'target_id', 'diff', 'metadata',
            'ip_address', 'user_agent', 'request_id',
            'created_at'
        ]
        read_only_fields = fields


class UserPermissionCreateSerializer(serializers.Serializer):
    """Serializer for creating user permission overrides."""
    
    permission_code = serializers.CharField(required=True)
    granted = serializers.BooleanField(required=True)
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for this permission override"
    )
    
    def validate_permission_code(self, value):
        """Validate permission code exists."""
        if not Permission.objects.filter(code=value).exists():
            raise serializers.ValidationError(
                f"Permission '{value}' does not exist"
            )
        return value
