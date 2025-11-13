"""
Management command to send onboarding reminder emails to tenants with incomplete onboarding.

Queries tenants with incomplete onboarding and sends reminder emails at:
- 3 days after tenant creation
- 7 days after tenant creation

Can be run manually or scheduled via Celery beat.

Usage:
    python manage.py send_onboarding_reminders
    python manage.py send_onboarding_reminders --dry-run
    python manage.py send_onboarding_reminders --force  # Send to all incomplete
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.tenants.models import Tenant, TenantSettings
from apps.tenants.services.onboarding_service import OnboardingService


class Command(BaseCommand):
    help = 'Send onboarding reminder emails to tenants with incomplete onboarding'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which tenants would receive reminders without sending emails',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Send reminders to all tenants with incomplete onboarding (ignore timing)',
        )
        parser.add_argument(
            '--days',
            type=int,
            nargs='+',
            default=[3, 7],
            help='Days after creation to send reminders (default: 3 7)',
        )
    
    def handle(self, *args, **options):
        """Send onboarding reminder emails."""
        
        dry_run = options['dry_run']
        force = options['force']
        reminder_days = options['days']
        
        self.stdout.write('=' * 70)
        if dry_run:
            self.stdout.write('Onboarding Reminders - DRY RUN')
        else:
            self.stdout.write('Sending Onboarding Reminders')
        self.stdout.write('=' * 70)
        
        # Query tenants with incomplete onboarding
        self.stdout.write('\n1. Finding tenants with incomplete onboarding...')
        
        incomplete_tenants = Tenant.objects.filter(
            deleted_at__isnull=True,
            status__in=['trial', 'active'],
        ).select_related('subscription_tier')
        
        # Filter by onboarding status
        tenants_to_remind = []
        
        for tenant in incomplete_tenants:
            # Get tenant settings
            try:
                settings_obj = TenantSettings.objects.get(tenant=tenant)
            except TenantSettings.DoesNotExist:
                # No settings, skip
                continue
            
            # Skip if onboarding is complete
            if settings_obj.onboarding_completed:
                continue
            
            # Check if tenant should receive reminder
            days_since_creation = (timezone.now() - tenant.created_at).days
            
            if force:
                # Force mode: send to all incomplete
                tenants_to_remind.append((tenant, days_since_creation, 'forced'))
            else:
                # Check if tenant is at a reminder milestone
                for reminder_day in reminder_days:
                    if days_since_creation == reminder_day:
                        tenants_to_remind.append((tenant, days_since_creation, f'{reminder_day}-day'))
                        break
        
        self.stdout.write(f'   ✓ Found {len(tenants_to_remind)} tenants to remind')
        
        if not tenants_to_remind:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write('No tenants need reminders at this time.')
            self.stdout.write('=' * 70)
            return
        
        # Send reminders
        self.stdout.write(f'\n2. {"Simulating" if dry_run else "Sending"} reminder emails...')
        
        sent_count = 0
        failed_count = 0
        
        for tenant, days_old, reminder_type in tenants_to_remind:
            # Get onboarding status
            status = OnboardingService.get_onboarding_status(tenant)
            completion_percentage = status['completion_percentage']
            pending_steps = status['pending_steps']
            
            # Get contact email
            contact_email = tenant.contact_email
            if not contact_email:
                # Try to get owner's email
                from apps.rbac.models import TenantUser, Role
                owner_role = Role.objects.filter(tenant=tenant, name='Owner').first()
                if owner_role:
                    owner_membership = TenantUser.objects.filter(
                        tenant=tenant,
                        user_roles__role=owner_role,
                        is_active=True
                    ).first()
                    if owner_membership:
                        contact_email = owner_membership.user.email
            
            if not contact_email:
                self.stdout.write(
                    self.style.WARNING(
                        f'   ⚠ {tenant.name}: No contact email found'
                    )
                )
                failed_count += 1
                continue
            
            # Display tenant info
            self.stdout.write(
                f'   → {tenant.name} ({tenant.slug})'
            )
            self.stdout.write(
                f'     Email: {contact_email}'
            )
            self.stdout.write(
                f'     Days old: {days_old} ({reminder_type} reminder)'
            )
            self.stdout.write(
                f'     Completion: {completion_percentage}%'
            )
            self.stdout.write(
                f'     Pending steps: {len(pending_steps)}'
            )
            
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'     ✓ Would send reminder email'
                    )
                )
                sent_count += 1
            else:
                # Send reminder email
                try:
                    OnboardingService.send_reminder(tenant)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'     ✓ Sent reminder email'
                        )
                    )
                    sent_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'     ✗ Failed to send: {str(e)}'
                        )
                    )
                    failed_count += 1
        
        # Display summary
        self.stdout.write('\n' + '=' * 70)
        if dry_run:
            self.stdout.write('Dry Run Complete')
        else:
            self.stdout.write('Reminders Sent')
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Tenants checked: {incomplete_tenants.count()}')
        self.stdout.write(f'  Reminders {"would be sent" if dry_run else "sent"}: {sent_count}')
        if failed_count > 0:
            self.stdout.write(f'  Failed: {failed_count}')
        
        if dry_run:
            self.stdout.write(f'\nRun without --dry-run to actually send emails.')
        
        self.stdout.write('')
