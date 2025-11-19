# Multi-Provider LLM & Feedback System Quick Start Guide

## Overview

This guide covers the new multi-provider LLM support and feedback collection system implemented in Tasks 38-39.

## Multi-Provider LLM Support

### Supported Providers

1. **OpenAI**
   - GPT-4o (balanced performance)
   - GPT-4o Mini (cost-effective)
   - O1 Preview (complex reasoning)
   - O1 Mini (reasoning, cost-effective)

2. **Gemini** (NEW)
   - Gemini 1.5 Pro (1M context window, advanced tasks)
   - Gemini 1.5 Flash (1M context window, fast & cheap)

3. **Together AI**
   - Llama, Mistral, and other open-source models

### Cost Comparison

| Provider | Model | Cost per 1K tokens | Best For |
|----------|-------|-------------------|----------|
| Gemini | Flash | $0.0001875 | Simple queries (97% cheaper!) |
| OpenAI | GPT-4o Mini | $0.000375 | Simple queries |
| Gemini | Pro | $0.003125 | Large context (1M tokens) |
| OpenAI | GPT-4o | $0.00625 | Balanced performance |
| OpenAI | O1 Mini | $0.0075 | Reasoning tasks |
| OpenAI | O1 Preview | $0.0375 | Complex reasoning |

### Smart Routing

The system automatically routes queries to the optimal provider based on:

1. **Query Complexity** (0.0-1.0 score):
   - Conversation length
   - Message length
   - Complex keywords (analyze, compare, calculate, etc.)
   - Question complexity

2. **Context Size**:
   - >100K tokens → Gemini Pro (1M context window)

3. **Routing Rules**:
   - Complexity < 0.3 → Gemini Flash (cheapest)
   - Complexity > 0.7 → OpenAI O1 Preview (best reasoning)
   - Default → OpenAI GPT-4o (balanced)

### Configuration

#### 1. Add Gemini API Key to Tenant Settings

```python
from apps.tenants.models import TenantSettings

# Get or create tenant settings
settings = tenant.settings

# Add Gemini API key
settings.gemini_api_key = "your-gemini-api-key-here"
settings.save()
```

#### 2. Configure Routing (Optional)

```python
# Custom routing configuration
routing_config = {
    'simple_queries': {
        'provider': 'gemini',
        'model': 'gemini-1.5-flash',
        'reason': 'Cost optimization'
    },
    'large_context': {
        'provider': 'gemini',
        'model': 'gemini-1.5-pro',
        'reason': '1M token context'
    },
    'complex_reasoning': {
        'provider': 'openai',
        'model': 'o1-preview',
        'reason': 'Best reasoning'
    },
    'default': {
        'provider': 'openai',
        'model': 'gpt-4o',
        'reason': 'Balanced'
    }
}

settings.routing_config = routing_config
settings.save()
```

### Usage Example

```python
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.llm.provider_router import ProviderRouter
from apps.bot.services.llm.failover_manager import ProviderFailoverManager

# Create router
router = ProviderRouter()

# Route query
messages = [
    {'role': 'system', 'content': 'You are a helpful assistant'},
    {'role': 'user', 'content': 'What is 2+2?'}
]

decision = router.route(messages)
print(f"Using {decision.provider}/{decision.model}")
print(f"Reason: {decision.reason}")
print(f"Complexity: {decision.complexity_score:.2f}")

# Create provider with failover
factory = LLMProviderFactory()
failover = ProviderFailoverManager()

response, provider_used, model_used = failover.execute_with_failover(
    provider_factory=factory,
    tenant=tenant,
    messages=messages,
    primary_provider=decision.provider,
    primary_model=decision.model,
    temperature=0.7,
    max_tokens=1000
)

print(f"Response: {response.content}")
print(f"Cost: ${response.estimated_cost}")
print(f"Tokens: {response.total_tokens}")
```

### Automatic Failover

The system automatically fails over to backup providers if the primary fails:

1. **Default Fallback Order**:
   - OpenAI GPT-4o
   - Gemini 1.5 Pro
   - OpenAI GPT-4o Mini
   - Gemini 1.5 Flash

