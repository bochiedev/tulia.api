"""
Management command to assign Owner role to a user for a tenant.

Creates a TenantUser membership (if needed) and assigns the Owner role,
granting full access to all tenant features.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.rbac.models import User, TenantUser, Role
from apps.rbac.services import RBACService
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'Assign Owner role to a user for a tenant'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--tenant',
            type=str,
            required=True,
            help='Tenant ID or slug',
        )
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='User email address',
        )
        parser.add_argument(
            '--create-user',
            action='store_true',
            help='Create user if they do not exist (requires --password)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for new user (only used with --create-user)',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            default='',
            help='First name for new user',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            default='',
            help='Last name for new user',
        )
    
    def handle(self, *args, **options):
        """Assign Owner role to user for tenant."""
        
        tenant_id = options['tenant']
        email = options['email']
        create_user = options['create_user']
        password = options.get('password')
        first_name = options.get('first_name', '')
        last_name = options.get('last_name', '')
        
        # Validate create-user arguments
        if create_user and not password:
            raise CommandError(
                '--password is required when using --create-user'
            )
        
        # Find tenant by slug first, then by ID
        tenant = Tenant.objects.filter(slug=tenant_id).first()
        
        if not tenant:
            # Try by ID
            try:
                from uuid import UUID
                tenant_uuid = UUID(tenant_id)
                tenant = Tenant.objects.filter(id=tenant_uuid).first()
            except (ValueError, AttributeError):
                pass
        
        if not tenant:
            raise CommandError(f'Tenant not found: {tenant_id}')
        
        self.stdout.write(f'Tenant: {tenant.name} ({tenant.slug})')
        
        # Find or create user
        user = User.objects.by_email(email)
        
        if not user:
            if not create_user:
                raise CommandError(
                    f'User not found: {email}\n'
                    f'Use --create-user --password=<password> to create the user'
                )
            
            # Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created user: {email}')
            )
        else:
            self.stdout.write(f'User: {user.email}')
        
        # Find Owner role
        owner_role = Role.objects.by_name(tenant, 'Owner')
        
        if not owner_role:
            raise CommandError(
                f'Owner role not found for tenant: {tenant.name}\n'
                f'Run: python manage.py seed_tenant_roles --tenant={tenant.slug}'
            )
        
        # Get or create TenantUser membership
        tenant_user = TenantUser.objects.get_membership(tenant, user)
        
        if not tenant_user:
            # Create membership
            tenant_user = TenantUser.objects.create(
                tenant=tenant,
                user=user,
                invite_status='accepted',
                joined_at=timezone.now(),
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created membership for {user.email}')
            )
        else:
            # Ensure membership is active and accepted
            if not tenant_user.is_active or tenant_user.invite_status != 'accepted':
                tenant_user.is_active = True
                tenant_user.invite_status = 'accepted'
                if not tenant_user.joined_at:
                    tenant_user.joined_at = timezone.now()
                tenant_user.save()
                self.stdout.write(
                    self.style.WARNING(f'↻ Activated membership for {user.email}')
                )
            else:
                self.stdout.write(f'Membership: Active')
        
        # Assign Owner role
        try:
            user_role = RBACService.assign_role(
                tenant_user=tenant_user,
                role=owner_role,
                assigned_by=None  # System assignment
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Assigned Owner role to {user.email} for {tenant.name}'
                )
            )
            
            # Display granted permissions
            scopes = RBACService.resolve_scopes(tenant_user)
            self.stdout.write(f'\nGranted permissions: {len(scopes)}')
            
            # Group by category
            from collections import defaultdict
            by_category = defaultdict(list)
            
            from apps.rbac.models import Permission
            permissions = Permission.objects.filter(code__in=scopes).order_by('category', 'code')
            
            for perm in permissions:
                by_category[perm.category].append(perm.code)
            
            for category in sorted(by_category.keys()):
                self.stdout.write(f'\n  {category.upper()}:')
                for code in by_category[category]:
                    self.stdout.write(f'    • {code}')
            
        except Exception as e:
            # Check if role already assigned
            from apps.rbac.models import TenantUserRole
            existing = TenantUserRole.objects.filter(
                tenant_user=tenant_user,
                role=owner_role
            ).exists()
            
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n↻ Owner role already assigned to {user.email} for {tenant.name}'
                    )
                )
            else:
                raise CommandError(f'Failed to assign role: {str(e)}')
