# Starting the Bot System

Your webhook is now working and storing messages, but the AI bot isn't responding because **Celery is not running**.

## Quick Start

Open a new terminal and run:

```bash
cd ~/Music/tulia.api
source venv/bin/activate
celery -A config worker -l info
```

Keep this terminal open. You should see:
```
[tasks]
  . apps.analytics.tasks.rollup_daily_analytics
  . apps.bot.tasks.process_inbound_message  ← This is your new task!
  . apps.integrations.tasks.sync_woo_products
  ...
```

## Test It

1. Send a WhatsApp message to your Twilio number: **"Hello"**
2. Watch the Celery terminal - you should see:
   ```
   [INFO] Processing inbound message
   [INFO] Intent classified: GREETING (confidence: 0.95)
   [INFO] Response sent successfully
   ```
3. You should receive a WhatsApp response!

## What Happens Now

When a WhatsApp message arrives:

1. ✅ **Webhook receives it** (already working)
2. ✅ **Message stored in database** (already working)
3. 🆕 **Celery task triggered** → `process_inbound_message.delay()`
4. 🆕 **AI classifies intent** → Uses OpenAI GPT-4
5. 🆕 **Handler processes intent** → Product/Service/Support handlers
6. 🆕 **Response sent via Twilio** → Customer gets reply

## Supported Intents

Your bot can now handle:

**Products:**
- "Hello" → Greeting
- "Show me products" → Browse catalog
- "Tell me about [product]" → Product details
- "Add to cart" → Shopping cart

**Services:**
- "Book an appointment" → Appointment booking
- "Check availability" → Available slots
- "Cancel my appointment" → Cancellation

**Support:**
- "I need help" → Human handoff
- "STOP" → Opt-out

## Troubleshooting

### No response from bot?

Check Celery terminal for errors:
```bash
# Look for these errors:
- "OpenAI API key not configured" → Check .env OPENAI_API_KEY
- "Twilio send failed" → Check tenant Twilio credentials
- "Intent classification failed" → Check OpenAI API quota
```

### OpenAI API Key

Your `.env` already has:
```
OPENAI_API_KEY=sk-proj-Ye_pcWZ5VbrAK3y267dgG4kGmRYujSe9zJV-VXOyEid0-jhbufyfiyuvht-P-XjDqwsy0pWWp5cmgMWdUmwO34QwWFpAAGDPvwt1Lk9doL0gA
```

⚠️ **Note:** This key is visible in your `.env` - make sure it's in `.gitignore`!

### Check Recent Messages

```bash
source venv/bin/activate
python manage.py shell
```

```python
from apps.messaging.models import Message
from apps.bot.models import IntentEvent

# Check recent messages
messages = Message.objects.filter(direction='in').order_by('-created_at')[:5]
for m in messages:
    print(f"{m.created_at}: {m.text}")

# Check intent events
intents = IntentEvent.objects.order_by('-created_at')[:5]
for i in intents:
    print(f"{i.created_at}: {i.intent_name} ({i.confidence_score:.2f})")
```

## Production Setup

For production, use a process manager:

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
```

## Next Steps

1. **Start Celery** (see Quick Start above)
2. **Test with WhatsApp** - Send "Hello"
3. **Monitor logs** - Watch Celery terminal
4. **Check IntentEvents** - See what intents are being classified

Your bot is ready to go! 🚀
