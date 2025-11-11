"""
Serializers for TenantSettings API.

Security:
- Never expose encrypted credential values
- Return masked versions only
- Separate read/write serializers
- Validate credentials before saving
"""
from rest_framework import serializers
from apps.tenants.models import TenantSettings


class TenantSettingsReadSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for TenantSettings.
    
    Security:
    - Excludes all encrypted credential fields
    - Returns masked versions for configured integrations
    - Safe for general viewing with integrations:view scope
    """
    
    # Integration status flags
    has_woocommerce = serializers.SerializerMethodField()
    has_shopify = serializers.SerializerMethodField()
    has_twilio = serializers.SerializerMethodField()
    has_openai = serializers.SerializerMethodField()
    
    # Masked credential indicators
    woo_configured = serializers.SerializerMethodField()
    shopify_configured = serializers.SerializerMethodField()
    twilio_configured = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantSettings
        fields = [
            'tenant',
            'has_woocommerce',
            'has_shopify',
            'has_twilio',
            'has_openai',
            'woo_configured',
            'shopify_configured',
            'twilio_configured',
            'woo_store_url',
            'shopify_shop_domain',
            'stripe_customer_id',
            'stripe_payment_methods',
            'payout_method',
            'notification_settings',
            'feature_flags',
            'business_hours',
            'integrations_status',
            'branding',
            'compliance_settings',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['tenant', 'created_at', 'updated_at']
    
    def get_has_woocommerce(self, obj):
        """Check if WooCommerce is configured."""
        return obj.has_woocommerce_configured()
    
    def get_has_shopify(self, obj):
        """Check if Shopify is configured."""
        return obj.has_shopify_configured()
    
    def get_has_twilio(self, obj):
        """Check if Twilio is configured."""
        return obj.has_twilio_configured()
    
    def get_has_openai(self, obj):
        """Check if OpenAI is configured."""
        return bool(obj.openai_api_key)
    
    def get_woo_configured(self, obj):
        """Return masked WooCommerce configuration."""
        if not obj.has_woocommerce_configured():
            return None
        
        return {
            'store_url': obj.woo_store_url,
            'consumer_key_masked': self._mask_credential(obj.woo_consumer_key, prefix='ck_'),
            'has_webhook_secret': bool(obj.woo_webhook_secret)
        }
    
    def get_shopify_configured(self, obj):
        """Return masked Shopify configuration."""
        if not obj.has_shopify_configured():
            return None
        
        return {
            'shop_domain': obj.shopify_shop_domain,
            'has_access_token': bool(obj.shopify_access_token),
            'has_webhook_secret': bool(obj.shopify_webhook_secret)
        }
    
    def get_twilio_configured(self, obj):
        """Return masked Twilio configuration."""
        if not obj.has_twilio_configured():
            return None
        
        return {
            'sid_masked': self._mask_credential(obj.twilio_sid, prefix='AC'),
            'has_token': bool(obj.twilio_token),
            'has_webhook_secret': bool(obj.twilio_webhook_secret)
        }
    
    def _mask_credential(self, value, prefix=''):
        """Mask credential showing only last 4 characters."""
        if not value:
            return None
        
        if len(value) <= 4:
            return '****'
        
        return f"{prefix}****{value[-4:]}"


class WooCommerceCredentialsSerializer(serializers.Serializer):
    """Serializer for setting WooCommerce credentials."""
    
    store_url = serializers.URLField(required=True)
    consumer_key = serializers.CharField(required=True, min_length=10)
    consumer_secret = serializers.CharField(required=True, min_length=10)
    webhook_secret = serializers.CharField(required=False, allow_blank=True)
    test_connection = serializers.BooleanField(default=True)
    
    def validate(self, data):
        """Validate WooCommerce credentials by testing connection."""
        if data.get('test_connection', True):
            from apps.integrations.services.woo_service import WooService, WooServiceError
            
            try:
                service = WooService(
                    store_url=data['store_url'],
                    consumer_key=data['consumer_key'],
                    consumer_secret=data['consumer_secret']
                )
                # Test connection by fetching one product
                service.fetch_products_batch(page=1, per_page=1)
            except WooServiceError as e:
                raise serializers.ValidationError({
                    'non_field_errors': f'Failed to connect to WooCommerce: {str(e)}'
                })
        
        return data


class ShopifyCredentialsSerializer(serializers.Serializer):
    """Serializer for setting Shopify credentials."""
    
    shop_domain = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True, min_length=10)
    webhook_secret = serializers.CharField(required=False, allow_blank=True)
    test_connection = serializers.BooleanField(default=True)
    
    def validate_shop_domain(self, value):
        """Validate and normalize shop domain."""
        # Remove protocol if present
        value = value.replace('https://', '').replace('http://', '')
        # Ensure .myshopify.com suffix
        if not value.endswith('.myshopify.com'):
            if '.' not in value:
                value = f"{value}.myshopify.com"
        return value
    
    def validate(self, data):
        """Validate Shopify credentials by testing connection."""
        if data.get('test_connection', True):
            from apps.integrations.services.shopify_service import ShopifyService, ShopifyServiceError
            
            try:
                service = ShopifyService(
                    shop_domain=data['shop_domain'],
                    access_token=data['access_token']
                )
                # Test connection by fetching one product
                service.fetch_products_batch(page=1, per_page=1)
            except ShopifyServiceError as e:
                raise serializers.ValidationError({
                    'non_field_errors': f'Failed to connect to Shopify: {str(e)}'
                })
        
        return data


class TwilioCredentialsSerializer(serializers.Serializer):
    """Serializer for setting Twilio credentials."""
    
    sid = serializers.CharField(required=True, min_length=34, max_length=34)
    token = serializers.CharField(required=True, min_length=32)
    webhook_secret = serializers.CharField(required=False, allow_blank=True)
    
    def validate_sid(self, value):
        """Validate Twilio SID format."""
        if not value.startswith('AC'):
            raise serializers.ValidationError('Twilio SID must start with "AC"')
        return value


class OpenAICredentialsSerializer(serializers.Serializer):
    """Serializer for setting OpenAI credentials."""
    
    api_key = serializers.CharField(required=True, min_length=20)
    org_id = serializers.CharField(required=False, allow_blank=True)


class NotificationSettingsSerializer(serializers.Serializer):
    """Serializer for notification settings."""
    
    email = serializers.DictField(required=False)
    sms = serializers.DictField(required=False)
    in_app = serializers.DictField(required=False)
    quiet_hours = serializers.DictField(required=False)


class FeatureFlagsSerializer(serializers.Serializer):
    """Serializer for feature flags."""
    
    ai_responses_enabled = serializers.BooleanField(required=False)
    auto_handoff_enabled = serializers.BooleanField(required=False)
    product_recommendations = serializers.BooleanField(required=False)
    appointment_reminders = serializers.BooleanField(required=False)
    abandoned_cart_recovery = serializers.BooleanField(required=False)
    multi_language_support = serializers.BooleanField(required=False)


class BusinessHoursSerializer(serializers.Serializer):
    """Serializer for business hours."""
    
    monday = serializers.DictField(required=False)
    tuesday = serializers.DictField(required=False)
    wednesday = serializers.DictField(required=False)
    thursday = serializers.DictField(required=False)
    friday = serializers.DictField(required=False)
    saturday = serializers.DictField(required=False)
    sunday = serializers.DictField(required=False)


class BrandingSerializer(serializers.Serializer):
    """Serializer for branding settings."""
    
    business_name = serializers.CharField(required=False, max_length=255)
    logo_url = serializers.URLField(required=False, allow_blank=True)
    primary_color = serializers.CharField(required=False, max_length=7)
    welcome_message = serializers.CharField(required=False, max_length=500)
    footer_text = serializers.CharField(required=False, max_length=200)
    
    def validate_primary_color(self, value):
        """Validate hex color format."""
        if value and not value.startswith('#'):
            raise serializers.ValidationError('Color must be in hex format (#RRGGBB)')
        if value and len(value) != 7:
            raise serializers.ValidationError('Color must be 7 characters (#RRGGBB)')
        return value


class PaymentMethodSerializer(serializers.Serializer):
    """Serializer for payment method (read-only)."""
    
    id = serializers.CharField()
    last4 = serializers.CharField()
    brand = serializers.CharField()
    exp_month = serializers.IntegerField()
    exp_year = serializers.IntegerField()
    is_default = serializers.BooleanField()
