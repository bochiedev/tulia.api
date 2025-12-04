# Authentication Guide - JWT & Postman Setup

## Overview

The TuliaAI API uses **JWT (JSON Web Token)** authentication for all user operations. This guide explains how to authenticate and use the API with Postman.

## Authentication Methods

### 1. JWT Token (Required for User Operations)

**Format:**
```
Authorization: Bearer <token>
```

**Used for:**
- All user-specific operations
- Tenant management
- RBAC operations
- Product/Order/Service management

**How to get token:**
- Register: `POST /v1/auth/register`
- Login: `POST /v1/auth/login`

**Token lifespan:** 24 hours (configurable via `JWT_EXPIRATION_HOURS`)

### 2. Tenant Context (Required for Most Endpoints)

**Format:**
```
X-TENANT-ID: <tenant-uuid>
```

**Used for:**
- All tenant-scoped operations (products, orders, etc.)
- Not required for tenant management endpoints

### 3. API Keys (Deprecated for User Operations)

**Format:**
```
X-TENANT-API-KEY: <api-key>
```

**Status:** ⚠️ Deprecated for user operations
**Still used for:** Programmatic access (future feature)

## Postman Setup

### Step 1: Import Collection & Environment

1. Open Postman
2. Click **Import**
3. Select both files:
   - `postman/TuliaAI.postman_collection.json`
   - `postman/TuliaAI.postman_environment.json`
4. Select environment: **TuliaAI Development** (top right dropdown)

### Step 2: Authenticate

#### Option A: Register New User

1. Open **Authentication** → **Register**
2. Update request body:
   ```json
   {
     "email": "your-email@example.com",
     "password": "SecurePass123!",
     "first_name": "John",
     "last_name": "Doe",
     "business_name": "My Business"
   }
   ```
3. Click **Send**
4. ✅ Check console: "Token saved: ..."
5. ✅ Check console: "Tenant ID saved: ..."

**What happens:**
- User account created
- First tenant created with trial status
- TenantUser membership created with Owner role
- JWT token generated and saved to `{{access_token}}`
- Tenant ID saved to `{{tenant_id}}`

#### Option B: Login Existing User

1. Open **Authentication** → **Login**
2. Update request body:
   ```json
   {
     "email": "your-email@example.com",
     "password": "SecurePass123!"
   }
   ```
3. Click **Send**
4. ✅ Check console: "Token saved: ..."

**What happens:**
- User authenticated
- JWT token generated and saved to `{{access_token}}`

### Step 3: Verify Authentication

1. Open **Authentication** → **Get Profile**
2. Click **Send**
3. Should return **200 OK** with user profile:
   ```json
   {
     "id": "...",
     "email": "your-email@example.com",
     "first_name": "John",
     "last_name": "Doe",
     "full_name": "John Doe",
     "email_verified": false,
     "is_active": true
   }
   ```

**If you get 401:**
- Check environment (eye icon) - `access_token` should have a value
- Re-run Login/Register
- Check Authorization header is present in request

### Step 4: Test Tenant-Scoped Endpoint

1. Verify `tenant_id` is set in environment (eye icon)
2. Open **Products** → **List Products**
3. Click **Send**
4. Should return **200 OK** with products list

**If you get 401:**
- Check both `Authorization` and `X-TENANT-ID` headers are present
- Verify token is valid (not expired)
- Verify tenant ID is correct

## How It Works

### Collection-Level Authentication

The Postman collection is configured with Bearer token authentication at the collection level:

```json
{
  "auth": {
    "type": "bearer",
    "bearer": [
      {
        "key": "token",
        "value": "{{access_token}}",
        "type": "string"
      }
    ]
  }
}
```

This means **all requests automatically include:**
```
Authorization: Bearer {{access_token}}
```

### Auto-Save Token Scripts

**Login endpoint** has a test script:
```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set('access_token', jsonData.token);
    console.log('Token saved:', jsonData.token);
}
```

**Register endpoint** has a test script:
```javascript
if (pm.response.code === 201) {
    var jsonData = pm.response.json();
    pm.environment.set('access_token', jsonData.token);
    pm.environment.set('tenant_id', jsonData.tenant.id);
    console.log('Token saved:', jsonData.token);
    console.log('Tenant ID saved:', jsonData.tenant.id);
}
```

These scripts automatically save the token to your environment, so you don't have to copy/paste manually.

## Endpoint Categories

### Public Endpoints (No Auth)

