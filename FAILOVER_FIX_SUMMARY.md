# LLM Provider Failover Fix

**Date**: November 20, 2025  
**Status**: ✅ FIXED

## Issues Found

### 1. OpenAI Quota Exceeded (429 Error)
```
Error code: 429 - insufficient_quota
Message: "You exceeded your current quota, please check your plan and billing details"
```

**Root Cause**: OpenAI API key has no remaining quota/credits.

### 2. Gemini Model Name Error (404 Error)
```
404 models/gemini-1.5-pro-latest is not found for API version v1beta
```

**Root Cause**: Gemini API v1beta doesn't support `-latest` suffix in model names.

### 3. No Together AI in Fallback Chain
When both OpenAI and Gemini failed, the system had no other providers to try.

## Fixes Applied

### Fix 1: Corrected Gemini Model Names

**File**: `apps/bot/services/llm/gemini_provider.py`

**Changed**:
```python
# BEFORE (BROKEN)
'gemini-1.5-pro': {
    'api_model_name': 'gemini-1.5-pro-latest',  # ❌ Not supported in v1beta
}

# AFTER (FIXED)
'gemini-1.5-pro': {
    'api_model_name': 'gemini-1.5-pro',  # ✅ Stable version works
}
```

All model configurations updated:
- `gemini-1.5-pro` → uses `gemini-1.5-pro` (not `-latest`)
- `gemini-1.5-flash` → uses `gemini-1.5-flash` (not `-latest`)
- `gemini-1.5-pro-latest` → maps to `gemini-1.5-pro`
- `gemini-1.5-flash-latest` → maps to `gemini-1.5-flash`

### Fix 2: Added Together AI to Fallback Chain

**File**: `apps/bot/services/llm/failover_manager.py`

**New Fallback Order**:
```python
[
    ('openai', 'gpt-4o'),                                      # 1st: Primary
    ('gemini', 'gemini-1.5-pro'),                             # 2nd: Google fallback
    ('together', 'Qwen/Qwen2.5-72B-Instruct-Turbo'),         # 3rd: Multilingual powerhouse
    ('openai', 'gpt-4o-mini'),                                # 4th: Cheaper OpenAI
    ('gemini', 'gemini-1.5-flash'),                           # 5th: Cheaper Gemini
    ('together', 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo'),  # 6th: Strong Llama
    ('together', 'Qwen/Qwen2.5-7B-Instruct-Turbo'),          # 7th: Cost-effective final fallback
]
```

**Why This Order?**
1. **OpenAI GPT-4o**: Best quality, try first
2. **Gemini 1.5 Pro**: Good quality, large context
3. **Qwen 2.5 72B**: Excellent for multilingual (Swahili/Sheng), via Together AI
4. **OpenAI GPT-4o-mini**: Cheaper OpenAI option
5. **Gemini 1.5 Flash**: Cheaper Gemini option
6. **Llama 3.1 70B**: Strong open-source model
7. **Qwen 2.5 7B**: Final fallback, very cheap ($0.30/1M tokens)

## Configuration Required

### Set Together AI API Key

To enable Together AI fallback, add to `.env`:

```bash
TOGETHER_API_KEY=your-together-api-key-here
```

**Get API Key**: https://api.together.xyz/

### Alternative: Use Gemini Only

If you don't want to use Together AI, ensure Gemini is configured:

```bash
GEMINI_API_KEY=your-gemini-api-key-here
```

**Get API Key**: https://makersuite.google.com/app/apikey

## Testing

### Test Gemini Fix

```bash
DJANGO_SETTINGS_MODULE=config.settings python -c "
import django
django.setup()
from apps.bot.services.llm.gemini_provider import GeminiProvider
import os

provider = GeminiProvider(api_key=os.getenv('GEMINI_API_KEY'))
print(f'✅ Gemini models: {list(provider.MODELS.keys())}')
print(f'✅ gemini-1.5-pro maps to: {provider.MODELS[\"gemini-1.5-pro\"][\"api_model_name\"]}')
"
```

### Test Failover Chain

```bash
DJANGO_SETTINGS_MODULE=config.settings python -c "
import django
django.setup()
from apps.bot.services.llm.failover_manager import ProviderFailoverManager

manager = ProviderFailoverManager()
print('✅ Fallback order:')
for i, (provider, model) in enumerate(manager.fallback_order, 1):
    print(f'  {i}. {provider}/{model}')
"
```

## Expected Behavior

### Scenario 1: OpenAI Quota Exceeded

