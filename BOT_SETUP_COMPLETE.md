# 🎉 Bot Setup Complete!

Your Twilio webhook is now fully integrated with AI-powered intent processing.

## What Was Fixed

### 1. Twilio Signature Verification ✅
**Problem:** Webhook was returning 401 - signature verification failed

**Root Cause:** Your tenant had the wrong Twilio Account SID configured
- Webhooks coming from: `AC245ecdc0caca40e8bb9821e2c469bfa2`
- Tenant had configured: `ACbd4391b4e4270acaf4bce53b26c2683a` (wrong!)

**Solution:** Updated tenant's Twilio credentials to match the actual account

### 2. AI Intent Processing ✅
**Problem:** Messages were stored but no bot response

**Root Cause:** Intent processing task wasn't implemented

**Solution:** 
- Created `apps/bot/tasks.py` with `process_inbound_message` Celery task
- Installed OpenAI package (`pip install openai`)
- Connected webhook to trigger the task
- Verified all components are configured

## How It Works Now

```
WhatsApp Message
    ↓
Twilio Webhook → /v1/webhooks/twilio/
    ↓
1. Verify signature ✅
2. Resolve tenant ✅
3. Store message ✅
4. Enqueue Celery task ✅
    ↓
Celery Worker (process_inbound_message)
    ↓
5. Classify intent with OpenAI GPT-4 🤖
6. Route to handler (Product/Service/Support)
7. Send response via Twilio
    ↓
Customer receives reply! 💬
```

## Start the Bot

Open a **new terminal** and run:

```bash
cd ~/Music/tulia.api
./start_celery.sh
```

Or manually:
```bash
source venv/bin/activate
celery -A config worker -l info
```

You should see:
```
[tasks]
  . apps.bot.tasks.process_inbound_message  ← Your new task!
  . apps.analytics.tasks.rollup_daily_analytics
  . apps.integrations.tasks.sync_woo_products
  ...

[INFO] celery@hostname ready.
```

## Test It

1. **Send a WhatsApp message** to `+1 415 523 8886`:
   ```
   Hello
   ```

2. **Watch the Celery terminal** - you should see:
   ```
   [INFO] Processing inbound message
   [INFO] Intent classified: GREETING (confidence: 0.95)
   [INFO] Response sent successfully
   ```

3. **Receive bot response** on WhatsApp! 🎉

## Supported Intents

Your bot can now understand and respond to:

### Product Intents
- **GREETING**: "Hello", "Hi", "Hey"
- **BROWSE_PRODUCTS**: "Show me products", "What do you sell?"
- **PRODUCT_DETAILS**: "Tell me about [product]"
- **PRICE_CHECK**: "How much is [product]?"
- **ADD_TO_CART**: "Add [product] to cart"
- **CHECKOUT_LINK**: "I want to buy", "Checkout"

### Service Intents
- **BROWSE_SERVICES**: "What services do you offer?"
- **SERVICE_DETAILS**: "Tell me about [service]"
- **CHECK_AVAILABILITY**: "When are you available?"
- **BOOK_APPOINTMENT**: "Book a haircut for tomorrow at 2pm"
- **CANCEL_APPOINTMENT**: "Cancel my appointment"

### Support Intents
- **HUMAN_HANDOFF**: "I need help", "Talk to a person"
- **OPT_OUT**: "STOP", "Unsubscribe"

## Configuration

### Environment Variables (.env)
```bash
# OpenAI for intent classification
OPENAI_API_KEY=sk-proj-Ye_pcWZ5VbrA...  ✅ Configured

# Celery/Redis for async processing
CELERY_BROKER_URL=redis://localhost:6379/1  ✅ Configured
REDIS_URL=redis://localhost:6379/0  ✅ Configured
```

### Tenant Settings (Database)
```python
# Starter Store tenant
Twilio SID: AC245ecdc0caca40e8bb9821e2c469bfa2  ✅ Fixed
Twilio Token: 87955d40bc...  ✅ Configured
WhatsApp Number: +14155238886  ✅ Configured
```

