# CI/CD Setup Guide

## Overview

This document describes the CI/CD pipeline configuration for Tulia AI. The pipeline uses GitHub Actions to automate testing, security scanning, and deployment to staging and production environments.

## Pipeline Architecture

### 1. Continuous Integration (CI)

Triggered on every push and pull request to `main` and `develop` branches.

**Jobs:**
- **Test**: Runs unit and integration tests with coverage reporting
- **Lint**: Performs code quality checks (flake8, black, isort)
- **Security Scan**: Runs security vulnerability scanning (bandit, safety, Trivy)
- **Docker Build**: Tests Docker image builds

### 2. Continuous Deployment (CD)

**Staging Deployment:**
- Triggered on push to `develop` branch
- Deploys to staging environment
- Uses staging secrets and test API keys

**Production Deployment:**
- Triggered on push to `main` branch or version tags
- Requires manual approval (GitHub environment protection)
- Creates database backup before deployment
- Runs smoke tests after deployment
- Creates GitHub release for tagged versions

## Required GitHub Secrets

### General Secrets

```bash
# CI/CD Secrets (for testing)
SECRET_KEY                    # Django secret key for tests
JWT_SECRET_KEY               # JWT secret key for tests
ENCRYPTION_KEY               # Encryption key for tests
OPENAI_API_KEY              # OpenAI API key (can use test key)
```

### Staging Environment Secrets

```bash
# Server Access
STAGING_HOST                 # SSH host for staging server
STAGING_USER                 # SSH username
STAGING_SSH_KEY             # SSH private key
STAGING_PORT                # SSH port (default: 22)

# Django Configuration
STAGING_SECRET_KEY          # Django secret key
STAGING_ALLOWED_HOSTS       # Comma-separated list of allowed hosts
STAGING_FRONTEND_URL        # Frontend URL

# Database
STAGING_DATABASE_URL        # PostgreSQL connection string

# Redis
STAGING_REDIS_URL          # Redis connection string
STAGING_CELERY_BROKER_URL  # Celery broker URL
STAGING_CELERY_RESULT_BACKEND  # Celery result backend URL

# JWT & Encryption
STAGING_JWT_SECRET_KEY     # JWT secret key
STAGING_ENCRYPTION_KEY     # Encryption key

# OpenAI
STAGING_OPENAI_API_KEY     # OpenAI API key

# Sentry
STAGING_SENTRY_DSN         # Sentry DSN for error tracking

# Email
STAGING_EMAIL_HOST         # SMTP host
STAGING_EMAIL_PORT         # SMTP port
STAGING_EMAIL_HOST_USER    # SMTP username
STAGING_EMAIL_HOST_PASSWORD  # SMTP password

# Payment Providers (Test Keys)
STAGING_STRIPE_SECRET_KEY
STAGING_STRIPE_PUBLISHABLE_KEY
STAGING_STRIPE_WEBHOOK_SECRET
STAGING_PAYSTACK_SECRET_KEY
STAGING_PAYSTACK_PUBLIC_KEY
STAGING_PESAPAL_CONSUMER_KEY
STAGING_PESAPAL_CONSUMER_SECRET
STAGING_PESAPAL_IPN_ID
STAGING_MPESA_CONSUMER_KEY
STAGING_MPESA_CONSUMER_SECRET
STAGING_MPESA_SHORTCODE
STAGING_MPESA_PASSKEY
STAGING_MPESA_INITIATOR_NAME
STAGING_MPESA_INITIATOR_PASSWORD
STAGING_MPESA_B2C_SHORTCODE
STAGING_MPESA_B2C_SECURITY_CREDENTIAL
```

### Production Environment Secrets

