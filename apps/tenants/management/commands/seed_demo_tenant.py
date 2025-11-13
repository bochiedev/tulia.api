"""
Management command to create a demo tenant with verified email and all settings configured.

Creates:
- Demo user with verified email
- Demo tenant with all settings configured
- Twilio credentials (demo values)
- Payment method (demo Stripe token)
- Business settings (timezone, hours, preferences)
- Onboarding marked as complete

Useful for development, testing, and demonstrations.evelopment and testing.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from datetime import time
from decimal import Decimal
import uuid

from apps.tenants.models import Tenant, SubscriptionTier, TenantSettings
from apps.rbac.models import User, TenantUser, Role
from apps.rbac.services import RBACService


class Command(BaseCommand):
    help = 'Create a demo tenant with verified email and all settings configured'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--email',
            type=str,
            default='demo@example.com',
            help='Email address for demo user (default: demo@example.com)',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='demo123!',
            help='Password for demo user (default: demo123!)',
        )
        parser.add_argument(
            '--tenant-name',
            type=str,
            default='Demo Tenant',
            help='Name for demo tenant (default: Demo Tenant)',
        )
        parser.add_argument(
            '--tenant-slug',
            type=str,
            default='demo-tenant',
            help='Slug for demo tenant (default: demo-tenant)',
        )
        parser.add_argument(
            '--phone',
            type=str,
            default=None,
            help='WhatsApp number for demo tenant (default: auto-generated)',
        )
        parser.add_argument(
            '--tier',
            type=str,
            default='Growth',
            choices=['Starter', 'Growth', 'Enterprise'],
            help='Subscription tier (default: Growth)',
        )
    
    def handle(self, *args, **options):
        """Create demo tenant with all settings configured."""
        
        self.stdout.write('=' * 70)
        self.stdout.write('Creating Demo Tenant with Complete Configuration')
        self.stdout.write('=' * 70)
        
        # Extract options
        email = options['email']
        password = options['password']
        tenant_name = options['tenant_name']
        tenant_slug = options['tenant_slug']
        phone = options['phone']
        tier_name = options['tier']
        
        # Generate unique phone number if not provided
        if not phone:
            import random
            phone = f'+1555{random.randint(1000000, 9999999)}'
        
        # Ensure subscription tiers exist
        self.stdout.write('\n1. Checking subscription tiers...')
        if SubscriptionTier.objects.count() == 0:
            self.stdout.write('   Seeding subscription tiers...')
            call_command('seed_subscription_tiers', verbosity=0)
        
        tier = SubscriptionTier.objects.get(name=tier_name)
        self.stdout.write(f'   ✓ Using tier: {tier.name}')
        
        # Ensure permissions exist
        self.stdout.write('\n2. Checking permissions...')
        from apps.rbac.models import Permission
        if Permission.objects.count() == 0:
            self.stdout.write('   Seeding permissions...')
            call_command('seed_permissions', verbosity=0)
        else:
            self.stdout.write(f'   ✓ {Permission.objects.count()} permissions exist')
        
        # Create or get user with verified email
        self.stdout.write(f'\n3. Creating demo user: {email}')
        user = User.objects.by_email(email)
        
        if user:
            self.stdout.write(f'   ⚠ User already exists: {email}')
            # Update to ensure email is verified
            if not user.email_verified:
                user.email_verified = True
                user.email_verification_token = None
                user.email_verification_sent_at = None
                user.save(update_fields=['email_verified', 'email_verification_token', 'email_verification_sent_at', 'updated_at'])
                self.stdout.write('   ✓ Email marked as verified')
        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name='Demo',
                last_name='User',
            )
            # Mark email as verified
            user.email_verified = True
            user.save(update_fields=['email_verified', 'updated_at'])
            self.stdout.write(f'   ✓ Created user with verified email')
        
        # Create or get tenant
        self.stdout.write(f'\n4. Creating demo tenant: {tenant_name}')
        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        
        if tenant:
            self.stdout.write(f'   ⚠ Tenant already exists: {tenant_slug}')
        else:
            # Generate demo credentials
            demo_sid = f'AC{uuid.uuid4().hex[:32]}'
            demo_token = uuid.uuid4().hex
            demo_secret = uuid.uuid4().hex
            
            tenant = Tenant.objects.create(
                name=tenant_name,
                slug=tenant_slug,
                status='active',  # Active, not trial
                subscription_tier=tier,
                whatsapp_number=phone,
                twilio_sid=demo_sid,
                twilio_token=demo_token,
                webhook_secret=demo_secret,
                contact_email=email,
                timezone='America/New_York',
            )
            self.stdout.write(f'   ✓ Created tenant: {tenant.name}')
        
        # Seed roles for tenant
        self.stdout.write('\n5. Setting up RBAC roles...')
        call_command('seed_tenant_roles', tenant=tenant.slug, verbosity=0)
        self.stdout.write('   ✓ Roles seeded')
        
        # Create tenant membership
        self.stdout.write('\n6. Creating tenant membership...')
        tenant_user, created = TenantUser.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={
                'invite_status': 'accepted',
                'joined_at': timezone.now(),
            }
        )
        
        if created:
            self.stdout.write('   ✓ Created tenant membership')
        else:
            self.stdout.write('   ⚠ Membership already exists')
        
        # Assign Owner role
        self.stdout.write('\n7. Assigning Owner role...')
        role = Role.objects.by_name(tenant, 'Owner')
        if role:
            # Check if already assigned
            existing_role = tenant_user.user_roles.filter(role=role).first()
            if not existing_role:
                RBACService.assign_role(
                    tenant_user=tenant_user,
                    role=role,
                    assigned_by=None
                )
                self.stdout.write('   ✓ Assigned Owner role')
            else:
                self.stdout.write('   ⚠ Owner role already assigned')
        
        # Configure tenant settings
        self.stdout.write('\n8. Configuring tenant settings...')
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        
        # Initialize onboarding status if not set
        if not settings_obj.onboarding_status:
            settings_obj.initialize_onboarding_status()
        
        # Configure Twilio credentials (demo values)
        if not settings_obj.twilio_sid:
            settings_obj.twilio_sid = f'AC{uuid.uuid4().hex[:32]}'
            settings_obj.twilio_token = uuid.uuid4().hex
            settings_obj.twilio_webhook_secret = uuid.uuid4().hex
            settings_obj.twilio_whatsapp_number = phone
            self.stdout.write('   ✓ Configured Twilio credentials (demo)')
            
            # Mark step complete
            settings_obj.onboarding_status['twilio_configured'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
        
        # Add demo payment method
        if not settings_obj.stripe_payment_methods:
            settings_obj.stripe_customer_id = f'cus_{uuid.uuid4().hex[:24]}'
            settings_obj.stripe_payment_methods = [{
                'id': f'pm_{uuid.uuid4().hex[:24]}',
                'type': 'card',
                'card': {
                    'brand': 'visa',
                    'last4': '4242',
                    'exp_month': 12,
                    'exp_year': 2025,
                },
                'is_default': True,
                'created_at': timezone.now().isoformat(),
            }]
            self.stdout.write('   ✓ Added demo payment method')
            
            # Mark step complete
            settings_obj.onboarding_status['payment_method_added'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
        
        # Configure business settings
        if not settings_obj.business_hours:
            settings_obj.business_hours = {
                '0': {'start': '09:00', 'end': '17:00'},  # Monday
                '1': {'start': '09:00', 'end': '17:00'},  # Tuesday
                '2': {'start': '09:00', 'end': '17:00'},  # Wednesday
                '3': {'start': '09:00', 'end': '17:00'},  # Thursday
                '4': {'start': '09:00', 'end': '17:00'},  # Friday
            }
            settings_obj.quiet_hours = {
                'start': '22:00',
                'end': '08:00',
            }
            settings_obj.notification_preferences = {
                'email': {
                    'order_placed': True,
                    'order_fulfilled': True,
                    'appointment_booked': True,
                    'appointment_cancelled': True,
                },
                'sms': {
                    'order_placed': False,
                    'order_fulfilled': False,
                    'appointment_booked': True,
                    'appointment_cancelled': True,
                }
            }
            self.stdout.write('   ✓ Configured business settings')
            
            # Mark step complete
            settings_obj.onboarding_status['business_settings_configured'] = {
                'completed': True,
                'completed_at': timezone.now().isoformat()
            }
        
        # Mark onboarding as complete
        settings_obj.onboarding_completed = True
        settings_obj.onboarding_completed_at = timezone.now()
        
        settings_obj.save()
        self.stdout.write('   ✓ Onboarding marked as complete')
        
        # Display summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('Demo Tenant Created Successfully!')
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'\nDemo Tenant Details:')
        self.stdout.write(f'  Name: {tenant.name}')
        self.stdout.write(f'  Slug: {tenant.slug}')
        self.stdout.write(f'  ID: {tenant.id}')
        self.stdout.write(f'  Tier: {tenant.subscription_tier.name}')
        self.stdout.write(f'  Status: {tenant.status}')
        self.stdout.write(f'  WhatsApp: {tenant.whatsapp_number}')
        
        self.stdout.write(f'\nDemo User Credentials:')
        self.stdout.write(f'  Email: {user.email}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write(f'  Email Verified: {user.email_verified}')
        self.stdout.write(f'  Role: Owner')
        
        self.stdout.write(f'\nConfiguration Status:')
        self.stdout.write(f'  Twilio: ✓ Configured')
        self.stdout.write(f'  Payment Method: ✓ Added')
        self.stdout.write(f'  Business Settings: ✓ Configured')
        self.stdout.write(f'  Onboarding: ✓ Complete')
        
        self.stdout.write(f'\nYou can now login with:')
        self.stdout.write(f'  POST /v1/auth/login')
        self.stdout.write(f'  {{"email": "{email}", "password": "{password}"}}')
        
        self.stdout.write('')
