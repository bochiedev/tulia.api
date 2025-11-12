# Monitoring and Alerting Setup Guide

This guide covers the setup and configuration of monitoring and alerting for the Tulia AI WhatsApp Commerce Platform.

## Table of Contents

1. [Overview](#overview)
2. [Sentry Setup](#sentry-setup)
3. [Application Logging](#application-logging)
4. [Health Checks](#health-checks)
5. [Metrics Collection](#metrics-collection)
6. [Alerting Rules](#alerting-rules)
7. [Dashboard Setup](#dashboard-setup)
8. [Incident Response](#incident-response)

---

## Overview

The Tulia AI platform uses a multi-layered monitoring approach:

- **Error Tracking**: Sentry for exception monitoring and performance tracking
- **Application Logs**: Structured JSON logging to files and stdout
- **Health Checks**: HTTP endpoint for service health verification
- **Metrics**: Custom business and system metrics
- **Alerts**: Automated notifications for critical issues

### Monitoring Stack

```
┌─────────────────────────────────────────────────────────┐
│                   Application Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │   Web    │  │  Celery  │  │  Celery  │             │
│  │  Server  │  │  Worker  │  │   Beat   │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │             │             │                      │
│       └─────────────┴─────────────┘                     │
│                     │                                    │
└─────────────────────┼────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌────────┐   ┌─────────┐   ┌────────┐
   │ Sentry │   │  Logs   │   │ Health │
   │        │   │  (JSON) │   │ Checks │
   └────────┘   └─────────┘   └────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      ▼
              ┌──────────────┐
              │   Alerting   │
              │   (Email,    │
              │   Slack,     │
              │   PagerDuty) │
              └──────────────┘
```

---

## Sentry Setup

### 1. Create Sentry Project

1. Sign up at https://sentry.io
2. Create a new project for Django
3. Copy the DSN (Data Source Name)

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/7890123
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
```

### 3. Verify Sentry Integration

The Sentry SDK is already configured in `config/settings.py`. Test it:

```python
# Test Sentry integration
python manage.py shell

from sentry_sdk import capture_message, capture_exception

# Test message
capture_message("Test message from Tulia AI", level="info")

# Test exception
try:
    1 / 0
except Exception as e:
    capture_exception(e)
```

Check your Sentry dashboard to see the test events.

### 4. Sentry Features

#### Error Tracking

Automatically captures:
- Unhandled exceptions
- HTTP errors (4xx, 5xx)
- Database errors
- Celery task failures

#### Performance Monitoring

Tracks:
- Request duration
- Database query performance
- External API calls
- Celery task execution time

#### Release Tracking

Set `SENTRY_RELEASE` to track which version introduced errors:

```bash
# In CI/CD pipeline
export SENTRY_RELEASE=$(git rev-parse --short HEAD)

# Or use semantic versioning
export SENTRY_RELEASE=v1.2.3
```

#### User Context

Automatically includes:
- Tenant ID
- User ID
- Request ID
- IP address

#### Breadcrumbs

Sentry captures events leading to errors:
- HTTP requests
- Database queries
- Log messages
- User actions

### 5. Sentry Alerts

Configure alerts in Sentry dashboard:

1. **Critical Errors**:
   - Trigger: New error or regression
   - Action: Email + Slack notification
   - Frequency: Immediately

2. **High Error Rate**:
   - Trigger: >10 errors/minute
   - Action: PagerDuty alert
   - Frequency: Every 5 minutes

3. **Performance Degradation**:
   - Trigger: P95 response time >2s
   - Action: Slack notification
   - Frequency: Every 15 minutes

### 6. Sentry Best Practices

```python
# Add custom context
from sentry_sdk import set_context, set_tag

set_tag("tenant_id", str(tenant.id))
set_tag("subscription_tier", tenant.subscription_tier.name)

set_context("order", {
    "order_id": str(order.id),
    "total": float(order.total),
    "status": order.status,
})

# Capture custom events
from sentry_sdk import capture_message

capture_message(
    "Subscription payment failed",
    level="warning",
    extras={
        "tenant_id": str(tenant.id),
        "amount": float(subscription.amount),
        "attempt": payment_attempt,
    }
)

# Filter sensitive data
import sentry_sdk

def before_send(event, hint):
    # Remove sensitive data
    if 'request' in event:
        if 'headers' in event['request']:
            event['request']['headers'].pop('Authorization', None)
            event['request']['headers'].pop('X-TENANT-API-KEY', None)
    return event

sentry_sdk.init(
    dsn=SENTRY_DSN,
    before_send=before_send,
)
```

---

## Application Logging

### 1. Log Configuration

Logging is configured in `config/settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'apps.core.logging.JSONFormatter',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'json',  # Use 'verbose' for development
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/tulia.log',
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 2. Log Levels

Use appropriate log levels:

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: Detailed information for debugging
logger.debug(f"Processing message for tenant {tenant_id}")

# INFO: General informational messages
logger.info(f"Order {order_id} created successfully")

# WARNING: Warning messages for unexpected situations
logger.warning(f"Rate limit approaching for tenant {tenant_id}")

# ERROR: Error messages for failures
logger.error(f"Failed to send message: {error}", exc_info=True)

# CRITICAL: Critical issues requiring immediate attention
logger.critical(f"Database connection lost")
```

### 3. Structured Logging

Use structured logging for better searchability:

```python
logger.info(
    "Order created",
    extra={
        "tenant_id": str(tenant.id),
        "order_id": str(order.id),
        "customer_id": str(customer.id),
        "total": float(order.total),
        "currency": order.currency,
        "request_id": request.request_id,
    }
)
```

JSON output:
```json
{
  "timestamp": "2025-01-12T10:30:00.123Z",
  "level": "INFO",
  "message": "Order created",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_id": "789e0123-e89b-12d3-a456-426614174000",
  "customer_id": "456e7890-e89b-12d3-a456-426614174000",
  "total": 99.99,
  "currency": "USD",
  "request_id": "req_abc123"
}
```

### 4. Log Aggregation

#### Option 1: ELK Stack (Elasticsearch, Logstash, Kibana)

```yaml
# docker-compose.yml addition
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
  environment:
    - discovery.type=single-node
  ports:
    - "9200:9200"

logstash:
  image: docker.elastic.co/logstash/logstash:8.11.0
  volumes:
    - ./logstash/pipeline:/usr/share/logstash/pipeline
  depends_on:
    - elasticsearch

kibana:
  image: docker.elastic.co/kibana/kibana:8.11.0
  ports:
    - "5601:5601"
  depends_on:
    - elasticsearch
```

#### Option 2: Cloud Logging Services

- **Datadog**: https://www.datadoghq.com/
- **Loggly**: https://www.loggly.com/
- **Papertrail**: https://www.papertrail.com/
- **CloudWatch**: AWS CloudWatch Logs

### 5. Log Rotation

Logs are automatically rotated:

```python
# Configured in settings.py
'file': {
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': '/app/logs/tulia.log',
    'maxBytes': 10485760,  # 10 MB
    'backupCount': 5,  # Keep 5 backup files
}
```

Manual rotation with logrotate:

```bash
# /etc/logrotate.d/tulia-ai
/opt/tulia-ai/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 tulia tulia
    sharedscripts
    postrotate
        systemctl reload tulia-web
    endscript
}
```

---

## Health Checks

### 1. Health Check Endpoint

**Endpoint**: `GET /v1/health`

**Response** (Healthy):
```json
{
  "status": "healthy",
  "timestamp": "2025-01-12T10:30:00Z",
  "checks": {
    "database": "connected",
    "redis": "connected",
    "celery": "available"
  }
}
```

**Response** (Unhealthy):
```json
{
  "status": "unhealthy",
  "timestamp": "2025-01-12T10:30:00Z",
  "checks": {
    "database": "connected",
    "redis": "error: Connection refused",
    "celery": "unavailable"
  }
}
```

### 2. Health Check Script

```bash
#!/bin/bash
# /opt/tulia-ai/scripts/health_check.sh

HEALTH_URL="http://localhost:8000/v1/health"
TIMEOUT=10

# Make request
RESPONSE=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$HEALTH_URL")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

# Check status
if [ "$HTTP_CODE" -eq 200 ]; then
    STATUS=$(echo "$BODY" | jq -r '.status')
    if [ "$STATUS" = "healthy" ]; then
        echo "✓ Health check passed"
        exit 0
    else
        echo "✗ Health check failed: $STATUS"
        echo "$BODY" | jq '.'
        exit 1
    fi
else
    echo "✗ Health check failed with HTTP $HTTP_CODE"
    exit 1
fi
```

### 3. External Monitoring

#### UptimeRobot

1. Sign up at https://uptimerobot.com
2. Add HTTP(s) monitor
3. URL: `https://api.yourdomain.com/v1/health`
4. Interval: 5 minutes
5. Alert contacts: Email, Slack, SMS

#### Pingdom

1. Sign up at https://www.pingdom.com
2. Add Uptime Check
3. URL: `https://api.yourdomain.com/v1/health`
4. Check frequency: 1 minute
5. Alert when: Down for 2 minutes

### 4. Kubernetes Health Checks

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tulia-web
spec:
  template:
    spec:
      containers:
      - name: web
        image: tulia-ai:latest
        livenessProbe:
          httpGet:
            path: /v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
```

---

## Metrics Collection

### 1. Application Metrics

Track key business metrics:

```python
# apps/core/metrics.py
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

class MetricsCollector:
    @staticmethod
    def increment(metric_name, value=1, tags=None):
        """Increment a counter metric."""
        key = f"metrics:{metric_name}"
        if tags:
            key += f":{':'.join(f'{k}={v}' for k, v in tags.items())}"
        
        cache.incr(key, delta=value)
        
        logger.info(
            f"Metric incremented: {metric_name}",
            extra={
                "metric": metric_name,
                "value": value,
                "tags": tags,
            }
        )
    
    @staticmethod
    def gauge(metric_name, value, tags=None):
        """Set a gauge metric."""
        key = f"metrics:{metric_name}"
        if tags:
            key += f":{':'.join(f'{k}={v}' for k, v in tags.items())}"
        
        cache.set(key, value, timeout=3600)
        
        logger.info(
            f"Metric set: {metric_name}",
            extra={
                "metric": metric_name,
                "value": value,
                "tags": tags,
            }
        )

# Usage
from apps.core.metrics import MetricsCollector

# Increment counter
MetricsCollector.increment(
    "messages.sent",
    tags={"tenant_id": str(tenant.id), "type": "outbound"}
)

# Set gauge
MetricsCollector.gauge(
    "active_conversations",
    value=Conversation.objects.filter(status='open').count(),
    tags={"tenant_id": str(tenant.id)}
)
```

### 2. Key Metrics to Track

#### Application Metrics
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Active connections

#### Business Metrics
- Active tenants
- Messages sent/received
- Orders created
- Appointments booked
- Revenue generated
- Subscription conversions

#### System Metrics
- CPU usage
- Memory usage
- Disk usage
- Network I/O

#### Database Metrics
- Connection pool usage
- Query duration
- Slow queries (>1s)
- Database size

#### Redis Metrics
- Memory usage
- Hit rate
- Connected clients
- Evicted keys

#### Celery Metrics
- Queue length
- Task processing time
- Failed tasks
- Worker availability

### 3. Prometheus Integration (Optional)

```python
# requirements.txt addition
django-prometheus==2.3.1

# settings.py
INSTALLED_APPS = [
    'django_prometheus',
    # ... other apps
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ... other middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# urls.py
urlpatterns = [
    path('', include('django_prometheus.urls')),
    # ... other urls
]
```

Access metrics at: `http://localhost:8000/metrics`

---

## Alerting Rules

### 1. Critical Alerts (Immediate Response)

#### Health Check Failure
- **Condition**: Health endpoint returns 503 or times out
- **Action**: PagerDuty alert + Slack notification
- **Escalation**: After 5 minutes, call on-call engineer

#### Database Connection Failure
- **Condition**: Cannot connect to PostgreSQL
- **Action**: PagerDuty alert + Slack notification
- **Escalation**: Immediate

#### High Error Rate
- **Condition**: >5% of requests return 5xx errors
- **Action**: PagerDuty alert + Slack notification
- **Escalation**: After 10 minutes

#### Celery Workers Down
- **Condition**: No active Celery workers
- **Action**: PagerDuty alert + Slack notification
- **Escalation**: After 5 minutes

### 2. Warning Alerts (Monitor Closely)

#### High Response Time
- **Condition**: P95 response time >2 seconds
- **Action**: Slack notification
- **Frequency**: Every 15 minutes

#### Database Connection Pool High
- **Condition**: >80% of connection pool in use
- **Action**: Slack notification
- **Frequency**: Every 10 minutes

#### Redis Memory High
- **Condition**: >80% of Redis memory used
- **Action**: Slack notification
- **Frequency**: Every 10 minutes

#### Celery Queue Backlog
- **Condition**: >1000 tasks in queue
- **Action**: Slack notification
- **Frequency**: Every 15 minutes

#### Disk Space Low
- **Condition**: <20% disk space available
- **Action**: Email + Slack notification
- **Frequency**: Daily

### 3. Info Alerts (Awareness)

#### Deployment Completed
- **Condition**: New version deployed
- **Action**: Slack notification

#### Scheduled Task Completed
- **Condition**: Nightly analytics rollup finished
- **Action**: Slack notification (if failed)

#### Subscription Expiring
- **Condition**: Tenant subscription expires in 3 days
- **Action**: Email notification to tenant

### 4. Alert Configuration Examples

#### Slack Webhook

```python
# apps/core/alerts.py
import requests
import logging

logger = logging.getLogger(__name__)

def send_slack_alert(message, severity="info"):
    """Send alert to Slack."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured")
        return
    
    color = {
        "critical": "#FF0000",
        "warning": "#FFA500",
        "info": "#0000FF",
    }.get(severity, "#808080")
    
    payload = {
        "attachments": [{
            "color": color,
            "title": f"Tulia AI Alert - {severity.upper()}",
            "text": message,
            "footer": "Tulia AI Monitoring",
            "ts": int(time.time()),
        }]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")

# Usage
from apps.core.alerts import send_slack_alert

send_slack_alert(
    "Database connection pool at 85% capacity",
    severity="warning"
)
```

#### PagerDuty Integration

```python
# requirements.txt addition
pypd==1.1.0

# apps/core/alerts.py
import pypd

pypd.api_key = os.getenv("PAGERDUTY_API_KEY")

def trigger_pagerduty_alert(title, description, severity="error"):
    """Trigger PagerDuty incident."""
    try:
        pypd.EventV2.create(data={
            'routing_key': os.getenv("PAGERDUTY_ROUTING_KEY"),
            'event_action': 'trigger',
            'payload': {
                'summary': title,
                'severity': severity,
                'source': 'tulia-ai',
                'custom_details': {
                    'description': description,
                }
            }
        })
    except Exception as e:
        logger.error(f"Failed to trigger PagerDuty alert: {e}")
```

---

## Dashboard Setup

### 1. Grafana Dashboard

```yaml
# docker-compose.yml addition
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana_data:/var/lib/grafana
    - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
```

### 2. Dashboard Panels

#### System Overview
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (%)
- Active connections

#### Business Metrics
- Active tenants
- Messages sent (last 24h)
- Orders created (last 24h)
- Revenue (last 24h)

#### Infrastructure
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)
- Network I/O

#### Database
- Connection pool usage
- Query duration
- Slow queries
- Database size

#### Celery
- Queue length by queue
- Task processing time
- Failed tasks
- Active workers

---

## Incident Response

### 1. Incident Response Workflow

```
1. Alert Received
   ↓
2. Acknowledge Alert
   ↓
3. Assess Severity
   ↓
4. Investigate Root Cause
   ↓
5. Implement Fix or Mitigation
   ↓
6. Verify Resolution
   ↓
7. Document Incident
   ↓
8. Post-Mortem (if critical)
```

### 2. Runbooks

Create runbooks for common incidents:

#### Database Connection Issues

```markdown
# Runbook: Database Connection Issues

## Symptoms
- Health check failing
- 500 errors in application
- "OperationalError: could not connect to server"

## Investigation
1. Check PostgreSQL status: `systemctl status postgresql`
2. Check connection pool: `SELECT count(*) FROM pg_stat_activity;`
3. Check database logs: `tail -f /var/log/postgresql/postgresql-15-main.log`

## Resolution
1. Restart PostgreSQL: `systemctl restart postgresql`
2. If connection pool exhausted, restart application
3. If disk full, clear space and restart

## Prevention
- Monitor connection pool usage
- Set up alerts for high connection count
- Regular database maintenance
```

### 3. On-Call Rotation

Set up on-call rotation in PagerDuty:

1. Create escalation policy
2. Define on-call schedule
3. Configure alert routing
4. Test escalation flow

---

## Additional Resources

- **Sentry Documentation**: https://docs.sentry.io/
- **Django Logging**: https://docs.djangoproject.com/en/4.2/topics/logging/
- **Prometheus**: https://prometheus.io/docs/
- **Grafana**: https://grafana.com/docs/

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
