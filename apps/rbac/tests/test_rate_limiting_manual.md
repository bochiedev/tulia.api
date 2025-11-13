# Rate Limiting Manual Testing Guide

## Overview

Rate limiting has been implemented on all authentication and settings endpoints using `django-ratelimit`. This document provides guidance for manual testing.

## Implemented Rate Limits

### Authentication Endpoints (Per IP)

1. **POST /v1/auth/register** - 10 requests/minute
2. **POST /v1/auth/login** - 10 requests/minute  
3. **POST /v1/auth/forgot-password** - 5 requests/minute

### Settings Endpoints (Per User)

All POST/PUT/DELETE operations on settings endpoints - 60 requests/minute:

- PATCH /v1/settings
- PUT /v1/settings/integrations/woocommerce
- DELETE /v1/settings/integrations/woocommerce
- PUT /v1/settings/integrations/shopify
- DELETE /v1/settings/integrations/shopify
- PUT /v1/settings/integrations/twilio
- DELETE /v1/settings/integrations/twilio
- POST /v1/settings/integrations/openai
- POST /v1/settings/payment-methods
- PUT /v1/settings/payment-methods/{id}/default
- DELETE /v1/settings/payment-methods/{id}
- PUT /v1/settings/payout-method
- DELETE /v1/settings/payout-method
- PUT /v1/settings/business
- POST /v1/settings/api-keys
- DELETE /v1/settings/api-keys/{id}

### Tenant Management Endpoints (Per User)

All POST/PUT/DELETE operations - 60 requests/minute:

- POST /v1/tenants
- PUT /v1/tenants/{id}
- DELETE /v1/tenants/{id}
- POST /v1/tenants/{id}/members
- DELETE /v1/tenants/{id}/members/{user_id}

## Manual Testing

### Test Registration Rate Limit

```bash
# Make 11 registration requests rapidly
for i in {1..11}; do
  curl -X POST http://localhost:8000/v1/auth/register \
    -H "Content-Type: application/json" \
    -d "{
      \"email\": \"user${i}@example.com\",
      \"password\": \"SecurePass123!\",
      \"first_name\": \"Test\",
      \"last_name\": \"User\",
      \"business_name\": \"Business ${i}\"
    }"
  echo ""
done
```

Expected: First 10 succeed or fail with validation errors. 11th returns 429.

### Test Login Rate Limit

```bash
# Make 11 login requests rapidly
for i in {1..11}; do
  curl -X POST http://localhost:8000/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{
      "email": "test@example.com",
      "password": "WrongPassword123!"
    }'
  echo ""
done
```

Expected: First 10 return 401 (wrong password). 11th returns 429.

### Test Forgot Password Rate Limit

```bash
# Make 6 password reset requests rapidly
for i in {1..6}; do
  curl -X POST http://localhost:8000/v1/auth/forgot-password \
    -H "Content-Type: application/json" \
    -d '{
      "email": "test@example.com"
    }'
  echo ""
done
```

Expected: First 5 return 200. 6th returns 429.

### Test Settings Rate Limit

```bash
# Get JWT token first
TOKEN=$(curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }' | jq -r '.token')

# Make 61 settings update requests rapidly
for i in {1..61}; do
  curl -X PATCH http://localhost:8000/v1/settings \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-TENANT-ID: {tenant_id}" \
    -H "Content-Type: application/json" \
    -d '{
      "notification_settings": {
        "email_enabled": true
      }
    }'
  echo ""
done
```

Expected: First 60 succeed or fail with permission errors. 61st returns 429.

## Rate Limit Response Format

When rate limit is exceeded, the API returns:

```json
{
  "error": "Rate limit exceeded. Please try again later.",
  "code": "RATE_LIMIT_EXCEEDED",
  "request_id": "abc123..."
}
```

HTTP Status Code: 429 Too Many Requests

## Configuration

Rate limiting is configured using `django-ratelimit` decorators:

- `@ratelimit(key='ip', rate='10/m', method='POST', block=True)` - For auth endpoints
- `@ratelimit(key='user_or_ip', rate='60/m', method=['POST', 'PUT', 'DELETE'], block=True)` - For settings endpoints

The custom exception handler in `apps/core/exceptions.py` catches `Ratelimited` exceptions and returns proper 429 responses.

## Notes

- Rate limits are per IP for authentication endpoints (prevents brute force attacks)
- Rate limits are per user for settings endpoints (prevents abuse by authenticated users)
- Rate limit counters reset after the time window (1 minute)
- In production, consider using Redis for distributed rate limiting across multiple servers
