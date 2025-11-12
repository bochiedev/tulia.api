# Monitoring and Observability Guide

This document describes the monitoring and observability features implemented in Tulia AI.

## Overview

Tulia AI implements comprehensive monitoring and observability through:

1. **Structured JSON Logging** - All logs are formatted as JSON with request tracing
2. **Sentry Error Tracking** - Automatic error capture with rich context
3. **Celery Task Logging** - Enhanced logging for background tasks
4. **PII Masking** - Automatic masking of sensitive data in logs

## Structured Logging

### Configuration

Logging is configured in `config/settings.py` with environment-based settings:

```bash
# .env
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
JSON_LOGS=True          # Enable JSON formatting (recommended for production)
```

### Log Format

All logs include:
- `timestamp`: ISO 8601 timestamp in UTC
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Logger name (e.g., `apps.messaging.services`)
- `message`: Log message (with PII masked)
- `module`: Python module name
- `function`: Function name
- `line`: Line number
- `request_id`: Unique request ID for tracing (if available)
- `tenant_id`: Tenant UUID (if available)
- `task_id`: Celery task ID (if available)
- `task_name`: Celery task name (if available)

Example JSON log:
```json
{
  "timestamp": "2025-11-12T10:30:45.123456Z",
  "level": "INFO",
  "logger": "apps.messaging.services",
  "message": "Message sent to customer +123***",
  "module": "messaging_service",
  "function": "send_message",
  "line": 145,
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tenant_id": "tenant-uuid-here",
  "customer_id": "customer-uuid-here"
}
```

### PII Masking

The logging system automatically masks sensitive data:

**Phone Numbers**: `+1234567890` → `+12*******`

**Email Addresses**: `user@example.com` → `u***@example.com`

**API Keys/Tokens**: `api_key: sk_live_abc123` → `api_key: ********`

**Credit Cards**: `4111 1111 1111 1111` → `************1111`

**Sensitive Fields**: Any field containing these keywords is masked:
- phone, phone_e164, phone_number, mobile
- email, email_address
- password, password_hash, passwd
- api_key, api_token, access_token, refresh_token, bearer_token
- secret, secret_key, webhook_secret
- twilio_sid, twilio_token, twilio_auth_token
- credit_card, card_number, cvv, ssn
- woo_consumer_key, woo_consumer_secret
- shopify_access_token

### Using Structured Logging

```python
import logging

logger = logging.getLogger(__name__)

# Basic logging
logger.info("Processing order")

# With extra context
logger.info(
    "Order created",
    extra={
        'order_id': str(order.id),
        'customer_id': str(customer.id),
        'total': float(order.total),
    }
)

# Error logging with exception
try:
    process_payment()
except Exception as e:
    logger.error(
        "Payment processing failed",
        extra={'order_id': str(order.id)},
        exc_info=True  # Include stack trace
    )
```

## Sentry Error Tracking

### Configuration

Configure Sentry in your `.env` file:

```bash
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production  # development, staging, production
SENTRY_RELEASE=1.0.0          # Optional: Your app version
```

### Features

1. **Automatic Error Capture** - All unhandled exceptions are sent to Sentry
2. **User Context** - User and tenant information attached to errors
3. **Breadcrumbs** - Detailed event trail leading to errors
4. **Performance Monitoring** - Transaction tracking for slow operations
5. **Release Tracking** - Track errors by deployment version

### Sentry Context

The system automatically sets context for errors:

**Tenant Context**:
```python
{
  "tenant": {
    "id": "tenant-uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "status": "active",
    "subscription_tier": "Growth"
  }
}
```

**User Context**:
```python
{
  "id": "user-uuid",
  "email": "user@example.com",
  "is_active": true,
  "tenant_id": "tenant-uuid",
  "roles": ["Admin", "Catalog Manager"]
}
```

**Customer Context**:
```python
{
  "customer": {
    "id": "customer-uuid",
    "tenant_id": "tenant-uuid",
    "has_name": true,
    "timezone": "America/New_York",
    "tags": ["vip", "repeat_customer"]
  }
}
```

### Using Sentry Utilities

