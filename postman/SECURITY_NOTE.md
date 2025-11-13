# 🔒 Security: JWT vs API Key Authentication

## ⚠️ IMPORTANT: Use JWT for User Operations

The Postman collection has been updated to use **JWT authentication** by default. This is critical for security.

## Why JWT Instead of API Keys?

### JWT Authentication ✅
- **RBAC Enforced** - Respects user roles and permissions
- **Audit Trail** - Tracks which user performed actions
- **Secure** - Scoped to user's actual permissions
- **Four-Eyes Approval** - Works correctly for sensitive operations

### API Key Authentication ⚠️
- **NO RBAC** - Bypasses all permission checks
- **No User Context** - Can't track who did what
- **Security Risk** - Full access to everything
- **Use ONLY for** - Webhooks and system integrations

## How to Use the Collection

### Step 1: Login to Get JWT Token

1. Open **Authentication → Login**
2. Update the request body with your credentials:
   ```json
   {
     "email": "your@email.com",
     "password": "yourpassword"
   }
   ```
3. Click **Send**
4. The `access_token` is automatically saved to `{{access_token}}` variable

### Step 2: Use Other Endpoints

All other endpoints now automatically use:
- **Authorization:** Bearer `{{access_token}}` (inherited from collection)
- **X-TENANT-ID:** `{{tenant_id}}` (set per request)

**RBAC is now enforced!** ✅

## Example: Testing Catalog Access

### Without Proper Scope (403 Forbidden)
```bash
# User without catalog:view scope
GET /v1/products/
Headers:
  Authorization: Bearer <token>
  X-TENANT-ID: <tenant_id>

Response: 403 Forbidden
{
  "detail": "Missing required scope: catalog:view"
}
```

### With Proper Scope (200 OK)
```bash
# User with catalog:view scope
GET /v1/products/
Headers:
  Authorization: Bearer <token>
  X-TENANT-ID: <tenant_id>

Response: 200 OK
{
  "results": [...]
}
```

## When to Use API Keys

**ONLY use API keys for:**

1. **Webhooks** (already configured correctly)
   - Twilio webhooks
   - WooCommerce webhooks
   - Shopify webhooks

2. **System Integrations** (if needed)
   - CI/CD pipelines
   - Automated scripts
   - Background jobs

**NEVER use API keys for:**
- ❌ Testing in Postman
- ❌ User-facing operations
- ❌ Anything that needs RBAC
- ❌ Operations requiring audit trail

## Token Expiration

JWT tokens expire after 24 hours (default). When expired:

1. Use **Authentication → Refresh Token** to get a new token
2. Or login again

## Security Best Practices

1. ✅ Always use JWT for user operations
2. ✅ Never commit tokens to git
3. ✅ Rotate API keys regularly
4. ✅ Use environment variables for sensitive data
5. ✅ Test with users having different roles to verify RBAC

## Testing RBAC

### Create Test Users with Different Roles

```bash
# Create user with limited permissions
POST /v1/memberships/<tenant_id>/invite
Body: {
  "email": "analyst@example.com",
  "role_ids": ["<analyst_role_id>"]
}

# Login as that user
POST /v1/auth/login
Body: {
  "email": "analyst@example.com",
  "password": "password"
}

# Try to edit products (should fail - analyst only has view)
POST /v1/products/
Headers:
  Authorization: Bearer <analyst_token>
  X-TENANT-ID: <tenant_id>

Response: 403 Forbidden
{
  "detail": "Missing required scope: catalog:edit"
}
```

## Summary

- 🔒 **JWT = Secure** - Use for all user operations
- ⚠️ **API Key = Bypass** - Use only for system operations
- ✅ **Collection Updated** - Now uses JWT by default
- 🎯 **RBAC Enforced** - Permissions are now checked

**Always login first, then use the collection!**
