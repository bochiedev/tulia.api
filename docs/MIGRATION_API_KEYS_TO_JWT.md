# Migration Guide: API Keys to JWT Authentication

## Overview

This guide helps you migrate from API key authentication to JWT token authentication for user operations.

## What's Changing?

### Before (API Keys)

```bash
curl -X GET https://api.tulia.ai/v1/products \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key"
```

### After (JWT Tokens)

```bash
# 1. Login to get token
curl -X POST https://api.tulia.ai/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your-password"
  }'

# Response: {"token": "eyJ...", "user": {...}}

# 2. Use token in requests
curl -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer eyJ..." \
  -H "X-TENANT-ID: tenant-uuid"
```

## Why This Change?

1. **User Identity**: Know exactly who performed each action
2. **Audit Trail**: Better compliance and security
3. **RBAC Integration**: Per-user permissions instead of tenant-wide
4. **Security**: Tokens expire automatically (24 hours)
5. **Industry Standard**: JWT is widely adopted

## Migration Steps

### Step 1: Get JWT Token

#### Option A: Login with Existing User

```bash
POST /v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}

Response:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

#### Option B: Register New User

```bash
POST /v1/auth/register
Content-Type: application/json

{
  "email": "newuser@example.com",
  "password": "secure-password",
  "business_name": "My Business",
  "first_name": "Jane",
  "last_name": "Smith"
}

Response:
{
  "token": "eyJ...",
  "user": {...},
  "tenant": {...}
}
```

### Step 2: Update Your Client Code

#### Python Example

**Before:**
```python
import requests

headers = {
    'X-TENANT-ID': 'tenant-uuid',
    'X-TENANT-API-KEY': 'your-api-key'
}

response = requests.get(
    'https://api.tulia.ai/v1/products',
    headers=headers
)
```

**After:**
```python
import requests

# Login once to get token
login_response = requests.post(
    'https://api.tulia.ai/v1/auth/login',
    json={
        'email': 'user@example.com',
        'password': 'your-password'
    }
)
token = login_response.json()['token']

# Use token in subsequent requests
headers = {
    'Authorization': f'Bearer {token}',
    'X-TENANT-ID': 'tenant-uuid'
}

response = requests.get(
    'https://api.tulia.ai/v1/products',
    headers=headers
)
```

#### JavaScript Example

**Before:**
```javascript
const headers = {
  'X-TENANT-ID': 'tenant-uuid',
  'X-TENANT-API-KEY': 'your-api-key'
};

const response = await fetch('https://api.tulia.ai/v1/products', {
  headers
});
```

**After:**
```javascript
// Login once to get token
const loginResponse = await fetch('https://api.tulia.ai/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'your-password'
  })
});

const { token } = await loginResponse.json();

// Use token in subsequent requests
const headers = {
  'Authorization': `Bearer ${token}`,
  'X-TENANT-ID': 'tenant-uuid'
};

const response = await fetch('https://api.tulia.ai/v1/products', {
  headers
});
```

#### cURL Example

**Before:**
```bash
curl -X GET https://api.tulia.ai/v1/products \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key"
```

**After:**
```bash
# Login to get token
TOKEN=$(curl -X POST https://api.tulia.ai/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"your-password"}' \
  | jq -r '.token')

# Use token in requests
curl -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: tenant-uuid"
```

### Step 3: Handle Token Expiration

Tokens expire after 24 hours. Implement token refresh logic:

```python
class APIClient:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.token = None
        self.token_expires_at = None
    
    def login(self):
        """Login and get JWT token."""
        response = requests.post(
            'https://api.tulia.ai/v1/auth/login',
            json={'email': self.email, 'password': self.password}
        )
        data = response.json()
        self.token = data['token']
        
        # Token expires in 24 hours
        from datetime import datetime, timedelta
        self.token_expires_at = datetime.now() + timedelta(hours=24)
    
    def ensure_authenticated(self):
        """Ensure we have a valid token."""
        if not self.token or datetime.now() >= self.token_expires_at:
            self.login()
    
    def get(self, url, tenant_id):
        """Make authenticated GET request."""
        self.ensure_authenticated()
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'X-TENANT-ID': tenant_id
        }
        
        response = requests.get(url, headers=headers)
        
        # Handle 401 (token expired)
        if response.status_code == 401:
            self.login()  # Refresh token
            headers['Authorization'] = f'Bearer {self.token}'
            response = requests.get(url, headers=headers)
        
        return response

