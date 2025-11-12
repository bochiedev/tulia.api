# Monitoring Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### 1. Configure Environment Variables

Add to your `.env` file:

```bash
# Logging
LOG_LEVEL=INFO
JSON_LOGS=True

# Sentry (get DSN from https://sentry.io)
SENTRY_DSN=https://your-key@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
```

### 2. That's It!

Monitoring is now active. All logs, errors, and tasks are automatically tracked.

## 📝 Common Use Cases

### Log a Message

```python
import logging

logger = logging.getLogger(__name__)

# Simple log
logger.info("Order created")

# With context
logger.info(
    "Order created",
    extra={'order_id': order_id, 'total': total}
)
```

### Track an Error

```python
from apps.core.sentry_utils import capture_exception

try:
    process_payment()
except Exception as e:
    capture_exception(e, order={'id': order_id})
```

### Add Debug Breadcrumbs

```python
from apps.core.sentry_utils import add_breadcrumb

add_breadcrumb(
    category="webhook",
    message="Received Twilio webhook",
    level="info",
    data={'from': phone_number}
)
```

### Create a Monitored Task

```python
from celery import shared_task
from apps.core.tasks import TenantTask

@shared_task(base=TenantTask, bind=True)
def my_task(self, tenant_id):
    # Automatic logging and error tracking!
    return result
```

## 🔍 View Logs and Errors

### Local Development
- **Console**: Logs appear in terminal
- **File**: Check `logs/tulia.log`

### Production
- **Sentry**: https://sentry.io (errors and performance)
- **Log Aggregation**: ELK, Datadog, CloudWatch, etc.

## 🛡️ Security Features

All sensitive data is automatically masked:
- Phone numbers: `+1234567890` → `+12*******`
- Emails: `user@example.com` → `u***@example.com`
- API keys: `sk_live_abc123` → `********`
- Credit cards: `4111 1111 1111 1111` → `************1111`

## 📊 What's Tracked Automatically

✅ All HTTP requests (with request_id)
✅ All Celery tasks (start, complete, fail, retry)
✅ All exceptions (with full context)
✅ User and tenant context
✅ Performance metrics
✅ Database queries (in DEBUG mode)

## 🎯 Best Practices

1. **Use appropriate log levels**:
   - `DEBUG`: Detailed info (dev only)
   - `INFO`: Normal operations
   - `WARNING`: Potential issues
   - `ERROR`: Failures
   - `CRITICAL`: System failures

2. **Add context to logs**:
   ```python
   logger.info("Action", extra={'key': 'value'})
   ```

3. **Use breadcrumbs for debugging**:
   ```python
   add_breadcrumb(category="flow", message="Step 1")
   ```

4. **Capture exceptions with context**:
   ```python
   capture_exception(e, context={'key': 'value'})
   ```

## 🔧 Troubleshooting

### Logs not appearing?
- Check `LOG_LEVEL` in `.env`
- Verify logger name matches module
- Check `logs/` directory exists

### Sentry not working?
- Verify `SENTRY_DSN` is correct
- Check `SENTRY_ENVIRONMENT` is set
- Ensure `DEBUG=False` in production

### PII leaking?
- Review `apps/core/logging.py`
- Add field names to `SENSITIVE_FIELDS`
- Report to security team

## 📚 Full Documentation

See `MONITORING.md` for complete documentation.

## 🆘 Support

- **Docs**: `MONITORING.md`
- **Tests**: `apps/core/tests/test_logging.py`
- **Utils**: `apps/core/sentry_utils.py`
- **Tasks**: `apps/core/tasks.py`

---

**Remember**: All monitoring is automatic. Just write your code normally and everything is tracked! 🎉
