# Postman Quick Fix - Working Token

## Your Valid Token

I've verified your token and updated the environment file.

**User:** owner@starter.demo  
**Tenant:** Starter Store  
**Tenant ID:** 604923c8-cff3-49d7-b3a3-fe5143c5c46b

## Setup in Postman (2 Minutes)

### Step 1: Re-import Environment

1. In Postman, delete the old "TuliaAI Development" environment
2. Click **Import**
3. Select `postman/TuliaAI.postman_environment.json`
4. Select the environment from dropdown (top right)

### Step 2: Verify Token is Set

1. Click the **eye icon** (top right)
2. Check these values:
   - `access_token`: Should show `eyJhbGc...` (your token)
   - `tenant_id`: Should show `604923c8-cff3-49d7-b3a3-fe5143c5c46b`

### Step 3: Test It

1. Open **Authentication** → **Get Profile**
2. Click **Send**
3. Should return **200 OK** with:
   ```json
   {
     "id": "8e4e594f-86cd-455a-8639-1855c2f07e3e",
     "email": "owner@starter.demo",
     "first_name": "Owner",
     "last_name": "User",
     "full_name": "Owner User"
   }
   ```

### Step 4: Test Tenant-Scoped Endpoint

1. Open **Products** → **List Products**
2. Click **Send**
3. Should return **200 OK** with products list

## If Still Getting 401

### Check 1: Authorization Header

In the request, click **Headers** tab and verify:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

If missing:
1. Go to Collection → **Authorization** tab
2. Type: **Bearer Token**
3. Token: `{{access_token}}`

### Check 2: Environment Selected

Make sure "TuliaAI Development" is selected in the dropdown (top right).

### Check 3: Token in Environment

1. Click eye icon
2. If `access_token` is empty, manually paste:
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo
   ```

## Manual Token Setting (Alternative)

If re-importing doesn't work:

1. Click **eye icon** (top right)
2. Click **Edit** on "TuliaAI Development"
3. Find `access_token` variable
4. Paste this value:
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo
   ```
5. Click **Save**

## Celery Issue - No Logs

If you're not seeing Celery logs when sending WhatsApp messages:

### Check 1: Is Celery Running?

```bash
ps aux | grep celery | grep -v grep
```

If nothing shows, start it:
```bash
./start_celery.sh
```

### Check 2: Is Redis Running?

```bash
redis-cli ping
```

Should return: `PONG`

If not, start it:
```bash
redis-server
```

### Check 3: Test Task Manually

```bash
source venv/bin/activate
python diagnose_issues.py
```

This will:
- Check if Celery is running
- Check if Redis is running
- Check if messages exist
- Try to enqueue a test task

### Check 4: Send Test WhatsApp Message

1. Send "Hello" to your Twilio number: `+1 415 523 8886`
2. Watch Django terminal for:
   ```
   INFO Twilio webhook received
   INFO Tenant resolved by WhatsApp number
   INFO Inbound message stored
   INFO Intent processing task enqueued
   ```
3. Watch Celery terminal for:
   ```
   [INFO] Task apps.bot.tasks.process_inbound_message received
   [INFO] Processing inbound message
   [INFO] Intent classified: GREETING (confidence: 0.95)
   [INFO] Response sent successfully
   [INFO] Task succeeded
   ```

## Token Expiration

This token expires in **24 hours** (on Nov 15, 2025 at ~8:30 AM).

When it expires, just login again:
```bash
POST /v1/auth/login
{
  "email": "owner@starter.demo",
  "password": "your-password"
}
```

The response will include a new token that's automatically saved.

## Quick Test Commands

### Test Token Validity
```bash
source venv/bin/activate
python manage.py shell -c "
from apps.rbac.services import AuthService
token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo'
user = AuthService.get_user_from_jwt(token)
print('Valid!' if user else 'Invalid/Expired')
"
```

### Test with curl
```bash
curl -X GET http://localhost:8000/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiOGU0ZTU5NGYtODZjZC00NTVhLTg2MzktMTg1NWMyZjA3ZTNlIiwiZW1haWwiOiJvd25lckBzdGFydGVyLmRlbW8iLCJleHAiOjE3NjMxODc5ODQsImlhdCI6MTc2MzEwMTU4NH0.KNc2y6uUd2GSvIxQq-Hm5mAYASyI7CpAXnGaZmdwsAo"
```

Should return your user profile.

## Summary

✅ Token is valid and working  
✅ Environment file updated  
✅ Tenant ID is set  

**Next steps:**
1. Re-import environment in Postman
2. Test `/v1/auth/me` endpoint
3. Start Celery if you want bot responses
4. Send WhatsApp message to test

Your authentication should work now! 🎉
