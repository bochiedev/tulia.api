# Test User Setup Guide for RAG Testing

## Quick Setup

### 1. Create Test User and Data

Run the seed command to create the test user with phone +254722241161:

```bash
python manage.py seed_test_user --phone=+254722241161 --tenant-slug=starter-store
```

This will create:
- ✅ Customer with phone +254722241161
- ✅ Active conversation with sample messages
- ✅ Customer preferences (all consents enabled)
- ✅ Agent configuration with RAG enabled
- ✅ Sample products (5 items)
- ✅ Sample services (3 services with availability)

### 2. Upload FAQ Document for RAG Testing

Upload the sample FAQ document to enable document retrieval:

```bash
# Using curl
curl -X POST http://localhost:8000/v1/documents/upload \
  -H "X-TENANT-ID: <TENANT_ID>" \
  -H "X-TENANT-API-KEY: <API_KEY>" \
  -F "file=@test_data/sample_faq.txt"
```

Or use the API endpoint from your application.

### 3. Verify Setup

Check that everything is created:

```bash
python manage.py shell
```

```python
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation
from apps.bot.models import AgentConfiguration, Document

# Get tenant
tenant = Tenant.objects.get(slug='starter-store')
print(f"Tenant: {tenant.name}")

# Get customer
customer = Customer.objects.get(tenant=tenant, phone_e164='+254722241161')
print(f"Customer: {customer.name} ({customer.phone_e164})")

# Get conversation
conversation = Conversation.objects.get(tenant=tenant, customer=customer)
print(f"Conversation: {conversation.id}")
print(f"Messages: {conversation.messages.count()}")

# Check agent config
config = AgentConfiguration.objects.get(tenant=tenant)
print(f"\nRAG Configuration:")
print(f"  Document Retrieval: {config.enable_document_retrieval}")
print(f"  Database Retrieval: {config.enable_database_retrieval}")
print(f"  Internet Enrichment: {config.enable_internet_enrichment}")
print(f"  Source Attribution: {config.enable_source_attribution}")

# Check documents
docs = Document.objects.filter(tenant=tenant)
print(f"\nDocuments: {docs.count()}")
for doc in docs:
    print(f"  - {doc.file_name} ({doc.status})")
```

## Test Scenarios

### Scenario 1: Document Retrieval Test

**Query:** "What is your return policy?"

**Expected Behavior:**
1. RAG retrieves information from uploaded FAQ document
2. Response includes: "30-day return policy"
3. Source attribution: "[Source: sample_faq.txt]"

**Test:**
```bash
# Send message via WhatsApp or API
curl -X POST http://localhost:8000/v1/webhooks/twilio/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+254722241161" \
  -d "To=whatsapp:+<YOUR_TWILIO_NUMBER>" \
  -d "Body=What is your return policy?"
```

### Scenario 2: Database Retrieval Test

**Query:** "Tell me about the iPhone 15 Pro"

**Expected Behavior:**
1. RAG retrieves product from database
2. Response includes: price, description, availability
3. Source attribution: "[Source: Our Catalog]"

**Test:**
```bash
curl -X POST http://localhost:8000/v1/webhooks/twilio/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+254722241161" \
  -d "To=whatsapp:+<YOUR_TWILIO_NUMBER>" \
  -d "Body=Tell me about the iPhone 15 Pro"
```

### Scenario 3: Service Booking Test

**Query:** "Can I book a haircut appointment?"

**Expected Behavior:**
1. RAG retrieves service information from database
2. Response includes: service details, pricing, availability
3. Offers to book appointment

**Test:**
```bash
curl -X POST http://localhost:8000/v1/webhooks/twilio/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+254722241161" \
  -d "To=whatsapp:+<YOUR_TWILIO_NUMBER>" \
  -d "Body=Can I book a haircut appointment?"
```

### Scenario 4: Multi-Source Retrieval Test

**Query:** "Do you ship internationally?"

**Expected Behavior:**
1. RAG retrieves from FAQ document (primary source)
2. May also retrieve from database if relevant products found
3. Response includes shipping information
4. Source attribution from document

**Test:**
```bash
curl -X POST http://localhost:8000/v1/webhooks/twilio/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+254722241161" \
  -d "To=whatsapp:+<YOUR_TWILIO_NUMBER>" \
  -d "Body=Do you ship internationally?"
```

### Scenario 5: Internet Enrichment Test

**Query:** "Tell me more about wireless headphones features"

**Expected Behavior:**
1. RAG retrieves product from database
2. May enrich with internet search for detailed specs
3. Response combines catalog info + enriched details
4. Multiple source attributions

**Test:**
```bash
curl -X POST http://localhost:8000/v1/webhooks/twilio/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+254722241161" \
  -d "To=whatsapp:+<YOUR_TWILIO_NUMBER>" \
  -d "Body=Tell me more about wireless headphones features"
```

## Verification Checklist

After running tests, verify:

