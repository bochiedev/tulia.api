# Tulia AI - Conversational Commerce Platform

> **Multi-tenant WhatsApp commerce platform** that enables businesses to sell products and services through AI-powered conversations.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

---

## 🚀 Quick Start

**New to Tulia AI?** Follow our comprehensive [Setup Guide](SETUP.md) to get running in 10 minutes.

```bash
# 1. Clone and setup
git clone <repository-url>
cd tulia.api
python -m venv venv
source venv/bin/activate

# 2. Choose your installation type:

# Full installation (includes AI/RAG features)
pip install -r requirements.txt

# OR minimal installation (basic API only)
pip install -r requirements-minimal.txt

# OR development installation (includes testing tools)
pip install -r requirements-dev.txt

# 2. Configure (see SETUP.md for details)
cp .env.example .env
# Edit .env with your AI provider API key

# 3. Database and demo data
python manage.py migrate
python manage.py seed_permissions
python manage.py seed_subscription_tiers
python manage.py seed_demo_data

# 4. Run
python manage.py runserver
```

**Access:**
- API: http://localhost:8000
- Admin: http://localhost:8000/admin
- API Docs: http://localhost:8000/schema/swagger/

---

## 📋 What is Tulia AI?

**Tulia AI** is a **multi-tenant SaaS platform** that transforms WhatsApp into a complete commerce channel. Businesses can:

- 🛍️ **Sell products** - Sync catalogs from WooCommerce/Shopify or manage natively
- 📅 **Book services** - Schedule appointments with availability management
- 💬 **Automate conversations** - AI bot handles customer inquiries 24/7
- 💳 **Process payments** - Integrated wallet with M-Pesa, Paystack, Stripe, Pesapal
- 📊 **Track analytics** - Comprehensive metrics on sales, conversations, customer behavior
- 🌍 **Multi-language** - English, Swahili, Sheng with automatic detection
- 🔐 **Enterprise RBAC** - Role-based access control with scope-based permissions

---

## 📖 Documentation

- **[Setup Guide](SETUP.md)** - Complete installation and configuration guide
- **[API Documentation](http://localhost:8000/schema/swagger/)** - Interactive API docs (when running)
- **[Architecture Overview](docs/architecture/)** - System design and data models

---

## 📦 Requirements Files

Choose the appropriate requirements file for your use case:

| File | Purpose | Use Case |
|------|---------|----------|
| `requirements.txt` | **Full production** | Complete platform with AI/RAG features |
| `requirements-minimal.txt` | **Basic API only** | Core Django API without AI features |
| `requirements-dev.txt` | **Development** | Includes testing tools and dev dependencies |

**Python 3.12.4 Compatible** - All versions tested for compatibility and minimal conflicts.

### Installation Examples

```bash
# Production deployment with all features
pip install -r requirements.txt

# Lightweight deployment (no AI features)
pip install -r requirements-minimal.txt

# Development environment
pip install -r requirements-dev.txt
```

---

## 🔧 Key Features

### Multi-Tenant Architecture
- Complete data isolation between tenants
- Subscription tiers (Starter, Growth, Enterprise)
- Per-tenant configuration and branding

### AI-Powered Conversations
- Uses LangChain/LangGraph for conversation management
- Supports OpenAI, Google Gemini, and Together AI
- RAG system learns from uploaded documents
- Multi-language support with automatic detection

### WhatsApp Integration
- **Important**: Twilio credentials configured per tenant, not globally
- **Future**: Meta Tech Provider integration for direct WhatsApp Business API
- Rich messaging (buttons, lists, images, product cards)

### Payment Processing
- M-Pesa (Kenya mobile payments)
- Paystack (African card payments)
- Stripe (International payments)
- Pesapal (East African payments)
- **Note**: Payment providers configured per tenant

### Security & RBAC
- JWT authentication with scope-based permissions
- Complete audit logging
- Encrypted credentials storage
- Multi-tenant data isolation

---

## 🏃 Running the Application

See [SETUP.md](SETUP.md) for detailed instructions.

**Development:**
```bash
python manage.py runserver                    # Django server
celery -A config worker -l info              # Background tasks (optional)
celery -A config beat -l info                # Scheduled tasks (optional)
```

**Production:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📚 API Usage

### Authentication
```bash
# Login to get JWT token
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Use token in requests
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID"
```

### Key Endpoints
- `/v1/auth/login` - Authentication
- `/v1/tenants` - Tenant management
- `/v1/products` - Product catalog
- `/v1/services` - Service booking
- `/v1/orders` - Order management
- `/v1/conversations` - WhatsApp conversations
- `/v1/analytics/daily` - Analytics data

---

## 🧪 Testing

```bash
pytest                                        # Run all tests
pytest --cov=apps --cov-report=html         # With coverage
pytest apps/bot/tests/                       # Specific tests
```

---

## 📁 Project Structure

```
tulia.api/
├── apps/                    # Django applications
│   ├── core/               # Base models, middleware, utilities
│   ├── tenants/            # Multi-tenant management
│   ├── rbac/               # Role-based access control
│   ├── messaging/          # WhatsApp messaging via Twilio
│   ├── bot/                # AI conversation handling (LangChain/LangGraph)
│   ├── catalog/            # Product catalog management
│   ├── services/           # Service booking and appointments
│   ├── orders/             # Order processing and management
│   ├── integrations/       # External integrations (WooCommerce, Shopify, Payments)
│   └── analytics/          # Business analytics and reporting
├── config/                 # Django configuration
├── docs/                   # Architecture documentation
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── SETUP.md               # Detailed setup guide
└── README.md              # This file
```

---

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Generate strong secrets (see SETUP.md)
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Set up PostgreSQL with connection pooling
- [ ] Configure Redis with persistence
- [ ] Set up SSL/TLS certificates
- [ ] Configure monitoring (Sentry)
- [ ] Set up backup strategy

### Docker Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📞 Support

- **Setup Issues**: See [SETUP.md](SETUP.md)
- **API Questions**: http://localhost:8000/schema/swagger/
- **Email**: support@trytulia.com

---

## 🔑 Key Points

1. **Multi-tenant**: Each business is a separate tenant with isolated data
2. **Twilio per tenant**: Configure WhatsApp credentials per tenant, not in .env
3. **AI via LangChain**: Uses LangChain/LangGraph - no direct API management needed
4. **Payment per tenant**: Configure payment providers per tenant in admin
5. **Future Meta integration**: Will replace Twilio dependency for WhatsApp
6. **One AI provider**: Configure only OpenAI OR Gemini OR Together AI - not all three

---

**Built with ❤️ for conversational commerce**