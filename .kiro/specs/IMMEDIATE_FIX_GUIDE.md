# Immediate Fix Guide - Current API Error

## Current Problem

The `/v1/customers` endpoint is returning 403 Forbidden because:
1. The endpoint requires `conversations:view` scope
2. The API is being called with only tenant API key (no user authentication)
3. The middleware sets `request.scopes = set()` when no user is authenticated
4. The permission check fails because the required scope is missing

## Root Cause

The system is designed to require BOTH:
- Tenant API key (for tenant context)
- User authentication (for RBAC scopes)

But currently only tenant API key is being provided.

## Quick Fix Options

### Option 1: Implement JWT Authentication (Recommended)

Follow the updated specs to implement JWT authentication:

1. Install djangorestframework-simplejwt
```bash
pip install djangorestframework-simplejwt
```

2. Add to settings.py:
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}
```

3. Create auth endpoints (see Task 2 in platform-operator-api-access/tasks.md)

4. Update Postman to include JWT token:
```
Authorization: Bearer <jwt_token>
X-TENANT-ID: <tenant_id>
X-TENANT-API-KEY: <api_key>
```

### Option 2: Temporary Workaround (Not Recommended)

Create a service account user and authenticate with it:

1. Create a user via Django admin or shell
2. Create TenantUser membership with Owner role
3. Login to get session/token
4. Use that authentication with tenant headers

### Option 3: Remove RBAC Requirement (Not Recommended)

Temporarily remove the permission class from CustomerListView:

```python
class CustomerListView(APIView):
    # permission_classes = [HasTenantScopes]  # Comment out
    # required_scopes = {'conversations:view'}  # Comment out
```

**Warning**: This removes security controls and should only be used for testing.

## Recommended Path Forward

1. **Immediate**: Use Option 3 to unblock testing (with caution)
2. **Short-term**: Implement Option 1 (JWT authentication)
3. **Long-term**: Follow all specs for complete platform operator and tenant self-service

## Testing After Fix

Once JWT is implemented, test with:

```bash
# 1. Login
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Response: {"access": "eyJ...", "refresh": "eyJ..."}

# 2. Use token with tenant headers
curl -X GET http://localhost:8000/v1/customers \
  -H "Authorization: Bearer eyJ..." \
  -H "X-TENANT-ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b" \
  -H "X-TENANT-API-KEY: your-api-key"
```

## Reference

- See `.kiro/specs/AUTHENTICATION_ARCHITECTURE.md` for complete authentication guide
- See `.kiro/specs/platform-operator-api-access/tasks.md` for implementation tasks
- See `.kiro/specs/SPEC_UPDATES_SUMMARY.md` for overview of changes
