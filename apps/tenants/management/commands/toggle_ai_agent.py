"""
Management command to enable/disable AI agent for a tenant.

Usage:
    python manage.py toggle_ai_agent <tenant_slug> --enable
    python manage.py toggle_ai_agent <tenant_slug> --disable
    python manage.py toggle_ai_agent <tenant_slug> --status
"""
from django.core.management.base import BaseCommand, CommandError
from apps.tenants.models import Tenant, TenantSettings


class Command(BaseCommand):
    help = 'Enable or disable AI agent for a tenant'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'tenant_slug',
            type=str,
            help='Tenant slug'
        )
        parser.add_argument(
            '--enable',
            action='store_true',
            help='Enable AI agent for this tenant'
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='Disable AI agent for this tenant'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show current AI agent status for this tenant'
        )
    
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        enable = options.get('enable', False)
        disable = options.get('disable', False)
        status = options.get('status', False)
        
        # Validate arguments
        if sum([enable, disable, status]) != 1:
            raise CommandError(
                'You must specify exactly one of: --enable, --disable, or --status'
            )
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant with slug "{tenant_slug}" does not exist')
        
        # Get or create tenant settings
        settings, created = TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                'feature_flags': {}
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created settings for tenant "{tenant.name}"')
            )
        
        # Handle status check
        if status:
            current_status = settings.is_feature_enabled('ai_agent_enabled')
            self.stdout.write(
                self.style.SUCCESS(
                    f'AI agent for tenant "{tenant.name}" ({tenant_slug}): '
                    f'{"ENABLED" if current_status else "DISABLED"}'
                )
            )
            
            # Show additional info
            if current_status:
                # Check if LLM is configured
                has_openai = bool(settings.openai_api_key)
                has_together = bool(settings.together_api_key)
                llm_provider = settings.llm_provider or 'openai'
                
                self.stdout.write(
                    f'  LLM Provider: {llm_provider}'
                )
                self.stdout.write(
                    f'  OpenAI configured: {"Yes" if has_openai else "No"}'
                )
                self.stdout.write(
                    f'  Together AI configured: {"Yes" if has_together else "No"}'
                )
                
                if llm_provider == 'openai' and not has_openai:
                    self.stdout.write(
                        self.style.WARNING(
                            '  WARNING: OpenAI is selected but not configured!'
                        )
                    )
                elif llm_provider == 'together' and not has_together:
                    self.stdout.write(
                        self.style.WARNING(
                            '  WARNING: Together AI is selected but not configured!'
                        )
                    )
            
            return
        
        # Handle enable/disable
        if enable:
            # Check if LLM is configured
            has_openai = bool(settings.openai_api_key)
            has_together = bool(settings.together_api_key)
            
            if not has_openai and not has_together:
                raise CommandError(
                    'Cannot enable AI agent: No LLM provider is configured. '
                    'Please configure OpenAI or Together AI credentials first.'
                )
            
            # Enable AI agent
            if 'ai_agent_enabled' not in settings.feature_flags:
                settings.feature_flags = settings.feature_flags or {}
            
            settings.feature_flags['ai_agent_enabled'] = True
            settings.save(update_fields=['feature_flags', 'updated_at'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ AI agent ENABLED for tenant "{tenant.name}" ({tenant_slug})'
                )
            )
            
            # Show which provider will be used
            llm_provider = settings.llm_provider or 'openai'
            self.stdout.write(
                f'  Using LLM provider: {llm_provider}'
            )
            
        elif disable:
            # Disable AI agent
            if 'ai_agent_enabled' not in settings.feature_flags:
                settings.feature_flags = settings.feature_flags or {}
            
            settings.feature_flags['ai_agent_enabled'] = False
            settings.save(update_fields=['feature_flags', 'updated_at'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ AI agent DISABLED for tenant "{tenant.name}" ({tenant_slug})'
                )
            )
            self.stdout.write(
                '  Messages will be processed using the legacy intent service'
            )
