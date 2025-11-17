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
    
    def validate_store_url(self, value):
        """Validate and normalize WooCommerce store URL."""
        from apps.core.validators import InputValidator
        
        if not value or not value.strip():
            raise serializers.ValidationError('Store URL is required')
        
        value = value.strip()
        
        # Normalize URL
        normalized = InputValidator.normalize_url(value)
        
        # Validate URL format
        if not InputValidator.validate_url(normalized):
            raise serializers.ValidationError(
                'Please enter a valid store URL (e.g., https://example.com)'
            )
        
        return normalized
    
    def validate_shop_domain(self, value):
        """Validate and normalize shop domain."""
        if not value or not value.strip():
            raise serializers.ValidationError('Shop domain is required')
        
        value = value.strip()
        
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
    whatsapp_number = serializers.CharField(required=False, allow_blank=True)
    
    def validate_sid(self, value):
        """Validate Twilio SID format."""
        if not value or not value.strip():
            raise serializers.ValidationError('Twilio SID is required')
        
        value = value.strip()
        
        if not value.startswith('AC'):
            raise serializers.ValidationError('Twilio SID must start with "AC"')
        
        if len(value) != 34:
            raise serializers.ValidationError('Twilio SID must be 34 characters long')
        
        return value
    
    def validate_whatsapp_number(self, value):
        """Validate WhatsApp number format (E.164)."""
        from apps.core.validators import InputValidator
        
        if not value:
            return value
        
        value = value.strip()
        
        # Normalize to E.164 format
        normalized = InputValidator.normalize_phone_e164(value)
        
        # Validate E.164 format
        if not InputValidator.validate_phone_e164(normalized):
            raise serializers.ValidationError(
                'WhatsApp number must be in E.164 format (e.g., +1234567890)'
            )
        
        return normalized


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
    
    ai_agent_enabled = serializers.BooleanField(
        required=False,
        help_text="Enable AI-powered agent (uses LLM for intelligent responses)"
    )
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
        from apps.core.validators import InputValidator
        
        if not value:
            return value
        
        value = value.strip()
        
        # Ensure it starts with #
        if not value.startswith('#'):
            value = f'#{value}'
        
        # Validate hex color format
        if not InputValidator.validate_hex_color(value):
            raise serializers.ValidationError(
                'Color must be in hex format (e.g., #FF5733)'
            )
        
        return value


class PaymentMethodSerializer(serializers.Serializer):
    """Serializer for payment method (read-only)."""
    
    id = serializers.CharField()
    last4 = serializers.CharField()
    brand = serializers.CharField()
    exp_month = serializers.IntegerField()
    exp_year = serializers.IntegerField()
    is_default = serializers.BooleanField()


class AddPaymentMethodSerializer(serializers.Serializer):
    """Serializer for adding a payment method."""
    
    stripe_token = serializers.CharField(required=True, min_length=10)


class PayoutMethodSerializer(serializers.Serializer):
    """Serializer for updating payout method."""
    
    method = serializers.ChoiceField(
        choices=['bank_transfer', 'mobile_money', 'paypal'],
        required=True
    )
    details = serializers.DictField(required=True)
    
    def validate(self, data):
        """Validate required fields based on method type."""
        method = data['method']
        details = data['details']
        
        if method == 'bank_transfer':
            required_fields = ['account_number', 'routing_number', 'account_holder_name']
            for field in required_fields:
                if not details.get(field):
                    raise serializers.ValidationError({
                        'details': f"Missing required field for bank transfer: {field}"
                    })
        
        elif method == 'mobile_money':
            required_fields = ['phone_number', 'provider']
            for field in required_fields:
                if not details.get(field):
                    raise serializers.ValidationError({
                        'details': f"Missing required field for mobile money: {field}"
                    })
            
            # Validate phone number format
            phone_number = details['phone_number']
            if not phone_number.startswith('+'):
                raise serializers.ValidationError({
                    'details': 'Phone number must be in E.164 format (e.g., +1234567890)'
                })
        
        elif method == 'paypal':
            if not details.get('email'):
                raise serializers.ValidationError({
                    'details': 'Missing required field for PayPal: email'
                })
        
        return data


class APIKeySerializer(serializers.Serializer):
    """Serializer for API key (read-only, masked)."""
    
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    key_preview = serializers.CharField(read_only=True, help_text="First 8 characters of the key")
    created_at = serializers.DateTimeField(read_only=True)
    created_by = serializers.CharField(read_only=True, help_text="Email of user who created the key")
    last_used_at = serializers.DateTimeField(read_only=True, allow_null=True)


