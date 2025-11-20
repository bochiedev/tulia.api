# Conversational Commerce UX Enhancement - Deployment Checklist

## Pre-Deployment

### Code Review
- [ ] All code reviewed and approved
- [ ] No merge conflicts
- [ ] All tests passing (unit, integration, property-based)
- [ ] Code coverage meets threshold (>80%)
- [ ] No critical security vulnerabilities
- [ ] RBAC enforcement verified on all new endpoints
- [ ] Documentation complete and accurate

### Database Migrations
- [ ] Migration files created and reviewed
- [ ] Migrations tested in staging environment
- [ ] Rollback migrations prepared
- [ ] Data migration scripts tested (if applicable)
- [ ] Database backup completed before migration
- [ ] Migration execution time estimated
- [ ] Downtime window scheduled (if needed)

**Migration Commands**:
```bash
# Check for pending migrations
python manage.py showmigrations

# Test migrations in staging
python manage.py migrate --plan

# Create backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migrations
python manage.py migrate

# Verify migrations
python manage.py showmigrations | grep "\[X\]"
```

### Configuration
- [ ] Environment variables documented in `.env.example`
- [ ] Feature flags configured in settings
- [ ] Default configuration values set
- [ ] Tenant-specific settings reviewed
- [ ] Redis cache configuration verified
- [ ] Celery worker configuration updated
- [ ] Monitoring alerts configured

**Required Environment Variables**:
```bash
# Feature Flags (optional, defaults to True)
ENABLE_MESSAGE_HARMONIZATION=true
ENABLE_IMMEDIATE_PRODUCT_DISPLAY=true
ENABLE_GROUNDED_VALIDATION=true
ENABLE_REFERENCE_RESOLUTION=true

# Configuration
MESSAGE_HARMONIZATION_WAIT_SECONDS=3
MAX_PRODUCTS_TO_SHOW=5
REFERENCE_CONTEXT_TTL_MINUTES=5

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=300
```

### Testing
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] All property-based tests passing
- [ ] Performance tests completed
- [ ] Load testing completed
- [ ] Security testing completed
- [ ] End-to-end conversation flows tested
- [ ] WhatsApp rich message rendering verified
- [ ] Fallback scenarios tested

**Test Execution**:
```bash
# Run all tests
pytest

# Run specific test suites
pytest apps/bot/tests/test_message_harmonization_property.py
pytest apps/bot/tests/test_reference_resolution_property.py
pytest apps/bot/tests/test_integration_all_components.py

# Run with coverage
pytest --cov=apps/bot --cov-report=html

# Run property-based tests with more iterations
pytest apps/bot/tests/ -k "property" --hypothesis-iterations=1000
```

### Staging Deployment
- [ ] Code deployed to staging environment
- [ ] Migrations run successfully in staging
- [ ] Smoke tests passed in staging
- [ ] Manual testing completed in staging
- [ ] Performance metrics acceptable in staging
- [ ] No errors in staging logs
- [ ] Rollback tested in staging

### Documentation
- [ ] API documentation updated
- [ ] User guide created
- [ ] Admin guide created
- [ ] Deployment checklist created (this document)
- [ ] Rollback plan documented
- [ ] Runbook updated
- [ ] Changelog updated

### Stakeholder Communication
- [ ] Product team notified of deployment
- [ ] Support team trained on new features
- [ ] Customer success team briefed
- [ ] Deployment window communicated
- [ ] Rollback criteria defined
- [ ] On-call engineer assigned

## Deployment Steps

### 1. Pre-Deployment Verification (T-1 hour)

**Checklist**:
- [ ] All pre-deployment items completed
- [ ] Deployment window confirmed
- [ ] Team members available
- [ ] Rollback plan reviewed
- [ ] Monitoring dashboards open
- [ ] Communication channels ready

**Commands**:
```bash
# Verify current production state
python manage.py check --deploy

# Check database connectivity
python manage.py dbshell -c "SELECT 1;"

# Verify Redis connectivity
redis-cli ping

# Check Celery workers
celery -A config inspect active
```

### 2. Database Backup (T-30 minutes)

**Checklist**:
- [ ] Full database backup completed
- [ ] Backup verified and downloadable
- [ ] Backup location documented
- [ ] Backup retention policy confirmed

**Commands**:
```bash
# Create backup
BACKUP_FILE="backup_ux_enhancement_$(date +%Y%m%d_%H%M%S).sql"
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -F c -f $BACKUP_FILE

# Verify backup
pg_restore --list $BACKUP_FILE | head -20

# Upload to S3 (if applicable)
aws s3 cp $BACKUP_FILE s3://wabot-backups/production/

# Document backup location
echo "Backup: s3://wabot-backups/production/$BACKUP_FILE" >> deployment_log.txt
```

