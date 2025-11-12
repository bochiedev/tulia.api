"""
Management command to create comprehensive demo data for testing and demos.

Creates:
- 3 demo tenants (one per subscription tier)
- 50 products per tenant with variants
- 10 services per tenant with availability windows
- 100 customers per tenant with varied consent preferences
- Historical messages and orders for analytics
- Appointments and bookings
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from datetime import timedelta, datetime, time
from decimal import Decimal
import random
import uuid

from apps.tenants.models import Tenant, SubscriptionTier, Customer
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service, ServiceVariant, AvailabilityWindow, Appointment
from apps.messaging.models import (
    Conversation, Message, MessageTemplate, 
    CustomerPreferences, ConsentEvent
)
from apps.orders.models import Order
from apps.rbac.models import User, TenantUser, Role
from apps.rbac.services import RBACService


class Command(BaseCommand):
    help = 'Create comprehensive demo data for testing and demos'
    
    # Product categories and sample data
    PRODUCT_CATEGORIES = {
        'Electronics': [
            ('Wireless Headphones', 79.99, 'Premium wireless headphones with noise cancellation'),
            ('Smart Watch', 299.99, 'Fitness tracking smartwatch with heart rate monitor'),
            ('Bluetooth Speaker', 49.99, 'Portable waterproof Bluetooth speaker'),
            ('Phone Case', 19.99, 'Protective phone case with card holder'),
            ('USB-C Cable', 12.99, 'Fast charging USB-C cable 6ft'),
            ('Power Bank', 39.99, '20000mAh portable power bank'),
            ('Wireless Charger', 29.99, 'Fast wireless charging pad'),
            ('Screen Protector', 9.99, 'Tempered glass screen protector'),
            ('Car Mount', 24.99, 'Magnetic car phone mount'),
            ('Earbuds', 129.99, 'True wireless earbuds with charging case'),
        ],
        'Clothing': [
            ('T-Shirt', 24.99, 'Premium cotton t-shirt'),
            ('Jeans', 59.99, 'Classic fit denim jeans'),
            ('Hoodie', 49.99, 'Comfortable pullover hoodie'),
            ('Sneakers', 89.99, 'Athletic running sneakers'),
            ('Jacket', 79.99, 'Lightweight windbreaker jacket'),
            ('Dress', 69.99, 'Elegant evening dress'),
            ('Shorts', 34.99, 'Casual summer shorts'),
            ('Socks', 12.99, 'Pack of 5 athletic socks'),
            ('Hat', 19.99, 'Adjustable baseball cap'),
            ('Scarf', 29.99, 'Soft winter scarf'),
        ],
        'Home & Kitchen': [
            ('Coffee Maker', 79.99, 'Programmable drip coffee maker'),
            ('Blender', 59.99, 'High-speed blender for smoothies'),
            ('Toaster', 39.99, '4-slice stainless steel toaster'),
            ('Knife Set', 89.99, 'Professional chef knife set'),
            ('Cutting Board', 24.99, 'Bamboo cutting board'),
            ('Mixing Bowls', 29.99, 'Set of 5 stainless steel bowls'),
            ('Cookware Set', 149.99, 'Non-stick cookware set 10-piece'),
            ('Dish Rack', 34.99, 'Stainless steel dish drying rack'),
            ('Storage Containers', 19.99, 'Food storage container set'),
            ('Kitchen Scale', 22.99, 'Digital kitchen scale'),
        ],
        'Beauty & Personal Care': [
            ('Face Cream', 34.99, 'Hydrating face moisturizer'),
            ('Shampoo', 14.99, 'Nourishing shampoo for all hair types'),
            ('Body Lotion', 19.99, 'Moisturizing body lotion'),
            ('Perfume', 79.99, 'Eau de parfum 50ml'),
            ('Lip Balm', 4.99, 'Moisturizing lip balm'),
            ('Sunscreen', 24.99, 'SPF 50 sunscreen lotion'),
            ('Hair Dryer', 59.99, 'Professional ionic hair dryer'),
            ('Makeup Brush Set', 39.99, 'Professional makeup brush set'),
            ('Nail Polish', 9.99, 'Long-lasting nail polish'),
            ('Face Mask', 12.99, 'Hydrating sheet mask pack of 5'),
        ],
        'Sports & Outdoors': [
            ('Yoga Mat', 29.99, 'Non-slip yoga mat with carrying strap'),
            ('Dumbbell Set', 89.99, 'Adjustable dumbbell set'),
            ('Resistance Bands', 19.99, 'Set of 5 resistance bands'),
            ('Water Bottle', 24.99, 'Insulated stainless steel water bottle'),
            ('Gym Bag', 39.99, 'Durable gym duffel bag'),
            ('Jump Rope', 14.99, 'Speed jump rope for cardio'),
            ('Foam Roller', 29.99, 'High-density foam roller'),
            ('Exercise Ball', 24.99, 'Anti-burst exercise ball'),
            ('Bike Lock', 34.99, 'Heavy-duty bike lock'),
            ('Running Belt', 19.99, 'Adjustable running belt with pockets'),
        ],
    }
    
    # Service categories and sample data
    SERVICE_CATEGORIES = {
        'Beauty & Wellness': [
            ('Haircut', 35, 30, 'Professional haircut and styling'),
            ('Hair Coloring', 85, 90, 'Full hair coloring service'),
            ('Manicure', 25, 45, 'Classic manicure'),
            ('Pedicure', 35, 60, 'Relaxing pedicure'),
            ('Facial Treatment', 75, 60, 'Deep cleansing facial'),
            ('Massage', 90, 60, 'Full body relaxation massage'),
            ('Waxing', 45, 30, 'Professional waxing service'),
            ('Makeup Application', 65, 45, 'Professional makeup'),
        ],
        'Professional Services': [
            ('Consultation', 150, 60, 'Professional consultation'),
            ('Legal Advice', 200, 60, 'Legal consultation'),
            ('Tax Preparation', 175, 90, 'Tax filing service'),
            ('Business Coaching', 250, 90, 'Business strategy session'),
            ('Career Counseling', 125, 60, 'Career guidance session'),
            ('Financial Planning', 200, 90, 'Financial planning consultation'),
        ],
        'Home Services': [
            ('House Cleaning', 120, 120, 'Deep house cleaning'),
            ('Lawn Mowing', 50, 60, 'Lawn mowing and edging'),
            ('Plumbing Repair', 95, 60, 'Plumbing repair service'),
            ('Electrical Work', 110, 60, 'Electrical repair service'),
            ('Painting', 200, 240, 'Interior painting service'),
            ('Carpet Cleaning', 85, 90, 'Professional carpet cleaning'),
        ],
    }
    
    # Customer names for demo data
    FIRST_NAMES = [
        'James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
        'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica',
        'Thomas', 'Sarah', 'Charles', 'Karen', 'Christopher', 'Nancy', 'Daniel', 'Lisa',
        'Matthew', 'Betty', 'Anthony', 'Margaret', 'Mark', 'Sandra', 'Donald', 'Ashley',
        'Steven', 'Kimberly', 'Paul', 'Emily', 'Andrew', 'Donna', 'Joshua', 'Michelle',
    ]
    
    LAST_NAMES = [
        'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
        'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas',
        'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White',
        'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young',
    ]
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--skip-tiers',
            action='store_true',
            help='Skip subscription tier seeding',
        )
        parser.add_argument(
            '--skip-permissions',
            action='store_true',
            help='Skip permission seeding',
        )
        parser.add_argument(
            '--tenants-only',
            action='store_true',
            help='Only create tenants, skip products/services/customers',
        )
    
    def handle(self, *args, **options):
        """Create comprehensive demo data."""
        
        self.stdout.write('=' * 70)
        self.stdout.write('Creating Comprehensive Demo Data')
        self.stdout.write('=' * 70)
        
        # Ensure subscription tiers exist
        if not options['skip_tiers']:
            self.stdout.write('\n1. Checking subscription tiers...')
            if SubscriptionTier.objects.count() == 0:
                self.stdout.write('   Seeding subscription tiers...')
                call_command('seed_subscription_tiers')
            else:
                self.stdout.write(f'   ✓ {SubscriptionTier.objects.count()} tiers exist')
        
        # Ensure permissions exist
        if not options['skip_permissions']:
            self.stdout.write('\n2. Checking permissions...')
            from apps.rbac.models import Permission
            if Permission.objects.count() == 0:
                self.stdout.write('   Seeding permissions...')
                call_command('seed_permissions')
            else:
                self.stdout.write(f'   ✓ {Permission.objects.count()} permissions exist')
        
        # Get subscription tiers
        starter_tier = SubscriptionTier.objects.get(name='Starter')
        growth_tier = SubscriptionTier.objects.get(name='Growth')
        enterprise_tier = SubscriptionTier.objects.get(name='Enterprise')
        
        # Create 3 demo tenants
        self.stdout.write('\n3. Creating demo tenants...')
        
        tenants_data = [
            {
                'name': 'Starter Store',
                'slug': 'starter-store',
                'tier': starter_tier,
                'phone': '+15555551001',
                'owner_email': 'owner@starter.demo',
            },
            {
                'name': 'Growth Business',
                'slug': 'growth-business',
                'tier': growth_tier,
                'phone': '+15555551002',
                'owner_email': 'owner@growth.demo',
            },
            {
                'name': 'Enterprise Corp',
                'slug': 'enterprise-corp',
                'tier': enterprise_tier,
                'phone': '+15555551003',
                'owner_email': 'owner@enterprise.demo',
            },
        ]
        
        created_tenants = []
        
        for tenant_data in tenants_data:
            tenant = self._create_tenant(tenant_data)
            created_tenants.append(tenant)
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ Created: {tenant.name} ({tenant.subscription_tier.name})')
            )
        
        if options['tenants_only']:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write('Tenants created successfully!')
            self.stdout.write('=' * 70)
            return
        
        # Seed data for each tenant
        for tenant in created_tenants:
            self.stdout.write(f'\n4. Seeding data for {tenant.name}...')
            
            # Create products
            self.stdout.write(f'   Creating 50 products...')
            products = self._create_products(tenant, count=50)
            self.stdout.write(f'   ✓ Created {len(products)} products')
            
            # Create services
            self.stdout.write(f'   Creating 10 services...')
            services = self._create_services(tenant, count=10)
            self.stdout.write(f'   ✓ Created {len(services)} services')
            
            # Create customers
            self.stdout.write(f'   Creating 100 customers...')
            customers = self._create_customers(tenant, count=100)
            self.stdout.write(f'   ✓ Created {len(customers)} customers')
            
            # Create historical data
            self.stdout.write(f'   Creating historical messages and orders...')
            self._create_historical_data(tenant, customers, products, services)
            self.stdout.write(f'   ✓ Created historical data')
        
        # Display summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('Demo Data Created Successfully!')
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'\nCreated:')
        self.stdout.write(f'  Tenants: {len(created_tenants)}')
        self.stdout.write(f'  Products: {Product.objects.count()}')
        self.stdout.write(f'  Services: {Service.objects.count()}')
        self.stdout.write(f'  Customers: {Customer.objects.count()}')
        self.stdout.write(f'  Messages: {Message.objects.count()}')
        self.stdout.write(f'  Orders: {Order.objects.count()}')
        self.stdout.write(f'  Appointments: {Appointment.objects.count()}')
        
        self.stdout.write(f'\nDemo Tenants:')
        for tenant in created_tenants:
            self.stdout.write(f'  - {tenant.name} ({tenant.slug})')
            self.stdout.write(f'    Tier: {tenant.subscription_tier.name}')
            self.stdout.write(f'    Phone: {tenant.whatsapp_number}')
            self.stdout.write(f'    ID: {tenant.id}')
        
        self.stdout.write('')
    
    def _create_tenant(self, data):
        """Create a demo tenant."""
        # Check if tenant already exists
        existing = Tenant.objects.filter(slug=data['slug']).first()
        if existing:
            return existing
        
        # Generate demo credentials
        demo_sid = f'AC{uuid.uuid4().hex[:32]}'
        demo_token = uuid.uuid4().hex
        demo_secret = uuid.uuid4().hex
        
        tenant = Tenant.objects.create(
            name=data['name'],
            slug=data['slug'],
            status='trial',
            subscription_tier=data['tier'],
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
            whatsapp_number=data['phone'],
            twilio_sid=demo_sid,
            twilio_token=demo_token,
            webhook_secret=demo_secret,
            contact_email=data['owner_email'],
            timezone='America/New_York',
        )
        
        # Seed roles for tenant
        call_command('seed_tenant_roles', tenant=tenant.slug, verbosity=0)
        
        # Create owner user
        user = User.objects.by_email(data['owner_email'])
        if not user:
            user = User.objects.create_user(
                email=data['owner_email'],
                password='demo123!',
                first_name='Owner',
                last_name='User',
            )
        
        # Create tenant membership
        tenant_user, _ = TenantUser.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={
                'invite_status': 'accepted',
                'joined_at': timezone.now(),
            }
        )
        
        # Assign Owner role
        role = Role.objects.by_name(tenant, 'Owner')
        if role:
            RBACService.assign_role(
                tenant_user=tenant_user,
                role=role,
                assigned_by=None,
                request=None
            )
        
        return tenant
    
    def _create_products(self, tenant, count=50):
        """Create demo products for a tenant."""
        products = []
        categories = list(self.PRODUCT_CATEGORIES.keys())
        
        for i in range(count):
            # Select category and product
            category = random.choice(categories)
            product_data = random.choice(self.PRODUCT_CATEGORIES[category])
            title, base_price, description = product_data
            
            # Add variation to title
            title = f"{title} - {category}"
            
            # Create product
            product = Product.objects.create(
                tenant=tenant,
                external_source='manual',
                title=title,
                description=description,
                price=Decimal(str(base_price)),
                currency='USD',
                sku=f'SKU-{uuid.uuid4().hex[:8].upper()}',
                stock=random.randint(0, 100) if random.random() > 0.2 else None,  # 80% have stock tracking
                is_active=True,
                images=[f'https://via.placeholder.com/400x400?text={title[:20]}'],
                metadata={'category': category},
            )
            
            # Create 1-3 variants for some products
            if random.random() > 0.5:
                variant_count = random.randint(1, 3)
                for v in range(variant_count):
                    variant_attrs = {}
                    variant_title = title
                    
                    if category == 'Clothing':
                        sizes = ['S', 'M', 'L', 'XL']
                        colors = ['Black', 'White', 'Blue', 'Red', 'Gray']
                        variant_attrs = {
                            'size': random.choice(sizes),
                            'color': random.choice(colors),
                        }
                        variant_title = f"{variant_attrs['size']} / {variant_attrs['color']}"
                    elif category == 'Electronics':
                        storage = ['64GB', '128GB', '256GB', '512GB']
                        variant_attrs = {'storage': random.choice(storage)}
                        variant_title = variant_attrs['storage']
                    else:
                        variant_title = f"Variant {v+1}"
                    
                    ProductVariant.objects.create(
                        product=product,
                        title=variant_title,
                        sku=f'{product.sku}-V{v+1}',
                        price=Decimal(str(base_price * random.uniform(0.9, 1.2))),
                        stock=random.randint(0, 50) if product.stock is not None else None,
                        attrs=variant_attrs,
                    )
            
            products.append(product)
        
        return products
    
    def _create_services(self, tenant, count=10):
        """Create demo services for a tenant."""
        services = []
        all_services = []
        
        # Flatten service categories
        for category, service_list in self.SERVICE_CATEGORIES.items():
            for service_data in service_list:
                all_services.append((category, *service_data))
        
        # Select random services
        selected_services = random.sample(all_services, min(count, len(all_services)))
        
        for category, title, price, duration, description in selected_services:
            # Create service
            service = Service.objects.create(
                tenant=tenant,
                title=title,
                description=description,
                base_price=Decimal(str(price)),
                currency='USD',
                is_active=True,
                requires_slot=True,
                images=[f'https://via.placeholder.com/400x400?text={title[:20]}'],
                metadata={'category': category},
            )
            
            # Create 1-2 variants
            variant_count = random.randint(1, 2)
            for v in range(variant_count):
                variant_duration = duration * (v + 1)
                variant_price = price * (v + 1) * 0.9  # Discount for longer sessions
                
                ServiceVariant.objects.create(
                    service=service,
                    title=f"{variant_duration} minutes",
                    duration_minutes=variant_duration,
                    price=Decimal(str(variant_price)),
                )
            
            # Create availability windows (Mon-Fri, 9am-5pm)
            for weekday in range(5):  # Monday to Friday
                AvailabilityWindow.objects.create(
                    tenant=tenant,
                    service=service,
                    weekday=weekday,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    capacity=random.randint(2, 5),
                    timezone='America/New_York',
                )
            
            services.append(service)
        
        return services
    
    def _create_customers(self, tenant, count=100):
        """Create demo customers for a tenant."""
        customers = []
        
        for i in range(count):
            first_name = random.choice(self.FIRST_NAMES)
            last_name = random.choice(self.LAST_NAMES)
            
            # Generate phone number
            phone = f'+1555{random.randint(1000000, 9999999)}'
            
            # Create customer
            customer = Customer.objects.create(
                tenant=tenant,
                phone_e164=phone,
                name=f'{first_name} {last_name}',
                timezone='America/New_York',
                tags=['demo', f'segment_{random.randint(1, 5)}'],
                last_seen_at=timezone.now() - timedelta(days=random.randint(0, 30)),
            )
            
            # Create preferences with varied consent
            consent_prefs = {
                'transactional_messages': True,  # Always true
                'reminder_messages': random.random() > 0.2,  # 80% opt-in
                'promotional_messages': random.random() > 0.6,  # 40% opt-in
            }
            
            prefs = CustomerPreferences.objects.create(
                tenant=tenant,
                customer=customer,
                **consent_prefs
            )
            
            # Create consent event for promotional if opted in
            if consent_prefs['promotional_messages']:
                ConsentEvent.objects.create(
                    tenant=tenant,
                    customer=customer,
                    preferences=prefs,
                    consent_type='promotional_messages',
                    previous_value=False,
                    new_value=True,
                    source='customer_initiated',
                    reason='Opted in during onboarding',
                )
            
            customers.append(customer)
        
        return customers
    
    def _create_historical_data(self, tenant, customers, products, services):
        """Create historical messages, orders, and appointments."""
        # Create conversations and messages for random customers
        sample_customers = random.sample(customers, min(30, len(customers)))
        
        for customer in sample_customers:
            # Create conversation
            conversation = Conversation.objects.create(
                tenant=tenant,
                customer=customer,
                status=random.choice(['open', 'bot', 'closed']),
                channel='whatsapp',
                last_intent=random.choice([
                    'BROWSE_PRODUCTS', 'PRODUCT_DETAILS', 'CHECK_AVAILABILITY',
                    'BOOK_APPOINTMENT', 'CHECKOUT_LINK'
                ]),
            )
            
            # Create 3-10 messages
            message_count = random.randint(3, 10)
            for m in range(message_count):
                direction = 'in' if m % 2 == 0 else 'out'
                message_type = 'customer_inbound' if direction == 'in' else 'bot_response'
                
                Message.objects.create(
                    conversation=conversation,
                    direction=direction,
                    message_type=message_type,
                    text=self._generate_sample_message(direction),
                    created_at=timezone.now() - timedelta(days=random.randint(1, 30)),
                )
        
        # Create orders for some customers
        order_customers = random.sample(customers, min(20, len(customers)))
        
        for customer in order_customers:
            # Create 1-3 orders
            order_count = random.randint(1, 3)
            for o in range(order_count):
                # Select 1-3 products
                order_products = random.sample(products, min(random.randint(1, 3), len(products)))
                
                items = []
                subtotal = Decimal('0')
                
                for product in order_products:
                    quantity = random.randint(1, 3)
                    price = product.price
                    
                    items.append({
                        'product_id': str(product.id),
                        'title': product.title,
                        'quantity': quantity,
                        'price': float(price),
                        'subtotal': float(price * quantity),
                    })
                    
                    subtotal += price * quantity
                
                shipping = Decimal('5.99')
                total = subtotal + shipping
                
                Order.objects.create(
                    tenant=tenant,
                    customer=customer,
                    currency='USD',
                    subtotal=subtotal,
                    shipping=shipping,
                    total=total,
                    status=random.choice(['paid', 'fulfilled', 'placed']),
                    items=items,
                    payment_ref=f'PAY-{uuid.uuid4().hex[:16].upper()}',
                    created_at=timezone.now() - timedelta(days=random.randint(1, 60)),
                )
        
        # Create appointments for some customers
        appointment_customers = random.sample(customers, min(15, len(customers)))
        
        for customer in appointment_customers:
            # Create 1-2 appointments
            appointment_count = random.randint(1, 2)
            for a in range(appointment_count):
                service = random.choice(services)
                variant = service.variants.first()
                
                # Random date in next 30 days
                days_ahead = random.randint(1, 30)
                start_dt = timezone.now() + timedelta(days=days_ahead, hours=random.randint(9, 16))
                end_dt = start_dt + timedelta(minutes=variant.duration_minutes if variant else 60)
                
                Appointment.objects.create(
                    tenant=tenant,
                    customer=customer,
                    service=service,
                    variant=variant,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    status=random.choice(['pending', 'confirmed']),
                    notes='Demo appointment',
                )
    
    def _generate_sample_message(self, direction):
        """Generate sample message text."""
        if direction == 'in':
            messages = [
                'Hi, I\'m looking for products',
                'Can you show me your services?',
                'What are your prices?',
                'I want to book an appointment',
                'Do you have this in stock?',
                'Can I check availability?',
                'I\'d like to place an order',
                'What time slots are available?',
            ]
        else:
            messages = [
                'Hello! How can I help you today?',
                'Here are our available products...',
                'I can help you book an appointment',
                'Let me check availability for you',
                'Here are the details you requested',
                'Your order has been confirmed!',
                'Would you like to see more options?',
                'Is there anything else I can help with?',
            ]
        
        return random.choice(messages)
