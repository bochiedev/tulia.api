"""
Django admin configuration for RBAC app.
"""
from django.contrib import admin
from .models import Permission, Role, RolePermission, TenantUser, UserPermission

# Register models with default admin
admin.site.register(Permission)
admin.site.register(Role)
admin.site.register(RolePermission)
admin.site.register(TenantUser)
admin.site.register(UserPermission)
