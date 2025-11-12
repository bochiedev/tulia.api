# Tulia AI - WhatsApp Commerce & Services Platform

> Multi-tenant WhatsApp commerce and services platform with AI-powered conversational commerce, comprehensive RBAC, and subscription management.

Multi-tenant WhatsApp-based commerce and services platform powered by AI.

## Features

- **Multi-Tenant Architecture**: Strict tenant isolation with separate customer data, catalogs, and analytics
- **WhatsApp Integration**: Twilio-powered WhatsApp messaging for customer interactions
- **Product Catalog**: Sync products from WooCommerce and Shopify
- **Service Booking**: Native appointment scheduling with availability management
- **AI-Powered Bot**: Intent classification and conversational commerce
- **Subscription Management**: Tiered pricing with feature limits
- **Payment Facilitation**: Integrated wallet system with transaction fees
- **Analytics**: Comprehensive metrics for messages, orders, bookings, and revenue
- **Consent Management**: GDPR-compliant customer preference tracking

## Tech Stack

- **Backend**: Django 4.2+, Django REST Framework
- **Database**: PostgreSQL with connection pooling
- **Cache & Queue**: Redis, Celery
- **AI/LLM**: OpenAI/Claude for intent classification
- **Messaging**: Twilio WhatsApp API
- **Monitoring**: Sentry for error tracking
- **API Docs**: OpenAPI 3.0 with Swagger UI

## Project Structure

```
tulia/
├── apps/
│   ├── core/          # Base models, middleware, utilities
│   ├── tenants/       # Tenant management and isolation
│   ├── messaging/     # WhatsApp messaging and templates
│   ├── catalog/       # Product catalog management
│   ├── orders/        # Order and cart management
│   ├── services/      # Service booking and availability
│   ├── analytics/     # Metrics and reporting
│   ├── integrations/  # Twilio, WooCommerce, Shopify
│   └── bot/           # AI intent classification and handlers
├── config/            # Django settings and configuration
├── logs/              # Application logs
└── manage.py
```

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+ (using psycopg3 driver)
- Redis 7+
- Docker & Docker Compose (optional)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tulia
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

8. **Run Celery worker** (in separate terminal)
   ```bash
   celery -A config worker -l info
   ```

9. **Run Celery beat** (in separate terminal)
   ```bash
   celery -A config beat -l info
   ```

### Docker Setup

1. **Build and start services**
   ```bash
   docker-compose up -d
   ```

2. **Run migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

3. **Create superuser**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

## API Documentation

Once the server is running, access the API documentation at:

- **OpenAPI Schema**: http://localhost:8000/schema/
- **Swagger UI**: http://localhost:8000/schema/swagger/

## Django Admin Panel

Access the Django admin panel to manage your data:

- **Admin Panel**: http://localhost:8000/admin
- **Login**: Use your superuser credentials

Create a superuser if you haven't already:
```bash
python manage.py createsuperuser
# Or with Docker:
docker-compose exec web python manage.py createsuperuser
```

The admin panel provides full CRUD access to:
- Tenants, subscriptions, and wallets
- RBAC (roles, permissions, users)
- Products, services, and appointments
- Customers, conversations, and messages
- Orders and analytics

## Health Check

Check system health at: http://localhost:8000/v1/health/

## Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps

# Run specific test file
pytest apps/core/tests/test_models.py

# Run with markers
pytest -m unit
pytest -m integration
```

## Configuration

### Environment Variables

Key environment variables (see `.env.example` for full list):

- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CELERY_BROKER_URL`: Celery broker URL
- `OPENAI_API_KEY`: OpenAI API key for intent classification
- `SENTRY_DSN`: Sentry DSN for error tracking

### Celery Queues

- `default`: General background tasks
- `integrations`: External API calls (Twilio, WooCommerce, Shopify)
- `analytics`: Metrics aggregation and reporting
- `messaging`: Outbound message processing
- `bot`: Intent classification and response generation

## Development Guidelines

### Multi-Tenant First

Every query must be tenant-scoped. Never leak cross-tenant data.

```python
# Good
products = Product.objects.filter(tenant=tenant, is_active=True)

# Bad
products = Product.objects.filter(is_active=True)
```

### BaseModel Usage

All models should inherit from `BaseModel` for UUID primary keys, soft delete, and timestamps:

```python
from apps.core.models import BaseModel

class MyModel(BaseModel):
    name = models.CharField(max_length=255)
```

### Logging

Use structured logging with request_id and tenant_id:

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Processing order", extra={
    'order_id': str(order.id),
    'tenant_id': str(tenant.id),
})
```

## License

Proprietary - All rights reserved

## Documentation

All documentation is organized in the **[docs/](docs/)** folder:

- **[Quick Start](docs/QUICKSTART_DEPLOYMENT.md)** - Get up and running in 10 minutes
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Complete deployment guide
- **[Twilio Webhook Setup](docs/TWILIO_WEBHOOK_SETUP.md)** - Configure Twilio webhooks
- **[API Documentation](docs/api/)** - API reference and Postman guides
- **[Complete Documentation Index](docs/README.md)** - Browse all documentation

### Quick Production Deployment

```bash
# 1. Clone and configure
git clone <repository-url>
cd tulia
cp .env.example .env
# Edit .env with production values

# 2. Start services with production configuration
docker-compose -f docker-compose.prod.yml up -d

# 3. Run migrations
docker-compose exec web python manage.py migrate

# 4. Seed initial data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers

# 5. Verify deployment
curl https://api.yourdomain.com/v1/health
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Support

For support, contact: support@tulia.ai
