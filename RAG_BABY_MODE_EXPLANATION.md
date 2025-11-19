# RAG Workflow Explained (Baby Mode) 🍼

## The Big Picture: What is RAG?

Imagine you're a student taking an open-book exam. Instead of memorizing everything, you can look up answers in your textbooks when you need them. That's basically what RAG does for AI!

**RAG = Retrieval-Augmented Generation**
- **Retrieval** = Looking up information
- **Augmented** = Enhanced/improved
- **Generation** = Creating responses

## The Problem RAG Solves

**Without RAG:**
```
Customer: "What is your return policy?"
AI: "I think it's 30 days... or maybe 14? I'm not sure." ❌
```

**With RAG:**
```
Customer: "What is your return policy?"
AI: [Looks up in FAQ document]
AI: "According to our FAQ, we offer a 30-day return policy..." ✅
```

## Where LangChain and Pinecone Fit

Think of building a house:
- **LangChain** = The construction tools (hammer, saw, drill)
- **Pinecone** = The storage warehouse (where you keep materials)

### LangChain = The Smart Tools 🔧

LangChain is like a Swiss Army knife for AI. It provides ready-made tools so you don't have to build everything from scratch.

**What LangChain Does in Our System:**

1. **Text Splitting (Chunking)**
   - **File:** `apps/bot/services/chunking_service.py`
   - **What it does:** Breaks big documents into bite-sized pieces
   
   ```python
   from langchain.text_splitter import RecursiveCharacterTextSplitter
   
   # LangChain's smart text splitter
   splitter = RecursiveCharacterTextSplitter(
       chunk_size=400,      # Each piece is ~400 tokens
       chunk_overlap=50,    # Pieces overlap by 50 tokens
       separators=["\n\n", "\n", ". ", " "]  # Split at paragraphs, sentences, etc.
   )
   ```
   
   **Baby Mode Analogy:**
   - You have a 100-page book
   - LangChain cuts it into 200 small cards (chunks)
   - Each card has 1-2 paragraphs
   - Cards overlap a bit so you don't lose context
   
   **Why?** AI can't read a whole book at once, but it can read small cards!

### Pinecone = The Smart Library 📚

Pinecone is like a magical library where you can find things by meaning, not just by title.

**What Pinecone Does in Our System:**

1. **Stores Vector Embeddings**
   - **File:** `apps/bot/services/vector_store.py`
   - **What it does:** Stores "meaning fingerprints" of text
   
   ```python
   from pinecone import Pinecone
   
   # Connect to Pinecone
   pc = Pinecone(api_key="your-key")
   index = pc.Index("tulia-rag")
   
   # Store a chunk with its "meaning fingerprint"
   index.upsert(vectors=[
       {
           "id": "chunk_123",
           "values": [0.1, 0.5, 0.3, ...],  # 1536 numbers = meaning fingerprint
           "metadata": {"text": "Our return policy is 30 days"}
       }
   ])
   ```
   
   **Baby Mode Analogy:**
   - Regular library: Find books by title/author
   - Pinecone library: Find books by what they mean
   - You ask: "Tell me about returns"
   - Pinecone finds: "return policy", "refund", "money back" (similar meanings!)

## The Complete RAG Workflow (Step by Step)

### Phase 1: Setup (One Time) 📥

