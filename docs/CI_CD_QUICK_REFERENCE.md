# CI/CD Quick Reference

## Quick Setup (5 Minutes)

### 1. Generate Secrets
```bash
./scripts/setup_ci_secrets.sh
```

### 2. Add Secrets to Platform

**GitHub Actions:**
```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

**GitLab CI:**
```
Project → Settings → CI/CD → Variables → Add variable
```

### 3. Create Environments (GitHub Only)

**Staging:**
- Name: `staging`
- Protection: None (auto-deploy)
- Branch: `develop`

**Production:**
- Name: `production`
- Protection: Required reviewers
- Branch: `main`, tags `v*`

## Essential Secrets

### Minimum Required (for CI tests)
```bash
SECRET_KEY=<generate-with-script>
JWT_SECRET_KEY=<generate-with-script>
ENCRYPTION_KEY=<generate-with-script>
OPENAI_API_KEY=<your-key>
```

### Staging Deployment
```bash
STAGING_HOST=<server-ip>
STAGING_USER=<ssh-user>
STAGING_SSH_KEY=<private-key>
STAGING_SECRET_KEY=<generate>
STAGING_JWT_SECRET_KEY=<generate>
STAGING_ENCRYPTION_KEY=<generate>
STAGING_DATABASE_URL=<postgres-url>
STAGING_REDIS_URL=<redis-url>
```

### Production Deployment
```bash
PRODUCTION_HOST=<server-ip>
PRODUCTION_USER=<ssh-user>
PRODUCTION_SSH_KEY=<private-key>
PRODUCTION_SECRET_KEY=<generate>
PRODUCTION_JWT_SECRET_KEY=<generate>
PRODUCTION_ENCRYPTION_KEY=<generate>
PRODUCTION_DATABASE_URL=<postgres-url>
PRODUCTION_REDIS_URL=<redis-url>
```

## Common Commands

### Generate Keys
```bash
# All keys at once
python scripts/generate_secrets.py

# Individual keys
python -c "import secrets; print(secrets.token_urlsafe(50))"  # SECRET_KEY
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"  # ENCRYPTION_KEY
```

### Test CI Locally
```bash
# Run tests
pytest --cov=apps

# Check code quality
flake8 apps config
black --check apps config

# Security scan
bandit -r apps config
```

### Manual Deployment
```bash
# GitHub Actions
Actions → Deploy to Staging/Production → Run workflow

# GitLab CI
CI/CD → Pipelines → Run pipeline → Select branch
```

## Troubleshooting

### Tests Fail in CI
```bash
# Check environment variables are set
# Verify database connection
# Check Redis connection
# Review test logs in CI output
```

### Deployment Fails
```bash
# SSH into server
ssh user@server

# Check logs
cd /opt/tulia-ai
docker-compose -f docker-compose.prod.yml logs

# Verify .env file
cat .env | grep SECRET_KEY

# Test health endpoint
curl http://localhost:8000/v1/health
```

### Secrets Not Loading
```bash
# Verify secret name matches exactly
# Check environment scope (staging/production)
# Ensure no trailing spaces in secret values
# Restart deployment after updating secrets
```

## Deployment Flow

### Staging
```
1. Push to develop branch
2. CI tests run automatically
3. If tests pass, deploy to staging
4. Verify at staging URL
```

### Production
```
1. Merge develop to main (or create tag)
2. CI tests run automatically
3. Manual approval required (GitHub)
4. Database backup created
5. Deploy to production
6. Smoke tests run
7. Notification sent
```

## Security Checklist

- [ ] All secrets use environment variables (no hardcoded values)
- [ ] Different keys for each environment
- [ ] SSH keys are unique per environment
- [ ] Production requires manual approval
- [ ] Secrets are masked in CI logs
- [ ] .env files are in .gitignore
- [ ] Secrets file deleted after setup
- [ ] Team members have appropriate access levels

## Support

- Full documentation: `docs/CI_CD_SETUP.md`
- Security guide: `docs/SECURITY_BEST_PRACTICES.md`
- Deployment guide: `docs/DEPLOYMENT.md`
