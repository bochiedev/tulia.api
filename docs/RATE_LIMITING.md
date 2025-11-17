# Rate Limiting Guide

## Overview

Tulia AI implements comprehensive rate limiting to protect against abuse, brute force attacks, and denial of service attempts. Rate limits are enforced using Redis as a distributed storage backend, ensuring consistent limits across multiple application instances.

## Rate Limit Categories

### 1. Authentication Endpoints (Public)

These endpoints are publicly accessible and have strict rate limits to prevent abuse:

| Endpoint | Rate Limit | Key Type | Purpose |
|----------|-----------|----------|---------|
| `POST /v1/auth/register` | **3 requests/hour** | IP address | Prevent account creation spam and automated registration |
| `POST /v1/auth/login` | **5 requests/minute** per IP<br>**10 requests/hour** per email | IP + Email | Prevent brute force password attacks and credential stuffing |
| `POST /v1/auth/verify-email` | **10 requests/hour** | IP address | Prevent verification token abuse |
| `POST /v1/auth/forgot-password` | **3 requests/hour** | IP address | Prevent password reset spam and email enumeration |
| `POST /v1/auth/reset-password` | **5 requests/hour** | IP address | Prevent reset token brute forcing |

### 2. Tenant-Scoped Endpoints

Rate limits for authenticated endpoints vary by subscription tier:

| Tier | API Requests/Hour | Messages/Day | Webhooks/Hour |
|------|-------------------|--------------|---------------|
| **Starter** | 1,000 | 1,000 | 500 |
| **Growth** | 10,000 | 10,000 | 5,000 |
| **Professional** | 50,000 | 50,000 | 25,000 |
| **Enterprise** | Unlimited | Unlimited | Unlimited |

### 3. Sensitive Operations

Additional rate limits on sensitive operations:

| Operation | Rate Limit | Scope |
|-----------|-----------|-------|
| Withdrawal initiation | 10/hour | Per user |
| Withdrawal approval | 20/hour | Per user |
| Role assignment | 100/hour | Per tenant |
| Permission grant | 100/hour | Per tenant |
| API key generation | 10/hour | Per tenant |

## Rate Limit Response

### HTTP Status Code

When a rate limit is exceeded, the API returns:

```
HTTP/1.1 429 Too Many Requests
```

### Response Body

```json
{
  "error": "Rate limit exceeded. Please try again later.",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 3600
}
```

### Response Headers

```
Retry-After: 3600
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705334400
```

| Header | Description |
|--------|-------------|
| `Retry-After` | Seconds until rate limit resets |
| `X-RateLimit-Limit` | Maximum requests allowed in window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when limit resets |

## Implementation Details

### Storage Backend

- **Technology**: Redis
- **Algorithm**: Sliding window counter
- **Distribution**: Works across multiple application instances
- **Persistence**: Rate limit data survives application restarts
- **Cleanup**: Automatic TTL-based expiration

### Rate Limit Keys

Rate limits are tracked using Redis keys with the following format:

```
rl:<key_type>:<identifier>:<endpoint>
```

Examples:
- `rl:ip:192.168.1.1:register` - Registration attempts from IP
- `rl:email:user@example.com:login` - Login attempts for email
- `rl:user:uuid:withdraw` - Withdrawal attempts by user

### Key Types

| Key Type | Description | Example |
|----------|-------------|---------|
| `ip` | Client IP address | `192.168.1.1` |
| `email` | User email address | `user@example.com` |
| `user` | User UUID | `123e4567-e89b-12d3-a456-426614174000` |
| `tenant` | Tenant UUID | `789e4567-e89b-12d3-a456-426614174001` |

## Security Features

### 1. Brute Force Protection

**Login Rate Limiting**:
- 5 attempts per minute per IP prevents rapid password guessing
- 10 attempts per hour per email prevents targeted account attacks
- Dual-layer protection (IP + email) catches distributed attacks

**Example Attack Scenario**:
```
Attacker tries 100 passwords for user@example.com:
- First 5 attempts succeed (within 1 minute)
- Attempts 6-10 blocked by IP rate limit
- After 1 minute, 5 more attempts allowed
- After 10 total attempts, email rate limit blocks further attempts for 1 hour
```

### 2. Account Enumeration Prevention

**Registration Rate Limiting**:
- 3 registrations per hour per IP prevents email enumeration
- Prevents automated account creation for spam

**Password Reset Rate Limiting**:
- 3 reset requests per hour per IP prevents email enumeration
- Consistent response regardless of email existence

### 3. Denial of Service Protection

**Request Rate Limiting**:
- Per-tenant limits prevent single tenant from overwhelming system
- Per-IP limits prevent distributed attacks
- Automatic recovery after time window

### 4. Security Event Logging

All rate limit violations are logged with:
- Timestamp
- IP address
- User agent
- Endpoint
- Rate limit type
- Exceeded limit value

Critical violations are sent to Sentry for real-time alerting.

## Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Rate Limiting
RATE_LIMIT_ENABLED=True

# JWT Configuration (affects token expiration)
JWT_EXPIRATION_HOURS=24
```

### Django Settings

```python
# config/settings.py

# Django-ratelimit configuration
RATELIMIT_USE_CACHE = 'default'  # Use Redis cache
RATELIMIT_ENABLE = env.bool('RATE_LIMIT_ENABLED', default=True)
RATELIMIT_VIEW = 'apps.core.exceptions.ratelimit_view'

# Cache configuration (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'tulia',
        'TIMEOUT': 300,
    }
}
```

## Testing Rate Limits

### Manual Testing

```bash
# Test login rate limit (5/min per IP)
for i in {1..6}; do
  curl -X POST http://localhost:8000/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}' \
    -w "\nStatus: %{http_code}\n"
  sleep 1
