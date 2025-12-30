"""
Management command to display subscription tier information and pricing.
"""
from django.core.management.base import BaseCommand
from apps.tenants.models import SubscriptionTier, Tenant, Subscription


class Command(BaseCommand):
    help = 'Display subscription tier information and current tenant subscriptions'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('💳 WabotIQ Subscription Information')
        )
        self.stdout.write('='*60)

        # Show subscription tiers
        tiers = SubscriptionTier.objects.all().order_by('monthly_price')
        
        if not tiers.exists():
            self.stdout.write(
                self.style.ERROR('❌ No subscription tiers found. Run: python manage.py create_subscription_tiers')
            )
            return

        self.stdout.write('\n📋 Available Subscription Tiers:\n')
        
        for tier in tiers:
            monthly = tier.monthly_price
            yearly = tier.yearly_price
            yearly_monthly = yearly / 12
            discount = ((monthly * 12 - yearly) / (monthly * 12) * 100)
            
            self.stdout.write(f'🏷️  {tier.name.upper()}')
            self.stdout.write(f'   Monthly: ${monthly}')
            self.stdout.write(f'   Yearly:  ${yearly} (${yearly_monthly:.2f}/month - {discount:.0f}% discount)')
            self.stdout.write(f'   Description: {tier.description}')
            
            # Features
            features = []
            if tier.monthly_messages:
                features.append(f'{tier.monthly_messages:,} messages/month')
            else:
                features.append('Unlimited messages')
                
            if tier.max_products:
                features.append(f'{tier.max_products:,} products max')
            else:
                features.append('Unlimited products')
                
            if tier.max_services:
                features.append(f'{tier.max_services} services max')
            else:
                features.append('Unlimited services')
                
            if tier.payment_facilitation:
                features.append(f'Payment processing ({tier.transaction_fee_percentage}% fee)')
            
            if tier.priority_support:
                features.append('Priority support')
                
            if tier.custom_branding:
                features.append('Custom branding')
            
            features.append(f'API access: {tier.get_api_access_display()}')
            
            self.stdout.write(f'   Features: {", ".join(features)}')
            
            # Show tenant count
            tenant_count = tier.tenants.count()
            self.stdout.write(f'   Active tenants: {tenant_count}')
            self.stdout.write('')

        # Show current subscriptions
        subscriptions = Subscription.objects.select_related('tenant', 'tier').all()
        
        if subscriptions.exists():
            self.stdout.write('\n🏢 Current Tenant Subscriptions:\n')
            
            for sub in subscriptions:
                price = sub.calculate_price()
                self.stdout.write(
                    f'• {sub.tenant.name} - {sub.tier.name} ({sub.billing_cycle}) - ${price}'
                )
        
        # Summary
        total_tenants = Tenant.objects.count()
        active_subs = subscriptions.filter(status='active').count()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'📊 Summary:')
        self.stdout.write(f'   Total tenants: {total_tenants}')
        self.stdout.write(f'   Active subscriptions: {active_subs}')
        
        if total_tenants > 0:
            # Revenue calculation
            monthly_revenue = sum(
                sub.tier.monthly_price if sub.billing_cycle == 'monthly' 
                else sub.tier.yearly_price / 12
                for sub in subscriptions.filter(status='active')
            )
            yearly_revenue = sum(
                sub.tier.monthly_price * 12 if sub.billing_cycle == 'monthly'
                else sub.tier.yearly_price
                for sub in subscriptions.filter(status='active')
            )
            
            self.stdout.write(f'   Monthly recurring revenue: ${monthly_revenue:.2f}')
            self.stdout.write(f'   Annual recurring revenue: ${yearly_revenue:.2f}')
        
        self.stdout.write('='*60)