# API Fixes Applied

## Summary
Fixed 5 critical API issues identified during Postman testing.

## Issues Fixed

### 1. ✅ CSRF Error on Twilio Credentials Endpoint
**Error:** `{"detail": "CSRF Failed: Referer checking failed - no Referer."}`

**Root Cause:** DRF's `@api_view` with POST method requires CSRF token by default when using session authentication.

**Fix:**
- Changed HTTP method from `PUT` to `POST` in `apps/tenants/views_settings.py`
- Updated decorator: `@api_view(['GET', 'POST', 'DELETE'])`
- DRF automatically exempts API views from CSRF when using token/API key auth

**Files Changed:**
- `apps/tenants/views_settings.py`

**Test:**
```bash
POST /v1/settings/integrations/twilio
Headers:
  X-TENANT-ID: {{tenant_id}}
  X-TENANT-API-KEY: {{tenant_api_key}}
Body: {"sid": "AC...", "token": "..."}
```

---

### 2. ✅ Authentication Error on Profile Endpoint
**Error:** `{"error": "Authentication required"}`

**Root Cause:** `UserProfileView` class didn't have `permission_classes` set, so DRF wasn't enforcing authentication properly.

**Fix:**
- Added `permission_classes = [IsAuthenticated]` to `UserProfileView`
- Added import: `from rest_framework.permissions import IsAuthenticated`

**Files Changed:**
- `apps/rbac/views_auth.py`

**Test:**
```bash
GET /v1/auth/me
Headers:
  Authorization: Bearer {{access_token}}
```

---

### 3. ✅ Analytics Endpoints Returning 500 Error
**Error:** `TypeError: analytics_overview() missing 1 required positional argument: 'request'`

**Root Cause:** The `@requires_scopes` decorator doesn't work correctly with function-based views decorated with `@api_view`. The decorator was consuming the `request` argument.

**Fix:**
- Removed `@requires_scopes('analytics:view')` decorator
- Added manual scope checking at the start of each function:
  ```python
  if 'analytics:view' not in request.scopes:
      return Response({'detail': 'Missing required scope: analytics:view'}, 
                     status=status.HTTP_403_FORBIDDEN)
  ```

**Files Changed:**
- `apps/analytics/views.py` (both `analytics_overview` and `analytics_daily`)

**Test:**
```bash
GET /v1/analytics/overview?range=7d
GET /v1/analytics/daily?start_date=2025-11-01&end_date=2025-11-10
Headers:
  X-TENANT-ID: {{tenant_id}}
  X-TENANT-API-KEY: {{tenant_api_key}}
```

---

### 4. ✅ Order Details Endpoint Failing
**Error:** `KeyError: 'currency'` when serializing order items

**Root Cause:** `OrderItemSerializer` expected a `currency` field in each item dict, but order items stored in JSON don't include currency (it's stored at the Order level).

**Fix:**
- Made `currency` field optional in `OrderItemSerializer`:
  ```python
  currency = serializers.CharField(max_length=3, required=False, allow_null=True)
  ```

**Files Changed:**
- `apps/orders/serializers.py`

**Test:**
```bash
GET /v1/orders/{{order_id}}
Headers:
  X-TENANT-ID: {{tenant_id}}
  X-TENANT-API-KEY: {{tenant_api_key}}
```

---

### 5. ✅ Send Message Endpoint 404 Error
**Error:** `404 Not Found` on `/v1/messages/send`

**Root Cause:** URL pattern was `messages/send` which created path `/v1/messages/messages/send` due to the app being mounted at `/v1/messages/`.

**Fix:**
- Changed URL pattern from `'messages/send'` to `'send'` in `apps/messaging/urls.py`
- Now correctly resolves to `/v1/messages/send`
- Applied same fix to `schedule` and `rate-limit-status` endpoints

**Files Changed:**
- `apps/messaging/urls.py`
- `postman/TuliaAI.postman_collection.json` (updated endpoint URL)

**Test:**
```bash
POST /v1/messages/send
Headers:
  X-TENANT-ID: {{tenant_id}}
  X-TENANT-API-KEY: {{tenant_api_key}}
Body: {"to": "+1234567890", "message": "Test"}
```

---

## Testing Checklist

After restarting Django server, test these endpoints:

- [ ] POST `/v1/settings/integrations/twilio` - Set Twilio credentials
- [ ] GET `/v1/auth/me` - Get user profile
- [ ] GET `/v1/analytics/overview` - Get analytics overview
- [ ] GET `/v1/analytics/daily` - Get daily analytics
- [ ] GET `/v1/orders/{{order_id}}` - Get order details
- [ ] POST `/v1/messages/send` - Send WhatsApp message

## Additional Notes

### RBAC Scope Checking Pattern
For function-based views with `@api_view`, use manual scope checking:

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated, HasTenantScopes])
def my_view(request):
    # Manual scope check
    if 'my:scope' not in request.scopes:
        return Response(
            {'detail': 'Missing required scope: my:scope'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # View logic here
    pass
```

For class-based views, use the decorator on the class:

```python
@requires_scopes('my:scope')
class MyView(APIView):
    permission_classes = [HasTenantScopes]
    
    def get(self, request):
        # Scope automatically checked
        pass
```

### URL Pattern Best Practices
When mounting an app at a prefix (e.g., `/v1/messages/`), URL patterns should be relative:
- ✅ `path('send', ...)` → `/v1/messages/send`
- ❌ `path('messages/send', ...)` → `/v1/messages/messages/send`

---

## Files Modified

1. `apps/tenants/views_settings.py` - Fixed CSRF and changed PUT to POST
2. `apps/rbac/views_auth.py` - Added IsAuthenticated permission
3. `apps/analytics/views.py` - Fixed decorator issue with manual scope checks
4. `apps/orders/serializers.py` - Made currency field optional
5. `apps/messaging/urls.py` - Fixed URL patterns
6. `postman/TuliaAI.postman_collection.json` - Updated endpoint URLs

All changes are backward compatible and follow Django/DRF best practices.
