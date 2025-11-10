"""
Django admin configuration for tenants app.
"""
from django.contrib import admin
from .models import Tenant, SubscriptionTier, GlobalParty, Customer


@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    """Admin interface for SubscriptionTier."""
    
    list_display = [
        'name', 'monthly_price', 'yearly_price',
        'monthly_messages', 'max_products', 'max_services',
        'payment_facilitation', 'created_at'
    ]
    list_filter = ['payment_facilitation', 'priority_support', 'custom_branding']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Pricing', {
            'fields': ('monthly_price', 'yearly_price', 'currency')
        }),
        ('Feature Limits', {
            'fields': (
                'monthly_messages', 'max_products', 'max_services',
                'max_campaign_sends', 'max_daily_outbound'
            )
        }),
        ('Features', {
            'fields': (
                'payment_facilitation', 'transaction_fee_percentage',
                'ab_test_variants', 'priority_support', 'custom_branding',
                'api_access'
            )
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Admin interface for Tenant."""
    
    list_display = [
        'name', 'slug', 'status', 'subscription_tier',
        'whatsapp_number', 'trial_end_date', 'created_at'
    ]
    list_filter = ['status', 'subscription_tier', 'subscription_waived']
    search_fields = ['name', 'slug', 'whatsapp_number', 'contact_email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'status')
        }),
        ('Subscription', {
            'fields': (
                'subscription_tier', 'subscription_waived',
                'trial_start_date', 'trial_end_date'
            )
        }),
        ('Twilio Configuration', {
            'fields': (
                'whatsapp_number', 'twilio_sid', 'twilio_token',
                'webhook_secret'
            ),
            'description': 'Sensitive fields are encrypted at rest'
        }),
        ('API Access', {
            'fields': ('api_keys', 'allowed_origins')
        }),
        ('Settings', {
            'fields': ('timezone', 'quiet_hours_start', 'quiet_hours_end')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GlobalParty)
class GlobalPartyAdmin(admin.ModelAdmin):
    """Admin interface for GlobalParty."""
    
    list_display = ['id', 'created_at']
    readonly_fields = ['id', 'phone_e164', 'created_at', 'updated_at']
    search_fields = ['id']
    
    def has_add_permission(self, request):
        """Prevent manual creation of GlobalParty records."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of GlobalParty records."""
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin interface for Customer."""
    
    list_display = [
        'id', 'tenant', 'name', 'last_seen_at',
        'first_interaction_at', 'created_at'
    ]
    list_filter = ['tenant', 'timezone', 'language']
    search_fields = ['name', 'tenant__name', 'tenant__slug']
    readonly_fields = [
        'id', 'phone_e164', 'global_party',
        'created_at', 'updated_at', 'deleted_at'
    ]
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Identity', {
            'fields': ('phone_e164', 'global_party'),
            'description': 'Phone number is encrypted. GlobalParty is internal-only.'
        }),
        ('Profile', {
            'fields': ('name', 'timezone', 'language')
        }),
        ('Metadata', {
            'fields': ('tags', 'metadata')
        }),
        ('Activity', {
            'fields': ('last_seen_at', 'first_interaction_at')
        }),
        ('System', {
            'fields': ('id', 'created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
