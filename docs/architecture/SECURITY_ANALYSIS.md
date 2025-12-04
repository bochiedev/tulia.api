# Security Analysis: API Key vs JWT Authentication

## 🚨 Critical Security Issue Identified

You've identified a **major security concern**: Using API keys alone bypasses RBAC entirely.

## Current Authentication Flow

### JWT Authentication (User-Based)
```
Request with Authorization: Bearer <token>
  ↓
Middleware validates JWT
  ↓
Sets request.user = User instance
  ↓
Validates TenantUser membership
  ↓
Resolves RBAC scopes from roles + overrides
  ↓
Sets request.scopes = {catalog:view, orders:edit, ...}
  ↓
View checks required scopes
  ↓
✅ RBAC enforced
```

### API Key Authentication (Service-Based)
```
Request with X-TENANT-API-KEY
  ↓
Middleware validates API key
  ↓
Sets request.user = None (AnonymousUser)
  ↓
Skips TenantUser membership check
  ↓
Sets request.scopes = {} (empty)
  ↓
View checks required scopes
  ↓
❌ RBAC BYPASSED!
```

## The Security Risk

**Anyone with an API key has unrestricted access to ALL tenant data**, regardless of:
- User permissions
- Role assignments
- Permission overrides
- Four-eyes approval requirements

**Example Attack Scenario:**
1. Attacker obtains API key (leaked in logs, git, etc.)
2. Attacker can:
   - View all customer data
   - Modify products
   - Approve their own withdrawals (bypassing four-eyes)
   - Delete orders
   - Access analytics
   - **Everything** - no restrictions!

## Recommended Solution

### Use JWT for User Operations, API Keys for System Operations

#### JWT Authentication (User Operations)
**Use for:**
- All Postman testing
- Dashboard/frontend requests
- Any operation that should respect RBAC
- Operations that need audit trail

**Headers:**
```
Authorization: Bearer <jwt_token>
X-TENANT-ID: <tenant_uuid>
```

**Benefits:**
- ✅ Full RBAC enforcement
- ✅ Audit trail with user attribution
- ✅ Respects role assignments
- ✅ Four-eyes approval works correctly

#### API Key Authentication (System Operations)
**Use ONLY for:**
- Webhook callbacks (Twilio, WooCommerce, Shopify)
- System-to-system integrations
- Automated background jobs
- CI/CD pipelines

**Headers:**
```
X-TENANT-ID: <tenant_uuid>
X-TENANT-API-KEY: <api_key>
```

**Limitations:**
- ❌ No RBAC enforcement
- ❌ No user attribution in audit logs
- ⚠️ Should be restricted to specific operations

## Implementation Options

### Option 1: Current Design (Recommended for Now)

**Keep current design but use correctly:**

1. **For Postman Testing** → Use JWT
   ```bash
   # Step 1: Login
   POST /v1/auth/login
   Body: {"email": "user@example.com", "password": "pass"}
   
   # Step 2: Copy access_token from response
   
   # Step 3: Use JWT for all requests
   GET /v1/products/
   Headers:
     Authorization: Bearer <access_token>
     X-TENANT-ID: <tenant_id>
   ```

2. **For Webhooks** → Use API Key
   ```bash
   # Twilio webhook (no user context needed)
   POST /v1/webhooks/twilio/
   Headers:
     X-TWILIO-SIGNATURE: <signature>
   # No API key needed - verified by signature
   ```

3. **For System Scripts** → Use API Key
   ```bash
   # Automated product sync (system operation)
   POST /v1/products/sync/woocommerce
   Headers:
     X-TENANT-ID: <tenant_id>
     X-TENANT-API-KEY: <api_key>
   ```

### Option 2: Enhanced API Keys (Future Enhancement)

**Associate API keys with users and enforce RBAC:**

```python
class TenantAPIKey(BaseModel):
    tenant = ForeignKey(Tenant)
    user = ForeignKey(User)  # ← Associate with user
    key_hash = CharField()
    name = CharField()
    scopes = JSONField()  # ← Restrict to specific scopes
    is_active = BooleanField()
```

**Benefits:**
- API keys can have limited scopes
- Audit trail shows which API key was used
- Can revoke individual keys
- Can create read-only keys, admin keys, etc.

**Implementation:**
1. Add `user` field to `TenantAPIKey` model
2. When validating API key, set `request.user` from key's user
3. Resolve scopes from user's roles + key's scope restrictions
4. Enforce RBAC as normal

## Immediate Action Required

### 1. Update Postman Collection to Use JWT

Change all user-operation requests from:
```json
{
  "header": [
    {"key": "X-TENANT-ID", "value": "{{tenant_id}}"},
    {"key": "X-TENANT-API-KEY", "value": "{{tenant_api_key}}"}
  ]
}
```

To:
```json
{
  "auth": {
    "type": "bearer",
    "bearer": [{"key": "token", "value": "{{access_token}}"}]
  },
  "header": [
    {"key": "X-TENANT-ID", "value": "{{tenant_id}}"}
  ]
}
```

### 2. Document API Key Usage

Add clear documentation:
- ⚠️ API keys bypass RBAC
- ⚠️ Use only for system operations
- ⚠️ Never use for user-facing operations
- ⚠️ Rotate keys regularly
- ⚠️ Never commit keys to git

### 3. Consider Implementing Option 2

For production, implement user-associated API keys with scope restrictions.

## Testing with JWT

### Step 1: Login
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {...}
}
```

### Step 2: Use JWT for Requests
```bash
curl http://localhost:8000/v1/products/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b"
```

**Now RBAC is enforced!** ✅

## Comparison Table

| Feature | JWT Auth | API Key Auth |
|---------|----------|--------------|
| User Context | ✅ Yes | ❌ No |
| RBAC Enforcement | ✅ Yes | ❌ No |
| Audit Trail | ✅ User attributed | ⚠️ Anonymous |
| Scope Checking | ✅ Enforced | ❌ Bypassed |
| Four-Eyes Approval | ✅ Works | ❌ Bypassed |
| Use Case | User operations | System operations |
| Security Level | 🔒 High | ⚠️ Low |

## Conclusion

**You are absolutely correct** - using API keys for user operations is a security risk. 

**Recommended approach:**
1. Use JWT for all Postman testing and user operations
2. Reserve API keys for webhooks and system integrations only
3. Consider implementing user-associated API keys with scope restrictions for production

**Immediate next step:** Update Postman collection to use JWT authentication instead of API keys.