# Usage
client = APIClient('user@example.com', 'password')
response = client.get('https://api.tulia.ai/v1/products', 'tenant-uuid')
```

### Step 4: Update Environment Variables

Remove API key variables and add user credentials:

**Before:**
```bash
TULIA_TENANT_ID=tenant-uuid
TULIA_API_KEY=your-api-key
```

**After:**
```bash
TULIA_TENANT_ID=tenant-uuid
TULIA_USER_EMAIL=user@example.com
TULIA_USER_PASSWORD=your-password
```

## Common Scenarios

### Scenario 1: Frontend Application

**Store token securely:**

```javascript
// After login
const { token } = await loginResponse.json();

// Option 1: localStorage (simple but less secure)
localStorage.setItem('auth_token', token);

// Option 2: httpOnly cookie (more secure)
// Set cookie on server-side after login

// Retrieve token for requests
const token = localStorage.getItem('auth_token');
```

**Implement auto-refresh:**

```javascript
class APIClient {
  constructor() {
    this.token = localStorage.getItem('auth_token');
  }
  
  async request(url, options = {}) {
    // Add auth header
    options.headers = {
      ...options.headers,
      'Authorization': `Bearer ${this.token}`
    };
    
    let response = await fetch(url, options);
    
    // If 401, try to refresh token
    if (response.status === 401) {
      await this.login();
      options.headers['Authorization'] = `Bearer ${this.token}`;
      response = await fetch(url, options);
    }
    
    return response;
  }
  
  async login() {
    const response = await fetch('/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: this.email,
        password: this.password
      })
    });
    
    const { token } = await response.json();
    this.token = token;
    localStorage.setItem('auth_token', token);
  }
}
```

### Scenario 2: Backend Service

**Use service account:**

```python
import os
import requests
from datetime import datetime, timedelta

