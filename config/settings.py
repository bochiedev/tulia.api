"""
Django settings for Tulia AI WhatsApp Commerce Platform.
"""
import os
from pathlib import Path
import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from kombu import Queue, Exchange

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    DB_CONN_MAX_AGE=(int, 600),
    RATE_LIMIT_ENABLED=(bool, True),
    JSON_LOGS=(bool, False),
    LOG_LEVEL=(str, 'INFO'),
)

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Proxy/ngrok support for correct URL scheme detection
# Required for Twilio webhook signature verification
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'django_ratelimit',
    
    # Tulia apps
    'apps.core',
    'apps.tenants',
    'apps.rbac',
    'apps.messaging',
    'apps.catalog',
    'apps.orders',
    'apps.services',
    'apps.analytics',
    'apps.integrations',
    'apps.bot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom middleware
    'apps.tenants.middleware.RequestIDMiddleware',
    'apps.tenants.middleware.TenantContextMiddleware',
    'apps.tenants.middleware.WebhookSubscriptionMiddleware',
    'apps.core.cors.TenantCORSMiddleware',
    'apps.core.rate_limiting.RateLimitMiddleware',
]

# Add query logging middleware in development
if DEBUG:
    MIDDLEWARE.append('apps.core.query_logging.QueryLoggingMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL'),
}
DATABASES['default']['CONN_MAX_AGE'] = env('DB_CONN_MAX_AGE')

