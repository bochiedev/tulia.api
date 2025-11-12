"""
Django admin configuration for analytics app.
"""
from django.contrib import admin
from .models import AnalyticsDaily

# Register model with default admin (read-only)
@admin.register(AnalyticsDaily)
class AnalyticsDailyAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'date']
    list_filter = ['date', 'tenant']
    search_fields = ['tenant__name']
    
    def has_add_permission(self, request):
        """Prevent manual creation."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion."""
        return False
