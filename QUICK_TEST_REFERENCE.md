# Quick Test Reference Card

## 🚀 One-Command Setup

```bash
python manage.py seed_test_user --phone=+254722241161 --tenant-slug=starter-store
```

## 📱 Test User Details

```
Phone:  +254722241161
Tenant: Starter Store
Name:   Test Customer
```

## 🧪 Quick Test Queries

Send these via WhatsApp to +254722241161:

1. **"What is your return policy?"**
   - Tests: Document retrieval
   - Expected: 30-day policy info + [Source: FAQ]

2. **"Tell me about the iPhone 15 Pro"**
   - Tests: Database retrieval
   - Expected: Product details + [Source: Catalog]

3. **"Can I book a haircut?"**
   - Tests: Service retrieval
   - Expected: Service info + availability

4. **"Do you ship internationally?"**
   - Tests: Multi-source retrieval
   - Expected: Shipping info + sources

## ✅ Verify Setup

```python
python manage.py shell

from apps.tenants.models import Customer
customer = Customer.objects.get(phone_e164='+254722241161')
print(f"✓ {customer.name} - {customer.tenant.name}")
```

## 📊 Check RAG Status

```python
from apps.bot.models import AgentConfiguration
config = AgentConfiguration.objects.get(tenant__slug='starter-store')
print(f"Document: {config.enable_document_retrieval}")
print(f"Database: {config.enable_database_retrieval}")
print(f"Internet: {config.enable_internet_enrichment}")
print(f"Attribution: {config.enable_source_attribution}")
```

## 📄 Sample Data Included

- ✅ 5 Products (iPhone, Headphones, Watch, Coffee Maker, Yoga Mat)
- ✅ 3 Services (Haircut, Massage, Consultation)
- ✅ Sample conversation with 3 messages
- ✅ FAQ content (in test_data/sample_faq.txt)
- ✅ RAG fully configured

## 🔍 Monitor RAG

```python
from apps.bot.models import AgentInteraction
interaction = AgentInteraction.objects.filter(
    conversation__customer__phone_e164='+254722241161'
).latest('created_at')

rag = interaction.metadata.get('rag_context')
if rag:
    print(f"Documents: {len(rag.get('document_results', []))}")
    print(f"Database: {len(rag.get('database_results', []))}")
    print(f"Time: {rag.get('retrieval_time_ms')}ms")
```

## 📚 Full Guides

- Setup: `TEST_USER_SETUP_GUIDE.md`
- Summary: `TEST_DATA_SUMMARY.md`
- RAG Guide: `apps/bot/docs/RAG_INTEGRATION_GUIDE.md`
