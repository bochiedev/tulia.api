# Design Document

## Overview

This design addresses the issue where Django admin is blocked by tenant authentication middleware. The solution ensures that `/admin` paths bypass tenant header validation while maintaining security for all API endpoints.

## Architecture

The fix involves modifying the `TenantContextMiddleware` to properly handle public paths, specifically the Django admin interface. The middleware already has a `PUBLIC_PATHS` list and an `_is_public_path()` method, but the current implementation still requires tenant headers even for public paths.

### Current Flow

```
Request → TenantContextMiddleware
  ↓
  Extract headers (X-TENANT-ID, X-TENANT-API-KEY)
  ↓
  Check if headers present → NO → Return 401 error
  ↓
  (Public path check happens too late)
```

### Proposed Flow

```
Request → TenantContextMiddleware
  ↓
  Check if path is public (e.g., /admin/)
  ↓
  YES → Set tenant=None, membership=None, scopes=set() → Continue
  ↓
  NO → Extract and validate tenant headers → Continue or Return 401
```

## Components and Interfaces

### Modified Component: TenantContextMiddleware

**Location:** `apps/tenants/middleware.py`

**Changes:**

1. **Move public path check earlier** - Check if the path is public BEFORE extracting and validating headers
2. **Update PUBLIC_PATHS documentation** - Add comments explaining why each path is public
3. **Add debug logging** - Log when requests bypass tenant authentication

**Public Paths:**

- `/v1/webhooks/` - External webhook callbacks (verified by signature)
- `/v1/health` - Health check endpoint for monitoring
- `/schema` - OpenAPI schema endpoints for documentation
- `/admin/` - Django admin interface (uses session authentication)

### No Changes Required

- **Django Admin Configuration** - No changes needed; admin continues to use session authentication
- **API Endpoints** - All `/v1/` endpoints (except webhooks and health) continue to require tenant headers
- **Other Middleware** - No changes to other middleware components

## Data Models

No data model changes required.

## Error Handling

### Current Behavior (Incorrect)

- Request to `/admin` → 401 error with message "X-TENANT-ID and X-TENANT-API-KEY headers are required"

### New Behavior (Correct)

- Request to `/admin` → Bypasses tenant authentication → Django admin handles authentication via sessions
- Request to `/v1/products` without headers → 401 error (unchanged)
- Request to `/v1/webhooks/twilio` → Bypasses tenant authentication (unchanged)

## Testing Strategy

### Unit Tests

Not required - this is a simple logic reordering in existing middleware.

### Manual Testing

1. **Test Django Admin Access**
   - Navigate to `http://localhost:8000/admin`
   - Should see Django admin login page (not 401 error)
   - Login with superuser credentials
   - Should access admin successfully

2. **Test API Endpoint Protection**
   - Request to `http://localhost:8000/v1/products` without headers
   - Should return 401 error with "X-TENANT-ID and X-TENANT-API-KEY headers are required"

3. **Test Public Endpoints**
   - Request to `http://localhost:8000/v1/health` without headers
   - Should return 200 OK
   - Request to `http://localhost:8000/schema` without headers
   - Should return OpenAPI schema

### Integration Tests

Existing tests should continue to pass without modification, as the change only affects the order of checks in the middleware.

## Security Considerations

### Maintained Security

- **API Endpoints** - All `/v1/` endpoints (except webhooks and health) continue to require tenant authentication
- **Multi-tenant Isolation** - Tenant data isolation is maintained for all API endpoints
- **Webhook Security** - Webhooks continue to be verified by signature validation

### Django Admin Security

- **Session Authentication** - Django admin continues to use Django's built-in session authentication
- **Superuser Requirement** - Only Django superusers can access admin (enforced by Django)
- **No Tenant Context** - Admin requests have `request.tenant = None`, preventing accidental tenant data access

### Risk Assessment

**Risk:** Admin views might attempt to access `request.tenant` and fail

**Mitigation:** Django admin views don't use tenant context; they operate on the global database level. The admin is designed for system-level management, not tenant-specific operations.

## Implementation Notes

The fix is minimal and involves:

1. Moving the `_is_public_path()` check to the beginning of `process_request()`
2. Early return when path is public (setting tenant/membership/scopes to None/empty)
3. Adding debug logging for public path access
4. Adding inline comments to PUBLIC_PATHS list

This is a low-risk change that fixes a critical usability issue without compromising security.
