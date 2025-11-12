"""
Management command to list API keys for a tenant.
"""
from django.core.management.base import BaseCommand, CommandError
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'List API keys for a tenant (shows metadata only, not the actual keys)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_slug',
            type=str,
            help='Slug of the tenant to list API keys for'
        )
    
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant with slug "{tenant_slug}" does not exist')
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*70}\n'
            f'API Keys for tenant: {tenant.name} ({tenant.slug})\n'
            f'Tenant ID: {tenant.id}\n'
            f'{"="*70}\n'
        ))
        
        if not tenant.api_keys:
            self.stdout.write(self.style.WARNING(
                '\nNo API keys found for this tenant.\n'
                f'Generate one with: python manage.py generate_api_key {tenant_slug}\n'
            ))
            return
        
        self.stdout.write(f'\nTotal API keys: {len(tenant.api_keys)}\n')
        
        for idx, key_entry in enumerate(tenant.api_keys, 1):
            self.stdout.write(f'\n{idx}. {key_entry.get("name", "Unnamed Key")}')
            self.stdout.write(f'   Created: {key_entry.get("created_at", "Unknown")}')
            self.stdout.write(f'   Hash: {key_entry.get("key_hash", "N/A")[:16]}...')
        
        self.stdout.write(f'\n{"="*70}\n')
        self.stdout.write(self.style.WARNING(
            '\nNote: The actual API keys are not stored and cannot be retrieved.\n'
            'If you lost an API key, generate a new one with:\n'
            f'  python manage.py generate_api_key {tenant_slug}\n'
        ))
