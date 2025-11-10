# Tulia AI - Quick Start Guide

Get up and running with Tulia AI in 5 minutes.

## Option 1: Docker (Recommended)

```bash
# 1. Clone and navigate to project
cd tulia

# 2. Create environment file
cp .env.example .env
# Edit .env with your configuration (at minimum, set SECRET_KEY and ENCRYPTION_KEY)

# 3. Start all services
docker-compose up -d

# 4. Run migrations
docker-compose exec web python manage.py migrate

# 5. Create superuser
docker-compose exec web python manage.py createsuperuser

# 6. Access the application
# API: http://localhost:8000/v1/
# Swagger: http://localhost:8000/schema/swagger/
# Health: http://localhost:8000/v1/health/
# Admin: http://localhost:8000/admin/
```

## Option 2: Local Development

```bash
# 1. Run setup script
./scripts/setup.sh

# 2. Activate virtual environment
source venv/bin/activate

# 3. Edit .env file
cp .env.example .env
# Set SECRET_KEY, DATABASE_URL, REDIS_URL, etc.

# 4. Start PostgreSQL and Redis
# Using Docker:
docker-compose up -d db redis

# Or install locally and start services

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Start development server
python manage.py runserver

# 8. In separate terminals, start Celery
celery -A config worker -l info
celery -A config beat -l info
```

## Generate Required Keys

```python
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Verify Installation

```bash
# Check health
curl http://localhost:8000/v1/health/

# Expected response:
# {
#   "status": "healthy",
#   "database": "healthy",
#   "cache": "healthy",
#   "celery": "healthy"
# }
```

## Common Commands

```bash
# Run tests
make test

# Run migrations
make migrate

# Create migrations
make makemigrations

# Django shell
make shell

# View logs (Docker)
make docker-logs

# Stop services (Docker)
make docker-down
```

## API Endpoints

- **Health Check**: `GET /v1/health/`
- **OpenAPI Schema**: `GET /schema/`
- **Swagger UI**: `GET /schema/swagger/`
- **Admin Panel**: `GET /admin/`

## Next Steps

1. Review the [README.md](README.md) for detailed documentation
2. Check [DEPLOYMENT.md](DEPLOYMENT.md) for production setup
3. Start implementing Task 2: Tenant models and multi-tenant isolation
4. Explore the API at http://localhost:8000/schema/swagger/

## Troubleshooting

### Database connection error
- Ensure PostgreSQL is running
- Check DATABASE_URL in .env
- Verify database exists: `psql -U tulia_user -d tulia_db`
- Verify psycopg3 is installed: `python -c "import psycopg; print(psycopg.__version__)"`

### Redis connection error
- Ensure Redis is running: `redis-cli ping`
- Check REDIS_URL in .env

### Celery not working
- Check Redis is running (Celery broker)
- Verify CELERY_BROKER_URL in .env
- Check worker logs: `docker-compose logs celery_worker`

### Import errors
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review error messages in Sentry (if configured)
- Contact: support@tulia.ai
