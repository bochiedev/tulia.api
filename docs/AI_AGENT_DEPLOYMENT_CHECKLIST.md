# AI Agent Deployment Checklist

## Overview

This checklist ensures a smooth deployment of the AI-powered customer service agent to production. Follow each section carefully and verify all items before proceeding to the next phase.

## Deployment Phases

1. [Pre-Deployment](#pre-deployment)
2. [Environment Configuration](#environment-configuration)
3. [Database Migrations](#database-migrations)
4. [Cache Setup](#cache-setup)
5. [Monitoring Setup](#monitoring-setup)
6. [Testing](#testing)
7. [Gradual Rollout](#gradual-rollout)
8. [Post-Deployment](#post-deployment)
9. [Rollback Procedures](#rollback-procedures)

---

## Pre-Deployment

### Code Review
- [ ] All code changes reviewed and approved
- [ ] Unit tests passing (100% for new code)
- [ ] Integration tests passing
- [ ] Performance tests completed
- [ ] Security audit completed
- [ ] RBAC enforcement verified on all endpoints
- [ ] Multi-tenant isolation verified

### Documentation
- [ ] API documentation updated
- [ ] Tenant onboarding guide created
- [ ] Deployment checklist reviewed
- [ ] Runbook updated with new procedures
- [ ] Changelog updated

### Dependencies
- [ ] All Python dependencies installed (`requirements.txt`)
- [ ] OpenAI Python SDK installed (`openai>=1.0.0`)
- [ ] Redis available for caching
- [ ] PostgreSQL version compatible (12+)
- [ ] Celery workers configured

### Backup
- [ ] Database backup completed
- [ ] Configuration backup saved
- [ ] Rollback plan documented
- [ ] Recovery time objective (RTO) defined
- [ ] Recovery point objective (RPO) defined

---

## Environment Configuration

### Required Environment Variables

#### OpenAI Configuration
```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-...

# OpenAI Organization ID (optional)
OPENAI_ORG_ID=org-...

# Default model (optional, defaults to gpt-4o)
DEFAULT_AI_MODEL=gpt-4o
```

#### Together AI Configuration (Optional)
```bash
# Together AI API Key (if using Together AI)
TOGETHER_API_KEY=...

# Together AI Base URL
TOGETHER_BASE_URL=https://api.together.xyz
```

#### Feature Flags
```bash
# Enable AI agent globally (default: true)
AI_AGENT_ENABLED=true

# Enable AI agent per tenant (checked at runtime)
# Controlled via TenantSettings.is_feature_enabled('ai_agent_enabled')
```

#### Cache Configuration
```bash
# Redis URL for caching
REDIS_URL=redis://localhost:6379/0

# Cache TTL for agent configuration (seconds, default: 300)
AGENT_CONFIG_CACHE_TTL=300

# Cache TTL for knowledge base (seconds, default: 60)
KNOWLEDGE_CACHE_TTL=60

# Cache TTL for catalog data (seconds, default: 60)
CATALOG_CACHE_TTL=60
```

#### Performance Configuration
```bash
# Max context window size (tokens)
MAX_CONTEXT_WINDOW=128000

# Default temperature
DEFAULT_TEMPERATURE=0.7

# Max retries for LLM API calls
LLM_MAX_RETRIES=3

# Timeout for LLM API calls (seconds)
LLM_TIMEOUT=30
```

#### Monitoring Configuration
```bash
# Sentry DSN for error tracking
SENTRY_DSN=https://...

# Enable structured logging
STRUCTURED_LOGGING=true

# Log level
LOG_LEVEL=INFO
```

### Verification Commands

```bash
# Verify environment variables
python manage.py check_env_vars

# Test OpenAI connection
python -c "from openai import OpenAI; client = OpenAI(); print(client.models.list())"

# Test Redis connection
redis-cli ping

# Test database connection
python manage.py dbshell
```

### Checklist
- [ ] All required environment variables set
- [ ] OpenAI API key valid and tested
- [ ] Together AI configured (if using)
- [ ] Redis connection verified
- [ ] Database connection verified
- [ ] Feature flags configured
- [ ] Cache TTLs appropriate for load
- [ ] Monitoring configured

---

## Database Migrations

### Migration Files

Verify these migrations exist:

```bash
# Agent Configuration
apps/bot/migrations/0003_add_agent_configuration.py

# Knowledge Base
apps/bot/migrations/0004_add_knowledge_entry.py

# Conversation Context
apps/bot/migrations/0005_add_conversation_context.py

# Agent Interactions
apps/bot/migrations/0006_add_agent_interaction_model.py

# Message Queue
apps/bot/migrations/0007_add_message_queue.py

# Together AI Support
apps/tenants/migrations/0012_add_together_ai_configuration.py
```

### Pre-Migration Checks

```bash
# Check for pending migrations
python manage.py showmigrations bot
python manage.py showmigrations tenants

# Verify migration plan
python manage.py sqlmigrate bot 0003
python manage.py sqlmigrate bot 0004
python manage.py sqlmigrate bot 0005
python manage.py sqlmigrate bot 0006
python manage.py sqlmigrate bot 0007

# Check for migration conflicts
python manage.py makemigrations --check --dry-run
```

### Run Migrations

```bash
# Backup database first!
pg_dump -U postgres -d wabotiq > backup_pre_ai_agent.sql

# Run migrations
python manage.py migrate bot
python manage.py migrate tenants

# Verify migrations applied
python manage.py showmigrations bot
python manage.py showmigrations tenants
```

### Post-Migration Verification

```bash
# Verify tables created
python manage.py dbshell
\dt bot_*

# Check indexes
\di bot_*

# Verify constraints
\d bot_agentconfiguration
\d bot_knowledgeentry
\d bot_conversationcontext
\d bot_agentinteraction
\d bot_messagequeue
```

### Checklist
- [ ] Database backup completed
- [ ] All migrations identified
- [ ] Migration plan reviewed
- [ ] Migrations executed successfully
- [ ] Tables created with correct schema
- [ ] Indexes created
- [ ] Foreign keys established
- [ ] No migration errors in logs

---

## Cache Setup

### Redis Configuration

```bash
# Install Redis (if not already installed)
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server

# Or as service
sudo systemctl start redis
sudo systemctl enable redis
```

### Cache Verification

```bash
# Test Redis connection
redis-cli ping
# Expected: PONG

# Check Redis info
redis-cli info

# Test cache operations
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test_key', 'test_value', 60)
>>> cache.get('test_key')
'test_value'
>>> cache.delete('test_key')
```

### Cache Warming (Optional)

```bash
# Pre-populate cache with agent configurations
python manage.py warm_agent_cache

# Pre-populate knowledge base embeddings
python manage.py warm_knowledge_cache
```

### Checklist
- [ ] Redis installed and running
- [ ] Redis connection verified
- [ ] Cache operations tested
- [ ] Cache TTLs configured
- [ ] Cache warming completed (if applicable)
- [ ] Redis persistence configured
- [ ] Redis memory limits set

---

## Monitoring Setup

### Sentry Configuration

```python
# config/settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
    ],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    environment=os.getenv('ENVIRONMENT', 'production'),
)
```

### Logging Configuration

```python
# config/settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/ai_agent.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'apps.bot': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Metrics to Monitor

1. **Response Time**
   - p50, p95, p99 latency
   - Target: <3s for p95

2. **Error Rate**
   - LLM API errors
   - Database errors
   - Cache errors
   - Target: <1%

3. **Cost Metrics**
   - Token usage per conversation
   - Cost per conversation
   - Daily/monthly spend

4. **Agent Performance**
   - Average confidence score
   - Handoff rate
   - Knowledge base hit rate

5. **System Health**
   - Celery queue length
   - Redis memory usage
   - Database connection pool

### Alerting Rules

```yaml
# Example alerting configuration
alerts:
  - name: high_error_rate
    condition: error_rate > 5%
    duration: 5m
    severity: critical
    
  - name: slow_response_time
    condition: p95_latency > 5s
    duration: 10m
    severity: warning
    
  - name: high_cost
    condition: daily_cost > $100
    duration: 1h
    severity: warning
    
  - name: high_handoff_rate
    condition: handoff_rate > 20%
    duration: 30m
    severity: warning
```

### Checklist
- [ ] Sentry configured and tested
- [ ] Structured logging enabled
- [ ] Log rotation configured
- [ ] Metrics collection enabled
- [ ] Dashboards created
- [ ] Alerts configured
- [ ] On-call rotation defined
- [ ] Runbook updated

---

## Testing

### Unit Tests

```bash
# Run all bot tests
pytest apps/bot/tests/ -v

# Run specific test categories
pytest apps/bot/tests/test_llm_providers.py -v
pytest apps/bot/tests/test_agent_configuration.py -v
pytest apps/bot/tests/test_knowledge_base_service.py -v
pytest apps/bot/tests/test_context_builder_service.py -v
pytest apps/bot/tests/test_fuzzy_matcher_service.py -v

# Check coverage
pytest apps/bot/tests/ --cov=apps.bot --cov-report=html
```

### Integration Tests

```bash
# Run integration tests
pytest apps/bot/tests/test_integration_e2e.py -v

# Test full message flow
pytest apps/bot/tests/test_integration_e2e.py::test_full_message_flow -v

# Test knowledge base integration
pytest apps/bot/tests/test_knowledge_base_api.py -v
```

### API Tests

```bash
# Test agent configuration endpoints
curl -X GET http://localhost:8000/v1/bot/agent-config \
  -H "X-TENANT-ID: <test-tenant-id>" \
  -H "X-TENANT-API-KEY: <test-api-key>"

# Test knowledge base endpoints
curl -X GET http://localhost:8000/v1/bot/knowledge \
  -H "X-TENANT-ID: <test-tenant-id>" \
  -H "X-TENANT-API-KEY: <test-api-key>"

# Test analytics endpoints
curl -X GET http://localhost:8000/v1/bot/analytics/conversations \
  -H "X-TENANT-ID: <test-tenant-id>" \
  -H "X-TENANT-API-KEY: <test-api-key>"
```

### Performance Tests

```bash
# Load test with locust
locust -f tests/load/ai_agent_load_test.py --host=http://localhost:8000

# Stress test
ab -n 1000 -c 10 -H "X-TENANT-ID: <test-tenant-id>" \
   -H "X-TENANT-API-KEY: <test-api-key>" \
   http://localhost:8000/v1/bot/agent-config
```

### End-to-End Tests

```bash
# Test complete customer journey
python tests/e2e/test_customer_journey.py

# Test scenarios:
# 1. Customer asks FAQ question
# 2. Customer asks about product
# 3. Customer requests human agent
# 4. Customer sends multiple messages
# 5. Customer returns after pause
```

### Checklist
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] API endpoints tested
- [ ] Performance tests completed
- [ ] Load tests show acceptable performance
- [ ] End-to-end scenarios verified
- [ ] RBAC enforcement tested
- [ ] Multi-tenant isolation verified
- [ ] Error handling tested
- [ ] Rollback tested

---

## Gradual Rollout

### Phase 1: Internal Testing (Week 1)

**Scope**: Internal demo tenant only

```bash
# Enable for demo tenant
python manage.py toggle_ai_agent --tenant-id=<demo-tenant-id> --enable
```

**Checklist**:
- [ ] Demo tenant configured
- [ ] Knowledge base populated
- [ ] Internal team testing
- [ ] No critical issues found
- [ ] Performance acceptable
- [ ] Costs within budget

### Phase 2: Beta Testing (Week 2-3)

**Scope**: 5-10 selected beta tenants

```bash
# Enable for beta tenants
for tenant_id in <beta-tenant-ids>; do
  python manage.py toggle_ai_agent --tenant-id=$tenant_id --enable
done
```

**Checklist**:
- [ ] Beta tenants selected
- [ ] Beta tenants onboarded
- [ ] Knowledge bases configured
- [ ] Daily monitoring
- [ ] Feedback collected
- [ ] Issues addressed
- [ ] Performance metrics good

### Phase 3: Limited Rollout (Week 4-5)

**Scope**: 10% of tenants

```bash
# Enable for 10% of tenants
python manage.py rollout_ai_agent --percentage=10
```

**Checklist**:
- [ ] 10% rollout completed
- [ ] Monitoring dashboards reviewed daily
- [ ] No significant issues
- [ ] Cost tracking on target
- [ ] Handoff rates acceptable
- [ ] Customer feedback positive

### Phase 4: Expanded Rollout (Week 6-7)

**Scope**: 50% of tenants

```bash
# Enable for 50% of tenants
python manage.py rollout_ai_agent --percentage=50
```

**Checklist**:
- [ ] 50% rollout completed
- [ ] System performance stable
- [ ] Costs within projections
- [ ] No critical issues
- [ ] Support tickets manageable

### Phase 5: Full Rollout (Week 8+)

**Scope**: 100% of tenants

```bash
# Enable for all tenants
python manage.py rollout_ai_agent --percentage=100
```

**Checklist**:
- [ ] 100% rollout completed
- [ ] All systems stable
- [ ] Monitoring in place
- [ ] Support team trained
- [ ] Documentation complete

---

## Post-Deployment

### Immediate (Day 1)

- [ ] Verify all tenants can access agent configuration
- [ ] Check error rates in Sentry
- [ ] Monitor response times
- [ ] Review first 100 interactions
- [ ] Check cost tracking
- [ ] Verify cache hit rates

### Short-term (Week 1)

- [ ] Review analytics daily
- [ ] Monitor handoff rates
- [ ] Track cost trends
- [ ] Collect tenant feedback
- [ ] Address any issues
- [ ] Update documentation as needed

### Medium-term (Month 1)

- [ ] Comprehensive performance review
- [ ] Cost analysis and optimization
- [ ] Feature usage analysis
- [ ] Tenant satisfaction survey
- [ ] Knowledge base effectiveness review
- [ ] Identify improvement opportunities

### Long-term (Month 3+)

- [ ] Quarterly performance review
- [ ] Cost optimization initiatives
- [ ] Feature enhancements based on feedback
- [ ] Scale planning
- [ ] Documentation updates
- [ ] Team training updates

---

## Rollback Procedures

### Immediate Rollback (Critical Issues)

If critical issues are discovered:

```bash
# Disable AI agent globally
export AI_AGENT_ENABLED=false

# Or disable per tenant
python manage.py toggle_ai_agent --tenant-id=<tenant-id> --disable

# Restart services
sudo systemctl restart gunicorn
sudo systemctl restart celery
```

### Database Rollback

If database issues occur:

```bash
# Stop services
sudo systemctl stop gunicorn
sudo systemctl stop celery

# Restore database backup
psql -U postgres -d wabotiq < backup_pre_ai_agent.sql

# Rollback migrations
python manage.py migrate bot 0002  # Before AI agent migrations
python manage.py migrate tenants 0011  # Before Together AI

# Restart services
sudo systemctl start gunicorn
sudo systemctl start celery
```

### Partial Rollback

If issues affect specific tenants:

```bash
# Disable for affected tenants only
python manage.py toggle_ai_agent --tenant-id=<tenant-id> --disable

# Tenants fall back to legacy intent system automatically
```

### Rollback Checklist

- [ ] Issue severity assessed
- [ ] Rollback decision made
- [ ] Stakeholders notified
- [ ] Rollback procedure executed
- [ ] Services restarted
- [ ] Functionality verified
- [ ] Monitoring confirmed
- [ ] Post-mortem scheduled

---

## Troubleshooting

### Common Issues

#### Issue: LLM API Errors

**Symptoms**: 500 errors, "OpenAI API error" in logs

**Solutions**:
1. Verify API key is valid
2. Check API rate limits
3. Verify network connectivity
4. Check OpenAI status page
5. Enable fallback models

#### Issue: High Response Times

**Symptoms**: >5s response times

**Solutions**:
1. Check LLM API latency
2. Verify cache is working
3. Optimize knowledge base queries
4. Check database performance
5. Review context size

#### Issue: Cache Misses

**Symptoms**: High database load, slow responses

**Solutions**:
1. Verify Redis is running
2. Check cache TTLs
3. Warm cache after deployment
4. Review cache key generation
5. Monitor Redis memory

#### Issue: High Costs

**Symptoms**: Costs exceed projections

**Solutions**:
1. Review token usage per interaction
2. Optimize knowledge base
3. Switch to cheaper models
4. Implement cost limits
5. Review context size

---

## Success Criteria

### Technical Metrics

- [ ] Response time p95 < 3 seconds
- [ ] Error rate < 1%
- [ ] Cache hit rate > 80%
- [ ] Database query time < 100ms
- [ ] Celery queue length < 100

### Business Metrics

- [ ] Handoff rate < 10%
- [ ] Average confidence > 0.75
- [ ] Cost per conversation < $0.02
- [ ] Customer satisfaction > 4/5
- [ ] Knowledge base coverage > 80%

### Operational Metrics

- [ ] Zero critical incidents
- [ ] Mean time to recovery < 1 hour
- [ ] Support ticket volume stable
- [ ] Team trained and confident
- [ ] Documentation complete

---

## Sign-off

### Pre-Deployment Sign-off

- [ ] Engineering Lead: _______________
- [ ] Product Manager: _______________
- [ ] DevOps Lead: _______________
- [ ] QA Lead: _______________

### Post-Deployment Sign-off

- [ ] Engineering Lead: _______________
- [ ] Product Manager: _______________
- [ ] Customer Success: _______________
- [ ] Support Lead: _______________

---

## Additional Resources

- **API Documentation**: `/docs/api/AI_AGENT_API_GUIDE.md`
- **Onboarding Guide**: `/docs/guides/AI_AGENT_ONBOARDING_GUIDE.md`
- **Runbook**: `/docs/AI_AGENT_RUNBOOK.md`
- **Architecture**: `.kiro/specs/ai-powered-customer-service-agent/design.md`

---

**Deployment Date**: _______________  
**Deployed By**: _______________  
**Version**: _______________
