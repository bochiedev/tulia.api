# Environment Variables Reference

This document provides a comprehensive reference for all environment variables used in the Tulia AI WhatsApp Commerce Platform.

## Table of Contents

1. [Core Django Settings](#core-django-settings)
2. [Database Configuration](#database-configuration)
3. [Redis and Caching](#redis-and-caching)
4. [Celery Configuration](#celery-configuration)
5. [Security and Encryption](#security-and-encryption)
6. [External Services](#external-services)
7. [Logging and Monitoring](#logging-and-monitoring)
8. [Email Configuration](#email-configuration)
9. [Application Settings](#application-settings)
10. [Feature Flags](#feature-flags)

---

## Core Django Settings

### SECRET_KEY
- **Required**: Yes
- **Type**: String
- **Description**: Django secret key for cryptographic signing
- **Example**: `django-insecure-your-secret-key-here`
- **Production**: Must be unique, random, and kept secret
- **Generate**: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

### DEBUG
- **Required**: Yes
- **Type**: Boolean
- **Default**: `False`
- **Description**: Enable Django debug mode
- **Values**: `True` or `False`
- **Production**: MUST be `False`
- **Warning**: Never enable in production - exposes sensitive information

### ALLOWED_HOSTS
- **Required**: Yes (in production)
- **Type**: Comma-separated list
- **Default**: Empty list
- **Description**: List of host/domain names that Django can serve
- **Example**: `api.yourdomain.com,yourdomain.com,localhost`
- **Production**: Must include all domains serving the application
- **Development**: Can use `*` or `localhost,127.0.0.1`

---

## Database Configuration

### DATABASE_URL
- **Required**: Yes
- **Type**: Database URL string
- **Description**: Complete database connection string
- **Format**: `postgresql://user:password@host:port/database`
- **Example**: `postgresql://tulia_user:tulia_pass@localhost:5432/tulia_db`
- **Development**: Can use SQLite: `sqlite:///db.sqlite3`
- **Production**: Must use PostgreSQL 15+
- **Note**: Supports connection pooling and SSL parameters

### DB_CONN_MAX_AGE
- **Required**: No
- **Type**: Integer (seconds)
- **Default**: `600` (10 minutes)
- **Description**: Database connection lifetime for connection pooling
- **Example**: `600`
- **Range**: `0` (no pooling) to `3600` (1 hour)
- **Production**: Recommended `600` for optimal performance

### POSTGRES_DB
- **Required**: Yes (for Docker)
- **Type**: String
- **Default**: `tulia_db`
- **Description**: PostgreSQL database name
- **Example**: `tulia_db`

### POSTGRES_USER
- **Required**: Yes (for Docker)
- **Type**: String
- **Default**: `tulia_user`
- **Description**: PostgreSQL username
- **Example**: `tulia_user`

### POSTGRES_PASSWORD
- **Required**: Yes (for Docker)
- **Type**: String
- **Default**: `tulia_pass`
- **Description**: PostgreSQL password
- **Example**: `tulia_pass`
- **Production**: Use strong, randomly generated password

---

## Redis and Caching

### REDIS_URL
- **Required**: Yes
- **Type**: Redis URL string
- **Description**: Redis connection URL for caching
- **Format**: `redis://host:port/db`
- **Example**: `redis://localhost:6379/0`
- **With Auth**: `redis://:password@localhost:6379/0`
- **SSL**: `rediss://localhost:6380/0`
- **Production**: Consider using separate Redis instances for cache, broker, and results

### CELERY_BROKER_URL
- **Required**: Yes
- **Type**: Redis URL string
- **Description**: Celery message broker URL
- **Format**: `redis://host:port/db`
- **Example**: `redis://localhost:6379/1`
- **Note**: Use different database number than REDIS_URL

### CELERY_RESULT_BACKEND
- **Required**: Yes
- **Type**: Redis URL string
- **Description**: Celery result backend URL
- **Format**: `redis://host:port/db`
- **Example**: `redis://localhost:6379/2`
- **Note**: Use different database number than REDIS_URL and CELERY_BROKER_URL

---

## Celery Configuration

All Celery configuration is managed through the above Redis URLs and Django settings. Additional Celery settings are configured in `config/settings.py`:

- **CELERY_TASK_TIME_LIMIT**: 30 minutes (hard limit)
- **CELERY_TASK_SOFT_TIME_LIMIT**: 25 minutes (soft limit)
- **CELERY_TASK_TRACK_STARTED**: Enabled
- **CELERY_TASK_SERIALIZER**: JSON
- **CELERY_RESULT_SERIALIZER**: JSON

Queue configuration:
- `default`: General tasks
- `integrations`: WooCommerce/Shopify sync
- `analytics`: Analytics rollup
- `messaging`: Message sending
- `bot`: Intent processing

---

## Security and Encryption

### ENCRYPTION_KEY
- **Required**: Yes
- **Type**: Base64-encoded string (32 bytes)
- **Description**: AES-256 encryption key for PII data
- **Example**: `your-base64-encoded-32-byte-key-here`
- **Generate**: `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode('utf-8'))"`
- **Production**: MUST be unique and kept secret
- **Warning**: Changing this key will make existing encrypted data unreadable
- **Backup**: Store securely in secrets management system

### RATE_LIMIT_ENABLED
- **Required**: No
- **Type**: Boolean
- **Default**: `True`
- **Description**: Enable rate limiting middleware
- **Values**: `True` or `False`
- **Production**: Should be `True`
- **Development**: Can be `False` for testing

---

## External Services

### OPENAI_API_KEY
- **Required**: Yes (if using OpenAI)
- **Type**: String
- **Description**: OpenAI API key for intent classification
- **Format**: `sk-...`
- **Example**: `sk-proj-abc123...`
- **Get Key**: https://platform.openai.com/api-keys
- **Note**: Either OPENAI_API_KEY or ANTHROPIC_API_KEY required

### ANTHROPIC_API_KEY
- **Required**: Yes (if using Claude)
- **Type**: String
- **Description**: Anthropic Claude API key for intent classification
- **Format**: `sk-ant-...`
- **Example**: `sk-ant-api03-abc123...`
- **Get Key**: https://console.anthropic.com/
- **Note**: Either OPENAI_API_KEY or ANTHROPIC_API_KEY required

### SENTRY_DSN
- **Required**: No (highly recommended for production)
- **Type**: String
- **Description**: Sentry Data Source Name for error tracking
- **Format**: `https://[key]@[organization].ingest.sentry.io/[project]`
- **Example**: `https://abc123@o123456.ingest.sentry.io/7890123`
- **Get DSN**: https://sentry.io/settings/projects/
- **Production**: Strongly recommended for error monitoring

### SENTRY_ENVIRONMENT
- **Required**: No
- **Type**: String
- **Default**: `development`
- **Description**: Environment name for Sentry
- **Values**: `development`, `staging`, `production`
- **Example**: `production`

### SENTRY_RELEASE
- **Required**: No
- **Type**: String
- **Description**: Release version for Sentry tracking
- **Example**: `1.0.0`, `v2.3.1`, `abc123def`
- **Note**: Helps track which version introduced errors

---

## Logging and Monitoring

### LOG_LEVEL
- **Required**: No
- **Type**: String
- **Default**: `INFO`
- **Description**: Minimum log level to output
- **Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Development**: `DEBUG` or `INFO`
- **Production**: `INFO` or `WARNING`

### JSON_LOGS
- **Required**: No
- **Type**: Boolean
- **Default**: `False`
- **Description**: Output logs in JSON format
- **Values**: `True` or `False`
- **Development**: `False` (human-readable)
- **Production**: `True` (machine-parseable)
- **Note**: JSON logs are better for log aggregation systems

---

## Email Configuration

### EMAIL_BACKEND
- **Required**: No
- **Type**: String
- **Default**: `django.core.mail.backends.console.EmailBackend`
- **Description**: Django email backend to use
- **Values**:
  - `django.core.mail.backends.console.EmailBackend` (development)
  - `django.core.mail.backends.smtp.EmailBackend` (production)
  - `django.core.mail.backends.dummy.EmailBackend` (testing)
- **Production**: Use SMTP backend

### EMAIL_HOST
- **Required**: Yes (if using SMTP)
- **Type**: String
- **Description**: SMTP server hostname
- **Example**: `smtp.sendgrid.net`, `smtp.gmail.com`, `smtp.mailgun.org`

### EMAIL_PORT
- **Required**: Yes (if using SMTP)
- **Type**: Integer
- **Default**: `587`
- **Description**: SMTP server port
- **Values**: `25`, `465` (SSL), `587` (TLS)
- **Recommended**: `587` with TLS

### EMAIL_USE_TLS
- **Required**: No
- **Type**: Boolean
- **Default**: `True`
- **Description**: Use TLS encryption for SMTP
- **Values**: `True` or `False`
- **Production**: Should be `True`

### EMAIL_HOST_USER
- **Required**: Yes (if using SMTP)
- **Type**: String
- **Description**: SMTP authentication username
- **Example**: `apikey` (SendGrid), `your-email@gmail.com`

### EMAIL_HOST_PASSWORD
- **Required**: Yes (if using SMTP)
- **Type**: String
- **Description**: SMTP authentication password or API key
- **Example**: `your-sendgrid-api-key`
- **Security**: Keep secret, use environment variables

### DEFAULT_FROM_EMAIL
- **Required**: No
- **Type**: String
- **Default**: `noreply@tulia.ai`
- **Description**: Default sender email address
- **Example**: `noreply@yourdomain.com`
- **Format**: Must be valid email address

---

## Application Settings

### FRONTEND_URL
- **Required**: Yes (for tenant onboarding)
- **Type**: String
- **Default**: `http://localhost:3000`
- **Description**: Frontend application URL for CORS and email links (verification, password reset)
- **Example**: `https://app.yourdomain.com`
- **Production**: Must be HTTPS URL
- **Note**: Used to generate links in verification and password reset emails

### DEFAULT_TRIAL_DAYS
- **Required**: No
- **Type**: Integer
- **Default**: `14`
- **Description**: Default free trial duration in days for new tenant registrations
- **Example**: `14`, `30`, `7`
- **Range**: `1` to `365`

### JWT_SECRET_KEY
- **Required**: No
- **Type**: String
- **Default**: Uses `SECRET_KEY` if not set
- **Description**: Secret key for JWT token signing (tenant onboarding authentication)
- **Example**: Leave empty to use Django's SECRET_KEY
- **Production**: Recommended to use same as SECRET_KEY for simplicity
- **Note**: If set, must be kept secret and never changed (invalidates all tokens)

### JWT_ALGORITHM
- **Required**: No
- **Type**: String
- **Default**: `HS256`
- **Description**: Algorithm for JWT token signing
- **Values**: `HS256`, `HS384`, `HS512`
- **Recommended**: `HS256` (HMAC with SHA-256)

### JWT_EXPIRATION_HOURS
- **Required**: No
- **Type**: Integer
- **Default**: `24`
- **Description**: JWT access token expiration time in hours
- **Example**: `24` (1 day), `1` (1 hour), `168` (7 days)
- **Range**: `1` to `720` (30 days)
- **Recommended**: `24` for good balance of security and UX

### JWT_REFRESH_EXPIRATION_DAYS
- **Required**: No
- **Type**: Integer
- **Default**: `7`
- **Description**: JWT refresh token expiration time in days
- **Example**: `7`, `14`, `30`
- **Range**: `1` to `90`
- **Recommended**: `7` for good balance of security and UX

### CORS_ALLOWED_ORIGINS
- **Required**: No (if CORS_ALLOW_ALL_ORIGINS is False)
- **Type**: Comma-separated list
- **Description**: Allowed origins for CORS requests
- **Example**: `https://app.yourdomain.com,https://admin.yourdomain.com`
- **Development**: Can be empty if CORS_ALLOW_ALL_ORIGINS=True
- **Production**: Must list all allowed origins

---

## Feature Flags

### RBAC_ADMIN_CAN_APPROVE
- **Required**: No
- **Type**: Boolean
- **Default**: `False`
- **Description**: Allow Admin role to approve withdrawals
- **Values**: `True` or `False`
- **Note**: If False, only Owner can approve withdrawals (four-eyes)

---

## Per-Tenant Configuration

The following credentials are **NOT** stored in environment variables. They are stored per-tenant in the `TenantSettings` model and configured through the admin interface or API:

### Twilio Configuration (Per Tenant)
- `twilio_sid`: Twilio Account SID
- `twilio_token`: Twilio Auth Token
- `whatsapp_number`: Twilio WhatsApp number
- `webhook_secret`: Webhook signature verification secret

### WooCommerce Configuration (Per Tenant)
- `woo_store_url`: WooCommerce store URL
- `woo_consumer_key`: WooCommerce API consumer key
- `woo_consumer_secret`: WooCommerce API consumer secret

### Shopify Configuration (Per Tenant)
- `shopify_shop_domain`: Shopify shop domain
- `shopify_access_token`: Shopify Admin API access token

**See**: `apps/tenants/SETTINGS_QUICK_REFERENCE.md` for details on managing tenant settings.

---

## Environment-Specific Examples

### Development (.env)

```bash
SECRET_KEY=django-insecure-dev-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=sqlite:///db.sqlite3
DB_CONN_MAX_AGE=0

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

ENCRYPTION_KEY=dev-key-base64-encoded-32-bytes-here

OPENAI_API_KEY=your-dev-key

SENTRY_DSN=
SENTRY_ENVIRONMENT=development

RATE_LIMIT_ENABLED=False

LOG_LEVEL=DEBUG
JSON_LOGS=False

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

FRONTEND_URL=http://localhost:3000

DEFAULT_TRIAL_DAYS=14

# JWT Authentication (Tenant Onboarding)
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
JWT_REFRESH_EXPIRATION_DAYS=7

# Stripe (Optional - for payment methods)
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
```

### Staging (.env)

```bash
SECRET_KEY=your-unique-staging-secret-key
DEBUG=False
ALLOWED_HOSTS=staging-api.yourdomain.com

DATABASE_URL=postgresql://tulia_user:strong_password@staging-db.internal:5432/tulia_staging
DB_CONN_MAX_AGE=600

REDIS_URL=redis://staging-redis.internal:6379/0
CELERY_BROKER_URL=redis://staging-redis.internal:6379/1
CELERY_RESULT_BACKEND=redis://staging-redis.internal:6379/2

ENCRYPTION_KEY=staging-unique-base64-encoded-32-bytes

OPENAI_API_KEY=sk-your-staging-key

SENTRY_DSN=https://abc@o123.ingest.sentry.io/456
SENTRY_ENVIRONMENT=staging
SENTRY_RELEASE=v1.2.3-staging

RATE_LIMIT_ENABLED=True

LOG_LEVEL=INFO
JSON_LOGS=True

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply-staging@yourdomain.com

FRONTEND_URL=https://staging-app.yourdomain.com

DEFAULT_TRIAL_DAYS=14

# JWT Authentication
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
JWT_REFRESH_EXPIRATION_DAYS=7

# Stripe
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here

CORS_ALLOWED_ORIGINS=https://staging-app.yourdomain.com
```

### Production (.env)

```bash
SECRET_KEY=your-unique-production-secret-key-keep-secret
DEBUG=False
ALLOWED_HOSTS=api.yourdomain.com,yourdomain.com

DATABASE_URL=postgresql://tulia_user:very_strong_password@prod-db.internal:5432/tulia_prod
DB_CONN_MAX_AGE=600

REDIS_URL=redis://:redis_password@prod-redis.internal:6379/0
CELERY_BROKER_URL=redis://:redis_password@prod-redis.internal:6379/1
CELERY_RESULT_BACKEND=redis://:redis_password@prod-redis.internal:6379/2

ENCRYPTION_KEY=production-unique-base64-encoded-32-bytes-keep-secret

OPENAI_API_KEY=sk-your-production-key

SENTRY_DSN=https://xyz@o789.ingest.sentry.io/012
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=v1.2.3

RATE_LIMIT_ENABLED=True

LOG_LEVEL=INFO
JSON_LOGS=True

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-production-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

FRONTEND_URL=https://app.yourdomain.com

DEFAULT_TRIAL_DAYS=14

# JWT Authentication
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
JWT_REFRESH_EXPIRATION_DAYS=7

# Stripe
STRIPE_SECRET_KEY=sk_live_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_key_here

CORS_ALLOWED_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
```

---

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use different keys** for each environment
3. **Rotate secrets regularly** (every 90 days)
4. **Use secrets management** systems in production (AWS Secrets Manager, HashiCorp Vault, etc.)
5. **Restrict access** to environment variables
6. **Audit secret usage** regularly
7. **Use strong passwords** for all services
8. **Enable encryption** for data in transit and at rest

---

## Validation

To validate your environment configuration:

```bash
# Check for missing required variables
python manage.py check

# Test database connection
python manage.py dbshell

# Test Redis connection
python -c "from django.core.cache import cache; cache.set('test', 'ok'); print(cache.get('test'))"

# Test Celery connection
celery -A config inspect ping

# Test email configuration
python manage.py sendtestemail your-email@example.com

# Verify all settings
python manage.py diffsettings
```

---

## Troubleshooting

### Missing Required Variables

**Error**: `ImproperlyConfigured: Set the SECRET_KEY environment variable`

**Solution**: Ensure all required variables are set in your `.env` file

### Invalid Database URL

**Error**: `OperationalError: could not connect to server`

**Solution**: Verify DATABASE_URL format and credentials

### Redis Connection Failed

**Error**: `ConnectionError: Error connecting to Redis`

**Solution**: Check REDIS_URL and ensure Redis is running

### Encryption Key Issues

**Error**: `ValueError: Fernet key must be 32 url-safe base64-encoded bytes`

**Solution**: Generate a new key with the provided command

---

## Additional Resources

- **Django Settings**: https://docs.djangoproject.com/en/4.2/ref/settings/
- **django-environ**: https://django-environ.readthedocs.io/
- **Celery Configuration**: https://docs.celeryproject.org/en/stable/userguide/configuration.html
- **Sentry Django**: https://docs.sentry.io/platforms/python/guides/django/

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
