# Task 30: RAG Infrastructure - Implementation Complete

## Overview
Task 30 implements the foundational RAG (Retrieval-Augmented Generation) infrastructure for WabotIQ, enabling document-based knowledge retrieval and semantic search capabilities.

## What Was Implemented

### 1. Dependencies (Task 30.1)
**File: `requirements.txt`**
- Added LangChain ecosystem:
  - `langchain==0.3.7`
  - `langchain-openai==0.2.5`
  - `langchain-community==0.3.7`
  - `langchain-pinecone==0.2.0`
- Added Pinecone vector database:
  - `pinecone-client==5.0.1`
- Added document processing libraries:
  - `pypdf2==3.0.1` - PDF text extraction
  - `pdfplumber==0.11.4` - OCR fallback for scanned PDFs
  - `nltk==3.9.1` - Natural language processing
  - `tiktoken==0.8.0` - Token counting

### 2. Database Models (Task 30.2)
**File: `apps/bot/models_rag.py`**

Created 4 new models for RAG functionality:

#### Document Model
- Stores uploaded documents (PDF, TXT)
- Tracks processing status (pending → processing → completed/failed)
- Records file metadata (name, type, size, path)
- Tracks statistics (chunk_count, total_tokens)
- Tenant-scoped with proper indexing

#### DocumentChunk Model
- Stores document chunks with embeddings
- Links to parent document
- Tracks chunk position and metadata (page_number, section)
- Stores vector_id for vector store reference
- Unique constraint on (document, chunk_index)

#### InternetSearchCache Model
- Caches internet search results (24 hour TTL)
- Reduces API calls and costs
- Query hash for fast lookup
- Tracks hit count for analytics

#### RAGRetrievalLog Model
- Logs all RAG retrieval operations
- Tracks performance metrics (retrieval_time_ms)
- Records costs (embedding_tokens, estimated_cost)
- Supports analytics and debugging
- Multi-source tracking (document, database, internet)

**Migrations:**
- `0010_add_rag_models.py` - Creates RAG tables with indexes
- `0011_add_rag_config_fields.py` - Adds RAG config to AgentConfiguration

### 3. Embedding Service (Task 30.3)
**File: `apps/bot/services/embedding_service.py`**

Features:
- OpenAI embeddings integration (text-embedding-3-small/large)
- Single text and batch embedding support
- Redis caching (5 min TTL for queries)
- Cost tracking per embedding
- Automatic retry logic
- Tenant-specific configuration
- Max batch size: 100 texts

Key Methods:
- `embed_text()` - Generate embedding for single text
- `embed_batch()` - Batch process up to 100 texts
- `create_for_tenant()` - Factory method with tenant config

### 4. Vector Store Integration (Task 30.4)
**File: `apps/bot/services/vector_store.py`**

#### Abstract Base Class
- `VectorStore` - Interface for vector store implementations
- Methods: `upsert()`, `search()`, `delete()`
- Supports multiple backends (Pinecone implemented)

#### Pinecone Implementation
- `PineconeVectorStore` - Production-ready Pinecone integration
- Automatic index creation with serverless spec
- Tenant isolation via namespaces
- Metadata filtering support
- Similarity search with configurable top_k
- Batch operations for efficiency

Key Features:
- Namespace-based tenant isolation
- Automatic index management
- Metadata filtering
- Cosine similarity search
- Error handling and logging

### 5. Document Store Service
**File: `apps/bot/services/document_store_service.py`**

High-level service orchestrating RAG operations:

Features:
- Document upload with validation
- File type and size validation
- Tenant-specific file storage
- Semantic search across documents
- Document deletion with cleanup
- Status tracking

Key Methods:
- `upload_document()` - Upload and validate documents
- `search_documents()` - Semantic search with embeddings
- `delete_document()` - Clean deletion (DB + vector store + file)
- `get_document_status()` - Track processing progress

### 6. Configuration Updates

#### Django Settings (`config/settings.py`)
```python
# RAG Configuration
PINECONE_API_KEY = env('PINECONE_API_KEY', default=None)
PINECONE_INDEX_NAME = env('PINECONE_INDEX_NAME', default='wabotiq-rag')
PINECONE_DIMENSION = env.int('PINECONE_DIMENSION', default=1536)
PINECONE_METRIC = env('PINECONE_METRIC', default='cosine')
PINECONE_CLOUD = env('PINECONE_CLOUD', default='aws')
PINECONE_REGION = env('PINECONE_REGION', default='us-east-1')

# Document upload settings
MAX_DOCUMENT_SIZE = env.int('MAX_DOCUMENT_SIZE', default=10 * 1024 * 1024)
ALLOWED_DOCUMENT_TYPES = ['pdf', 'txt']
DOCUMENT_STORAGE_PATH = os.path.join(BASE_DIR, 'media', 'documents')

# RAG retrieval settings
RAG_CHUNK_SIZE = env.int('RAG_CHUNK_SIZE', default=400)
RAG_CHUNK_OVERLAP = env.int('RAG_CHUNK_OVERLAP', default=50)
RAG_TOP_K_RESULTS = env.int('RAG_TOP_K_RESULTS', default=5)
RAG_SEMANTIC_WEIGHT = env.float('RAG_SEMANTIC_WEIGHT', default=0.7)
RAG_KEYWORD_WEIGHT = env.float('RAG_KEYWORD_WEIGHT', default=0.3)
```

