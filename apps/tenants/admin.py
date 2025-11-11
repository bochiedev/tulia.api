"""
Django admin configuration for tenants app.
"""
from django.contrib import admin
from .models import Tenant, SubscriptionTier, GlobalParty, Customer, TenantSettings


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



@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    """Admin interface for TenantSettings."""
    
    list_display = [
        'tenant', 'has_woocommerce', 'has_shopify', 
        'has_twilio', 'created_at'
    ]
    search_fields = ['tenant__name', 'tenant__slug']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Twilio Integration', {
            'fields': ('twilio_sid', 'twilio_token', 'twilio_webhook_secret'),
            'description': 'Encrypted fields - values are masked in admin'
        }),
        ('WooCommerce Integration', {
            'fields': (
                'woo_store_url', 'woo_consumer_key',
                'woo_consumer_secret', 'woo_webhook_secret'
            ),
            'classes': ('collapse',)
        }),
        ('Shopify Integration', {
            'fields': (
                'shopify_shop_domain', 'shopify_access_token',
                'shopify_webhook_secret'
            ),
            'classes': ('collapse',)
        }),
        ('WhatsApp Business', {
            'fields': ('whatsapp_business_id', 'whatsapp_access_token'),
            'classes': ('collapse',)
        }),
        ('OpenAI / LLM', {
            'fields': ('openai_api_key', 'openai_org_id'),
            'classes': ('collapse',)
        }),
        ('Payment Methods', {
            'fields': (
                'stripe_customer_id', 'stripe_payment_methods',
                'payout_method', 'payout_details'
            ),
            'classes': ('collapse',),
            'description': 'PCI-DSS compliant - only tokenized references stored'
        }),
        ('Notification Settings', {
            'fields': ('notification_settings',),
            'classes': ('collapse',)
        }),
        ('Feature Flags', {
            'fields': ('feature_flags',),
            'classes': ('collapse',)
        }),
        ('Business Hours', {
            'fields': ('business_hours',),
            'classes': ('collapse',)
        }),
        ('Integration Status', {
            'fields': ('integrations_status',),
            'classes': ('collapse',)
        }),
        ('Branding', {
            'fields': ('branding',),
            'classes': ('collapse',)
        }),
        ('Compliance', {
            'fields': ('compliance_settings',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_woocommerce(self, obj):
        """Display if WooCommerce is configured."""
        return obj.has_woocommerce_configured()
    has_woocommerce.boolean = True
    has_woocommerce.short_description = 'WooCommerce'
    
    def has_shopify(self, obj):
        """Display if Shopify is configured."""
        return obj.has_shopify_configured()
    has_shopify.boolean = True
    has_shopify.short_description = 'Shopify'
    
    def has_twilio(self, obj):
        """Display if Twilio is configured."""
        return obj.has_twilio_configured()
    has_twilio.boolean = True
    has_twilio.short_description = 'Twilio'
