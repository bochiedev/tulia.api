# Tenant Data Used for RAG and Customer Understanding

## Overview

The AI agent uses multiple data sources to understand customers and provide contextual responses. This document outlines all the data collected, stored, and used for RAG (Retrieval-Augmented Generation) and customer understanding.

---

## 1. Conversation Context Data

### ConversationContext Model
**Purpose**: Stores conversation state, memory, and key facts about the customer

**Data Stored**:

```json
{
  "conversation_id": "uuid",
  "tenant_id": "uuid",
  
  // Conversation Summary
  "conversation_summary": "Brief summary of conversation so far",
  "summary_updated_at": "2025-11-20T10:30:00Z",
  
  // Key Facts (Structured Memory)
  "key_facts": [
    {
      "fact": "Customer prefers gaming laptops",
      "confidence": 0.95,
      "extracted_at": "2025-11-20T10:25:00Z",
      "source": "message_id_123"
    },
    {
      "fact": "Budget is around 50K",
      "confidence": 0.90,
      "extracted_at": "2025-11-20T10:26:00Z",
      "source": "message_id_124"
    },
    {
      "fact": "Interested in HP or Acer brands",
      "confidence": 0.85,
      "extracted_at": "2025-11-20T10:27:00Z",
      "source": "message_id_125"
    }
  ],
  
  // Current State
  "current_intent": "BROWSE_PRODUCTS",
  "current_topic": "laptops",
  "awaiting_response": false,
  "last_question": "Which laptop do you prefer?",
  
  // Language Preference
  "language_preference": "mixed",  // en, sw, sheng, mixed
  "language_usage": {
    "en": 5,
    "sw": 3,
    "sheng": 2
  },
  
  // Context Expiration
  "context_expires_at": "2025-11-20T11:00:00Z",
  "last_activity_at": "2025-11-20T10:30:00Z",
  
  // Metadata
  "metadata": {
    "total_messages": 8,
    "bot_messages": 4,
    "customer_messages": 4,
    "handoff_count": 0,
    "low_confidence_count": 0
  }
}
```

**Key Features**:
- ✅ Conversation summary (auto-generated every 20 messages)
- ✅ Key facts extraction (customer preferences, budget, interests)
- ✅ Current intent and topic tracking
- ✅ Language preference tracking
- ✅ Context expiration (30 minutes of inactivity)

---

## 2. Customer Data

### Customer Model
**Purpose**: Stores customer profile and preferences

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // Identity
  "phone_e164": "+254712345678",
  "name": "John Doe",
  "email": "john@example.com",
  
  // Profile
  "language_preference": "sw",
  "timezone": "Africa/Nairobi",
  
  // Consent
  "consent_marketing": true,
  "consent_transactional": true,
  "consent_given_at": "2025-11-20T10:00:00Z",
  
  // Status
  "is_active": true,
  "is_blocked": false,
  "blocked_reason": null,
  
  // Metadata
  "metadata": {
    "source": "whatsapp",
    "first_contact": "2025-11-20T10:00:00Z",
    "total_conversations": 5,
    "total_orders": 2,
    "total_spent": 75000.00,
    "preferred_categories": ["electronics", "fashion"],
    "tags": ["vip", "repeat_customer"]
  },
  
  // Timestamps
  "created_at": "2025-11-20T10:00:00Z",
  "updated_at": "2025-11-20T10:30:00Z",
  "last_seen_at": "2025-11-20T10:30:00Z"
}
```

---

## 3. Conversation History

### Message Model
**Purpose**: Stores all messages in the conversation

**Data Stored**:

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  
  // Message Content
  "text": "Niaje, una laptop ngapi?",
  "direction": "inbound",  // inbound or outbound
  
  // Processing
  "processed": true,
  "processed_at": "2025-11-20T10:25:05Z",
  
  // Intent (if classified)
  "intent": "BROWSE_PRODUCTS",
  "intent_confidence": 0.92,
  "slots": {
    "product_type": "laptop",
    "query_type": "price"
  },
  
  // Language
  "detected_language": ["sheng", "sw"],
  "language_mix": "mixed",
  
  // Metadata
  "metadata": {
    "twilio_sid": "SM...",
    "media_urls": [],
    "spelling_corrections": [],
    "processing_time_ms": 1250
  },
  
  "created_at": "2025-11-20T10:25:00Z"
}
```

