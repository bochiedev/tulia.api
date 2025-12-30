"""
Management command to check platform settings configuration.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.platform_settings import PlatformSettings
import json


class Command(BaseCommand):
    help = 'Check platform settings configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['table', 'json'],
            default='table',
            help='Output format (default: table)'
        )

    def handle(self, *args, **options):
        """Check and display platform settings."""
        
        self.stdout.write(
            self.style.SUCCESS('🔧 Tulia AI Platform Settings Check')
        )
        self.stdout.write('=' * 50)
        
        # Get all settings
        all_settings = PlatformSettings.get_all_settings()
        
        if options['format'] == 'json':
            self.stdout.write(json.dumps(all_settings, indent=2))
            return
        
        # Display in table format
        self._display_ai_settings()
        self._display_service_providers()
        self._display_payment_settings()
        self._display_security_settings()
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(
            self.style.SUCCESS('✅ Platform settings check complete')
        )

    def _display_ai_settings(self):
        """Display AI provider settings."""
        self.stdout.write('\n🤖 AI Provider Configuration:')
        
        ai_config = PlatformSettings.get_ai_provider_config()
        provider = ai_config.get('provider')
        
        if provider:
            self.stdout.write(f"  Provider: {provider}")
            self.stdout.write(f"  Model: {ai_config.get('model', 'N/A')}")
            self.stdout.write(f"  API Key: {'✅ Configured' if ai_config.get('api_key') else '❌ Missing'}")
        else:
            self.stdout.write(self.style.WARNING("  ❌ No AI provider configured"))
            self.stdout.write("     Add OPENAI_API_KEY, GOOGLE_API_KEY, or TOGETHER_API_KEY to .env")

    def _display_service_providers(self):
        """Display service provider settings."""
        self.stdout.write('\n📧 Service Providers:')
        
        # Email
        email_config = PlatformSettings.get_email_config()
        provider_source = self._get_setting_source('email_provider')
        self.stdout.write(f"  Email Provider: {email_config['provider']} {provider_source}")
        if email_config['provider'] == 'sendgrid':
            api_key_status = '✅ Configured' if email_config.get('api_key') else '❌ Missing'
            api_key_source = self._get_setting_source('sendgrid_api_key')
            self.stdout.write(f"    SendGrid API Key: {api_key_status} {api_key_source}")
        elif email_config['provider'] == 'console':
            self.stdout.write("    ✅ Console mode (development)")
        
        from_email_source = self._get_setting_source('default_from_email')
        self.stdout.write(f"    From Email: {email_config['from_email']} {from_email_source}")
        
        # SMS
        sms_config = PlatformSettings.get_sms_config()
        sms_source = self._get_setting_source('sms_provider')
        self.stdout.write(f"  SMS Provider: {sms_config['provider']} {sms_source}")
        if sms_config['provider'] == 'africastalking':
            username_status = '✅ Configured' if sms_config.get('username') else '❌ Missing'
            api_key_status = '✅ Configured' if sms_config.get('api_key') else '❌ Missing'
            username_source = self._get_setting_source('africastalking_username')
            api_key_source = self._get_setting_source('africastalking_api_key')
            self.stdout.write(f"    Username: {username_status} {username_source}")
            self.stdout.write(f"    API Key: {api_key_status} {api_key_source}")
        
        # WhatsApp
        whatsapp_provider = PlatformSettings.get_whatsapp_provider()
        whatsapp_source = self._get_setting_source('whatsapp_provider')
        self.stdout.write(f"  WhatsApp Provider: {whatsapp_provider} {whatsapp_source}")
        if whatsapp_provider == 'twilio':
            self.stdout.write("    Note: Twilio credentials configured per tenant")
    
    def _get_setting_source(self, key: str) -> str:
        """Get the source of a setting (database or environment)."""
        try:
            from apps.core.models import PlatformSetting
            if PlatformSetting.objects.filter(key=key).exists():
                return "(DB)"
            else:
                return "(ENV)"
        except:
            return "(ENV)"

    def _display_payment_settings(self):
        """Display payment configuration."""
        self.stdout.write('\n💳 Payment Configuration:')
        
        collection_mode = PlatformSettings.get_payment_collection_mode()
        self.stdout.write(f"  Collection Mode: {collection_mode}")
        
        if collection_mode == 'platform_collect':
            transaction_fee = PlatformSettings.get_platform_transaction_fee()
            withdrawal_fees = PlatformSettings.get_withdrawal_fees()
            min_withdrawal = PlatformSettings.get_min_withdrawal_amount()
            
            self.stdout.write(f"  Platform Transaction Fee: {transaction_fee}%")
            self.stdout.write(f"  Withdrawal Flat Fee: {withdrawal_fees['flat_fee']}")
            self.stdout.write(f"  Withdrawal Percentage Fee: {withdrawal_fees['percentage_fee']}%")
            self.stdout.write(f"  Minimum Withdrawal: {min_withdrawal}")
            
            # Check platform payment credentials
            self.stdout.write("  Platform Payment Credentials:")
            
            # M-Pesa
            mpesa_creds = PlatformSettings.get_platform_payment_credentials('mpesa')
            mpesa_status = '✅ Configured' if mpesa_creds.get('consumer_key') else '❌ Missing'
            mpesa_source = self._get_payment_credential_source('mpesa')
            self.stdout.write(f"    M-Pesa: {mpesa_status} {mpesa_source}")
            
            # Stripe
            stripe_creds = PlatformSettings.get_platform_payment_credentials('stripe')
            stripe_status = '✅ Configured' if stripe_creds.get('secret_key') else '❌ Missing'
            stripe_source = self._get_payment_credential_source('stripe')
            self.stdout.write(f"    Stripe: {stripe_status} {stripe_source}")
            
            # Paystack
            paystack_creds = PlatformSettings.get_platform_payment_credentials('paystack')
            paystack_status = '✅ Configured' if paystack_creds.get('secret_key') else '❌ Missing'
            paystack_source = self._get_payment_credential_source('paystack')
            self.stdout.write(f"    Paystack: {paystack_status} {paystack_source}")
    
    def _get_payment_credential_source(self, provider: str) -> str:
        """Get the source of payment credentials (database or environment)."""
        try:
            from apps.core.models import PlatformPaymentCredential
            from django.conf import settings
            
            environment = 'production' if not getattr(settings, 'DEBUG', True) else 'sandbox'
            
            if PlatformPaymentCredential.objects.filter(
                provider=provider, 
                environment=environment, 
                is_active=True
            ).exists():
                return "(DB)"
            else:
                return "(ENV)"
        except:
            return "(ENV)"

    def _display_security_settings(self):
        """Display security-related settings."""
        self.stdout.write('\n🔒 Security Settings:')
        
        # Check required keys
        secret_key_status = '✅ Configured' if getattr(settings, 'SECRET_KEY', '') else '❌ Missing'
        jwt_key_status = '✅ Configured' if getattr(settings, 'JWT_SECRET_KEY', '') else '❌ Missing'
        encryption_key_status = '✅ Configured' if getattr(settings, 'ENCRYPTION_KEY', '') else '❌ Missing'
        
        self.stdout.write(f"  Django SECRET_KEY: {secret_key_status}")
        self.stdout.write(f"  JWT_SECRET_KEY: {jwt_key_status}")
        self.stdout.write(f"  ENCRYPTION_KEY: {encryption_key_status}")
        
        # Debug mode warning
        if getattr(settings, 'DEBUG', False):
            self.stdout.write(self.style.WARNING("  ⚠️  DEBUG=True (disable for production)"))
        else:
            self.stdout.write("  ✅ DEBUG=False (production ready)")