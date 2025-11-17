#!/usr/bin/env python
"""
Seed realistic demo data for testing.
"""
import os
import sys
import django
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenants.models import Tenant, Customer
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service, ServiceVariant, AvailabilityWindow
from apps.messaging.models import Conversation, Message


def seed_bella_beauty_salon():
    """Seed Bella Beauty Salon - beauty services business."""
    print("\n🎨 Seeding Bella Beauty Salon...")
    
    tenant = Tenant.objects.filter(whatsapp_number='+14155238886').first()
    if not tenant:
        print("❌ Tenant not found")
        return
    
    tenant.name = "Bella Beauty Salon"
    tenant.slug = "bella-beauty"
    tenant.timezone = "Africa/Nairobi"
    tenant.contact_email = "info@bellabeauty.co.ke"
    tenant.save()
    print(f"✅ Updated: {tenant.name}")
    
    # Services
    services = [
        ('Hair Styling', 'Professional hair services', [
            ('Haircut & Blow Dry', 1500, 60),
            ('Hair Coloring', 3500, 120),
            ('Deep Conditioning', 2000, 45),
        ]),
        ('Manicure & Pedicure', 'Nail care services', [
            ('Basic Manicure', 800, 30),
            ('Gel Manicure', 1500, 45),
            ('Spa Pedicure', 1200, 60),
        ]),
        ('Facial Treatments', 'Rejuvenating facials', [
            ('Classic Facial', 2500, 60),
            ('Anti-Aging Facial', 4000, 90),
        ]),
        ('Makeup Services', 'Professional makeup', [
            ('Bridal Makeup', 8000, 120),
            ('Event Makeup', 3500, 60),
        ]),
    ]
    
    for svc_title, svc_desc, variants in services:
        service, _ = Service.objects.get_or_create(
            tenant=tenant,
            title=svc_title,
            defaults={'description': svc_desc, 'is_active': True}
        )
        
        for var_title, price, duration in variants:
            ServiceVariant.objects.get_or_create(
                service=service,
                title=var_title,
                defaults={'price': Decimal(price), 'duration_minutes': duration}
            )
        
        # Add availability (Mon-Fri, 9 AM - 6 PM)
        for day in range(5):
            AvailabilityWindow.objects.get_or_create(
                tenant=tenant,
                service=service,
                weekday=day,
                defaults={
                    'start_time': '09:00',
                    'end_time': '18:00',
                    'capacity': 3,
                    'timezone': tenant.timezone
                }
            )
        
        print(f"  ✅ {svc_title} ({len(variants)} variants)")
    
    # Customers
    customers = [
        ('+254722111222', 'Sarah Wanjiku', 'Hi, I need to book a haircut'),
        ('+254733222333', 'Grace Akinyi', 'Do you have availability for manicure?'),
        ('+254744333444', 'Mary Njeri', 'I want bridal makeup'),
    ]
    
    for phone, name, msg in customers:
        customer, _ = Customer.objects.get_or_create(
            tenant=tenant, phone_e164=phone, defaults={'name': name}
        )
        conv, _ = Conversation.objects.get_or_create(
            tenant=tenant, customer=customer,
            defaults={'status': 'bot', 'channel': 'whatsapp'}
        )
        Message.objects.get_or_create(
            conversation=conv, direction='in',
            defaults={'text': msg, 'message_type': 'customer_inbound', 'provider_status': 'delivered'}
        )
        print(f"  ✅ {name}")
    
    print(f"✅ Bella Beauty Salon complete!\n")


def seed_techmart_electronics():
    """Seed TechMart Electronics - e-commerce store."""
    print("\n💻 Seeding TechMart Electronics...")
    
    tenants = Tenant.objects.exclude(whatsapp_number='+14155238886')
    if not tenants.exists():
        print("❌ No additional tenants")
        return
    
    tenant = tenants.first()
    tenant.name = "TechMart Electronics"
    tenant.slug = "techmart"
    tenant.timezone = "Africa/Nairobi"
    tenant.contact_email = "sales@techmart.co.ke"
    tenant.save()
    print(f"✅ Updated: {tenant.name}")
    
    # Products
    products = [
        ('Samsung Galaxy A54', '6.4" display, 128GB, 50MP camera', [
            ('Black - 128GB', 'SAM-A54-BLK-128', 42000, 15),
            ('White - 128GB', 'SAM-A54-WHT-128', 42000, 10),
            ('Blue - 256GB', 'SAM-A54-BLU-256', 48000, 8),
        ]),
        ('Apple AirPods Pro', 'Active Noise Cancellation, Wireless charging', [
            ('AirPods Pro (2nd Gen)', 'APP-PRO-2ND', 28000, 20),
        ]),
        ('HP Pavilion Laptop', 'Intel Core i5, 8GB RAM, 512GB SSD', [
            ('Silver - i5/8GB/512GB', 'HP-PAV-SLV-I5', 65000, 5),
            ('Black - i7/16GB/1TB', 'HP-PAV-BLK-I7', 85000, 3),
        ]),
        ('Sony WH-1000XM5', 'Premium noise cancelling headphones', [
            ('Black', 'SONY-WH1000XM5-BLK', 38000, 12),
            ('Silver', 'SONY-WH1000XM5-SLV', 38000, 8),
        ]),
        ('Samsung 55" 4K TV', 'Crystal UHD 4K, HDR, Smart TV', [
            ('55" Crystal UHD', 'SAM-TV-55-4K', 58000, 6),
        ]),
    ]
    
    for prod_title, prod_desc, variants in products:
        product, _ = Product.objects.get_or_create(
            tenant=tenant,
            title=prod_title,
            defaults={
                'description': prod_desc,
                'price': Decimal('0'),
                'external_source': 'manual'
            }
        )
        
        for var_title, sku, price, stock in variants:
            ProductVariant.objects.get_or_create(
                product=product,
                sku=sku,
                defaults={'title': var_title, 'price': Decimal(price), 'stock': stock}
            )
        
        print(f"  ✅ {prod_title} ({len(variants)} variants)")
    
    # Customers
    customers = [
        ('+254722555666', 'John Kamau', 'Do you have Samsung phones?'),
        ('+254733666777', 'Peter Omondi', 'I need a laptop for work'),
        ('+254744777888', 'David Mwangi', 'What headphones do you have?'),
    ]
    
    for phone, name, msg in customers:
        customer, _ = Customer.objects.get_or_create(
            tenant=tenant, phone_e164=phone, defaults={'name': name}
        )
        conv, _ = Conversation.objects.get_or_create(
            tenant=tenant, customer=customer,
            defaults={'status': 'bot', 'channel': 'whatsapp'}
        )
        Message.objects.get_or_create(
            conversation=conv, direction='in',
            defaults={'text': msg, 'message_type': 'customer_inbound', 'provider_status': 'delivered'}
        )
        print(f"  ✅ {name}")
    
    print(f"✅ TechMart Electronics complete!\n")