**What's Used**:
- Last 20 messages for context
- Language patterns for consistency
- Intent history for understanding customer journey
- Spelling corrections for better understanding

---

## 4. Customer Purchase History

### Order Model
**Purpose**: Tracks customer orders for personalization

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "customer_id": "uuid",
  
  // Order Details
  "order_number": "ORD-2025-001",
  "status": "completed",
  "total_amount": 35000.00,
  "currency": "KES",
  
  // Items
  "items": [
    {
      "product_id": "uuid",
      "product_name": "Samsung Galaxy A54",
      "quantity": 1,
      "price": 35000.00,
      "category": "electronics"
    }
  ],
  
  // Timestamps
  "ordered_at": "2025-11-15T14:30:00Z",
  "completed_at": "2025-11-16T10:00:00Z",
  
  // Metadata
  "metadata": {
    "payment_method": "mpesa",
    "delivery_method": "pickup",
    "notes": "Customer prefers Samsung products"
  }
}
```

**What's Used**:
- Purchase history for recommendations
- Preferred brands and categories
- Average order value
- Purchase frequency

---

## 5. Appointment History

### Appointment Model
**Purpose**: Tracks service bookings

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "customer_id": "uuid",
  
  // Appointment Details
  "service_id": "uuid",
  "service_name": "Haircut & Styling",
  "status": "confirmed",
  
  // Timing
  "scheduled_at": "2025-11-22T14:00:00Z",
  "duration_minutes": 60,
  
  // Metadata
  "metadata": {
    "preferred_stylist": "Jane",
    "special_requests": "Short sides, long top",
    "reminder_sent": true
  },
  
  "created_at": "2025-11-20T10:30:00Z"
}
```

**What's Used**:
- Booking history for recommendations
- Preferred services and times
- Special requests and preferences

---

## 6. RAG Document Data

### Document Model
**Purpose**: Stores uploaded documents (PDFs, TXT) for knowledge retrieval

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // File Info
  "file_name": "product_catalog_2025.pdf",
  "file_type": "pdf",
  "file_path": "documents/tenant_123/product_catalog_2025.pdf",
  "file_size": 2048576,  // bytes
  
  // Processing Status
  "status": "completed",
  "processing_progress": 100,
  "chunk_count": 45,
  "total_tokens": 12500,
  
  // Metadata
  "uploaded_by": "admin@example.com",
  "processed_at": "2025-11-20T09:00:00Z",
  "created_at": "2025-11-20T08:55:00Z"
}
```

### DocumentChunk Model
**Purpose**: Stores document chunks with embeddings for semantic search

**Data Stored**:

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "tenant_id": "uuid",
  
  // Chunk Content
  "chunk_index": 5,
  "content": "Our gaming laptops feature high-performance GPUs...",
  "token_count": 250,
  
  // Metadata
  "page_number": 3,
  "section": "Gaming Laptops",
  
  // Embedding Info
  "embedding_model": "text-embedding-3-small",
  "vector_id": "doc_123_chunk_5",
  
  // Note: Actual embedding vector stored in Pinecone
}
```

**What's Used**:
- Semantic search for relevant information
- Product specifications and details
- Business policies and FAQs
- Service descriptions

---

## 7. Catalog Data (Products & Services)

### Product Data
**Purpose**: Real-time product information

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // Product Info
  "title": "HP Pavilion Gaming Laptop",
  "description": "15.6\" FHD, Intel i5, 8GB RAM, GTX 1650",
  "price": 48000.00,
  "currency": "KES",
  
  // Inventory
  "stock_quantity": 5,
  "is_active": true,
  "is_available": true,
  
  // Categorization
  "category": "Electronics",
  "tags": ["gaming", "laptop", "hp"],
  
  // AI Analysis (if enabled)
  "ai_analysis": {
    "key_features": ["Gaming GPU", "Fast processor", "Good value"],
    "use_cases": ["Gaming", "Content creation", "General use"],
    "target_audience": ["Gamers", "Students", "Professionals"],
    "sentiment_score": 0.85
  },
  
  // Metadata
  "metadata": {
    "brand": "HP",
    "model": "Pavilion Gaming 15",
    "warranty": "1 year",
    "specifications": {
      "processor": "Intel Core i5-11300H",
      "ram": "8GB DDR4",
      "storage": "512GB SSD",
      "gpu": "NVIDIA GTX 1650"
    }
  }
}
```

### Service Data
**Purpose**: Service offerings and availability

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // Service Info
  "title": "Premium Haircut & Styling",
  "description": "Professional haircut with styling",
  "price": 1000.00,
  "duration_minutes": 60,
  
  // Availability
  "is_active": true,
  "availability_windows": [
    {
      "day_of_week": 1,  // Monday
      "start_time": "09:00",
      "end_time": "18:00",
      "capacity": 4
    }
  ],
  
  // Metadata
  "metadata": {
    "category": "Hair Services",
    "stylist": "Jane Doe",
    "requirements": "None",
    "cancellation_policy": "24 hours notice"
  }
}
```

