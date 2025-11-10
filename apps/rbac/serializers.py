"""
RBAC serializers for REST API endpoints.

Provides serialization for:
- User and TenantUser (memberships)
- Roles and role assignments
- Permissions and permission overrides
- Audit logs
"""
from rest_framework import serializers
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)


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
