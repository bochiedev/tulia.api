# Conversational Commerce UX Enhancement - Rollback Plan

## Overview

This document provides detailed procedures for rolling back the Conversational Commerce UX Enhancement feature in case of critical issues. The rollback plan includes multiple strategies based on severity and time constraints.

## Rollback Strategies

### Strategy 1: Feature Flag Rollback (Fastest)
**Time**: 5 minutes  
**Risk**: Low  
**Use When**: Feature-specific issues, no data corruption

### Strategy 2: Configuration Rollback
**Time**: 10 minutes  
**Risk**: Low  
**Use When**: Configuration issues, no code bugs

### Strategy 3: Code Rollback (No Database Changes)
**Time**: 20 minutes  
**Risk**: Medium  
**Use When**: Code bugs, database schema unchanged

### Strategy 4: Full Rollback (Code + Database)
**Time**: 30-60 minutes  
**Risk**: High  
**Use When**: Critical bugs, data corruption, schema issues

## Rollback Triggers

### Critical Triggers (Immediate Rollback)

Initiate immediate rollback if:
- **Error Rate**: >5% for >15 minutes
- **Response Time**: >2 seconds (p95) for >15 minutes
- **Data Corruption**: Any evidence of data loss or corruption
- **Security Issue**: Security vulnerability discovered
- **Service Outage**: Complete service failure
- **User Impact**: >10% of users unable to use core features

### Warning Triggers (Evaluate for Rollback)

Consider rollback if:
- **Error Rate**: 2-5% for >30 minutes
- **Response Time**: 1-2 seconds (p95) for >30 minutes
- **Feature Failure**: Specific feature failing for >50% of attempts
- **Business Metrics**: Conversation completion rate drops >20%
- **Customer Complaints**: Significant increase in support tickets

### Monitoring Alerts

**Critical Alerts** (Auto-page on-call):
```yaml
- name: High Error Rate
  condition: error_rate > 5%
  duration: 15 minutes
  action: Page on-call engineer

- name: Slow Response Time
  condition: p95_response_time > 2000ms
  duration: 15 minutes
  action: Page on-call engineer

- name: Service Down
  condition: health_check_failed
  duration: 5 minutes
  action: Page on-call engineer
```

**Warning Alerts** (Notify team):
```yaml
- name: Elevated Error Rate
  condition: error_rate > 2%
  duration: 30 minutes
  action: Notify team channel

- name: Degraded Performance
  condition: p95_response_time > 1000ms
  duration: 30 minutes
  action: Notify team channel
```

## Strategy 1: Feature Flag Rollback

### When to Use
- Specific feature causing issues
- No database schema changes needed
- Quick mitigation required
- Issues isolated to new functionality

### Procedure

#### Step 1: Identify Problematic Feature (2 minutes)

**Check Logs**:
```bash
# Check recent errors
tail -1000 /var/log/wabot/application.log | grep ERROR

# Check specific feature errors
grep "MessageHarmonizationService" /var/log/wabot/application.log | tail -50
grep "ReferenceContextManager" /var/log/wabot/application.log | tail -50
grep "GroundedResponseValidator" /var/log/wabot/application.log | tail -50
```

**Check Metrics**:
```python
# Check feature-specific metrics
from apps.bot.models import MessageHarmonizationLog

# Recent harmonization failures
failures = MessageHarmonizationLog.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=1),
    status='failed'
).count()

print(f"Harmonization failures in last hour: {failures}")
```

#### Step 2: Disable Problematic Feature (1 minute)

**Via Management Command**:
```bash
# Disable message harmonization
python manage.py configure_ux_features --disable-harmonization

# Disable immediate product display
python manage.py configure_ux_features --disable-immediate-display

# Disable grounded validation
python manage.py configure_ux_features --disable-grounded-validation

# Disable reference resolution
python manage.py configure_ux_features --disable-reference-resolution

# Disable all enhancements
python manage.py configure_ux_features --disable-all-enhancements
```

**Via Django Admin**:
1. Navigate to `/admin/bot/agentconfiguration/`
2. Select all configurations
3. Use bulk action: "Disable [feature name]"
4. Confirm action

