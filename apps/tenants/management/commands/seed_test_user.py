"""
Management command to create specific test user for RAG testing.

Creates:
- Customer with phone +254722241161 for Starter Store tenant
- Sample conversation with messages
- Sample documents for RAG testing
- Sample products and services
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import os

from apps.tenants.models import Tenant, Customer
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service, ServiceVariant, AvailabilityWindow
from apps.messaging.models import Conversation, Message, CustomerPreferences
from apps.bot.models import Document, AgentConfiguration


class Command(BaseCommand):
    help = 'Create specific test user with phone +254722241161 for Starter Store'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-slug',
            type=str,
            default='starter-store',
            help='Tenant slug (default: starter-store)'
        )
        parser.add_argument(
            '--phone',
            type=str,
            default='+254722241161',
            help='Customer phone number (default: +254722241161)'
        )
    
    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        phone = options['phone']
        
        self.stdout.write(self.style.SUCCESS(f'\n🚀 Creating test user for RAG testing...\n'))
        
        # Get or create tenant
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
            self.stdout.write(f'✓ Found tenant: {tenant.name} ({tenant.slug})')
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Tenant "{tenant_slug}" not found!'))
            self.stdout.write('  Run: python manage.py seed_demo_data first')
            return
        
        # Create or get customer
        customer, created = Customer.objects.get_or_create(
            tenant=tenant,
            phone_e164=phone,
            defaults={
                'name': 'Test Customer',
                'first_name': 'Test',
                'last_name': 'Customer',
                'timezone': 'Africa/Nairobi',
                'tags': ['test', 'rag-testing'],
                'last_seen_at': timezone.now(),
            }
        )
        
        if created:
            self.stdout.write(f'✓ Created customer: {customer.name} ({phone})')
        else:
            self.stdout.write(f'✓ Found existing customer: {customer.name} ({phone})')
        
        # Create customer preferences
        prefs, created = CustomerPreferences.objects.get_or_create(
            tenant=tenant,
            customer=customer,
            defaults={
                'transactional_messages': True,
                'reminder_messages': True,
                'promotional_messages': True,
            }
        )
        
        if created:
            self.stdout.write(f'✓ Created customer preferences')
        
        # Create or get conversation
        conversation, created = Conversation.objects.get_or_create(
            tenant=tenant,
            customer=customer,
            channel='whatsapp',
            defaults={
                'status': 'active',
                'last_message_at': timezone.now(),
            }
        )
        
        if created:
            self.stdout.write(f'✓ Created conversation')
            
            # Create sample messages
            messages = [
                {
                    'direction': 'inbound',
                    'text': 'Hi, I need help with your products',
                    'timestamp': timezone.now() - timedelta(minutes=10)
                },
                {
                    'direction': 'outbound',
                    'text': 'Hello! I\'d be happy to help you. What would you like to know?',
                    'timestamp': timezone.now() - timedelta(minutes=9)
                },
                {
                    'direction': 'inbound',
                    'text': 'What is your return policy?',
                    'timestamp': timezone.now() - timedelta(minutes=5)
                },
            ]
            
            for msg_data in messages:
                Message.objects.create(
                    conversation=conversation,
                    direction=msg_data['direction'],
                    text=msg_data['text'],
                    channel='whatsapp',
                    status='delivered' if msg_data['direction'] == 'outbound' else 'received',
                    created_at=msg_data['timestamp']
                )
            
            self.stdout.write(f'✓ Created {len(messages)} sample messages')
        else:
            self.stdout.write(f'✓ Found existing conversation with {conversation.messages.count()} messages')
        
        # Configure agent for RAG
        agent_config, created = AgentConfiguration.objects.get_or_create(
            tenant=tenant,
            defaults={
                'agent_name': 'StarterBot',
                'tone': 'friendly',
                'enable_document_retrieval': True,
                'enable_database_retrieval': True,
                'enable_internet_enrichment': True,
                'enable_source_attribution': True,
                'max_document_results': 3,
                'max_database_results': 5,
                'max_internet_results': 2,
                'agent_can_do': """
- Answer questions about products and services
- Help with orders and bookings
- Provide information from our knowledge base
- Search our catalog in real-time
- Book appointments and check availability
- Explain our policies and procedures
""",
                'agent_cannot_do': """
