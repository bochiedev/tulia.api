# Performance Optimization Services - Quick Reference

## Overview

This document provides quick reference for using the performance optimization services in the AI-powered customer service agent.

## Catalog Cache Service

### Basic Usage

```python
from apps.bot.services.catalog_cache_service import CatalogCacheService

# Get cached products for tenant
products = CatalogCacheService.get_products(tenant, active_only=True)

# Get cached services for tenant
services = CatalogCacheService.get_services(tenant, active_only=True)

# Get single product with caching
product = CatalogCacheService.get_product(product_id)

# Get single service with caching
service = CatalogCacheService.get_service(service_id)
```

### Cache Invalidation

```python
# Invalidate after product changes
CatalogCacheService.invalidate_products(tenant_id)

# Invalidate after service changes
CatalogCacheService.invalidate_services(tenant_id)

# Invalidate specific product
CatalogCacheService.invalidate_product(product_id, tenant_id)

# Invalidate specific service
CatalogCacheService.invalidate_service(service_id, tenant_id)
```

### Cache Warming

```python
# Pre-load cache for tenant (useful on startup or after cache clear)
result = CatalogCacheService.warm_cache(tenant)
print(f"Cached {result['products']} products and {result['services']} services")
```

## Query Optimizer

### Optimized Queries

```python
from apps.bot.services.query_optimizer import QueryOptimizer

# Get conversation with all related data (1-2 queries instead of 10+)
conversation = QueryOptimizer.get_conversation_with_context(conversation_id)

# Get messages with optimized query
messages = QueryOptimizer.get_conversation_messages(conversation_id, limit=20)

# Get agent interactions with caching
interactions = QueryOptimizer.get_agent_interactions(conversation_id, limit=10)

# Get knowledge entries with caching
entries = QueryOptimizer.get_knowledge_entries_for_tenant(
    tenant_id,
    entry_type='faq',
    active_only=True
)
```

### Statistics and Metrics

```python
# Get conversation statistics (cached)
stats = QueryOptimizer.get_conversation_statistics(tenant_id)
print(f"Total conversations: {stats['total_conversations']}")
print(f"By status: {stats['by_status']}")

# Get agent performance metrics (cached)
metrics = QueryOptimizer.get_agent_performance_metrics(tenant_id)
print(f"Average confidence: {metrics['avg_confidence']:.2f}")
print(f"Handoff rate: {metrics['handoff_rate']:.2%}")
print(f"Total cost: ${metrics['total_cost']:.2f}")
```

### Bulk Operations

```python
# Bulk prefetch multiple conversations
conversation_ids = ['id1', 'id2', 'id3']
conversations = QueryOptimizer.bulk_prefetch_conversations(conversation_ids)

# Access prefetched data
for conv_id, conversation in conversations.items():
    # All related data already loaded
    messages = conversation.messages.all()  # No additional query
    interactions = conversation.agent_interactions.all()  # No additional query
```

### Cache Invalidation

```python
# Invalidate conversation cache after updates
QueryOptimizer.invalidate_conversation_cache(conversation_id)

# Invalidate tenant cache after major changes
QueryOptimizer.invalidate_tenant_cache(tenant_id)
```

## Message Deduplication

### Automatic Deduplication

```python
from apps.bot.services.message_deduplication import MessageDeduplicationService

# Check if message is duplicate
is_dup = MessageDeduplicationService.is_duplicate(
    message_id=str(message.id),
    conversation_id=str(conversation.id),
    message_text=message.text
)

if is_dup:
    print("Skipping duplicate message")
    return
```

### Distributed Locking

```python
from apps.bot.services.message_deduplication import (
    MessageDeduplicationService,
    MessageLockError
)

# Acquire lock and process message
try:
    with MessageDeduplicationService.acquire_lock(
        message_id=str(message.id),
        conversation_id=str(conversation.id),
        message_text=message.text,
        worker_id='worker-1'
    ):
        # Process message - guaranteed single execution
        result = process_message(message, conversation, tenant)
        
except MessageLockError as e:
    print(f"Lock acquisition failed: {e}")
    # Message is being processed by another worker
```

### Processing State

```python
# Get current processing state
state = MessageDeduplicationService.get_processing_state(
    message_id=str(message.id),
    conversation_id=str(conversation.id),
    message_text=message.text
)

if state:
    print(f"Status: {state['status']}")
    print(f"Worker: {state['worker_id']}")
    if state['status'] == 'processing':
        print(f"Started at: {state['started_at']}")
    elif state['status'] == 'completed':
        print(f"Completed at: {state['completed_at']}")
```

### Recovery

```python
# Force release stuck lock (use with caution)
released = MessageDeduplicationService.force_release_lock(
    message_id=str(message.id),
    conversation_id=str(conversation.id),
    message_text=message.text
)

if released:
    print("Lock forcefully released")
```

### Decorator Pattern