No authentication required:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/verify-email`
- `POST /v1/auth/forgot-password`
- `POST /v1/auth/reset-password`
- `POST /v1/webhooks/twilio` (verified by signature)
- `GET /v1/health`
- `GET /schema/*`

### JWT-Only Endpoints

Require `Authorization: Bearer <token>` only:

- `GET /v1/auth/me` - User profile
- `PUT /v1/auth/me` - Update profile
- `POST /v1/auth/logout` - Logout
- `POST /v1/auth/refresh-token` - Refresh token
- `GET /v1/tenants` - List user's tenants
- `POST /v1/tenants` - Create tenant

### Tenant-Scoped Endpoints

Require both `Authorization: Bearer <token>` AND `X-TENANT-ID: <uuid>`:

- All product endpoints (`/v1/products/*`)
- All order endpoints (`/v1/orders/*`)
- All service endpoints (`/v1/services/*`)
- All message endpoints (`/v1/messages/*`)
- All analytics endpoints (`/v1/analytics/*`)
- Tenant settings (`/v1/settings/*`)
- RBAC endpoints (`/v1/memberships/*`, `/v1/roles/*`)
- Wallet endpoints (`/v1/wallet/*`)

## Troubleshooting

### 401: "Authorization header with Bearer token is required"

**Cause:** No Authorization header present

**Fix:**
1. Check environment (eye icon) - `access_token` should have a value
2. If empty, run Login or Register
3. Verify collection-level auth is enabled (Collection → Authorization → Type: Bearer Token)

### 401: "Invalid or expired JWT token"

**Cause:** Token is invalid or expired (24 hours)

**Fix:**
1. Run Login again to get a new token
2. Check token format: should start with `eyJ`
3. Verify token in Django shell:
   ```python
   from apps.rbac.services import AuthService
   user = AuthService.get_user_from_jwt("YOUR_TOKEN")
   print(user)  # Should show user, not None
   ```

### 401: "X-TENANT-ID header is required"

**Cause:** Tenant-scoped endpoint called without tenant ID

**Fix:**
1. Check environment (eye icon) - `tenant_id` should have a value
2. If empty, run Register (creates tenant) or get tenant ID from `/v1/tenants`
3. Verify `X-TENANT-ID` header is present in request

### 403: "User does not have required scope"

**Cause:** User lacks RBAC permission for the operation

**Fix:**
1. Check endpoint documentation for required scope
2. Contact tenant owner to assign appropriate role
3. Or use Owner account which has all permissions

### Token Not Saving Automatically

**Cause:** Test script not running or console not visible

**Fix:**
1. Open Postman Console (View → Show Postman Console)
2. Run Login/Register
3. Check console for "Token saved: ..." message
4. If not present, manually copy token from response and paste into environment

**Manual token setting:**
1. Run Login/Register
2. Copy `token` value from response body
3. Click eye icon (top right)
4. Click "Edit" on environment
5. Paste token into `access_token` field
6. Save

## Testing Authentication Flow

### Test 1: Register → Profile → List Tenants

```bash
1. POST /v1/auth/register
   → Returns: token, user, tenant
   → Auto-saves: access_token, tenant_id

2. GET /v1/auth/me
   → Returns: user profile
   → Verifies: JWT authentication works

3. GET /v1/tenants
   → Returns: list of user's tenants
   → Verifies: JWT-only endpoint works
```

### Test 2: Login → List Products → Create Product

```bash
1. POST /v1/auth/login
   → Returns: token, user
   → Auto-saves: access_token

2. GET /v1/products/
   → Returns: products list
   → Verifies: Tenant-scoped read works

3. POST /v1/products/
   → Creates: new product
   → Verifies: Tenant-scoped write works
   → Requires: catalog:edit scope
```

### Test 3: Token Refresh

```bash
1. POST /v1/auth/login
   → Get initial token

2. Wait 23 hours (or change JWT_EXPIRATION_HOURS to 1 minute for testing)

3. POST /v1/auth/refresh-token
   → Returns: new token
   → Auto-saves: access_token

4. GET /v1/auth/me
   → Verifies: new token works
```

## Security Best Practices

1. **Never commit tokens** - They're in `.gitignore` for a reason
2. **Rotate tokens regularly** - Use refresh endpoint
3. **Use HTTPS in production** - Never send tokens over HTTP
4. **Store tokens securely** - Use environment variables, not code
5. **Implement token blacklist** - For logout in production (optional)
6. **Monitor token usage** - Check audit logs for suspicious activity

## Django Shell Testing

Test authentication manually:

```python
# Start shell
python manage.py shell

# Test JWT generation
from apps.rbac.services import AuthService
from apps.rbac.models import User

user = User.objects.get(email='your-email@example.com')
token = AuthService.generate_jwt(user)
print(f"Token: {token}")

# Test JWT validation
validated_user = AuthService.get_user_from_jwt(token)
print(f"User: {validated_user.email}")

# Test login
result = AuthService.login('your-email@example.com', 'your-password')
if result:
    print(f"Login successful: {result['token']}")
else:
    print("Login failed")
```

## Next Steps

1. ✅ Import Postman collection and environment
2. ✅ Register or login to get token
3. ✅ Verify authentication with `/v1/auth/me`
4. ✅ Test tenant-scoped endpoints
5. ✅ Explore RBAC and permissions
6. ✅ Build your application!

## Support

If you encounter issues:

1. Check Postman console for token saving
2. Check Django logs for authentication errors
3. Verify environment variables are set
4. Test authentication in Django shell
5. Review `FIXES_APPLIED.md` for common issues

**Remember:** Tokens expire after 24 hours - just login again!
