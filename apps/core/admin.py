"""
Django admin configuration for core app.
"""
from django.contrib import admin
from django.utils.html import format_html
from apps.core.models import PlatformSetting, PlatformPaymentCredential


# Customize admin site header and title
admin.site.site_header = "Tulia AI Administration"
admin.site.site_title = "Tulia AI Admin"
admin.site.index_title = "Welcome to Tulia AI Administration"


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    """Admin interface for platform settings."""
    
    list_display = [
        'key', 'category', 'masked_value', 'setting_type', 
        'is_active', 'is_sensitive', 'updated_at'
    ]
    list_filter = ['category', 'setting_type', 'is_active', 'is_sensitive']
    search_fields = ['key', 'description']
    ordering = ['category', 'key']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'value', 'description')
        }),
        ('Configuration', {
            'fields': ('setting_type', 'category', 'is_sensitive', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def masked_value(self, obj):
        """Display masked value for sensitive settings."""
        if obj.is_sensitive:
            return format_html('<code>{}</code>', obj.masked_value)
        else:
            return format_html('<code>{}</code>', obj.value[:50] + '...' if len(obj.value) > 50 else obj.value)
    masked_value.short_description = 'Value'
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form based on setting type."""
        form = super().get_form(request, obj, **kwargs)
        
        if obj and obj.is_sensitive:
            # Add help text for sensitive fields
            form.base_fields['value'].help_text = (
                "⚠️ This is a sensitive setting. The value will be masked in the admin interface."
            )
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Save model and clear cache."""
        super().save_model(request, obj, form, change)
        
        # Clear cache for this setting
        from django.core.cache import cache
        cache_key = f"platform_setting:{obj.key}"
        cache.delete(cache_key)


@admin.register(PlatformPaymentCredential)
class PlatformPaymentCredentialAdmin(admin.ModelAdmin):
    """Admin interface for platform payment credentials."""
    
    list_display = [
        'provider', 'environment', 'masked_api_key', 
        'is_active', 'description', 'updated_at'
    ]
    list_filter = ['provider', 'environment', 'is_active']
    search_fields = ['provider', 'description']
    ordering = ['provider', 'environment']
    
    fieldsets = (
        ('Provider Information', {
            'fields': ('provider', 'environment', 'description')
        }),
        ('Credentials', {
            'fields': ('api_key', 'api_secret'),
            'description': 'These fields are encrypted in the database.'
        }),
        ('Additional Configuration', {
            'fields': ('additional_config',),
            'description': 'Provider-specific settings like shortcode, passkey, etc.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form with help text."""
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for different providers
        if obj:
            if obj.provider == 'mpesa':
                form.base_fields['api_key'].help_text = "M-Pesa Consumer Key"
                form.base_fields['api_secret'].help_text = "M-Pesa Consumer Secret"
                form.base_fields['additional_config'].help_text = (
                    'JSON format: {"shortcode": "123456", "passkey": "your_passkey"}'
                )
            elif obj.provider == 'stripe':
                form.base_fields['api_key'].help_text = "Stripe Secret Key"
                form.base_fields['additional_config'].help_text = (
                    'JSON format: {"publishable_key": "pk_...", "webhook_secret": "whsec_..."}'
                )
            elif obj.provider == 'paystack':
                form.base_fields['api_key'].help_text = "Paystack Secret Key"
                form.base_fields['additional_config'].help_text = (
                    'JSON format: {"public_key": "pk_..."}'
                )
        
        return form
