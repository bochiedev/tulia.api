# Authentication Methods Comparison

## Overview

This document compares the old API key authentication with the new JWT token authentication to help understand the benefits and changes.

## Side-by-Side Comparison

| Feature | API Keys (Old) | JWT Tokens (New) |
|---------|---------------|------------------|
| **Authentication Method** | X-TENANT-API-KEY header | Authorization: Bearer header |
| **User Identity** | ❌ No user tracking | ✅ Tied to specific user |
| **Audit Trail** | ❌ Tenant-level only | ✅ User-level tracking |
| **Expiration** | ❌ Never expires | ✅ 24 hours |
| **Revocation** | ❌ Manual deletion | ✅ Automatic expiration |
| **RBAC Integration** | ❌ Tenant-wide permissions | ✅ Per-user permissions |
| **Security** | ⚠️ Shared credentials | ✅ Individual credentials |
| **Industry Standard** | ❌ Custom implementation | ✅ JWT standard (RFC 7519) |
| **Multi-User Support** | ❌ Same key for all users | ✅ Different token per user |
| **Permission Granularity** | ❌ All or nothing | ✅ Fine-grained per user |

## Request Examples

### API Key (Old)

```bash
# All users share the same API key
curl -X GET https://api.tulia.ai/v1/products \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: shared-api-key-123"

# Problems:
# - Can't tell which user made the request
# - All users have same permissions
# - Key never expires
# - If leaked, affects all users
```

### JWT Token (New)

```bash
# Each user has their own token
curl -X POST https://api.tulia.ai/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Response: {"token": "eyJ...", "user": {...}}

curl -X GET https://api.tulia.ai/v1/products \
  -H "Authorization: Bearer eyJ..." \
  -H "X-TENANT-ID: tenant-uuid"

# Benefits:
# - Know exactly which user made the request
# - Each user has different permissions
# - Token expires after 24 hours
# - If leaked, only affects one user
```

## Authentication Flow

### API Key Flow (Old)

```
1. Admin generates API key for tenant
2. API key is shared with all users
3. Users include API key in requests
4. System validates API key belongs to tenant
5. All users have same permissions
```

**Problems:**
- No user identity
- Shared credentials
- No expiration
- No audit trail

### JWT Token Flow (New)

```
1. User logs in with email/password
2. System generates JWT token for user
3. User includes token in requests
4. System validates token and extracts user identity
5. System resolves user's specific permissions
6. Token expires after 24 hours
```

**Benefits:**
- User identity tracked
- Individual credentials
- Automatic expiration
- Complete audit trail

## Security Comparison

### API Key Security (Old)

| Aspect | Security Level | Notes |
|--------|---------------|-------|
| **Credential Sharing** | ❌ Low | Same key shared by all users |
| **Expiration** | ❌ None | Keys never expire |
| **Revocation** | ⚠️ Manual | Must manually delete key |
| **Audit Trail** | ❌ Limited | Only know tenant, not user |
| **Leak Impact** | ❌ High | Affects all users |
| **Rotation** | ⚠️ Manual | Must manually generate new key |

### JWT Token Security (New)

| Aspect | Security Level | Notes |
|--------|---------------|-------|
| **Credential Sharing** | ✅ High | Each user has own token |
| **Expiration** | ✅ Automatic | 24-hour expiration |
| **Revocation** | ✅ Automatic | Expires automatically |
| **Audit Trail** | ✅ Complete | Know exact user |
| **Leak Impact** | ✅ Low | Only affects one user |
| **Rotation** | ✅ Automatic | New token on each login |

## RBAC Integration

### API Key (Old)

```python
# All users with API key have same permissions
# No way to differentiate between users
# No way to grant/deny specific permissions

if validate_api_key(tenant, api_key):
    # All users can do everything
    allow_access()
```

**Limitations:**
- No per-user permissions
- No role-based access
- No permission overrides
- No four-eyes approval

### JWT Token (New)

```python
# Each user has specific permissions based on roles
# Can grant/deny permissions per user
# Supports four-eyes approval

user = get_user_from_jwt(token)
membership = get_membership(tenant, user)
scopes = resolve_scopes(membership)

if 'catalog:edit' in scopes:
    allow_access()
else:
    deny_access()
```

**Benefits:**
- Per-user permissions
- Role-based access control
- User-specific overrides
- Four-eyes approval support

## Audit Trail Comparison

### API Key (Old)

```json
{
  "timestamp": "2025-11-13T10:00:00Z",
  "action": "product_created",
  "tenant_id": "tenant-uuid",
  "user": "unknown"  // ❌ Can't identify user
}
```

### JWT Token (New)

```json
{
  "timestamp": "2025-11-13T10:00:00Z",
  "action": "product_created",
  "tenant_id": "tenant-uuid",
  "user_id": "user-uuid",
  "user_email": "john@example.com",  // ✅ Know exact user
  "scopes": ["catalog:edit"],
  "request_id": "req-123"
}
```

## Use Case Comparison

### Use Case 1: Multiple Team Members