done

# Expected: First 5 return 401, 6th returns 429
```

### Automated Testing

```bash
# Run rate limiting tests
python -m pytest apps/rbac/tests/test_rate_limiting.py -v
python -m pytest apps/rbac/tests/test_rate_limiting_redis.py -v
```

## Monitoring

### Redis Monitoring

View rate limit keys in Redis:

```bash
redis-cli

# List all rate limit keys
> KEYS rl:*

# Check specific rate limit
> GET rl:ip:192.168.1.1:login
> TTL rl:ip:192.168.1.1:login

# View rate limit details
> HGETALL rl:ip:192.168.1.1:login
```

### Application Monitoring

Rate limit metrics are tracked in:
- Application logs (structured JSON)
- Sentry (critical violations)
- Analytics dashboard (rate limit violations per endpoint)

### Metrics to Monitor

1. **Rate Limit Hit Rate**: Percentage of requests hitting rate limits
2. **Top Rate Limited IPs**: IPs with most violations
3. **Top Rate Limited Endpoints**: Endpoints with most violations
4. **Rate Limit Violations by Time**: Identify attack patterns

## Troubleshooting

### Rate Limit Not Working

**Symptoms**: Requests not being rate limited

**Solutions**:
1. Check Redis is running: `redis-cli ping`
2. Verify Redis URL: `echo $REDIS_URL`
3. Check rate limiting is enabled: `echo $RATE_LIMIT_ENABLED`
4. Test cache connection:
   ```python
   from django.core.cache import cache
   cache.set('test', 'value')
   print(cache.get('test'))  # Should print 'value'
   ```

### Rate Limit Too Strict

**Symptoms**: Legitimate users being blocked

**Solutions**:
1. Review rate limit logs to identify patterns
2. Adjust rate limits in view decorators:
   ```python
   @ratelimit(key='ip', rate='10/m', method='POST')  # Increase from 5/m
   ```
3. Consider implementing rate limit exemptions for trusted IPs
4. Implement user-specific rate limits for authenticated users

### Rate Limit Not Resetting

**Symptoms**: Rate limit persists after time window

**Solutions**:
1. Check Redis TTL: `redis-cli TTL rl:ip:192.168.1.1:login`
2. Verify system time is correct: `date`
3. Check Redis memory policy: `redis-cli CONFIG GET maxmemory-policy`
4. Manually clear rate limit: `redis-cli DEL rl:ip:192.168.1.1:login`

### Clear All Rate Limits

**For testing/development only**:

```bash
redis-cli
> KEYS rl:*
> DEL rl:ip:127.0.0.1:login
# Or clear all rate limits
> EVAL "return redis.call('del', unpack(redis.call('keys', 'rl:*')))" 0
```

## Best Practices

### For API Clients

1. **Implement Exponential Backoff**: When receiving 429, wait before retrying
2. **Respect Retry-After Header**: Wait specified seconds before retry
3. **Cache Responses**: Reduce unnecessary API calls
4. **Batch Requests**: Combine multiple operations when possible
5. **Monitor Rate Limit Headers**: Track remaining requests

### For Developers

1. **Test Rate Limits**: Include rate limit tests in test suite
2. **Document Limits**: Clearly document rate limits in API docs
3. **Log Violations**: Monitor rate limit violations for abuse patterns
4. **Graceful Degradation**: Handle 429 responses gracefully
5. **User Feedback**: Provide clear error messages to users

### For Operations

1. **Monitor Redis**: Track Redis memory, connections, and performance
2. **Set Alerts**: Alert on high rate limit violation rates
3. **Review Logs**: Regularly review rate limit logs for patterns
4. **Adjust Limits**: Tune rate limits based on usage patterns
5. **Plan Capacity**: Ensure Redis can handle peak load

## Production Considerations

### Redis Configuration

```bash
# redis.conf

# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence (optional for rate limiting)
save 900 1
save 300 10
save 60 10000

# Performance
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

### High Availability

For production deployments:

1. **Redis Sentinel**: Automatic failover for Redis
2. **Redis Cluster**: Distributed rate limiting across nodes
3. **Backup Redis**: Separate Redis instance for rate limiting
4. **Connection Pooling**: Configure appropriate pool size
5. **Health Checks**: Monitor Redis availability

### Scaling Considerations

As your application scales:

1. **Separate Redis Instance**: Dedicated Redis for rate limiting
2. **Increase Limits**: Adjust limits based on legitimate traffic
3. **Tier-Based Limits**: Different limits for different subscription tiers
4. **Geographic Distribution**: Consider regional rate limits
5. **CDN Integration**: Offload static content to reduce API calls

## Security Recommendations

1. **Enable Rate Limiting**: Always enable in production
2. **Monitor Violations**: Set up alerts for unusual patterns
3. **Regular Review**: Review and adjust limits quarterly
4. **Incident Response**: Have plan for handling rate limit attacks
5. **Documentation**: Keep rate limit documentation up to date

## Related Documentation

- [Authentication Guide](AUTHENTICATION.md) - JWT authentication and security
- [Redis Rate Limiting Configuration](REDIS_RATE_LIMITING.md) - Detailed Redis setup
- [Security Best Practices](SECURITY_BEST_PRACTICES.md) - Overall security guidelines
- [API Quick Reference](api/API_QUICK_REFERENCE.md) - API endpoint reference

## Support

For rate limiting issues:
1. Check application logs for rate limit violations
2. Review Redis logs for connection issues
3. Monitor Sentry for critical violations
4. Contact support with request ID and timestamp