# Configure based on database engine
if 'postgresql' in DATABASES['default']['ENGINE']:
    DATABASES['default']['OPTIONS'] = {
        'connect_timeout': 10,
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
# Use our custom User model from apps.rbac for authentication
# This model supports multi-tenant access and is compatible with Django admin
AUTH_USER_MODEL = 'rbac.User'

# Authentication Backends
# Use our custom email-based authentication backend
AUTHENTICATION_BACKENDS = [
    'apps.rbac.backends.EmailAuthBackend',
]

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.core.authentication.MiddlewareAuthentication',  # Use user from TenantContextMiddleware
    ],
    'DEFAULT_PERMISSION_CLASSES': [],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# DRF Spectacular (OpenAPI)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Tulia AI WhatsApp Commerce API',
    'DESCRIPTION': '''
Multi-tenant WhatsApp commerce and services platform with comprehensive RBAC.

## Authentication

All API requests require JWT authentication:
- `Authorization: Bearer <token>` - JWT token obtained from `/v1/auth/login` or `/v1/auth/register`
- `X-TENANT-ID`: UUID of the tenant context (required for tenant-scoped operations)

**Note:** Webhooks are public endpoints verified by signature, not by JWT tokens.

## Rate Limiting

Authentication endpoints are rate limited to prevent abuse:

| Endpoint | Rate Limit | Key Type |
|----------|-----------|----------|
| `POST /v1/auth/register` | 3/hour | IP address |
| `POST /v1/auth/login` | 5/min per IP, 10/hour per email | IP + Email |
| `POST /v1/auth/verify-email` | 10/hour | IP address |
| `POST /v1/auth/forgot-password` | 3/hour | IP address |
| `POST /v1/auth/reset-password` | 5/hour | IP address |

When rate limit is exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

See the [Rate Limiting Guide](/docs/RATE_LIMITING.md) for complete documentation.

## Authorization (RBAC)

The platform implements Role-Based Access Control (RBAC) with the following components:

### Permissions
Granular capabilities identified by codes (e.g., `catalog:view`, `finance:withdraw:approve`).
See the `/v1/permissions` endpoint for the complete list.

### Roles
Collections of permissions that can be assigned to users. Each tenant has default roles:
- **Owner**: All permissions
- **Admin**: All permissions except `finance:withdraw:approve`
- **Finance Admin**: `analytics:view`, `finance:*`, `orders:view`
- **Catalog Manager**: `analytics:view`, `catalog:*`, `services:*`, `availability:edit`
- **Support Lead**: `conversations:view`, `handoff:perform`, `orders:view`, `appointments:view`
- **Analyst**: `analytics:view`, `catalog:view`, `services:view`, `orders:view`, `appointments:view`

### Scopes
The effective set of permission codes a user has for a specific tenant, resolved from:
1. Roles assigned to the user
2. User-specific permission overrides (grants or denies)

Deny overrides always take precedence over role grants.

### Four-Eyes Approval
Sensitive operations like financial withdrawals require two different users:
- One user initiates the action (`finance:withdraw:initiate`)
- A different user approves it (`finance:withdraw:approve`)

## Multi-Tenant Isolation

All data is strictly isolated by tenant. Users can be members of multiple tenants with different roles in each.
The `X-TENANT-ID` header determines which tenant context is active for the request.

## Canonical Permissions

| Code | Description | Category |
|------|-------------|----------|
| `catalog:view` | View products and catalog | Catalog |
| `catalog:edit` | Create, update, delete products | Catalog |
| `services:view` | View services | Services |
| `services:edit` | Create, update, delete services | Services |
| `availability:edit` | Manage service availability windows | Services |
| `conversations:view` | View customer conversations | Messaging |
| `handoff:perform` | Perform human handoff | Messaging |
| `orders:view` | View orders | Orders |
| `orders:edit` | Create, update orders | Orders |
| `appointments:view` | View appointments | Appointments |
| `appointments:edit` | Create, update, cancel appointments | Appointments |
| `analytics:view` | View analytics and reports | Analytics |
| `finance:view` | View wallet and transactions | Finance |
| `finance:withdraw:initiate` | Initiate withdrawal requests | Finance |
| `finance:withdraw:approve` | Approve withdrawal requests | Finance |
| `finance:reconcile` | Perform financial reconciliation | Finance |
| `integrations:manage` | Manage external integrations | Integrations |
| `users:manage` | Invite users, assign roles, manage permissions | Users |

## Example Workflows

### Login and Get JWT Token
```bash
# Login to get JWT token
curl -X POST https://api.tulia.ai/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "user@example.com",
    "password": "your-password"
  }'
# Returns: {"token": "eyJ...", "user": {...}}

# Use the token in subsequent requests
export TOKEN="eyJ..."
```

### Invite a User and Assign Roles
```bash
# 1. Invite user (requires users:manage scope)
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/invite \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "newuser@example.com",
    "role_ids": ["role-uuid-1", "role-uuid-2"]
  }'

# 2. User accepts invitation and logs in

# 3. Assign additional roles
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/{user_id}/roles \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "role_ids": ["role-uuid-3"]
  }'
```

### Grant User-Specific Permission Override
```bash
# Grant a specific permission to a user (overrides role permissions)
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "permission_code": "finance:reconcile",
    "granted": true,
    "reason": "Temporary access for Q4 audit"
  }'

# Deny a permission (even if granted by role)
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "permission_code": "catalog:edit",
    "granted": false,
    "reason": "Suspended pending investigation"
  }'
```

### Four-Eyes Withdrawal Approval
```bash
# 1. User A initiates withdrawal (requires finance:withdraw:initiate)
curl -X POST https://api.tulia.ai/v1/wallet/withdraw \\
  -H "Authorization: Bearer $TOKEN_USER_A" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "destination": "bank_account_123"
  }'
# Returns: {"transaction_id": "txn-uuid", "status": "pending_approval"}

# 2. User B approves withdrawal (requires finance:withdraw:approve, must be different user)
curl -X POST https://api.tulia.ai/v1/wallet/withdrawals/{transaction_id}/approve \\
  -H "Authorization: Bearer $TOKEN_USER_B" \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "notes": "Approved for monthly payout"
  }'
# Returns: {"transaction_id": "txn-uuid", "status": "approved"}

# If User A tries to approve their own withdrawal:
# Returns: 409 Conflict - "Four-eyes validation failed: initiator and approver must be different users"
```
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/v1/',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
    },
    'SECURITY': [
        {
            'JWTAuth': []
        }
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'JWTAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'JWT token obtained from /v1/auth/login or /v1/auth/register. Include as: Authorization: Bearer <token>. For tenant-scoped operations, also include X-TENANT-ID header.',
            }
        }
    },
    'SERVERS': [
        {
            'url': 'http://localhost:8000',
            'description': 'Development server'
        },
        {
            'url': 'https://api-staging.tulia.ai',
            'description': 'Staging server'
        },
        {
            'url': 'https://api.tulia.ai',
            'description': 'Production server'
        }
    ],
    'TAGS': [
        {'name': 'Authentication', 'description': 'User registration, login, and profile management'},
        {'name': 'Tenant Management', 'description': 'Tenant creation, listing, and member management'},
        {'name': 'Settings', 'description': 'General tenant settings and business configuration'},
        {'name': 'Settings - API Keys', 'description': 'API key generation and management'},
        {'name': 'Settings - Onboarding', 'description': 'Onboarding status tracking and completion'},
        {'name': 'Integrations', 'description': 'External service integrations (Twilio, WooCommerce, Shopify, OpenAI)'},
        {'name': 'Finance - Payment Methods', 'description': 'Payment method management for subscription billing'},
        {'name': 'Finance - Payout Methods', 'description': 'Payout method configuration for receiving earnings'},
        {'name': 'Finance - Wallet', 'description': 'Wallet balance and transaction management'},
        {'name': 'Finance - Withdrawals', 'description': 'Withdrawal requests with four-eyes approval'},
        {'name': 'RBAC - Memberships', 'description': 'User membership and invitation management'},
        {'name': 'RBAC - Roles', 'description': 'Role management and permission assignments'},
        {'name': 'RBAC - Permissions', 'description': 'Permission listing and user-specific overrides'},
        {'name': 'RBAC - Audit', 'description': 'Audit log viewing for compliance'},
        {'name': 'Catalog', 'description': 'Product catalog management'},
        {'name': 'Services', 'description': 'Bookable services and availability'},
        {'name': 'Orders', 'description': 'Order management'},
        {'name': 'Appointments', 'description': 'Appointment booking and management'},
        {'name': 'Messaging', 'description': 'WhatsApp messaging and conversations'},
        {'name': 'Analytics', 'description': 'Business analytics and reporting'},
        {'name': 'Test Utilities', 'description': 'Testing and development utilities (disable in production)'},
    ],
}

# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# HTTPS Enforcement (Production Only)
if not DEBUG:
    # Redirect all HTTP requests to HTTPS
    SECURE_SSL_REDIRECT = True
    
    # HSTS (HTTP Strict Transport Security)
    # Tells browsers to only access site via HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Secure Cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
else:
    # Development settings - no HTTPS enforcement
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Security Headers (All Environments)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME type sniffing
SECURE_BROWSER_XSS_FILTER = True    # Enable XSS filter in browsers
X_FRAME_OPTIONS = 'DENY'            # Prevent clickjacking

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only allow all origins in development

if not DEBUG:
    # Production: Require explicit CORS origins
    cors_origins = env.list('CORS_ALLOWED_ORIGINS', default=[])
    
    # Validate all origins are HTTPS
    for origin in cors_origins:
        if not origin.startswith('https://'):
            raise ValueError(
                f"CORS origin must use HTTPS in production: {origin}. "
                f"Update CORS_ALLOWED_ORIGINS in .env"
            )
    
    CORS_ALLOWED_ORIGINS = cors_origins
    
    # Require CORS origins to be configured
    if not CORS_ALLOWED_ORIGINS:
        import warnings
        warnings.warn(
            "CORS_ALLOWED_ORIGINS not configured. "
            "Set CORS_ALLOWED_ORIGINS in .env for production deployment."
        )
else:
    # Development: Allow configured origins or all if none specified
    CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

# CORS Headers
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-tenant-id',
    'x-tenant-api-key',
]

# Redis Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'tulia',
        'TIMEOUT': 300,
    }
}

# Celery Configuration
# CELERY_BROKER_URL = env('CELERY_BROKER_URL')
# CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
# CELERY_ACCEPT_CONTENT = ['json']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_TIMEZONE = TIME_ZONE
# CELERY_TASK_TRACK_STARTED = True
# CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
# CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
# CELERY_TASK_DEFAULT_QUEUE = 'default'
# CELERY_TASK_DEFAULT_PRIORITY = 5


# CELERY_DEFAULT_QUEUE = "default"
# CELERY_DEFAULT_EXCHANGE = "default"
# CELERY_DEFAULT_ROUTING_KEY = "default"

# CELERY_QUEUES = (
#     Queue("default", Exchange("default"), routing_key="default"),
#     Queue("integrations", Exchange("integrations"), routing_key="integrations"),
#     Queue("analytics", Exchange("analytics"), routing_key="analytics"),
#     Queue("messaging", Exchange("messaging"), routing_key="messaging"),
#     Queue("bot", Exchange("bot"), routing_key="bot"),
# )

# # Celery Queue Configuration
# CELERY_TASK_ROUTES = {
#     'apps.integrations.tasks.*': {'queue': 'integrations'},
#     'apps.analytics.tasks.*': {'queue': 'analytics'},
#     'apps.messaging.tasks.*': {'queue': 'messaging'},
#     'apps.bot.tasks.*': {'queue': 'bot'},
# }


# Broker / backend (ensure these env variables are set)
CELERY_BROKER_URL = env('CELERY_BROKER_URL')            # e.g. redis://localhost:6379/1
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')    # e.g. redis://localhost:6379/2

# Serialization / content
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Timezone & task limits
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60        # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60   # 25 minutes

# Default queue/routing keys (explicit)
# These keys line up with the Queue definitions below.
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'

# Optional: default priority for tasks (only used if you set/need priorities)
# Remove or adjust if you do not use priorities.
CELERY_TASK_DEFAULT_PRIORITY = 5

# Explicit Queue definitions (use kombu.Queue objects)
CELERY_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('integrations', Exchange('integrations'), routing_key='integrations'),
    Queue('analytics', Exchange('analytics'), routing_key='analytics'),
    Queue('messaging', Exchange('messaging'), routing_key='messaging'),
    Queue('bot', Exchange('bot'), routing_key='bot'),
)

# Routing: map tasks to logical queues
CELERY_TASK_ROUTES = {
    'apps.integrations.tasks.*': {'queue': 'integrations'},
    'apps.analytics.tasks.*':     {'queue': 'analytics'},
    'apps.messaging.tasks.*':     {'queue': 'messaging'},
    'apps.bot.tasks.*':           {'queue': 'bot'},
}

# Optional reliability / performance tuning (recommended for production)
# These are sensible defaults but tweak as needed:
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # avoid one worker prefetching many long tasks
CELERY_ACKS_LATE = True   


# Encryption
ENCRYPTION_KEY = env('ENCRYPTION_KEY', default=None)
# Support for key rotation - old keys used for decryption only
ENCRYPTION_OLD_KEYS = env.list('ENCRYPTION_OLD_KEYS', default=[])

# Rate Limiting
RATE_LIMIT_ENABLED = env('RATE_LIMIT_ENABLED')

# Django-ratelimit configuration
# Use Redis cache for distributed rate limiting
RATELIMIT_USE_CACHE = 'default'  # Use the default Redis cache
RATELIMIT_ENABLE = RATE_LIMIT_ENABLED  # Enable/disable rate limiting

# Use custom view for rate limit responses (returns 429 instead of 403)
RATELIMIT_VIEW = 'apps.core.exceptions.ratelimit_view'

# Logging Configuration
LOG_LEVEL = env('LOG_LEVEL')
JSON_LOGS = env('JSON_LOGS')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'apps.core.logging.JSONFormatter',
        },
        'verbose': {
            '()': 'apps.core.log_sanitizer.SanitizingFormatter',
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            '()': 'apps.core.log_sanitizer.SanitizingFormatter',
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'sanitize': {
            '()': 'apps.core.log_sanitizer.SanitizingFilter',
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'json' if JSON_LOGS else 'verbose',
            'filters': ['sanitize'],
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'tulia.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'json' if JSON_LOGS else 'verbose',
            'filters': ['sanitize'],
        },
        'security': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'json' if JSON_LOGS else 'verbose',
            'filters': ['sanitize'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'security': {
            'handlers': ['security', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Sentry Configuration
SENTRY_DSN = env('SENTRY_DSN', default=None)
SENTRY_ENVIRONMENT = env('SENTRY_ENVIRONMENT', default='development')
SENTRY_RELEASE = env('SENTRY_RELEASE', default=None)

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        environment=SENTRY_ENVIRONMENT,
        release=SENTRY_RELEASE,
        traces_sample_rate=0.1 if not DEBUG else 1.0,
        profiles_sample_rate=0.1 if not DEBUG else 0.0,
        send_default_pii=False,
        before_send=lambda event, hint: event if not DEBUG else None,
        # Attach stack traces to all messages
        attach_stacktrace=True,
        # Maximum breadcrumbs to capture
        max_breadcrumbs=50,
        # Enable performance monitoring
        enable_tracing=True,
    )

# OpenAI/Claude Configuration
OPENAI_API_KEY = env('OPENAI_API_KEY', default=None)
OPENAI_MODEL = env('OPENAI_MODEL', default='gpt-4o-mini')
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default=None)

# Subscription Configuration
DEFAULT_TRIAL_DAYS = env.int('DEFAULT_TRIAL_DAYS', default=14)

# Email Configuration
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='localhost')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@tulia.ai')

# Frontend Configuration
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')

# JWT Authentication Configuration
# SECURITY: JWT_SECRET_KEY must be set explicitly and must differ from SECRET_KEY
JWT_SECRET_KEY = env('JWT_SECRET_KEY')  # No default - must be set explicitly

# Validate JWT_SECRET_KEY length (must be at least 32 characters)
if len(JWT_SECRET_KEY) < 32:
    raise environ.ImproperlyConfigured(
        "JWT_SECRET_KEY must be at least 32 characters long for security. "
        "Current length: {}. Generate a strong key with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\"".format(len(JWT_SECRET_KEY))
    )

# Validate JWT_SECRET_KEY is different from SECRET_KEY
if JWT_SECRET_KEY == SECRET_KEY:
    raise environ.ImproperlyConfigured(
        "JWT_SECRET_KEY must be different from SECRET_KEY for security. "
        "Using the same key for both purposes weakens security. "
        "Generate a separate JWT key with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

# Validate JWT_SECRET_KEY entropy (must have sufficient randomness)
def _validate_jwt_key_entropy(key: str) -> None:
    """
    Validate that JWT_SECRET_KEY has sufficient entropy.
    
    Checks:
    - At least 16 unique characters (50% of minimum length)
    - Not all same character
    - Not simple repeating patterns
    """
    unique_chars = len(set(key))
    
    # Must have at least 16 unique characters for 32+ char key
    if unique_chars < 16:
        raise environ.ImproperlyConfigured(
            f"JWT_SECRET_KEY has insufficient entropy. "
            f"Found only {unique_chars} unique characters, need at least 16. "
            f"Generate a strong key with: "
            f"python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    
    # Check for simple repeating patterns (e.g., "aaaaaaa", "abababa")
    if len(key) >= 4:
        # Check if key is just one character repeated
        if key == key[0] * len(key):
            raise environ.ImproperlyConfigured(
                "JWT_SECRET_KEY is a repeating character pattern. "
                "Generate a strong key with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # Check for simple 2-character patterns (e.g., "ababab")
        if len(key) >= 6:
            pattern = key[:2]
            if key == pattern * (len(key) // len(pattern)) + pattern[:len(key) % len(pattern)]:
                raise environ.ImproperlyConfigured(
                    "JWT_SECRET_KEY is a simple repeating pattern. "
                    "Generate a strong key with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )

_validate_jwt_key_entropy(JWT_SECRET_KEY)

JWT_ALGORITHM = env('JWT_ALGORITHM', default='HS256')
JWT_EXPIRATION_HOURS = env.int('JWT_EXPIRATION_HOURS', default=24)

# Payment Gateway Configuration

# Stripe (International - Cards)
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default=None)
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default=None)
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default=None)

# Paystack (Africa - Card Payments)
PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY', default=None)
PAYSTACK_PUBLIC_KEY = env('PAYSTACK_PUBLIC_KEY', default=None)

# Pesapal (East Africa - Cards & Mobile Money)
PESAPAL_CONSUMER_KEY = env('PESAPAL_CONSUMER_KEY', default=None)
PESAPAL_CONSUMER_SECRET = env('PESAPAL_CONSUMER_SECRET', default=None)
PESAPAL_IPN_ID = env('PESAPAL_IPN_ID', default=None)
PESAPAL_API_URL = env('PESAPAL_API_URL', default='https://cybqa.pesapal.com/pesapalv3')

# M-Pesa (Kenya - Mobile Money)
MPESA_CONSUMER_KEY = env('MPESA_CONSUMER_KEY', default=None)
MPESA_CONSUMER_SECRET = env('MPESA_CONSUMER_SECRET', default=None)
MPESA_SHORTCODE = env('MPESA_SHORTCODE', default=None)
MPESA_PASSKEY = env('MPESA_PASSKEY', default=None)
MPESA_INITIATOR_NAME = env('MPESA_INITIATOR_NAME', default=None)
MPESA_INITIATOR_PASSWORD = env('MPESA_INITIATOR_PASSWORD', default=None)
MPESA_ENVIRONMENT = env('MPESA_ENVIRONMENT', default='sandbox')
MPESA_API_URL = env('MPESA_API_URL', default='https://sandbox.safaricom.co.ke')

# M-Pesa B2C (For Tenant Withdrawals)
MPESA_B2C_SHORTCODE = env('MPESA_B2C_SHORTCODE', default=None)
MPESA_B2C_SECURITY_CREDENTIAL = env('MPESA_B2C_SECURITY_CREDENTIAL', default=None)

# PesaLink (Bank-to-Bank Transfers)
PESALINK_API_KEY = env('PESALINK_API_KEY', default=None)
PESALINK_API_SECRET = env('PESALINK_API_SECRET', default=None)
PESALINK_INSTITUTION_CODE = env('PESALINK_INSTITUTION_CODE', default=None)
PESALINK_API_URL = env('PESALINK_API_URL', default='https://api.pesalink.co.ke')