**API Key (Old):**
```
Problem: All team members share same API key
- Can't tell who did what
- Can't revoke access for one person
- Can't give different permissions
- If one person leaves, must change key for everyone
```

**JWT Token (New):**
```
Solution: Each team member has own account
- Know exactly who did what
- Can revoke access for one person
- Can give different permissions per person
- If one person leaves, only their access is revoked
```

### Use Case 2: Compliance & Audit

**API Key (Old):**
```
Problem: Can't prove who performed actions
- Audit logs show tenant, not user
- Can't meet compliance requirements
- Can't track individual accountability
```

**JWT Token (New):**
```
Solution: Complete audit trail per user
- Audit logs show exact user
- Meets compliance requirements (SOC2, GDPR)
- Full individual accountability
```

### Use Case 3: Security Incident

**API Key (Old):**
```
Problem: If API key is leaked
- All users affected
- Must regenerate key
- Must update key everywhere
- All users must update their code
```

**JWT Token (New):**
```
Solution: If token is leaked
- Only one user affected
- Token expires in 24 hours
- User just needs to login again
- Other users unaffected
```

### Use Case 4: Permission Management

**API Key (Old):**
```
Problem: Can't differentiate permissions
- All users have same access
- Can't restrict sensitive operations
- Can't implement four-eyes approval
```

**JWT Token (New):**
```
Solution: Fine-grained permissions per user
- Each user has specific permissions
- Can restrict sensitive operations
- Can implement four-eyes approval
- Can grant temporary access
```

## Migration Impact

### What Changes

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **API Requests** | Add Authorization header | Low |
| **Client Code** | Implement login flow | Medium |
| **Error Handling** | Handle 401 (token expiration) | Low |
| **Token Storage** | Store token securely | Low |
| **Webhooks** | No change | None |

### What Stays the Same

- ✅ X-TENANT-ID header still required
- ✅ Webhook endpoints unchanged
- ✅ API endpoints unchanged
- ✅ Response formats unchanged
- ✅ Error codes unchanged (except auth)

## Performance Comparison

### API Key (Old)

```
Request → Validate API key hash → Allow/Deny
Time: ~5ms
```

### JWT Token (New)

```
Request → Validate JWT signature → Extract user → 
Resolve RBAC scopes (cached) → Allow/Deny
Time: ~10ms (first request), ~5ms (cached)
```

**Impact:** Minimal performance difference due to caching.

## Cost Comparison

### API Key (Old)

```
Costs:
- Manual key management
- Security incidents (leaked keys)
- Compliance failures
- Limited audit capabilities
```

### JWT Token (New)

```
Costs:
- Initial implementation (one-time)
- Token storage (minimal)

Benefits:
- Reduced security incidents
- Better compliance
- Complete audit trail
- Reduced support burden
```

## Developer Experience

### API Key (Old)

```python
# Simple but limited
headers = {
    'X-TENANT-ID': 'tenant-uuid',
    'X-TENANT-API-KEY': 'api-key'
}
```

**Pros:**
- Simple to use
- No login required

**Cons:**
- No user identity
- Shared credentials
- Security concerns

### JWT Token (New)

```python
# Slightly more complex but much better
# Login once
token = login('user@example.com', 'password')

# Use token
headers = {
    'Authorization': f'Bearer {token}',
    'X-TENANT-ID': 'tenant-uuid'
}
```

**Pros:**
- User identity
- Individual credentials
- Better security
- Industry standard

**Cons:**
- Requires login step
- Must handle expiration

## Recommendation

### When to Use JWT Tokens (New)

✅ **Always** for user operations:
- Web applications
- Mobile applications
- Desktop applications
- CLI tools
- Any user-facing interface

### When Webhooks Stay Public

✅ **Always** for external services:
- Twilio webhooks
- WooCommerce webhooks
- Shopify webhooks
- Payment provider webhooks

## Summary

| Aspect | Winner | Reason |
|--------|--------|--------|
| **Security** | JWT | Individual credentials, expiration |
| **Audit Trail** | JWT | User-level tracking |
| **RBAC** | JWT | Per-user permissions |
| **Compliance** | JWT | Complete audit trail |
| **Simplicity** | API Key | Fewer steps |
| **Industry Standard** | JWT | RFC 7519 standard |
| **Multi-User** | JWT | Individual accounts |
| **Revocation** | JWT | Automatic expiration |

**Overall Winner: JWT Tokens** 🏆

JWT tokens provide significantly better security, audit trail, and RBAC integration with minimal additional complexity.

## Next Steps

1. Review [Authentication Guide](./AUTHENTICATION.md)
2. Follow [Migration Guide](./MIGRATION_API_KEYS_TO_JWT.md)
3. Use [Quick Reference](./JWT_QUICK_REFERENCE.md) for examples
4. Test with your application
5. Deploy to production

## Questions?

- Check [Authentication Guide](./AUTHENTICATION.md)
- Review [Migration Guide](./MIGRATION_API_KEYS_TO_JWT.md)
- Contact support: support@tulia.ai
