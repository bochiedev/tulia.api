"""
Management command to seed subscription tiers.

Creates the three default subscription tiers: Starter, Growth, Enterprise
with their respective feature limits and pricing.
"""
from django.core.management.base import BaseCommand
from decimal import Decimal
from apps.tenants.models import SubscriptionTier


class Command(BaseCommand):
    help = 'Seed subscription tiers (Starter, Growth, Enterprise)'
    
    def handle(self, *args, **options):
        """Create or update the three subscription tiers."""
        
        tiers_data = [
            {
                'name': 'Starter',
                'description': 'Perfect for small businesses getting started with WhatsApp commerce',
                'monthly_price': Decimal('29.00'),
                'yearly_price': Decimal('278.40'),  # 20% off: 29 * 12 * 0.8
                'currency': 'USD',
                'monthly_messages': 1000,
                'max_products': 100,
                'max_services': 10,
                'max_campaign_sends': 500,
                'max_daily_outbound': 50,
                'payment_facilitation': False,
                'transaction_fee_percentage': Decimal('0.00'),
                'ab_test_variants': 2,
                'priority_support': False,
                'custom_branding': False,
                'api_access': 'read',
            },
            {
                'name': 'Growth',
                'description': 'For growing businesses with higher volume and payment processing needs',
                'monthly_price': Decimal('99.00'),
                'yearly_price': Decimal('950.40'),  # 20% off: 99 * 12 * 0.8
                'currency': 'USD',
                'monthly_messages': 10000,
                'max_products': 1000,
                'max_services': 50,
                'max_campaign_sends': 5000,
                'max_daily_outbound': 500,
                'payment_facilitation': True,
                'transaction_fee_percentage': Decimal('3.50'),
                'ab_test_variants': 2,
                'priority_support': False,
                'custom_branding': False,
                'api_access': 'full',
            },
            {
                'name': 'Enterprise',
                'description': 'For large businesses with unlimited usage and premium features',
                'monthly_price': Decimal('299.00'),
                'yearly_price': Decimal('2870.40'),  # 20% off: 299 * 12 * 0.8
                'currency': 'USD',
                'monthly_messages': None,  # Unlimited
                'max_products': None,  # Unlimited
                'max_services': None,  # Unlimited
                'max_campaign_sends': None,  # Unlimited
                'max_daily_outbound': None,  # Unlimited
                'payment_facilitation': True,
                'transaction_fee_percentage': Decimal('2.50'),
                'ab_test_variants': 4,
                'priority_support': True,
                'custom_branding': True,
                'api_access': 'full',
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for tier_data in tiers_data:
            tier, created = SubscriptionTier.objects.update_or_create(
                name=tier_data['name'],
                defaults=tier_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created tier: {tier.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated tier: {tier.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSeeding complete: {created_count} created, {updated_count} updated'
            )
        )
        
        # Display summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('Subscription Tiers Summary:')
        self.stdout.write('=' * 60)
        
        for tier in SubscriptionTier.objects.all().order_by('monthly_price'):
            self.stdout.write(f'\n{tier.name}:')
            self.stdout.write(f'  Monthly: ${tier.monthly_price}')
            self.stdout.write(f'  Yearly: ${tier.yearly_price}')
            self.stdout.write(f'  Messages: {tier.monthly_messages or "Unlimited"}')
            self.stdout.write(f'  Products: {tier.max_products or "Unlimited"}')
            self.stdout.write(f'  Services: {tier.max_services or "Unlimited"}')
            self.stdout.write(f'  Payment Facilitation: {tier.payment_facilitation}')
            if tier.payment_facilitation:
                self.stdout.write(f'  Transaction Fee: {tier.transaction_fee_percentage}%')