- Process payments directly
- Access external systems without integration
- Provide medical or legal advice
- Make changes to orders without confirmation
- Share customer data with third parties
""",
            }
        )
        
        if created:
            self.stdout.write(f'✓ Created agent configuration with RAG enabled')
        else:
            # Update existing config to enable RAG
            agent_config.enable_document_retrieval = True
            agent_config.enable_database_retrieval = True
            agent_config.enable_internet_enrichment = True
            agent_config.enable_source_attribution = True
            agent_config.agent_can_do = """
- Answer questions about products and services
- Help with orders and bookings
- Provide information from our knowledge base
- Search our catalog in real-time
- Book appointments and check availability
- Explain our policies and procedures
"""
            agent_config.agent_cannot_do = """
- Process payments directly
- Access external systems without integration
- Provide medical or legal advice
- Make changes to orders without confirmation
- Share customer data with third parties
"""
            agent_config.save()
            self.stdout.write(f'✓ Updated agent configuration with RAG enabled')
        
        # Create sample products if none exist
        product_count = Product.objects.filter(tenant=tenant).count()
        if product_count < 5:
            self.stdout.write(f'\n📦 Creating sample products...')
            
            products_data = [
                {
                    'title': 'iPhone 15 Pro',
                    'description': 'Latest iPhone with A17 Pro chip, titanium design, and advanced camera system',
                    'price': Decimal('999.00'),
                    'category': 'Electronics',
                    'sku': 'IPH15PRO',
                },
                {
                    'title': 'Wireless Headphones',
                    'description': 'Premium noise-cancelling wireless headphones with 30-hour battery life',
                    'price': Decimal('79.99'),
                    'category': 'Electronics',
                    'sku': 'WH-NC-001',
                },
                {
                    'title': 'Smart Watch',
                    'description': 'Fitness tracking smartwatch with heart rate monitor and GPS',
                    'price': Decimal('299.99'),
                    'category': 'Electronics',
                    'sku': 'SW-FIT-001',
                },
                {
                    'title': 'Coffee Maker',
                    'description': 'Programmable drip coffee maker with thermal carafe',
                    'price': Decimal('79.99'),
                    'category': 'Home & Kitchen',
                    'sku': 'CM-PROG-001',
                },
                {
                    'title': 'Yoga Mat',
                    'description': 'Non-slip yoga mat with carrying strap, perfect for home or studio',
                    'price': Decimal('29.99'),
                    'category': 'Sports & Outdoors',
                    'sku': 'YM-NS-001',
                },
            ]
            
            for product_data in products_data:
                product = Product.objects.create(
                    tenant=tenant,
                    **product_data,
                    is_active=True,
                    stock_quantity=100,
                    currency='USD',
                )
                
                # Create default variant
                ProductVariant.objects.create(
                    tenant=tenant,
                    product=product,
                    title='Default',
                    sku=product.sku,
                    price=product.price,
                    stock_quantity=100,
                    is_active=True,
                )
            
            self.stdout.write(f'✓ Created {len(products_data)} sample products')
        else:
            self.stdout.write(f'✓ Tenant already has {product_count} products')
        
        # Create sample services if none exist
        service_count = Service.objects.filter(tenant=tenant).count()
        if service_count < 3:
            self.stdout.write(f'\n💇 Creating sample services...')
            
            services_data = [
                {
                    'title': 'Haircut',
                    'description': 'Professional haircut with wash and style',
                    'base_price': Decimal('25.00'),
                    'duration_minutes': 30,
                    'category': 'Beauty',
                },
                {
                    'title': 'Massage',
                    'description': 'Relaxing full-body massage therapy',
                    'base_price': Decimal('60.00'),
                    'duration_minutes': 60,
                    'category': 'Wellness',
                },
                {
                    'title': 'Consultation',
                    'description': 'One-on-one consultation session',
                    'base_price': Decimal('50.00'),
                    'duration_minutes': 45,
                    'category': 'Professional',
                },
            ]
            
            for service_data in services_data:
                service = Service.objects.create(
                    tenant=tenant,
                    **service_data,
                    is_active=True,
                    currency='USD',
                )
                
                # Create default variant
                ServiceVariant.objects.create(
                    tenant=tenant,
                    service=service,
                    title='Standard',
                    price=service.base_price,
                    duration_minutes=service.duration_minutes,
                    is_active=True,
                )
                
                # Create availability windows (Mon-Fri, 9am-5pm)
                for day in range(5):  # Monday to Friday
                    AvailabilityWindow.objects.create(
                        tenant=tenant,
                        service=service,
                        day_of_week=day,
                        start_time='09:00',
                        end_time='17:00',
                        max_bookings_per_slot=3,
                        is_active=True,
                    )
            
            self.stdout.write(f'✓ Created {len(services_data)} sample services with availability')
        else:
            self.stdout.write(f'✓ Tenant already has {service_count} services')
        
        # Create sample FAQ document content
        self.stdout.write(f'\n📄 Sample FAQ content for document upload:')
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        
        faq_content = """