```python
from apps.core.sentry_utils import (
    set_tenant_context,
    set_customer_context,
    set_user_context,
    add_breadcrumb,
    capture_exception,
    capture_message,
    start_transaction,
)

# Set context (usually done automatically by middleware)
set_tenant_context(tenant)
set_customer_context(customer)
set_user_context(user, tenant_user)

# Add breadcrumbs for debugging
add_breadcrumb(
    category="webhook",
    message="Received Twilio webhook",
    level="info",
    data={'from': '+1234567890', 'body': 'Hello'}
)

# Capture exceptions with context
try:
    process_order()
except Exception as e:
    capture_exception(
        e,
        order={'id': str(order.id), 'status': order.status}
    )

# Capture messages
capture_message(
    "Unusual activity detected",
    level="warning",
    activity={'type': 'bulk_orders', 'count': 100}
)

# Performance monitoring
transaction = start_transaction(
    name="webhook.twilio.process",
    op="webhook"
)
try:
    # Your code here
    transaction.set_status("ok")
finally:
    transaction.finish()
```

## Celery Task Logging

### Base Task Classes

Use the provided base task classes for enhanced logging:

```python
from apps.core.tasks import LoggedTask, TenantTask

# For general tasks
@app.task(base=LoggedTask, bind=True)
def my_task(self, arg1, arg2):
    # Task automatically logs start, completion, failures, and retries
    return result

# For tenant-scoped tasks
@app.task(base=TenantTask, bind=True)
def tenant_task(self, tenant_id, arg1):
    # Automatically sets tenant context in Sentry
    return result
```

### Task Logging Features

1. **Start Logging**: Logs task name, ID, and parameters
2. **Completion Logging**: Logs task ID and result summary
3. **Failure Logging**: Logs exception details and sends to Sentry
4. **Retry Logging**: Logs retry attempts with reason
5. **Performance Monitoring**: Creates Sentry transactions
6. **PII Sanitization**: Removes sensitive data from logs

### Task Logging Example

```python
from celery import shared_task
from apps.core.tasks import TenantTask
import logging

logger = logging.getLogger(__name__)

@shared_task(base=TenantTask, bind=True, max_retries=3)
def sync_products(self, tenant_id, store_url):
    """
    Sync products from external store.
    
    This task automatically:
    - Logs start with tenant_id and store_url
    - Sets tenant context in Sentry
    - Logs completion with result
    - Logs failures and sends to Sentry
    - Logs retry attempts
    """
    logger.info(f"Starting product sync for {store_url}")
    
    try:
        # Your sync logic here
        products = fetch_products(store_url)
        
        logger.info(
            f"Synced {len(products)} products",
            extra={'product_count': len(products)}
        )
        
        return {'synced': len(products)}
        
    except Exception as e:
        logger.error(f"Product sync failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

## Request Tracing

Every request gets a unique `request_id` that flows through:
- HTTP request/response headers (`X-Request-ID`)
- All log entries
- Sentry error reports
- Celery task logs

This enables end-to-end tracing of requests across the system.

### Using Request IDs

```python
# In views
def my_view(request):
    request_id = request.request_id
    logger.info("Processing request", extra={'request_id': request_id})

# In middleware
class MyMiddleware:
    def process_request(self, request):
        request_id = request.request_id
        # Use for tracing
