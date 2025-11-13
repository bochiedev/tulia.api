# JWT Authentication Quick Reference

## Quick Start

### 1. Login

```bash
curl -X POST https://api.tulia.ai/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"your-password"}'
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

### 2. Use Token

```bash
curl -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer eyJ..." \
  -H "X-TENANT-ID: tenant-uuid"
```

## Common Patterns

### Python

```python
import requests

# Login
response = requests.post('https://api.tulia.ai/v1/auth/login', json={
    'email': 'user@example.com',
    'password': 'password'
})
token = response.json()['token']

# Use token
headers = {
    'Authorization': f'Bearer {token}',
    'X-TENANT-ID': 'tenant-uuid'
}
response = requests.get('https://api.tulia.ai/v1/products', headers=headers)
```

### JavaScript

```javascript
// Login
const loginResponse = await fetch('https://api.tulia.ai/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password'
  })
});
const { token } = await loginResponse.json();

// Use token
const response = await fetch('https://api.tulia.ai/v1/products', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-TENANT-ID': 'tenant-uuid'
  }
});
```

### cURL

```bash
# Login and save token
TOKEN=$(curl -s -X POST https://api.tulia.ai/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.token')

# Use token
curl -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: tenant-uuid"
```

## Endpoint Types

### Public Endpoints (No Auth)

```bash
# Health check
GET /v1/health

# Register
POST /v1/auth/register

# Login
POST /v1/auth/login

# Webhooks (signature-verified)
POST /v1/webhooks/twilio
POST /v1/webhooks/woocommerce
POST /v1/webhooks/shopify
```

### JWT-Only Endpoints (No Tenant)

```bash
# User profile
GET /v1/auth/me
Authorization: Bearer <token>

# List tenants
GET /v1/tenants
Authorization: Bearer <token>
```

### Tenant-Scoped Endpoints

```bash
# Products
GET /v1/products
Authorization: Bearer <token>
X-TENANT-ID: <tenant-uuid>

# Orders
POST /v1/orders
Authorization: Bearer <token>
X-TENANT-ID: <tenant-uuid>
```

## Error Handling

### 401 Unauthorized

**Missing Token:**
```json
{
  "error": {
    "code": "MISSING_TOKEN",
    "message": "Authorization header with Bearer token is required"
  }
}
```

**Invalid Token:**
```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Invalid or expired JWT token"
  }
}
```

**Solution:** Login again to get a new token.

### 403 Forbidden

**No Access:**
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have access to this tenant"
  }
}
```

**Solution:** Verify X-TENANT-ID and user membership.

## Token Expiration

Tokens expire after **24 hours**.

### Handle Expiration

```python
def make_request(url, headers):
    response = requests.get(url, headers=headers)
    
    # If 401, refresh token
    if response.status_code == 401:
        token = login()  # Get new token
        headers['Authorization'] = f'Bearer {token}'
        response = requests.get(url, headers=headers)
    
    return response
```

## Security Best Practices

1. **HTTPS Only** - Always use HTTPS in production
2. **Secure Storage** - Store tokens securely (httpOnly cookies)
3. **Short Expiration** - 24-hour expiration limits exposure
4. **No Sensitive Data** - Tokens contain only user_id and email
5. **Validate Responses** - Check for 401/403 errors

## Testing

### Test Login

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

### Test Authenticated Request

```bash
TOKEN="your-token-here"
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: tenant-uuid"
```

## Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

## Common Issues

### "Invalid or expired JWT token"

- Token has expired (24 hours)
- Token format is incorrect
- JWT_SECRET_KEY mismatch

**Fix:** Login again to get a new token.

### "You do not have access to this tenant"

- User is not a member of the tenant
- Membership status is not 'accepted'
- X-TENANT-ID is incorrect

**Fix:** Verify tenant membership and X-TENANT-ID.

### "Missing required scope"

- User doesn't have required permission
- Role doesn't include permission
- User-level permission deny

**Fix:** Contact tenant admin to grant permission.

## Full Documentation

- [Authentication Guide](./AUTHENTICATION.md)
- [Migration Guide](./MIGRATION_API_KEYS_TO_JWT.md)
- [RBAC Quick Reference](../.kiro/steering/rbac-quick-reference.md)

## Support

For help:
1. Check error message and code
2. Review documentation
3. Test with curl first
4. Contact support with request_id
