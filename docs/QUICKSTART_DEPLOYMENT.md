# Quick Start Deployment Guide

Get Tulia AI up and running in 10 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Git installed
- 4GB RAM available
- 10GB disk space

## Quick Start with Docker Compose

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/yourorg/tulia-ai.git
cd tulia-ai

# Create environment file
cp .env.example .env

# Generate encryption key
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode('utf-8'))"
# Copy the output and set ENCRYPTION_KEY in .env

# Generate JWT secret key (REQUIRED - must be different from SECRET_KEY)
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# Copy the output and set JWT_SECRET_KEY in .env

# Set your OpenAI API key in .env
# OPENAI_API_KEY=sk-your-key-here
```

### 2. Start Services

```bash
# Build and start all services
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps
```

### 3. Initialize Database

```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Seed initial data
docker-compose exec web python manage.py seed_permissions
docker-compose exec web python manage.py seed_subscription_tiers

# (Optional) Load demo data
docker-compose exec web python manage.py seed_demo_data
```

### 4. Verify Installation

```bash
# Check health
curl http://localhost:8000/v1/health

# Expected response:
# {"status":"healthy","database":"connected","redis":"connected","celery":"available"}
```

### 5. Access the Application

- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/schema/swagger/
- **Admin**: http://localhost:8000/admin

## Next Steps

1. **Read the full deployment guide**: See `DEPLOYMENT.md`
2. **Configure environment variables**: See `ENVIRONMENT_VARIABLES.md`
3. **Set up monitoring**: See `MONITORING_SETUP.md`
4. **Review API documentation**: Visit http://localhost:8000/schema/swagger/

## Common Commands

```bash
# View logs
docker-compose logs -f web
docker-compose logs -f celery_worker

# Restart services
docker-compose restart web
docker-compose restart celery_worker

# Stop all services
docker-compose down

# Stop and remove volumes (DESTRUCTIVE)
docker-compose down -v

# Run Django management commands
docker-compose exec web python manage.py <command>

# Access Django shell
docker-compose exec web python manage.py shell

# Access database shell
docker-compose exec web python manage.py dbshell

# Run tests
docker-compose exec web pytest
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database connection errors

```bash
# Check database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Redis connection errors

```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

## Production Deployment

For production deployment, see:
- `DEPLOYMENT.md` - Complete deployment guide
- `docker-compose.prod.yml` - Production Docker Compose configuration
- `Dockerfile.prod` - Production Dockerfile

---

**Need Help?**
- Full Documentation: `DEPLOYMENT.md`
- Environment Variables: `ENVIRONMENT_VARIABLES.md`
- Database Migrations: `DATABASE_MIGRATIONS.md`
- Monitoring: `MONITORING_SETUP.md`