### 3. Enable Maintenance Mode (T-15 minutes)

**Checklist**:
- [ ] Maintenance page enabled
- [ ] Users notified of maintenance
- [ ] Webhook processing paused
- [ ] Celery workers gracefully stopped

**Commands**:
```bash
# Enable maintenance mode
python manage.py maintenance_mode on

# Stop Celery workers gracefully
celery -A config control shutdown

# Verify no active tasks
celery -A config inspect active
```

### 4. Deploy Code (T-10 minutes)

**Checklist**:
- [ ] Latest code pulled from repository
- [ ] Dependencies installed
- [ ] Static files collected
- [ ] Code ownership verified

**Commands**:
```bash
# Pull latest code
git fetch origin
git checkout main
git pull origin main

# Verify correct version
git log -1 --oneline

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Verify file permissions
chown -R www-data:www-data /app
```

### 5. Run Migrations (T-5 minutes)

**Checklist**:
- [ ] Migrations executed successfully
- [ ] No migration errors
- [ ] Database schema verified
- [ ] Data integrity confirmed

**Commands**:
```bash
# Show migration plan
python manage.py migrate --plan

# Run migrations
python manage.py migrate

# Verify migrations
python manage.py showmigrations | grep "\[X\]"

# Check for any issues
python manage.py check
```

### 6. Update Configuration (T-3 minutes)

**Checklist**:
- [ ] Feature flags enabled
- [ ] Default configurations set
- [ ] Cache cleared
- [ ] Configuration verified

**Commands**:
```bash
# Clear cache
python manage.py clear_cache

# Set default configurations
python manage.py configure_ux_features --enable-all

# Verify configuration
python manage.py show_ux_config
```

### 7. Restart Services (T-2 minutes)

**Checklist**:
- [ ] Application server restarted
- [ ] Celery workers restarted
- [ ] Services health checked
- [ ] No startup errors

**Commands**:
```bash
# Restart application server (example for gunicorn)
sudo systemctl restart gunicorn

# Restart Celery workers
celery -A config worker --loglevel=info --detach

# Restart Celery beat (if applicable)
celery -A config beat --loglevel=info --detach

# Verify services
sudo systemctl status gunicorn
celery -A config inspect ping
```

### 8. Disable Maintenance Mode (T-1 minute)

**Checklist**:
- [ ] All services running
- [ ] Health checks passing
- [ ] Maintenance mode disabled
- [ ] Users can access system

**Commands**:
```bash
# Disable maintenance mode
python manage.py maintenance_mode off

# Verify application is accessible
curl -I https://api.wabotiq.com/v1/health
```

### 9. Smoke Tests (T+5 minutes)

**Checklist**:
- [ ] Health endpoint responding
- [ ] Authentication working
- [ ] Message processing working
- [ ] Product queries working
- [ ] Rich messages rendering
- [ ] Reference resolution working
- [ ] No critical errors in logs

**Commands**:
```bash
# Health check
curl https://api.wabotiq.com/v1/health

# Test message processing
python manage.py test_bot_message --tenant-id=<test_tenant_id>

# Test product discovery
python manage.py test_product_discovery --tenant-id=<test_tenant_id>

# Check logs for errors
tail -f /var/log/wabot/application.log | grep ERROR
```

### 10. Monitoring Verification (T+15 minutes)

**Checklist**:
- [ ] Application metrics normal
- [ ] Error rate acceptable (<1%)
- [ ] Response times acceptable (<500ms)
- [ ] No critical alerts
- [ ] Database performance normal
- [ ] Cache hit rate acceptable (>80%)

**Dashboards to Check**:
- Application Performance Monitoring (APM)
- Error tracking (Sentry)
- Database metrics (CloudWatch/Datadog)
- Cache metrics (Redis)
- Business metrics (conversation completion rate)

## Post-Deployment

### Immediate Verification (T+30 minutes)

**Checklist**:
- [ ] All smoke tests passing
- [ ] No critical errors in logs
- [ ] Monitoring metrics stable
- [ ] User feedback positive
- [ ] Support tickets normal
- [ ] Performance acceptable

**Metrics to Monitor**:
```python
# Check feature usage
from apps.bot.models import MessageHarmonizationLog, ReferenceContext

# Message harmonization usage
harmonizations = MessageHarmonizationLog.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=1)
).count()
print(f"Harmonizations in last hour: {harmonizations}")

# Reference resolution usage
contexts = ReferenceContext.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=1)
).count()
print(f"Reference contexts created: {contexts}")
```