- [ ] Customer receives responses
- [ ] Responses include relevant information
- [ ] Source attribution is present (if enabled)
- [ ] RAG context is logged in AgentInteraction
- [ ] No errors in logs
- [ ] Response time is acceptable (<2 seconds)

## Troubleshooting

### Issue: No RAG context retrieved

**Check:**
1. Is RAG enabled in AgentConfiguration?
   ```python
   config = AgentConfiguration.objects.get(tenant=tenant)
   print(config.enable_document_retrieval)
   ```

2. Are documents processed?
   ```python
   docs = Document.objects.filter(tenant=tenant, status='completed')
   print(docs.count())
   ```

3. Check logs:
   ```bash
   tail -f logs/app.log | grep "RAG"
   ```

### Issue: No source attribution

**Check:**
1. Is attribution enabled?
   ```python
   config = AgentConfiguration.objects.get(tenant=tenant)
   print(config.enable_source_attribution)
   ```

2. Was RAG context actually retrieved?
   ```python
   from apps.bot.models import AgentInteraction
   interaction = AgentInteraction.objects.filter(
       conversation__customer__phone_e164='+254722241161'
   ).latest('created_at')
   print(interaction.metadata.get('rag_context'))
   ```

### Issue: Document not processed

**Check document status:**
```python
from apps.bot.models import Document
docs = Document.objects.filter(tenant=tenant)
for doc in docs:
    print(f"{doc.file_name}: {doc.status}")
```

**Manually trigger processing:**
```python
from apps.bot.tasks import process_document
doc = Document.objects.filter(tenant=tenant, status='pending').first()
if doc:
    process_document.delay(doc.id)
```

## Test Data Summary

### Customer Details
- **Phone:** +254722241161
- **Name:** Test Customer
- **Timezone:** Africa/Nairobi
- **Tags:** test, rag-testing

### Products Created
1. iPhone 15 Pro - $999.00
2. Wireless Headphones - $79.99
3. Smart Watch - $299.99
4. Coffee Maker - $79.99
5. Yoga Mat - $29.99

### Services Created
1. Haircut - $25.00 (30 min)
2. Massage - $60.00 (60 min)
3. Consultation - $50.00 (45 min)

### Sample Messages
1. "Hi, I need help with your products"
2. "Hello! I'd be happy to help you. What would you like to know?"
3. "What is your return policy?"

### RAG Configuration
- Document Retrieval: ✅ Enabled
- Database Retrieval: ✅ Enabled
- Internet Enrichment: ✅ Enabled
- Source Attribution: ✅ Enabled
- Max Document Results: 3
- Max Database Results: 5
- Max Internet Results: 2

## Additional Test Queries

Try these queries to test different RAG scenarios:

1. **Policy Questions:**
   - "What is your return policy?"
   - "Do you ship internationally?"
   - "What payment methods do you accept?"
   - "Do you offer warranties?"

2. **Product Questions:**
   - "Tell me about the iPhone 15 Pro"
   - "Do you have wireless headphones?"
   - "What's the price of the smart watch?"
   - "Is the yoga mat in stock?"

3. **Service Questions:**
   - "Can I book a haircut?"
   - "What services do you offer?"
   - "How much is a massage?"
   - "What are your available times?"

4. **General Questions:**
   - "How can I contact customer service?"
   - "Do you have a physical store?"
   - "Do you offer student discounts?"
   - "How do I track my order?"

## Expected Response Format

With RAG and attribution enabled, responses should look like:

```
According to our FAQ, we offer a 30-day return policy on all items. 
You can return any product within 30 days of purchase for a full 
refund, as long as it's in its original condition with all tags and 
packaging intact. [Source: sample_faq.txt]

Would you like to know more about our return process?
```

## Monitoring RAG Performance

Check RAG performance in the database:

```python
from apps.bot.models import AgentInteraction
from django.utils import timezone
from datetime import timedelta

# Get recent interactions with RAG
recent = AgentInteraction.objects.filter(
    conversation__customer__phone_e164='+254722241161',
    created_at__gte=timezone.now() - timedelta(hours=1)
)

for interaction in recent:
    rag_context = interaction.metadata.get('rag_context')
    if rag_context:
        print(f"\nInteraction: {interaction.id}")
        print(f"Query: {interaction.customer_message}")
        print(f"Document Results: {len(rag_context.get('document_results', []))}")
        print(f"Database Results: {len(rag_context.get('database_results', []))}")
        print(f"Internet Results: {len(rag_context.get('internet_results', []))}")
        print(f"Retrieval Time: {rag_context.get('retrieval_time_ms')}ms")
```

## Next Steps

After verifying the test user works:

1. Test with real WhatsApp messages
2. Upload more documents (PDFs, text files)
3. Add more products and services
4. Test different query types
5. Monitor RAG analytics
6. Adjust configuration based on results

## Support

If you encounter issues:
1. Check logs: `tail -f logs/app.log`
2. Verify database: Use Django shell
3. Test API endpoints: Use curl or Postman
4. Review documentation: `apps/bot/docs/RAG_INTEGRATION_GUIDE.md`
