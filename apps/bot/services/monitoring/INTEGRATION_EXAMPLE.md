# Integration Example: Adding Monitoring to AI Agent Service

This document shows how to integrate the monitoring system into the existing AI agent service.

## Step 1: Import the Monitor

At the top of `apps/bot/services/ai_agent_service.py`:

```python
from apps.bot.services.monitoring import get_agent_monitor
```

## Step 2: Initialize Monitor in AIAgentService

Add monitor initialization in the `__init__` method:

```python
class AIAgentService:
    def __init__(
        self,
        context_builder: Optional[ContextBuilderService] = None,
        config_service: Optional[AgentConfigurationService] = None,
        fuzzy_matcher: Optional[FuzzyMatcherService] = None,
        rich_message_builder: Optional[RichMessageBuilder] = None
    ):
        # Existing initialization...
        self.context_builder = context_builder or create_context_builder_service()
        self.config_service = config_service or create_agent_config_service()
        # ... other initializations ...
        
        # Add monitor (will be set per-tenant in process_message)
        self.monitor = None
```

## Step 3: Update process_message Method

Replace existing logging with comprehensive monitoring:

```python
def process_message(
    self,
    message: Message,
    conversation: Conversation,
    tenant
) -> AgentResponse:
    """Process customer message and generate AI response."""
    start_time = timezone.now()
    
    # Initialize tenant-specific monitor
    self.monitor = get_agent_monitor(tenant_id=str(tenant.id))
    
    try:
        # ... existing preprocessing code ...
        
        # Build context with timing
        context_start = time.time()
        context = self.context_builder.build_context(
            conversation=conversation,
            message=processed_message,
            tenant=tenant,
            max_tokens=100000
        )
        context_build_time_ms = int((time.time() - context_start) * 1000)
        
        # Log context building
        self.monitor.log_context_building(
            conversation_id=str(conversation.id),
            context_data=context.to_dict(),
            build_time_ms=context_build_time_ms
        )
        
        # ... existing code for suggestions and model selection ...
        
        # Generate response with LLM call logging
        response = self.generate_response(
            context=context,
            agent_config=agent_config,
            model=model,
            tenant=tenant,
            suggestions=suggestions
        )
        
        # Calculate processing time
        end_time = timezone.now()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        response.processing_time_ms = processing_time_ms
        
        # Check handoff with logging
        should_handoff, handoff_reason = self.should_handoff(
            response=response,
            conversation=conversation,
            agent_config=agent_config
        )
        
        # Log handoff decision
        self.monitor.log_handoff_decision(
            conversation_id=str(conversation.id),
            should_handoff=should_handoff,
            reason=handoff_reason,
            confidence_score=response.confidence_score,
            consecutive_low_confidence=conversation.low_confidence_count
        )
        
        response.should_handoff = should_handoff
        response.handoff_reason = handoff_reason
        
        # ... existing handoff and context update code ...
        
        # Log and record complete interaction
        self.monitor.log_and_record_interaction(
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
            detected_intents=response.metadata.get('detected_intents', []),
            message_type='text' if not response.use_rich_message else response.metadata.get('rich_message_type', 'text'),
            context_size_tokens=context.context_size_tokens,
            context_truncated=context.truncated
        )
        
        return response
        
    except Exception as e:
        # Log error
        if self.monitor:
            self.monitor.log_error(
                conversation_id=str(conversation.id),
                error_type='agent_processing_error',
                error_message=str(e),
                operation='process_message',
                stack_trace=traceback.format_exc()
            )
        
        # ... existing fallback response code ...
        return fallback_response
```

## Step 4: Update generate_response Method

Add LLM call logging:

```python
def generate_response(
    self,
    context: AgentContext,
    agent_config: AgentConfiguration,
    model: str,
    tenant,
    suggestions: Optional[Dict[str, Any]] = None
) -> AgentResponse:
    """Generate AI response using LLM provider."""
    
    try:
        # ... existing prompt building code ...
        
        # Call LLM with timing
        llm_start = time.time()
        llm_response = provider.generate(
            messages=messages,
            model=model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_response_length * 2
        )
        llm_time_ms = int((time.time() - llm_start) * 1000)
        
        # Log LLM call
        if self.monitor:
            self.monitor.log_and_record_llm_call(
                conversation_id=str(context.conversation.id),
                provider=llm_response.provider,
                model=llm_response.model,
                prompt_tokens=llm_response.input_tokens,
                completion_tokens=llm_response.output_tokens,
                total_tokens=llm_response.total_tokens,
                estimated_cost=llm_response.estimated_cost,
                response_time_ms=llm_time_ms,
                success=True
            )
        
        # ... existing response creation code ...
        
        return response
        
    except Exception as e:
        # Log LLM error
        if self.monitor:
            self.monitor.log_and_record_llm_call(
                conversation_id=str(context.conversation.id),
                provider='openai',
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost=Decimal('0.0'),
                response_time_ms=0,
                success=False,
                error=str(e)
            )
        raise
```

