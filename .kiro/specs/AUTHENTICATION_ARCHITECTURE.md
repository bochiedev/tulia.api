# Tulia AI Authentication Architecture

## Overview

Tulia AI uses a unified JWT-based authentication system with three distinct access patterns depending on the API endpoint type. This document describes the complete authentication and authorization architecture.

## Authentication Patterns

### 1. Platform Operator APIs (Superuser Access)

**Use Case**: Platform administrators managing the entire system

**Authentication**: JWT token only

**Headers Required**:
```
Authorization: Bearer <jwt_access_token>
```

**Authorization**:
- User must have `is_superuser=True` flag
- Platform-level privileges checked (e.g., `platform:tenants:manage`)
- No tenant context required

**Example Endpoints**:
- `GET /v1/platform/tenants` - List all tenants
- `GET /v1/platform/analytics/overview` - System-wide analytics
- `POST /v1/platform/tenants` - Create new tenant

**Middleware Behavior**:
- Validates JWT token
- Checks `user.is_superuser == True`
- Sets `request.is_platform_operator = True`
- Sets `request.platform_privileges` based on superuser status
- Sets `request.tenant = None` (no tenant context)

---

### 2. Tenant Self-Service APIs (User Managing Own Tenant)

**Use Case**: Users creating and managing their own tenants during onboarding

**Authentication**: JWT token only

**Headers Required**:
```
Authorization: Bearer <jwt_access_token>
```

**Authorization**:
- User must be authenticated (valid JWT)
- RBAC scopes checked based on user's role in tenant
- Tenant context derived from user's membership

**Example Endpoints**:
- `POST /v1/auth/register` - User registration
- `POST /v1/auth/login` - User login
- `POST /v1/tenants` - Create new tenant
- `GET /v1/tenants/me` - List user's tenants
- `POST /v1/tenants/{id}/switch` - Switch tenant context

**Middleware Behavior**:
- Validates JWT token
- For tenant creation: No tenant context required
- For tenant list: Returns all tenants where user has membership
- For tenant operations: Validates user has membership in target tenant

---

### 3. Tenant-Scoped APIs (Standard Tenant Operations)

**Use Case**: Users accessing tenant-specific resources and operations

**Authentication**: JWT token + Tenant API Key + Tenant ID

**Headers Required**:
```
Authorization: Bearer <jwt_access_token>
X-TENANT-ID: <tenant_uuid>
X-TENANT-API-KEY: <tenant_api_key>
```

**Authorization**:
- User must be authenticated (valid JWT)
- Tenant API key must be valid for the specified tenant
- User must have TenantUser membership in the tenant
- RBAC scopes checked based on user's roles in tenant

**Example Endpoints**:
- `GET /v1/customers` - List customers
- `GET /v1/products` - List products
- `POST /v1/orders` - Create order
- `GET /v1/analytics/dashboard` - Tenant analytics
- `POST /v1/settings/integrations/twilio` - Update Twilio credentials

**Middleware Behavior**:
- Validates JWT token
- Validates X-TENANT-API-KEY against tenant's stored keys
- Validates user has TenantUser membership in tenant
- Resolves user's RBAC scopes from roles and permission overrides
- Sets `request.user`, `request.tenant`, `request.membership`, `request.scopes`

---

## JWT Token Structure

### Access Token (1 hour expiry)

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "is_superuser": false,
  "exp": 1699876543,
  "iat": 1699872943,
  "token_type": "access"
}
```

### Refresh Token (7 days expiry)

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "exp": 1700477743,
  "iat": 1699872943,
  "token_type": "refresh"
}
```

## Authentication Endpoints

### User Registration
```http
POST /v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe"
}

Response:
{
  "user_id": "uuid",
  "email": "user@example.com",
  "message": "Registration successful. Please check your email to verify your account."
}
```

### User Login
```http
POST /v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_superuser": false
  }
}
```

