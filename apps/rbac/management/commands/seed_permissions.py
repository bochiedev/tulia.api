"""
Management command to seed canonical permissions.

Creates all global Permission records that define available access controls
across the system. This command is idempotent and safe to re-run.
"""
from django.core.management.base import BaseCommand
from apps.rbac.models import Permission


class Command(BaseCommand):
    help = 'Seed canonical permissions (idempotent)'
    
    # Canonical permissions with categories, labels, and descriptions
    CANONICAL_PERMISSIONS = [
        # Catalog Permissions
        {
            'code': 'catalog:view',
            'label': 'View Catalog',
            'description': 'View products and product details',
            'category': 'catalog',
        },
        {
            'code': 'catalog:edit',
            'label': 'Edit Catalog',
            'description': 'Create, update, and delete products',
            'category': 'catalog',
        },
        
        # Services Permissions
        {
            'code': 'services:view',
            'label': 'View Services',
            'description': 'View services and service details',
            'category': 'services',
        },
        {
            'code': 'services:edit',
            'label': 'Edit Services',
            'description': 'Create, update, and delete services',
            'category': 'services',
        },
        {
            'code': 'availability:edit',
            'label': 'Edit Availability',
            'description': 'Manage service availability windows',
            'category': 'services',
        },
        
        # Conversations Permissions
        {
            'code': 'conversations:view',
            'label': 'View Conversations',
            'description': 'View customer conversations and message history',
            'category': 'conversations',
        },
        {
            'code': 'handoff:perform',
            'label': 'Perform Handoff',
            'description': 'Take over conversations from bot to human agent',
            'category': 'conversations',
        },
        
        # Orders Permissions
        {
            'code': 'orders:view',
            'label': 'View Orders',
            'description': 'View order history and details',
            'category': 'orders',
        },
        {
            'code': 'orders:edit',
            'label': 'Edit Orders',
            'description': 'Update order status and details',
            'category': 'orders',
        },
        
        # Appointments Permissions
        {
            'code': 'appointments:view',
            'label': 'View Appointments',
            'description': 'View appointment bookings and details',
            'category': 'appointments',
        },
        {
            'code': 'appointments:edit',
            'label': 'Edit Appointments',
            'description': 'Update appointment status and details',
            'category': 'appointments',
        },
        
        # Analytics Permissions
        {
            'code': 'analytics:view',
            'label': 'View Analytics',
            'description': 'View business analytics and reports',
            'category': 'analytics',
        },
        
        # Finance Permissions
        {
            'code': 'finance:view',
            'label': 'View Finance',
            'description': 'View wallet balance and transaction history',
            'category': 'finance',
        },
        {
            'code': 'finance:withdraw:initiate',
            'label': 'Initiate Withdrawal',
            'description': 'Request withdrawal from wallet',
            'category': 'finance',
        },
        {
            'code': 'finance:withdraw:approve',
            'label': 'Approve Withdrawal',
            'description': 'Approve withdrawal requests (four-eyes)',
            'category': 'finance',
        },
        {
            'code': 'finance:reconcile',
            'label': 'Reconcile Finance',
            'description': 'Perform financial reconciliation and adjustments',
            'category': 'finance',
        },
        
        # Integrations Permissions
        {
            'code': 'integrations:manage',
            'label': 'Manage Integrations',
            'description': 'Configure and manage external integrations (Twilio, WooCommerce, Shopify)',
            'category': 'integrations',
        },
        
        # Users Permissions
        {
            'code': 'users:manage',
            'label': 'Manage Users',
            'description': 'Invite users, assign roles, and manage permissions',
            'category': 'users',
        },
    ]
    
    def handle(self, *args, **options):
        """Create or update all canonical permissions."""
        
        created_count = 0
        updated_count = 0
        
        self.stdout.write('Seeding canonical permissions...\n')
        
        for perm_data in self.CANONICAL_PERMISSIONS:
            permission, created = Permission.objects.get_or_create_permission(
                code=perm_data['code'],
                label=perm_data['label'],
                description=perm_data['description'],
                category=perm_data['category']
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {permission.code}')
                )
            else:
                # Update fields if they changed
                updated = False
                if permission.label != perm_data['label']:
                    permission.label = perm_data['label']
                    updated = True
                if permission.description != perm_data['description']:
                    permission.description = perm_data['description']
                    updated = True
                if permission.category != perm_data['category']:
                    permission.category = perm_data['category']
                    updated = True
                
                if updated:
                    permission.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Updated: {permission.code}')
                    )
                else:
                    self.stdout.write(
                        self.style.HTTP_INFO(f'  Exists: {permission.code}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Seeding complete: {created_count} created, {updated_count} updated, '
                f'{len(self.CANONICAL_PERMISSIONS) - created_count - updated_count} unchanged'
            )
        )
        
        # Display summary by category
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('Permissions Summary by Category:')
        self.stdout.write('=' * 70)
        
        categories = Permission.objects.values_list('category', flat=True).distinct().order_by('category')
        
        for category in categories:
            perms = Permission.objects.filter(category=category).order_by('code')
            self.stdout.write(f'\n{category.upper()}:')
            for perm in perms:
                self.stdout.write(f'  • {perm.code:<30} {perm.label}')
        
        self.stdout.write(f'\nTotal permissions: {Permission.objects.count()}')
