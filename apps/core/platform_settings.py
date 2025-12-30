"""
Platform-wide settings management.

This module handles platform-level configurations that can be changed
without code deployment. Settings are stored in the database with
environment variables as fallbacks.
"""
from django.conf import settings
from django.core.cache import cache
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PlatformSettings:
    """
    Centralized platform settings management.
    
    Provides a unified interface for platform-wide configurations.
    Uses database settings with environment variable fallbacks.
    """
    
    # Cache settings for 5 minutes
    CACHE_TTL = 300
    CACHE_KEY_PREFIX = "platform_settings"
    
    @classmethod
    def _get_db_setting(cls, key: str, default=None):
        """Get setting from database with caching."""
        try:
            from apps.core.models import PlatformSetting
            return PlatformSetting.objects.get_setting(key, default)
        except Exception as e:
            logger.warning(f"Failed to get database setting '{key}': {e}")
            return default
    
    @classmethod
    def _get_env_setting(cls, key: str, default=None):
        """Get setting from environment variables."""
        return getattr(settings, key.upper(), default)
    
    @classmethod
    def _get_setting(cls, key: str, env_key: str = None, default=None):
        """
        Get setting with database-first, environment fallback strategy.
        
        Args:
            key: Database setting key
            env_key: Environment variable key (defaults to key.upper())
            default: Default value if not found
        """
        if env_key is None:
            env_key = key.upper()
        
        # Try database first
        db_value = cls._get_db_setting(key)
        if db_value is not None:
            return db_value
        
        # Fallback to environment
        env_value = cls._get_env_setting(env_key, default)
        return env_value
    
    @classmethod
    def get_email_provider(cls) -> str:
        """Get the current email service provider."""
        return cls._get_setting('email_provider', 'EMAIL_PROVIDER', 'console')
    
    @classmethod
    def get_sms_provider(cls) -> str:
        """Get the current SMS service provider."""
        return cls._get_setting('sms_provider', 'SMS_PROVIDER', 'console')
    
    @classmethod
    def get_whatsapp_provider(cls) -> str:
        """Get the current WhatsApp service provider."""
        return cls._get_setting('whatsapp_provider', 'WHATSAPP_PROVIDER', 'twilio')
    
    @classmethod
    def get_payment_collection_mode(cls) -> str:
        """
        Get payment collection mode.
        
        Returns:
            'platform_collect': Platform collects payments, tenants withdraw
            'direct_tenant': Tenants collect payments directly
        """
        return cls._get_setting('payment_collection_mode', 'PAYMENT_COLLECTION_MODE', 'platform_collect')
    
    @classmethod
    def get_platform_transaction_fee(cls) -> float:
        """Get platform transaction fee percentage."""
        value = cls._get_setting('platform_transaction_fee_percent', 'PLATFORM_TRANSACTION_FEE_PERCENT', '2.5')
        return float(value)
    
    @classmethod
    def get_withdrawal_fees(cls) -> Dict[str, float]:
        """Get withdrawal fee structure."""
        flat_fee = cls._get_setting('withdrawal_fee_flat', 'WITHDRAWAL_FEE_FLAT', '50.0')
        percentage_fee = cls._get_setting('withdrawal_fee_percent', 'WITHDRAWAL_FEE_PERCENT', '1.0')
        
        return {
            'flat_fee': float(flat_fee),
            'percentage_fee': float(percentage_fee),
        }
    
    @classmethod
    def get_min_withdrawal_amount(cls) -> float:
        """Get minimum withdrawal amount."""
        value = cls._get_setting('min_withdrawal_amount', 'MIN_WITHDRAWAL_AMOUNT', '1000.0')
        return float(value)
    
    @classmethod
    def get_ai_provider_config(cls) -> Dict[str, Any]:
        """
        Get AI provider configuration.
        
        Returns the configured AI provider and its settings.
        """
        config = {}
        
        # Check database settings first, then environment
        openai_key = cls._get_setting('openai_api_key', 'OPENAI_API_KEY')
        google_key = cls._get_setting('google_api_key', 'GOOGLE_API_KEY')
        together_key = cls._get_setting('together_api_key', 'TOGETHER_API_KEY')
        
        # Check OpenAI
        if openai_key:
            config['provider'] = 'openai'
            config['api_key'] = openai_key
            config['model'] = cls._get_setting('openai_model', 'OPENAI_MODEL', 'gpt-4o-mini')
            return config
        
        # Check Google Gemini
        if google_key:
            config['provider'] = 'gemini'
            config['api_key'] = google_key
            config['model'] = cls._get_setting('gemini_model', 'GEMINI_MODEL', 'gemini-1.5-flash')
            return config
        
        # Check Together AI
        if together_key:
            config['provider'] = 'together'
            config['api_key'] = together_key
            config['model'] = cls._get_setting('together_model', 'TOGETHER_MODEL', 'meta-llama/Llama-2-7b-chat-hf')
            return config
        
        # No provider configured
        config['provider'] = None
        logger.warning("No AI provider configured. Set API keys in database or environment")
        return config
    
    @classmethod
    def get_email_config(cls) -> Dict[str, Any]:
        """Get email service configuration."""
        provider = cls.get_email_provider()
        
        if provider == 'sendgrid':
            return {
                'provider': 'sendgrid',
                'api_key': cls._get_setting('sendgrid_api_key', 'SENDGRID_API_KEY', ''),
                'from_email': cls._get_setting('default_from_email', 'DEFAULT_FROM_EMAIL', 'noreply@trytulia.com'),
            }
        elif provider == 'console':
            return {
                'provider': 'console',
                'from_email': cls._get_setting('default_from_email', 'DEFAULT_FROM_EMAIL', 'noreply@trytulia.com'),
            }
        else:
            return {
                'provider': provider,
                'from_email': cls._get_setting('default_from_email', 'DEFAULT_FROM_EMAIL', 'noreply@trytulia.com'),
            }
    
    @classmethod
    def get_sms_config(cls) -> Dict[str, Any]:
        """Get SMS service configuration."""
        provider = cls.get_sms_provider()
        
        if provider == 'africastalking':
            return {
                'provider': 'africastalking',
                'username': cls._get_setting('africastalking_username', 'AFRICASTALKING_USERNAME', ''),
                'api_key': cls._get_setting('africastalking_api_key', 'AFRICASTALKING_API_KEY', ''),
            }
        elif provider == 'console':
            return {
                'provider': 'console',
            }
        else:
            return {
                'provider': provider,
            }
    
    @classmethod
    def is_platform_collect_mode(cls) -> bool:
        """Check if platform is in collect mode (vs direct tenant)."""
        return cls.get_payment_collection_mode() == 'platform_collect'
    
    @classmethod
    def calculate_platform_fee(cls, amount: float) -> float:
        """Calculate platform fee for a transaction amount."""
        if not cls.is_platform_collect_mode():
            return 0.0
        
        fee_percent = cls.get_platform_transaction_fee()
        return (amount * fee_percent) / 100
    
    @classmethod
    def calculate_withdrawal_fee(cls, amount: float) -> float:
        """Calculate withdrawal fee for a given amount."""
        fees = cls.get_withdrawal_fees()
        flat_fee = fees['flat_fee']
        percentage_fee = (amount * fees['percentage_fee']) / 100
        
        return flat_fee + percentage_fee
    
    @classmethod
    def get_platform_payment_credentials(cls, provider: str, environment: str = None) -> Dict[str, Any]:
        """
        Get platform payment credentials for a specific provider.
        
        Args:
            provider: Payment provider name (mpesa, stripe, paystack)
            environment: Environment (sandbox/production), auto-detected if None
        
        Returns:
            Dictionary with provider credentials
        """
        try:
            from apps.core.models import PlatformPaymentCredential
            
            # Auto-detect environment if not provided
            if environment is None:
                environment = 'production' if not getattr(settings, 'DEBUG', True) else 'sandbox'
            
            # Try to get from database first
            try:
                credential = PlatformPaymentCredential.objects.get(
                    provider=provider,
                    environment=environment,
                    is_active=True
                )
                
                if provider == 'mpesa':
                    return {
                        'consumer_key': credential.api_key,
                        'consumer_secret': credential.api_secret,
                        'shortcode': credential.get_config_value('shortcode', ''),
                        'passkey': credential.get_config_value('passkey', ''),
                        'environment': environment,
                    }
                elif provider == 'stripe':
                    return {
                        'secret_key': credential.api_key,
                        'publishable_key': credential.get_config_value('publishable_key', ''),
                        'webhook_secret': credential.get_config_value('webhook_secret', ''),
                    }
                elif provider == 'paystack':
                    return {
                        'secret_key': credential.api_key,
                        'public_key': credential.get_config_value('public_key', ''),
                    }
                    
            except PlatformPaymentCredential.DoesNotExist:
                # Fallback to environment variables
                pass
                
        except Exception as e:
            logger.warning(f"Failed to get platform payment credentials from database: {e}")
        
        # Fallback to environment variables
        if provider == 'mpesa':
            return {
                'consumer_key': getattr(settings, 'PLATFORM_MPESA_CONSUMER_KEY', ''),
                'consumer_secret': getattr(settings, 'PLATFORM_MPESA_CONSUMER_SECRET', ''),
                'shortcode': getattr(settings, 'PLATFORM_MPESA_SHORTCODE', ''),
                'passkey': getattr(settings, 'PLATFORM_MPESA_PASSKEY', ''),
                'environment': getattr(settings, 'PLATFORM_MPESA_ENVIRONMENT', 'sandbox'),
            }
        elif provider == 'stripe':
            return {
                'secret_key': getattr(settings, 'PLATFORM_STRIPE_SECRET_KEY', ''),
                'publishable_key': getattr(settings, 'PLATFORM_STRIPE_PUBLISHABLE_KEY', ''),
                'webhook_secret': getattr(settings, 'PLATFORM_STRIPE_WEBHOOK_SECRET', ''),
            }
        elif provider == 'paystack':
            return {
                'secret_key': getattr(settings, 'PLATFORM_PAYSTACK_SECRET_KEY', ''),
                'public_key': getattr(settings, 'PLATFORM_PAYSTACK_PUBLIC_KEY', ''),
            }
        else:
            return {}
    
    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """Get all platform settings as a dictionary."""
        return {
            'email_provider': cls.get_email_provider(),
            'sms_provider': cls.get_sms_provider(),
            'whatsapp_provider': cls.get_whatsapp_provider(),
            'payment_collection_mode': cls.get_payment_collection_mode(),
            'platform_transaction_fee': cls.get_platform_transaction_fee(),
            'withdrawal_fees': cls.get_withdrawal_fees(),
            'min_withdrawal_amount': cls.get_min_withdrawal_amount(),
            'ai_provider': cls.get_ai_provider_config(),
            'email_config': cls.get_email_config(),
            'sms_config': cls.get_sms_config(),
        }


# Convenience functions for common operations
def get_current_ai_provider() -> Optional[str]:
    """Get the currently configured AI provider name."""
    config = PlatformSettings.get_ai_provider_config()
    return config.get('provider')


def is_ai_provider_configured() -> bool:
    """Check if any AI provider is configured."""
    return get_current_ai_provider() is not None


def get_platform_fee_for_amount(amount: float) -> float:
    """Calculate platform fee for a transaction amount."""
    return PlatformSettings.calculate_platform_fee(amount)


def can_tenant_withdraw(amount: float) -> bool:
    """Check if tenant can withdraw the specified amount."""
    min_amount = PlatformSettings.get_min_withdrawal_amount()
    return amount >= min_amount