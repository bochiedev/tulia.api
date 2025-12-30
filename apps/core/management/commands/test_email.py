"""
Management command to test email functionality.
"""
from django.core.management.base import BaseCommand
from apps.core.services.email_service import send_welcome_email, EmailService


class Command(BaseCommand):
    help = 'Test email functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email address to send test email to'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Test User',
            help='Name for the test email'
        )
        parser.add_argument(
            '--type',
            choices=['welcome', 'raw'],
            default='welcome',
            help='Type of test email to send'
        )

    def handle(self, *args, **options):
        """Send test email."""
        
        email = options['email']
        name = options['name']
        email_type = options['type']
        
        self.stdout.write(
            self.style.SUCCESS(f'📧 Testing email service...')
        )
        
        try:
            if email_type == 'welcome':
                success = send_welcome_email(
                    user_email=email,
                    user_name=name,
                    verification_url="https://app.trytulia.com/verify-email?token=test123"
                )
                email_desc = "welcome email with verification"
            else:
                success = EmailService.send_email(
                    to_emails=[email],
                    subject="Test Email from Tulia AI",
                    html_content="<h1>Hello!</h1><p>This is a test email from Tulia AI.</p>",
                    text_content="Hello!\n\nThis is a test email from Tulia AI."
                )
                email_desc = "raw test email"
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Successfully sent {email_desc} to {email}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to send {email_desc} to {email}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'💥 Error sending email: {e}')
            )