## Step 5: Update Context Builder Service

Add knowledge search logging in `apps/bot/services/context_builder_service.py`:

```python
from apps.bot.services.monitoring import get_agent_monitor

class ContextBuilderService:
    def get_relevant_knowledge(
        self,
        query: str,
        tenant,
        entry_types: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[tuple]:
        """Retrieve relevant knowledge base entries using semantic search."""
        
        search_start = time.time()
        
        try:
            results = self.knowledge_service.search(
                tenant=tenant,
                query=query,
                entry_types=entry_types,
                limit=limit,
                min_similarity=0.7
            )
            
            search_time_ms = int((time.time() - search_start) * 1000)
            
            # Log knowledge search (if we have conversation context)
            # Note: This requires passing conversation_id to this method
            # or using a thread-local context
            
            top_score = results[0][1] if results else None
            
            logger.debug(
                f"Found {len(results)} relevant knowledge entries for query: "
                f"'{query[:50]}...'"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve knowledge entries: {e}")
            return []
```

## Step 6: Create Metrics Dashboard View (Optional)

Create a simple API endpoint to expose metrics:

```python
# In apps/bot/views_agent_interactions.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.permissions import HasTenantScopes
from apps.bot.services.monitoring.metrics_collector import MetricsCollector

@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
def agent_metrics_view(request):
    """
    Get current agent metrics for the tenant.
    
    Required scope: analytics:view
    """
    # Check scope
    if 'analytics:view' not in request.scopes:
        return Response({'error': 'Missing required scope: analytics:view'}, status=403)
    
    tenant_id = str(request.tenant.id)
    
    # Try to get cached metrics first
    metrics = MetricsCollector.get_cached_metrics(tenant_id=tenant_id)
    
    if not metrics:
        # If no cached metrics, return empty state
        metrics = {
            'message': 'No metrics available yet',
            'response_time': {},
            'token_usage': {},
            'cost': {},
            'handoff': {},
            'knowledge_base': {},
            'model_usage': {}
        }
    
    return Response(metrics)
```

## Step 7: Configure Logging

Update Django settings to use JSON logging in production:

```python
# In config/settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'apps.bot.services.monitoring.structured_logger.JSONFormatter',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/agent.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'apps.bot.agent': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

## Step 8: Test the Integration

```python
# Test script
from apps.bot.services.monitoring import get_agent_monitor
from decimal import Decimal

# Get monitor
monitor = get_agent_monitor(tenant_id='test-tenant-id')

# Simulate an interaction
monitor.log_and_record_interaction(
    conversation_id='test-conversation-id',
    customer_message='Hello, I need help',
    agent_response='Hi! How can I assist you today?',
    model_used='gpt-4o',
    confidence_score=0.95,
    processing_time_ms=1234,
    token_usage={
        'prompt_tokens': 100,
        'completion_tokens': 20,
        'total_tokens': 120
    },
    estimated_cost=Decimal('0.002'),
    handoff_triggered=False,
    handoff_reason='',
    message_type='text',
    context_size_tokens=500,
    context_truncated=False
)

# Get metrics
metrics = monitor.get_metrics_summary()
print(f"Metrics: {metrics}")
```

## Benefits

After integration, you'll have:

1. **Structured JSON logs** for all agent operations
2. **Real-time metrics** on performance, cost, and quality
3. **Automatic alerting** for issues
4. **Historical data** for analysis and optimization
5. **Tenant-specific insights** for each customer

## Next Steps

1. Set up log aggregation (e.g., ELK stack, CloudWatch)
2. Create Grafana dashboards for metrics visualization
3. Configure alert handlers (Slack, PagerDuty, etc.)
4. Set up automated reports
5. Tune alert thresholds based on your SLAs
