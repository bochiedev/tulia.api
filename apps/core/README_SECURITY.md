# Security Features Implementation

This document describes the security features implemented in the core app.

## Rate Limiting

### Overview
Redis-based rate limiting using sliding window algorithm to prevent abuse and ensure fair resource usage across tenants.

### Features
- **Per-tenant rate limiting**: Separate limits for each tenant
- **Separate limits for API and webhooks**: Different rate limits for API requests vs webhook calls
- **Sliding window algorithm**: More accurate than fixed window, prevents burst attacks
- **Automatic retry-after calculation**: Returns seconds until rate limit resets
- **Rate limit headers**: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

### Configuration
Default limits (per hour):
- API requests: 1000 requests/hour
- Webhook calls: 10000 requests/hour

### Usage
```python
from apps.core.rate_limiting import RateLimiter

# Check rate limit
is_allowed, retry_after = RateLimiter.check_rate_limit(tenant_id, 'api')

if not is_allowed:
    # Rate limit exceeded
    return Response({'error': 'Rate limit exceeded'}, status=429)

# Increment counter
RateLimiter.increment(tenant_id, 'api')

# Get status
status = RateLimiter.get_status(tenant_id, 'api')
# Returns: {'limit': 1000, 'current': 50, 'remaining': 950, 'reset_at': 1699999999}
```

### Middleware
The `RateLimitMiddleware` automatically enforces rate limits on all API requests:
- Returns 429 with Retry-After header when limit exceeded
- Adds rate limit headers to all responses
- Logs rate limit violations for monitoring

## CORS Validation

### Overview
Tenant-specific CORS validation that checks Origin header against tenant.allowed_origins.

### Features
- **Tenant-specific origins**: Each tenant can configure their own allowed origins
- **Wildcard support**: Supports wildcard subdomain patterns (e.g., https://*.example.com)
- **Development mode**: Wildcard '*' allows all origins for development
- **Strict production mode**: Only explicitly allowed origins are permitted
- **Automatic CORS headers**: Adds appropriate CORS headers to responses

### Configuration
Configure allowed origins in tenant model:
```python
tenant.allowed_origins = [
    'https://example.com',           # Exact match
    'https://*.subdomain.com',       # Wildcard subdomain
    '*',                             # Allow all (development only)
]
```

### Middleware
The `TenantCORSMiddleware` validates CORS requests:
- Checks Origin header against tenant.allowed_origins
- Returns 403 for unauthorized origins
- Adds CORS headers to responses for allowed origins
- Bypasses validation for webhooks and health checks

## PII Encryption

### Overview
AES-256-GCM encryption for sensitive data like phone numbers, emails, and credentials.

### Features
- **Transparent encryption/decryption**: Automatic at ORM level
- **Encrypted field lookups**: Supports exact, iexact, and in lookups
- **PII masking**: Utilities for masking PII in logs and exports
- **Sanitization**: Functions for sanitizing data for logging and export

### Encrypted Fields
```python
from apps.core.fields import EncryptedCharField, EncryptedTextField

class Customer(models.Model):
    phone_e164 = EncryptedCharField(max_length=20)
    email = EncryptedCharField(max_length=255, null=True)
```

### Encrypted Lookups
```python
# Exact match (automatically encrypts lookup value)
customer = Customer.objects.get(phone_e164='+1234567890')

# In lookup
customers = Customer.objects.filter(
    phone_e164__in=['+1234567890', '+0987654321']
)
```

### PII Masking
```python
from apps.core.encryption import (
    mask_pii,
    mask_email,
    mask_phone,
    sanitize_for_export,
    sanitize_for_logging,
)

# Mask phone number
masked = mask_phone('+1234567890')  # Returns: *******7890

# Mask email
masked = mask_email('user@example.com')  # Returns: u***@e******.com

# Sanitize for export (masks PII)
sanitized = sanitize_for_export({
    'id': '123',
    'phone_e164': '+1234567890',
    'email': 'user@example.com',
})
# Returns: {'id': '123', 'phone_e164': '*******7890', 'email': 'u***@e******.com'}

# Sanitize for logging (removes secrets, masks PII)
sanitized = sanitize_for_logging({
    'phone_e164': '+1234567890',
    'password': 'secret123',
    'api_key': 'key-123',
})
# Returns: {'phone_e164': '*******7890', 'password': '[REDACTED]', 'api_key': '[REDACTED]'}
```

## Requirements Mapping

### Requirement 22: Rate Limiting
- ✅ 22.1: Track request count per tenant per time window
- ✅ 22.2: Return 429 when limit exceeded
- ✅ 22.3: Include Retry-After header
- ✅ 22.4: Use X-TENANT-ID header to identify tenant
- ✅ 22.5: Log rate limit events

### Requirement 1.8: CORS Validation
- ✅ Validate Origin header against tenant.allowed_origins
- ✅ Support wildcard for development
- ✅ Apply strict mode for production

### Requirement 20: PII Encryption
- ✅ 20.1: Encrypt phone numbers before storing
- ✅ 20.2: Decrypt transparently when retrieving
- ✅ 20.3: Support encrypted field lookups
- ✅ 20.4: Mask PII in audit logs
- ✅ 20.5: Provide options to exclude/mask PII in exports

## Testing

All security features have comprehensive test coverage:
- `apps/core/tests/test_rate_limiting.py`: Rate limiting tests
- `apps/core/tests/test_cors.py`: CORS validation tests
- `apps/core/tests/test_encryption.py`: Encryption and PII masking tests

Run tests:
```bash
python manage.py test apps.core.tests.test_rate_limiting
python manage.py test apps.core.tests.test_cors
python manage.py test apps.core.tests.test_encryption
```

## Middleware Order

The middleware is applied in the following order (in settings.py):
1. `RequestIDMiddleware` - Inject request ID
2. `TenantContextMiddleware` - Resolve tenant context
3. `WebhookSubscriptionMiddleware` - Check subscription status
4. `TenantCORSMiddleware` - Validate CORS
5. `RateLimitMiddleware` - Enforce rate limits

This order ensures:
- Request ID is available for all logging
- Tenant context is resolved before CORS/rate limiting
- CORS validation happens before rate limiting
- Rate limiting is the last check before request processing