```bash
# Server Access
PRODUCTION_HOST            # SSH host for production server
PRODUCTION_USER            # SSH username
PRODUCTION_SSH_KEY         # SSH private key
PRODUCTION_PORT            # SSH port (default: 22)

# Database Backup
PRODUCTION_DB_USER         # Database user for backups
PRODUCTION_DB_NAME         # Database name for backups

# Django Configuration
PRODUCTION_SECRET_KEY      # Django secret key
PRODUCTION_ALLOWED_HOSTS   # Comma-separated list of allowed hosts
PRODUCTION_FRONTEND_URL    # Frontend URL

# Database
PRODUCTION_DATABASE_URL    # PostgreSQL connection string

# Redis
PRODUCTION_REDIS_URL       # Redis connection string
PRODUCTION_CELERY_BROKER_URL  # Celery broker URL
PRODUCTION_CELERY_RESULT_BACKEND  # Celery result backend URL

# JWT & Encryption
PRODUCTION_JWT_SECRET_KEY  # JWT secret key
PRODUCTION_ENCRYPTION_KEY  # Encryption key

# OpenAI
PRODUCTION_OPENAI_API_KEY  # OpenAI API key

# Sentry
PRODUCTION_SENTRY_DSN      # Sentry DSN for error tracking

# Email
PRODUCTION_EMAIL_HOST      # SMTP host
PRODUCTION_EMAIL_PORT      # SMTP port
PRODUCTION_EMAIL_HOST_USER # SMTP username
PRODUCTION_EMAIL_HOST_PASSWORD  # SMTP password

# Payment Providers (Production Keys)
PRODUCTION_STRIPE_SECRET_KEY
PRODUCTION_STRIPE_PUBLISHABLE_KEY
PRODUCTION_STRIPE_WEBHOOK_SECRET
PRODUCTION_PAYSTACK_SECRET_KEY
PRODUCTION_PAYSTACK_PUBLIC_KEY
PRODUCTION_PESAPAL_CONSUMER_KEY
PRODUCTION_PESAPAL_CONSUMER_SECRET
PRODUCTION_PESAPAL_IPN_ID
PRODUCTION_MPESA_CONSUMER_KEY
PRODUCTION_MPESA_CONSUMER_SECRET
PRODUCTION_MPESA_SHORTCODE
PRODUCTION_MPESA_PASSKEY
PRODUCTION_MPESA_INITIATOR_NAME
PRODUCTION_MPESA_INITIATOR_PASSWORD
PRODUCTION_MPESA_B2C_SHORTCODE
PRODUCTION_MPESA_B2C_SECURITY_CREDENTIAL
PRODUCTION_PESALINK_API_KEY
PRODUCTION_PESALINK_API_SECRET
PRODUCTION_PESALINK_INSTITUTION_CODE
PRODUCTION_PESALINK_API_URL

# Notifications
SLACK_WEBHOOK_URL          # Slack webhook for deployment notifications
```

## Setting Up GitHub Secrets

### 1. Navigate to Repository Settings

```
GitHub Repository → Settings → Secrets and variables → Actions
```

### 2. Add Repository Secrets

Click "New repository secret" and add each secret listed above.

### 3. Configure Environments

Create two environments with protection rules:

**Staging Environment:**
```
Settings → Environments → New environment → "staging"
- No required reviewers (auto-deploy)
- Deployment branches: develop
```

**Production Environment:**
```
Settings → Environments → New environment → "production"
- Required reviewers: Add team members who can approve deployments
- Deployment branches: main, tags matching v*
```

## Generating Secure Keys

Use the provided script to generate all required keys:

```bash
python scripts/generate_secrets.py
```

Or generate individual keys:

```bash
# Django SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(50))"

# JWT_SECRET_KEY (must be different from SECRET_KEY)
python -c "import secrets; print(secrets.token_urlsafe(50))"

# ENCRYPTION_KEY (must be exactly 32 bytes, base64-encoded)
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode('utf-8'))"
```

## Server Setup Requirements

### Prerequisites

Both staging and production servers must have:

