#!/usr/bin/env python
"""Setup script for Starter Store tenant with dummy data"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenants.models import Tenant, TenantSettings
from apps.bot.models import AgentConfiguration, KnowledgeEntry
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service, ServiceVariant
from apps.rbac.models import TenantUser, Role
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

def main():
    # Try to find by WhatsApp number first, then by name
    try:
        tenant = Tenant.objects.get(whatsapp_number="+14155238886")
        created = False
        print(f"Found existing tenant by WhatsApp number: {tenant.name}")
    except Tenant.DoesNotExist:
        try:
            tenant = Tenant.objects.get(name="Starter Store")
            created = False
            print(f"Found existing tenant by name: {tenant.name}")
        except Tenant.DoesNotExist:
            tenant = Tenant.objects.create(
                name="Starter Store",
                slug="starter-store",
                status="active",
                whatsapp_number="+14155238886"
            )
            created = True
            print(f"Created new tenant: {tenant.name}")
    
    # Update tenant details
    tenant.name = "Starter Store"
    tenant.status = "active"
    if not tenant.whatsapp_number:
        tenant.whatsapp_number = "+14155238886"
    tenant.save()
    print(f"Tenant ID: {tenant.id}")
    
    # Create owner user
    owner_user, user_created = User.objects.get_or_create(
        email="owner@starterstore.com",
        defaults={
            "username": "starter_owner",
            "first_name": "Store",
            "last_name": "Owner",
            "is_active": True
        }
    )
    if user_created:
        owner_user.set_password("ChangeMe123!")
        owner_user.save()
        print(f"Created owner user: {owner_user.email} (password: ChangeMe123!)")
    else:
        print(f"Found owner user: {owner_user.email}")
    
    # Create TenantUser with Owner role
    owner_role = Role.objects.filter(tenant=tenant, name="Owner").first()
    tenant_user, _ = TenantUser.objects.get_or_create(
        tenant=tenant,
        user=owner_user,
        defaults={"is_active": True}
    )
    if owner_role:
        tenant_user.roles.add(owner_role)
        print(f"Assigned Owner role to {owner_user.email}")
    
    settings, _ = TenantSettings.objects.get_or_create(tenant=tenant)
    settings.twilio_sid = "ACbd4391b4e4270acaf4bce53b26c2683a"
    settings.twilio_token = "87955d40bc1ca76a583cd5d10fa67be0"
    settings.save()
    print(f"Saved Twilio credentials for {tenant.name}")
    
    agent_config, _ = AgentConfiguration.objects.get_or_create(
        tenant=tenant,
        defaults={
            "agent_name": "Stella",
            "personality_traits": {
                "tone": "friendly",
                "style": "helpful",
                "traits": ["patient", "knowledgeable", "enthusiastic"]
            },
            "tone": "friendly",
            "default_model": "gpt-4o",
            "fallback_models": ["gpt-4o-mini"],
            "temperature": 0.7,
            "max_response_length": 500,
            "behavioral_restrictions": [
                "Never share customer data",
                "Always be respectful",
                "Don't make promises about delivery"
            ],
            "confidence_threshold": 0.7,
            "auto_handoff_topics": ["complaints", "refunds", "custom_orders"],
            "max_low_confidence_attempts": 2,
            "enable_proactive_suggestions": True,
            "enable_spelling_correction": True,
            "enable_rich_messages": True
        }
    )
    print(f"Created agent: {agent_config.agent_name}")
    
    faqs = [
        {
            "title": "What are your business hours?",
            "content": "We are open Monday to Saturday from 9:00 AM to 6:00 PM EAT. Closed on Sundays.",
            "category": "General",
            "entry_type": "faq"
        },
        {
            "title": "Do you offer delivery?",
            "content": "Yes! Delivery within Nairobi for orders above KES 1,000. Takes 1-2 days. Fee: KES 200 CBD, KES 350 other areas.",
            "category": "Delivery",
            "entry_type": "faq"
        },
        {
            "title": "What payment methods do you accept?",
            "content": "M-Pesa (0712345678), cash on delivery, bank transfers (KCB 1234567890).",
            "category": "Payment",
            "entry_type": "faq"
        },
        {
            "title": "What is your return policy?",
            "content": "Returns within 7 days if unused. Refunds in 5-7 days. Contact us with order number.",
            "category": "Returns",
            "entry_type": "policy"
        },
        {
            "title": "Where is your store located?",
            "content": "Tom Mboya Street, Nairobi CBD, next to Uchumi. Branch at Sarit Centre Westlands.",
            "category": "Location",
            "entry_type": "location"
        },
        {
            "title": "Do you have a loyalty program?",
            "content": "Yes! Starter Rewards: 1 point per KES 100. 100 points = KES 100 discount.",
            "category": "Rewards",
            "entry_type": "faq"
        }
    ]
    
    for faq_data in faqs:
        KnowledgeEntry.objects.get_or_create(
            tenant=tenant,
            title=faq_data["title"],
            defaults={
                "content": faq_data["content"],
                "category": faq_data["category"],
                "entry_type": faq_data["entry_type"],
                "is_active": True,
                "priority": 1
            }
        )
    print(f"Created {len(faqs)} FAQs")
    
    products_data = [
        {
            "name": "Premium Coffee Beans - Arabica",
            "description": "High-quality Arabica from Mount Kenya. Rich flavor with chocolate and caramel hints.",
            "price": "1200.00",
            "category": "Beverages",
            "stock": 50
        },
        {
            "name": "Organic Honey - 500g",
            "description": "Pure raw honey from local beekeepers. No additives.",
            "price": "800.00",
            "category": "Food",
            "stock": 30
        },
        {
            "name": "Handwoven Basket - Large",
            "description": "Beautiful basket by local artisans. Eco-friendly.",
            "price": "1500.00",
            "category": "Home & Living",
            "stock": 15
        },
        {
            "name": "Shea Butter Body Lotion - 250ml",
            "description": "Moisturizing lotion with shea butter and vitamin E.",
            "price": "650.00",
            "category": "Beauty",
            "stock": 40
        },
        {
            "name": "Cotton T-Shirt - Unisex",
            "description": "100% cotton, multiple colors. Sizes: S, M, L, XL.",
            "price": "900.00",
            "category": "Clothing",
            "stock": 60
        }
    ]
    
    for prod_data in products_data:
        product, _ = Product.objects.get_or_create(
            tenant=tenant,
            name=prod_data["name"],
            defaults={
                "description": prod_data["description"],
                "category": prod_data["category"],
                "is_active": True
            }
        )
        ProductVariant.objects.get_or_create(
            product=product,
            name="Default",
            defaults={
                "price": Decimal(prod_data["price"]),
                "stock_quantity": prod_data["stock"],
                "is_active": True
            }
        )
    
    print(f"Created {len(products_data)} products")
    
    services_data = [
        {
            "name": "Personal Shopping Assistant",
            "description": "Expert help to find what you need. Product suggestions and guidance.",
            "duration": 60,
            "price": "500.00"
        },
        {
            "name": "Gift Wrapping Service",
            "description": "Professional wrapping with premium paper, ribbon, and card.",
            "duration": 15,
            "price": "200.00"
        },
        {
            "name": "Product Consultation",
            "description": "30-min consultation with product experts.",
            "duration": 30,
            "price": "300.00"
        }
    ]
    
    for svc_data in services_data:
        service, _ = Service.objects.get_or_create(
            tenant=tenant,
            name=svc_data["name"],
            defaults={
                "description": svc_data["description"],
                "duration_minutes": svc_data["duration"],
                "is_active": True
            }
        )
        ServiceVariant.objects.get_or_create(
            service=service,
            name="Standard",
            defaults={
                "price": Decimal(svc_data["price"]),
                "duration_minutes": svc_data["duration"],
                "is_active": True
            }
        )
    
    print(f"Created {len(services_data)} services")
    
    print("\n" + "="*60)
    print(f"SETUP COMPLETE FOR {tenant.name.upper()}")
    print("="*60)
    print(f"Tenant ID: {tenant.id}")
    print(f"Owner Email: {owner_user.email}")
    print(f"Owner Password: ChangeMe123! (CHANGE THIS!)")
    print(f"Agent Name: {agent_config.agent_name}")
    print(f"WhatsApp: {tenant.whatsapp_number}")
    print(f"Products: {Product.objects.filter(tenant=tenant).count()}")
    print(f"Services: {Service.objects.filter(tenant=tenant).count()}")
    print(f"FAQs: {KnowledgeEntry.objects.filter(tenant=tenant).count()}")
    print("\nNext Steps:")
    print("1. Change the owner password immediately")
    print("2. Generate API key: python manage.py generate_api_key --tenant-id " + str(tenant.id))
    print("3. Test WhatsApp: Send message to +14155238886")
    print("="*60)

if __name__ == '__main__':
    main()
