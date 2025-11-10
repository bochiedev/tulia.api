"""
Django settings for Tulia AI WhatsApp Commerce Platform.
"""
import os
from pathlib import Path
import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

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
]

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
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# DRF Spectacular (OpenAPI)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Tulia AI WhatsApp Commerce API',
    'DESCRIPTION': '''
Multi-tenant WhatsApp commerce and services platform with comprehensive RBAC.

## Authentication

All API requests require authentication via headers:
- `X-TENANT-ID`: UUID of the tenant context
- `X-TENANT-API-KEY`: API key for the tenant

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

### Invite a User and Assign Roles
```bash
# 1. Invite user (requires users:manage scope)
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/invite \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "newuser@example.com",
    "role_ids": ["role-uuid-1", "role-uuid-2"]
  }'

# 2. User accepts invitation and logs in

# 3. Assign additional roles
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/{user_id}/roles \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "role_ids": ["role-uuid-3"]
  }'
```

### Grant User-Specific Permission Override
```bash
# Grant a specific permission to a user (overrides role permissions)
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "permission_code": "finance:reconcile",
    "granted": true,
    "reason": "Temporary access for Q4 audit"
  }'

# Deny a permission (even if granted by role)
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
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
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "destination": "bank_account_123"
  }'
# Returns: {"transaction_id": "txn-uuid", "status": "pending_approval"}

# 2. User B approves withdrawal (requires finance:withdraw:approve, must be different user)
curl -X POST https://api.tulia.ai/v1/wallet/withdrawals/{transaction_id}/approve \\
  -H "X-TENANT-ID: {tenant_id}" \\
  -H "X-TENANT-API-KEY: {api_key}" \\
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
            'TenantAuth': []
        }
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'TenantAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-TENANT-ID',
                'description': 'Tenant UUID for multi-tenant context. Must be accompanied by X-TENANT-API-KEY header.',
            }
        }
    },
    'TAGS': [
        {'name': 'RBAC - Memberships', 'description': 'User membership and invitation management'},
        {'name': 'RBAC - Roles', 'description': 'Role management and permission assignments'},
        {'name': 'RBAC - Permissions', 'description': 'Permission listing and user-specific overrides'},
        {'name': 'RBAC - Audit', 'description': 'Audit log viewing for compliance'},
        {'name': 'Finance - Wallet', 'description': 'Wallet balance and transaction management'},
        {'name': 'Finance - Withdrawals', 'description': 'Withdrawal requests with four-eyes approval'},
        {'name': 'Catalog', 'description': 'Product catalog management'},
        {'name': 'Services', 'description': 'Bookable services and availability'},
        {'name': 'Orders', 'description': 'Order management'},
        {'name': 'Appointments', 'description': 'Appointment booking and management'},
        {'name': 'Messaging', 'description': 'WhatsApp messaging and conversations'},
        {'name': 'Analytics', 'description': 'Business analytics and reporting'},
        {'name': 'Integrations', 'description': 'External service integrations'},
    ],
}

# CORS
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

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
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Celery Queue Configuration
CELERY_TASK_ROUTES = {
    'apps.integrations.tasks.*': {'queue': 'integrations'},
    'apps.analytics.tasks.*': {'queue': 'analytics'},
    'apps.messaging.tasks.*': {'queue': 'messaging'},
    'apps.bot.tasks.*': {'queue': 'bot'},
}

CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_PRIORITY = 5

# Encryption
ENCRYPTION_KEY = env('ENCRYPTION_KEY', default=None)

# Rate Limiting
RATE_LIMIT_ENABLED = env('RATE_LIMIT_ENABLED')

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
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
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
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'json' if JSON_LOGS else 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'tulia.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'json' if JSON_LOGS else 'verbose',
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
    },
}

# Sentry Configuration
SENTRY_DSN = env('SENTRY_DSN', default=None)
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        environment=env('SENTRY_ENVIRONMENT', default='development'),
        traces_sample_rate=0.1 if not DEBUG else 1.0,
        send_default_pii=False,
        before_send=lambda event, hint: event if not DEBUG else None,
    )

# OpenAI/Claude Configuration
OPENAI_API_KEY = env('OPENAI_API_KEY', default=None)
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