```
┌─────────────────────────────────────────────────────────────┐
│ 1. UPLOAD DOCUMENT                                          │
│    Customer uploads "FAQ.pdf"                               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. EXTRACT TEXT                                             │
│    Read PDF → "Our return policy is 30 days..."            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CHUNK TEXT (LangChain)                                   │
│    Big document → 200 small chunks                          │
│                                                              │
│    Chunk 1: "Our return policy is 30 days..."              │
│    Chunk 2: "You can return items in original..."          │
│    Chunk 3: "Contact customer service for..."              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. CREATE EMBEDDINGS (OpenAI)                               │
│    Convert text → numbers (meaning fingerprints)            │
│                                                              │
│    "return policy" → [0.1, 0.5, 0.3, 0.8, ...]             │
│    (1536 numbers that represent the meaning)                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. STORE IN PINECONE                                        │
│    Save chunks + embeddings in vector database              │
│                                                              │
│    Pinecone now has:                                        │
│    - 200 chunks from FAQ.pdf                                │
│    - Each with its meaning fingerprint                      │
│    - Organized by tenant (no mixing!)                       │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Retrieval (Every Query) 🔍

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CUSTOMER ASKS QUESTION                                   │
│    "What is your return policy?"                            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. CREATE QUERY EMBEDDING (OpenAI)                          │
│    Convert question → numbers                               │
│                                                              │
│    "return policy" → [0.12, 0.48, 0.31, 0.79, ...]         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. SEARCH PINECONE                                          │
│    Find chunks with similar meaning fingerprints            │
│                                                              │
│    Query: [0.12, 0.48, 0.31, ...]                          │
│    ↓                                                         │
│    Pinecone compares with all stored chunks                 │
│    ↓                                                         │
│    Returns top 3 most similar:                              │
│    1. "Our return policy is 30 days..." (95% match)        │
│    2. "You can return items in original..." (87% match)    │
│    3. "Contact customer service for..." (75% match)        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ALSO SEARCH DATABASE                                     │
│    Look for products, services, orders                      │
│                                                              │
│    Found: 0 products (not relevant to returns)              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. COMBINE RESULTS                                          │
│    Merge document chunks + database results                 │
│                                                              │
│    Context for AI:                                          │
│    "From FAQ: Our return policy is 30 days..."             │
│    "From FAQ: You can return items in original..."         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. SEND TO AI (OpenAI GPT-4)                                │
│    Prompt: "Using this context, answer the question..."     │
│                                                              │
│    Context: [Retrieved information]                         │
│    Question: "What is your return policy?"                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. AI GENERATES RESPONSE                                    │
│    "According to our FAQ, we offer a 30-day return         │
│     policy on all items. [Source: FAQ.pdf]"                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. SEND TO CUSTOMER                                         │
│    Customer gets accurate answer with source!               │
└─────────────────────────────────────────────────────────────┘
```

## The Magic of Embeddings (Explained Simply)

**What are embeddings?**
Embeddings are like GPS coordinates for words and sentences.

**Example:**

```
Text: "return policy"
Embedding: [0.12, 0.48, 0.31, 0.79, 0.22, ...] (1536 numbers)

Text: "refund rules"
Embedding: [0.13, 0.47, 0.30, 0.78, 0.21, ...] (very similar numbers!)

Text: "pizza recipe"
Embedding: [0.89, 0.02, 0.65, 0.11, 0.93, ...] (very different numbers!)
```

**Why this works:**
- Similar meanings → Similar numbers
- Different meanings → Different numbers
- Pinecone can find similar numbers super fast!

## Real Code Examples

### 1. LangChain Chunking (apps/bot/services/chunking_service.py)

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Create the splitter
splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,           # Each chunk ~400 tokens
    chunk_overlap=50,         # 50 tokens overlap
    separators=["\n\n", "\n", ". ", " "]  # Split smartly
)

# Use it
text = "Our return policy is 30 days. You can return items..."
chunks = splitter.split_text(text)

# Result:
# chunks[0] = "Our return policy is 30 days. You can return items..."
# chunks[1] = "...return items in original packaging. Contact us..."
```

**What LangChain does here:**
- Tries to split at paragraph breaks first
- If chunk too big, splits at sentences
- If still too big, splits at words
- Keeps some overlap so context isn't lost

### 2. Pinecone Storage (apps/bot/services/vector_store.py)

```python
from pinecone import Pinecone

# Connect to Pinecone
pc = Pinecone(api_key="your-key")
index = pc.Index("tulia-rag")

# Store chunks
vectors = [
    {
        "id": "chunk_1",
        "values": [0.1, 0.5, 0.3, ...],  # Embedding (1536 numbers)
        "metadata": {
            "text": "Our return policy is 30 days",
            "document_id": "faq_123",
            "tenant_id": "tenant_456"
        }
    }
]

# Upload to Pinecone
index.upsert(vectors=vectors, namespace="tenant_456")
```

**What Pinecone does here:**
- Stores the embedding (meaning fingerprint)
- Stores metadata (text, document ID, tenant ID)
- Uses namespace for tenant isolation (no mixing!)

### 3. Pinecone Search (apps/bot/services/vector_store.py)

```python
# Search for similar chunks
query_embedding = [0.12, 0.48, 0.31, ...]  # From "return policy" question

results = index.query(
    vector=query_embedding,
    top_k=3,                              # Get top 3 matches
    namespace="tenant_456",               # Only this tenant's data
    include_metadata=True
)