STARTER STORE - FREQUENTLY ASKED QUESTIONS

RETURN POLICY
Q: What is your return policy?
A: We offer a 30-day return policy on all items. You can return any product 
within 30 days of purchase for a full refund, as long as it's in its original 
condition with all tags and packaging intact.

Q: How do I initiate a return?
A: Contact our customer service team with your order number and reason for 
return. We'll provide you with a return shipping label and instructions.

SHIPPING INFORMATION
Q: How long does shipping take?
A: Standard shipping takes 5-7 business days. Express shipping (2-3 days) 
and overnight shipping are also available at checkout.

Q: Do you ship internationally?
A: Yes, we ship to most countries worldwide. International shipping times 
vary by destination (typically 10-15 business days).

PAYMENT & PRICING
Q: What payment methods do you accept?
A: We accept all major credit cards (Visa, Mastercard, American Express), 
PayPal, and M-Pesa for customers in Kenya.

Q: Do you offer price matching?
A: Yes! If you find a lower price on an identical item from a competitor, 
we'll match it. Contact us with proof of the lower price.

PRODUCT INFORMATION
Q: Are your products authentic?
A: Yes, all our products are 100% authentic and sourced directly from 
authorized distributors and manufacturers.

Q: Do you offer warranties?
A: Most electronics come with a 1-year manufacturer warranty. Extended 
warranty options are available at checkout.

CUSTOMER SERVICE
Q: How can I contact customer service?
A: You can reach us via WhatsApp, email (support@starterstore.com), or 
phone (+254-XXX-XXXX). Our hours are Monday-Friday, 9am-5pm EAT.

Q: Do you have a physical store?
A: We are primarily an online store, but we have a showroom in Nairobi 
where you can view select products by appointment.
"""
        
        self.stdout.write(faq_content)
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Test user setup complete!\n'))
        self.stdout.write(f'\n📋 Test Details:')
        self.stdout.write(f'   Tenant: {tenant.name} ({tenant.slug})')
        self.stdout.write(f'   Customer: {customer.name} ({phone})')
        self.stdout.write(f'   Conversation ID: {conversation.id}')
        self.stdout.write(f'   Messages: {conversation.messages.count()}')
        self.stdout.write(f'   Products: {Product.objects.filter(tenant=tenant).count()}')
        self.stdout.write(f'   Services: {Service.objects.filter(tenant=tenant).count()}')
        self.stdout.write(f'   RAG Enabled: ✓')
        self.stdout.write(f'\n📝 Next Steps:')
        self.stdout.write(f'   1. Upload the FAQ content above as a document via API:')
        self.stdout.write(f'      POST /v1/documents/upload')
        self.stdout.write(f'   2. Test RAG by sending messages from {phone}')
        self.stdout.write(f'   3. Ask questions like "What is your return policy?"')
        self.stdout.write(f'   4. Verify source attribution in responses')
        self.stdout.write(f'\n🧪 Test Queries:')
        self.stdout.write(f'   - "What is your return policy?"')
        self.stdout.write(f'   - "Tell me about the iPhone 15 Pro"')
        self.stdout.write(f'   - "Do you ship internationally?"')
        self.stdout.write(f'   - "Can I book a haircut appointment?"')
        self.stdout.write(f'   - "What payment methods do you accept?"')
        self.stdout.write(f'\n')