**Via Python**:
```python
from apps.bot.models import AgentConfiguration

# Disable for all tenants
AgentConfiguration.objects.all().update(
    enable_message_harmonization=False
)

# Disable for specific tenant
config = AgentConfiguration.objects.get(tenant=tenant)
config.enable_message_harmonization = False
config.save()
```

#### Step 3: Clear Cache (1 minute)

```bash
# Clear Redis cache
redis-cli FLUSHDB

# Clear Django cache
python manage.py clear_cache

# Restart cache-dependent services
sudo systemctl restart gunicorn
```

#### Step 4: Verify Resolution (1 minute)

```bash
# Check health endpoint
curl https://api.wabotiq.com/v1/health

# Test message processing
python manage.py test_bot_message --tenant-id=<test_tenant_id>

# Check error rate
tail -100 /var/log/wabot/application.log | grep ERROR | wc -l
```

#### Step 5: Monitor (Ongoing)

**Metrics to Watch**:
- Error rate should drop to <1%
- Response time should return to normal (<500ms)
- Conversation completion rate should stabilize
- No new critical errors

**Duration**: Monitor for 30 minutes before declaring success

### Rollback Verification

**Success Criteria**:
- [ ] Error rate <1%
- [ ] Response time <500ms (p95)
- [ ] No critical errors in logs
- [ ] User reports normal functionality
- [ ] Business metrics stable

**If Issues Persist**: Proceed to Strategy 2 or 3

## Strategy 2: Configuration Rollback

### When to Use
- Configuration changes causing issues
- Feature flags insufficient
- No code changes needed
- Database schema unchanged

### Procedure

#### Step 1: Backup Current Configuration (2 minutes)

```bash
# Export current configuration
python manage.py dumpdata bot.AgentConfiguration > config_backup_$(date +%Y%m%d_%H%M%S).json

# Verify backup
cat config_backup_*.json | jq '.[] | select(.model == "bot.agentconfiguration") | .fields' | head -20
```

#### Step 2: Restore Previous Configuration (3 minutes)

**From Backup File**:
```bash
# Restore from backup
python manage.py loaddata config_backup_pre_deployment.json

# Verify restoration
python manage.py show_ux_config
```

**Manual Restoration**:
```python
from apps.bot.models import AgentConfiguration

# Reset to default values
AgentConfiguration.objects.all().update(
    enable_message_harmonization=True,
    harmonization_wait_seconds=3,
    enable_immediate_product_display=True,
    max_products_to_show=5,
    enable_grounded_validation=True,
    enable_reference_resolution=True,
    use_business_name_as_identity=True,
    custom_bot_greeting=''
)
```

#### Step 3: Clear Cache and Restart (3 minutes)

```bash
# Clear cache
redis-cli FLUSHDB
python manage.py clear_cache

# Restart services
sudo systemctl restart gunicorn
celery -A config control shutdown
celery -A config worker --loglevel=info --detach
```

#### Step 4: Verify and Monitor (2 minutes)

```bash
# Verify configuration
python manage.py show_ux_config

# Test functionality
python manage.py test_bot_message --tenant-id=<test_tenant_id>

# Monitor logs
tail -f /var/log/wabot/application.log | grep ERROR
```

## Strategy 3: Code Rollback (No Database Changes)

### When to Use
- Code bugs identified
- Database schema unchanged
- Feature flags insufficient
- Configuration rollback insufficient

### Procedure

#### Step 1: Enable Maintenance Mode (2 minutes)

```bash
# Enable maintenance mode
python manage.py maintenance_mode on

# Verify maintenance page
curl -I https://api.wabotiq.com/

# Notify users
python manage.py send_maintenance_notification
```

#### Step 2: Stop Services (2 minutes)

```bash
# Stop application server
sudo systemctl stop gunicorn

# Stop Celery workers gracefully
celery -A config control shutdown

# Verify no active tasks
celery -A config inspect active

# Wait for tasks to complete (max 2 minutes)
sleep 120
```

#### Step 3: Revert Code (5 minutes)

```bash
# Identify previous stable version
git log --oneline -10

# Checkout previous version
PREVIOUS_COMMIT="<commit_hash_before_deployment>"
git checkout $PREVIOUS_COMMIT

# Verify correct version
git log -1 --oneline

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Verify file permissions
chown -R www-data:www-data /app
```

#### Step 4: Restart Services (3 minutes)