1. **Docker and Docker Compose installed**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo apt-get install docker-compose-plugin
   ```

2. **Application directory structure**
   ```bash
   sudo mkdir -p /opt/tulia-ai/backups
   sudo chown -R $USER:$USER /opt/tulia-ai
   cd /opt/tulia-ai
   ```

3. **Docker Compose configuration**
   - Copy `docker-compose.prod.yml` to `/opt/tulia-ai/`
   - Ensure proper file permissions

4. **SSH access configured**
   - Add deployment SSH key to `~/.ssh/authorized_keys`
   - Ensure user has Docker permissions: `sudo usermod -aG docker $USER`

### Network Configuration

Ensure the following ports are accessible:

- **80**: HTTP (redirects to HTTPS)
- **443**: HTTPS
- **8000**: Application (internal, behind nginx)
- **5432**: PostgreSQL (internal only)
- **6379**: Redis (internal only)

## Deployment Workflow

### Staging Deployment

1. **Create a pull request** to `develop` branch
2. **CI pipeline runs** automatically (tests, linting, security scans)
3. **Merge to develop** after approval
4. **Staging deployment triggers** automatically
5. **Verify deployment** at staging URL

### Production Deployment

1. **Merge develop to main** or create a version tag
2. **CI pipeline runs** on main branch
3. **Production deployment requires approval** (if configured)
4. **Backup is created** before deployment
5. **New version is deployed**
6. **Smoke tests run** automatically
7. **Notification sent** to Slack (if configured)

### Manual Deployment

Trigger manual deployment via GitHub Actions UI:

```
Actions → Deploy to Staging/Production → Run workflow
```

## Monitoring Deployments

### View Deployment Status

```
GitHub Repository → Actions → Select workflow run
```

### Check Deployment Logs

```
Actions → Workflow run → Job → Step logs
```

### Server Logs

SSH into the server and check logs:

```bash
cd /opt/tulia-ai
docker-compose -f docker-compose.prod.yml logs -f
```

## Rollback Procedure

### Automatic Rollback

If health checks fail, the deployment will fail and the previous version remains running.

### Manual Rollback

1. **SSH into the server**
   ```bash
   ssh user@server
   cd /opt/tulia-ai
   ```

2. **Restore database backup** (if needed)
   ```bash
   docker-compose -f docker-compose.prod.yml exec -T db psql -U tulia_user tulia_db < backups/backup_YYYYMMDD_HHMMSS.sql
   ```

3. **Deploy previous version**
   ```bash
   docker pull ghcr.io/your-org/tulia-ai:prod-PREVIOUS_SHA
   docker-compose -f docker-compose.prod.yml down
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Security Best Practices

### 1. Secret Rotation

Rotate secrets regularly:

```bash
# Generate new keys
python scripts/generate_secrets.py

# Update GitHub secrets
# Update server .env files
# Restart services
```

### 2. Access Control

- Limit who can approve production deployments
- Use separate SSH keys for staging and production
- Rotate SSH keys periodically
- Use least-privilege principle for service accounts

### 3. Monitoring

- Enable Sentry for error tracking
- Set up Slack notifications for deployment events
- Monitor application logs regularly
- Set up alerts for critical errors

### 4. Backup Strategy

- Automated database backups before each deployment
- Keep last 7 backups on server
- Store critical backups off-site
- Test backup restoration regularly

## Troubleshooting

### Deployment Fails at Health Check

```bash
# Check application logs
docker-compose -f docker-compose.prod.yml logs web

# Check if services are running
docker-compose -f docker-compose.prod.yml ps

# Manually test health endpoint
curl http://localhost:8000/v1/health
```

### Database Migration Fails

```bash
# Check migration status
docker-compose -f docker-compose.prod.yml exec web python manage.py showmigrations

# Run migrations manually
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# Check for migration conflicts
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate --plan
```

### Environment Variables Not Loading

```bash
# Verify .env file exists and has correct permissions
ls -la /opt/tulia-ai/.env

# Check if variables are loaded in container
docker-compose -f docker-compose.prod.yml exec web env | grep SECRET_KEY

# Restart services to reload environment
docker-compose -f docker-compose.prod.yml restart
```

### SSH Connection Issues

```bash
# Test SSH connection
ssh -i ~/.ssh/deploy_key user@server

# Verify SSH key permissions
chmod 600 ~/.ssh/deploy_key

# Check SSH agent
ssh-add -l
```

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Security Best Practices](./SECURITY_BEST_PRACTICES.md)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Check server logs
4. Contact the DevOps team
