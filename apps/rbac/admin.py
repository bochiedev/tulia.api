"""
Django admin configuration for RBAC app.
"""
from django.contrib import admin
from .models import (
    Permission,
    Role,
    RolePermission,
    TenantUser,
    UserPermission,
    PasswordResetToken,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'email_verified', 'last_login_at', 'created_at']
    list_filter = ['is_active', 'email_verified', 'is_superuser', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at', 'last_login_at', 'email_verification_sent_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('email', 'first_name', 'last_name', 'phone')
        }),
        ('Authentication', {
            'fields': ('password_hash', 'is_active', 'is_superuser')
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