### Short-Term Monitoring (T+2 hours)

**Checklist**:
- [ ] Conversation completion rate stable
- [ ] No increase in error rate
- [ ] Response times acceptable
- [ ] Feature adoption tracking
- [ ] Customer feedback collected
- [ ] Support team reports no issues

**Key Metrics**:
- Message harmonization success rate: >95%
- Reference resolution success rate: >90%
- Product discovery empty results: <10%
- Language consistency score: >95%
- Grounding validation failure rate: <5%
- Rich message usage rate: >80%

### Medium-Term Monitoring (T+24 hours)

**Checklist**:
- [ ] All metrics stable
- [ ] No performance degradation
- [ ] Feature usage as expected
- [ ] Customer satisfaction maintained
- [ ] No rollback needed
- [ ] Documentation accurate

**Analysis**:
```python
# Analyze feature impact
from apps.analytics.models import AnalyticsDaily

# Compare metrics before/after deployment
before = AnalyticsDaily.objects.filter(
    date__range=[deployment_date - timedelta(days=7), deployment_date]
).aggregate(
    avg_completion_rate=Avg('conversation_completion_rate'),
    avg_response_time=Avg('avg_response_time_ms')
)

after = AnalyticsDaily.objects.filter(
    date__range=[deployment_date, deployment_date + timedelta(days=7)]
).aggregate(
    avg_completion_rate=Avg('conversation_completion_rate'),
    avg_response_time=Avg('avg_response_time_ms')
)

print(f"Completion rate change: {after['avg_completion_rate'] - before['avg_completion_rate']:.2%}")
print(f"Response time change: {after['avg_response_time'] - before['avg_response_time']:.0f}ms")
```

### Long-Term Monitoring (T+1 week)

**Checklist**:
- [ ] Feature adoption measured
- [ ] Business impact assessed
- [ ] Customer feedback analyzed
- [ ] Performance optimizations identified
- [ ] Documentation updated based on learnings
- [ ] Team retrospective completed

**Success Criteria**:
- Conversation completion rate increased by >10%
- Average conversation length decreased by >20%
- Customer satisfaction score maintained or improved
- Support ticket volume stable or decreased
- No critical bugs reported

## Rollback Plan

### Rollback Triggers

Initiate rollback if:
- Critical bugs affecting >10% of users
- Error rate >5% for >15 minutes
- Response time >2 seconds for >15 minutes
- Data corruption detected
- Security vulnerability discovered
- Business metrics degraded >20%

### Rollback Procedure

#### Quick Rollback (Feature Flags)

**Time**: 5 minutes

**Steps**:
1. Disable problematic features via feature flags
2. Clear cache
3. Verify issue resolved
4. Monitor metrics

**Commands**:
```bash
# Disable all new features
python manage.py configure_ux_features --disable-all-enhancements

# Clear cache
python manage.py clear_cache

# Restart services
sudo systemctl restart gunicorn
celery -A config control shutdown
celery -A config worker --loglevel=info --detach

# Verify
curl https://api.wabotiq.com/v1/health
```

#### Full Rollback (Code + Database)

**Time**: 30 minutes

**Steps**:
1. Enable maintenance mode
2. Stop services
3. Restore database backup
4. Revert code to previous version
5. Restart services
6. Verify functionality
7. Disable maintenance mode

**Commands**:
```bash
# Enable maintenance mode
python manage.py maintenance_mode on

# Stop services
sudo systemctl stop gunicorn
celery -A config control shutdown

# Restore database
BACKUP_FILE="backup_ux_enhancement_20250120_140000.sql"
pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -c $BACKUP_FILE

# Revert code
git checkout <previous_commit_hash>
pip install -r requirements.txt
python manage.py collectstatic --noinput

# Restart services
sudo systemctl start gunicorn
celery -A config worker --loglevel=info --detach

# Disable maintenance mode
python manage.py maintenance_mode off

# Verify
curl https://api.wabotiq.com/v1/health
python manage.py test_bot_message --tenant-id=<test_tenant_id>
```

### Post-Rollback

**Checklist**:
- [ ] Services restored to previous state
- [ ] Metrics returned to normal
- [ ] Users notified of rollback
- [ ] Root cause analysis initiated
- [ ] Incident report created
- [ ] Fix plan developed

## Emergency Contacts

### On-Call Engineers
- Primary: [Name] - [Phone] - [Email]
- Secondary: [Name] - [Phone] - [Email]
- Escalation: [Name] - [Phone] - [Email]

