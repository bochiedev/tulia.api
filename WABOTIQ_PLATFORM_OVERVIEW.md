# WabotIQ Platform - Complete Overview

**Version**: 1.0  
**Last Updated**: November 21, 2025

---

## Table of Contents

1. [What is WabotIQ?](#what-is-wabotiq)
2. [Core Features](#core-features)
3. [Technology Stack](#technology-stack)
4. [Architecture](#architecture)
5. [Multi-Tenant System](#multi-tenant-system)
6. [AI Agent System](#ai-agent-system)
7. [Integration Ecosystem](#integration-ecosystem)
8. [Security & RBAC](#security--rbac)
9. [Data Flow](#data-flow)
10. [Deployment](#deployment)

---

## What is WabotIQ?

**WabotIQ** (formerly Tulia AI) is a **multi-tenant WhatsApp commerce and services platform** that enables businesses to:

- 🛍️ **Sell products** via WhatsApp conversations
- 📅 **Book appointments** for services
- 🤖 **Automate customer service** with AI
- 💰 **Process payments** through integrated wallets
- 📊 **Track analytics** and customer insights
- 🌍 **Communicate in multiple languages** (English, Swahili, Sheng)

### The Problem It Solves

**Traditional e-commerce challenges in Africa:**
- High cart abandonment rates on websites
- Low trust in online payments
- Preference for conversational commerce
- Need for multilingual support
- Complex integration requirements

**WabotIQ Solution:**
- Customers shop via WhatsApp (familiar, trusted)
- AI agent handles inquiries 24/7
- Natural language understanding (English/Swahili/Sheng)
- Integrated payment processing
- Simple setup for businesses

---

## Core Features

### 1. Conversational Commerce 💬

**AI-Powered Shopping Assistant**
- Natural language product search
- Price inquiries and comparisons
- Stock availability checks
- Order placement via chat
- Multilingual support (English, Swahili, Sheng)

**Example Conversation:**
```
Customer: "Niaje, una laptop ngapi?"
Bot: "Mambo! Poa. Laptops from 25K to 150K. Unataka ya gaming ama office work?"

Customer: "Gaming, budget ni 50K"
Bot: "Sawa! For 50K, I recommend:
1. HP Pavilion Gaming - 48K
2. Acer Nitro 5 - 52K
Unapenda gani?"
```

### 2. Service Booking 📅

**Appointment Management**
- Service catalog with pricing
- Availability calendar
- Automated booking confirmations
- Reminder notifications
- Rescheduling and cancellations

**Use Cases:**
- Hair salons
- Spas and wellness centers
- Repair services
- Consultations
- Any appointment-based business

### 3. Product Catalog 🛍️

**Multi-Source Catalog**
- WooCommerce integration
- Shopify integration
- Manual product management
- Real-time inventory sync
- Category and tag management

**Features:**
- Product variants (size, color, etc.)
- Pricing and discounts
- Stock tracking
- Image support
- AI-powered product analysis

### 4. AI Agent 🤖

**Intelligent Customer Service**
- Intent classification
- Context-aware responses
- Multi-turn conversations
- Personality matching
- Automatic handoff to humans

**Capabilities:**
- Answer product questions
- Process orders
- Book appointments
- Handle complaints
- Provide recommendations

### 5. Payment Processing 💰

**Integrated Wallet System**
- M-Pesa integration (Kenya)
- Paystack (Africa-wide)
- Pesapal (East Africa)
- Stripe (International)
- Transaction fee management

**Features:**
- Customer payments (C2B)
- Tenant withdrawals (B2C)
- Four-eyes approval for withdrawals
- Transaction history
- Automated reconciliation

### 6. Analytics & Reporting 📊

**Comprehensive Insights**
- Message volume and response times
- Order conversion rates
- Revenue tracking
- Customer behavior analysis
- AI agent performance metrics

**Dashboards:**
- Real-time metrics
- Historical trends
- Customer segmentation
- Product performance
- Service utilization

### 7. RBAC (Role-Based Access Control) 🔐

**Granular Permissions**
- Owner, Admin, Manager roles
- Custom role creation
- Scope-based permissions
- Four-eyes approval workflows
- Audit logging

**Permission Scopes:**
- `catalog:view`, `catalog:edit`
- `orders:view`, `orders:edit`
- `finance:view`, `finance:withdraw:initiate`, `finance:withdraw:approve`
- `analytics:view`
- `users:manage`

### 8. Multi-Language Support 🌍

**Kenyan Market Focus**
- English (formal and casual)
- Swahili (standard Kenyan)
- Sheng (street slang)
- Code-switching (mixed languages)
- Personality-driven responses

---

## Technology Stack

### Backend Framework
```
Django 4.2+
├── Django REST Framework (API)
├── drf-spectacular (OpenAPI docs)
├── django-cors-headers (CORS)
└── django-ratelimit (Rate limiting)
```

### Database & Caching
```
PostgreSQL 15+
├── psycopg3 (Modern driver)
├── UUID primary keys
├── Soft delete support
└── Full-text search

Redis 7+
├── Caching (database 0)
├── Rate limiting (database 0)
├── Celery broker (database 1)
└── Celery results (database 2)
```

### Task Queue
```
Celery 5.3+
├── Background tasks
├── Scheduled jobs (Celery Beat)
├── Multiple queues:
│   ├── default (general tasks)
│   ├── integrations (external APIs)
│   ├── analytics (metrics)
│   ├── messaging (outbound messages)
│   └── bot (AI processing)
```

### AI & LLM Providers
```
OpenAI
├── GPT-4o (primary)
├── GPT-4o-mini (cost-effective)
└── text-embedding-3-small (embeddings)

Google Gemini
├── Gemini 1.5 Pro (large context)
└── Gemini 1.5 Flash (fast, cheap)

Together AI
├── Llama 3.1 (8B, 70B, 405B)
├── Mistral (7B, 8x7B, 8x22B)
├── Qwen 2.5 (7B, 72B) - Excellent for Swahili
└── DeepSeek 67B (cost-effective)

Anthropic Claude (optional)
└── Claude 3.5 Sonnet
```

### RAG (Retrieval-Augmented Generation)
```
LangChain 0.3+
├── Document processing
├── Text splitting
├── Embedding generation
└── Retrieval chains

Pinecone
├── Vector database
├── Semantic search
├── Tenant namespaces
└── 1536-dimensional embeddings

Document Processing
├── PyPDF2 (PDF extraction)
├── pdfplumber (Advanced PDF)
├── NLTK (Text processing)
└── tiktoken (Token counting)
```

### External Integrations
```
Twilio
├── WhatsApp Business API
├── SMS (optional)
└── Webhook verification

WooCommerce
├── REST API integration
├── Product sync
├── Order sync
└── Webhook support

Shopify
├── REST API integration
├── Product sync
├── Order sync
└── Webhook support

Payment Providers
├── M-Pesa (Safaricom - Kenya)
├── Paystack (Africa-wide)
├── Pesapal (East Africa)
└── Stripe (International)
```

### Security & Monitoring
```
Security
├── JWT authentication
├── API key authentication
├── Encryption (cryptography)
├── CORS protection
└── Rate limiting

Monitoring
├── Sentry (error tracking)
├── Structured logging
├── Request ID tracking
└── Performance metrics
```

### Testing
```
pytest 8.0+
├── pytest-django (Django integration)
├── pytest-cov (Coverage)
├── factory-boy (Test fixtures)
└── hypothesis (Property testing)
```

### Development Tools
```
Docker & Docker Compose
├── Development environment
├── Production deployment
└── Service orchestration

Git
├── Version control
├── Branch strategy
└── CI/CD integration
```

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CUSTOMER LAYER                          │
│  WhatsApp Users → Twilio WhatsApp API → WabotIQ Platform   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    API GATEWAY LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ REST API     │  │ Webhooks     │  │ Admin Panel  │     │
│  │ (DRF)        │  │ (Twilio)     │  │ (Django)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   MIDDLEWARE LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Tenant       │  │ RBAC         │  │ Rate         │     │
│  │ Resolution   │  │ Enforcement  │  │ Limiting     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ AI Agent     │  │ Catalog      │  │ Orders       │     │
│  │ Service      │  │ Management   │  │ Processing   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Service      │  │ Payment      │  │ Analytics    │     │
│  │ Booking      │  │ Processing   │  │ Engine       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    TASK QUEUE LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Celery       │  │ Message      │  │ Analytics    │     │
│  │ Workers      │  │ Processing   │  │ Aggregation  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Redis        │  │ Pinecone     │     │
│  │ (Primary DB) │  │ (Cache)      │  │ (Vectors)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  EXTERNAL SERVICES                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ OpenAI/      │  │ WooCommerce/ │  │ M-Pesa/      │     │
│  │ Gemini       │  │ Shopify      │  │ Paystack     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Application Structure

```
wabotiq/
├── apps/
│   ├── core/              # Base models, middleware, utilities
│   │   ├── models.py      # BaseModel (UUID, soft delete)
│   │   ├── middleware.py  # Tenant resolution, RBAC
│   │   ├── permissions.py # HasTenantScopes, @requires_scopes
│   │   └── exceptions.py  # Custom exceptions
│   │
│   ├── tenants/           # Multi-tenant management
│   │   ├── models.py      # Tenant, TenantSettings, Customer
│   │   ├── views.py       # Tenant CRUD, settings
│   │   └── middleware.py  # Tenant context injection
│   │
│   ├── rbac/              # Role-Based Access Control
│   │   ├── models.py      # Permission, Role, RolePermission
│   │   ├── services.py    # Scope resolution, four-eyes
│   │   └── seeders.py     # Default roles and permissions
│   │
│   ├── messaging/         # WhatsApp messaging
│   │   ├── models.py      # Conversation, Message
│   │   ├── views.py       # Webhook handlers
│   │   └── services.py    # Message processing
│   │
│   ├── bot/               # AI Agent
│   │   ├── models.py      # AgentInteraction, ConversationContext
│   │   ├── tasks.py       # Celery tasks for message processing
│   │   ├── services/
│   │   │   ├── ai_agent_service.py          # Main AI orchestration
│   │   │   ├── context_builder_service.py   # Context assembly
│   │   │   ├── multi_language_processor.py  # Multilingual support
│   │   │   ├── rag_retriever_service.py     # RAG retrieval
│   │   │   └── llm/
│   │   │       ├── openai_provider.py
│   │   │       ├── gemini_provider.py
│   │   │       ├── together_provider.py
│   │   │       └── failover_manager.py
│   │   └── views.py       # Agent interaction analytics
│   │
│   ├── catalog/           # Product catalog
│   │   ├── models.py      # Product, ProductVariant, Category
│   │   ├── views.py       # Product CRUD
│   │   └── services.py    # Catalog management
│   │
│   ├── services/          # Service booking
│   │   ├── models.py      # Service, ServiceVariant, Appointment
│   │   ├── views.py       # Service CRUD, booking
│   │   └── services.py    # Availability management
│   │
│   ├── orders/            # Order management
│   │   ├── models.py      # Order, OrderItem, Cart
│   │   ├── views.py       # Order CRUD
│   │   └── services.py    # Order processing
│   │
│   ├── analytics/         # Analytics and reporting
│   │   ├── models.py      # AnalyticsDaily, Metrics
│   │   ├── views.py       # Analytics endpoints
│   │   └── tasks.py       # Aggregation jobs
│   │
│   └── integrations/      # External integrations
│       ├── services/
│       │   ├── twilio_service.py      # WhatsApp messaging
│       │   ├── woo_service.py         # WooCommerce sync
│       │   ├── shopify_service.py     # Shopify sync
│       │   └── payment_service.py     # Payment processing
│       └── views.py       # Webhook handlers
│
├── config/                # Django configuration
│   ├── settings.py        # Main settings
│   ├── urls.py            # URL routing
│   ├── celery.py          # Celery configuration
│   └── wsgi.py            # WSGI application
│
├── docs/                  # Documentation
├── logs/                  # Application logs
├── scripts/               # Management scripts
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image
├── docker-compose.yml     # Development environment
└── manage.py              # Django management
```

---

## Multi-Tenant System

### Tenant Isolation

**Every query MUST be tenant-scoped:**

```python
# ✅ CORRECT
products = Product.objects.filter(tenant=tenant, is_active=True)

# ❌ WRONG - Cross-tenant data leakage!
products = Product.objects.filter(is_active=True)
```

### Tenant Resolution

**Middleware automatically resolves tenant:**

```python
# Request headers
X-TENANT-ID: uuid
X-TENANT-API-KEY: key

# Middleware sets
request.tenant = Tenant object
request.membership = TenantUser object
request.scopes = Set of permission scopes
```

### Tenant Data Isolation

**Database Level:**
- All models have `tenant` foreign key
- Indexes include `tenant_id`
- Queries filtered by tenant

**Vector Store Level:**
- Separate Pinecone namespaces per tenant
- Format: `tenant_{tenant_id}`

**Cache Level:**
- Cache keys prefixed with tenant ID
- Format: `tenant:{tenant_id}:key`

---

## AI Agent System

### Architecture

```
Customer Message
      ↓
┌─────────────────────────────────────┐
│ 1. Message Deduplication            │
│    - Check for duplicate processing │
│    - Acquire distributed lock       │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│ 2. Language Detection               │
│    - Detect English/Swahili/Sheng  │
│    - Determine customer energy      │
│    - Track language preference      │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│ 3. Context Building                 │
│    - Load conversation history      │
│    - Load customer profile          │
│    - Load purchase history          │
│    - Load key facts                 │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│ 4. RAG Retrieval                    │
│    - Documents (PDFs, TXT)          │
│    - Database (products, services)  │
│    - Internet (enrichment)          │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│ 5. LLM Generation                   │
│    - Select model (GPT-4o/Gemini)  │
│    - Generate response              │
│    - Failover if needed             │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│ 6. Response Formatting              │
│    - Match customer language        │
│    - Add personality                │
│    - Create rich message (optional) │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│ 7. Send via Twilio                  │
│    - WhatsApp message               │
│    - Track interaction              │
│    - Update context                 │
└─────────────────────────────────────┘
```

### LLM Provider Failover

**7-Tier Fallback System:**

```
1. OpenAI GPT-4o              → Primary (best quality)
2. Gemini 1.5 Pro             → Google fallback
3. Together Qwen 2.5 72B      → Multilingual powerhouse
4. OpenAI GPT-4o-mini         → Cheaper OpenAI
5. Gemini 1.5 Flash           → Cheaper Gemini
6. Together Llama 3.1 70B     → Strong open-source
7. Together Qwen 2.5 7B       → Final fallback ($0.30/1M)
```

**Automatic Failover:**
- Provider health tracking
- Retry with exponential backoff
- Seamless customer experience

---

## Integration Ecosystem

### Twilio WhatsApp

**Inbound Messages:**
```
Customer sends WhatsApp message
      ↓
Twilio receives message
      ↓
Twilio webhook → WabotIQ
      ↓
Signature verification
      ↓
Message processing (Celery)
      ↓
AI agent generates response
      ↓
Send via Twilio API
```

**Outbound Messages:**
```
System triggers message
      ↓
Celery task queued
      ↓
Twilio API call
      ↓
Message sent to customer
      ↓
Delivery status tracked
```

### WooCommerce

**Product Sync:**
```
WooCommerce webhook → WabotIQ
      ↓
Product created/updated
      ↓
Sync to local database
      ↓
Generate embeddings (optional)
      ↓
Update vector store
```

**Order Sync:**
```
Customer places order via WhatsApp
      ↓
Create order in WabotIQ
      ↓
Sync to WooCommerce
      ↓
Update inventory
      ↓
Send confirmation
```

### Shopify

**Similar to WooCommerce:**
- Product sync via webhooks
- Order creation and sync
- Inventory management
- Real-time updates

### Payment Providers

**M-Pesa (Kenya):**
- STK Push for customer payments
- B2C for tenant withdrawals
- Callback handling
- Transaction reconciliation

**Paystack (Africa):**
- Card payments
- Mobile money
- Bank transfers
- Webhook notifications

**Pesapal (East Africa):**
- Card payments
- Mobile money (M-Pesa, Airtel)
- Bank transfers
- IPN callbacks

**Stripe (International):**
- Card payments
- Alternative payment methods
- Subscription billing
- Webhook events

---

## Security & RBAC

### Authentication

**JWT Tokens:**
```python
# Login
POST /v1/auth/login
{
  "email": "user@example.com",
  "password": "password"
}

# Response
{
  "token": "eyJ...",
  "user": {...}
}

# Use token
Authorization: Bearer eyJ...
X-TENANT-ID: uuid
```

**API Keys:**
```python
# Tenant API key
X-TENANT-ID: uuid
X-TENANT-API-KEY: key
```

### RBAC (Role-Based Access Control)

**Permission Scopes:**
```
catalog:view, catalog:edit
orders:view, orders:edit
services:view, services:edit
appointments:view, appointments:edit
finance:view, finance:withdraw:initiate, finance:withdraw:approve
analytics:view
integrations:manage
users:manage
```

**Default Roles:**
```
Owner → ALL permissions
Admin → ALL except finance:withdraw:approve
Finance Admin → analytics:view, finance:*, orders:view
Catalog Manager → analytics:view, catalog:*, services:*
Support Lead → conversations:view, handoff:perform, orders:view
Analyst → analytics:view, catalog:view, services:view, orders:view
```

**Enforcement:**
```python
# View level
class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view'}

# Decorator
@requires_scopes('catalog:edit')
def update_product(request):
    pass
```

### Data Encryption

**Encrypted Fields:**
- Twilio credentials
- API keys
- Payment credentials
- Customer PII (phone, email)

**Encryption Method:**
- AES-256-GCM
- Fernet (symmetric encryption)
- Key rotation support

---

## Data Flow

### Message Processing Flow

```
1. Customer sends: "Niaje, una laptop ngapi?"
      ↓
2. Twilio webhook → WabotIQ
      ↓
3. Create Message record
      ↓
4. Queue Celery task: process_inbound_message
      ↓
5. AI Agent processes:
   - Detect language: [sheng, sw]
   - Build context: conversation history, customer data
   - RAG retrieval: laptop products
   - Generate response: "Mambo! Poa. Laptops from 25K..."
      ↓
6. Send via Twilio
      ↓
7. Track interaction for analytics
```

### Order Processing Flow

```
1. Customer: "Niongeze number 2 kwa cart"
      ↓
2. AI Agent:
   - Resolve reference: "number 2" = Samsung A54
   - Add to cart
   - Calculate total
      ↓
3. Customer: "Checkout"
      ↓
4. AI Agent:
   - Create order
   - Generate payment link
   - Send M-Pesa STK push
      ↓
5. Customer pays
      ↓
6. M-Pesa callback → WabotIQ
      ↓
7. Update order status
      ↓
8. Sync to WooCommerce/Shopify
      ↓
9. Send confirmation
```

---

## Deployment

### Development

```bash
# Clone repository
git clone <repo-url>
cd wabotiq

# Setup environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env

# Database
python manage.py migrate

# Run services
python manage.py runserver  # Django
celery -A config worker -l info  # Celery worker
celery -A config beat -l info  # Celery beat
```

### Docker

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Production Checklist

✅ Set `DEBUG=False`  
✅ Configure `SECRET_KEY` (50+ chars)  
✅ Set `ALLOWED_HOSTS`  
✅ Configure PostgreSQL  
✅ Configure Redis  
✅ Set all API keys (OpenAI, Gemini, Together AI, Twilio)  
✅ Configure Sentry DSN  
✅ Set up SSL/TLS  
✅ Configure CORS  
✅ Set up backups  
✅ Configure monitoring  

---

## Summary

### What WabotIQ Does

**For Businesses:**
- 🛍️ Sell products via WhatsApp
- 📅 Book appointments
- 🤖 Automate customer service
- 💰 Process payments
- 📊 Track analytics

**For Customers:**
- 💬 Shop via WhatsApp (familiar, easy)
- 🌍 Communicate in their language
- 🤖 Get instant responses 24/7
- 💳 Pay securely
- 📦 Track orders

### Technology Highlights

**Backend:** Django 4.2+ with DRF  
**Database:** PostgreSQL 15+ with Redis caching  
**AI:** OpenAI, Gemini, Together AI with 7-tier failover  
**RAG:** LangChain + Pinecone for semantic search  
**Messaging:** Twilio WhatsApp API  
**Payments:** M-Pesa, Paystack, Pesapal, Stripe  
**Queue:** Celery with Redis broker  
**Monitoring:** Sentry error tracking  

### Key Differentiators

✅ **Multi-tenant** - Strict isolation, scalable  
✅ **Multilingual** - English, Swahili, Sheng with personality  
✅ **AI-powered** - 7-tier LLM failover, RAG-enhanced  
✅ **Conversational** - Natural shopping experience  
✅ **Integrated** - WooCommerce, Shopify, multiple payment providers  
✅ **Secure** - RBAC, encryption, audit logging  
✅ **Production-ready** - Tested, documented, deployed  

**WabotIQ enables businesses to sell and serve customers via WhatsApp with AI automation, multilingual support, and integrated payments!** 🚀🇰🇪