## Monitoring

### Check Recent Messages
```bash
source venv/bin/activate
python manage.py shell
```

```python
from apps.messaging.models import Message
from apps.bot.models import IntentEvent

# Recent inbound messages
Message.objects.filter(direction='in').order_by('-created_at')[:5]

# Recent intent classifications
IntentEvent.objects.order_by('-created_at')[:5]
```

### Check Celery Tasks
```bash
# In Celery terminal, watch for:
[INFO] Task apps.bot.tasks.process_inbound_message[uuid] received
[INFO] Intent classified: GREETING (confidence: 0.95)
[INFO] Response sent successfully
[INFO] Task apps.bot.tasks.process_inbound_message[uuid] succeeded
```

### Django Logs
```bash
# In Django runserver terminal:
INFO Twilio webhook received
INFO Tenant resolved by WhatsApp number
INFO Inbound message stored
INFO Intent processing task enqueued  ← New!
```

## Troubleshooting

### No bot response?

**Check 1: Is Celery running?**
```bash
ps aux | grep celery
```
If not, start it: `./start_celery.sh`

**Check 2: Check Celery logs**
Look for errors in the Celery terminal

**Check 3: OpenAI API quota**
```bash
# Test OpenAI connection
python manage.py shell
```
```python
from apps.bot.services.intent_service import create_intent_service
service = create_intent_service()
result = service.classify_intent("Hello")
print(result)
```

**Check 4: Twilio credentials**
```bash
python manage.py shell
```
```python
from apps.tenants.models import Tenant
tenant = Tenant.objects.get(whatsapp_number='+14155238886')
print(f"SID: {tenant.settings.twilio_sid}")
print(f"Token: {tenant.settings.twilio_token[:10]}...")
```

### Low confidence intents

If the bot says "I'm having trouble understanding":
- The AI couldn't classify the intent with high confidence
- After 2 consecutive low-confidence messages, it auto-escalates to human
- Check `IntentEvent` table for confidence scores

### Rate limits

OpenAI has rate limits based on your plan:
- Free tier: 3 requests/minute
- Paid tier: Higher limits

If you hit limits, you'll see errors in Celery logs.

## Files Created/Modified

### New Files
- ✅ `apps/bot/tasks.py` - Celery task for intent processing
- ✅ `START_BOT.md` - Quick start guide
- ✅ `test_bot_setup.py` - Setup verification script
- ✅ `start_celery.sh` - Celery startup script
- ✅ `debug_twilio_signature.py` - Signature debugging tool
- ✅ `fix_twilio_credentials.py` - Credential fix helper

### Modified Files
- ✅ `apps/integrations/views.py` - Added Celery task trigger

### Installed Packages
- ✅ `openai==2.8.0` - OpenAI API client

## Next Steps

1. **Start Celery** (see "Start the Bot" above)
2. **Test with WhatsApp** - Send "Hello"
3. **Monitor logs** - Watch both Django and Celery terminals
4. **Add products** - Populate your catalog so customers can browse
5. **Add services** - Set up services and availability for bookings

## Production Deployment

For production, use a process manager like Supervisor:

```bash
# Install supervisor
sudo apt-get install supervisor

# Create config: /etc/supervisor/conf.d/tulia-celery.conf
[program:tulia-celery]
command=/path/to/venv/bin/celery -A config worker -l info
directory=/path/to/tulia.api
user=your-user
autostart=true
autorestart=true
stdout_logfile=/var/log/tulia/celery.log
stderr_logfile=/var/log/tulia/celery-error.log

# Start it
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start tulia-celery
```

## Support

If you encounter issues:

1. Run the verification script: `python test_bot_setup.py`
2. Check Celery logs for errors
3. Check Django logs for webhook issues
4. Verify OpenAI API key is valid
5. Verify Twilio credentials match your account

---

**Your bot is ready! Start Celery and send a test message.** 🚀
