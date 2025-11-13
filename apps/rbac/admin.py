"""
Django admin configuration for RBAC app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Permission,
    Role,
    RolePermission,
    TenantUser,
    UserPermission,
    PasswordResetToken,
)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom admin for our User model.
    
    Adapted to work with email-based authentication (no username field).
    """
    # Fields to display in the user list
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_superuser', 'email_verified', 'created_at']
    list_filter = ['is_active', 'is_superuser', 'email_verified', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-created_at']
    
    # Fieldsets for the user detail/edit page
    fieldsets = (
        (None, {
            'fields': ('email', 'password_hash')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_superuser')
        }),
        ('Email Verification', {
            'fields': ('email_verified', 'email_verification_token', 'email_verification_sent_at')
        }),
        ('Two-Factor Authentication', {
            'fields': ('two_factor_enabled', 'two_factor_secret')
        }),
        ('Activity', {
            'fields': ('last_login_at', 'created_at', 'updated_at')
        }),
    )
    
    # Fieldsets for adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password_hash', 'is_active', 'is_superuser'),
        }),
    )
    
    # Read-only fields
    readonly_fields = ['created_at', 'updated_at', 'last_login_at']
    
    # Use email as the unique identifier
    filter_horizontal = ()


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    """Admin interface for PasswordResetToken model."""
    list_display = ['user', 'token_preview', 'expires_at', 'used', 'used_at', 'created_at']
    list_filter = ['used', 'expires_at', 'created_at']
    search_fields = ['user__email', 'token']
    readonly_fields = ['token', 'created_at', 'updated_at', 'used_at']
    
    def token_preview(self, obj):
        """Show first 8 characters of token."""
        return f"{obj.token[:8]}..." if obj.token else ""
    token_preview.short_description = 'Token'


# Register other models with default admin
admin.site.register(Permission)
admin.site.register(Role)
admin.site.register(RolePermission)
admin.site.register(TenantUser)
admin.site.register(UserPermission)