2. **Health Tracking**:
   - Tracks success/failure rates per provider
   - Marks providers unhealthy if failure rate >50%
   - Skips unhealthy providers in failover

3. **Timeout**: 30 seconds per provider attempt

### Cost & Performance Tracking

All provider usage is automatically tracked:

```python
from apps.bot.models_provider_tracking import ProviderUsage, ProviderDailySummary

# Get usage for tenant
usage = ProviderUsage.objects.for_tenant(tenant)

# Get today's summary
from datetime import date
summary = ProviderDailySummary.objects.filter(
    tenant=tenant,
    date=date.today()
)

for s in summary:
    print(f"{s.provider}/{s.model}:")
    print(f"  Calls: {s.total_calls}")
    print(f"  Cost: ${s.total_cost}")
    print(f"  Success Rate: {s.success_rate:.2%}")
    print(f"  Avg Latency: {s.avg_latency_ms:.0f}ms")
```

### Celery Tasks

Schedule these tasks in your celery beat configuration:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Daily aggregation at 1 AM
    'aggregate-provider-usage': {
        'task': 'bot.aggregate_provider_daily_summary',
        'schedule': crontab(hour=1, minute=0),
    },
    
    # Weekly cleanup on Sunday at 2 AM
    'cleanup-provider-usage': {
        'task': 'bot.cleanup_old_provider_usage',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),
    },
    
    # Hourly health check
    'provider-health-check': {
        'task': 'bot.calculate_provider_health_metrics',
        'schedule': crontab(minute=0),
    },
}
```

## Feedback Collection System

### Features

1. **Explicit Feedback**:
   - Thumbs up/down ratings
   - Optional text comments

2. **Implicit Signals**:
   - User continued conversation
   - Completed action (purchase/booking)
   - Requested human handoff
   - Response time (engagement)

3. **Human Corrections**:
   - Capture bot errors
   - Store corrected responses
   - Training approval workflow
   - Quality scoring

### API Endpoints

#### 1. Submit Feedback (Public)

```bash
POST /v1/bot/feedback/submit/
Content-Type: application/json

{
  "agent_interaction_id": 123,
  "rating": "helpful",
  "feedback_text": "Great response, very helpful!"
}
```

#### 2. Get Feedback Analytics

```bash
GET /v1/bot/feedback/analytics/?days=30
X-TENANT-ID: <tenant-id>
X-TENANT-API-KEY: <api-key>

Response:
{
  "total_feedback": 150,
  "helpful_count": 120,
  "not_helpful_count": 30,
  "helpful_rate": 0.80,
  "avg_implicit_score": 0.75,
  "feedback_with_comments": 45,
  "user_continued_rate": 0.85,
  "completed_action_rate": 0.60,
  "requested_human_rate": 0.10
}
```

#### 3. Create Human Correction

```bash
POST /v1/bot/corrections/
X-TENANT-ID: <tenant-id>
X-TENANT-API-KEY: <api-key>
Content-Type: application/json

{
  "agent_interaction": 123,
  "conversation": 456,
  "bot_response": "I don't know about that product.",
  "human_response": "That product is our bestseller! It's available in 3 colors...",
  "correction_reason": "Bot failed to find product in catalog",
  "correction_category": "missing_information"
}
```

#### 4. Approve Correction for Training

```bash
POST /v1/bot/corrections/123/approve/
X-TENANT-ID: <tenant-id>
X-TENANT-API-KEY: <api-key>
Content-Type: application/json

{
  "approved": true,
  "quality_score": 4.5
}
```

#### 5. Get Approved Corrections

```bash
GET /v1/bot/corrections/approved/
X-TENANT-ID: <tenant-id>
X-TENANT-API-KEY: <api-key>

Response: List of corrections approved for training
```

### Usage in Code

```python
from apps.bot.models_feedback import InteractionFeedback, HumanCorrection

