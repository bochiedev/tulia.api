# Security Fix: TenantContextMiddleware Path Configuration

## Issue Identified

A recent change to `apps/tenants/middleware.py` introduced two security issues:

### 1. Invalid `/v1/admin/` Path
- **Added to**: `JWT_ONLY_PATHS`
- **Problem**: This path doesn't exist in the codebase
- **Risk**: Could create confusion and potential security gaps
- **Resolution**: Removed from `JWT_ONLY_PATHS`

### 2. Duplicate `/v1/auth/refresh-token` Entry
- **Added to**: Both `PUBLIC_PATHS` and `JWT_ONLY_PATHS`
- **Problem**: Redundant and confusing configuration
- **Resolution**: Kept in `PUBLIC_PATHS` only (correct location)

## Correct Configuration

### PUBLIC_PATHS (No authentication required)
```python
PUBLIC_PATHS = [
    '/v1/webhooks/',           # External webhooks (signature verified)
    '/v1/health',              # Health check
    '/v1/auth/register',       # User registration
    '/v1/auth/login',          # User login
    '/v1/auth/verify-email',   # Email verification
    '/v1/auth/forgot-password', # Password reset request
    '/v1/auth/reset-password',  # Password reset
    '/v1/auth/refresh-token',  # Token refresh (JWT auth handled by view)
    '/schema',                 # OpenAPI schema
    '/admin/',                 # Django admin (session auth)
]
```

### JWT_ONLY_PATHS (JWT required, no tenant context)
```python
JWT_ONLY_PATHS = [
    '/v1/tenants',    # Tenant list and create
    '/v1/auth/me',    # User profile
    '/v1/auth/logout', # Logout
]
```

## Why `/v1/auth/refresh-token` is in PUBLIC_PATHS

The refresh token endpoint:
1. **Requires JWT authentication** - But this is handled by the view itself, not the middleware
2. **No tenant context needed** - User might be switching tenants
3. **Django AuthenticationMiddleware still runs** - Sets `request.user` from JWT
4. **View validates authentication** - Returns 401 if user not authenticated

## Why `/v1/admin/` Was Removed

1. **Path doesn't exist** - Django admin is at `/admin/`, not `/v1/admin/`
2. **Wrong authentication method** - Django admin uses session auth, not JWT
3. **Already covered** - `/admin/` is in PUBLIC_PATHS with correct session auth

## Security Implications

✅ **After fix**:
- All authentication paths correctly configured
- No duplicate entries
- No non-existent paths
- Clear separation between public, JWT-only, and tenant-scoped endpoints

❌ **Before fix**:
- Confusing duplicate entries
- Non-existent path could cause unexpected behavior
- Unclear authentication requirements

## Testing Recommendations

1. **Verify refresh token works**:
   ```bash
   curl -X POST http://localhost:8000/v1/auth/refresh-token \
     -H "Authorization: Bearer <valid-jwt-token>"
   ```

2. **Verify Django admin works**:
   ```bash
   # Should redirect to login
   curl http://localhost:8000/admin/
   ```

3. **Verify tenant-scoped endpoints require tenant context**:
   ```bash
   # Should return 401 without X-TENANT-ID
   curl -X GET http://localhost:8000/v1/products/ \
     -H "Authorization: Bearer <valid-jwt-token>"
   ```

## Related Files

- `apps/tenants/middleware.py` - Fixed middleware configuration
- `apps/rbac/views_auth.py` - RefreshTokenView implementation
- `.kiro/specs/django-admin-access-fix/tasks.md` - Admin access requirements

## Date

2025-01-14

## Status

✅ **FIXED** - Security issue resolved, middleware configuration corrected
