# Quick Start Guide

## 1. Import to Postman

Drag both files into Postman:
- `TuliaAI.postman_collection.json`
- `TuliaAI.postman_environment.json`

Select environment: **TuliaAI Development**

## 2. Your Credentials (Already Configured!)

From your `.env` file:

```
Tenant ID: 604923c8-cff3-49d7-b3a3-fe5143c5c46b
API Key: a96b73152af3e755424b11a6dad39a44bbebb553c7608f0b138a48ba95e54d68
```

These are already set in the environment variables!

## 3. Test the API (3 Steps)

### Step 1: Health Check
```
GET {{base_url}}/v1/health/
```
No auth required. Should return 200 OK.

### Step 2: List Integrations
```
GET {{base_url}}/v1/settings/integrations
Headers:
  X-TENANT-ID: {{tenant_id}}
  X-TENANT-API-KEY: {{tenant_api_key}}
```
Should return your integration status.

### Step 3: Set Twilio Credentials
```
POST {{base_url}}/v1/settings/integrations/twilio
Headers:
  X-TENANT-ID: {{tenant_id}}
  X-TENANT-API-KEY: {{tenant_api_key}}
  Content-Type: application/json

Body:
{
  "sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "token": "your_twilio_auth_token",
  "whatsapp_number": "whatsapp:+14155238886",
  "test_connection": true
}
```

## 4. Get Twilio Credentials

From [Twilio Console](https://console.twilio.com/):
1. Copy **Account SID** (starts with AC)
2. Copy **Auth Token** (click to reveal)
3. Get your WhatsApp number from **Messaging → Try it out → Send a WhatsApp message**

## 5. Configure Webhook

In Twilio Console:
1. Go to **Messaging → Settings → WhatsApp sandbox settings**
2. Set webhook URL: `https://your-ngrok-url.ngrok-free.app/v1/webhooks/twilio/`
3. Method: POST
4. Save

## 6. Test WhatsApp

Send a message to your Twilio WhatsApp number. Check Django logs:

```bash
# Should see:
INFO Twilio webhook received
INFO Tenant resolved by WhatsApp number
INFO Inbound message stored
```

## Common Headers

All tenant-scoped endpoints need:
```
X-TENANT-ID: {{tenant_id}}
X-TENANT-API-KEY: {{tenant_api_key}}
```

These are automatically included in all requests!

## Troubleshooting

**401 Unauthorized?**
- Check API key is correct
- Verify tenant ID matches

**403 Forbidden?**
- You need the required RBAC scope
- Check endpoint description for required scope

**Signature verification failed?**
- Restart Django server after adding proxy settings
- Verify ngrok URL matches Twilio webhook URL exactly
- Check Twilio auth token is correct

## Next Steps

1. ✅ Import collection
2. ✅ Test health check
3. ✅ Set Twilio credentials
4. ✅ Configure webhook
5. ✅ Send test WhatsApp message
6. 🎉 Your AI bot is live!
