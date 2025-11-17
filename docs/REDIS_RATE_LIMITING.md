# Redis Rate Limiting Configuration

## Overview

The application uses Redis as the storage backend for rate limiting to ensure distributed rate limiting works correctly across multiple application instances.

## Configuration

### Settings (config/settings.py)

```python
# Django-ratelimit configuration
RATELIMIT_USE_CACHE = 'default'  # Use the default Redis cache
RATELIMIT_ENABLE = RATE_LIMIT_ENABLED  # Enable/disable rate limiting
RATELIMIT_VIEW = 'apps.core.exceptions.ratelimit_view'  # Custom 429 response
```

### Environment Variables (.env)

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_ENABLED=True
```

## How It Works

1. **Storage Backend**: `django-ratelimit` uses the Django cache framework, which is configured to use Redis
2. **Cache Configuration**: The `RATELIMIT_USE_CACHE = 'default'` setting tells django-ratelimit to use the default Redis cache
3. **Distributed**: Since Redis is a centralized store, rate limits work correctly across multiple application instances
4. **Key Format**: Rate limit keys are stored in Redis with the format `rl:<key_type>:<identifier>:<endpoint>`

## Rate Limits Applied

### Authentication Endpoints

| Endpoint | Rate Limit | Key Type |
|----------|-----------|----------|
| `/v1/auth/register` | 3/hour | IP address |
| `/v1/auth/login` | 5/min per IP, 10/hour per email | IP + Email |
| `/v1/auth/verify-email` | 10/hour | IP address |
| `/v1/auth/forgot-password` | 3/hour | IP address |
| `/v1/auth/reset-password` | 5/hour | IP address |

### Other Endpoints

- Settings endpoints: 60/min per user or IP
- API key management: 60/min per user or IP
- Tenant management: 60/min per user or IP

## Testing

Run the Redis rate limiting tests:

```bash
# Test Redis configuration
python -m pytest apps/rbac/tests/test_redis_rate_limit_config.py -v

# Test rate limiting behavior
python -m pytest apps/rbac/tests/test_rate_limiting_redis.py -v
```

## Monitoring

Rate limit keys in Redis:
- Have TTL set to expire after the rate limit window
- Use sorted sets for sliding window algorithm
- Are automatically cleaned up by Redis when expired

To view rate limit keys in Redis:

```bash
redis-cli
> KEYS rl:*
> TTL rl:ip:127.0.0.1:register
```

## Production Considerations

1. **Redis Persistence**: Configure Redis persistence (RDB or AOF) to prevent rate limit data loss on restart
2. **Redis Memory**: Monitor Redis memory usage and set `maxmemory` policy to `allkeys-lru`
3. **Separate Redis Instance**: Consider using a separate Redis instance for rate limiting in production
4. **Connection Pool**: The cache is configured with connection pooling (max 50 connections)

## Troubleshooting

### Rate Limits Not Working

1. Check Redis is running: `redis-cli ping`
2. Verify Redis URL in `.env`: `REDIS_URL=redis://localhost:6379/0`
3. Check rate limiting is enabled: `RATE_LIMIT_ENABLED=True`
4. Verify cache configuration: `python manage.py shell` → `from django.core.cache import cache; cache.set('test', 'value'); cache.get('test')`

### Rate Limits Too Strict

Adjust rate limits in the view decorators:

```python
@ratelimit(key='ip', rate='10/m', method='POST')  # Change rate here
```

### Clear Rate Limits

To clear all rate limits:

```bash
redis-cli
> KEYS rl:*
> DEL rl:ip:127.0.0.1:register
# Or clear all
> FLUSHDB
```

## Security Benefits

1. **Brute Force Protection**: Prevents password guessing attacks on login
2. **Account Enumeration**: Limits registration attempts to prevent email enumeration
3. **DoS Protection**: Prevents denial of service attacks by limiting request rates
4. **Distributed**: Works across multiple application instances
5. **Automatic Cleanup**: Redis TTL ensures old rate limit data is automatically removed
