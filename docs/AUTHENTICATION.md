# Authentication Architecture

## Overview

WabotIQ uses **JWT (JSON Web Token) authentication** for all user operations. This document explains the authentication flow, token management, and security considerations.

## Authentication Methods

### 1. JWT Token Authentication (User Operations)

**All user-facing API endpoints require JWT authentication.**

#### How It Works

1. **Registration/Login**: User obtains a JWT token
2. **Token Usage**: Include token in `Authorization` header for all requests
3. **Token Validation**: Middleware validates token and extracts user identity
4. **RBAC Resolution**: System resolves user's permissions based on tenant membership

#### Token Format

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Token Payload

```json
{
  "user_id": "uuid-of-user",
  "email": "user@example.com",
  "exp": 1234567890,  // Expiration timestamp
  "iat": 1234567890   // Issued at timestamp
}
```

#### Token Expiration

- Default: 24 hours (configurable via `JWT_EXPIRATION_HOURS`)
- After expiration, user must login again to get a new token
- Future: Implement refresh tokens for seamless re-authentication

### 2. Webhook Signature Verification (External Services)

**Webhooks are public endpoints that don't require JWT tokens.**

Webhooks from external services (Twilio, WooCommerce, Shopify) are verified using:
- **Signature verification**: Each provider signs requests with a secret
- **Timestamp validation**: Reject old requests to prevent replay attacks
- **IP whitelisting** (optional): Restrict to known provider IPs

#### Public Webhook Paths

```python
PUBLIC_PATHS = [
    '/v1/webhooks/twilio',
    '/v1/webhooks/woocommerce',
    '/v1/webhooks/shopify',
    '/v1/health',
]
```

## Authentication Flow

### User Registration

```bash
POST /v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password",
  "business_name": "My Business",
  "first_name": "John",
  "last_name": "Doe"
}

Response:
{
  "token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "tenant": {
    "id": "uuid",
    "name": "My Business",
    "slug": "my-business",
    "status": "trial"
  }
}
```

### User Login

```bash
POST /v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password"
}

Response:
{
  "token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

### Making Authenticated Requests

#### JWT-Only Endpoints (No Tenant Context)

These endpoints work across all tenants the user has access to:

```bash
# Get user profile
GET /v1/auth/me
Authorization: Bearer eyJ...

# List all tenants user has access to
GET /v1/tenants
Authorization: Bearer eyJ...
```

#### Tenant-Scoped Endpoints

These endpoints require both JWT token AND tenant context:

```bash
# Get products for a specific tenant
GET /v1/products
Authorization: Bearer eyJ...
X-TENANT-ID: tenant-uuid

# Create an order
POST /v1/orders
Authorization: Bearer eyJ...
X-TENANT-ID: tenant-uuid
Content-Type: application/json

