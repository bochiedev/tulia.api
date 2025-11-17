# AI Agent Monitoring and Observability

Comprehensive monitoring system for the AI-powered customer service agent, providing structured logging, metrics collection, and alerting capabilities.

## Overview

The monitoring system consists of four main components:

1. **Structured Logger** - JSON-formatted logging for all agent operations
2. **Metrics Collector** - Real-time metrics aggregation and analysis
3. **Alert Manager** - Threshold-based alerting system
4. **Integration Module** - Unified interface for easy integration

## Features

### Structured Logging

- JSON-formatted logs for easy parsing and analysis
- Comprehensive event tracking:
  - Agent interactions with full context
  - LLM API calls and responses
  - Context building steps
  - Handoff decisions with reasons
  - Knowledge base searches
  - Errors with full context

### Metrics Collection

- **Response Time Metrics**: p50, p95, p99 percentiles
- **Token Usage**: Total, prompt, and completion tokens per conversation
- **Cost Tracking**: Per conversation, per token, and by model
- **Handoff Metrics**: Rate and breakdown by reason
- **Knowledge Base Metrics**: Hit rate and average similarity scores
- **Model Usage**: Distribution and cost breakdown

### Alerting

- Configurable thresholds for:
  - Slow response times (p95, p99)
  - High costs per conversation
  - High handoff rates
  - Low knowledge base hit rates
  - High error rates
- Cooldown periods to prevent alert fatigue
- Multiple alert handlers (logging, Sentry, custom)

## Usage

### Basic Integration

```python
from apps.bot.services.monitoring import get_agent_monitor

# Get monitor instance for a tenant
monitor = get_agent_monitor(tenant_id=str(tenant.id))

# Log and record a complete interaction
monitor.log_and_record_interaction(
    conversation_id=str(conversation.id),
    customer_message=message.text,
    agent_response=response.content,
    model_used=response.model_used,
    confidence_score=response.confidence_score,
    processing_time_ms=response.processing_time_ms,
    token_usage={
        'prompt_tokens': response.input_tokens,
        'completion_tokens': response.output_tokens,
        'total_tokens': response.total_tokens
    },
    estimated_cost=response.estimated_cost,
    handoff_triggered=response.should_handoff,
    handoff_reason=response.handoff_reason,
    message_type='text',
    context_size_tokens=context.context_size_tokens,
    context_truncated=context.truncated
)
```

### Logging Individual Operations

```python
# Log LLM API call
monitor.log_and_record_llm_call(
    conversation_id=str(conversation.id),
    provider='openai',
    model='gpt-4o',
    prompt_tokens=1000,
    completion_tokens=200,
    total_tokens=1200,
    estimated_cost=Decimal('0.015'),
    response_time_ms=1500,
    success=True
)

# Log context building
monitor.log_context_building(
    conversation_id=str(conversation.id),
    context_data={
        'history_count': 10,
        'knowledge_count': 3,
        'products_count': 5,
        'services_count': 2,
        'orders_count': 1,
        'appointments_count': 0,
        'context_size_tokens': 5000,
        'truncated': False
    },
    build_time_ms=250
)

# Log handoff decision
monitor.log_handoff_decision(
    conversation_id=str(conversation.id),
    should_handoff=True,
    reason='consecutive_low_confidence',
    confidence_score=0.65,
    consecutive_low_confidence=3
)

# Log knowledge search
monitor.log_knowledge_search(
    conversation_id=str(conversation.id),
    query="return policy",
    results_count=3,
    top_similarity_score=0.85,
    search_time_ms=120
)

# Log error
monitor.log_error(
    conversation_id=str(conversation.id),
    error_type='llm_api_error',
    error_message='API timeout',
    operation='generate_response'
)
```

### Accessing Metrics

```python
# Get current metrics summary
metrics = monitor.get_metrics_summary()

# Access specific metrics
print(f"P95 Response Time: {metrics['response_time']['p95_ms']}ms")
print(f"Average Cost: ${metrics['cost']['avg_per_conversation_usd']:.4f}")
print(f"Handoff Rate: {metrics['handoff']['handoff_rate']*100:.1f}%")
print(f"Knowledge Hit Rate: {metrics['knowledge_base']['hit_rate']*100:.1f}%")

# Get model usage distribution
for model, stats in metrics['model_usage'].items():
    print(f"{model}: {stats['count']} calls, ${stats['total_cost']:.2f}")
```

