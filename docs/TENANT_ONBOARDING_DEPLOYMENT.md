# Tenant Self-Service Onboarding - Deployment Guide

## Overview

This document covers the deployment requirements and procedures for the Tenant Self-Service Onboarding feature. This feature enables users to register accounts, create tenants, and configure settings through a comprehensive REST API.

## Table of Contents

1. [New Environment Variables](#new-environment-variables)
2. [Database Migrations](#database-migrations)
3. [Celery Task Configuration](#celery-task-configuration)
4. [Email Configuration](#email-configuration)
5. [Deployment Checklist](#deployment-checklist)
6. [Rollback Procedures](#rollback-procedures)

---

## New Environment Variables

### JWT Authentication

The onboarding system uses JWT tokens for user authentication. Configure these variables:

```bash
# JWT Configuration
JWT_SECRET_KEY=  # Leave empty to use SECRET_KEY (recommended)
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24  # Access token expiry (1 day)
JWT_REFRESH_EXPIRATION_DAYS=7  # Refresh token expiry (7 days)
```

**Notes:**
- If `JWT_SECRET_KEY` is empty, Django's `SECRET_KEY` will be used
- Access tokens expire after 24 hours by default
- Refresh tokens expire after 7 days by default
- Use HS256 algorithm (HMAC with SHA-256)

### Email Configuration

Email is required for verification and password reset flows:

```bash
# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net  # Or your SMTP provider
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey  # For SendGrid
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

**Email Providers:**
- **SendGrid** (recommended): `smtp.sendgrid.net:587`
- **Mailgun**: `smtp.mailgun.org:587`
- **AWS SES**: `email-smtp.us-east-1.amazonaws.com:587`
- **Gmail**: `smtp.gmail.com:587` (not recommended for production)

**Testing Email:**
```bash
# Development: Use console backend (prints to console)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Testing: Use dummy backend (discards emails)
EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend
```

### Frontend URL

Required for email links (verification, password reset):

```bash
# Frontend URL
FRONTEND_URL=https://app.yourdomain.com
```

**Notes:**
- Must be the full URL including protocol (https://)
- Used to generate links in verification and password reset emails
- Should point to your frontend application

### Stripe Configuration (Optional)

Required if using payment method management:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

**Notes:**
- Use test keys (`sk_test_`, `pk_test_`) for development
- Use live keys (`sk_live_`, `pk_live_`) for production
- Webhook secret is used to verify Stripe webhook signatures


---

## Database Migrations

### New Migrations

The onboarding feature includes several database migrations:

1. **User Model Enhancements** (`apps/rbac/migrations/0002_add_email_verification_and_password_reset.py`)
   - Adds `email_verified` field
   - Adds `email_verification_token` field
   - Adds `email_verification_sent_at` field

2. **Password Reset Tokens** (included in above migration)
   - Creates `PasswordResetToken` model
   - Adds indexes for token lookup

3. **Onboarding Tracking** (`apps/tenants/migrations/0006_add_onboarding_tracking.py`)
   - Adds `onboarding_status` JSONField to TenantSettings
   - Adds `onboarding_completed` BooleanField
   - Adds `onboarding_completed_at` DateTimeField

### Running Migrations

**Development:**
```bash
# Create migrations (if not already created)
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Verify migrations
python manage.py showmigrations
```

**Production:**
```bash
# 1. Backup database first!
pg_dump -U tulia_user tulia_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Review migrations
python manage.py sqlmigrate rbac 0002
python manage.py sqlmigrate tenants 0006

# 3. Apply migrations
python manage.py migrate

# 4. Verify
python manage.py showmigrations
```

**Docker:**
```bash
# Apply migrations
docker-compose exec web python manage.py migrate

# Verify
docker-compose exec web python manage.py showmigrations
```

### Migration Details

#### User Model Changes

```sql
-- Add email verification fields
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(255);
ALTER TABLE users ADD COLUMN email_verification_sent_at TIMESTAMP;

-- Create password reset tokens table
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_password_reset_token ON password_reset_tokens(token, expires_at, used);
```

#### TenantSettings Changes

```sql
-- Add onboarding tracking fields
ALTER TABLE tenant_settings ADD COLUMN onboarding_status JSONB DEFAULT '{}';
ALTER TABLE tenant_settings ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE tenant_settings ADD COLUMN onboarding_completed_at TIMESTAMP;
```

### Data Migration

After applying migrations, initialize onboarding status for existing tenants:

```bash
# Run management command
python manage.py shell

# In Python shell:
from apps.tenants.models import TenantSettings

for settings in TenantSettings.objects.all():
    if not settings.onboarding_status:
        settings.initialize_onboarding_status()
        print(f"Initialized onboarding for tenant: {settings.tenant.name}")
```

Or use a data migration script:

```python
# apps/tenants/migrations/0007_initialize_onboarding.py
from django.db import migrations

def initialize_onboarding(apps, schema_editor):
    TenantSettings = apps.get_model('tenants', 'TenantSettings')
    
    for settings in TenantSettings.objects.all():
        settings.onboarding_status = {
            'twilio_configured': {'completed': False, 'completed_at': None},
            'payment_method_added': {'completed': False, 'completed_at': None},
            'business_settings_configured': {'completed': False, 'completed_at': None},
            'woocommerce_configured': {'completed': False, 'completed_at': None},
            'shopify_configured': {'completed': False, 'completed_at': None},
            'payout_method_configured': {'completed': False, 'completed_at': None},
        }
        settings.save(update_fields=['onboarding_status'])

class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0006_add_onboarding_tracking'),
    ]
    
    operations = [
        migrations.RunPython(initialize_onboarding),
    ]
```


---

## Celery Task Configuration

### New Celery Tasks

The onboarding feature includes a scheduled task for sending onboarding reminders.

#### Onboarding Reminder Task

**Task:** `apps.tenants.tasks.send_onboarding_reminders`

**Purpose:** Send email reminders to tenants with incomplete onboarding

**Schedule:** Daily at 10:00 AM (configurable)

**Configuration:**

Add to `config/settings.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ... existing tasks ...
    
    'send-onboarding-reminders': {
        'task': 'apps.tenants.tasks.send_onboarding_reminders',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10:00 AM
        'options': {
            'queue': 'default',
        },
    },
}
```

**Customizing Schedule:**

```python
# Every day at 9:00 AM
'schedule': crontab(hour=9, minute=0)

# Every Monday at 10:00 AM
'schedule': crontab(hour=10, minute=0, day_of_week=1)

# Every 6 hours
'schedule': crontab(minute=0, hour='*/6')
```

### Manual Task Execution

You can manually trigger the onboarding reminder task:

```bash
# Using management command
python manage.py send_onboarding_reminders

# Using Celery
python manage.py shell
>>> from apps.tenants.tasks import send_onboarding_reminders
>>> send_onboarding_reminders.delay()
```

### Celery Worker Configuration

Ensure Celery workers are running to process tasks:

**Development:**
```bash
# Start worker
celery -A config worker -l info

# Start beat scheduler
celery -A config beat -l info
```

**Production (systemd):**

Create `/etc/systemd/system/tulia-celery-beat.service`:

```ini
[Unit]
Description=Tulia AI Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=tulia
Group=tulia
WorkingDirectory=/opt/tulia-ai
Environment="PATH=/opt/tulia-ai/venv/bin"
EnvironmentFile=/opt/tulia-ai/.env
ExecStart=/opt/tulia-ai/venv/bin/celery -A config beat \
  --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --pidfile=/var/run/celery/beat.pid \
  --logfile=/var/log/celery/beat.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tulia-celery-beat
sudo systemctl start tulia-celery-beat
sudo systemctl status tulia-celery-beat
```

**Docker Compose:**

Add to `docker-compose.yml`:

```yaml
services:
  celery_beat:
    build: .
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis
    restart: unless-stopped
```

### Monitoring Celery Tasks

**Check task status:**
```bash
# List scheduled tasks
celery -A config inspect scheduled

# List active tasks
celery -A config inspect active

# Check worker status
celery -A config inspect ping
```

**View task logs:**
```bash
# Systemd
sudo journalctl -u tulia-celery-worker -f
sudo journalctl -u tulia-celery-beat -f

# Docker
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat
```


---

## Email Configuration

### Email Templates

The onboarding feature uses email templates for:

1. **Email Verification** - Sent after registration
2. **Password Reset** - Sent when user requests password reset
3. **Onboarding Reminders** - Sent at 3 days and 7 days if onboarding incomplete

### Email Template Customization

Email templates are located in `apps/rbac/templates/emails/` and `apps/tenants/templates/emails/`.

**Verification Email:**
- Template: `apps/rbac/templates/emails/verify_email.html`
- Subject: "Verify Your Email Address - WabotIQ"
- Variables: `user`, `verification_url`, `frontend_url`

**Password Reset Email:**
- Template: `apps/rbac/templates/emails/password_reset.html`
- Subject: "Reset Your Password - WabotIQ"
- Variables: `user`, `reset_url`, `frontend_url`

**Onboarding Reminder Email:**
- Template: `apps/tenants/templates/emails/onboarding_reminder.html`
- Subject: "Complete Your WabotIQ Setup"
- Variables: `tenant`, `completion_percentage`, `pending_steps`, `dashboard_url`

### Testing Email Configuration

**Test email sending:**
```bash
python manage.py shell

from django.core.mail import send_mail

send_mail(
    'Test Email',
    'This is a test email from WabotIQ.',
    'noreply@yourdomain.com',
    ['test@example.com'],
    fail_silently=False,
)
```

**Test verification email:**
```bash
python manage.py shell

from apps.rbac.services import AuthService

user = User.objects.get(email='test@example.com')
AuthService.send_verification_email(user)
```

### Email Provider Setup

#### SendGrid (Recommended)

1. Sign up at [sendgrid.com](https://sendgrid.com)
2. Create an API key with "Mail Send" permissions
3. Configure environment variables:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.your-api-key-here
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

4. Verify sender identity in SendGrid dashboard

#### Mailgun

1. Sign up at [mailgun.com](https://mailgun.com)
2. Add and verify your domain
3. Get SMTP credentials from dashboard
4. Configure environment variables:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@yourdomain.com
EMAIL_HOST_PASSWORD=your-mailgun-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

#### AWS SES

1. Set up AWS SES in your region
2. Verify your domain or email address
3. Create SMTP credentials
4. Configure environment variables:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD=your-smtp-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### Email Deliverability

**Best Practices:**

1. **Verify Domain**: Set up SPF, DKIM, and DMARC records
2. **Use Dedicated IP**: For high-volume sending
3. **Monitor Bounce Rate**: Keep below 5%
4. **Handle Unsubscribes**: Provide unsubscribe links
5. **Warm Up IP**: Gradually increase sending volume
6. **Test Spam Score**: Use tools like mail-tester.com

**SPF Record Example:**
```
v=spf1 include:sendgrid.net ~all
```

**DKIM Setup:**
Follow your email provider's DKIM setup guide.

**DMARC Record Example:**
```
v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```


---

## Deployment Checklist

Use this checklist when deploying the tenant onboarding feature.

### Pre-Deployment

- [ ] **Review Code Changes**
  - [ ] All code reviewed and approved
  - [ ] Tests passing (unit, integration, RBAC)
  - [ ] No security vulnerabilities

- [ ] **Environment Variables**
  - [ ] JWT configuration added
  - [ ] Email configuration added and tested
  - [ ] Frontend URL configured
  - [ ] Stripe keys added (if using payment methods)
  - [ ] All variables added to production environment

- [ ] **Database Backup**
  - [ ] Full database backup created
  - [ ] Backup verified and stored securely
  - [ ] Rollback procedure documented

- [ ] **Migration Review**
  - [ ] Migrations reviewed for safety
  - [ ] Migrations tested on staging
  - [ ] Data migration plan prepared (if needed)

- [ ] **Email Testing**
  - [ ] Email provider configured
  - [ ] Test emails sent successfully
  - [ ] Email templates reviewed
  - [ ] SPF/DKIM/DMARC configured

- [ ] **Celery Configuration**
  - [ ] Celery Beat schedule configured
  - [ ] Celery workers running
  - [ ] Task monitoring set up

### Deployment Steps

1. **Put Application in Maintenance Mode** (if needed)
   ```bash
   # Create maintenance page or use load balancer
   ```

2. **Pull Latest Code**
   ```bash
   cd /opt/tulia-ai
   git fetch origin
   git checkout v1.x.x  # Replace with version tag
   ```

3. **Update Dependencies**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run Database Migrations**
   ```bash
   python manage.py migrate
   ```

5. **Initialize Onboarding for Existing Tenants**
   ```bash
   python manage.py shell
   # Run initialization script (see Data Migration section)
   ```

6. **Collect Static Files**
   ```bash
   python manage.py collectstatic --noinput
   ```

7. **Restart Services**
   ```bash
   sudo systemctl restart tulia-web
   sudo systemctl restart tulia-celery-worker
   sudo systemctl restart tulia-celery-beat
   ```

8. **Verify Health Checks**
   ```bash
   curl http://localhost:8000/v1/health
   ```

9. **Smoke Test Critical Endpoints**
   ```bash
   # Test registration
   curl -X POST http://localhost:8000/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"Test123!","first_name":"Test","last_name":"User","business_name":"Test Corp"}'
   
   # Test login
   curl -X POST http://localhost:8000/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"Test123!"}'
   ```

10. **Remove Maintenance Mode**
    ```bash
    # Remove maintenance page or re-enable in load balancer
    ```

### Post-Deployment

- [ ] **Verify Services**
  - [ ] Web application responding
  - [ ] Celery workers processing tasks
  - [ ] Celery Beat scheduler running
  - [ ] Email sending working

- [ ] **Monitor Logs**
  - [ ] Check application logs for errors
  - [ ] Check Celery logs
  - [ ] Check email delivery logs
  - [ ] Monitor Sentry for errors

- [ ] **Test User Flows**
  - [ ] User registration
  - [ ] Email verification
  - [ ] Login
  - [ ] Tenant creation
  - [ ] Settings configuration
  - [ ] API key generation

- [ ] **Monitor Metrics**
  - [ ] Response times
  - [ ] Error rates
  - [ ] Database performance
  - [ ] Email delivery rates

- [ ] **Update Documentation**
  - [ ] Update API documentation
  - [ ] Update changelog
  - [ ] Update version number
  - [ ] Tag release in Git

- [ ] **Notify Team**
  - [ ] Deployment completed
  - [ ] New features available
  - [ ] Known issues (if any)

### Docker Deployment

For Docker-based deployments:

```bash
# 1. Pull latest images
docker-compose pull

# 2. Stop services
docker-compose down

# 3. Start services with new images
docker-compose up -d

# 4. Run migrations
docker-compose exec web python manage.py migrate

# 5. Initialize onboarding
docker-compose exec web python manage.py shell
# Run initialization script

# 6. Verify health
docker-compose exec web curl http://localhost:8000/v1/health

# 7. Check logs
docker-compose logs -f web
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat
```


---

## Rollback Procedures

If issues are detected after deployment, follow these rollback procedures.

### Quick Rollback (Code Only)

If the issue is in application code and migrations haven't been applied:

```bash
# 1. Put application in maintenance mode

# 2. Checkout previous version
cd /opt/tulia-ai
git checkout v1.x.x-previous  # Replace with previous version

# 3. Restart services
sudo systemctl restart tulia-web
sudo systemctl restart tulia-celery-worker
sudo systemctl restart tulia-celery-beat

# 4. Verify health
curl http://localhost:8000/v1/health

# 5. Remove maintenance mode
```

### Full Rollback (Code + Database)

If migrations have been applied and need to be rolled back:

```bash
# 1. Put application in maintenance mode

# 2. Stop services
sudo systemctl stop tulia-web
sudo systemctl stop tulia-celery-worker
sudo systemctl stop tulia-celery-beat

# 3. Restore database backup
psql -U tulia_user -d tulia_db < backup_20251113_100000.sql

# 4. Checkout previous version
cd /opt/tulia-ai
git checkout v1.x.x-previous

# 5. Verify migrations match database state
python manage.py showmigrations

# 6. Start services
sudo systemctl start tulia-web
sudo systemctl start tulia-celery-worker
sudo systemctl start tulia-celery-beat

# 7. Verify health
curl http://localhost:8000/v1/health

# 8. Remove maintenance mode
```

### Selective Migration Rollback

If only specific migrations need to be rolled back:

```bash
# Rollback User model changes
python manage.py migrate rbac 0001

# Rollback TenantSettings changes
python manage.py migrate tenants 0005

# Verify
python manage.py showmigrations
```

### Docker Rollback

```bash
# 1. Stop services
docker-compose down

# 2. Restore database
docker-compose exec db psql -U tulia_user tulia_db < backup_20251113_100000.sql

# 3. Use previous image tag
# Edit docker-compose.yml to use previous image version

# 4. Start services
docker-compose up -d

# 5. Verify
docker-compose exec web curl http://localhost:8000/v1/health
```

### Rollback Decision Tree

```
Issue Detected
    │
    ├─ Application Error (500s)
    │   ├─ Check logs for stack trace
    │   ├─ If code issue → Quick Rollback
    │   └─ If data issue → Full Rollback
    │
    ├─ Migration Error
    │   ├─ If migration failed → Fix and retry
    │   └─ If migration succeeded but broke app → Full Rollback
    │
    ├─ Email Not Sending
    │   ├─ Check email configuration
    │   ├─ Test with different provider
    │   └─ If critical → Rollback email changes only
    │
    ├─ Celery Tasks Failing
    │   ├─ Check Celery logs
    │   ├─ Restart Celery workers
    │   └─ If persistent → Rollback
    │
    └─ Performance Degradation
        ├─ Check database query performance
        ├─ Check Redis connection
        └─ If severe → Rollback and investigate
```

### Post-Rollback Actions

After rolling back:

1. **Investigate Root Cause**
   - Review logs and error messages
   - Identify what went wrong
   - Document findings

2. **Fix Issues**
   - Create hotfix branch
   - Fix identified issues
   - Test thoroughly on staging

3. **Plan Re-Deployment**
   - Schedule new deployment
   - Update deployment checklist
   - Communicate with team

4. **Monitor Closely**
   - Watch metrics during re-deployment
   - Have rollback plan ready
   - Keep team on standby

---

## Monitoring and Alerts

### Key Metrics to Monitor

After deployment, monitor these metrics:

1. **Registration Metrics**
   - Registration attempts per hour
   - Successful registrations
   - Failed registrations (with reasons)
   - Email verification rate

2. **Authentication Metrics**
   - Login attempts per hour
   - Successful logins
   - Failed logins
   - JWT token generation rate

3. **Onboarding Metrics**
   - Onboarding completion rate
   - Average time to complete onboarding
   - Most common incomplete steps
   - Reminder email open rate

4. **Email Metrics**
   - Emails sent per hour
   - Email delivery rate
   - Bounce rate
   - Open rate (if tracking enabled)

5. **API Metrics**
   - Request rate for new endpoints
   - Response times (p50, p95, p99)
   - Error rates (4xx, 5xx)
   - Rate limit hits

6. **Celery Metrics**
   - Task queue length
   - Task processing time
   - Failed tasks
   - Worker availability

### Alerting Rules

Configure alerts for:

**Critical:**
- Registration endpoint returning 500 errors
- Email sending failing (>10% failure rate)
- Database migration errors
- Celery Beat scheduler stopped

**Warning:**
- Registration rate drops >50%
- Email delivery rate <95%
- Onboarding completion rate <30%
- Response time >2s (p95)

**Info:**
- New user registrations
- Onboarding completions
- API key generations

### Logging

Ensure proper logging for:

```python
# Registration events
logger.info(f"User registered: {user.email}")
logger.error(f"Registration failed: {error}")

# Email events
logger.info(f"Verification email sent to: {user.email}")
logger.error(f"Email sending failed: {error}")

# Onboarding events
logger.info(f"Onboarding step completed: {step} for tenant: {tenant.id}")
logger.warning(f"Onboarding incomplete after 7 days: {tenant.id}")

# API key events
logger.info(f"API key generated for tenant: {tenant.id}")
logger.warning(f"API key revoked: {key_id}")
```

---

## Troubleshooting

### Common Deployment Issues

#### Issue: Migration Fails

**Error:** `django.db.utils.OperationalError: column "email_verified" already exists`

**Solution:**
```bash
# Check if column exists
psql -U tulia_user -d tulia_db -c "\d users"

# If column exists, fake the migration
python manage.py migrate rbac 0002 --fake

# Verify
python manage.py showmigrations
```

#### Issue: Email Not Sending

**Error:** `SMTPAuthenticationError: (535, b'Authentication failed')`

**Solution:**
1. Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
2. Check if email provider requires app-specific password
3. Test SMTP connection:
   ```bash
   telnet smtp.sendgrid.net 587
   ```

#### Issue: Celery Beat Not Running

**Error:** No scheduled tasks executing

**Solution:**
```bash
# Check Celery Beat status
sudo systemctl status tulia-celery-beat

# Check logs
sudo journalctl -u tulia-celery-beat -n 50

# Restart
sudo systemctl restart tulia-celery-beat

# Verify schedule
celery -A config inspect scheduled
```

#### Issue: JWT Token Invalid

**Error:** `Invalid or expired token`

**Solution:**
1. Verify JWT_SECRET_KEY is set correctly
2. Check token expiration settings
3. Ensure clocks are synchronized (NTP)
4. Test token generation:
   ```python
   from apps.rbac.services import AuthService
   user = User.objects.first()
   token = AuthService.generate_jwt(user)
   print(token)
   ```

---

## Additional Resources

- **API Documentation**: `docs/api/TENANT_ONBOARDING_API_GUIDE.md`
- **User Guide**: `docs/guides/TENANT_ONBOARDING_GUIDE.md`
- **Environment Variables**: `docs/ENVIRONMENT_VARIABLES.md`
- **Main Deployment Guide**: `docs/DEPLOYMENT.md`
- **Database Migrations**: `docs/DATABASE_MIGRATIONS.md`

---

## Support

For deployment support:

- **Email**: devops@yourdomain.com
- **Slack**: #tulia-ai-ops
- **On-Call**: PagerDuty rotation

---

**Last Updated**: 2025-11-13
**Version**: 1.0.0
