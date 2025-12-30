"""
Management command to create subscription tiers with monthly/yearly pricing.
Yearly plans have 10% discount by default.
"""
from django.core.management.base import BaseCommand
from decimal import Decimal
from apps.tenants.models import SubscriptionTier


class Command(BaseCommand):
    help = 'Create subscription tiers with monthly and yearly pricing'

    def handle(self, *args, **options):
        tiers = [
            {
                'name': 'Starter',
                'description': 'Perfect for small businesses getting started',
                'monthly_price': Decimal('29.00'),
                'yearly_price': Decimal('261.00'),  # 10% discount
                'monthly_messages': 1000,
                'max_products': 100,
                'max_services': 5,
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
                'description': 'For growing businesses with more customers',
                'monthly_price': Decimal('99.00'),
                'yearly_price': Decimal('891.00'),  # 10% discount
                'monthly_messages': 5000,
                'max_products': 1000,
                'max_services': 50,
                'max_campaign_sends': 2500,
                'max_daily_outbound': 200,
                'payment_facilitation': True,
                'transaction_fee_percentage': Decimal('3.50'),
                'ab_test_variants': 5,
                'priority_support': False,
                'custom_branding': True,
                'api_access': 'full',
            },
            {
                'name': 'Enterprise',
                'description': 'For large businesses with high volume needs',
                'monthly_price': Decimal('299.00'),
                'yearly_price': Decimal('2691.00'),  # 10% discount
                'monthly_messages': None,  # Unlimited
                'max_products': None,  # Unlimited
                'max_services': None,  # Unlimited
                'max_campaign_sends': None,  # Unlimited
                'max_daily_outbound': None,  # Unlimited
                'payment_facilitation': True,
                'transaction_fee_percentage': Decimal('2.50'),
                'ab_test_variants': 10,
                'priority_support': True,
                'custom_branding': True,
                'api_access': 'full',
            }
        ]

        for tier_data in tiers:
            tier, created = SubscriptionTier.objects.get_or_create(
                name=tier_data['name'],
                defaults=tier_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created subscription tier: {tier.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Subscription tier already exists: {tier.name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Successfully created/verified all subscription tiers')
        )