### Key Stakeholders
- Engineering Lead: [Name] - [Email]
- Product Manager: [Name] - [Email]
- Customer Success: [Name] - [Email]
- Support Lead: [Name] - [Email]

### External Services
- AWS Support: [Account ID] - [Support Plan]
- Twilio Support: [Account SID] - [Support Level]
- Database Provider: [Contact Info]

## Deployment Log Template

```markdown
# Deployment Log - Conversational Commerce UX Enhancement

**Date**: YYYY-MM-DD
**Time**: HH:MM UTC
**Version**: vX.Y.Z
**Deployed By**: [Name]

## Pre-Deployment
- [ ] All checklist items completed
- [ ] Backup created: [Location]
- [ ] Team notified: [Time]

## Deployment Timeline
- T-30: Backup completed
- T-15: Maintenance mode enabled
- T-10: Code deployed
- T-5: Migrations run
- T-0: Services restarted
- T+1: Maintenance mode disabled
- T+5: Smoke tests passed
- T+15: Monitoring verified

## Issues Encountered
[None / List any issues]

## Rollback Performed
[No / Yes - Reason]

## Post-Deployment Status
- Error Rate: X%
- Response Time: Xms
- Conversation Completion Rate: X%
- Feature Usage: X conversations

## Notes
[Any additional notes or observations]

## Sign-Off
- Engineering: [Name] - [Time]
- Product: [Name] - [Time]
```

## Appendix

### Useful Commands

**Check Application Status**:
```bash
# Application health
curl https://api.wabotiq.com/v1/health

# Database connectivity
python manage.py dbshell -c "SELECT 1;"

# Redis connectivity
redis-cli ping

# Celery workers
celery -A config inspect active
```

**View Logs**:
```bash
# Application logs
tail -f /var/log/wabot/application.log

# Error logs
tail -f /var/log/wabot/error.log

# Celery logs
tail -f /var/log/wabot/celery.log

# Filter for specific errors
grep "ERROR" /var/log/wabot/application.log | tail -50
```

**Monitor Metrics**:
```bash
# Database connections
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT count(*) FROM pg_stat_activity;"

# Redis memory usage
redis-cli info memory

# Application memory usage
ps aux | grep gunicorn | awk '{sum+=$6} END {print sum/1024 " MB"}'
```

### Configuration Files

**Feature Flags** (`config/settings.py`):
```python
# UX Enhancement Feature Flags
UX_ENHANCEMENT_FEATURES = {
    'message_harmonization': env.bool('ENABLE_MESSAGE_HARMONIZATION', True),
    'immediate_product_display': env.bool('ENABLE_IMMEDIATE_PRODUCT_DISPLAY', True),
    'grounded_validation': env.bool('ENABLE_GROUNDED_VALIDATION', True),
    'reference_resolution': env.bool('ENABLE_REFERENCE_RESOLUTION', True),
}

# Configuration
MESSAGE_HARMONIZATION_WAIT_SECONDS = env.int('MESSAGE_HARMONIZATION_WAIT_SECONDS', 3)
MAX_PRODUCTS_TO_SHOW = env.int('MAX_PRODUCTS_TO_SHOW', 5)
REFERENCE_CONTEXT_TTL_MINUTES = env.int('REFERENCE_CONTEXT_TTL_MINUTES', 5)
```

### Monitoring Queries

**Feature Usage**:
```sql
-- Message harmonization usage
SELECT 
    DATE(created_at) as date,
    COUNT(*) as harmonizations,
    AVG(ARRAY_LENGTH(message_ids, 1)) as avg_messages_combined,
    AVG(wait_time_ms) as avg_wait_time_ms
FROM bot_messageharmonizationlog
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Reference resolution usage
SELECT 
    DATE(created_at) as date,
    list_type,
    COUNT(*) as contexts_created,
    COUNT(CASE WHEN expires_at > NOW() THEN 1 END) as active_contexts
FROM bot_referencecontext
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), list_type
ORDER BY date DESC, list_type;
```

**Performance Metrics**:
```sql
-- Average response times
SELECT 
    DATE(created_at) as date,
    AVG(response_time_ms) as avg_response_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_response_time,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99_response_time
FROM messaging_message
WHERE created_at >= NOW() - INTERVAL '7 days'
    AND direction = 'outbound'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

## Sign-Off

**Deployment Approved By**:
- Engineering Lead: _________________ Date: _______
- Product Manager: _________________ Date: _______
- DevOps Lead: _________________ Date: _______

**Deployment Completed By**:
- Engineer: _________________ Date: _______ Time: _______

**Post-Deployment Verification**:
- Engineer: _________________ Date: _______ Time: _______
- QA: _________________ Date: _______ Time: _______