```bash
# Start application server
sudo systemctl start gunicorn

# Verify application started
sudo systemctl status gunicorn

# Start Celery workers
celery -A config worker --loglevel=info --detach

# Start Celery beat
celery -A config beat --loglevel=info --detach

# Verify workers
celery -A config inspect ping
```

#### Step 5: Disable Maintenance Mode (1 minute)

```bash
# Disable maintenance mode
python manage.py maintenance_mode off

# Verify application accessible
curl https://api.wabotiq.com/v1/health
```

#### Step 6: Verify and Monitor (5 minutes)

```bash
# Run smoke tests
python manage.py test_bot_message --tenant-id=<test_tenant_id>
python manage.py test_product_discovery --tenant-id=<test_tenant_id>

# Check logs
tail -100 /var/log/wabot/application.log | grep ERROR

# Monitor metrics
# - Error rate
# - Response time
# - Conversation completion rate
```

### Rollback Verification

**Success Criteria**:
- [ ] Application accessible
- [ ] Smoke tests passing
- [ ] Error rate <1%
- [ ] Response time normal
- [ ] No critical errors
- [ ] User functionality restored

## Strategy 4: Full Rollback (Code + Database)

### When to Use
- Critical bugs with data corruption
- Database schema issues
- Migration failures
- Complete feature removal needed

### ⚠️ WARNING
This is the most disruptive rollback strategy. Only use when absolutely necessary.

### Procedure

#### Step 1: Assess Situation (5 minutes)

**Questions to Answer**:
- What is the extent of data corruption?
- Can we recover without full rollback?
- What is the acceptable data loss window?
- Are there any in-flight transactions?

**Check Database State**:
```sql
-- Check for data corruption
SELECT COUNT(*) FROM bot_messageharmonizationlog WHERE message_ids IS NULL;
SELECT COUNT(*) FROM bot_referencecontext WHERE items IS NULL;

-- Check migration status
SELECT * FROM django_migrations WHERE app = 'bot' ORDER BY applied DESC LIMIT 10;

-- Check for orphaned records
SELECT COUNT(*) FROM bot_referencecontext WHERE conversation_id NOT IN (SELECT id FROM messaging_conversation);
```

#### Step 2: Enable Maintenance Mode (2 minutes)

```bash
# Enable maintenance mode
python manage.py maintenance_mode on

# Notify all users
python manage.py send_emergency_notification --message="System maintenance in progress. Service will be restored shortly."
```

#### Step 3: Stop All Services (3 minutes)

```bash
# Stop application server
sudo systemctl stop gunicorn

# Stop Celery workers immediately
celery -A config control shutdown

# Stop Celery beat
pkill -f "celery beat"

# Verify all stopped
ps aux | grep -E "(gunicorn|celery)"
```

#### Step 4: Backup Current Database (10 minutes)

```bash
# Create backup of current state (for forensics)
BACKUP_FILE="backup_rollback_$(date +%Y%m%d_%H%M%S).sql"
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -F c -f $BACKUP_FILE

# Verify backup
pg_restore --list $BACKUP_FILE | head -20

# Upload to S3
aws s3 cp $BACKUP_FILE s3://wabot-backups/production/rollbacks/
```

#### Step 5: Restore Database (15 minutes)

```bash
# Identify pre-deployment backup
RESTORE_FILE="backup_ux_enhancement_20250120_140000.sql"

# Download from S3 if needed
aws s3 cp s3://wabot-backups/production/$RESTORE_FILE .

# Restore database
pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -c $RESTORE_FILE

# Verify restoration
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM django_migrations WHERE app = 'bot';"
```

#### Step 6: Revert Code (5 minutes)

```bash
# Checkout previous stable version
PREVIOUS_COMMIT="<commit_hash_before_deployment>"
git checkout $PREVIOUS_COMMIT

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput
```

#### Step 7: Verify Database Integrity (5 minutes)

```bash
# Run Django checks
python manage.py check

# Verify migrations
python manage.py showmigrations

# Test database connectivity
python manage.py dbshell -c "SELECT 1;"

# Run data integrity checks
python manage.py check_data_integrity
```

#### Step 8: Restart Services (3 minutes)

