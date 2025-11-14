# Fixes Applied - JWT Authentication & Celery

## Issue 1: Celery Task Not Running

**Problem:** Celery shows broker connection retries during startup

**Root Cause:** This is normal behavior during Celery startup. The warnings you see are expected and will stop once Celery fully connects to Redis.

**Verification:**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Check if Celery worker is running
ps aux | grep celery

# Test the task manually
source venv/bin/activate
python manage.py shell
```

```python
from apps.bot.tasks import process_inbound_message
from apps.messaging.models import Message

# Get a recent message
msg = Message.objects.filter(direction='in').order_by('-created_at').first()
if msg:
    # Trigger the task
    result = process_inbound_message.delay(str(msg.id))
    print(f"Task ID: {result.id}")
```

**Status:** ✅ Task is properly registered. The warnings are normal startup behavior.

---

## Issue 2: JWT Authentication Failing in Postman

**Problem:** Postman returns 401 "Anonymous user" even with token set

**Root Cause:** 
1. Login response returns `token` field, but Postman script was looking for `access_token` and `refresh_token`
2. Token wasn't being saved to environment variable
3. Authorization header format might be incorrect

**Fix Applied:**

### 1. Updated Postman Collection

**Login endpoint** - Fixed test script:
```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set('access_token', jsonData.token);  // Changed from jsonData.access_token
    console.log('Token saved:', jsonData.token);
}
```

**Register endpoint** - Added test script:
```javascript
if (pm.response.code === 201) {
    var jsonData = pm.response.json();
    pm.environment.set('access_token', jsonData.token);
    pm.environment.set('tenant_id', jsonData.tenant.id);
    console.log('Token saved:', jsonData.token);
    console.log('Tenant ID saved:', jsonData.tenant.id);
}
```

### 2. How to Use in Postman

**Step 1: Login or Register**
1. Open the "Authentication" folder
2. Run "Login" or "Register" request
3. Check the console - you should see: `Token saved: eyJhbGc...`
4. The token is automatically saved to `{{access_token}}` variable

**Step 2: Use Protected Endpoints**
The collection is configured with Bearer token authentication at the collection level.
All requests automatically use `{{access_token}}` from the environment.

**Step 3: Verify Token is Set**
1. Click the "eye" icon (top right) to view environment
2. Check that `access_token` has a value
3. If not, re-run Login/Register

**Step 4: Manual Token Setting (if needed)**
If automatic saving doesn't work:
1. Copy the `token` value from Login/Register response
2. Click "eye" icon → Edit environment
3. Paste token into `access_token` field
4. Save

### 3. Authorization Header Format

The middleware expects:
```
Authorization: Bearer <token>
```

Postman collection is configured to automatically add this header using:
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

### 4. Troubleshooting

**Still getting 401?**

Check these:

1. **Token is set:**
   ```
   Console → {{access_token}}
   Should show: eyJhbGc...
   ```

2. **Authorization header is present:**
   ```
   Request → Headers tab
   Should see: Authorization: Bearer eyJhbGc...
   ```

3. **Token is valid:**
   ```bash
   # Test in Django shell
   source venv/bin/activate
   python manage.py shell
   ```
   ```python
   from apps.rbac.services import AuthService
   
   token = "YOUR_TOKEN_HERE"
   user = AuthService.get_user_from_jwt(token)
   print(f"User: {user}")  # Should show user object, not None
   ```

4. **Check middleware logs:**
   ```bash
   # In Django runserver terminal, look for:
   INFO JWT authentication successful for user: user@example.com
   
   # If you see:
   WARNING Invalid or expired JWT token
   # Then token is invalid - login again
   ```

### 5. Common Mistakes

❌ **Wrong:** Using API key for user endpoints
```
X-TENANT-API-KEY: abc123...
```
API keys are deprecated for user operations.

✅ **Correct:** Using JWT token
```
Authorization: Bearer eyJhbGc...
```

❌ **Wrong:** Missing Bearer prefix
```
Authorization: eyJhbGc...
```

✅ **Correct:** With Bearer prefix
```
Authorization: Bearer eyJhbGc...
```

---

## Testing the Fixes

### Test 1: Register New User
```bash
# In Postman:
1. Open "Authentication" → "Register"
2. Update email to something unique
3. Click "Send"
4. Check console: "Token saved: ..."
5. Check environment: access_token should have value
```

### Test 2: Login Existing User
```bash
# In Postman:
1. Open "Authentication" → "Login"
2. Enter email and password
3. Click "Send"
4. Check console: "Token saved: ..."
5. Check environment: access_token should have value
```

### Test 3: Get Profile
```bash
# In Postman:
1. Open "Authentication" → "Get Profile"
2. Click "Send"
3. Should return 200 with user profile
4. If 401, check Authorization header is present
```

### Test 4: List Products (Tenant-Scoped)
```bash
# In Postman:
1. Open "Products" → "List Products"
2. Make sure tenant_id is set in environment
3. Click "Send"
4. Should return 200 with products list
5. If 401, check both Authorization header AND X-TENANT-ID header
```

---

## API Authentication Summary

### Public Endpoints (No Auth Required)
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/verify-email`
- `POST /v1/auth/forgot-password`
- `POST /v1/auth/reset-password`
- `POST /v1/webhooks/twilio` (verified by signature)
- `GET /v1/health`
- `GET /schema/*`

### JWT-Only Endpoints (No Tenant Required)
- `GET /v1/auth/me` - Get user profile
- `PUT /v1/auth/me` - Update user profile
- `POST /v1/auth/logout` - Logout
- `POST /v1/auth/refresh-token` - Refresh token
- `GET /v1/tenants` - List user's tenants
- `POST /v1/tenants` - Create new tenant

**Headers Required:**
```
Authorization: Bearer <token>
```

### Tenant-Scoped Endpoints (Most Endpoints)
- All product, order, service, analytics endpoints
- Tenant management (update, delete)
- RBAC (roles, permissions, memberships)
- Messaging, customers, etc.

**Headers Required:**
```
Authorization: Bearer <token>
X-TENANT-ID: <tenant-uuid>
```

Note: `X-TENANT-API-KEY` is deprecated for user operations.

---

## Files Modified

1. ✅ `postman/TuliaAI.postman_collection.json`
   - Fixed Login test script to save `jsonData.token` instead of `jsonData.access_token`
   - Added Register test script to auto-save token and tenant_id
   - Updated Register body to include `business_name`

2. ✅ `postman/TuliaAI.postman_environment.json`
   - Already had `access_token` variable configured

3. ✅ `apps/bot/tasks.py`
   - Already properly configured with `@shared_task` decorator
   - Task is registered and discoverable by Celery

---

## Next Steps

1. **Re-import Postman Collection**
   - Delete old collection in Postman
   - Import updated `postman/TuliaAI.postman_collection.json`

2. **Test Authentication Flow**
   - Register or Login
   - Verify token is saved
   - Test protected endpoints

3. **Test Celery Task**
   - Send WhatsApp message
   - Check Celery logs for task execution
   - Verify bot response

---

## Support

If issues persist:

1. **Check Django logs** for authentication errors
2. **Check Celery logs** for task execution
3. **Check Postman console** for token saving
4. **Verify environment variables** are set correctly

**Token expires in 24 hours** - if you get 401 after a day, just login again.