class APIKeyCreateSerializer(serializers.Serializer):
    """Serializer for creating a new API key."""
    
    name = serializers.CharField(
        required=True,
        max_length=100,
        help_text="Descriptive name for the API key"
    )
    
    def validate_name(self, value):
        """Validate name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("API key name cannot be empty")
        return value.strip()


class APIKeyResponseSerializer(serializers.Serializer):
    """Serializer for API key generation response (includes plain key once)."""
    
    message = serializers.CharField()
    api_key = serializers.CharField(help_text="Plain API key - save this now, it won't be shown again")
    key_id = serializers.CharField()
    name = serializers.CharField()
    key_preview = serializers.CharField()
    created_at = serializers.DateTimeField()
    warning = serializers.CharField()


class BusinessSettingsSerializer(serializers.Serializer):
    """
    Serializer for business settings.
    
    Includes timezone, business hours, quiet hours, and notification preferences.
    """
    
    timezone = serializers.CharField(required=False, max_length=50)
    business_hours = serializers.DictField(required=False)
    quiet_hours = serializers.DictField(required=False)
    notification_preferences = serializers.DictField(required=False)
    
    def validate_timezone(self, value):
        """Validate timezone against IANA timezone database."""
        if not value:
            return value
        
        try:
            import zoneinfo
            # Try to load the timezone to validate it exists
            zoneinfo.ZoneInfo(value)
            return value
        except (ImportError, zoneinfo.ZoneInfoNotFoundError):
            # Fallback to pytz if zoneinfo not available (Python < 3.9)
            try:
                import pytz
                if value not in pytz.all_timezones:
                    raise serializers.ValidationError(
                        f"Invalid timezone: {value}. Must be a valid IANA timezone (e.g., 'America/New_York')"
                    )
                return value
            except ImportError:
                raise serializers.ValidationError(
                    "Timezone validation not available. Please ensure pytz or zoneinfo is installed."
                )
    
    def validate_business_hours(self, value):
        """
        Validate business hours format.
        
        Expected format:
        {
            "monday": {"open": "09:00", "close": "17:00", "closed": false},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": false},
            ...
        }
        """
        if not value:
            return value
        
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day, hours in value.items():
            if day not in valid_days:
                raise serializers.ValidationError(
                    f"Invalid day: {day}. Must be one of: {', '.join(valid_days)}"
                )
            
            if not isinstance(hours, dict):
                raise serializers.ValidationError(
                    f"Hours for {day} must be a dictionary with 'open', 'close', and 'closed' keys"
                )
            
            # If day is marked as closed, skip time validation
            if hours.get('closed', False):
                continue
            
            # Validate time format (HH:MM)
            for time_key in ['open', 'close']:
                if time_key not in hours:
                    raise serializers.ValidationError(
                        f"Missing '{time_key}' time for {day}"
                    )
                
                time_str = hours[time_key]
                if not isinstance(time_str, str):
                    raise serializers.ValidationError(
                        f"Time for {day}.{time_key} must be a string in HH:MM format"
                    )
                
                # Validate HH:MM format
                try:
                    parts = time_str.split(':')
                    if len(parts) != 2:
                        raise ValueError()
                    
                    hour = int(parts[0])
                    minute = int(parts[1])
                    
                    if not (0 <= hour <= 23):
                        raise ValueError("Hour must be between 0 and 23")
                    if not (0 <= minute <= 59):
                        raise ValueError("Minute must be between 0 and 59")
                    
                except (ValueError, AttributeError) as e:
                    raise serializers.ValidationError(
                        f"Invalid time format for {day}.{time_key}: {time_str}. Must be HH:MM (e.g., '09:00')"
                    )
        
        return value
    
    def validate_quiet_hours(self, value):
        """
        Validate quiet hours format.
        
        Expected format:
        {
            "enabled": true,
            "start": "22:00",
            "end": "08:00"
        }
        """
        if not value:
            return value
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Quiet hours must be a dictionary")
        
        # If quiet hours are disabled, no need to validate times
        if not value.get('enabled', False):
            return value
        
        # Validate start and end times
        for time_key in ['start', 'end']:
            if time_key not in value:
                raise serializers.ValidationError(
                    f"Missing '{time_key}' time for quiet hours"
                )
            
            time_str = value[time_key]
            if not isinstance(time_str, str):
                raise serializers.ValidationError(
                    f"Quiet hours {time_key} must be a string in HH:MM format"
                )
            
            # Validate HH:MM format
            try:
                parts = time_str.split(':')
                if len(parts) != 2:
                    raise ValueError()
                
                hour = int(parts[0])
                minute = int(parts[1])
                
                if not (0 <= hour <= 23):
                    raise ValueError("Hour must be between 0 and 23")
                if not (0 <= minute <= 59):
                    raise ValueError("Minute must be between 0 and 59")
                
            except (ValueError, AttributeError):
                raise serializers.ValidationError(
                    f"Invalid time format for quiet hours {time_key}: {time_str}. Must be HH:MM (e.g., '22:00')"
                )
        
        # Note: We allow overnight ranges (e.g., 22:00 to 08:00)
        # The application logic should handle this correctly
        
        return value
    
    def validate_notification_preferences(self, value):
        """
        Validate notification preferences format.
        
        Expected format:
        {
            "email": {
                "order_received": true,
                "low_stock": true,
                "appointment_booked": true
            },
            "sms": {
                "order_received": false,
                "low_stock": true
            },
            "in_app": {
                "order_received": true,
                "appointment_booked": true
            }
        }
        """
        if not value:
            return value
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Notification preferences must be a dictionary")
        
        valid_channels = ['email', 'sms', 'in_app']
        
        for channel, preferences in value.items():
            if channel not in valid_channels:
                raise serializers.ValidationError(
                    f"Invalid notification channel: {channel}. Must be one of: {', '.join(valid_channels)}"
                )
            
            if not isinstance(preferences, dict):
                raise serializers.ValidationError(
                    f"Preferences for {channel} must be a dictionary"
                )
            
            # Validate that all values are booleans
            for event, enabled in preferences.items():
                if not isinstance(enabled, bool):
                    raise serializers.ValidationError(
                        f"Notification preference for {channel}.{event} must be a boolean"
                    )
        
        return value


class TogetherAICredentialsSerializer(serializers.Serializer):
    """Serializer for setting Together AI credentials."""
    
    api_key = serializers.CharField(required=True, min_length=20)
    test_connection = serializers.BooleanField(default=False)
    
    def validate(self, data):
        """Validate Together AI credentials by testing connection."""
        if data.get('test_connection', False):
            from apps.bot.services.llm import TogetherAIProvider
            
            try:
                provider = TogetherAIProvider(api_key=data['api_key'])
                # Test connection by getting available models
                models = provider.get_available_models()
                if not models:
                    raise serializers.ValidationError({
                        'non_field_errors': 'Failed to retrieve models from Together AI'
                    })
            except Exception as e:
                raise serializers.ValidationError({
                    'non_field_errors': f'Failed to connect to Together AI: {str(e)}'
                })
        
        return data


class LLMConfigurationSerializer(serializers.Serializer):
    """
    Serializer for LLM configuration.
    
    Allows tenants to configure their LLM provider, model selection,
    and related settings for the AI agent.
    """
    
    llm_provider = serializers.ChoiceField(
        choices=['openai', 'together'],
        default='openai',
        help_text="LLM provider to use (openai, together)"
    )
    llm_timeout = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=1.0,
        max_value=300.0,
        help_text="Timeout in seconds for LLM API calls (1-300)"
    )
    llm_max_retries = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=5,
        help_text="Maximum number of retries for LLM API calls (0-5)"
    )
    
    def validate(self, data):
        """Validate LLM configuration."""
        provider = data.get('llm_provider', 'openai')
        
        # Get tenant from context
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError('Tenant context is required')
        
        # Check if API key is configured for the selected provider
        settings = tenant.settings
        
        if provider == 'openai':
            if not settings.openai_api_key:
                raise serializers.ValidationError({
                    'llm_provider': 'OpenAI API key is not configured. Please configure OpenAI credentials first.'
                })
        elif provider == 'together':
            if not settings.together_api_key:
                raise serializers.ValidationError({
                    'llm_provider': 'Together AI API key is not configured. Please configure Together AI credentials first.'
                })
        
        return data


class LLMProviderInfoSerializer(serializers.Serializer):
    """
    Serializer for LLM provider information.
    
    Returns available providers and their configuration status.
    """
    
    provider = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    is_configured = serializers.BooleanField(read_only=True)
    available_models = serializers.ListField(
        child=serializers.DictField(),
        read_only=True
    )


class LLMModelInfoSerializer(serializers.Serializer):
    """
    Serializer for LLM model information.
    
    Returns details about a specific model including pricing and capabilities.
    """
    
    name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    provider = serializers.CharField(read_only=True)
    context_window = serializers.IntegerField(read_only=True)
    input_cost_per_1k = serializers.DecimalField(
        max_digits=10,
        decimal_places=6,
        read_only=True
    )
    output_cost_per_1k = serializers.DecimalField(
        max_digits=10,
        decimal_places=6,
        read_only=True
    )
    capabilities = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    description = serializers.CharField(read_only=True)