def seed_fresh_bites_restaurant():
    """Seed Fresh Bites Restaurant - food delivery."""
    print("\n🍔 Seeding Fresh Bites Restaurant...")
    
    tenants = Tenant.objects.exclude(whatsapp_number='+14155238886').order_by('id')
    if tenants.count() < 2:
        print("❌ Not enough tenants")
        return
    
    tenant = tenants[1] if tenants.count() > 1 else tenants.first()
    tenant.name = "Fresh Bites Restaurant"
    tenant.slug = "fresh-bites"
    tenant.timezone = "Africa/Nairobi"
    tenant.contact_email = "orders@freshbites.co.ke"
    tenant.save()
    print(f"✅ Updated: {tenant.name}")
    
    # Menu items
    products = [
        ('Burgers', 'Juicy beef burgers', [
            ('Classic Beef Burger', 'BRG-CLASSIC', 650, 999),
            ('Cheese Burger', 'BRG-CHEESE', 750, 999),
            ('Chicken Burger', 'BRG-CHICKEN', 700, 999),
        ]),
        ('Pizza', 'Wood-fired pizzas', [
            ('Margherita - Medium', 'PZA-MARG-M', 900, 999),
            ('Pepperoni - Medium', 'PZA-PEPP-M', 1100, 999),
            ('BBQ Chicken - Large', 'PZA-BBQ-L', 1400, 999),
        ]),
        ('Pasta', 'Fresh pasta dishes', [
            ('Spaghetti Carbonara', 'PST-CARB', 850, 999),
            ('Penne Arrabiata', 'PST-ARRAB', 800, 999),
        ]),
        ('Beverages', 'Refreshing drinks', [
            ('Fresh Juice - Orange', 'JCE-ORANGE', 250, 999),
            ('Fresh Juice - Passion', 'JCE-PASSION', 250, 999),
            ('Soda - 500ml', 'SDA-500', 100, 999),
        ]),
        ('Desserts', 'Sweet treats', [
            ('Chocolate Cake', 'DST-CHOC-CAKE', 400, 999),
            ('Ice Cream - Vanilla', 'DST-ICE-VAN', 300, 999),
        ]),
    ]
    
    for prod_title, prod_desc, variants in products:
        product, _ = Product.objects.get_or_create(
            tenant=tenant,
            title=prod_title,
            defaults={
                'description': prod_desc,
                'price': Decimal('0'),
                'external_source': 'manual'
            }
        )
        
        for var_title, sku, price, stock in variants:
            ProductVariant.objects.get_or_create(
                product=product,
                sku=sku,
                defaults={'title': var_title, 'price': Decimal(price), 'stock': stock}
            )
        
        print(f"  ✅ {prod_title} ({len(variants)} variants)")
    
    # Customers
    customers = [
        ('+254722888999', 'Alice Wambui', 'Hi, I want to order food'),
        ('+254733999000', 'James Otieno', 'Do you deliver to Westlands?'),
        ('+254744000111', 'Lucy Chebet', 'What pizzas do you have?'),
    ]
    
    for phone, name, msg in customers:
        customer, _ = Customer.objects.get_or_create(
            tenant=tenant, phone_e164=phone, defaults={'name': name}
        )
        conv, _ = Conversation.objects.get_or_create(
            tenant=tenant, customer=customer,
            defaults={'status': 'bot', 'channel': 'whatsapp'}
        )
        Message.objects.get_or_create(
            conversation=conv, direction='in',
            defaults={'text': msg, 'message_type': 'customer_inbound', 'provider_status': 'delivered'}
        )
        print(f"  ✅ {name}")
    
    print(f"✅ Fresh Bites Restaurant complete!\n")


def main():
    print("=" * 60)
    print("🌱 SEEDING REALISTIC DEMO DATA")
    print("=" * 60)
    
    seed_bella_beauty_salon()
    seed_techmart_electronics()
    seed_fresh_bites_restaurant()
    
    print("=" * 60)
    print("✅ ALL DEMO DATA SEEDED!")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"  Tenants: {Tenant.objects.count()}")
    print(f"  Products: {Product.objects.count()}")
    print(f"  Services: {Service.objects.count()}")
    print(f"  Customers: {Customer.objects.count()}")
    print(f"  Conversations: {Conversation.objects.count()}")
    print("\n🎉 Ready for testing!\n")


if __name__ == '__main__':
    main()