# Record feedback
feedback = InteractionFeedback.objects.create(
    tenant=tenant,
    agent_interaction=interaction,
    conversation=conversation,
    customer=customer,
    rating='helpful',
    feedback_text='Very helpful!',
    user_continued=True,
    completed_action=True,
    response_time_seconds=15
)

# Calculate implicit satisfaction
score = feedback.implicit_satisfaction_score
print(f"Implicit satisfaction: {score:.2f}")

# Create correction
correction = HumanCorrection.objects.create(
    tenant=tenant,
    agent_interaction=interaction,
    conversation=conversation,
    bot_response="I don't know.",
    human_response="Here's the answer...",
    correction_reason="Bot lacked knowledge",
    correction_category='missing_information',
    corrected_by=human_agent
)

# Approve for training
correction.approved_for_training = True
correction.approved_by = supervisor
correction.approved_at = timezone.now()
correction.quality_score = 4.5
correction.save()
```

### WhatsApp Integration (Coming Soon)

```python
from apps.bot.services.rich_message_builder import RichMessageBuilder

# Add feedback buttons to response
builder = RichMessageBuilder(tenant)

message = builder.build_button_message(
    body="Here's the information you requested...",
    buttons=[
        {'id': 'feedback_helpful', 'title': '👍 Helpful'},
        {'id': 'feedback_not_helpful', 'title': '👎 Not Helpful'},
    ]
)

# Handle button click in webhook
if button_id == 'feedback_helpful':
    InteractionFeedback.objects.create(
        tenant=tenant,
        agent_interaction=interaction,
        conversation=conversation,
        customer=customer,
        rating='helpful',
        feedback_source='whatsapp_button'
    )
```

## Expected Cost Savings

With smart routing to Gemini Flash for simple queries:

- **Before**: 100% OpenAI GPT-4o at $0.00625/1K tokens
- **After**: 
  - 60% Gemini Flash at $0.0001875/1K tokens
  - 30% OpenAI GPT-4o at $0.00625/1K tokens
  - 10% OpenAI O1 at $0.0375/1K tokens

**Expected Savings: 60-70% of LLM costs**

## Monitoring

### Provider Health

```python
from apps.bot.services.llm.failover_manager import ProviderFailoverManager

failover = ProviderFailoverManager()
health = failover.get_provider_health()

for provider, stats in health.items():
    print(f"{provider}:")
    print(f"  Success Rate: {stats['success_rate']:.2%}")
    print(f"  Total Calls: {stats['total_calls']}")
    print(f"  Healthy: {stats['is_healthy']}")
```

### Daily Costs

```python
from apps.bot.models_provider_tracking import ProviderDailySummary
from datetime import date, timedelta

# Last 7 days
start = date.today() - timedelta(days=7)
summaries = ProviderDailySummary.objects.filter(
    tenant=tenant,
    date__gte=start
).order_by('date')

for summary in summaries:
    print(f"{summary.date} - {summary.provider}/{summary.model}:")
    print(f"  Cost: ${summary.total_cost}")
    print(f"  Calls: {summary.total_calls}")
    print(f"  Avg Latency: {summary.avg_latency_ms:.0f}ms")
```

## Troubleshooting

### Provider Failures

If a provider consistently fails:

1. Check API key configuration
2. Check provider health status
3. Review error logs
4. Reset provider stats if needed:

```python
failover.reset_provider_stats('gemini')
```

### High Costs

If costs are higher than expected:

1. Review routing configuration
2. Check complexity scoring
3. Analyze provider usage distribution
4. Adjust routing thresholds

### Low Feedback Collection

If feedback rate is low:

1. Enable feedback prompts in tenant settings
2. Add feedback buttons to more responses
3. Make feedback submission easier
4. Incentivize feedback (optional)

## Next Steps

1. **Configure Gemini API key** for your tenant
2. **Run migrations** to create tracking tables
3. **Schedule Celery tasks** for aggregation
4. **Monitor costs** and adjust routing as needed
5. **Collect feedback** to improve bot quality
6. **Review corrections** and approve for training

## Support

For issues or questions:
- Check logs in `apps/bot/services/llm/`
- Review provider health metrics
- Contact development team
