# CSRF and Authentication Fixes

## Root Causes Identified

### 1. DRF Default Authentication
**Problem:** Django REST Framework defaults to `SessionAuthentication` when `DEFAULT_AUTHENTICATION_CLASSES` is not specified. SessionAuthentication requires CSRF tokens for POST/PUT/DELETE requests.

**Impact:** All POST endpoints were returning CSRF errors even though the app uses JWT and API key authentication via middleware.

### 2. Auth Endpoint Path Configuration
**Problem:** `/v1/auth/` was in `PUBLIC_PATHS`, which meant the middleware skipped authentication entirely. But `/v1/auth/me` requires `IsAuthenticated` permission, causing a mismatch.

**Impact:** Profile endpoint returned "Authentication credentials were not provided" even with valid JWT token.

## Fixes Applied

### Fix 1: Disable DRF Session Authentication
**File:** `config/settings.py`

**Change:**
```python
REST_FRAMEWORK = {
    # ... other settings ...
    'DEFAULT_AUTHENTICATION_CLASSES': [],  # Authentication handled by TenantContextMiddleware
    'DEFAULT_PERMISSION_CLASSES': [],
    # ... other settings ...
}
```

**Why:** Setting `DEFAULT_AUTHENTICATION_CLASSES` to empty list tells DRF not to use any built-in authentication. Our custom `TenantContextMiddleware` handles all authentication (JWT and API keys), so we don't need DRF's SessionAuthentication which requires CSRF.

### Fix 2: Granular Auth Path Configuration
**File:** `apps/tenants/middleware.py`

**Before:**
```python
PUBLIC_PATHS = [
    '/v1/auth/',  # All auth endpoints treated as public
]

JWT_ONLY_PATHS = [
    '/v1/tenants',
]
```

**After:**
```python
PUBLIC_PATHS = [
    '/v1/auth/register',
    '/v1/auth/login',
    '/v1/auth/verify-email',
    '/v1/auth/forgot-password',
    '/v1/auth/reset-password',
    '/v1/auth/refresh-token',
    # ... other public paths ...
]

JWT_ONLY_PATHS = [
    '/v1/tenants',
    '/v1/auth/me',      # Profile endpoint requires JWT
    '/v1/auth/logout',  # Logout requires JWT
]
```

**Why:** 
- Public auth endpoints (register, login) don't need authentication
- Protected auth endpoints (profile, logout) need JWT but not tenant context
- This allows the middleware to properly authenticate JWT tokens for `/v1/auth/me`

## How Authentication Works Now

### Flow Diagram
```
Request → TenantContextMiddleware → View
          ↓
          Checks path type:
          
          1. PUBLIC_PATHS → Skip auth, continue
          2. JWT_ONLY_PATHS → Validate JWT, set request.user, skip tenant
          3. Other paths → Validate JWT/API key + tenant context
```

### Authentication Methods

#### 1. JWT Authentication (User-based)
```bash
curl -H "Authorization: Bearer <jwt_token>" \
     https://api.tulia.ai/v1/auth/me
```
- Used for user-specific operations
- Sets `request.user`
- For JWT_ONLY_PATHS: No tenant context required
- For other paths: Requires `X-TENANT-ID` header

#### 2. API Key Authentication (Service-to-service)
```bash
curl -H "X-TENANT-ID: <tenant_uuid>" \
     -H "X-TENANT-API-KEY: <api_key>" \
     https://api.tulia.ai/v1/products/
```
- Used for programmatic access
- No `request.user` (service account)
- Always requires tenant context

#### 3. No Authentication (Public endpoints)
```bash
curl https://api.tulia.ai/v1/auth/login \
     -d '{"email": "user@example.com", "password": "pass"}'
```
- Register, login, password reset, etc.
- No headers required

## Testing the Fixes

### 1. Test Twilio Credentials (API Key Auth)
```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/v1/settings/integrations/twilio \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b" \
  -H "X-TENANT-API-KEY: a96b73152af3e755424b11a6dad39a44bbebb553c7608f0b138a48ba95e54d68" \
  -d '{
    "sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "token": "your_auth_token",
    "whatsapp_number": "whatsapp:+14155238886"
  }'
```

**Expected:** 200 OK with credentials saved

### 2. Test Profile Endpoint (JWT Auth)
```bash
# First login
curl -X POST https://your-ngrok-url.ngrok-free.app/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Then get profile with token
curl https://your-ngrok-url.ngrok-free.app/v1/auth/me \
  -H "Authorization: Bearer <access_token_from_login>"
```

**Expected:** 200 OK with user profile

### 3. Test Send WhatsApp (API Key Auth)
```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/v1/test/send-whatsapp/ \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b" \
  -H "X-TENANT-API-KEY: a96b73152af3e755424b11a6dad39a44bbebb553c7608f0b138a48ba95e54d68" \
  -d '{
    "to": "+1234567890",
    "body": "Test message"
  }'
```

**Expected:** 200 OK with message sent

### 4. Test Send Message (API Key Auth)
```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/v1/messages/send \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b" \
  -H "X-TENANT-API-KEY: a96b73152af3e755424b11a6dad39a44bbebb553c7608f0b138a48ba95e54d68" \
  -d '{
    "to": "+1234567890",
    "message": "Test message"
  }'
```

**Expected:** 200 OK with message sent

## Important Notes

### CSRF is NOT Needed
- CSRF protection is for browser-based session authentication
- Our API uses stateless authentication (JWT tokens and API keys)
- CSRF tokens are not required and would break the API

### ngrok Considerations
- ngrok should work fine now
- Make sure your ngrok URL is in `ALLOWED_HOSTS` in `.env`
- The `USE_X_FORWARDED_HOST` and `SECURE_PROXY_SSL_HEADER` settings handle ngrok's proxy headers

### Postman Configuration
- For JWT endpoints: Use "Bearer Token" auth type with `{{access_token}}`
- For API key endpoints: Add headers manually:
  - `X-TENANT-ID: {{tenant_id}}`
  - `X-TENANT-API-KEY: {{tenant_api_key}}`
- No CSRF tokens needed!

## Troubleshooting

### Still Getting CSRF Errors?
1. **Restart Django server** - Settings changes require restart
2. Check that `DEFAULT_AUTHENTICATION_CLASSES = []` in settings
3. Verify you're not sending a `csrftoken` cookie

### Still Getting "Authentication credentials were not provided"?
1. Check the endpoint path matches exactly (trailing slashes matter)
2. For `/v1/auth/me`: Use `Authorization: Bearer <token>` header
3. For other endpoints: Use `X-TENANT-ID` and `X-TENANT-API-KEY` headers
4. Check Django logs for detailed error messages

### JWT Token Issues?
1. Token might be expired (default: 24 hours)
2. Use `/v1/auth/refresh-token` to get a new token
3. Or login again to get fresh tokens

## Files Modified

1. `config/settings.py` - Disabled DRF default authentication
2. `apps/tenants/middleware.py` - Fixed auth path configuration

## Next Steps

1. ✅ Restart Django server
2. ✅ Test all endpoints in Postman
3. ✅ Verify no CSRF errors
4. ✅ Verify JWT authentication works for profile endpoint
5. ✅ Test Twilio webhook with real WhatsApp message