class TuliaClient:
    def __init__(self):
        self.email = os.getenv('TULIA_USER_EMAIL')
        self.password = os.getenv('TULIA_USER_PASSWORD')
        self.tenant_id = os.getenv('TULIA_TENANT_ID')
        self.base_url = 'https://api.tulia.ai'
        self.token = None
        self.token_expires_at = None
    
    def _ensure_token(self):
        """Ensure we have a valid token."""
        if not self.token or datetime.now() >= self.token_expires_at:
            self._login()
    
    def _login(self):
        """Login and get JWT token."""
        response = requests.post(
            f'{self.base_url}/v1/auth/login',
            json={'email': self.email, 'password': self.password}
        )
        response.raise_for_status()
        
        data = response.json()
        self.token = data['token']
        self.token_expires_at = datetime.now() + timedelta(hours=23)
    
    def _headers(self):
        """Get headers with auth token."""
        self._ensure_token()
        return {
            'Authorization': f'Bearer {self.token}',
            'X-TENANT-ID': self.tenant_id
        }
    
    def get_products(self):
        """Get products from catalog."""
        response = requests.get(
            f'{self.base_url}/v1/products',
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()
    
    def create_order(self, order_data):
        """Create a new order."""
        response = requests.post(
            f'{self.base_url}/v1/orders',
            json=order_data,
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

# Usage
client = TuliaClient()
products = client.get_products()
```

### Scenario 3: CI/CD Pipeline

**Store credentials as secrets:**

```yaml
# GitHub Actions example
name: Deploy

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run API Tests
        env:
          TULIA_USER_EMAIL: ${{ secrets.TULIA_USER_EMAIL }}
          TULIA_USER_PASSWORD: ${{ secrets.TULIA_USER_PASSWORD }}
          TULIA_TENANT_ID: ${{ secrets.TULIA_TENANT_ID }}
        run: |
          # Login to get token
          TOKEN=$(curl -X POST https://api.tulia.ai/v1/auth/login \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$TULIA_USER_EMAIL\",\"password\":\"$TULIA_USER_PASSWORD\"}" \
            | jq -r '.token')
          
          # Run tests with token
          export TULIA_TOKEN=$TOKEN
          npm test
```

## Webhooks (No Changes Required)

**Webhooks remain public and are verified by signature:**

```python
# Twilio webhook handler
@csrf_exempt
def twilio_webhook(request):
    """
    Handle incoming Twilio messages.
    
    This endpoint is PUBLIC - no JWT required.
    Authentication is via Twilio signature verification.
    """
    # Verify Twilio signature
    if not verify_twilio_signature(request):
        return JsonResponse({'error': 'Invalid signature'}, status=403)
    
    # Process webhook
    # ...
```

## Troubleshooting

### Error: "Missing token"

**Problem:** No Authorization header provided

**Solution:**
```bash
# Add Authorization header
curl -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-TENANT-ID: tenant-uuid"
```

### Error: "Invalid or expired JWT token"

**Problem:** Token has expired (24 hours)

**Solution:** Login again to get a new token

```python
# Implement auto-refresh
if response.status_code == 401:
    # Token expired, login again
    login_response = requests.post('/v1/auth/login', json={...})
    token = login_response.json()['token']
    # Retry request with new token
```

### Error: "You do not have access to this tenant"

**Problem:** User is not a member of the specified tenant

**Solution:**
1. Verify X-TENANT-ID is correct
2. Check user has TenantUser membership
3. Ensure membership status is 'accepted'

```bash
# List tenants user has access to
curl -X GET https://api.tulia.ai/v1/tenants \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Error: "Missing required scope"

**Problem:** User doesn't have required permission

**Solution:**
1. Check user's roles in tenant
2. Verify role has required permission
3. Contact tenant admin to grant permission

## Testing Your Migration

### Test Checklist

- [ ] Login endpoint works
- [ ] Token is stored securely
- [ ] Token is included in all requests
- [ ] Token expiration is handled
- [ ] Error responses are handled
- [ ] Webhooks still work (no changes needed)
- [ ] All API endpoints work with JWT

### Test Script

```bash
#!/bin/bash

# Test login
echo "Testing login..."
RESPONSE=$(curl -s -X POST https://api.tulia.ai/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}')

TOKEN=$(echo $RESPONSE | jq -r '.token')

if [ "$TOKEN" = "null" ]; then
  echo "❌ Login failed"
  exit 1
fi

echo "✅ Login successful"

# Test authenticated request
echo "Testing authenticated request..."
RESPONSE=$(curl -s -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-TENANT-ID: tenant-uuid")

if echo $RESPONSE | jq -e '.error' > /dev/null; then
  echo "❌ Authenticated request failed"
  echo $RESPONSE | jq '.error'
  exit 1
fi

echo "✅ Authenticated request successful"
echo "✅ Migration complete!"
```

## Support

If you encounter issues during migration:

1. Check the [Authentication Documentation](./AUTHENTICATION.md)
2. Review error messages carefully
3. Test with curl first before updating client code
4. Contact support with request_id from error responses

## Timeline

- **Now**: JWT authentication is required for all user operations
- **Webhooks**: No changes required (signature verification)
- **API Keys**: Deprecated for user operations

## Summary

**Key Changes:**
1. Replace `X-TENANT-API-KEY` with `Authorization: Bearer <token>`
2. Login to get JWT token before making requests
3. Handle token expiration (24 hours)
4. Keep `X-TENANT-ID` header for tenant-scoped operations
5. Webhooks unchanged (signature verification)

**Benefits:**
- User-level audit trail
- Per-user permissions (RBAC)
- Automatic token expiration
- Industry standard security