# Results:
# [
#   {
#     "id": "chunk_1",
#     "score": 0.95,  # 95% similar!
#     "metadata": {"text": "Our return policy is 30 days..."}
#   },
#   {
#     "id": "chunk_2",
#     "score": 0.87,  # 87% similar
#     "metadata": {"text": "You can return items in original..."}
#   }
# ]
```

**What Pinecone does here:**
- Compares query embedding with all stored embeddings
- Finds the most similar ones (using cosine similarity)
- Returns top matches with scores
- Only searches within the tenant's namespace

## Why We Use Both

### LangChain = The Prep Cook 👨‍🍳
- Prepares the ingredients (chunks text)
- Uses smart techniques (recursive splitting)
- Makes everything ready for storage

### Pinecone = The Smart Fridge 🧊
- Stores everything organized
- Finds things by smell/taste (meaning), not just label
- Super fast retrieval (milliseconds!)

## The Full Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        CUSTOMER                              │
│                  "What is your return policy?"               │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI AGENT SERVICE                          │
│              (apps/bot/services/ai_agent_service.py)         │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  RAG RETRIEVER SERVICE                       │
│           (apps/bot/services/rag_retriever_service.py)       │
└────────────────────────┬─────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  DOCUMENTS   │  │   DATABASE   │  │   INTERNET   │
│              │  │              │  │              │
│ LangChain    │  │  PostgreSQL  │  │   Google     │
│ Pinecone     │  │   Queries    │  │   Search     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  CONTEXT SYNTHESIZER                         │
│           (apps/bot/services/context_synthesizer.py)         │
│                                                              │
│  Merges all results into coherent context                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      OPENAI GPT-4                            │
│                                                              │
│  Generates response using retrieved context                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  ATTRIBUTION HANDLER                         │
│           (apps/bot/services/attribution_handler.py)         │
│                                                              │
│  Adds source citations: [Source: FAQ.pdf]                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                        CUSTOMER                              │
│  "According to our FAQ, we offer a 30-day return policy..." │
│  "[Source: FAQ.pdf]"                                         │
└─────────────────────────────────────────────────────────────┘
```

## Key Files and What They Do

| File | Uses | Purpose |
|------|------|---------|
| `chunking_service.py` | **LangChain** | Splits documents into chunks |
| `vector_store.py` | **Pinecone** | Stores and searches embeddings |
| `embedding_service.py` | OpenAI | Creates meaning fingerprints |
| `document_store_service.py` | LangChain + Pinecone | Manages documents |
| `rag_retriever_service.py` | All of above | Orchestrates retrieval |

## Performance Numbers

```
Document Upload (one-time):
├─ Extract text: ~1 second
├─ Chunk with LangChain: ~0.5 seconds
├─ Create embeddings: ~2 seconds (OpenAI API)
└─ Store in Pinecone: ~0.5 seconds
   Total: ~4 seconds for 10-page PDF

Query (every time):
├─ Create query embedding: ~0.1 seconds
├─ Search Pinecone: ~0.05 seconds (super fast!)
├─ Search database: ~0.05 seconds
└─ Generate response: ~1-2 seconds
   Total: ~1.2-2.2 seconds
```

## Cost Breakdown

```
Per 1000 queries:
├─ Embeddings (OpenAI): $0.02
├─ Vector storage (Pinecone): $0.01
├─ LLM generation (OpenAI): $0.50
└─ Total: ~$0.53 per 1000 queries
```

## Why This Architecture?

1. **LangChain** = Don't reinvent the wheel
   - Text splitting is hard (sentence boundaries, context)
   - LangChain solved this already
   - Battle-tested by thousands of companies

2. **Pinecone** = Speed and scale
   - Searching millions of vectors in milliseconds
   - Handles tenant isolation with namespaces
   - Managed service (no infrastructure headaches)

3. **Together** = Best of both worlds
   - LangChain prepares data perfectly
   - Pinecone stores and retrieves lightning-fast
   - We focus on business logic, not infrastructure

## Summary (TL;DR)

**LangChain:**
- 🔧 Tool for splitting text smartly
- 📍 Used in: `chunking_service.py`
- 🎯 Purpose: Break documents into AI-friendly chunks

**Pinecone:**
- 📚 Smart library for storing meaning fingerprints
- 📍 Used in: `vector_store.py`, `document_store_service.py`
- 🎯 Purpose: Find relevant information super fast

**Together:**
1. LangChain chunks the document
2. OpenAI creates embeddings (meaning fingerprints)
3. Pinecone stores embeddings
4. Customer asks question
5. Pinecone finds relevant chunks
6. AI generates answer using chunks
7. Customer gets accurate response!

**The Magic:** Instead of AI guessing, it looks up the answer in your documents! 🎩✨
