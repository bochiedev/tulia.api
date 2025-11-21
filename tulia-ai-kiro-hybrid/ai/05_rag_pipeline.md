# 05 — RAG Pipeline (Tenant Docs + Catalog)

Tulia AI uses RAG (Retrieval-Augmented Generation) only for **grounded**
answers about:

- Return policies
- Delivery rules
- Detailed service descriptions
- Internal business docs (if provided)

## 5.1 Storage

- Vector DB: Pinecone
- Index: shared or per-region
- Namespace: `tenant_{uuid}`

Documents:
- `Document` records for each uploaded file
- `DocumentChunk` for each chunk (stored in DB, embedding id references Pinecone)

## 5.2 Ingestion

- Extract text from PDF/TXT/HTML
- Split into chunks (e.g., 300–500 tokens with overlap)
- Generate embeddings using `text-embedding-3-small` or similar
- Upsert into Pinecone under the tenant namespace

## 5.3 Retrieval

For intents like `ASK_RETURN_POLICY`, `GENERAL_FAQ`:

1. Formulate a query using:
   - Customer message
   - Conversation context
   - Tenant metadata (industry, location)

2. Run vector search (top_k=5–8).
3. Combine with any relevant structured data (e.g., `TenantSettings`).
4. Pass retrieved chunks + query into a **small LLM** with a strict prompt:

   - “Answer only using the provided context.”
   - “If the context is insufficient, say you are not sure.”

## 5.4 Anti-Hallucination Constraints

- If no chunks have similarity above threshold (e.g. 0.7), answer:
  - “I’m not sure about that. Naweza kukuunganishia na mtu wa team.”
- Never allow RAG to:
  - Confirm payments
  - Invent timeslots
  - Create or modify orders

## 5.5 API Sketch

```python
def answer_with_rag(tenant, question: str, context: "ConversationContext") -> str:
    # Retrieve relevant chunks
    # Call small LLM with strict prompt
    # Return safe, short answer
    ...
```