---

## 8. Agent Interaction Logs

### AgentInteraction Model
**Purpose**: Tracks every AI agent interaction for analytics

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "conversation_id": "uuid",
  "message_id": "uuid",
  
  // Model Info
  "model_used": "gpt-4o",
  "provider": "openai",
  
  // Performance
  "input_tokens": 1250,
  "output_tokens": 180,
  "total_tokens": 1430,
  "estimated_cost": 0.02145,
  "processing_time_ms": 1850,
  
  // Quality
  "confidence_score": 0.92,
  "message_type": "product_inquiry",
  
  // Handoff
  "handoff_triggered": false,
  "handoff_reason": null,
  
  // Context
  "context_size_tokens": 1100,
  "context_truncated": false,
  
  // RAG Usage
  "rag_sources_used": ["database", "documents"],
  "rag_results_count": 5,
  
  // Detected Intents
  "detected_intents": ["BROWSE_PRODUCTS", "PRICE_CHECK"],
  
  // Metadata
  "metadata": {
    "language_detected": ["sheng", "sw"],
    "spelling_corrections": 2,
    "suggestions_provided": 3,
    "rich_message_used": false
  },
  
  "created_at": "2025-11-20T10:25:05Z"
}
```

---

## 9. Knowledge Base Entries

### KnowledgeEntry Model
**Purpose**: Stores FAQs and business knowledge

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // Content
  "question": "What is your return policy?",
  "answer": "We accept returns within 7 days of purchase...",
  "category": "Policies",
  
  // Search
  "keywords": ["return", "refund", "policy", "exchange"],
  "embedding_model": "text-embedding-3-small",
  "vector_id": "kb_entry_123",
  
  // Usage
  "view_count": 45,
  "helpful_count": 38,
  "not_helpful_count": 2,
  
  // Status
  "is_active": true,
  "priority": 5,
  
  "created_at": "2025-11-01T10:00:00Z",
  "updated_at": "2025-11-15T14:30:00Z"
}
```

---

## 10. Internet Search Cache

### InternetSearchCache Model
**Purpose**: Caches internet search results to reduce API calls

**Data Stored**:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // Query
  "query": "HP Pavilion Gaming laptop specifications",
  "query_hash": "sha256_hash_of_query",
  
  // Results
  "results": [
    {
      "title": "HP Pavilion Gaming 15 Specs",
      "url": "https://example.com/specs",
      "snippet": "Intel Core i5, 8GB RAM, GTX 1650...",
      "relevance_score": 0.95
    }
  ],
  "result_count": 5,
  
  // Cache Management
  "expires_at": "2025-11-21T10:00:00Z",
  "hit_count": 12,
  
  "created_at": "2025-11-20T10:00:00Z"
}
```

---

## How Data is Used

### 1. Context Building Process

```
Customer Message: "Niaje, una laptop ngapi?"
                    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Load Conversation Context                      │
