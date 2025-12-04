# WabotIQ - AI-Powered WhatsApp Commerce Platform

> **Multi-tenant conversational commerce platform** that enables businesses to sell products and services through WhatsApp using AI-powered chatbots.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

---

## 📋 Table of Contents

- [What is WabotIQ?](#-what-is-wabotiq)
- [Key Features](#-key-features)
- [Quick Start](#-quick-start)
- [Prerequisites](#-prerequisites)
- [Installation Guide](#-installation-guide)
- [Configuration](#-configuration)
- [Demo Data Setup](#-demo-data-setup)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Testing](#-testing)
- [Documentation](#-documentation)
- [Troubleshooting](#-troubleshooting)

---

## 🤖 What is WabotIQ?

**WabotIQ** is a **multi-tenant SaaS platform** that transforms WhatsApp into a complete commerce channel. Businesses can:

- 🛍️ **Sell products** - Sync catalogs from WooCommerce/Shopify or manage natively
- 📅 **Book services** - Schedule appointments with availability management
- 💬 **Automate conversations** - AI bot handles customer inquiries 24/7
- 💳 **Process payments** - Integrated wallet with M-Pesa, Paystack, Stripe, Pesapal
- 📊 **Track analytics** - Comprehensive metrics on sales, conversations, customer behavior
- 🌍 **Multi-language** - English, Swahili, Sheng with automatic detection
- 🔐 **Enterprise RBAC** - Role-based access control with scope-based permissions

**Perfect for**: E-commerce stores, service businesses, salons, consultants, restaurants.

---

## ✨ Key Features

### 🏢 Multi-Tenant Architecture
- Strict tenant isolation with complete data separation
- Subscription tiers (Starter, Growth, Enterprise)
- Per-tenant configuration (branding, AI settings, integrations)

### 💬 Conversational Commerce
- AI-powered intent classification (OpenAI/Gemini/Together AI)
- RAG system learns from FAQs, products, conversation history
- Rich messages (product cards, buttons, lists, images)
- Multi-language support with automatic detection
- Progressive handoff to human agents

### 🛒 Product & Service Management
- Product catalog sync (WooCommerce/Shopify) or native management
- Service booking with availability windows
- Real-time inventory tracking
- Product variants (size, color, storage)

### 💳 Payment Processing
- **M-Pesa** - STK Push and B2C withdrawals (Kenya)
- **Paystack** - Cards and mobile money (Africa)
- **Pesapal** - Cards and mobile money (East Africa)
- **Stripe** - International card payments
- Wallet system with transaction tracking

### 🔐 Security & RBAC
- JWT authentication for secure API access
- Scope-based permissions (catalog:view, orders:edit, etc.)
- Four-eyes approval for sensitive operations
- Complete audit logging
- Encrypted credentials at rest

---

## 🚀 Quick Start

Get WabotIQ running in **10 minutes**:

```bash
# 1. Clone and setup
git clone <repository-url>
cd tulia.api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your settings

# 3. Database setup
python manage.py migrate
python manage.py seed_permissions
python manage.py seed_subscription_tiers

# 4. Create demo data
python manage.py seed_demo_data

# 5. Create admin
python manage.py createsuperuser

# 6. Run
python manage.py runserver
# In separate terminals:
celery -A config worker -l info
celery -A config beat -l info
```

**Access:**
- API: http://localhost:8000
- Admin: http://localhost:8000/admin
- Docs: http://localhost:8000/schema/swagger/

---

## 📦 Prerequisites

### Required Services

| Service | Version | Purpose | Installation |
|---------|---------|---------|--------------|
| **Python** | 3.12+ | Runtime | [python.org](https://www.python.org/) |
| **PostgreSQL** | 15+ | Database | [postgresql.org](https://www.postgresql.org/) |
| **Redis** | 7+ | Cache & Queue | [redis.io](https://redis.io/) |

### Required API Keys

To run WabotIQ fully, you'll need accounts with these services:

| Service | Purpose | Required? | Get API Key |
|---------|---------|-----------|-------------|
| **OpenAI** | AI intent classification | ✅ Yes | [platform.openai.com](https://platform.openai.com/) |
| **Twilio** | WhatsApp messaging | ✅ Yes | [twilio.com/console](https://www.twilio.com/console) |
| **M-Pesa** | Kenya mobile payments | ⚠️ Optional | [developer.safaricom.co.ke](https://developer.safaricom.co.ke/) |
| **Paystack** | African payments | ⚠️ Optional | [paystack.com](https://paystack.com/) |
| **Stripe** | International payments | ⚠️ Optional | [stripe.com](https://stripe.com/) |
| **Pinecone** | Vector database for RAG | ⚠️ Optional | [pinecone.io](https://www.pinecone.io/) |

**Note**: You can start with just OpenAI and Twilio. Payment providers are optional for testing.

### System Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space
- **OS**: Linux, macOS, or Windows with WSL2

---

## 📥 Installation Guide

### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip postgresql-15 redis-server
```

**macOS (with Homebrew):**
```bash
brew install python@3.12 postgresql@15 redis
brew services start postgresql
brew services start redis
```

**Windows:**
- Install Python 3.12 from [python.org](https://www.python.org/)
- Install PostgreSQL from [postgresql.org](https://www.postgresql.org/)
- Install Redis using [WSL2](https://redis.io/docs/getting-started/installation/install-redis-on-windows/) or [Memurai](https://www.memurai.com/)

### Step 2: Clone Repository

```bash
git clone <repository-url>
cd tulia.api
```

### Step 3: Create Virtual Environment

```bash
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### Step 4: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Set Up PostgreSQL Database

```bash
# Create database and user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE wabotiq;
CREATE USER wabotiq_user WITH PASSWORD 'your_secure_password';
ALTER ROLE wabotiq_user SET client_encoding TO 'utf8';
ALTER ROLE wabotiq_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE wabotiq_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE wabotiq TO wabotiq_user;
\q
```

### Step 6: Verify Redis

```bash
# Check Redis is running
redis-cli ping
# Should return: PONG
```

---

## ⚙️ Configuration

### Environment Variables

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# === DJANGO SETTINGS ===
SECRET_KEY=your-secret-key-here-generate-with-django
DEBUG=True  # Set to False in production
ALLOWED_HOSTS=localhost,127.0.0.1

# === DATABASE ===
DATABASE_URL=postgresql://wabotiq_user:your_secure_password@localhost:5432/wabotiq

# === REDIS & CELERY ===
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# === AI / LLM (Required) ===
OPENAI_API_KEY=sk-proj-your-openai-key-here
OPENAI_MODEL=gpt-4o  # or gpt-4o-mini for lower cost

# Alternative LLM providers (optional)
GEMINI_API_KEY=your-gemini-key-here
TOGETHER_API_KEY=your-together-key-here

# === TWILIO (Required for WhatsApp) ===
# Get from: https://console.twilio.com
TWILIO_ACCOUNT_SID=AC********************************
TWILIO_AUTH_TOKEN=********************************
TWILIO_WHATSAPP_NUMBER=+14155238886  # Your Twilio WhatsApp number

# === PAYMENT PROVIDERS (Optional) ===

# M-Pesa (Kenya)
MPESA_CONSUMER_KEY=your-mpesa-consumer-key
MPESA_CONSUMER_SECRET=your-mpesa-consumer-secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your-mpesa-passkey
MPESA_ENVIRONMENT=sandbox  # or production

# Paystack (Africa)
PAYSTACK_SECRET_KEY=sk_test_********************************
PAYSTACK_PUBLIC_KEY=pk_test_********************************

# Stripe (International)
STRIPE_SECRET_KEY=sk_test_********************************
STRIPE_PUBLISHABLE_KEY=pk_test_********************************
STRIPE_WEBHOOK_SECRET=whsec_********************************

# Pesapal (East Africa)
PESAPAL_CONSUMER_KEY=your-pesapal-consumer-key
PESAPAL_CONSUMER_SECRET=your-pesapal-consumer-secret
PESAPAL_IPN_ID=your-ipn-id

# === PINECONE (Optional - for RAG) ===
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=wabotiq-rag
PINECONE_ENVIRONMENT=us-east-1-aws

# === MONITORING (Optional) ===
SENTRY_DSN=your-sentry-dsn-here
```

### Minimum Configuration for Testing

To get started quickly, you only need:

```bash
SECRET_KEY=django-insecure-test-key-change-in-production
DEBUG=True
DATABASE_URL=postgresql://wabotiq_user:password@localhost:5432/wabotiq
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

---

## 🎭 Demo Data Setup

WabotIQ includes comprehensive demo data to help you test all features.

### Seed Initial System Data

```bash
# 1. Seed permissions (required for RBAC)
python manage.py seed_permissions

# 2. Seed subscription tiers (Starter, Growth, Enterprise)
python manage.py seed_subscription_tiers
```

### Create Demo Tenants with Full Data

```bash
# Creates 3 demo tenants with products, services, customers, orders
python manage.py seed_demo_data
```

This creates:
- **3 demo tenants** (one per subscription tier)
- **50 products per tenant** with variants and images
- **10 services per tenant** with availability windows
- **100 customers per tenant** with varied preferences
- **Historical messages and orders** for analytics
- **Appointments and bookings**

**Demo Tenants Created:**

| Tenant | Slug | Tier | Phone | Owner Email |
|--------|------|------|-------|-------------|
| Starter Store | starter-store | Starter | +15555551001 | owner@starter.demo |
| Growth Business | growth-business | Growth | +15555551002 | owner@growth.demo |
| Enterprise Corp | enterprise-corp | Enterprise | +15555551003 | owner@enterprise.demo |

**Default Password**: `demo123!`

### Create Individual Test Tenant

```bash
# Create a single tenant with basic setup
python manage.py seed_demo_tenant \
  --name "My Test Store" \
  --slug "my-test-store" \
  --email "admin@test.com"
```

### Seed Roles for Existing Tenant

```bash
# Seed RBAC roles for a specific tenant
python manage.py seed_tenant_roles --tenant=starter-store
```

### Create Test User

```bash
# Create a test user with specific role
python manage.py seed_test_user \
  --email "test@example.com" \
  --tenant-slug "starter-store" \
  --role "Admin"
```

---

## 🤖 Setting Up the AI Bot

The AI bot needs data to provide intelligent responses. Here's how to feed it information:

### 1. Upload FAQs for RAG System

Create a FAQ file with your business information:

```bash
# Example FAQ format (see test_data/sample_faq.txt)
cat > my_store_faq.txt << 'EOF'
RETURN POLICY
Q: What is your return policy?
A: We offer a 30-day return policy on all items...

SHIPPING INFORMATION
Q: How long does shipping take?
A: Standard shipping takes 5-7 business days...

PAYMENT METHODS
Q: What payment methods do you accept?
A: We accept M-Pesa, credit cards, and cash on delivery...
EOF
```

Upload FAQs via API:

```bash
# Get JWT token first
TOKEN=$(curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@starter.demo","password":"demo123!"}' \
  | jq -r '.token')

# Upload FAQ document
curl -X POST http://localhost:8000/v1/bot/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: <tenant-uuid>" \
  -F "file=@my_store_faq.txt" \
  -F "document_type=faq"
```

### 2. Configure Bot Personality

Update tenant settings via Django admin or API:

```python
# Via Django shell
python manage.py shell

from apps.tenants.models import Tenant, TenantSettings

tenant = Tenant.objects.get(slug='starter-store')
settings = tenant.settings

# Configure bot personality
settings.bot_name = "Sarah"
settings.bot_personality = "friendly"  # friendly, professional, casual
settings.welcome_message = "Hi! I'm Sarah from Starter Store. How can I help you today?"
settings.confidence_threshold = 0.7
settings.enable_spelling_correction = True
settings.save()
```

### 3. Test Bot Responses

Send a test message via API:

```bash
curl -X POST http://localhost:8000/v1/webhooks/twilio/inbound/<tenant-id> \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+254722000000" \
  -d "Body=Hi, what products do you have?"
```

### 4. Monitor Bot Performance

Check bot analytics in Django admin:
- **Conversations** → View all customer interactions
- **Messages** → See bot responses and confidence scores
- **Analytics Daily** → Track AI performance metrics

---

## 🏃 Running the Application

### Development Mode

**Terminal 1 - Django Server:**
```bash
source venv/bin/activate
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```bash
source venv/bin/activate
celery -A config worker -l info
```

**Terminal 3 - Celery Beat (Scheduled Tasks):**
```bash
source venv/bin/activate
celery -A config beat -l info
```

### Production Mode (Docker)

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Seed data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers
docker-compose exec web python manage.py seed_demo_data

# View logs
docker-compose logs -f web
```

### Health Check

Verify the application is running:

```bash
curl http://localhost:8000/v1/health/

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "celery": "running"
}
```

---

## 📚 API Documentation

### Interactive API Docs

Once running, access comprehensive API documentation:

- **Swagger UI**: http://localhost:8000/schema/swagger/
- **ReDoc**: http://localhost:8000/schema/redoc/
- **OpenAPI Schema**: http://localhost:8000/schema/

### Authentication

All API requests require JWT authentication:

```bash
# 1. Login to get token
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@starter.demo",
    "password": "demo123!"
  }'

# Response:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "email": "owner@starter.demo",
    "first_name": "Owner"
  }
}

# 2. Use token in requests
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "X-TENANT-ID: <tenant-uuid>"
```

### Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/auth/login` | POST | Login and get JWT token |
| `/v1/auth/register` | POST | Register new user |
| `/v1/products` | GET | List products |
| `/v1/products` | POST | Create product |
| `/v1/services` | GET | List services |
| `/v1/appointments` | POST | Book appointment |
| `/v1/orders` | GET | List orders |
| `/v1/conversations` | GET | List conversations |
| `/v1/analytics/daily` | GET | Get daily analytics |
| `/v1/wallet/balance` | GET | Get wallet balance |

### Postman Collection

Import the Postman collection for easy API testing:

```bash
# Collection is at: postman/postman_collection.json
# Import into Postman and set environment variables
```

---

## 🧪 Testing

### Run All Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with coverage report
pytest --cov=apps --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Tests

```bash
# Test specific app
pytest apps/bot/tests/

# Test specific file
pytest apps/bot/tests/test_intent_service.py

# Test specific function
pytest apps/bot/tests/test_intent_service.py::test_classify_intent

# Run with markers
pytest -m unit  # Only unit tests
pytest -m integration  # Only integration tests
```

### Test Coverage

Current test coverage:
- **Core**: 95%
- **Tenants**: 92%
- **Messaging**: 88%
- **Bot**: 85%
- **Catalog**: 90%
- **Orders**: 87%
- **RBAC**: 93%

### Manual Testing Checklist

**1. Create Tenant:**
```bash
python manage.py seed_demo_tenant --name "Test Store" --slug "test-store" --email "test@example.com"
```

**2. Login:**
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"demo123!"}'
```

**3. Create Product:**
```bash
curl -X POST http://localhost:8000/v1/products \
  -H "Authorization: Bearer <token>" \
  -H "X-TENANT-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Product",
    "description": "A test product",
    "price": "99.99",
    "currency": "USD",
    "sku": "TEST-001"
  }'
```

**4. Simulate WhatsApp Message:**
```bash
curl -X POST http://localhost:8000/v1/webhooks/twilio/inbound/<tenant-id> \
  -d "From=whatsapp:+254722000000" \
  -d "Body=Show me your products"
```

---

## 📁 Project Structure

```
tulia.api/
├── apps/                           # Django applications
│   ├── core/                       # Base models, middleware, utilities
│   │   ├── models.py              # BaseModel with UUID, soft delete
│   │   ├── middleware.py          # Tenant context, request ID
│   │   └── permissions.py         # RBAC permission classes
│   ├── tenants/                   # Tenant management
│   │   ├── models.py              # Tenant, TenantSettings, SubscriptionTier
│   │   ├── services/              # TenantService for business logic
│   │   └── management/commands/   # seed_demo_data, seed_demo_tenant
│   ├── rbac/                      # Role-Based Access Control
│   │   ├── models.py              # User, Role, Permission, TenantUser
│   │   ├── services.py            # RBACService, AuthService
│   │   └── management/commands/   # seed_permissions, seed_tenant_roles
│   ├── messaging/                 # WhatsApp messaging
│   │   ├── models.py              # Conversation, Message, MessageTemplate
│   │   ├── services/              # TwilioService, MessageService
│   │   └── views.py               # Webhook handlers
│   ├── bot/                       # AI bot and intent handling
│   │   ├── services/              # IntentService, RAGService
│   │   ├── tools/                 # Bot tools (product search, booking)
│   │   └── tasks.py               # Celery tasks for async processing
│   ├── catalog/                   # Product catalog
│   │   ├── models.py              # Product, ProductVariant
│   │   └── views.py               # Product CRUD APIs
│   ├── services/                  # Service booking
│   │   ├── models.py              # Service, ServiceVariant, Appointment
│   │   └── views.py               # Booking APIs
│   ├── orders/                    # Order management
│   │   ├── models.py              # Order, OrderItem
│   │   └── views.py               # Order APIs
│   ├── integrations/              # External integrations
│   │   ├── services/              # WooService, ShopifyService, PaymentService
│   │   │   ├── mpesa_service.py  # M-Pesa integration
│   │   │   ├── paystack_service.py
│   │   │   └── payment_service.py
│   │   └── views.py               # Webhook handlers
│   └── analytics/                 # Analytics and metrics
│       ├── models.py              # AnalyticsDaily, AnalyticsMonthly
│       └── tasks.py               # Aggregation tasks
├── config/                        # Django configuration
│   ├── settings.py                # Main settings
│   ├── urls.py                    # URL routing
│   ├── celery.py                  # Celery configuration
│   └── wsgi.py                    # WSGI application
├── docs/                          # Documentation
│   ├── architecture/              # System architecture docs
│   ├── guides/                    # User and developer guides
│   └── setup/                     # Setup and configuration
├── test_data/                     # Test fixtures and sample data
│   └── sample_faq.txt            # Example FAQ for bot training
├── postman/                       # Postman collections
├── scripts/                       # Utility scripts
├── logs/                          # Application logs
├── .env.example                   # Environment variables template
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Pytest configuration
├── conftest.py                    # Pytest fixtures
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Docker services
└── manage.py                      # Django management script
```

---

## 📖 Documentation

Comprehensive documentation is available in the `docs/` directory:

### Architecture
- **[Platform Overview](docs/architecture/WABOTIQ_PLATFORM_OVERVIEW.md)** - Complete system architecture
- **[Tenant Data Structure](docs/architecture/TENANT_DATA_STRUCTURE.md)** - Data models and relationships
- **[RAG Flow Diagram](docs/architecture/RAG_FLOW_DIAGRAM.md)** - How the AI bot learns
- **[Security Analysis](docs/architecture/SECURITY_ANALYSIS.md)** - Security architecture
- **[Security Audit Report](docs/architecture/SECURITY_AUDIT_REPORT.md)** - Security findings

### Guides
- **[Authentication Guide](docs/guides/AUTHENTICATION_GUIDE.md)** - JWT auth and API access
- **[Payment Integration](docs/guides/PAYMENT_INTEGRATION_SUMMARY.md)** - M-Pesa, Paystack, Stripe setup
- **[Quick Reference](docs/guides/QUICK_REFERENCE.md)** - Common tasks and commands
- **[Quick Test Reference](docs/guides/QUICK_TEST_REFERENCE.md)** - Testing guide
- **[Multi-language Setup](docs/guides/MULTILINGUAL_QUICK_START.md)** - Language support
- **[RAG Explanation](docs/guides/RAG_BABY_MODE_EXPLANATION.md)** - RAG system simplified

### Setup
- **[Starter Store Setup](docs/setup/STARTER_STORE_SETUP.md)** - Demo tenant setup
- **[Test User Guide](docs/setup/TEST_USER_SETUP_GUIDE.md)** - Creating test users
- **[Test Data Summary](docs/setup/TEST_DATA_SUMMARY.md)** - Test data structure

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Database Connection Error

**Error**: `django.db.utils.OperationalError: could not connect to server`

**Solution**:
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list  # macOS

# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql  # macOS

# Verify connection
psql -U wabotiq_user -d wabotiq -h localhost
```

#### 2. Redis Connection Error

**Error**: `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solution**:
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Start Redis
sudo systemctl start redis  # Linux
brew services start redis  # macOS
```

#### 3. Celery Worker Not Processing Tasks

**Error**: Tasks stuck in queue, not executing

**Solution**:
```bash
# Check Celery worker is running
celery -A config inspect active

# Restart worker with verbose logging
celery -A config worker -l debug

# Check Redis queue
redis-cli
> LLEN celery
> LRANGE celery 0 -1
```

#### 4. OpenAI API Key Invalid

**Error**: `openai.error.AuthenticationError: Incorrect API key`

**Solution**:
```bash
# Verify API key in .env
cat .env | grep OPENAI_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Get new key from: https://platform.openai.com/api-keys
```

#### 5. Migrations Not Applied

**Error**: `django.db.utils.ProgrammingError: relation does not exist`

**Solution**:
```bash
# Check migration status
python manage.py showmigrations

# Apply all migrations
python manage.py migrate

# If migrations conflict, reset (⚠️ destroys data)
python manage.py migrate --fake-initial
```

#### 6. Port Already in Use

**Error**: `Error: That port is already in use`

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
python manage.py runserver 8001
```

#### 7. Permission Denied Errors

**Error**: `PermissionError: [Errno 13] Permission denied`

**Solution**:
```bash
# Fix file permissions
chmod +x manage.py
chmod -R 755 logs/

# Fix virtual environment
chmod -R 755 venv/
```

#### 8. Module Not Found

**Error**: `ModuleNotFoundError: No module named 'apps'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify Python path
python -c "import sys; print(sys.path)"
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs**: `tail -f logs/django.log`
2. **Enable debug mode**: Set `DEBUG=True` in `.env`
3. **Check Django admin**: http://localhost:8000/admin
4. **Review documentation**: See `docs/` directory
5. **Check API docs**: http://localhost:8000/schema/swagger/

### Debug Mode

Enable verbose logging for troubleshooting:

```python
# config/settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

---

## 🚀 Deployment

### Production Checklist

Before deploying to production:

- [ ] Set `DEBUG=False` in `.env`
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Set up PostgreSQL with connection pooling
- [ ] Configure Redis with persistence
- [ ] Set up SSL/TLS certificates
- [ ] Configure Sentry for error tracking
- [ ] Set up backup strategy
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerts
- [ ] Review security settings
- [ ] Test all integrations
- [ ] Set up log rotation

### Docker Production Deployment

```bash
# 1. Build production image
docker-compose -f docker-compose.prod.yml build

# 2. Start services
docker-compose -f docker-compose.prod.yml up -d

# 3. Run migrations
docker-compose exec web python manage.py migrate

# 4. Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# 5. Seed initial data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers

# 6. Create superuser
docker-compose exec web python manage.py createsuperuser

# 7. Verify deployment
curl https://your-domain.com/v1/health/
```

### Environment-Specific Settings

**Development**:
```bash
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

**Staging**:
```bash
DEBUG=False
ALLOWED_HOSTS=staging.wabotiq.com
SENTRY_ENVIRONMENT=staging
```

**Production**:
```bash
DEBUG=False
ALLOWED_HOSTS=api.wabotiq.com
SENTRY_ENVIRONMENT=production
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Run tests**: `pytest`
5. **Commit changes**: `git commit -m 'Add amazing feature'`
6. **Push to branch**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Code Standards

- Follow PEP 8 style guide
- Write docstrings for all functions/classes
- Add tests for new features
- Update documentation
- Use type hints where applicable

---

## 📄 License

Proprietary - All rights reserved

---

## 🙏 Acknowledgments

Built with:
- [Django](https://www.djangoproject.com/) - Web framework
- [Django REST Framework](https://www.django-rest-framework.org/) - API framework
- [Celery](https://docs.celeryproject.org/) - Task queue
- [OpenAI](https://openai.com/) - AI/LLM
- [Twilio](https://www.twilio.com/) - WhatsApp API
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Redis](https://redis.io/) - Cache and queue

---

## 📞 Support

For questions, issues, or support:

- **Email**: support@wabotiq.com
- **Documentation**: [docs/](docs/)
- **API Docs**: http://localhost:8000/schema/swagger/

---

**Made with ❤️ for conversational commerce**
