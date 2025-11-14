# OpenAI Model Configuration Fix

## Problem
The bot was failing with error:
```
openai.BadRequestError: Error code: 400 - {'error': {'message': "Invalid parameter: 'response_format' of type 'json_object' is not supported with this model."}}
```

This occurred because the code was using `response_format={"type": "json_object"}` with a model that doesn't support JSON mode.

## Root Cause
- The default model was set to `gpt-4` which may not support JSON mode depending on the version
- The code didn't check if the model supports JSON mode before using the parameter
- No fallback mechanism for models without JSON mode support

## Solution Applied

### 1. Changed Default Model
- Updated default from `gpt-4` to `gpt-4o-mini`
- `gpt-4o-mini` is faster, cheaper, and supports JSON mode

### 2. Added Model Compatibility Check
- Added `_check_json_mode_support()` method to detect if model supports JSON mode
- Only adds `response_format` parameter if model supports it
- Supported models:
  - gpt-4o, gpt-4o-mini, gpt-4-turbo
  - gpt-3.5-turbo-1106 and later versions

### 3. Added JSON Extraction Fallback
- Added `_extract_json_from_text()` method to parse JSON from non-JSON-mode responses
- Handles markdown code blocks: ```json ... ```
- Extracts JSON objects from plain text responses

### 4. Made Model Configurable
- Added `OPENAI_MODEL` environment variable
- Can be set in `.env` file
- Falls back to `gpt-4o-mini` if not set

## Configuration

Add to your `.env` file:
```bash
OPENAI_MODEL=gpt-4o-mini  # Options: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo-1106
```

## Files Modified
1. `apps/bot/services/intent_service.py` - Added compatibility checks and fallback parsing
2. `.env` - Added OPENAI_MODEL configuration
3. `.env.example` - Added OPENAI_MODEL with documentation

## Testing
After applying this fix:
1. Restart Celery workers: `./start_celery.sh`
2. Send a test message to your WhatsApp bot
3. Check logs - should see: `IntentService initialized with model: gpt-4o-mini (JSON mode: True)`
4. Message should be processed successfully without 400 errors

## Benefits
- ✅ Works with all OpenAI models (with or without JSON mode)
- ✅ Faster and cheaper with gpt-4o-mini
- ✅ Configurable via environment variable
- ✅ Automatic fallback for non-JSON-mode models
- ✅ Better error handling and logging