### Token Refresh
```http
POST /v1/auth/refresh
Content-Type: application/json

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

## Middleware Flow

```mermaid
flowchart TD
    A[Incoming Request] --> B{Public Path?}
    B -->|Yes| C[Skip Auth]
    B -->|No| D{JWT Token Present?}
    D -->|No| E[401 Unauthorized]
    D -->|Yes| F[Validate JWT]
    F -->|Invalid| E
    F -->|Valid| G{Platform Endpoint?}
    G -->|Yes| H{is_superuser?}
    H -->|No| I[403 Forbidden]
    H -->|Yes| J[Set Platform Context]
    J --> K[Continue to View]
    G -->|No| L{Tenant Headers Present?}
    L -->|No| M{Tenant Self-Service?}
    M -->|Yes| N[Set User Context Only]
    N --> K
    M -->|No| O[403 Tenant Context Required]
    L -->|Yes| P[Validate Tenant API Key]
    P -->|Invalid| E
    P -->|Valid| Q[Check TenantUser Membership]
    Q -->|No Membership| I
    Q -->|Has Membership| R[Resolve RBAC Scopes]
    R --> S[Set Full Tenant Context]
    S --> K
```

## Permission Classes

### HasPlatformPrivileges
Used for platform operator endpoints

```python
class MyPlatformView(APIView):
    permission_classes = [HasPlatformPrivileges]
    required_platform_privileges = {'platform:tenants:view'}
```

### HasTenantScopes
Used for tenant-scoped endpoints

```python
class MyTenantView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view'}
```

### IsAuthenticated (JWT Only)
Used for tenant self-service endpoints

```python
class MyTenantManagementView(APIView):
    permission_classes = [IsAuthenticated]
```

## Security Considerations

### JWT Security
- Tokens signed with SECRET_KEY (256-bit minimum)
- Access tokens short-lived (1 hour)
- Refresh tokens longer-lived (7 days) but can be revoked
- Tokens include user_id and is_superuser claims
- No sensitive data in JWT payload

### Tenant API Key Security
- Keys hashed with SHA-256 before storage
- Plaintext key shown only once at creation
- Keys can be rotated without changing tenant ID
- Multiple keys per tenant supported
- Keys can be revoked individually

### RBAC Security
- Scopes resolved per-request (no caching of permissions)
- Deny overrides always win over allow
- Audit logging for all permission changes
- Four-eyes approval for sensitive operations

### Rate Limiting
- Platform endpoints: 100 req/min per user
- Tenant endpoints: 1000 req/min per tenant
- Auth endpoints: 10 req/min per IP

## Migration Path

### Phase 1: Add JWT Authentication
1. Install djangorestframework-simplejwt
2. Create auth endpoints (register, login, refresh)
3. Add JWT authentication class to REST_FRAMEWORK settings
4. Update middleware to handle JWT tokens

### Phase 2: Update Existing Endpoints
1. Add JWT requirement to all endpoints
2. Keep tenant API key requirement for tenant-scoped endpoints
3. Update documentation and examples
4. Notify existing API clients of changes

### Phase 3: Platform Operator Access
1. Add platform endpoints with HasPlatformPrivileges
2. Create superuser accounts for platform operators
3. Document platform API usage

### Phase 4: Tenant Self-Service
1. Add tenant management endpoints
2. Implement onboarding flow
3. Add tenant switching functionality

## Example Usage

### Platform Operator: List All Tenants
```bash
curl -X GET https://api.trytulia.com/v1/platform/tenants \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### Tenant User: List Customers
```bash
curl -X GET https://api.trytulia.com/v1/customers \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -H "X-TENANT-API-KEY: wiq_abc123..."
```

### User: Create New Tenant
```bash
curl -X POST https://api.trytulia.com/v1/tenants \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My New Business",
    "slug": "my-new-business"
  }'
```

## Error Responses

### 401 Unauthorized (No JWT)
```json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Authentication credentials were not provided"
  }
}
```

### 401 Unauthorized (Invalid JWT)
```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Token is invalid or expired"
  }
}
```

### 403 Forbidden (Not Superuser)
```json
{
  "error": {
    "code": "PLATFORM_ACCESS_DENIED",
    "message": "Platform operator access required"
  }
}
```

### 403 Forbidden (Missing Tenant Context)
```json
{
  "error": {
    "code": "TENANT_CONTEXT_REQUIRED",
    "message": "X-TENANT-ID and X-TENANT-API-KEY headers are required"
  }
}
```

### 403 Forbidden (No Membership)
```json
{
  "error": {
    "code": "TENANT_ACCESS_DENIED",
    "message": "You do not have access to this tenant"
  }
}
```

### 403 Forbidden (Missing Scope)
```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Missing required scopes",
    "details": {
      "required": ["catalog:edit"],
      "missing": ["catalog:edit"]
    }
  }
}
```
