# RAG Integration Guide

## Overview

The AI Agent now supports Retrieval-Augmented Generation (RAG), allowing it to retrieve and use information from multiple sources to provide more accurate and contextual responses.

## Features

### 1. Document Retrieval
- Upload business documents (PDFs, text files)
- Automatic text extraction and chunking
- Semantic search across documents
- Source attribution with document names

### 2. Database Retrieval
- Real-time catalog queries (products, services)
- Order history and customer data
- Appointment availability
- Always up-to-date information

### 3. Internet Enrichment
- Product information enrichment
- Brand and model details
- Specifications and features
- Cached for performance

### 4. Source Attribution
- Automatic citation of sources
- Inline or endnote citation styles
- Configurable per tenant
- Transparent information sourcing

## Configuration

### Enable RAG for a Tenant

```python
from apps.bot.models import AgentConfiguration

# Get or create agent configuration
agent_config = AgentConfiguration.objects.get(tenant=tenant)

# Enable RAG sources
agent_config.enable_document_retrieval = True
agent_config.enable_database_retrieval = True
agent_config.enable_internet_enrichment = True
agent_config.enable_source_attribution = True

# Configure retrieval limits
agent_config.max_document_results = 3
agent_config.max_database_results = 5
agent_config.max_internet_results = 2

# Configure search weights
agent_config.semantic_search_weight = 0.7
agent_config.keyword_search_weight = 0.3

# Set embedding model
agent_config.embedding_model = 'text-embedding-3-small'

# Define agent capabilities
agent_config.agent_can_do = """
- Answer questions about products and services
- Help with orders and bookings
- Provide information from our knowledge base
- Search our catalog in real-time
- Book appointments and check availability
"""

agent_config.agent_cannot_do = """
- Process payments directly
- Access external systems without integration
- Provide medical or legal advice
- Make changes to orders without confirmation
"""

agent_config.save()
```

### Upload Documents

```python
from apps.bot.models import Document

# Upload a document
document = Document.objects.create(
    tenant=tenant,
    file=uploaded_file,
    file_name='FAQ.pdf',
    file_type='pdf',
    status='pending'
)

# Process document (triggers Celery task)
from apps.bot.tasks import process_document
process_document.delay(document.id)
```

## Usage Examples

### Example 1: Customer Asks About Return Policy

**Customer:** "What is your return policy?"

**Without RAG:**
"I can help you with that. Let me check our policies..."

**With RAG (Document Retrieval):**
"According to our FAQ, we offer a 30-day return policy on all items. You can return any product within 30 days of purchase for a full refund, as long as it's in its original condition. [Source: FAQ.pdf]"

### Example 2: Product Inquiry

**Customer:** "Tell me about the iPhone 15 Pro"

**Without RAG:**
"The iPhone 15 Pro is available in our store. Would you like to know more?"

**With RAG (Database + Internet):**
"The iPhone 15 Pro is available in our catalog for $999. It features:
- A17 Pro chip with 6-core CPU
- 48MP main camera with 5x telephoto
- Titanium design
- USB-C connectivity

We currently have it in stock in Space Black and Natural Titanium. [Sources: Our Catalog, Apple.com]"

### Example 3: Service Booking

**Customer:** "Can I book a haircut for tomorrow?"

**Without RAG:**
"Let me check our availability..."

**With RAG (Database Retrieval):**
"Yes! We have availability for haircuts tomorrow. Available slots:
- 10:00 AM
- 2:00 PM
- 4:30 PM

Our haircut service costs $25 and takes approximately 30 minutes. Would you like to book one of these slots? [Source: Our Services]"

## How It Works

### 1. Retrieval Flow

```
Customer Message
    ↓
Context Building
    ↓
RAG Enabled? → No → Skip RAG
    ↓ Yes
Parallel Retrieval:
    ├─ Document Search (semantic + keyword)
    ├─ Database Query (products, services, orders)
    └─ Internet Search (if needed)
    ↓
Context Synthesis
    ├─ Merge results
    ├─ Resolve conflicts
    └─ Prioritize sources
    ↓
Add to Prompt
    ↓
LLM Generation
    ↓
Add Attribution (if enabled)
    ↓
Response to Customer
```

### 2. Source Prioritization

When information conflicts, sources are prioritized:

1. **Business Documents** (highest priority)
   - FAQs, policies, guides uploaded by tenant
   - Most authoritative for business-specific information

2. **Database** (medium-high priority)
   - Real-time catalog data
   - Always current for pricing, availability, orders

3. **Internet** (lowest priority)
   - General product information
   - Used for enrichment only

### 3. Context Synthesis

The `ContextSynthesizer` merges information:
- Removes duplicates
- Resolves conflicts using prioritization
- Creates coherent summary
- Tracks all sources used

## API Usage

### Check RAG Status

```python
GET /v1/agent/configuration

Response:
{
    "enable_document_retrieval": true,
    "enable_database_retrieval": true,
    "enable_internet_enrichment": true,
    "enable_source_attribution": true,
    "max_document_results": 3,
    "max_database_results": 5,
    "max_internet_results": 2
}
```

### Upload Document

