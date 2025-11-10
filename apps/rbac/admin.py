"""
Django admin configuration for RBAC models.
"""
from django.contrib import admin
from apps.rbac.models import (
    User, TenantUser, Permission, Role, RolePermission,
    TenantUserRole, UserPermission, AuditLog
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""
    
    list_display = ['email', 'is_active', 'is_superuser', 'two_factor_enabled', 'last_login_at', 'created_at']
    list_filter = ['is_active', 'is_superuser', 'two_factor_enabled', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'last_login_at']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['email', 'first_name', 'last_name', 'phone']
        }),
        ('Status', {
            'fields': ['is_active', 'is_superuser']
        }),
        ('Security', {
            'fields': ['password_hash', 'two_factor_enabled', 'two_factor_secret']
        }),
        ('Activity', {
            'fields': ['last_login_at']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    """Admin interface for TenantUser model."""
    
    list_display = ['user', 'tenant', 'is_active', 'invite_status', 'joined_at', 'last_seen_at']
    list_filter = ['is_active', 'invite_status', 'created_at']
    search_fields = ['user__email', 'tenant__name', 'tenant__slug']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'invited_at', 'joined_at']
    raw_id_fields = ['tenant', 'user', 'invited_by']
    
    fieldsets = [
        ('Membership', {
            'fields': ['tenant', 'user', 'is_active', 'invite_status']
        }),
        ('Invitation', {
            'fields': ['invited_by', 'invited_at', 'joined_at']
        }),
        ('Activity', {
            'fields': ['last_seen_at']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin interface for Permission model."""
    
    list_display = ['code', 'label', 'category', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['code', 'label', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    
    fieldsets = [
        ('Permission Details', {
            'fields': ['code', 'label', 'description', 'category']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin interface for Role model."""
    
    list_display = ['name', 'tenant', 'is_system', 'created_at']
    list_filter = ['is_system', 'created_at']
    search_fields = ['name', 'description', 'tenant__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    raw_id_fields = ['tenant']
    
    fieldsets = [
        ('Role Details', {
            'fields': ['tenant', 'name', 'description', 'is_system']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Admin interface for RolePermission model."""
    
    list_display = ['role', 'permission', 'created_at']
    list_filter = ['created_at']
    search_fields = ['role__name', 'permission__code']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    raw_id_fields = ['role', 'permission']
    
    fieldsets = [
        ('Mapping', {
            'fields': ['role', 'permission']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(TenantUserRole)
class TenantUserRoleAdmin(admin.ModelAdmin):
    """Admin interface for TenantUserRole model."""
    
    list_display = ['tenant_user', 'role', 'assigned_by', 'assigned_at']
    list_filter = ['assigned_at']
    search_fields = ['tenant_user__user__email', 'role__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'assigned_at']
    raw_id_fields = ['tenant_user', 'role', 'assigned_by']
    
    fieldsets = [
        ('Assignment', {
            'fields': ['tenant_user', 'role', 'assigned_by', 'assigned_at']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    """Admin interface for UserPermission model."""
    
    list_display = ['tenant_user', 'permission', 'granted', 'granted_by', 'created_at']
    list_filter = ['granted', 'created_at']
    search_fields = ['tenant_user__user__email', 'permission__code', 'reason']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    raw_id_fields = ['tenant_user', 'permission', 'granted_by']
    
    fieldsets = [
        ('Override', {
            'fields': ['tenant_user', 'permission', 'granted']
        }),
        ('Audit', {
            'fields': ['reason', 'granted_by']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model."""
    
    list_display = ['action', 'user', 'tenant', 'target_type', 'target_id', 'created_at']
    list_filter = ['action', 'target_type', 'created_at']
    search_fields = ['action', 'user__email', 'tenant__name', 'target_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    raw_id_fields = ['tenant', 'user']
    
    fieldsets = [
        ('Action', {
            'fields': ['action', 'user', 'tenant']
        }),
        ('Target', {
            'fields': ['target_type', 'target_id']
        }),
        ('Changes', {
            'fields': ['diff', 'metadata']
        }),
        ('Request Context', {
            'fields': ['ip_address', 'user_agent', 'request_id']
        }),
        ('Metadata', {
            'fields': ['id', 'created_at', 'updated_at', 'deleted_at'],
            'classes': ['collapse']
        }),
    ]
    
    def has_add_permission(self, request):
        """Audit logs should not be manually created."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Audit logs should not be deleted."""
        return False