#### Environment Variables (`.env.example`)
Added RAG configuration section with:
- Pinecone API credentials
- Index configuration
- Document processing settings
- Search weights

#### AgentConfiguration Model
Added RAG-specific fields:
- `enable_document_retrieval` - Toggle document search
- `enable_database_retrieval` - Toggle DB search
- `enable_internet_enrichment` - Toggle internet search
- `enable_source_attribution` - Toggle citations
- `max_document_results` - Limit document results (1-10)
- `max_database_results` - Limit DB results (1-20)
- `max_internet_results` - Limit internet results (1-5)
- `semantic_search_weight` - Hybrid search weight (0.0-1.0)
- `keyword_search_weight` - Hybrid search weight (0.0-1.0)
- `embedding_model` - Model selection
- `agent_can_do` - Explicit capabilities
- `agent_cannot_do` - Explicit restrictions

### 7. Comprehensive Tests
**File: `apps/bot/tests/test_rag_infrastructure.py`**

Test Coverage:
- ✅ EmbeddingService: text embedding, batch embedding, cost calculation
- ✅ VectorStore: upsert, search, delete operations
- ✅ DocumentStoreService: upload, search, delete, status tracking
- ✅ Error handling: invalid file types, size limits, empty queries
- ✅ Tenant isolation verification

## Architecture Highlights

### Tenant Isolation
- **Database**: All models have tenant foreign key with indexes
- **Vector Store**: Namespace-based isolation (`tenant_{id}`)
- **File Storage**: Tenant-specific directories
- **Queries**: All operations filter by tenant_id

### Performance Optimizations
- **Caching**: Redis cache for embeddings (5 min TTL)
- **Batch Processing**: Up to 100 embeddings per API call
- **Indexes**: Optimized DB indexes for tenant_id, status, timestamps
- **Async Ready**: Services designed for Celery background processing

### Cost Management
- **Embedding Tracking**: Token usage and cost per operation
- **Search Caching**: Reduces redundant API calls
- **Model Selection**: Configurable embedding models
- **Batch Operations**: Reduces API overhead

### Security
- **Input Validation**: File type, size, content validation
- **Tenant Scoping**: All operations enforce tenant boundaries
- **Soft Deletes**: Audit trail for deleted documents
- **Metadata Filtering**: Vector store queries filtered by tenant

## Next Steps (Remaining RAG Tasks)

### Task 31: Document Management
- Document upload API endpoints
- Document processing pipeline (extraction, chunking)
- Celery tasks for async processing

### Task 32: Multi-Source Retrieval
- Hybrid search engine (semantic + keyword)
- Database store service
- Internet search service
- RAG retriever orchestrator

### Task 33: Context Synthesis & Attribution
- Context synthesizer for multi-source results
- Attribution handler for source citations

### Task 34: RAG Integration
- Integrate RAG into AI agent service
- Update prompt engineering
- Contextual retrieval

### Task 35: RAG Optimization & Analytics
- Performance optimizations
- Analytics endpoints
- Security audit

## Usage Example

```python
from apps.bot.services.document_store_service import DocumentStoreService

# Create service for tenant
service = DocumentStoreService.create_for_tenant(tenant)

# Upload document
with open('business_faq.pdf', 'rb') as f:
    document = service.upload_document(
        file=f,
        file_name='business_faq.pdf',
        uploaded_by='admin@example.com'
    )

# Search documents
results = service.search_documents(
    query='What are your business hours?',
    top_k=5
)

for result in results:
    print(f"Document: {result['document_name']}")
    print(f"Content: {result['content']}")
    print(f"Score: {result['score']}")
```

## Configuration Example

```python
# Update agent configuration
config = tenant.agent_configuration
config.enable_document_retrieval = True
config.enable_source_attribution = True
config.max_document_results = 3
config.semantic_search_weight = 0.7
config.embedding_model = 'text-embedding-3-small'
config.save()
```

## Testing

Run RAG infrastructure tests:
```bash
pytest apps/bot/tests/test_rag_infrastructure.py -v
```

## Dependencies Installation

```bash
pip install -r requirements.txt
```

## Database Migrations

```bash
python manage.py migrate bot
```

## Environment Setup

1. Get Pinecone API key from https://www.pinecone.io/
2. Add to `.env`:
```
PINECONE_API_KEY=your-api-key-here
PINECONE_INDEX_NAME=wabotiq-rag
```

## Status: ✅ COMPLETE

Task 30 (RAG Infrastructure) is fully implemented and tested. The foundation is ready for document processing, multi-source retrieval, and AI agent integration in subsequent tasks.