```python
POST /v1/documents/upload
Content-Type: multipart/form-data

file: <PDF or TXT file>

Response:
{
    "id": "uuid",
    "file_name": "FAQ.pdf",
    "status": "processing",
    "created_at": "2025-11-19T10:00:00Z"
}
```

### List Documents

```python
GET /v1/documents

Response:
{
    "count": 5,
    "results": [
        {
            "id": "uuid",
            "file_name": "FAQ.pdf",
            "status": "completed",
            "chunk_count": 42,
            "created_at": "2025-11-19T10:00:00Z"
        }
    ]
}
```

## Performance

### Retrieval Times

- **Document Search:** ~100-150ms
- **Database Query:** ~50-100ms
- **Internet Search:** ~200-300ms
- **Total (parallel):** ~300ms (target)

### Caching

- Query embeddings: 5 min TTL
- Search results: 1 min TTL
- Internet results: 24 hours TTL

### Optimization Tips

1. **Limit Results:** Use appropriate `max_*_results` values
2. **Disable Unused Sources:** Turn off sources you don't need
3. **Upload Quality Documents:** Well-structured documents retrieve better
4. **Monitor Performance:** Check RAG analytics dashboard

## Troubleshooting

### RAG Not Working

1. **Check Configuration:**
   ```python
   agent_config = AgentConfiguration.objects.get(tenant=tenant)
   print(agent_config.enable_document_retrieval)
   print(agent_config.enable_database_retrieval)
   ```

2. **Check Documents:**
   ```python
   documents = Document.objects.filter(tenant=tenant, status='completed')
   print(f"Completed documents: {documents.count()}")
   ```

3. **Check Logs:**
   ```bash
   # Look for RAG retrieval logs
   grep "RAG retrieval" logs/app.log
   ```

### No Results Retrieved

1. **Check Query:** Is the query specific enough?
2. **Check Documents:** Are documents processed and indexed?
3. **Check Embeddings:** Is the embedding service working?
4. **Check Vector Store:** Is Pinecone/vector store accessible?

### Attribution Not Showing

1. **Check Setting:**
   ```python
   agent_config.enable_source_attribution  # Should be True
   ```

2. **Check RAG Context:** Was information actually retrieved?
3. **Check Logs:** Look for attribution errors

## Best Practices

### 1. Document Management

- **Upload Quality Content:** Well-formatted PDFs work best
- **Organize by Topic:** Use clear file names
- **Update Regularly:** Keep documents current
- **Remove Outdated:** Delete old documents

### 2. Configuration

- **Start Conservative:** Begin with lower `max_*_results`
- **Monitor Performance:** Adjust based on metrics
- **Test Thoroughly:** Try various queries
- **Gather Feedback:** Ask customers about accuracy

### 3. Prompt Engineering

- **Use agent_can_do:** Be explicit about capabilities
- **Use agent_cannot_do:** Set clear boundaries
- **Update Regularly:** Refine based on interactions
- **Be Specific:** Detailed guidance works better

### 4. Monitoring

- **Track Retrieval Success:** Monitor hit rates
- **Monitor Latency:** Keep under 300ms target
- **Check Attribution:** Verify sources are cited
- **Review Conflicts:** Look for conflicting information

## Security

### Tenant Isolation

- All RAG queries are scoped to tenant
- Vector store uses tenant namespaces
- Documents are stored in tenant-specific directories
- No cross-tenant data leakage

### Input Sanitization

- Customer messages are sanitized before retrieval
- Prevents injection attacks
- Validates file uploads

### Access Control

- Document upload requires `integrations:manage` scope
- Document viewing requires proper tenant membership
- RBAC enforced on all endpoints

## Analytics

### Track RAG Usage

```python
from apps.bot.models import RAGRetrievalLog

# Get retrieval stats
logs = RAGRetrievalLog.objects.filter(
    tenant=tenant,
    created_at__gte=start_date
)

# Success rate
success_rate = logs.filter(success=True).count() / logs.count()

# Average retrieval time
avg_time = logs.aggregate(Avg('retrieval_time_ms'))

# Most retrieved documents
top_docs = logs.values('document_id').annotate(
    count=Count('id')
).order_by('-count')[:10]
```

### Monitor Performance

```python
# Check cache hit rates
from apps.bot.services.caching_service import CachingService

cache_stats = CachingService.get_stats()
print(f"Cache hit rate: {cache_stats['hit_rate']:.2%}")

# Check retrieval latency
from apps.bot.models import AgentInteraction

interactions = AgentInteraction.objects.filter(
    conversation__tenant=tenant,
    created_at__gte=start_date
)

# Get interactions with RAG
rag_interactions = interactions.filter(
    metadata__has_key='rag_context'
)

print(f"RAG usage: {rag_interactions.count() / interactions.count():.2%}")
```

## Support

For issues or questions:
1. Check logs: `logs/app.log`
2. Review analytics: RAG dashboard
3. Test configuration: Run test suite
4. Contact support: support@wabotiq.com

## References

- [RAG Architecture](./RAG_ARCHITECTURE.md)
- [Document API Guide](./DOCUMENT_API_GUIDE.md)
- [Vector Store Setup](./VECTOR_STORE_SETUP.md)
- [Performance Tuning](./PERFORMANCE_TUNING.md)
