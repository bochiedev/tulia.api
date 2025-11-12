"""
Django admin configuration for core app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User


# Customize the default User admin if needed
# This is optional - Django already provides a UserAdmin
# Uncomment and customize if you need additional fields

# class CustomUserAdmin(BaseUserAdmin):
#     list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined']
#     list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
#     
# # Unregister the default User admin and register custom one
# admin.site.unregister(User)
# admin.site.register(User, CustomUserAdmin)


# Customize admin site header and title
admin.site.site_header = "Tulia AI Administration"
admin.site.site_title = "Tulia AI Admin"
admin.site.index_title = "Welcome to Tulia AI Administration"
