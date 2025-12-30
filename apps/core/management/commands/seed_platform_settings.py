"""
Management command to seed initial platform settings.
"""
from django.core.management.base import BaseCommand
from apps.core.models import PlatformSetting, PlatformPaymentCredential


class Command(BaseCommand):
    help = 'Seed initial platform settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing settings'
        )

    def handle(self, *args, **options):
        """Seed platform settings."""
        
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS('🌱 Seeding platform settings...')
        )
        
        # Define initial settings
        initial_settings = [
            # Email Settings
            {
                'key': 'email_provider',
                'value': 'console',
                'category': 'email',
                'setting_type': 'string',
                'description': 'Email service provider (console, sendgrid, ses, mailgun)',
                'is_sensitive': False,
            },
            {
                'key': 'default_from_email',
                'value': 'noreply@trytulia.com',
                'category': 'email',
                'setting_type': 'string',
                'description': 'Default from email address',
                'is_sensitive': False,
            },
            
            # SMS Settings
            {
                'key': 'sms_provider',
                'value': 'console',
                'category': 'sms',
                'setting_type': 'string',
                'description': 'SMS service provider (console, africastalking, twilio_sms)',
                'is_sensitive': False,
            },
            
            # Payment Settings
            {
                'key': 'payment_collection_mode',
                'value': 'platform_collect',
                'category': 'payment',
                'setting_type': 'string',
                'description': 'Payment collection mode (platform_collect, direct_tenant)',
                'is_sensitive': False,
            },
            {
                'key': 'platform_transaction_fee_percent',
                'value': '2.5',
                'category': 'payment',
                'setting_type': 'float',
                'description': 'Platform transaction fee percentage',
                'is_sensitive': False,
            },
            {
                'key': 'withdrawal_fee_flat',
                'value': '50.0',
                'category': 'payment',
                'setting_type': 'float',
                'description': 'Flat withdrawal fee amount',
                'is_sensitive': False,
            },
            {
                'key': 'withdrawal_fee_percent',
                'value': '1.0',
                'category': 'payment',
                'setting_type': 'float',
                'description': 'Withdrawal fee percentage',
                'is_sensitive': False,
            },
            {
                'key': 'min_withdrawal_amount',
                'value': '1000.0',
                'category': 'payment',
                'setting_type': 'float',
                'description': 'Minimum withdrawal amount',
                'is_sensitive': False,
            },
            
            # General Settings
            {
                'key': 'whatsapp_provider',
                'value': 'twilio',
                'category': 'general',
                'setting_type': 'string',
                'description': 'WhatsApp service provider (twilio, meta_business)',
                'is_sensitive': False,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for setting_data in initial_settings:
            key = setting_data['key']
            
            if PlatformSetting.objects.filter(key=key).exists():
                if force:
                    PlatformSetting.objects.filter(key=key).update(**setting_data)
                    updated_count += 1
                    self.stdout.write(f"  ✅ Updated: {key}")
                else:
                    self.stdout.write(f"  ⏭️  Skipped: {key} (already exists)")
            else:
                PlatformSetting.objects.create(**setting_data)
                created_count += 1
                self.stdout.write(f"  ✅ Created: {key}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Platform settings seeded successfully!'
                f'\n   Created: {created_count}'
                f'\n   Updated: {updated_count}'
            )
        )
        
        # Show next steps
        self.stdout.write(
            self.style.WARNING(
                '\n📝 Next Steps:'
                '\n1. Configure API keys in Django Admin → Core → Platform Settings'
                '\n2. Set up payment credentials in Django Admin → Core → Platform Payment Credentials'
                '\n3. Run: python manage.py check_platform_settings'
            )
        )