```

## Log Levels

Use appropriate log levels:

- **DEBUG**: Detailed diagnostic information (disabled in production)
- **INFO**: General informational messages (normal operations)
- **WARNING**: Warning messages (potential issues)
- **ERROR**: Error messages (failures that need attention)
- **CRITICAL**: Critical errors (system failures)

Example:
```python
logger.debug("Detailed debug info")  # Development only
logger.info("Order created successfully")  # Normal operations
logger.warning("Rate limit approaching")  # Potential issues
logger.error("Payment failed", exc_info=True)  # Failures
logger.critical("Database connection lost")  # System failures
```

## Production Recommendations

1. **Enable JSON Logs**: Set `JSON_LOGS=True` for structured logging
2. **Set Log Level**: Use `LOG_LEVEL=INFO` (avoid DEBUG in production)
3. **Configure Sentry**: Set `SENTRY_DSN` and `SENTRY_ENVIRONMENT`
4. **Set Release**: Use `SENTRY_RELEASE` for deployment tracking
5. **Monitor Logs**: Use log aggregation tools (ELK, Datadog, CloudWatch)
6. **Set Alerts**: Configure Sentry alerts for critical errors
7. **Review Regularly**: Check Sentry dashboard and logs daily

## Troubleshooting

### Logs Not Appearing

1. Check `LOG_LEVEL` setting
2. Verify logger name matches module
3. Check log file permissions
4. Ensure logs directory exists

### Sentry Not Capturing Errors

1. Verify `SENTRY_DSN` is set correctly
2. Check `SENTRY_ENVIRONMENT` setting
3. Ensure `DEBUG=False` in production
4. Check Sentry project settings

### PII Leaking in Logs

1. Review `PIIMasker` patterns in `apps/core/logging.py`
2. Add sensitive field names to `SENSITIVE_FIELDS`
3. Use `extra` parameter carefully in log calls
4. Test with sample data before production

## Examples

### Complete Request Flow

```python
# 1. Request arrives with X-Request-ID header
# 2. Middleware sets tenant context
# 3. View processes request
def create_order(request):
    logger.info(
        "Creating order",
        extra={
            'request_id': request.request_id,
            'tenant_id': str(request.tenant.id),
        }
    )
    
    # 4. Add breadcrumb
    add_breadcrumb(
        category="order",
        message="Order validation started",
        level="info"
    )
    
    try:
        order = Order.objects.create(...)
        
        # 5. Log success
        logger.info(
            "Order created",
            extra={
                'order_id': str(order.id),
                'total': float(order.total),
            }
        )
        
        return JsonResponse({'order_id': str(order.id)})
        
    except Exception as e:
        # 6. Log error and send to Sentry
        logger.error(
            "Order creation failed",
            exc_info=True
        )
        capture_exception(e)
        return JsonResponse({'error': 'Failed'}, status=500)
```

### Celery Task with Monitoring

```python
@shared_task(base=TenantTask, bind=True, max_retries=3)
def process_campaign(self, tenant_id, campaign_id):
    """Process message campaign with full monitoring."""
    
    # Automatic: Task start logged
    # Automatic: Tenant context set in Sentry
    # Automatic: Sentry transaction started
    
    logger.info(f"Processing campaign {campaign_id}")
    
    try:
        campaign = MessageCampaign.objects.get(id=campaign_id)
        
        # Add breadcrumb
        add_breadcrumb(
            category="campaign",
            message=f"Campaign loaded: {campaign.name}",
            level="info",
            data={'target_count': campaign.target_count}
        )
        
        # Process campaign
        results = execute_campaign(campaign)
        
        # Log results
        logger.info(
            f"Campaign completed",
            extra={
                'campaign_id': campaign_id,
                'sent': results['sent'],
                'failed': results['failed'],
            }
        )
        
        # Automatic: Task completion logged
        # Automatic: Sentry transaction finished with "ok"
        
        return results
        
    except Exception as e:
        # Automatic: Error logged
        # Automatic: Sent to Sentry with context
        # Automatic: Retry logged if retrying
        # Automatic: Sentry transaction finished with "error"
        
        raise self.retry(exc=e, countdown=300)
```

## Monitoring Dashboard

Recommended metrics to monitor:

1. **Error Rate**: Errors per minute/hour
2. **Response Time**: P50, P95, P99 latencies
3. **Task Queue Length**: Celery queue depth
4. **Task Failure Rate**: Failed tasks per hour
5. **API Rate Limits**: Requests approaching limits
6. **Subscription Status**: Inactive/expired tenants
7. **Message Volume**: Messages sent per tenant
8. **Database Connections**: Connection pool usage

## Support

For issues or questions about monitoring:
1. Check Sentry dashboard for recent errors
2. Review application logs in `logs/tulia.log`
3. Check Celery worker logs
4. Contact DevOps team for infrastructure issues
