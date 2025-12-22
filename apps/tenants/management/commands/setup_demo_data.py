"""
Comprehensive management command to set up complete demo data.
Creates subscription tiers, loads test tenants, and sets up RBAC.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction


class Command(BaseCommand):
    help = 'Set up complete demo data including subscription tiers, tenants, and RBAC'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing data'
        )
        parser.add_argument(
            '--skip-rbac',
            action='store_true',
            help='Skip RBAC setup (if already configured)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up WabotIQ demo data...')
        )

        try:
            with transaction.atomic():
                # Step 1: Create subscription tiers
                self.stdout.write('\n📋 Step 1: Creating subscription tiers...')
                call_command('create_subscription_tiers')

                # Step 2: Set up RBAC (if not skipped)
                if not options['skip_rbac']:
                    self.stdout.write('\n🔐 Step 2: Setting up RBAC...')
                    try:
                        call_command('seed_permissions')
                        call_command('seed_tenant_roles')
                        self.stdout.write(
                            self.style.SUCCESS('✅ RBAC setup completed')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  RBAC setup skipped: {str(e)}')
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING('⏭️  RBAC setup skipped')
                    )

                # Step 3: Load test tenants
                self.stdout.write('\n🏢 Step 3: Loading test tenants...')
                call_command('load_test_tenants', overwrite=options['overwrite'])

                # Step 4: Summary
                self.print_summary()

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Setup failed: {str(e)}')
            )
            raise

    def print_summary(self):
        """Print setup summary with tenant information."""
        from apps.tenants.models import Tenant, SubscriptionTier
        from apps.catalog.models import Product
        from apps.services.models import Service

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('🎉 DEMO DATA SETUP COMPLETE!'))
        self.stdout.write('='*60)

        # Subscription tiers
        tiers = SubscriptionTier.objects.all()
        self.stdout.write(f'\n📋 Subscription Tiers: {tiers.count()}')
        for tier in tiers:
            monthly = tier.monthly_price
            yearly = tier.yearly_price
            discount = ((monthly * 12 - yearly) / (monthly * 12) * 100)
            self.stdout.write(
                f'  • {tier.name}: ${monthly}/month, ${yearly}/year ({discount:.0f}% yearly discount)'
            )

        # Tenants by industry
        tenants = Tenant.objects.all().order_by('name')
        self.stdout.write(f'\n🏢 Test Tenants: {tenants.count()}')
        
        industries = {
            'Food & Beverage': [],
            'Beauty & Personal Care': [],
            'Retail & E-commerce': [],
            'Healthcare': [],
            'Other': []
        }

        for tenant in tenants:
            if any(word in tenant.name.lower() for word in ['kitchen', 'restaurant', 'java', 'eats', 'spice']):
                industries['Food & Beverage'].append(tenant)
            elif any(word in tenant.name.lower() for word in ['salon', 'barber', 'glamour']):
                industries['Beauty & Personal Care'].append(tenant)
            elif any(word in tenant.name.lower() for word in ['perfume', 'scent']):
                industries['Retail & E-commerce'].append(tenant)
            elif any(word in tenant.name.lower() for word in ['pharmacy', 'health']):
                industries['Healthcare'].append(tenant)
            else:
                industries['Other'].append(tenant)

        for industry, tenant_list in industries.items():
            if tenant_list:
                self.stdout.write(f'\n  {industry}:')
                for tenant in tenant_list:
                    products = Product.objects.filter(tenant=tenant).count()
                    services = Service.objects.filter(tenant=tenant).count()
                    tier = tenant.subscription_tier.name if tenant.subscription_tier else 'None'
                    self.stdout.write(
                        f'    • {tenant.name} ({tier}) - {products} products, {services} services'
                    )

        # Quick stats
        total_products = Product.objects.count()
        total_services = Service.objects.count()
        
        self.stdout.write(f'\n📊 Total Products: {total_products}')
        self.stdout.write(f'📊 Total Services: {total_services}')

        # Test instructions
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('🧪 TESTING INSTRUCTIONS'))
        self.stdout.write('='*60)
        
        self.stdout.write('\n1. Test WhatsApp numbers to try:')
        for tenant in tenants[:5]:  # Show first 5
            self.stdout.write(f'   • {tenant.whatsapp_number} - {tenant.name}')
        
        self.stdout.write('\n2. Test different business types:')
        self.stdout.write('   • Food delivery (Mama Njeri\'s Kitchen)')
        self.stdout.write('   • Pharmacy orders (HealthPlus Pharmacy)')
        self.stdout.write('   • Beauty appointments (Glamour Salon)')
        self.stdout.write('   • Product inquiries (Scent Safari Perfumes)')
        
        self.stdout.write('\n3. Test subscription features:')
        self.stdout.write('   • Starter tier: Limited features')
        self.stdout.write('   • Growth tier: Payment processing enabled')
        self.stdout.write('   • Enterprise tier: Unlimited usage')
        
        self.stdout.write('\n4. Test bot hallucination scenarios:')
        self.stdout.write('   • Ask about products not in catalog')
        self.stdout.write('   • Request services not offered')
        self.stdout.write('   • Ask about policies not documented')
        
        self.stdout.write('\n5. Admin panel access:')
        self.stdout.write('   • Create superuser: python manage.py createsuperuser')
        self.stdout.write('   • Access: /admin/')
        
        self.stdout.write(f'\n✅ Setup complete! Ready for testing.')
        self.stdout.write('='*60)