```python
from apps.bot.services.message_deduplication import deduplicate_message

@deduplicate_message
def process_message(message, conversation, tenant):
    """
    This function will automatically:
    1. Check for duplicates
    2. Acquire distributed lock
    3. Process message
    4. Release lock
    """
    # Your processing logic here
    return result

# Use it
result = process_message(message, conversation, tenant)
```

## Context Builder with Caching

### Using Optimized Context Builder

```python
from apps.bot.services.context_builder_service import create_context_builder_service

# Create service (automatically uses caching)
context_builder = create_context_builder_service()

# Build context (uses catalog cache internally)
context = context_builder.build_context(
    conversation=conversation,
    message=message,
    tenant=tenant,
    max_tokens=100000
)

# Access cached catalog data
products = context.catalog_context.products  # From cache
services = context.catalog_context.services  # From cache
```

## Best Practices

### 1. Always Use Caching in Production

```python
# Good - uses cache
products = CatalogCacheService.get_products(tenant)

# Bad - bypasses cache (only for debugging)
products = CatalogCacheService.get_products(tenant, use_cache=False)
```

### 2. Invalidate Cache on Updates

```python
# After updating product
product.save()
CatalogCacheService.invalidate_product(product.id, tenant.id)

# After bulk updates
Product.objects.filter(tenant=tenant).update(is_active=True)
CatalogCacheService.invalidate_products(tenant.id)
```

### 3. Use Query Optimizer for Related Data

```python
# Good - optimized query
conversation = QueryOptimizer.get_conversation_with_context(conv_id)

# Bad - N+1 queries
conversation = Conversation.objects.get(id=conv_id)
tenant = conversation.tenant  # Additional query
customer = conversation.customer  # Additional query
```

### 4. Always Use Deduplication for Message Processing

```python
# Good - prevents duplicates
with MessageDeduplicationService.acquire_lock(...):
    process_message()

# Bad - can process duplicates
process_message()  # No deduplication
```

### 5. Monitor Cache Performance

```python
import logging
logger = logging.getLogger(__name__)

# Cache services log hits/misses automatically
# Monitor logs for cache performance:
# - "Retrieved X items from cache" = cache hit
# - "Cached X items" = cache miss (loaded from DB)
```

## Performance Tips

### 1. Warm Cache on Startup

```python
# In management command or startup script
from apps.tenants.models import Tenant
from apps.bot.services.catalog_cache_service import CatalogCacheService

for tenant in Tenant.objects.filter(is_active=True):
    CatalogCacheService.warm_cache(tenant)
```

### 2. Use Bulk Operations

```python
# Good - single bulk operation
conversations = QueryOptimizer.bulk_prefetch_conversations(conv_ids)

# Bad - multiple individual queries
conversations = [
    QueryOptimizer.get_conversation_with_context(id)
    for id in conv_ids
]
```

### 3. Set Appropriate TTLs

```python
# Short TTL for frequently changing data
CATALOG_CACHE_TTL = 60  # 1 minute

# Longer TTL for stable data
AGENT_CONFIG_CACHE_TTL = 300  # 5 minutes
KNOWLEDGE_CACHE_TTL = 600  # 10 minutes
```

### 4. Handle Cache Failures Gracefully

```python
try:
    products = CatalogCacheService.get_products(tenant)
except Exception as e:
    logger.error(f"Cache error: {e}")
    # Fallback to direct database query
    products = Product.objects.filter(tenant=tenant, is_active=True)
```

## Troubleshooting

### Cache Not Working

```python
# Check Redis connection
from django.core.cache import cache
cache.set('test', 'value', 60)
assert cache.get('test') == 'value'

# Check cache configuration
from django.conf import settings
print(settings.CACHES)
```

### High Cache Miss Rate

```python
# Check TTL settings - may be too short
# Check invalidation frequency - may be too aggressive
# Monitor logs for cache patterns

# Increase TTL if appropriate
CATALOG_CACHE_TTL = 120  # 2 minutes instead of 1
```

### Lock Timeouts

```python
# Check processing time
# Increase lock TTL if needed
MessageDeduplicationService.LOCK_TTL = 600  # 10 minutes

# Or optimize processing to be faster
```

### Memory Issues

```python
# Monitor Redis memory usage
# Reduce cache TTLs if needed
# Implement cache size limits
# Use cache eviction policies (LRU)
```

## Monitoring Queries

### Django Debug Toolbar (Development)

```python
# Install django-debug-toolbar
# Add to INSTALLED_APPS and middleware
# View query count in toolbar

# Before optimization: 50+ queries
# After optimization: 2-5 queries
```

### Query Logging (Production)

```python
# Enable query logging in settings
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}

# Monitor slow queries
# Identify N+1 problems
# Optimize with select_related/prefetch_related
```

## Additional Resources

- Django Caching Documentation: https://docs.djangoproject.com/en/4.2/topics/cache/
- Redis Documentation: https://redis.io/documentation
- Django Query Optimization: https://docs.djangoproject.com/en/4.2/topics/db/optimization/
- Distributed Locking Patterns: https://redis.io/topics/distlock

---

**Last Updated**: 2025-11-16
**Version**: 1.0
**Maintainer**: AI Agent Team
