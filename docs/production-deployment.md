# Production Deployment Guide

This guide covers deploying Tulia API to production with gunicorn and proper dependency management.

## Requirements Installation

### Option 1: Full Installation (Recommended)
```bash
pip install -r requirements.txt
```
Includes all features: AI/RAG, document processing, integrations.

### Option 2: Minimal Installation
```bash
pip install -r requirements-minimal.txt
```
Basic Django API only, no AI features. Use this if you're experiencing dependency conflicts.

## Gunicorn Configuration

### Basic Gunicorn Command
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### Production Gunicorn Configuration
Create `gunicorn.conf.py`:

```python
# gunicorn.conf.py
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "/var/log/tulia/gunicorn-access.log"
errorlog = "/var/log/tulia/gunicorn-error.log"
loglevel = "info"

# Process naming
proc_name = "tulia-api"

# Server mechanics
preload_app = True
daemon = False
pidfile = "/var/run/tulia/gunicorn.pid"
user = "tulia"
group = "tulia"
tmp_upload_dir = None

# SSL (if terminating SSL at gunicorn level)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"
```

### Run with Configuration File
```bash
gunicorn config.wsgi:application -c gunicorn.conf.py
```

## Environment Variables

Ensure these are set in production:

```bash
# Core Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/tulia_db

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Providers (at least one required)
OPENAI_API_KEY=your-openai-key
GOOGLE_API_KEY=your-google-key

# Monitoring
SENTRY_DSN=your-sentry-dsn
```

## Systemd Service

Create `/etc/systemd/system/tulia-api.service`:

```ini
[Unit]
Description=Tulia API
After=network.target

[Service]
User=tulia
Group=tulia
WorkingDirectory=/opt/tulia/tulia.api
Environment=PATH=/opt/tulia/venv/bin
EnvironmentFile=/opt/tulia/.env
ExecStart=/opt/tulia/venv/bin/gunicorn config.wsgi:application -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable tulia-api
sudo systemctl start tulia-api
sudo systemctl status tulia-api
```

## Dependency Conflict Resolution

If you encounter dependency conflicts:

1. **Try minimal installation first**:
   ```bash
   pip install -r requirements-minimal.txt
   ```

2. **Check for conflicts**:
   ```bash
   python scripts/check_dependencies.py
   ```

3. **Use virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Clear pip cache if needed**:
   ```bash
   pip cache purge
   pip install --no-cache-dir -r requirements.txt
   ```

## Common Issues

### Issue: Package version conflicts
**Solution**: Use `requirements-minimal.txt` or create a custom requirements file with only the packages you need.

### Issue: Python 3.12.4 compatibility
**Solution**: All versions in our requirements files are tested with Python 3.12.4. Ensure you're using the exact versions specified.

### Issue: Memory usage with full installation
**Solution**: Use `requirements-minimal.txt` for lighter deployments, or increase server memory.

## Performance Tuning

### Gunicorn Workers
- **CPU-bound**: `workers = (2 * CPU_cores) + 1`
- **I/O-bound**: `workers = (4 * CPU_cores) + 1`

### Database Connections
Set in Django settings:
```python
DATABASES = {
    'default': {
        # ... other settings
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'MAX_CONNS': 20,
        }
    }
}
```

### Redis Configuration
```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        }
    }
}
```

## Monitoring

### Health Check Endpoint
The API includes a health check at `/health/` that verifies:
- Database connectivity
- Redis connectivity
- Critical service availability

### Logging
Configure structured logging in production:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/tulia/django.log',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

## Security Checklist

- [ ] `DEBUG = False` in production
- [ ] Strong `SECRET_KEY` (50+ characters)
- [ ] HTTPS enabled (SSL certificate)
- [ ] Database credentials secured
- [ ] API keys in environment variables
- [ ] Firewall configured
- [ ] Regular security updates
- [ ] Backup strategy implemented

## Scaling

### Horizontal Scaling
- Use load balancer (nginx, HAProxy)
- Multiple gunicorn instances
- Shared Redis/PostgreSQL

### Vertical Scaling
- Increase gunicorn workers
- Optimize database queries
- Use Redis for caching

### Celery Workers
For background tasks:
```bash
celery -A config worker -l info --concurrency=4
celery -A config beat -l info
```