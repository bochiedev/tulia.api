# TuliaAI - Intelligent WhatsApp Commerce Platform

> **Enterprise-grade conversational commerce platform** that transforms WhatsApp into a complete sales and service channel using advanced AI orchestration.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)

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

## 🤖 What is TuliaAI?

**TuliaAI** is an **enterprise conversational commerce platform** that transforms WhatsApp into a complete business channel. Built with advanced AI orchestration and strict multi-tenant architecture, it enables businesses to:

- 🛍️ **Sell products & services** - Complete catalog management with intelligent recommendations
- 💬 **Automate conversations** - Advanced AI handles customer inquiries with human-like intelligence  
- 💳 **Process payments** - Integrated payment processing with multiple providers
- 📊 **Track performance** - Comprehensive analytics and business intelligence
- 🌍 **Scale globally** - Multi-language support with automatic detection
- 🔐 **Enterprise security** - Role-based access control with audit trails

**Perfect for**: E-commerce businesses, service providers, consultants, and enterprises requiring secure, scalable conversational commerce.

---

## ✨ Key Features

### 🏢 Multi-Tenant Architecture
- Complete tenant isolation with enterprise-grade security
- Flexible subscription tiers with feature controls
- Scalable infrastructure supporting thousands of tenants

### 💬 Advanced AI Orchestration  
- State-of-the-art LangGraph-based conversation management
- Multi-provider LLM support (OpenAI, Gemini, Together AI)
- Intelligent RAG system with document learning capabilities
- Context-aware responses with conversation memory

### 🛒 Complete Commerce Suite
- Product catalog with variants and inventory management
- Service booking with availability windows
- Order processing with payment integration
- Real-time analytics and reporting

### 💳 Payment Processing
- **M-Pesa** - Mobile money for Kenya market
- **Paystack** - Cards and mobile money across Africa  
- **Stripe** - International card payments
- **Pesapal** - East African payment gateway
- Wallet system with transaction tracking

### 🔐 Enterprise Security
- JWT-based authentication with role-based access control
- Scope-based permissions for granular access management
- Complete audit logging and compliance tracking
- Encrypted data storage and secure API endpoints

---

## 🚀 Quick Start

Get TuliaAI running in **5 minutes**:

```bash
# 1. Clone and setup
git clone <repository-url>
cd tulia.ai
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your database and API keys

# 3. Initialize database
python manage.py migrate
python manage.py seed_permissions
python manage.py seed_demo_data

# 4. Start services
python manage.py runserver &
celery -A config worker -l info &
celery -A config beat -l info &
```

**Access Points:**
- API: http://localhost:8000
- Admin: http://localhost:8000/admin  
- API Docs: http://localhost:8000/schema/swagger/

---

## 📦 Prerequisites

### Required Services

| Service | Version | Purpose |
|---------|---------|---------|
| **Python** | 3.12+ | Runtime environment |
| **PostgreSQL** | 15+ | Primary database |
| **Redis** | 7+ | Cache and message queue |

### API Keys Required

| Service | Purpose | Required? |
|---------|---------|-----------|
| **OpenAI** | AI conversation engine | ✅ Yes |
| **Twilio** | WhatsApp messaging | ✅ Yes |
| **Payment Provider** | Transaction processing | ⚠️ Optional |

**Note**: Payment providers (M-Pesa, Paystack, Stripe) are optional for development and testing.

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

# Production dependencies
pip install -r requirements.txt

# For development (includes testing and code quality tools)
pip install -r requirements-dev.txt
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

### Environment Setup

Copy and configure the environment file:

```bash
cp .env.example .env
```

### Essential Configuration

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/tulia_ai

# Cache and Queue  
REDIS_URL=redis://localhost:6379/0

# AI Engine (Required)
OPENAI_API_KEY=sk-proj-your-openai-key-here
OPENAI_MODEL=gpt-4o-mini

# WhatsApp Integration (Required)
TWILIO_ACCOUNT_SID=AC********************************
TWILIO_AUTH_TOKEN=********************************
TWILIO_WHATSAPP_NUMBER=+14155238886

# Payment Processing (Optional)
MPESA_CONSUMER_KEY=your-mpesa-key
PAYSTACK_SECRET_KEY=sk_test_your-paystack-key
STRIPE_SECRET_KEY=sk_test_your-stripe-key
```

### Docker Setup

For production deployment:

```bash
# Start all services
docker-compose up -d

# Initialize database
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py seed_demo_data
```

---

## 🏃 Running the Application

### Development Mode

```bash
# Terminal 1 - Main application
python manage.py runserver

# Terminal 2 - Background tasks  
celery -A config worker -l info

# Terminal 3 - Scheduled tasks
celery -A config beat -l info
```

### Production Mode

```bash
# Using Docker
docker-compose -f docker-compose.prod.yml up -d

# Verify deployment
curl http://localhost:8000/v1/health/
```

## 📚 API Documentation

Access comprehensive API documentation:

- **Interactive Docs**: http://localhost:8000/schema/swagger/
- **API Schema**: http://localhost:8000/schema/

### Authentication

All API requests require JWT authentication:

```bash
# Login to get token
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'

# Use token in requests
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "X-TENANT-ID: <tenant-uuid>"
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov-report=html

# Test specific module
pytest apps/bot/tests/
```

## 🔧 Troubleshooting

### Common Issues

**Database Connection Error:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list  # macOS

# Verify connection
psql -U your_user -d tulia_ai -h localhost
```

**Redis Connection Error:**
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Start Redis if needed
sudo systemctl start redis  # Linux
brew services start redis  # macOS
```

**API Key Issues:**
```bash
# Verify OpenAI API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Getting Help

- Check application logs: `tail -f logs/django.log`
- Enable debug mode: Set `DEBUG=True` in `.env`
- Review API documentation: http://localhost:8000/schema/swagger/

---

## 📄 License

Proprietary - All rights reserved

---

## 🙏 Acknowledgments

Built with Django, PostgreSQL, Redis, and advanced AI technologies.

---

**TuliaAI - Transforming conversations into commerce**
