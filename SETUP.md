# Tulia AI Setup Guide

This guide will get you up and running with Tulia AI in **10 minutes**.

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.12+ | Runtime |
| **PostgreSQL** | 15+ | Database (optional - SQLite works for development) |
| **Redis** | 7+ | Cache & Queue (optional for development) |

### Required API Keys

You need **at least one** AI provider:

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| **OpenAI** | AI conversations (recommended) | [platform.openai.com](https://platform.openai.com/) |
| **Google Gemini** | AI conversations (cost-effective) | [ai.google.dev](https://ai.google.dev/) |
| **Together AI** | Open source models | [together.ai](https://together.ai/) |

## Installation

### 1. Clone and Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd tulia.api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# === REQUIRED SETTINGS ===
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite for development)
DATABASE_URL=sqlite:///db.sqlite3

# Redis (optional for development)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# AI Provider (choose ONE - you don't need all three)
OPENAI_API_KEY=sk-proj-your-openai-key-here
OPENAI_MODEL=gpt-4o-mini

# Alternative providers (uncomment ONE if not using OpenAI):
# GEMINI_API_KEY=your-gemini-key-here
# TOGETHER_API_KEY=your-together-key-here

# JWT Authentication
JWT_SECRET_KEY=your-jwt-secret-key-32-chars-minimum
JWT_ALGORITHM=HS256

# Encryption
ENCRYPTION_KEY=your-base64-encoded-32-byte-key
```

### 3. Generate Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"

# Generate JWT_SECRET_KEY  
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(50))"

# Generate ENCRYPTION_KEY
python -c "import os, base64; print('ENCRYPTION_KEY=' + base64.b64encode(os.urandom(32)).decode('utf-8'))"
```

### 4. Database Setup

```bash
# Run migrations
python manage.py migrate

# Seed system data (required)
python manage.py seed_permissions
python manage.py seed_subscription_tiers

# Create admin user
python manage.py createsuperuser
```

### 5. Create Demo Data (Optional)

```bash
# Create demo tenants with sample data
python manage.py seed_demo_data
```

This creates 3 demo tenants:
- **Starter Store** (starter-store)
- **Growth Business** (growth-business)  
- **Enterprise Corp** (enterprise-corp)

Default password for demo users: `demo123!`

## Running the Application

### Development Mode

**Terminal 1 - Django Server:**
```bash
source venv/bin/activate
python manage.py runserver
```

**Terminal 2 - Celery Worker (Optional):**
```bash
source venv/bin/activate
celery -A config worker -l info
```

**Terminal 3 - Celery Beat (Optional):**
```bash
source venv/bin/activate
celery -A config beat -l info
```

### Access Points

- **API**: http://localhost:8000
- **Admin**: http://localhost:8000/admin  
- **API Docs**: http://localhost:8000/schema/swagger/
- **Health Check**: http://localhost:8000/v1/health/

## Tenant Configuration

**Important**: Tulia AI is multi-tenant. Each business is a separate tenant with isolated data.

### WhatsApp Integration

**Twilio credentials are configured PER TENANT, not in .env file.**

1. **Create a tenant** (via Django admin or API)
2. **Configure Twilio in tenant settings**:
   - Go to Django Admin → Tenants → Tenant Settings
   - Add your Twilio Account SID, Auth Token, and WhatsApp number
3. **Set up webhook** in Twilio console:
   ```
   Webhook URL: https://your-domain.com/v1/webhooks/twilio/inbound/{tenant_id}
   ```

### Payment Providers

Payment providers are also configured **per tenant**:
- M-Pesa (Kenya)
- Paystack (Africa)  
- Stripe (International)
- Pesapal (East Africa)

Configure these in Django Admin → Tenants → Tenant Settings.

### Future: Meta Tech Provider

The long-term solution is **Meta Tech Provider** integration, which will allow direct WhatsApp Business API access without Twilio dependency.

## AI Bot Configuration

### How It Works

The AI bot uses **LangChain and LangGraph** for conversation management. You don't need to manage OpenAI API calls directly - LangChain handles this internally.

### Choose ONE AI Provider

**Important**: You only need to configure **ONE** AI provider. The system will automatically use whichever provider you configure. You don't need accounts with all three providers.

**Available Providers:**

1. **OpenAI** (Recommended)
   - Models: gpt-4o, gpt-4o-mini, gpt-4-turbo
   - Best performance and reliability
   - Moderate cost
   - Get API key: [platform.openai.com](https://platform.openai.com/)

2. **Google Gemini** (Cost-effective)
   - Models: gemini-1.5-pro, gemini-1.5-flash
   - Large context window (1M tokens)
   - Lower cost than OpenAI
   - Get API key: [ai.google.dev](https://ai.google.dev/)

3. **Together AI** (Open source)
   - Access to Llama, Mistral, Qwen models
   - Very cost-effective for high volume
   - Open source model access
   - Get API key: [together.ai](https://together.ai/)

**Configuration Example:**
```bash
# Choose ONE of these in your .env file:

# Option 1: OpenAI
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini

# Option 2: Gemini (comment out OpenAI above)
# GEMINI_API_KEY=your-gemini-key-here

# Option 3: Together AI (comment out others above)
# TOGETHER_API_KEY=your-together-key-here
```

The system will automatically detect which provider is configured and use it. You can switch providers anytime by updating your .env file.

### Training the Bot

Upload knowledge documents to train the bot:

1. **Via Django Admin**:
   - Go to Bot → Documents → Add Document
   - Upload FAQ files, product catalogs, etc.

2. **Via API**:
   ```bash
   curl -X POST http://localhost:8000/v1/bot/documents/upload \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-TENANT-ID: $TENANT_ID" \
     -F "file=@faq.txt" \
     -F "document_type=faq"
   ```

## API Usage

### Authentication

All API requests require JWT authentication:

```bash
# 1. Login to get token
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Response includes token:
# {"token": "eyJ...", "user": {...}}

# 2. Use token in API requests
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID"
```

### Demo Tenant API Keys

If you ran `seed_demo_data`, you can use these for testing:

```bash
# Starter Store
TENANT_ID="604923c8-cff3-49d7-b3a3-fe5143c5c46b"
API_KEY="a96b73152af3e755424b11a6dad39a44bbebb553c7608f0b138a48ba95e54d68"

# Test API call
curl -X GET http://localhost:8000/v1/products \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY"
```

## Testing

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=apps --cov-report=html

# Specific tests
pytest apps/bot/tests/
```

### Manual Testing

1. **Create a product**:
   ```bash
   curl -X POST http://localhost:8000/v1/products \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-TENANT-ID: $TENANT_ID" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Test Product",
       "description": "A test product", 
       "price": "99.99",
       "currency": "USD"
     }'
   ```

2. **Simulate WhatsApp message**:
   ```bash
   curl -X POST http://localhost:8000/v1/webhooks/twilio/inbound/$TENANT_ID \
     -d "From=whatsapp:+254722000000" \
     -d "Body=Show me your products"
   ```

## Troubleshooting

### Common Issues

**Database Error:**
```bash
# Check if migrations are applied
python manage.py showmigrations

# Apply migrations
python manage.py migrate
```

**Redis Connection Error:**
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Start Redis (Linux)
sudo systemctl start redis

# Start Redis (macOS)
brew services start redis
```

**AI Model Not Working:**
- Verify API key is correct
- Check you have sufficient credits/quota
- Ensure model name is supported

**Twilio Webhook Issues:**
- Verify webhook URL is publicly accessible (use ngrok for development)
- Check tenant has Twilio credentials configured
- Verify webhook signature validation

### Health Check

```bash
curl http://localhost:8000/v1/health/
# Expected: {"status": "healthy", "database": "connected", "redis": "connected"}
```

### Debug Mode

Enable detailed logging in `.env`:
```bash
DEBUG=True
LOG_LEVEL=DEBUG
```

## Production Deployment

### Environment Settings

```bash
# Production settings
DEBUG=False
ALLOWED_HOSTS=api.trytulia.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Use PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/tulia_db

# Use Redis
REDIS_URL=redis://localhost:6379/0
```

### Docker Deployment

```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Seed system data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers
```

### Security Checklist

- [ ] Generate strong `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring (Sentry)
- [ ] Configure backup strategy
- [ ] Review CORS settings

## Support

For questions or issues:
- **Email**: support@trytulia.com
- **API Documentation**: http://localhost:8000/schema/swagger/

## Key Points to Remember

1. **Multi-tenant**: Each business is a separate tenant
2. **Twilio per tenant**: Configure WhatsApp credentials per tenant, not globally
3. **AI via LangChain**: No direct API key management needed
4. **Future Meta integration**: Will replace Twilio dependency
5. **Payment per tenant**: Configure payment providers per tenant
6. **One AI provider**: Configure only OpenAI OR Gemini OR Together AI - not all three

---

**You're ready to build conversational commerce! 🚀**