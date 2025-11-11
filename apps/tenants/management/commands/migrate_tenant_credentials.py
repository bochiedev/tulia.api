"""
Management command to migrate credentials from Tenant to TenantSettings.

This command migrates:
- Twilio credentials (sid, token, webhook_secret)
- From Tenant model to TenantSettings model

Usage:
    python manage.py migrate_tenant_credentials --dry-run
    python manage.py migrate_tenant_credentials
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.tenants.models import Tenant, TenantSettings


class Command(BaseCommand):
    help = 'Migrate credentials from Tenant to TenantSettings'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        tenants = Tenant.objects.all()
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for tenant in tenants:
            try:
                # Get or create settings
                settings, created = TenantSettings.objects.get_or_create(tenant=tenant)
                
                needs_migration = False
                changes = []
                
                # Check if Tenant has Twilio credentials that need migration
                if tenant.twilio_sid and not settings.twilio_sid:
                    needs_migration = True
                    changes.append(f"  - twilio_sid: {tenant.twilio_sid[:10]}...")
                    if not dry_run:
                        settings.twilio_sid = tenant.twilio_sid
                
                if tenant.twilio_token and not settings.twilio_token:
                    needs_migration = True
                    changes.append(f"  - twilio_token: ****")
                    if not dry_run:
                        settings.twilio_token = tenant.twilio_token
                
                if tenant.webhook_secret and not settings.twilio_webhook_secret:
                    needs_migration = True
                    changes.append(f"  - webhook_secret: ****")
                    if not dry_run:
                        settings.twilio_webhook_secret = tenant.webhook_secret
                
                if needs_migration:
                    self.stdout.write(
                        self.style.SUCCESS(f'\nMigrating tenant: {tenant.name} ({tenant.slug})')
                    )
                    for change in changes:
                        self.stdout.write(change)
                    
                    if not dry_run:
                        settings.save()
                    
                    migrated_count += 1
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Skipped {tenant.name}: Already migrated or no credentials')
                    )
            
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error migrating {tenant.name}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\nMigration Summary:'))
        self.stdout.write(f'  Total tenants: {tenants.count()}')
        self.stdout.write(self.style.SUCCESS(f'  Migrated: {migrated_count}'))
        self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('DRY RUN COMPLETE - Run without --dry-run to apply changes'))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('MIGRATION COMPLETE'))
