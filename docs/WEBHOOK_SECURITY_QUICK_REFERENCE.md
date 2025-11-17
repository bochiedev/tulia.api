# Webhook Security Quick Reference

## Overview

All webhook endpoints in this application use signature verification to prevent unauthorized access and message injection attacks.

## Twilio Webhooks

### Endpoints

| Endpoint | Purpose | Signature Verified |
|----------|---------|-------------------|
| `POST /v1/webhooks/twilio` | Incoming WhatsApp messages | ✅ Yes |
| `POST /v1/webhooks/twilio/status` | Message delivery status | ✅ Yes |

### How It Works

1. **Twilio signs each request** with your Auth Token using HMAC-SHA1
2. **Signature sent in header**: `X-Twilio-Signature`
3. **Server verifies signature** before processing
4. **Invalid signatures rejected** with 403 Forbidden

### Security Features

- ✅ HMAC-SHA1 signature verification
- ✅ Constant-time comparison (prevents timing attacks)
- ✅ Fail-secure error handling
- ✅ Security event logging
- ✅ Sentry alerts for critical events
- ✅ WebhookLog tracking

### Configuration

Signature verification uses the Twilio Auth Token from TenantSettings:

```python
# Django Admin > Tenants > Tenant Settings
twilio_sid = "AC..."
twilio_token = "..."  # Used for signature verification
```

### Testing

```bash
# Run webhook signature tests
pytest apps/integrations/tests/test_twilio_webhook.py -v

# Test invalid signature (should return 403)
curl -X POST https://your-domain.com/v1/webhooks/twilio \
  -d "From=whatsapp:+1234567890" \
  -d "Body=Test"
```

### Monitoring

**WebhookLog Model** (Django Admin > Integrations > Webhook Logs):
- All webhook attempts logged
- Status: `success`, `error`, `unauthorized`
- Full payload and headers stored

**Security Events** (Application Logs):
```json
{
  "event_type": "invalid_webhook_signature",
  "provider": "twilio",
  "tenant_id": "...",
  "ip_address": "...",
  "url": "...",
  "user_agent": "..."
}
```

**Sentry Alerts**:
- Critical events sent to Sentry
- Real-time alerting for security violations

### Troubleshooting

**403 Forbidden Error**:
1. Verify Twilio Auth Token in TenantSettings
2. Check webhook URL matches exactly (including https://)
3. Ensure no proxy is modifying requests
4. Review application logs for details

**Legitimate webhooks rejected**:
1. Confirm Auth Token is correct
2. Check for URL mismatches
3. Verify SSL certificate is valid
4. Test with real Twilio message (not curl)

## Implementation Details

### Signature Verification Function

```python
def verify_twilio_signature(url, params, signature, auth_token):
    """
    Verify Twilio webhook signature.
    
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Sort parameters and concatenate with URL
        sorted_params = sorted(params.items())
        data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
        
        # Compute HMAC-SHA1
        computed = hmac.new(
            auth_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64 encode and compare
        computed_b64 = base64.b64encode(computed).decode('utf-8')
        return hmac.compare_digest(computed_b64, signature)
    except:
        return False  # Fail securely
```

### Security Event Logging

```python
# Log invalid signature
SecurityLogger.log_invalid_webhook_signature(
    provider='twilio',
    tenant_id=str(tenant.id),
    ip_address=request.META.get('REMOTE_ADDR'),
    url=full_url,
    user_agent=request.META.get('HTTP_USER_AGENT')
)
```

### WebhookLog Integration

```python
# Mark as unauthorized
webhook_log.mark_unauthorized('Twilio signature verification failed')
```

## Best Practices

1. **Never disable signature verification** - It's a critical security control
2. **Monitor WebhookLog regularly** - Check for unauthorized attempts
3. **Set up Sentry alerts** - Get notified of security events
4. **Rotate Auth Token if compromised** - Update in Twilio Console and TenantSettings
5. **Use HTTPS only** - Required for secure signature verification
6. **Review logs periodically** - Look for patterns of attacks

## Production Checklist

- [ ] SSL certificate configured
- [ ] Webhook URL uses HTTPS
- [ ] Twilio Auth Token configured in TenantSettings
- [ ] Sentry DSN configured for alerts
- [ ] WebhookLog monitoring set up
- [ ] Security event alerting configured
- [ ] Tests passing: `pytest apps/integrations/tests/test_twilio_webhook.py`

## Resources

- Full Documentation: `docs/TWILIO_WEBHOOK_SETUP.md`
- Implementation: `apps/integrations/views.py`
- Security Logger: `apps/core/logging.py`
- Tests: `apps/integrations/tests/test_twilio_webhook.py`
- Twilio Security Docs: https://www.twilio.com/docs/usage/webhooks/webhooks-security

## Support

For issues or questions:
1. Check application logs for details
2. Review WebhookLog in Django Admin
3. Check Sentry for security events
4. Refer to full documentation