{
  "customer_id": "customer-uuid",
  "items": [...]
}
```

## Middleware Flow

### TenantContextMiddleware

This middleware handles authentication and tenant context resolution:

```
1. Extract request_id for tracing
2. Check if path is public (webhooks, health) → Skip auth
3. Extract Authorization header
4. Validate JWT token → Get user
5. Check if path is JWT-only (tenant list) → Skip tenant validation
6. Extract X-TENANT-ID header
7. Validate tenant exists and is active
8. Validate user has membership in tenant
9. Resolve user's RBAC scopes
10. Attach to request: user, tenant, membership, scopes
```

### Request Object Attributes

After middleware processing, the request object has:

```python
request.user          # User instance (from JWT)
request.tenant        # Tenant instance (from X-TENANT-ID)
request.membership    # TenantUser instance
request.scopes        # Set of permission codes
request.request_id    # Unique request ID for tracing
```

## RBAC Integration

JWT authentication is tightly integrated with RBAC:

1. **User Identity**: JWT provides user identity
2. **Tenant Context**: X-TENANT-ID header specifies which tenant
3. **Membership Validation**: Middleware checks TenantUser exists
4. **Scope Resolution**: RBACService resolves permissions from roles
5. **Permission Enforcement**: HasTenantScopes checks required scopes

### Example: Catalog View

```python
class ProductListView(APIView):
    """
    List products in catalog.
    
    Required scope: catalog:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view'}
    
    def get(self, request):
        # request.user - authenticated user
        # request.tenant - tenant from X-TENANT-ID
        # request.scopes - user's permissions in this tenant
        
        products = Product.objects.filter(tenant=request.tenant)
        # ...
```

## Security Considerations

### Token Security

1. **HTTPS Only**: Always use HTTPS in production
2. **Secure Storage**: Store tokens securely (httpOnly cookies or secure storage)
3. **Short Expiration**: 24-hour expiration limits exposure window
4. **No Sensitive Data**: Tokens contain only user_id and email

### Token Validation

1. **Signature Verification**: JWT signature prevents tampering
2. **Expiration Check**: Expired tokens are rejected
3. **User Active Check**: Inactive users can't authenticate
4. **Membership Check**: User must have accepted membership

### Tenant Isolation

1. **Explicit Tenant ID**: X-TENANT-ID must be provided
2. **Membership Validation**: User must be member of tenant
3. **Scope Enforcement**: Every endpoint checks required scopes
4. **Object-Level Checks**: HasTenantScopes validates object.tenant

### Webhook Security

1. **Signature Verification**: Validate webhook signatures
2. **Timestamp Validation**: Reject old requests
3. **Idempotency**: Handle duplicate webhooks gracefully
4. **Rate Limiting**: Prevent webhook flooding

## Error Responses

### 401 Unauthorized

Missing or invalid authentication:

```json
{
  "error": {
    "code": "MISSING_TOKEN",
    "message": "Authorization header with Bearer token is required"
  }
}
```

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Invalid or expired JWT token"
  }
}
```

### 403 Forbidden

Valid authentication but insufficient permissions:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have access to this tenant"
  }
}
```

```json
{
  "error": {
    "code": "SUBSCRIPTION_INACTIVE",
    "message": "Your subscription is inactive. Please update your payment method.",
    "details": {
      "subscription_status": "trial_expired",
      "trial_end_date": "2025-11-01T00:00:00Z"
    }
  }
}
```

## Migration from API Keys

**API keys are deprecated for user operations.**

### Why JWT Instead of API Keys?

1. **User Identity**: JWT tokens are tied to specific users
2. **Audit Trail**: Know exactly who performed each action
3. **RBAC Integration**: Permissions are per-user, not per-tenant
4. **Security**: Tokens expire automatically
5. **Standard**: JWT is an industry standard

### Migration Path

If you're currently using API keys:

1. **Login**: Call `/v1/auth/login` to get JWT token
2. **Update Clients**: Replace `X-TENANT-API-KEY` with `Authorization: Bearer <token>`
3. **Keep X-TENANT-ID**: Still required for tenant-scoped operations

### API Keys Still Supported For

- **Service-to-service**: Internal system integrations (if needed)
- **Webhooks**: Use signature verification instead

## Future Enhancements

### Refresh Tokens

Implement refresh tokens for seamless re-authentication:

```bash
POST /v1/auth/refresh-token
Authorization: Bearer <refresh_token>

Response:
{
  "token": "new-access-token",
  "refresh_token": "new-refresh-token"
}
```

### OAuth2 / Social Login

Support OAuth2 providers:
- Google
- Microsoft
- GitHub

### Multi-Factor Authentication (MFA)

Add optional MFA for enhanced security:
- TOTP (Time-based One-Time Password)
- SMS verification
- Email verification

### Session Management

Track active sessions and allow users to:
- View active sessions
- Revoke specific sessions
- Logout from all devices

## Testing Authentication

### Unit Tests

```python
def test_jwt_authentication(self):
    """Test JWT token generation and validation."""
    user = User.objects.create(email='test@example.com')
    user.set_password('password')
    user.save()
    
    # Generate token
    token = AuthService.generate_jwt(user)
    
    # Validate token
    validated_user = AuthService.get_user_from_jwt(token)
    assert validated_user.id == user.id
```

### Integration Tests

```python
def test_authenticated_request(self, client, user, tenant):
    """Test authenticated API request."""
    # Login to get token
    response = client.post('/v1/auth/login', {
        'email': user.email,
        'password': 'password'
    })
    token = response.json()['token']
    
    # Make authenticated request
    response = client.get('/v1/products', headers={
        'Authorization': f'Bearer {token}',
        'X-TENANT-ID': str(tenant.id)
    })
    
    assert response.status_code == 200
```

## Troubleshooting

### "Invalid or expired JWT token"

- Check token hasn't expired (24 hours default)
- Verify token format: `Authorization: Bearer <token>`
- Ensure JWT_SECRET_KEY matches between environments

### "You do not have access to this tenant"

- Verify user has TenantUser membership
- Check membership status is 'accepted'
- Confirm X-TENANT-ID is correct

### "Missing required scope"

- Check user's roles in tenant
- Verify role has required permission
- Check for user-level permission denies

## Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Django Secret (used as fallback for JWT_SECRET_KEY)
SECRET_KEY=your-django-secret-key
```

### Settings

```python
# config/settings.py

# JWT Authentication
JWT_SECRET_KEY = env('JWT_SECRET_KEY', default=SECRET_KEY)
JWT_ALGORITHM = env('JWT_ALGORITHM', default='HS256')
JWT_EXPIRATION_HOURS = env.int('JWT_EXPIRATION_HOURS', default=24)

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],  # Handled by middleware
    'DEFAULT_PERMISSION_CLASSES': [],
}
```

## Summary

- **JWT tokens** for all user operations
- **Signature verification** for webhooks
- **RBAC integration** for fine-grained permissions
- **Tenant isolation** via X-TENANT-ID header
- **Secure by default** with HTTPS and token expiration