### Custom Alert Handlers

```python
from apps.bot.services.monitoring.alerting import get_alert_manager, Alert

def send_slack_alert(alert: Alert):
    """Send alert to Slack."""
    # Your Slack integration code here
    pass

# Register custom handler
alert_manager = get_alert_manager(tenant_id=str(tenant.id))
alert_manager.register_handler(send_slack_alert)

# Add custom threshold
from apps.bot.services.monitoring.alerting import AlertThreshold

custom_threshold = AlertThreshold(
    name='very_high_cost',
    metric_path='cost.total_usd',
    operator='gt',
    threshold_value=100.0,
    severity='critical',
    description='Total cost exceeds $100',
    cooldown_minutes=60
)
alert_manager.add_threshold(custom_threshold)
```

## Log Format

All logs are output in JSON format for easy parsing:

```json
{
  "timestamp": "2025-11-16T10:30:45.123456Z",
  "level": "INFO",
  "logger": "apps.bot.agent",
  "message": "Agent interaction completed successfully",
  "module": "ai_agent_service",
  "function": "process_message",
  "line": 123,
  "event_type": "agent_interaction",
  "conversation_id": "uuid-here",
  "tenant_id": "uuid-here",
  "model_used": "gpt-4o",
  "confidence_score": 0.85,
  "processing_time_ms": 1234,
  "token_usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 200,
    "total_tokens": 1200
  },
  "estimated_cost": 0.015,
  "handoff_triggered": false,
  "message_type": "text"
}
```

## Metrics Cache

Metrics are cached in Redis for distributed access:

```python
from apps.bot.services.monitoring.metrics_collector import MetricsCollector

# Get cached metrics (useful for dashboards)
cached_metrics = MetricsCollector.get_cached_metrics(tenant_id=str(tenant.id))
```

## Alert Configuration

Default alert thresholds:

| Alert | Metric | Threshold | Severity | Cooldown |
|-------|--------|-----------|----------|----------|
| slow_response_p95 | p95 response time | > 5s | warning | 15 min |
| slow_response_p99 | p99 response time | > 10s | error | 15 min |
| high_cost_per_conversation | avg cost | > $0.10 | warning | 30 min |
| very_high_cost_per_conversation | avg cost | > $0.25 | error | 30 min |
| high_handoff_rate | handoff rate | > 30% | warning | 20 min |
| very_high_handoff_rate | handoff rate | > 50% | error | 20 min |
| low_knowledge_hit_rate | hit rate | < 50% | warning | 30 min |

## Error Rate Monitoring

Automatic error rate monitoring with alerts:

- **5-minute window**: Alert if error rate > 10%
- **15-minute window**: Alert if error rate > 5%

Errors are automatically tracked when using the monitoring integration.

## Best Practices

1. **Always use the unified monitor**: Use `get_agent_monitor()` for consistent logging and metrics
2. **Include context**: Add relevant metadata to all log calls
3. **Monitor metrics regularly**: Check metrics dashboard to identify trends
4. **Tune alert thresholds**: Adjust thresholds based on your specific needs
5. **Handle alerts promptly**: Set up proper alert handlers for your team

## Integration with Existing Code

The monitoring system is designed to integrate seamlessly with the existing AI agent service. Simply replace existing logging calls with the monitoring integration:

```python
# Before
logger.info(f"Processing message {message.id}")

# After
monitor.log_and_record_interaction(...)
```

## Performance Impact

The monitoring system is designed for minimal performance impact:

- Asynchronous logging (non-blocking)
- In-memory metrics with periodic cache updates
- Efficient data structures (deque with max size)
- Cooldown periods to prevent excessive alerting

## Requirements

- Django 4.2+
- Redis (for caching)
- Python 3.9+
- Optional: Sentry (for critical alerts)

## Future Enhancements

- Grafana dashboard integration
- Prometheus metrics export
- Custom metric aggregation periods
- Machine learning-based anomaly detection
- Distributed tracing support
