# LangChain & Pinecone Quick Reference 🚀

## One-Sentence Summary

**LangChain** cuts documents into smart chunks, **Pinecone** stores and finds them by meaning.

## Where They're Used

| Component | File | Line | What It Does |
|-----------|------|------|--------------|
| **LangChain** | `chunking_service.py` | 7 | Splits text into chunks |
| **Pinecone** | `vector_store.py` | 10 | Stores & searches vectors |
| **Both** | `document_store_service.py` | 16-17 | Manages documents |
| **Both** | `tasks.py` | 1465+ | Document processing |

## The Workflow (3 Steps)

### 1. Setup (Upload Document)
```
Document → LangChain (chunk) → OpenAI (embed) → Pinecone (store)
```

### 2. Query (Customer Question)
```
Question → OpenAI (embed) → Pinecone (search) → Results
```

### 3. Response (AI Answer)
```
Results → OpenAI GPT-4 (generate) → Answer with sources
```

## Code Examples

### LangChain (Chunking)
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,
    chunk_overlap=50
)
chunks = splitter.split_text("Long document text...")
```

### Pinecone (Storage)
```python
from pinecone import Pinecone

pc = Pinecone(api_key="your-key")
index = pc.Index("tulia-rag")

# Store
index.upsert(vectors=[{
    "id": "chunk_1",
    "values": [0.1, 0.5, ...],  # 1536 numbers
    "metadata": {"text": "..."}
}])

# Search
results = index.query(
    vector=[0.12, 0.48, ...],
    top_k=3
)
```

## Key Concepts

### Embeddings (The Magic Numbers)
```
"return policy" → [0.12, 0.48, 0.31, ...] (1536 numbers)
"refund rules"  → [0.13, 0.47, 0.30, ...] (similar!)
"pizza recipe"  → [0.89, 0.02, 0.65, ...] (different!)
```

### Why Similar Numbers?
- Similar meanings = Similar numbers
- Pinecone finds similar numbers fast
- That's how it finds relevant chunks!

## Performance

```
Document Upload:  ~4 seconds (10-page PDF)
Query Search:     ~50ms (Pinecone)
Total Response:   ~1.2 seconds
```

## Cost (Per 1000 Queries)

```
Embeddings:  $0.02
Pinecone:    $0.01
LLM:         $0.50
Total:       $0.53
```

## Tenant Isolation

```
Pinecone Index: "tulia-rag"
├─ Namespace: "tenant_starter-store"
│  └─ 200 chunks
├─ Namespace: "tenant_growth-business"
│  └─ 300 chunks
└─ Namespace: "tenant_enterprise-corp"
   └─ 500 chunks

Each tenant only sees their own data! 🔒
```

## Why This Combo?

| Tool | Purpose | Benefit |
|------|---------|---------|
| LangChain | Smart splitting | Preserves context |
| Pinecone | Fast search | <100ms retrieval |
| Together | RAG system | Accurate answers |

## Test It

```bash
# Create test user
python manage.py seed_test_user

# Upload document (triggers LangChain + Pinecone)
# Via API: POST /v1/documents/upload

# Query (uses Pinecone search)
# Send WhatsApp: "What is your return policy?"
```

## Full Guides

- Baby Mode: `RAG_BABY_MODE_EXPLANATION.md`
- Visual: `LANGCHAIN_PINECONE_VISUAL.md`
- Integration: `apps/bot/docs/RAG_INTEGRATION_GUIDE.md`

## TL;DR

```
Customer asks → Pinecone finds relevant chunks → AI answers
                    ↑
                LangChain prepared the chunks
```

**That's it!** 🎉
