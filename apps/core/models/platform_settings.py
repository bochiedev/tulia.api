"""
Platform-wide settings model.

Stores configurable platform settings in the database with Django admin interface.
Environment variables serve as fallbacks when database settings don't exist.
"""
from django.db import models
from django.core.cache import cache
from apps.core.models import BaseModel
from apps.core.fields import EncryptedCharField
import logging

logger = logging.getLogger(__name__)


class PlatformSettingsManager(models.Manager):
    """Manager for platform settings with caching."""
    
    def get_setting(self, key: str, default=None):
        """Get a platform setting with caching."""
        cache_key = f"platform_setting:{key}"
        
        # Try cache first
        value = cache.get(cache_key)
        if value is not None:
            return value
        
        # Try database
        try:
            setting = self.get(key=key)
            value = setting.value
            # Cache for 5 minutes
            cache.set(cache_key, value, 300)
            return value
        except PlatformSetting.DoesNotExist:
            return default
    
    def set_setting(self, key: str, value: str, description: str = ""):
        """Set a platform setting and update cache."""
        setting, created = self.update_or_create(
            key=key,
            defaults={
                'value': value,
                'description': description
            }
        )
        
        # Update cache
        cache_key = f"platform_setting:{key}"
        cache.set(cache_key, value, 300)
        
        return setting
    
    def clear_cache(self, key: str = None):
        """Clear platform settings cache."""
        if key:
            cache_key = f"platform_setting:{key}"
            cache.delete(cache_key)
        else:
            # Clear all platform settings cache
            # This is a simple approach - in production you might want a more sophisticated cache invalidation
            cache.clear()


class PlatformSetting(BaseModel):
    """
    Platform-wide configuration settings.
    
    Stores settings that can be changed without code deployment.
    Supports encrypted values for sensitive data like API keys.
    """
    
    SETTING_TYPES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('encrypted', 'Encrypted String'),
        ('json', 'JSON Object'),
    ]
    
    CATEGORIES = [
        ('email', 'Email Service'),
        ('sms', 'SMS Service'),
        ('ai', 'AI Provider'),
        ('payment', 'Payment Settings'),
        ('security', 'Security'),
        ('general', 'General'),
    ]
    
    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Setting key (e.g., 'email_provider', 'sendgrid_api_key')"
    )
    
    value = models.TextField(
        help_text="Setting value (will be encrypted if setting_type is 'encrypted')"
    )
    
    setting_type = models.CharField(
        max_length=20,
        choices=SETTING_TYPES,
        default='string',
        help_text="Data type of the setting value"
    )
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORIES,
        default='general',
        help_text="Setting category for organization"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of what this setting controls"
    )
    
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Whether this setting contains sensitive data (API keys, passwords)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this setting is currently active"
    )
    
    objects = PlatformSettingsManager()
    
    class Meta:
        db_table = 'platform_settings'
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.key} = {self.masked_value}"
    
    @property
    def masked_value(self):
        """Return masked value for sensitive settings."""
        if self.is_sensitive and self.value:
            if len(self.value) > 8:
                return f"{self.value[:4]}...{self.value[-4:]}"
            else:
                return "***"
        return self.value
    
    def get_typed_value(self):
        """Return value converted to the appropriate Python type."""
        if not self.value:
            return None
        
        try:
            if self.setting_type == 'integer':
                return int(self.value)
            elif self.setting_type == 'float':
                return float(self.value)
            elif self.setting_type == 'boolean':
                return self.value.lower() in ('true', '1', 'yes', 'on')
            elif self.setting_type == 'json':
                import json
                return json.loads(self.value)
            else:  # string or encrypted
                return self.value
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting setting {self.key} to {self.setting_type}: {e}")
            return self.value
    
    def save(self, *args, **kwargs):
        """Save setting and clear cache."""
        super().save(*args, **kwargs)
        
        # Clear cache for this setting
        cache_key = f"platform_setting:{self.key}"
        cache.delete(cache_key)


class PlatformPaymentCredential(BaseModel):
    """
    Platform payment provider credentials.
    
    Stores encrypted credentials for payment providers that the platform
    uses to collect payments on behalf of tenants.
    """
    
    PROVIDERS = [
        ('mpesa', 'M-Pesa'),
        ('stripe', 'Stripe'),
        ('paystack', 'Paystack'),
        ('pesapal', 'Pesapal'),
    ]
    
    ENVIRONMENTS = [
        ('sandbox', 'Sandbox/Test'),
        ('production', 'Production'),
    ]
    
    provider = models.CharField(
        max_length=20,
        choices=PROVIDERS,
        help_text="Payment provider name"
    )
    
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENTS,
        default='sandbox',
        help_text="Environment (sandbox or production)"
    )
    
    # Generic credential fields (encrypted)
    api_key = EncryptedCharField(
        max_length=500,
        blank=True,
        help_text="Primary API key or consumer key"
    )
    
    api_secret = EncryptedCharField(
        max_length=500,
        blank=True,
        help_text="API secret or consumer secret"
    )
    
    additional_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific configuration (shortcode, passkey, etc.)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether these credentials are currently active"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description or notes about these credentials"
    )
    
    class Meta:
        db_table = 'platform_payment_credentials'
        unique_together = [['provider', 'environment']]
        ordering = ['provider', 'environment']
        indexes = [
            models.Index(fields=['provider', 'environment', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_provider_display()} ({self.get_environment_display()})"
    
    @property
    def masked_api_key(self):
        """Return masked API key for display."""
        if self.api_key and len(self.api_key) > 8:
            return f"{self.api_key[:4]}...{self.api_key[-4:]}"
        return "***" if self.api_key else ""
    
    def get_config_value(self, key: str, default=None):
        """Get a value from additional_config."""
        return self.additional_config.get(key, default)
    
    def set_config_value(self, key: str, value):
        """Set a value in additional_config."""
        if not self.additional_config:
            self.additional_config = {}
        self.additional_config[key] = value