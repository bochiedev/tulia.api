"""
Management command to seed default roles for tenants.

Creates the six default roles (Owner, Admin, Finance Admin, Catalog Manager,
Support Lead, Analyst) with their respective permission mappings for one or
all tenants. This command is idempotent and safe to re-run.
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.rbac.models import Permission, Role, RolePermission
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = 'Seed default roles for tenant(s) (idempotent)'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant ID or slug to seed roles for',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Seed roles for all tenants',
        )
    
    # Default role definitions with their permission mappings
    DEFAULT_ROLES = {
        'Owner': {
            'description': 'Full access to all tenant features and settings',
            'permissions': 'ALL',  # Special marker for all permissions
        },
        'Admin': {
            'description': 'Administrative access to most features (excludes withdrawal approval)',
            'permissions': [
                'catalog:view', 'catalog:edit',
                'services:view', 'services:edit', 'availability:edit',
                'conversations:view', 'handoff:perform',
                'orders:view', 'orders:edit',
                'appointments:view', 'appointments:edit',
                'analytics:view',
                'finance:view', 'finance:withdraw:initiate', 'finance:reconcile',
                'integrations:manage',
                'users:manage',
                # Note: finance:withdraw:approve excluded by default
                # Can be added via RBAC_ADMIN_CAN_APPROVE setting
            ],
        },
        'Finance Admin': {
            'description': 'Financial operations and reporting access',
            'permissions': [
                'analytics:view',
                'finance:view',
                'finance:withdraw:initiate',
                'finance:withdraw:approve',
                'finance:reconcile',
                'orders:view',
            ],
        },
        'Catalog Manager': {
            'description': 'Manage products, services, and availability',
            'permissions': [
                'analytics:view',
                'catalog:view', 'catalog:edit',
                'services:view', 'services:edit',
                'availability:edit',
            ],
        },
        'Support Lead': {
            'description': 'Customer support and conversation management',
            'permissions': [
                'conversations:view',
                'handoff:perform',
                'orders:view',
                'appointments:view',
            ],
        },
        'Analyst': {
            'description': 'Read-only access to analytics and data',
            'permissions': [
                'analytics:view',
                'catalog:view',
                'services:view',
                'orders:view',
                'appointments:view',
            ],
        },
    }
    
    def handle(self, *args, **options):
        """Seed default roles for specified tenant(s)."""
        
        tenant_id = options.get('tenant')
        seed_all = options.get('all')
        
        # Validate arguments
        if not tenant_id and not seed_all:
            raise CommandError(
                'You must specify either --tenant=<id> or --all'
            )
        
        if tenant_id and seed_all:
            raise CommandError(
                'Cannot specify both --tenant and --all'
            )
        
        # Get tenants to seed
        if seed_all:
            tenants = Tenant.objects.all()
            self.stdout.write(f'Seeding roles for all {tenants.count()} tenants...\n')
        else:
            # Try to find tenant by slug first, then by ID
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
            
            tenants = [tenant]
            self.stdout.write(f'Seeding roles for tenant: {tenant.name}\n')
        
        # Seed roles for each tenant
        total_created = 0
        total_updated = 0
        
        for tenant in tenants:
            created, updated = self._seed_tenant_roles(tenant)
            total_created += created
            total_updated += updated
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Seeding complete: {total_created} roles created, '
                f'{total_updated} roles updated across {len(tenants)} tenant(s)'
            )
        )
    
    def _seed_tenant_roles(self, tenant):
        """Seed roles for a specific tenant."""
        
        self.stdout.write(f'\n{tenant.name} ({tenant.slug}):')
        
        created_count = 0
        updated_count = 0
        
        # Get all permissions for "ALL" marker
        all_permissions = list(Permission.objects.all())
        
        # Check if admin can approve withdrawals (from settings)
        admin_can_approve = getattr(settings, 'RBAC_ADMIN_CAN_APPROVE', False)
        
        for role_name, role_config in self.DEFAULT_ROLES.items():
            # Get or create role
            role, created = Role.objects.get_or_create_role(
                tenant=tenant,
                name=role_name,
                description=role_config['description'],
                is_system=True
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created role: {role_name}')
                )
            else:
                # Update description if changed
                if role.description != role_config['description']:
                    role.description = role_config['description']
                    role.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ↻ Updated role: {role_name}')
                    )
                else:
                    self.stdout.write(
                        self.style.HTTP_INFO(f'    Exists: {role_name}')
                    )
            
            # Get permissions for this role
            if role_config['permissions'] == 'ALL':
                permissions = all_permissions
            else:
                permission_codes = role_config['permissions']
                
                # Add finance:withdraw:approve to Admin if setting is enabled
                if role_name == 'Admin' and admin_can_approve:
                    if 'finance:withdraw:approve' not in permission_codes:
                        permission_codes = permission_codes + ['finance:withdraw:approve']
                
                permissions = Permission.objects.filter(code__in=permission_codes)
            
            # Sync role permissions (idempotent)
            self._sync_role_permissions(role, permissions)
        
        return created_count, updated_count
    
    def _sync_role_permissions(self, role, permissions):
        """
        Sync permissions for a role (idempotent).
        
        Ensures the role has exactly the specified permissions.
        Adds missing permissions and removes extra ones.
        """
        # Get current permission IDs for this role
        current_perm_ids = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        
        # Get target permission IDs
        target_perm_ids = set(p.id for p in permissions)
        
        # Add missing permissions
        to_add = target_perm_ids - current_perm_ids
        for perm_id in to_add:
            permission = Permission.objects.get(id=perm_id)
            RolePermission.objects.grant_permission(role, permission)
        
        # Remove extra permissions
        to_remove = current_perm_ids - target_perm_ids
        if to_remove:
            RolePermission.objects.filter(
                role=role,
                permission_id__in=to_remove
            ).delete()
        
        if to_add or to_remove:
            self.stdout.write(
                f'      Synced permissions: +{len(to_add)} -{len(to_remove)}'
            )
