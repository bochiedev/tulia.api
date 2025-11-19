# Test Data Summary

## Quick Answer: YES, We Have Test Data! ✅

For the specific user you asked about:
- **Phone:** +254722241161
- **Tenant:** Starter Store (starter-store)

## How to Set It Up

### Option 1: Quick Setup (Recommended)

Run this single command:

```bash
python manage.py seed_test_user --phone=+254722241161 --tenant-slug=starter-store
```

This creates everything you need:
- ✅ Customer with phone +254722241161
- ✅ Active conversation with sample messages
- ✅ 5 sample products
- ✅ 3 sample services with availability
- ✅ Agent configuration with RAG enabled
- ✅ Sample FAQ content (displayed in output)

### Option 2: Full Demo Data

If you want comprehensive demo data for all tiers:

```bash
python manage.py seed_demo_data
```

This creates:
- 3 demo tenants (Starter, Growth, Enterprise)
- 50 products per tenant
- 10 services per tenant
- 100 customers per tenant
- Historical messages and orders

**Note:** This uses random US phone numbers (+1555...), not the specific Kenyan number.

## What's Included for Test User

### Customer Details
```
Phone: +254722241161
Name: Test Customer
Timezone: Africa/Nairobi
Tags: test, rag-testing
Preferences: All consents enabled
```

### Sample Conversation
```
1. Customer: "Hi, I need help with your products"
2. Bot: "Hello! I'd be happy to help you. What would you like to know?"
3. Customer: "What is your return policy?"
```

### Sample Products (5 items)
1. **iPhone 15 Pro** - $999.00
   - Latest iPhone with A17 Pro chip, titanium design
   
2. **Wireless Headphones** - $79.99
   - Premium noise-cancelling with 30-hour battery
   
3. **Smart Watch** - $299.99
   - Fitness tracking with heart rate monitor
   
4. **Coffee Maker** - $79.99
   - Programmable drip coffee maker
   
5. **Yoga Mat** - $29.99
   - Non-slip with carrying strap

### Sample Services (3 services)
1. **Haircut** - $25.00 (30 min)
   - Available Mon-Fri, 9am-5pm
   
2. **Massage** - $60.00 (60 min)
   - Available Mon-Fri, 9am-5pm
   
3. **Consultation** - $50.00 (45 min)
   - Available Mon-Fri, 9am-5pm

### RAG Configuration
```
Document Retrieval: ✅ Enabled
Database Retrieval: ✅ Enabled
Internet Enrichment: ✅ Enabled
Source Attribution: ✅ Enabled

Max Results:
- Documents: 3
- Database: 5
- Internet: 2

Agent Can Do:
- Answer questions about products and services
- Help with orders and bookings
- Provide information from knowledge base
- Search catalog in real-time
- Book appointments

Agent Cannot Do:
- Process payments directly
- Access external systems without integration
- Provide medical or legal advice
```

### Sample FAQ Document
Located at: `test_data/sample_faq.txt`

Contains information about:
- Return policy (30-day returns)
- Shipping information (5-7 days standard)
- Payment methods (cards, PayPal, M-Pesa)
- Product authenticity guarantees
- Warranty information
- Customer service contact details
- And more...

## Testing RAG Features

### Test Query 1: Document Retrieval
```
Query: "What is your return policy?"

Expected Response:
"According to our FAQ, we offer a 30-day return policy on all items. 
You can return any product within 30 days of purchase for a full refund, 
as long as it's in its original condition. [Source: sample_faq.txt]"
```

### Test Query 2: Database Retrieval
```
Query: "Tell me about the iPhone 15 Pro"

Expected Response:
"The iPhone 15 Pro is available in our catalog for $999. It features 
the latest A17 Pro chip, titanium design, and advanced camera system. 
We currently have it in stock. [Source: Our Catalog]"
```

