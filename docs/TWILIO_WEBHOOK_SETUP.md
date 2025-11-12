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

**Headers Required**: None (Twilio signature validation is performed)

**Request Body** (from Twilio):
```
MessageSid=SM...
From=whatsapp:+254722244161
To=whatsapp:+14155238886
Body=Hello
```

**Response**: 200 OK with TwiML

## Troubleshooting

### Webhook not receiving messages

1. Check ngrok is running and URL is correct
2. Verify Twilio webhook URL is saved
3. Check Django logs for errors
4. Ensure no firewall blocking ngrok

### 403 Forbidden Error

The webhook endpoint is public and doesn't require tenant authentication.
If you see 403, check middleware configuration.

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

- Twilio webhooks are validated using signature verification
- No API keys required for webhook endpoint
- Tenant is resolved from the phone number
- All webhook attempts are logged in WebhookLog model

## Additional Resources

- Twilio WhatsApp API: https://www.twilio.com/docs/whatsapp/api
- ngrok Documentation: https://ngrok.com/docs
- Webhook Security: https://www.twilio.com/docs/usage/webhooks/webhooks-security


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

### Webhook receives message but no response

Check:
1. Tenant exists and subscription is active
2. Celery worker is running
3. OpenAI API key is configured
4. Check webhook logs in Django admin

### ngrok URL keeps changing

Use ngrok with fixed subdomain (paid) or update Twilio URL each restart.

## Production Checklist

- [ ] Replace ngrok with production domain
- [ ] Configure SSL certificate
- [ ] Update Twilio webhook URL
- [ ] Enable webhook signature validation
- [ ] Set up monitoring

## Resources

- Twilio Console: https://console.twilio.com/
- WhatsApp Sandbox: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
- ngrok Dashboard: https://dashboard.ngrok.com/