│ - Last 20 messages                                      │
│ - Key facts (budget, preferences)                       │
│ - Language preference (mixed: sheng + sw)               │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Load Customer History                          │
│ - Previous orders (Samsung A54 - 35K)                   │
│ - Preferred categories (electronics)                    │
│ - Total spent (75K)                                     │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 3: RAG Retrieval                                  │
│ - Documents: Product catalog chunks                     │
│ - Database: Laptop products (5 results)                 │
│ - Internet: Laptop specs (if needed)                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Build Complete Context                         │
│ - Conversation: "Customer asking about laptop prices"   │
│ - History: "Previously bought Samsung phone"            │
│ - Catalog: "5 laptops available: 25K-150K"             │
│ - Knowledge: "Gaming laptops section"                   │
│ - Language: "Respond in Sheng/Swahili mix"             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 5: Generate Response                              │
│ Bot: "Mambo! Poa. Laptops from 25K to 150K.           │
│       Unataka ya gaming ama office work?"               │
└─────────────────────────────────────────────────────────┘
```

### 2. Data Priority

**High Priority** (Always included):
1. Current message
2. Last 5 messages
3. Key facts from context
4. Language preference

**Medium Priority** (Included if relevant):
1. Customer purchase history
2. Catalog matches (products/services)
3. Knowledge base entries
4. Document chunks

**Low Priority** (Included if space allows):
1. Full conversation history (20 messages)
2. Internet search results
3. Appointment history
4. Order details

### 3. Context Window Management

```
Total Context Window: 128K tokens (GPT-4o)

Allocation:
- System Prompt: ~1K tokens
- Conversation History: ~5K tokens
- Customer Context: ~2K tokens
- RAG Results: ~10K tokens
- Current Message: ~0.5K tokens
- Response Space: ~2K tokens
-----------------------------------
Total Used: ~20K tokens
Remaining: ~108K tokens (for complex queries)
```

---

## Data Privacy & Security

### Tenant Isolation
✅ All data is scoped by `tenant_id`  
✅ No cross-tenant data leakage  
✅ Separate vector store namespaces per tenant  

### Data Encryption
✅ PII fields encrypted at rest  
✅ Phone numbers encrypted  
✅ Email addresses encrypted  

### Data Retention
✅ Conversation context expires after 30 minutes of inactivity  
✅ Key facts preserved for returning customers  
✅ Full message history retained for analytics  
✅ RAG cache expires after 24 hours  

### RBAC Enforcement
✅ All API endpoints require `analytics:view` scope  
✅ Tenant users can only access their own data  
✅ No superuser bypass in production  

---

## Viewing the Data

### API Endpoints

**1. Get Conversation Context**
```bash
GET /v1/bot/conversations/{conversation_id}/context
Required scope: analytics:view

Response:
{
  "conversation_summary": "Customer looking for gaming laptop...",
  "key_facts": [...],
  "language_preference": "mixed",
  "current_intent": "BROWSE_PRODUCTS"
}
```

**2. Get Agent Interactions**
```bash
GET /v1/bot/interactions?conversation_id={id}
Required scope: analytics:view

Response:
{
  "results": [
    {
      "model_used": "gpt-4o",
      "confidence_score": 0.92,
      "processing_time_ms": 1850,
      "rag_sources_used": ["database", "documents"]
    }
  ]
}
```

**3. Get Customer History**
```bash
GET /v1/customers/{customer_id}/history
Required scope: analytics:view

Response:
{
  "orders": [...],
  "appointments": [...],
  "total_spent": 75000.00,
  "preferred_categories": ["electronics"]
}
```

---

## Summary

### Data Sources (10 total)
1. ✅ Conversation Context - Memory and state
2. ✅ Customer Profile - Identity and preferences
3. ✅ Message History - Last 20 messages
4. ✅ Purchase History - Orders and spending
5. ✅ Appointment History - Service bookings
6. ✅ RAG Documents - Uploaded PDFs/TXT
7. ✅ Catalog Data - Products and services
8. ✅ Agent Interactions - Performance logs
9. ✅ Knowledge Base - FAQs and policies
10. ✅ Internet Cache - Search results

### Key Features
- ✅ Multi-source RAG retrieval
- ✅ Intelligent context prioritization
- ✅ Language preference tracking
- ✅ Key facts extraction
- ✅ Purchase history analysis
- ✅ Semantic search across documents
- ✅ Real-time catalog integration
- ✅ Internet enrichment (optional)

### Privacy & Security
- ✅ Tenant isolation enforced
- ✅ PII encryption at rest
- ✅ Context expiration (30 min)
- ✅ RBAC on all endpoints
- ✅ Audit logging enabled

**All data is structured, queryable, and can be displayed via API endpoints with proper RBAC enforcement!** 🔒📊
