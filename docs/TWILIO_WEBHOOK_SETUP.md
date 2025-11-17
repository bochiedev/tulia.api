# Twilio WhatsApp Webhook Setup Guide

This guide explains how to configure Twilio webhooks for local development using ngrok.

## Prerequisites

- Twilio account with WhatsApp sandbox or approved WhatsApp number
- ngrok installed (https://ngrok.com/)
- Tulia AI running locally

## Step 1: Start Your Local Server

```bash
# Start the Django development server
python manage.py runserver

# Or with Docker Compose
docker-compose up
```

Your server should be running on `http://localhost:8000`

## Step 2: Start ngrok Tunnel

Open a new terminal and start ngrok:

```bash
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://c00265fdeecd.ngrok-free.app -> http://localhost:8000
```

Copy the HTTPS URL (e.g., `https://c00265fdeecd.ngrok-free.app`)

## Step 3: Configure Twilio Webhook

Based on your screenshot, configure the following in Twilio Console:

### When a message comes in

**URL**: `https://c00265fdeecd.ngrok-free.app/v1/webhooks/twilio`
**Method**: `POST`

This is the main webhook that receives incoming WhatsApp messages.

### Status callback URL (Optional)

**URL**: Leave empty for now (or use same URL if you want delivery status updates)
**Method**: `GET` or `POST`

## Step 4: Test the Webhook

1. Send a WhatsApp message to your Twilio sandbox number
2. Check your Django logs for incoming webhook
3. The bot should respond automatically

## Webhook Endpoint Details

### POST /v1/webhooks/twilio

**Purpose**: Receives incoming WhatsApp messages from Twilio

**Authentication**: Signature verification (X-Twilio-Signature header)

**Headers Required**:
- `X-Twilio-Signature` - HMAC-SHA1 signature (automatically sent by Twilio)
- `Content-Type: application/x-www-form-urlencoded`

**Request Body** (from Twilio):
```
MessageSid=SM...
From=whatsapp:+254722244161
To=whatsapp:+14155238886
Body=Hello
```

**Response Codes**:
- `200 OK` - Message processed successfully
- `403 Forbidden` - Invalid signature (security violation)
- `404 Not Found` - Tenant not found for phone number
- `503 Service Unavailable` - Tenant subscription inactive

**Response**: 200 OK

**Security**: All requests are verified using HMAC-SHA1 signature verification before processing.

---

### POST /v1/webhooks/twilio/status

**Purpose**: Receives message delivery status updates from Twilio

**Authentication**: Signature verification (X-Twilio-Signature header)

**Headers Required**:
- `X-Twilio-Signature` - HMAC-SHA1 signature (automatically sent by Twilio)
- `Content-Type: application/x-www-form-urlencoded`

**Request Body** (from Twilio):
```
MessageSid=SM...
MessageStatus=delivered
```

**Status Values**:
- `queued` - Message queued for delivery
- `sent` - Message sent to carrier
- `delivered` - Message delivered to recipient
- `read` - Message read by recipient (if supported)
- `failed` - Message delivery failed
- `undelivered` - Message could not be delivered

**Response Codes**:
- `200 OK` - Status update processed successfully
- `403 Forbidden` - Invalid signature (security violation)
- `404 Not Found` - Message not found

**Response**: 200 OK

**Security**: All requests are verified using HMAC-SHA1 signature verification before processing. The message must exist in the database to retrieve the tenant's auth token for verification.

### Signature Verification Algorithm

The webhook uses HMAC-SHA1 signature verification following Twilio's specification:

1. **Concatenate** the webhook URL with sorted POST parameters:
   ```
   https://api.example.com/v1/webhooks/twilioBody=HelloFrom=whatsapp:+1234MessageSid=SM123To=whatsapp:+4155
   ```

2. **Compute HMAC-SHA1** using Auth Token as the secret key

3. **Base64 encode** the resulting hash

4. **Compare** with X-Twilio-Signature header using constant-time comparison

**Implementation** (apps/integrations/views.py):
```python
def verify_twilio_signature(url, params, signature, auth_token):
    """
    Verify Twilio webhook signature for security.
    
    Validates that the webhook request came from Twilio by comparing
    the X-Twilio-Signature header with a computed HMAC-SHA1 signature.
    """
    try:
        # Sort parameters alphabetically and concatenate with URL
        sorted_params = sorted(params.items())
        data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
        
        # Compute HMAC-SHA1 signature using auth token as key
        computed_signature = hmac.new(
            auth_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64 encode the computed signature
        computed_signature_b64 = base64.b64encode(computed_signature).decode('utf-8')
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_signature_b64, signature)
        
    except Exception as e:
        # Fail securely - return False on any exception
        return False
```

**Security Features**:
- Constant-time comparison prevents timing attacks
- Fails securely (returns False on any exception)
- Logs all verification failures with context
- Sends critical alerts to Sentry for monitoring

## Troubleshooting

### Webhook not receiving messages

1. Check ngrok is running and URL is correct
2. Verify Twilio webhook URL is saved
3. Check Django logs for errors
4. Ensure no firewall blocking ngrok

### 403 Forbidden Error

**This is expected behavior for invalid requests!**

The webhook endpoint uses signature verification instead of API key authentication. A 403 error means:

1. **Invalid signature** - The request didn't come from Twilio or the signature is incorrect
2. **Wrong Auth Token** - Your Twilio Auth Token in TenantSettings doesn't match
3. **URL mismatch** - The webhook URL in Twilio Console doesn't match the actual URL

**To fix:**

1. Verify Twilio Auth Token in Django Admin > Tenants > Tenant Settings
2. Ensure webhook URL in Twilio Console is exactly: `https://your-domain.com/v1/webhooks/twilio`
3. Check application logs for detailed signature verification errors
4. Test by sending a real message from WhatsApp (not curl)

### Messages not being processed

1. Check tenant exists and has valid subscription
2. Verify Twilio credentials in TenantSettings
3. Check Celery workers are running
4. Review application logs

## Production Setup

For production, replace ngrok URL with your actual domain:

```
https://api.yourdomain.com/v1/webhooks/twilio
```

Ensure:
- SSL certificate is valid
- Webhook endpoint is publicly accessible
- Twilio IP whitelist configured (if using firewall)

## Security

### Webhook Signature Verification ✅ IMPLEMENTED

All Twilio webhooks are **automatically verified** using HMAC-SHA1 signature verification to prevent unauthorized access and message injection attacks.

**Implementation Status**: ✅ Complete (Task 1.2 from Security Remediation Spec)

**What Was Implemented**:
- ✅ `verify_twilio_signature()` helper function with HMAC-SHA1 verification
- ✅ Signature verification in `twilio_webhook()` view (incoming messages)
- ✅ Signature verification in `twilio_status_callback()` view (delivery status)
- ✅ Security event logging via `SecurityLogger.log_invalid_webhook_signature()`
- ✅ WebhookLog creation with status='unauthorized' for failed verifications
- ✅ Sentry integration for critical security alerts
- ✅ Comprehensive test coverage (25 tests passing)
- ✅ Constant-time comparison to prevent timing attacks
- ✅ Secure failure handling (fail closed on any exception)

**How it works:**

1. Twilio signs each webhook request with your Auth Token
2. The signature is sent in the `X-Twilio-Signature` header
3. Our server recomputes the signature using your Auth Token
4. If signatures don't match, the request is rejected with 403 Forbidden

**What this protects against:**

- Webhook spoofing (attackers pretending to be Twilio)
- Message injection attacks
- Unauthorized access to your webhook endpoint
- Man-in-the-middle attacks

**Configuration:**

Signature verification is **enabled by default** and uses the Twilio Auth Token configured in your TenantSettings:

```python
# In Django Admin > Tenants > Tenant Settings
twilio_sid = "AC..."  # Your Twilio Account SID
twilio_token = "..."  # Your Twilio Auth Token (used for signature verification)
```

The implementation automatically retrieves credentials from TenantSettings with fallback to the Tenant model for backward compatibility:

```python
# Get Twilio credentials from TenantSettings (preferred) or Tenant model (fallback)
try:
    settings = tenant.settings
    if settings.has_twilio_configured():
        twilio_token = settings.twilio_token
    else:
        # Fallback to Tenant model
        twilio_token = tenant.twilio_token
except AttributeError:
    # Fallback to Tenant model
    twilio_token = tenant.twilio_token
```

**Security Events:**

Failed signature verifications are logged as critical security events using the SecurityLogger:

- Logged to application logs with full context (event_type, provider, tenant_id, ip_address, url, user_agent)
- Sent to Sentry for real-time alerting (critical events only)
- Recorded in WebhookLog model with status='unauthorized'
- Includes timestamp, IP address, and user agent for forensic analysis

**Implementation:**
```python
# Log as critical security event
SecurityLogger.log_invalid_webhook_signature(
    provider='twilio',
    tenant_id=str(tenant.id),
    ip_address=request.META.get('REMOTE_ADDR'),
    url=full_url,
    user_agent=request.META.get('HTTP_USER_AGENT')
)
```

**Testing Signature Verification:**

To test that signature verification is working:

```bash
# This should fail with 403 Forbidden (no valid signature)
curl -X POST https://your-domain.com/v1/webhooks/twilio \
  -d "From=whatsapp:+1234567890" \
  -d "To=whatsapp:+14155238886" \
  -d "Body=Test"

# Only requests from Twilio with valid signatures will succeed
```

**Automated Tests:**

The signature verification is covered by comprehensive tests in `apps/integrations/tests/test_twilio_webhook.py`:

- ✅ Valid signature verification (25 tests passing)
- ✅ Invalid signature rejection (403 response)
- ✅ Missing signature rejection (403 response)
- ✅ Security event logging for invalid signatures
- ✅ WebhookLog creation with status='unauthorized'
- ✅ Both webhook endpoints (message and status callback) verified

Run tests with:
```bash
pytest apps/integrations/tests/test_twilio_webhook.py -v
```

**Troubleshooting:**

If legitimate Twilio webhooks are being rejected:

1. Verify your Twilio Auth Token is correct in TenantSettings
2. Check that your webhook URL matches exactly (including https://)
3. Ensure no proxy is modifying the request
4. Check application logs for signature verification details

### Additional Security Features

- No API keys required for webhook endpoint (public endpoint with signature verification)
- Tenant is resolved from the phone number
- All webhook attempts are logged in WebhookLog model
- Rate limiting on webhook endpoint (future enhancement)
- IP whitelist support for Twilio IPs (optional)

## Monitoring & Security Events

### Webhook Logs

All webhook attempts are logged in the `WebhookLog` model. Access via Django Admin:

**Admin > Integrations > Webhook Logs**

Each log entry includes:
- Provider (twilio)
- Event type (message.received)
- Status (success, error, unauthorized)
- Full payload and headers
- Tenant information
- Timestamp and processing time

### Security Event Monitoring

Failed signature verifications trigger security events:

1. **Application Logs** - Structured JSON logs with full context
2. **Sentry Alerts** - Real-time alerts for critical security events
3. **WebhookLog** - Database record with status='unauthorized'

**Example log entry:**
```json
{
  "timestamp": "2025-11-17T10:30:00Z",
  "level": "ERROR",
  "logger": "security",
  "message": "Security event: invalid_webhook_signature",
  "event_type": "invalid_webhook_signature",
  "provider": "twilio",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "ip_address": "192.168.1.1",
  "url": "https://api.example.com/v1/webhooks/twilio",
  "user_agent": "TwilioProxy/1.1"
}
```

**Sentry Alert:**
Critical security events are also sent to Sentry with level='error' for real-time alerting and monitoring.

### Monitoring Best Practices

1. **Set up Sentry** - Configure Sentry DSN in settings for real-time alerts
2. **Monitor WebhookLog** - Regularly check for unauthorized attempts
3. **Alert on patterns** - Set up alerts for multiple failed verifications from same IP
4. **Review logs** - Periodically review security logs for suspicious activity
5. **Rotate tokens** - Rotate Twilio Auth Token if compromise suspected

### Security Incident Response

If you detect unauthorized webhook attempts:

1. **Verify credentials** - Check if Twilio Auth Token was compromised
2. **Rotate token** - Generate new Auth Token in Twilio Console
3. **Update settings** - Update token in TenantSettings
4. **Review logs** - Check WebhookLog for successful unauthorized access
5. **Investigate** - Determine source and method of attack
6. **Block IP** - Consider IP blocking if attacks persist

## Additional Resources

- Twilio WhatsApp API: https://www.twilio.com/docs/whatsapp/api
- ngrok Documentation: https://ngrok.com/docs
- Webhook Security: https://www.twilio.com/docs/usage/webhooks/webhooks-security
- Twilio Security Best Practices: https://www.twilio.com/docs/usage/security


## Complete Setup Example

### 1. Start Your Environment

Terminal 1 - Start Django:
```bash
python manage.py runserver
```

Terminal 2 - Start Celery Worker:
```bash
celery -A config worker -l info
```

Terminal 3 - Start ngrok:
```bash
ngrok http 8000
```

### 2. Configure Twilio

In Twilio Console > Messaging > Settings > WhatsApp Sandbox:

**When a message comes in**:
- URL: `https://c00265fdeecd.ngrok-free.app/v1/webhooks/twilio`
- Method: `POST`

**Status callback URL**: Leave empty for now

Click **Save**

### 3. Create Your First Tenant

Access Django admin at http://localhost:8000/admin

1. Create Subscription Tier (if not exists):
   - Name: Free
   - Price: 0
   - Max Products: 10
   - Monthly Messages: 100

2. Create Tenant:
   - Name: My Business
   - Contact Email: your@email.com
   - Timezone: Africa/Nairobi

3. Configure Tenant Settings (inline):
   - Twilio SID: Your Twilio Account SID
   - Twilio Token: Your Twilio Auth Token
   - WhatsApp Number: +14155238886

4. Generate API Key:
```bash
python manage.py generate_tenant_api_key <tenant-slug> "Development Key"
```

### 4. Test the Webhook

1. Join WhatsApp sandbox: Send "join one-block" to +1 415 523 8886
2. Send test message: "Hello"
3. Check Django logs for processing
4. You should receive a bot response!

## Troubleshooting

### "X-TENANT-ID and X-TENANT-API-KEY headers are required"

Webhook endpoint doesn't need these headers. Only API endpoints require them.

### Webhook returns 403 Forbidden

This means signature verification failed. Check:
1. Twilio Auth Token is correct in TenantSettings
2. Webhook URL in Twilio Console matches exactly (including https://)
3. No proxy or CDN is modifying the request
4. Check application logs for signature verification details
5. Verify the request is actually coming from Twilio

### Webhook receives message but no response

Check:
1. Tenant exists and subscription is active
2. Celery worker is running
3. OpenAI API key is configured
4. Check webhook logs in Django admin
5. Verify signature verification passed (status='success' in WebhookLog)

### ngrok URL keeps changing

Use ngrok with fixed subdomain (paid) or update Twilio URL each restart.

## Production Checklist

- [ ] Replace ngrok with production domain
- [ ] Configure SSL certificate (required for signature verification)
- [ ] Update Twilio webhook URL in Twilio Console to: `https://your-domain.com/v1/webhooks/twilio`
- [ ] Update status callback URL (optional) to: `https://your-domain.com/v1/webhooks/twilio/status`
- [ ] ✅ Webhook signature validation is enabled by default (no configuration needed)
- [ ] Confirm Twilio Auth Token is correctly configured in TenantSettings (Django Admin > Tenants > Tenant Settings)
- [ ] Set up Sentry DSN in environment variables for security event monitoring
- [ ] Test webhook with real Twilio messages (send WhatsApp message to your number)
- [ ] Monitor WebhookLog in Django Admin for any unauthorized attempts
- [ ] Review application logs for any signature verification failures
- [ ] Configure firewall rules (optional: whitelist Twilio IPs for additional security)
- [ ] Set up Sentry alerts for `invalid_webhook_signature` events
- [ ] Run automated tests to verify signature verification: `pytest apps/integrations/tests/test_twilio_webhook.py`

## Resources

- Twilio Console: https://console.twilio.com/
- WhatsApp Sandbox: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
- ngrok Dashboard: https://dashboard.ngrok.com/