### Test Query 3: Service Booking
```
Query: "Can I book a haircut appointment?"

Expected Response:
"Yes! We have haircut services available for $25 (30 minutes). 
Available slots: Monday-Friday, 9am-5pm. Would you like to book 
an appointment? [Source: Our Services]"
```

### Test Query 4: Multi-Source
```
Query: "Do you ship internationally?"

Expected Response:
"Yes, we ship to most countries worldwide. International shipping 
typically takes 10-15 business days. Customs fees may apply. 
[Source: sample_faq.txt]"
```

## Files Created

1. **apps/tenants/management/commands/seed_test_user.py**
   - Management command to create test user
   - Creates customer, conversation, products, services
   - Configures RAG settings

2. **test_data/sample_faq.txt**
   - Sample FAQ document for RAG testing
   - Contains policies, shipping, payment info
   - Ready to upload via API

3. **TEST_USER_SETUP_GUIDE.md**
   - Comprehensive setup and testing guide
   - Test scenarios and expected results
   - Troubleshooting tips

4. **TEST_DATA_SUMMARY.md** (this file)
   - Quick reference for test data
   - Summary of what's available

## Quick Start Commands

```bash
# 1. Create test user and data
python manage.py seed_test_user --phone=+254722241161 --tenant-slug=starter-store

# 2. Upload FAQ document (via API or admin)
# See TEST_USER_SETUP_GUIDE.md for API examples

# 3. Test via WhatsApp or API
# Send message: "What is your return policy?"

# 4. Verify in Django shell
python manage.py shell
>>> from apps.tenants.models import Customer
>>> customer = Customer.objects.get(phone_e164='+254722241161')
>>> print(customer.name, customer.tenant.name)
Test Customer Starter Store
```

## Verification

Check that everything is set up:

```python
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation
from apps.bot.models import AgentConfiguration
from apps.catalog.models import Product
from apps.services.models import Service

# Get tenant
tenant = Tenant.objects.get(slug='starter-store')

# Get customer
customer = Customer.objects.get(tenant=tenant, phone_e164='+254722241161')

# Get conversation
conversation = Conversation.objects.get(tenant=tenant, customer=customer)

# Check data
print(f"✓ Tenant: {tenant.name}")
print(f"✓ Customer: {customer.name} ({customer.phone_e164})")
print(f"✓ Conversation: {conversation.id}")
print(f"✓ Messages: {conversation.messages.count()}")
print(f"✓ Products: {Product.objects.filter(tenant=tenant).count()}")
print(f"✓ Services: {Service.objects.filter(tenant=tenant).count()}")

# Check RAG config
config = AgentConfiguration.objects.get(tenant=tenant)
print(f"✓ RAG Enabled: {config.enable_document_retrieval}")
```

## What's Different from seed_demo_data

| Feature | seed_demo_data | seed_test_user |
|---------|----------------|----------------|
| Phone Numbers | Random US (+1555...) | Specific Kenyan (+254722241161) |
| Tenants | 3 tenants (all tiers) | Uses existing tenant |
| Customers | 100 per tenant | 1 specific customer |
| Products | 50 per tenant | 5 essential products |
| Services | 10 per tenant | 3 essential services |
| RAG Config | Not configured | Fully configured |
| Purpose | Comprehensive demo | Specific testing |

## Next Steps

1. ✅ Run `seed_test_user` command
2. ✅ Upload FAQ document
3. ✅ Test RAG queries
4. ✅ Verify source attribution
5. ✅ Monitor performance

## Support

- Setup Guide: `TEST_USER_SETUP_GUIDE.md`
- RAG Integration: `apps/bot/docs/RAG_INTEGRATION_GUIDE.md`
- Implementation: `RAG_IMPLEMENTATION_SUMMARY.md`

---

**TL;DR:** Yes, we have test data! Run `python manage.py seed_test_user` to create a test user with phone +254722241161 for Starter Store tenant, complete with products, services, and RAG configuration.
