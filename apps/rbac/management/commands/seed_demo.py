"""
Management command to create a demo tenant with users and roles.

Creates a complete demo environment with:
- Demo tenant with trial subscription
- Owner user with full access
- Catalog Manager user
- Finance Admin user
- Support Lead user
- All roles properly assigned

This is useful for testing, demos, and development.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from datetime import timedelta
from decimal import Decimal
import uuid

from apps.tenants.models import Tenant, SubscriptionTier
from apps.rbac.models import User, TenantUser, Role
from apps.rbac.services import RBACService


class Command(BaseCommand):
    help = 'Create demo tenant with users and roles'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--tenant-name',
            type=str,
            default='Demo Business',
            help='Name for the demo tenant',
        )
        parser.add_argument(
            '--tenant-slug',
            type=str,
            default='demo-business',
            help='Slug for the demo tenant',
        )
        parser.add_argument(
            '--owner-email',
            type=str,
            default='owner@demo.tulia.ai',
            help='Email for the owner user',
        )
        parser.add_argument(
            '--owner-password',
            type=str,
            default='demo123!',
            help='Password for the owner user',
        )
        parser.add_argument(
            '--skip-if-exists',
            action='store_true',
            help='Skip creation if tenant already exists',
        )
    
    # Demo users to create
    DEMO_USERS = [
        {
            'email': 'owner@demo.tulia.ai',
            'password': 'demo123!',
            'first_name': 'Alice',
            'last_name': 'Owner',
            'role': 'Owner',
        },
        {
            'email': 'catalog@demo.tulia.ai',
            'password': 'demo123!',
            'first_name': 'Bob',
            'last_name': 'Catalog',
            'role': 'Catalog Manager',
        },
        {
            'email': 'finance@demo.tulia.ai',
            'password': 'demo123!',
            'first_name': 'Carol',
            'last_name': 'Finance',
            'role': 'Finance Admin',
        },
        {
            'email': 'support@demo.tulia.ai',
            'password': 'demo123!',
            'first_name': 'David',
            'last_name': 'Support',
            'role': 'Support Lead',
        },
        {
            'email': 'analyst@demo.tulia.ai',
            'password': 'demo123!',
            'first_name': 'Eve',
            'last_name': 'Analyst',
            'role': 'Analyst',
        },
    ]
    
    def handle(self, *args, **options):
        """Create demo tenant with users and roles."""
        
        tenant_name = options['tenant_name']
        tenant_slug = options['tenant_slug']
        owner_email = options['owner_email']
        owner_password = options['owner_password']
        skip_if_exists = options['skip_if_exists']
        
        # Update demo users with custom owner email/password
        if owner_email != 'owner@demo.tulia.ai':
            self.DEMO_USERS[0]['email'] = owner_email
        if owner_password != 'demo123!':
            self.DEMO_USERS[0]['password'] = owner_password
        
        self.stdout.write('=' * 70)
        self.stdout.write('Creating Demo Tenant')
        self.stdout.write('=' * 70)
        
        # Check if tenant already exists
        existing_tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if existing_tenant:
            if skip_if_exists:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n↻ Tenant already exists: {existing_tenant.name} ({existing_tenant.slug})'
                    )
                )
                return
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠ Tenant already exists: {existing_tenant.name}\n'
                        f'Use --skip-if-exists to skip creation or choose a different slug'
                    )
                )
                return
        
        # Ensure subscription tiers exist
        self.stdout.write('\n1. Checking subscription tiers...')
        starter_tier = SubscriptionTier.objects.filter(name='Starter').first()
        if not starter_tier:
            self.stdout.write('   Seeding subscription tiers...')
            call_command('seed_subscription_tiers')
            starter_tier = SubscriptionTier.objects.get(name='Starter')
        else:
            self.stdout.write('   ✓ Subscription tiers exist')
        
        # Ensure permissions exist
        self.stdout.write('\n2. Checking permissions...')
        from apps.rbac.models import Permission
        if Permission.objects.count() == 0:
            self.stdout.write('   Seeding permissions...')
            call_command('seed_permissions')
        else:
            self.stdout.write(f'   ✓ {Permission.objects.count()} permissions exist')
        
        # Create tenant
        self.stdout.write(f'\n3. Creating tenant: {tenant_name}...')
        
        # Generate demo credentials
        demo_sid = f'AC{uuid.uuid4().hex[:32]}'
        demo_token = uuid.uuid4().hex
        demo_secret = uuid.uuid4().hex
        
        tenant = Tenant.objects.create(
            name=tenant_name,
            slug=tenant_slug,
            status='trial',
            subscription_tier=starter_tier,
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
            whatsapp_number='+15555551234',  # Demo number
            contact_email=owner_email,
            timezone='America/New_York',
        )
        
        # Update tenant settings with integration credentials (created by signal)
        tenant.settings.twilio_sid = demo_sid
        tenant.settings.twilio_token = demo_token
        tenant.settings.twilio_webhook_secret = demo_secret
        tenant.settings.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'   ✓ Created tenant: {tenant.name} ({tenant.slug})')
        )
        self.stdout.write(f'   Trial expires: {tenant.trial_end_date.strftime("%Y-%m-%d")}')
        
        # Seed roles for tenant
        self.stdout.write('\n4. Seeding roles...')
        call_command('seed_tenant_roles', tenant=tenant.slug)
        
        # Create users and assign roles
        self.stdout.write('\n5. Creating demo users...')
        
        created_users = []
        
        for user_data in self.DEMO_USERS:
            # Create or get user
            user = User.objects.by_email(user_data['email'])
            
            if not user:
                user = User.objects.create_user(
                    email=user_data['email'],
                    password=user_data['password'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                )
                self.stdout.write(
                    self.style.SUCCESS(f'   ✓ Created user: {user.email}')
                )
            else:
                self.stdout.write(
                    self.style.HTTP_INFO(f'     Exists: {user.email}')
                )
            
            # Create tenant membership
            tenant_user, created = TenantUser.objects.get_or_create(
                tenant=tenant,
                user=user,
                defaults={
                    'invite_status': 'accepted',
                    'joined_at': timezone.now(),
                }
            )
            
            if created:
                self.stdout.write(f'     → Created membership')
            
            # Assign role
            role = Role.objects.by_name(tenant, user_data['role'])
            if role:
                RBACService.assign_role(
                    tenant_user=tenant_user,
                    role=role,
                    assigned_by=None
                )
                self.stdout.write(f'     → Assigned role: {user_data["role"]}')
            
            created_users.append({
                'email': user.email,
                'password': user_data['password'],
                'role': user_data['role'],
                'name': user.get_full_name(),
            })
        
        # Display summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('Demo Tenant Created Successfully!')
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'\nTenant Details:')
        self.stdout.write(f'  Name: {tenant.name}')
        self.stdout.write(f'  Slug: {tenant.slug}')
        self.stdout.write(f'  ID: {tenant.id}')
        self.stdout.write(f'  Status: {tenant.status}')
        self.stdout.write(f'  Tier: {tenant.subscription_tier.name}')
        self.stdout.write(f'  Trial Expires: {tenant.trial_end_date.strftime("%Y-%m-%d")}')
        self.stdout.write(f'  WhatsApp: {tenant.whatsapp_number}')
        
        self.stdout.write(f'\nDemo Users:')
        self.stdout.write('-' * 70)
        
        for user_info in created_users:
            self.stdout.write(f'\n  {user_info["name"]} ({user_info["role"]})')
            self.stdout.write(f'    Email:    {user_info["email"]}')
            self.stdout.write(f'    Password: {user_info["password"]}')
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('Next Steps:')
        self.stdout.write('=' * 70)
        self.stdout.write('\n1. Login with any of the demo users')
        self.stdout.write('2. Use X-TENANT-ID header with tenant ID in API requests')
        self.stdout.write('3. Test different permission levels with different users')
        self.stdout.write(f'\nExample API request:')
        self.stdout.write(f'  curl -H "X-TENANT-ID: {tenant.id}" \\')
        self.stdout.write(f'       -H "Authorization: Bearer <token>" \\')
        self.stdout.write(f'       http://localhost:8000/v1/products')
        self.stdout.write('')
