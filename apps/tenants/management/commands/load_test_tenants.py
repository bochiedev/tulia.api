"""
Management command to load comprehensive test tenant data.
Creates realistic tenants across different industries with products, services, and documents.
"""
import json
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from datetime import timedelta

from apps.tenants.models import (
    Tenant, SubscriptionTier, Subscription, Customer, TenantSettings
)
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service
from apps.bot.models import Document


class Command(BaseCommand):
    help = 'Load comprehensive test tenant data from JSON files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Load specific tenant by slug (optional)'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing tenants'
        )

    def handle(self, *args, **options):
        test_data_dir = os.path.join(settings.BASE_DIR, 'test_data', 'businesses')
        
        if not os.path.exists(test_data_dir):
            self.stdout.write(
                self.style.ERROR(f'Test data directory not found: {test_data_dir}')
            )
            return

        # Find all JSON files
        tenant_files = []
        for root, dirs, files in os.walk(test_data_dir):
            for file in files:
                if file.endswith('.json'):
                    tenant_files.append(os.path.join(root, file))

        if not tenant_files:
            self.stdout.write(
                self.style.ERROR('No tenant JSON files found in test_data/businesses/')
            )
            return

        # Filter by specific tenant if requested
        if options['tenant']:
            tenant_files = [f for f in tenant_files if options['tenant'] in f]
            if not tenant_files:
                self.stdout.write(
                    self.style.ERROR(f'No tenant file found for: {options["tenant"]}')
                )
                return

        self.stdout.write(f'Found {len(tenant_files)} tenant files to process')

        for file_path in tenant_files:
            try:
                self.load_tenant_from_file(file_path, options['overwrite'])
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error loading {file_path}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS('Successfully loaded all test tenant data')
        )

    def load_tenant_from_file(self, file_path, overwrite=False):
        """Load a single tenant from JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)

        tenant_data = data['tenant']
        slug = tenant_data['slug']

        # Check if tenant exists
        if Tenant.objects.filter(slug=slug).exists():
            if not overwrite:
                self.stdout.write(
                    self.style.WARNING(f'Tenant {slug} already exists, skipping')
                )
                return
            else:
                # Delete existing tenant and all related data
                Tenant.objects.filter(slug=slug).delete()
                self.stdout.write(f'Deleted existing tenant: {slug}')

        # Get subscription tier
        tier_name = tenant_data.get('subscription_tier', 'Starter')
        try:
            tier = SubscriptionTier.objects.get(name=tier_name)
        except SubscriptionTier.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Subscription tier not found: {tier_name}')
            )
            return

        # Create tenant
        tenant = Tenant.objects.create(
            name=tenant_data['name'],
            slug=tenant_data['slug'],
            whatsapp_number=tenant_data['whatsapp_number'],
            contact_email=tenant_data.get('contact_email'),
            contact_phone=tenant_data.get('contact_phone'),
            timezone=tenant_data.get('timezone', 'Africa/Nairobi'),
            bot_name=tenant_data.get('bot_name', 'Assistant'),
            tone_style=tenant_data.get('tone_style', 'friendly_concise'),
            default_language=tenant_data.get('default_language', 'en'),
            allowed_languages=tenant_data.get('allowed_languages', ['en']),
            subscription_tier=tier,
            status='active',
            trial_start_date=timezone.now() - timedelta(days=30),
            trial_end_date=timezone.now() + timedelta(days=365),
        )

        # Create subscription
        billing_cycle = tenant_data.get('billing_cycle', 'monthly')
        Subscription.objects.create(
            tenant=tenant,
            tier=tier,
            billing_cycle=billing_cycle,
            status='active',
            start_date=timezone.now().date(),
            next_billing_date=timezone.now().date() + timedelta(days=30 if billing_cycle == 'monthly' else 365)
        )

        # Create tenant settings
        TenantSettings.objects.create(
            tenant=tenant,
            business_hours=data.get('business_info', {}).get('business_hours', {}),
            onboarding_completed=True,
            onboarding_completed_at=timezone.now()
        )

        self.stdout.write(f'Created tenant: {tenant.name}')

        # Load products
        if 'products' in data:
            self.load_products(tenant, data['products'])

        # Load services
        if 'services' in data:
            self.load_services(tenant, data['services'])

        # Load documents
        if 'documents' in data:
            self.load_documents(tenant, data['documents'])

        # Load FAQs as documents
        if 'faqs' in data:
            self.load_faqs(tenant, data['faqs'])

        # Create some sample customers
        self.create_sample_customers(tenant)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully loaded tenant: {tenant.name}')
        )

    def load_products(self, tenant, products_data):
        """Load products for tenant."""
        for product_data in products_data:
            product = Product.objects.create(
                tenant=tenant,
                name=product_data['name'],
                description=product_data['description'],
                price=Decimal(str(product_data['price'])),
                category=product_data.get('category', 'General'),
                in_stock=product_data.get('in_stock', True),
                stock_quantity=product_data.get('stock_quantity', 0),
                image_url=product_data.get('image_url'),
                requires_prescription=product_data.get('requires_prescription', False)
            )

            # Create variants if specified
            if 'variants' in product_data:
                for variant_data in product_data['variants']:
                    ProductVariant.objects.create(
                        product=product,
                        name=variant_data['name'],
                        price=Decimal(str(variant_data['price'])),
                        stock_quantity=variant_data.get('stock_quantity', product.stock_quantity)
                    )

        self.stdout.write(f'  Created {len(products_data)} products')

    def load_services(self, tenant, services_data):
        """Load services for tenant."""
        for service_data in services_data:
            Service.objects.create(
                tenant=tenant,
                name=service_data['name'],
                description=service_data['description'],
                base_price=Decimal(str(service_data['base_price'])),
                duration_minutes=service_data['duration_minutes'],
                category=service_data.get('category', 'General'),
                is_active=True
            )

        self.stdout.write(f'  Created {len(services_data)} services')

    def load_documents(self, tenant, documents_data):
        """Load business documents for tenant."""
        for doc_type, content in documents_data.items():
            Document.objects.create(
                tenant=tenant,
                title=doc_type.replace('_', ' ').title(),
                content=content,
                document_type='policy' if 'policy' in doc_type else 'general',
                is_active=True
            )

        self.stdout.write(f'  Created {len(documents_data)} documents')

    def load_faqs(self, tenant, faqs_data):
        """Load FAQs as documents for tenant."""
        faq_content = "FREQUENTLY ASKED QUESTIONS\n\n"
        for faq in faqs_data:
            faq_content += f"Q: {faq['question']}\n"
            faq_content += f"A: {faq['answer']}\n\n"

        Document.objects.create(
            tenant=tenant,
            title='Frequently Asked Questions',
            content=faq_content,
            document_type='faq',
            is_active=True
        )

        self.stdout.write(f'  Created FAQ document with {len(faqs_data)} questions')

    def create_sample_customers(self, tenant):
        """Create sample customers for testing."""
        sample_customers = [
            {
                'phone_e164': '+254722999001',
                'name': 'John Kamau',
                'language_preference': 'en'
            },
            {
                'phone_e164': '+254722999002',
                'name': 'Mary Wanjiku',
                'language_preference': 'sw'
            },
            {
                'phone_e164': '+254722999003',
                'name': 'Peter Ochieng',
                'language_preference': 'en'
            }
        ]

        for customer_data in sample_customers:
            Customer.objects.create(
                tenant=tenant,
                phone_e164=customer_data['phone_e164'],
                name=customer_data['name'],
                language_preference=customer_data['language_preference'],
                marketing_opt_in=True,
                last_seen_at=timezone.now() - timedelta(days=1)
            )

        self.stdout.write(f'  Created {len(sample_customers)} sample customers')