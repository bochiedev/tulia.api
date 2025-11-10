# Tulia AI - Deployment Guide

This guide covers deploying Tulia AI to production environments.

## Prerequisites

- Python 3.12+
- PostgreSQL 15+ (with psycopg3 driver)
- Redis 7+
- Nginx (for production)
- Supervisor or systemd (for process management)

## Environment Variables

### Required Variables

```bash
# Django
SECRET_KEY=<generate-with-django-secret-key-generator>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/tulia_db
DB_CONN_MAX_AGE=600

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# AI/LLM
OPENAI_API_KEY=sk-...

# Sentry
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production

# Encryption
ENCRYPTION_KEY=<generate-with-cryptography.fernet.Fernet.generate_key()>

# Logging
LOG_LEVEL=INFO
JSON_LOGS=True
```

### Generating Secret Keys

```python
# Django SECRET_KEY
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())

# Encryption Key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Database Setup

### PostgreSQL Configuration

1. **Create database and user**
   ```sql
   CREATE DATABASE tulia_db;
   CREATE USER tulia_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE tulia_db TO tulia_user;
   ALTER USER tulia_user CREATEDB;  -- For running tests
   ```

2. **Configure connection pooling**
   ```bash
   # In postgresql.conf
   max_connections = 100
   shared_buffers = 256MB
   effective_cache_size = 1GB
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   ```

## Redis Configuration

```bash
# In redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Application Deployment

### Using Gunicorn

1. **Install Gunicorn**
   ```bash
   pip install gunicorn
   ```

2. **Create Gunicorn configuration**
   ```python
   # gunicorn.conf.py
   bind = "0.0.0.0:8000"
   workers = 4
   worker_class = "sync"
   worker_connections = 1000
   timeout = 30
   keepalive = 2
   errorlog = "/var/log/tulia/gunicorn-error.log"
   accesslog = "/var/log/tulia/gunicorn-access.log"
   loglevel = "info"
   ```

3. **Run Gunicorn**
   ```bash
   gunicorn config.wsgi:application -c gunicorn.conf.py
   ```

### Using Supervisor

```ini
# /etc/supervisor/conf.d/tulia.conf
[program:tulia-web]
command=/path/to/venv/bin/gunicorn config.wsgi:application -c gunicorn.conf.py
directory=/path/to/tulia
user=tulia
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/tulia/web.log

[program:tulia-celery-worker]
command=/path/to/venv/bin/celery -A config worker -l info -Q default,integrations,analytics,messaging,bot
directory=/path/to/tulia
user=tulia
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/tulia/celery-worker.log

[program:tulia-celery-beat]
command=/path/to/venv/bin/celery -A config beat -l info
directory=/path/to/tulia
user=tulia
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/tulia/celery-beat.log
```

### Using systemd

```ini
# /etc/systemd/system/tulia-web.service
[Unit]
Description=Tulia AI Web Service
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=tulia
Group=tulia
WorkingDirectory=/path/to/tulia
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn config.wsgi:application -c gunicorn.conf.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Nginx Configuration

```nginx
upstream tulia_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/key.pem;
    
    client_max_body_size 10M;
    
    location /static/ {
        alias /path/to/tulia/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location / {
        proxy_pass http://tulia_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

## Static Files

```bash
# Collect static files
python manage.py collectstatic --noinput

# Set proper permissions
chown -R tulia:tulia /path/to/tulia/staticfiles
```

## Monitoring & Logging

### Sentry Setup

1. Create Sentry project at https://sentry.io
2. Add DSN to environment variables
3. Verify error tracking:
   ```python
   from sentry_sdk import capture_message
   capture_message("Test message from Tulia AI")
   ```

### Log Rotation

```bash
# /etc/logrotate.d/tulia
/var/log/tulia/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 tulia tulia
    sharedscripts
    postrotate
        supervisorctl restart tulia-web tulia-celery-worker tulia-celery-beat
    endscript
}
```

## Security Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Use strong `SECRET_KEY` and `ENCRYPTION_KEY`
- [ ] Configure HTTPS with valid SSL certificate
- [ ] Set proper `ALLOWED_HOSTS`
- [ ] Enable CORS only for trusted origins
- [ ] Use environment variables for all secrets
- [ ] Configure database connection pooling
- [ ] Set up firewall rules (allow only 80, 443, SSH)
- [ ] Enable rate limiting
- [ ] Configure Sentry for error tracking
- [ ] Set up regular database backups
- [ ] Use strong passwords for database and Redis
- [ ] Restrict Redis to localhost or use authentication
- [ ] Keep dependencies updated

## Backup Strategy

### Database Backups

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/tulia"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U tulia_user tulia_db | gzip > $BACKUP_DIR/tulia_db_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "tulia_db_*.sql.gz" -mtime +30 -delete
```

### Redis Backups

Redis automatically saves snapshots based on configuration. Copy RDB file for backups:

```bash
cp /var/lib/redis/dump.rdb /backups/tulia/redis_$(date +%Y%m%d).rdb
```

## Performance Optimization

### Database Indexes

Ensure all foreign keys and frequently queried fields have indexes. Run:

```bash
python manage.py sqlmigrate <app> <migration> | grep INDEX
```

### Caching Strategy

- Tenant configuration: 1 hour TTL
- Product catalog: 15 minutes TTL
- Customer preferences: 5 minutes TTL
- Availability windows: 1 hour TTL

### Connection Pooling

Configure `DB_CONN_MAX_AGE=600` for persistent database connections.

## Scaling

### Horizontal Scaling

1. **Multiple Web Workers**: Run multiple Gunicorn instances behind load balancer
2. **Celery Workers**: Scale workers per queue based on load
3. **Database**: Use read replicas for analytics queries
4. **Redis**: Use Redis Cluster for high availability

### Vertical Scaling

- Web: 2-4 CPU cores, 4-8 GB RAM per instance
- Celery Worker: 2 CPU cores, 2-4 GB RAM per worker
- Database: 4+ CPU cores, 8+ GB RAM
- Redis: 2 CPU cores, 2-4 GB RAM

## Health Checks

Configure load balancer health checks:

```
GET /v1/health/
Expected: 200 OK
Interval: 30s
Timeout: 5s
Unhealthy threshold: 3
```

## Deployment Checklist

- [ ] Update code from repository
- [ ] Activate virtual environment
- [ ] Install/update dependencies: `pip install -r requirements.txt`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Collect static files: `python manage.py collectstatic --noinput`
- [ ] Run tests: `pytest`
- [ ] Restart web service
- [ ] Restart Celery workers
- [ ] Verify health check: `curl https://yourdomain.com/v1/health/`
- [ ] Monitor logs for errors
- [ ] Check Sentry for exceptions

## Rollback Procedure

1. Revert code to previous version
2. Rollback database migrations if needed: `python manage.py migrate <app> <previous_migration>`
3. Restart services
4. Verify health check

## Support

For deployment issues, contact: devops@tulia.ai