```
1. Try OpenAI GPT-4o → 429 Error (quota exceeded)
2. Try Gemini 1.5 Pro → ✅ Success
3. Response generated successfully
```

### Scenario 2: Both OpenAI and Gemini Fail

```
1. Try OpenAI GPT-4o → 429 Error
2. Try Gemini 1.5 Pro → Error
3. Try Together AI Qwen 2.5 72B → ✅ Success
4. Response generated successfully
```

### Scenario 3: All Providers Fail

```
1-7. All providers fail
8. Return error message to customer
9. Trigger human handoff
```

## Benefits

### 1. Reliability
- ✅ 7 fallback options instead of 4
- ✅ Multiple provider types (OpenAI, Google, Together AI)
- ✅ Automatic failover on any error

### 2. Cost Optimization
- ✅ Qwen 2.5 7B: $0.30/1M tokens (final fallback)
- ✅ Llama 3.1 70B: $0.88/1M tokens
- ✅ Much cheaper than OpenAI ($15/1M for GPT-4o)

### 3. Multilingual Support
- ✅ Qwen models excel at Swahili/Sheng
- ✅ Better than OpenAI for African languages
- ✅ Natural code-switching support

### 4. No Single Point of Failure
- ✅ If OpenAI is down → Use Gemini
- ✅ If Gemini is down → Use Together AI
- ✅ If one Together model fails → Try another

## Monitoring

### Check Provider Health

The failover manager tracks provider health:

```python
# In logs, you'll see:
INFO: Provider openai marked unhealthy: failure_rate=100.00%
INFO: Trying next provider in fallback order...
INFO: Attempt 3/7: provider=together, model=Qwen/Qwen2.5-72B-Instruct-Turbo
```

### Success Metrics

After fix, you should see:
- ✅ Fewer "All providers failed" errors
- ✅ More successful responses via fallback providers
- ✅ Lower average cost per request (using cheaper models)

## Troubleshooting

### Issue: "All providers failed"

**Check**:
1. Is `GEMINI_API_KEY` set in `.env`?
2. Is `TOGETHER_API_KEY` set in `.env`?
3. Do you have quota/credits on at least one provider?

**Solution**: Set at least one working API key:
```bash
# Option 1: Use Gemini (free tier available)
GEMINI_API_KEY=your-key

# Option 2: Use Together AI (pay-as-you-go)
TOGETHER_API_KEY=your-key

# Option 3: Top up OpenAI credits
# Go to: https://platform.openai.com/account/billing
```

### Issue: Gemini still returns 404

**Check**: Are you using the correct API version?

**Solution**: The fix uses stable model names without `-latest` suffix. If still failing, check your Gemini API key is valid:
```bash
curl -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Hello"}]}]}' \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=YOUR_API_KEY"
```

### Issue: Together AI not being used

**Check**: Is the API key set?
```bash
echo $TOGETHER_API_KEY
```

**Solution**: Add to `.env`:
```bash
TOGETHER_API_KEY=your-together-api-key-here
```

Then restart the application:
```bash
# Restart Celery workers
pkill -f celery
celery -A config worker -l info &

# Restart Django
python manage.py runserver
```

## Recommendations

### For Production

1. **Set all three API keys** for maximum reliability:
   ```bash
   OPENAI_API_KEY=your-openai-key
   GEMINI_API_KEY=your-gemini-key
   TOGETHER_API_KEY=your-together-key
   ```

2. **Monitor provider health** in logs

3. **Set up alerts** for "All providers failed" errors

4. **Keep credits topped up** on at least 2 providers

### For Development

1. **Use Gemini** (free tier available):
   ```bash
   GEMINI_API_KEY=your-gemini-key
   ```

2. **Or use Together AI** (cheap, pay-as-you-go):
   ```bash
   TOGETHER_API_KEY=your-together-key
   ```

### For Cost Optimization

1. **Primary**: Gemini 1.5 Flash ($0.075/1M input, $0.30/1M output)
2. **Fallback**: Qwen 2.5 7B via Together AI ($0.30/1M tokens)
3. **Reserve**: OpenAI for complex queries only

## Summary

✅ **Fixed Gemini model names** - No more 404 errors  
✅ **Added Together AI to fallback chain** - 7 fallback options now  
✅ **Better multilingual support** - Qwen models for Swahili/Sheng  
✅ **Cost optimization** - Cheaper fallback options  
✅ **Higher reliability** - Multiple provider types  

The bot will now automatically failover through 7 different provider/model combinations before giving up! 🎉
