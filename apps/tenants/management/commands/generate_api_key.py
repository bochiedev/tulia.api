"""
Management command to generate API keys for tenants.
"""
from django.core.management.base import BaseCommand, CommandError
from apps.tenants.models import Tenant
from apps.tenants.utils import add_api_key_to_tenant


class Command(BaseCommand):
    help = 'Generate a new API key for a tenant'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_slug',
            type=str,
            help='Slug of the tenant to generate API key for'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='API Key',
            help='Human-readable name for the API key'
        )
    
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        key_name = options['name']
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant with slug "{tenant_slug}" does not exist')
        
        # Generate API key
        plain_key = add_api_key_to_tenant(tenant, name=key_name)
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*70}\n'
            f'API Key generated successfully for tenant: {tenant.name}\n'
            f'{"="*70}\n'
        ))
        
        self.stdout.write(self.style.WARNING(
            f'\nAPI Key (save this, it will not be shown again):\n'
        ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{plain_key}\n'
        ))
        
        self.stdout.write(self.style.WARNING(
            f'\nTenant ID: {tenant.id}\n'
            f'Tenant Slug: {tenant.slug}\n'
            f'Key Name: {key_name}\n'
            f'\nUse these in your API requests:\n'
            f'  X-TENANT-ID: {tenant.id}\n'
            f'  X-TENANT-API-KEY: {plain_key}\n'
            f'{"="*70}\n'
        ))
