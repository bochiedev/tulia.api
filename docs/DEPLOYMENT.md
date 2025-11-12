# Tulia AI WhatsApp Commerce Platform - Deployment Guide

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Environment Configuration](#environment-configuration)
4. [Local Development Setup](#local-development-setup)
5. [Database Setup and Migrations](#database-setup-and-migrations)
6. [Production Deployment](#production-deployment)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Deployment Checklist](#deployment-checklist)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Tulia AI is a multi-tenant WhatsApp commerce and services platform built with Django, PostgreSQL, Redis, and Celery. This guide covers deployment for both local development and production environments.

### Architecture Components

- **Web Application**: Django + Django REST Framework
- **Database**: PostgreSQL 15+ with connection pooling
- **Cache & Queue**: Redis for caching and Celery message broker
- **Background Workers**: Celery workers for async tasks
- **Task Scheduler**: Celery Beat for scheduled tasks
- **Monitoring**: Sentry for error tracking and performance monitoring

---

## System Requirements

### Minimum Requirements

- **CPU**: 2 cores (4+ recommended for production)
- **RAM**: 4GB (8GB+ recommended for production)
- **Storage**: 20GB SSD (50GB+ for production)
- **OS**: Linux (Ubuntu 22.04 LTS recommended), macOS, or Windows with WSL2

### Software Dependencies

- **Python**: 3.12+
- **PostgreSQL**: 15+
- **Redis**: 7+
- **Docker**: 24+ (optional, for containerized deployment)
- **Docker Compose**: 2.20+ (optional)

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root based on `.env.example`:

```bash
# Copy the example file
cp .env.example .env
```

### Core Configuration

```bash
# Django Settings
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=False  # ALWAYS False in production
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com

# Database (PostgreSQL required for production)
DATABASE_URL=postgresql://tulia_user:tulia_pass@localhost:5432/tulia_db
DB_CONN_MAX_AGE=600

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### Security Configuration

```bash
# Encryption Key (CRITICAL - Generate securely)
# Generate with: python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode('utf-8'))"
ENCRYPTION_KEY=your-base64-encoded-32-byte-key-here

# Rate Limiting
RATE_LIMIT_ENABLED=True
```

### External Services

```bash
# AI/LLM for Intent Classification
OPENAI_API_KEY=sk-your-openai-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-claude-key-here

# Sentry Error Tracking (Highly Recommended)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0  # Set to your app version

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### Logging Configuration

```bash
# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
JSON_LOGS=True  # Enable JSON logging for production
```

### Application Configuration

```bash
# Frontend URL (for CORS and email links)
FRONTEND_URL=https://app.yourdomain.com

# Subscription
DEFAULT_TRIAL_DAYS=14

# CORS (comma-separated list)
CORS_ALLOWED_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
```

### Per-Tenant Configuration

**Note**: Twilio, WooCommerce, and Shopify credentials are stored per-tenant in the `TenantSettings` model, NOT in environment variables. These are configured through the admin interface or API after tenant creation.

---

## Local Development Setup

### Option 1: Docker Compose (Recommended)

The easiest way to get started is using Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/yourorg/tulia-ai.git
cd tulia-ai

# 2. Create and configure .env file
cp .env.example .env
# Edit .env with your configuration

# 3. Build and start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec web python manage.py migrate

# 5. Create superuser
docker-compose exec web python manage.py createsuperuser

# 6. Seed initial data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers

# 7. (Optional) Load demo data
docker-compose exec web python manage.py seed_demo_data

# 8. Access the application
# API: http://localhost:8000
# Swagger UI: http://localhost:8000/schema/swagger/
# Admin: http://localhost:8000/admin
```

### Option 2: Manual Setup

For development without Docker:

```bash
# 1. Clone the repository
git clone https://github.com/yourorg/tulia-ai.git
cd tulia-ai

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install and start PostgreSQL
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# macOS (with Homebrew):
brew install postgresql@15
brew services start postgresql@15

# 5. Create database
sudo -u postgres psql
CREATE DATABASE tulia_db;
CREATE USER tulia_user WITH PASSWORD 'tulia_pass';
ALTER ROLE tulia_user SET client_encoding TO 'utf8';
ALTER ROLE tulia_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE tulia_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE tulia_db TO tulia_user;
\q

# 6. Install and start Redis
# Ubuntu/Debian:
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS (with Homebrew):
brew install redis
brew services start redis

# 7. Configure environment
cp .env.example .env
# Edit .env with your local configuration

# 8. Run migrations
python manage.py migrate

# 9. Create superuser
python manage.py createsuperuser

# 10. Seed initial data
python manage.py seed_permissions
python manage.py seed_subscription_tiers

# 11. Start development server
python manage.py runserver

# 12. In separate terminals, start Celery workers
celery -A config worker -l info -Q default,integrations,analytics,messaging,bot
celery -A config beat -l info
```

### Verify Installation

```bash
# Check health endpoint
curl http://localhost:8000/v1/health

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "celery": "available"
}

# Access Swagger UI
open http://localhost:8000/schema/swagger/
```

---

## Database Setup and Migrations

### Initial Setup

```bash
# Run all migrations
python manage.py migrate

# Seed canonical permissions
python manage.py seed_permissions

# Seed subscription tiers
python manage.py seed_subscription_tiers

# Create default roles for all existing tenants
python manage.py seed_tenant_roles --all
```

### Creating Migrations

When you modify models:

```bash
# Create migration files
python manage.py makemigrations

# Review the migration
python manage.py sqlmigrate app_name migration_number

# Apply migrations
python manage.py migrate

# Verify migration status
python manage.py showmigrations
```

### Migration Best Practices

1. **Always review migrations** before applying to production
2. **Test migrations** on a staging environment first
3. **Backup database** before running migrations in production
4. **Use transactions** for data migrations
5. **Avoid destructive operations** without proper backups

### Database Backup and Restore

```bash
# Backup database
pg_dump -U tulia_user -h localhost tulia_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore database
psql -U tulia_user -h localhost tulia_db < backup_20250112_120000.sql

# Backup with Docker Compose
docker-compose exec db pg_dump -U tulia_user tulia_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore with Docker Compose
docker-compose exec -T db psql -U tulia_user tulia_db < backup_20250112_120000.sql
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] All environment variables configured correctly
- [ ] `DEBUG=False` in production
- [ ] `SECRET_KEY` is unique and secure
- [ ] `ENCRYPTION_KEY` is generated and stored securely
- [ ] Database backups configured
- [ ] SSL/TLS certificates installed
- [ ] Sentry DSN configured
- [ ] Email service configured
- [ ] CORS origins configured
- [ ] Rate limiting enabled
- [ ] Firewall rules configured
- [ ] Monitoring and alerting set up

### Deployment Options

#### Option 1: Docker Compose (Simple Production)

```bash
# 1. Clone repository on server
git clone https://github.com/yourorg/tulia-ai.git
cd tulia-ai

# 2. Configure production environment
cp .env.example .env
nano .env  # Edit with production values

# 3. Update docker-compose.yml for production
# - Remove volume mounts for code
# - Add restart policies
# - Configure resource limits

# 4. Build and start services
docker-compose -f docker-compose.prod.yml up -d

# 5. Run migrations
docker-compose exec web python manage.py migrate

# 6. Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# 7. Seed initial data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers
```

#### Option 2: Kubernetes (Scalable Production)

See `k8s/` directory for Kubernetes manifests (to be created separately).

#### Option 3: Platform-as-a-Service (Heroku, Railway, Render)

Most PaaS platforms support Django applications. Key considerations:

1. Use `Procfile` for process definitions
2. Configure buildpacks for Python
3. Set environment variables through platform UI
4. Use managed PostgreSQL and Redis add-ons
5. Configure worker dynos for Celery

### Web Server Configuration

#### Using Gunicorn (Recommended)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --threads 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

#### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/tulia-ai

upstream tulia_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Client body size (for file uploads)
    client_max_body_size 10M;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
    location / {
        proxy_pass http://tulia_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    location /static/ {
        alias /var/www/tulia-ai/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint (no auth required)
    location /v1/health {
        proxy_pass http://tulia_backend;
        access_log off;
    }
}
```

### Celery Workers Configuration

```bash
# Start Celery worker with multiple queues
celery -A config worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=default,integrations,analytics,messaging,bot \
  --max-tasks-per-child=1000 \
  --time-limit=1800 \
  --soft-time-limit=1500

# Start Celery Beat scheduler
celery -A config beat \
  --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Systemd Service Files

Create systemd service files for production:

**`/etc/systemd/system/tulia-web.service`**:
```ini
[Unit]
Description=Tulia AI Web Application
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=tulia
Group=tulia
WorkingDirectory=/opt/tulia-ai
Environment="PATH=/opt/tulia-ai/venv/bin"
EnvironmentFile=/opt/tulia-ai/.env
ExecStart=/opt/tulia-ai/venv/bin/gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --threads 2 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/tulia-celery-worker.service`**:
```ini
[Unit]
Description=Tulia AI Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=tulia
Group=tulia
WorkingDirectory=/opt/tulia-ai
Environment="PATH=/opt/tulia-ai/venv/bin"
EnvironmentFile=/opt/tulia-ai/.env
ExecStart=/opt/tulia-ai/venv/bin/celery -A config worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=default,integrations,analytics,messaging,bot \
  --pidfile=/var/run/celery/worker.pid \
  --logfile=/var/log/celery/worker.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/tulia-celery-beat.service`**:
```ini
[Unit]
Description=Tulia AI Celery Beat Scheduler
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=tulia
Group=tulia
WorkingDirectory=/opt/tulia-ai
Environment="PATH=/opt/tulia-ai/venv/bin"
EnvironmentFile=/opt/tulia-ai/.env
ExecStart=/opt/tulia-ai/venv/bin/celery -A config beat \
  --loglevel=info \
  --pidfile=/var/run/celery/beat.pid \
  --logfile=/var/log/celery/beat.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tulia-web tulia-celery-worker tulia-celery-beat
sudo systemctl start tulia-web tulia-celery-worker tulia-celery-beat
sudo systemctl status tulia-web tulia-celery-worker tulia-celery-beat
```

---

## Monitoring and Alerting

### Sentry Configuration

Sentry is configured in `config/settings.py` and provides:

- **Error Tracking**: Automatic capture of exceptions
- **Performance Monitoring**: Transaction tracing
- **Release Tracking**: Version-based error tracking
- **User Context**: Tenant and customer information

**Key Features**:
- Errors are automatically sent to Sentry
- Stack traces include local variables
- Breadcrumbs show events leading to errors
- Performance metrics for slow endpoints

**Sentry Dashboard**: https://sentry.io/organizations/your-org/projects/tulia-ai/

### Application Logging

Logs are written to:
- **Console**: All log levels (configurable)
- **File**: `/app/logs/tulia.log` (rotated at 10MB, 5 backups)
- **Format**: JSON (production) or verbose (development)

**Log Levels**:
- `DEBUG`: Detailed information for debugging
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical issues requiring immediate attention

**Viewing Logs**:
```bash
# Docker Compose
docker-compose logs -f web
docker-compose logs -f celery_worker

# Systemd
sudo journalctl -u tulia-web -f
sudo journalctl -u tulia-celery-worker -f

# Log files
tail -f /opt/tulia-ai/logs/tulia.log
```

### Health Checks

**Endpoint**: `GET /v1/health`

**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "celery": "available",
  "timestamp": "2025-01-12T10:30:00Z"
}
```

**Monitoring Script**:
```bash
#!/bin/bash
# /opt/tulia-ai/scripts/health_check.sh

HEALTH_URL="http://localhost:8000/v1/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed with status $RESPONSE"
    exit 1
fi
```

### Metrics to Monitor

1. **Application Metrics**:
   - Request rate (requests/second)
   - Response time (p50, p95, p99)
   - Error rate (4xx, 5xx)
   - Active connections

2. **Database Metrics**:
   - Connection pool usage
   - Query performance
   - Slow queries (>1s)
   - Database size

3. **Redis Metrics**:
   - Memory usage
   - Hit rate
   - Connected clients
   - Evicted keys

4. **Celery Metrics**:
   - Task queue length
   - Task processing time
   - Failed tasks
   - Worker availability

5. **Business Metrics**:
   - Active tenants
   - Messages processed
   - Orders created
   - Appointments booked
   - API usage per tenant

### Alerting Rules

Configure alerts for:

1. **Critical**:
   - Health check failures
   - Database connection failures
   - Redis connection failures
   - Celery worker down
   - Error rate > 5%

2. **Warning**:
   - Response time > 2s (p95)
   - Database connection pool > 80%
   - Redis memory > 80%
   - Celery queue length > 1000
   - Disk space > 80%

3. **Info**:
   - Deployment completed
   - Scheduled task completed
   - Tenant subscription expiring

### Recommended Monitoring Tools

- **Sentry**: Error tracking and performance monitoring (configured)
- **Prometheus + Grafana**: Metrics collection and visualization
- **Datadog**: Full-stack monitoring (alternative)
- **New Relic**: APM and infrastructure monitoring (alternative)
- **UptimeRobot**: External uptime monitoring

---

## Deployment Checklist

### Pre-Deployment

- [ ] Code reviewed and approved
- [ ] All tests passing
- [ ] Database migrations reviewed
- [ ] Environment variables configured
- [ ] Secrets rotated (if needed)
- [ ] Backup created
- [ ] Staging deployment tested
- [ ] Performance testing completed
- [ ] Security scan completed
- [ ] Documentation updated

### Deployment Steps

- [ ] Put application in maintenance mode (if needed)
- [ ] Pull latest code
- [ ] Install/update dependencies
- [ ] Run database migrations
- [ ] Collect static files
- [ ] Restart web servers
- [ ] Restart Celery workers
- [ ] Verify health checks
- [ ] Smoke test critical endpoints
- [ ] Monitor error rates
- [ ] Remove maintenance mode

### Post-Deployment

- [ ] Verify all services running
- [ ] Check error logs
- [ ] Monitor performance metrics
- [ ] Test critical user flows
- [ ] Notify team of deployment
- [ ] Update release notes
- [ ] Tag release in Git
- [ ] Update Sentry release

### Rollback Plan

If issues are detected:

```bash
# 1. Put application in maintenance mode
# 2. Revert to previous code version
git checkout <previous-tag>

# 3. Rollback database migrations (if needed)
python manage.py migrate app_name <previous_migration>

# 4. Restart services
sudo systemctl restart tulia-web tulia-celery-worker

# 5. Verify health checks
curl http://localhost:8000/v1/health

# 6. Remove maintenance mode
# 7. Investigate and fix issues
# 8. Plan re-deployment
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptoms**: `OperationalError: could not connect to server`

**Solutions**:
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection settings
psql -U tulia_user -h localhost -d tulia_db

# Verify DATABASE_URL in .env
echo $DATABASE_URL

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

#### 2. Redis Connection Errors

**Symptoms**: `ConnectionError: Error connecting to Redis`

**Solutions**:
```bash
# Check Redis is running
sudo systemctl status redis-server

# Test Redis connection
redis-cli ping

# Verify REDIS_URL in .env
echo $REDIS_URL

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

#### 3. Celery Workers Not Processing Tasks

**Symptoms**: Tasks stuck in queue, not being processed

**Solutions**:
```bash
# Check Celery worker status
celery -A config inspect active

# Check Celery worker logs
sudo journalctl -u tulia-celery-worker -f

# Restart Celery workers
sudo systemctl restart tulia-celery-worker

# Purge stuck tasks (use with caution)
celery -A config purge
```

#### 4. Migration Errors

**Symptoms**: `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Solutions**:
```bash
# Check migration status
python manage.py showmigrations

# Fake a migration (if already applied manually)
python manage.py migrate --fake app_name migration_number

# Reset migrations (DESTRUCTIVE - development only)
python manage.py migrate app_name zero
python manage.py migrate app_name
```

#### 5. Static Files Not Loading

**Symptoms**: 404 errors for CSS/JS files

**Solutions**:
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check STATIC_ROOT setting
python manage.py diffsettings | grep STATIC

# Verify Nginx configuration
sudo nginx -t
sudo systemctl reload nginx
```

#### 6. High Memory Usage

**Symptoms**: Server running out of memory

**Solutions**:
```bash
# Check memory usage
free -h
htop

# Check process memory
ps aux --sort=-%mem | head -n 10

# Reduce Celery concurrency
# Edit celery worker command: --concurrency=2

# Enable memory limits in Docker
# docker-compose.yml: mem_limit: 2g

# Restart services
sudo systemctl restart tulia-web tulia-celery-worker
```

#### 7. Slow API Responses

**Symptoms**: Requests taking >2 seconds

**Solutions**:
```bash
# Enable query logging
# Set DEBUG=True temporarily or use query_logging middleware

# Check database query performance
# Look for N+1 queries in logs

# Check Redis cache hit rate
redis-cli info stats | grep keyspace

# Increase database connection pool
# Update DB_CONN_MAX_AGE in .env

# Add database indexes
# Review slow query logs
```

### Getting Help

1. **Check Logs**: Always start with application and service logs
2. **Sentry**: Review error details and stack traces
3. **Health Check**: Verify all dependencies are healthy
4. **Documentation**: Review relevant sections of this guide
5. **Support**: Contact the development team with:
   - Error messages
   - Log excerpts
   - Steps to reproduce
   - Environment details

---

## Additional Resources

### Documentation
- **API Documentation**: https://api.yourdomain.com/schema/swagger/
- **Postman Collection**: See `postman_collection.json`
- **Architecture Diagram**: See `.kiro/specs/tulia-whatsapp-platform/design.md`
- **RBAC Guide**: See `apps/core/RBAC_QUICK_REFERENCE.md`
- **Tenant Settings**: See `apps/tenants/SETTINGS_QUICK_REFERENCE.md`

### Deployment Guides
- **Environment Variables**: See `ENVIRONMENT_VARIABLES.md` for complete reference
- **Database Migrations**: See `DATABASE_MIGRATIONS.md` for migration procedures
- **Monitoring Setup**: See `MONITORING_SETUP.md` for monitoring and alerting configuration

### External Resources
- **Django Documentation**: https://docs.djangoproject.com/en/4.2/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Redis Documentation**: https://redis.io/documentation
- **Celery Documentation**: https://docs.celeryproject.org/
- **Docker Documentation**: https://docs.docker.com/

---

## Security Considerations

1. **Never commit secrets** to version control
2. **Rotate credentials** regularly (every 90 days)
3. **Use strong passwords** for database and Redis
4. **Enable SSL/TLS** for all external connections
5. **Keep dependencies updated** for security patches
6. **Monitor access logs** for suspicious activity
7. **Implement rate limiting** to prevent abuse
8. **Use firewall rules** to restrict access
9. **Enable audit logging** for sensitive operations
10. **Regular security audits** and penetration testing

---

## Maintenance

### Regular Tasks

**Daily**:
- Monitor error rates and performance
- Review Sentry alerts
- Check disk space

**Weekly**:
- Review slow query logs
- Check for failed Celery tasks
- Review security logs

**Monthly**:
- Update dependencies
- Review and rotate credentials
- Database maintenance (VACUUM, ANALYZE)
- Review and archive old logs

**Quarterly**:
- Security audit
- Performance review
- Capacity planning
- Disaster recovery test

---

## Support

For deployment support, contact:
- **Email**: devops@yourdomain.com
- **Slack**: #tulia-ai-ops
- **On-Call**: PagerDuty rotation

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