```bash
# Start application server
sudo systemctl start gunicorn

# Start Celery workers
celery -A config worker --loglevel=info --detach

# Start Celery beat
celery -A config beat --loglevel=info --detach

# Verify all services
sudo systemctl status gunicorn
celery -A config inspect ping
```

#### Step 9: Disable Maintenance Mode (1 minute)

```bash
# Disable maintenance mode
python manage.py maintenance_mode off

# Verify application accessible
curl https://api.wabotiq.com/v1/health
```

#### Step 10: Comprehensive Verification (10 minutes)

```bash
# Run full test suite
pytest apps/bot/tests/ -v

# Run smoke tests
python manage.py test_bot_message --tenant-id=<test_tenant_id>
python manage.py test_product_discovery --tenant-id=<test_tenant_id>
python manage.py test_conversation_flow --tenant-id=<test_tenant_id>

# Verify data integrity
python manage.py check_data_integrity --verbose

# Check logs
tail -200 /var/log/wabot/application.log | grep ERROR
```

### Data Loss Assessment

After full rollback, assess data loss:

```python
from django.utils import timezone
from datetime import timedelta

# Calculate data loss window
deployment_time = timezone.datetime(2025, 1, 20, 14, 0, 0)
rollback_time = timezone.now()
data_loss_window = rollback_time - deployment_time

print(f"Data loss window: {data_loss_window}")

# Check affected conversations
from apps.messaging.models import Conversation, Message

affected_conversations = Conversation.objects.filter(
    updated_at__gte=deployment_time,
    updated_at__lte=rollback_time
)

print(f"Affected conversations: {affected_conversations.count()}")

# Check lost messages
lost_messages = Message.objects.filter(
    created_at__gte=deployment_time,
    created_at__lte=rollback_time
)

print(f"Lost messages: {lost_messages.count()}")
```

### Post-Rollback Data Recovery

If possible, recover lost data:

```bash
# Extract data from rollback backup
pg_restore -h $DB_HOST -U $DB_USER -d temp_recovery_db -C $BACKUP_FILE

# Export lost data
psql -h $DB_HOST -U $DB_USER -d temp_recovery_db -c "
  COPY (
    SELECT * FROM messaging_message 
    WHERE created_at >= '2025-01-20 14:00:00'
  ) TO '/tmp/lost_messages.csv' CSV HEADER;
"

# Review and selectively import
python manage.py import_lost_messages /tmp/lost_messages.csv --dry-run
python manage.py import_lost_messages /tmp/lost_messages.csv --confirm
```

## Post-Rollback Actions

### Immediate Actions (Within 1 hour)

1. **Verify System Stability**
   - [ ] Monitor error rates for 1 hour
   - [ ] Verify all core functionality working
   - [ ] Check business metrics
   - [ ] Review customer feedback

2. **Communication**
   - [ ] Notify stakeholders of rollback
   - [ ] Update status page
   - [ ] Inform support team
   - [ ] Prepare customer communication

3. **Incident Documentation**
   - [ ] Create incident report
   - [ ] Document timeline
   - [ ] Capture logs and metrics
   - [ ] Identify root cause

### Short-Term Actions (Within 24 hours)

1. **Root Cause Analysis**
   - [ ] Analyze what went wrong
   - [ ] Identify contributing factors
   - [ ] Document lessons learned
   - [ ] Create action items

2. **Fix Development**
   - [ ] Develop fix for identified issues
   - [ ] Add additional tests
   - [ ] Update deployment procedures
   - [ ] Plan re-deployment

3. **Process Improvements**
   - [ ] Update rollback procedures
   - [ ] Improve monitoring
   - [ ] Enhance testing
   - [ ] Update documentation

### Long-Term Actions (Within 1 week)

1. **Incident Review**
   - [ ] Conduct team retrospective
   - [ ] Share learnings organization-wide
   - [ ] Update runbooks
   - [ ] Improve alerting

2. **Re-Deployment Planning**
   - [ ] Develop comprehensive fix
   - [ ] Create detailed test plan
   - [ ] Plan phased rollout
   - [ ] Prepare enhanced monitoring

## Rollback Decision Matrix

| Severity | Impact | Response Time | Strategy | Approval Required |
|----------|--------|---------------|----------|-------------------|
| Critical | >10% users | Immediate | Feature Flag | On-call engineer |
| High | 5-10% users | <15 min | Feature Flag or Config | Engineering lead |
| Medium | 2-5% users | <30 min | Config or Code | Engineering lead + PM |
| Low | <2% users | <1 hour | Evaluate, may not rollback | Team decision |

## Communication Templates

### Internal Alert (Slack/Email)

```
🚨 ROLLBACK IN PROGRESS 🚨

Feature: Conversational Commerce UX Enhancement
Strategy: [Feature Flag / Configuration / Code / Full]
Reason: [Brief description]
Impact: [User impact description]
ETA: [Estimated completion time]
Status: [In Progress / Completed]

On-call: @engineer
Incident Commander: @lead

Updates will be posted every 15 minutes.
```

### Customer Communication

```
Subject: Service Update - Brief Maintenance Completed

Dear WabotIQ Customer,

We recently performed emergency maintenance on our platform to address a technical issue. The maintenance has been completed and all services are now fully operational.

Impact: [Brief description of what users may have experienced]
Duration: [Start time] to [End time]
Resolution: [What was done]

We apologize for any inconvenience this may have caused. If you continue to experience any issues, please contact our support team at support@wabotiq.com.

Thank you for your patience and understanding.

The WabotIQ Team
```

### Status Page Update

```
[RESOLVED] Emergency Maintenance

We performed emergency maintenance to address a technical issue affecting message processing. All services have been restored and are operating normally.

Timeline:
- [Time]: Issue detected
- [Time]: Rollback initiated
- [Time]: Services restored
- [Time]: Verification completed

If you continue to experience issues, please contact support.
```

## Rollback Checklist

### Pre-Rollback
- [ ] Rollback trigger confirmed
- [ ] Rollback strategy selected
- [ ] Incident commander assigned
- [ ] Team notified
- [ ] Stakeholders notified
- [ ] Backup verified available

### During Rollback
- [ ] Maintenance mode enabled (if needed)
- [ ] Services stopped (if needed)
- [ ] Rollback executed
- [ ] Services restarted
- [ ] Maintenance mode disabled
- [ ] Verification completed

### Post-Rollback
- [ ] System stability confirmed
- [ ] Metrics returned to normal
- [ ] Users notified
- [ ] Incident documented
- [ ] Root cause analysis initiated
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
- Database Provider: [Contact Info]
- Monitoring Service: [Contact Info]

## Appendix

### Useful Queries

**Check System Health**:
```sql
-- Recent error rate
SELECT 
    DATE_TRUNC('minute', created_at) as minute,
    COUNT(*) FILTER (WHERE level = 'ERROR') as errors,
    COUNT(*) as total
FROM logs
WHERE created_at >= NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;

-- Response time percentiles
SELECT 
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY response_time_ms) as p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99
FROM messaging_message
WHERE created_at >= NOW() - INTERVAL '1 hour'
    AND direction = 'outbound';
```

### Rollback Log Template

```markdown
# Rollback Log

**Date**: YYYY-MM-DD HH:MM UTC
**Feature**: Conversational Commerce UX Enhancement
**Strategy**: [Feature Flag / Configuration / Code / Full]
**Executed By**: [Name]

## Trigger
**Reason**: [Description]
**Metrics**: [Error rate, response time, etc.]
**User Impact**: [Description]

## Timeline
- [Time]: Issue detected
- [Time]: Rollback decision made
- [Time]: Rollback initiated
- [Time]: [Key steps]
- [Time]: Rollback completed
- [Time]: Verification completed

## Actions Taken
1. [Action 1]
2. [Action 2]
3. [Action 3]

## Verification
- [ ] Error rate normal
- [ ] Response time normal
- [ ] Functionality restored
- [ ] No data loss
- [ ] Users notified

## Data Loss
**Window**: [Start] to [End]
**Affected**: [Number] conversations, [Number] messages
**Recovery**: [Possible / Not possible / Partial]

## Root Cause
[Brief description - full RCA to follow]

## Next Steps
1. [Action 1]
2. [Action 2]
3. [Action 3]

## Sign-Off
- Incident Commander: _________________ Time: _______
- Engineering Lead: _________________ Time: _______
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-20  
**Owner**: Engineering Team  
**Review Frequency**: After each rollback or quarterly
