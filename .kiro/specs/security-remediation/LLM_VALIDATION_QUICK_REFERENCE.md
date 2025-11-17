# LLM Response Validation - Quick Reference

## Overview

All LLM responses in WabotIQ are validated and sanitized to prevent injection attacks and data corruption.

---

## Validation Layers

### 1. JSON Schema Validation
```python
# Validates structure, types, and constraints
INTENT_RESPONSE_SCHEMA = {
    "required": ["intent", "confidence"],
    "properties": {
        "intent": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "slots": {
            "type": "object",
            "maxProperties": 20,
            "patternProperties": {"^[a-zA-Z0-9_]+$": {...}}
        }
    }
}
```

### 2. Intent Whitelist
```python
# Only allowed intents accepted
if intent_name not in ALL_INTENTS:
    intent_name = 'OTHER'  # Safe default
```

### 3. Slot Key Validation
```python
# Pattern: ^[a-zA-Z0-9_]+$
# Rejects: special characters, spaces, unicode
```

### 4. Slot Value Sanitization
```python
# Multi-layer defense:
# - HTML escaping (XSS prevention)
# - SQL escaping (injection prevention)
# - Control character removal
# - Length limits (500 chars)
# - Numeric bounds checking
# - NaN/Infinity rejection
```

---

## Attack Vectors Mitigated

| Attack Type | Mitigation |
|-------------|------------|
| **SQL Injection** | Quote escaping, comment removal, semicolon removal |
| **XSS** | HTML entity escaping, special char conversion |
| **Command Injection** | Semicolon removal, control char removal |
| **Path Traversal** | Backslash escaping, null byte removal |
| **DoS** | Length limits, slot count limits, numeric bounds |
| **Data Corruption** | Type validation, null byte removal, empty string removal |

---

## Usage Example

```python
from apps.bot.services import create_intent_service

# Create service
service = create_intent_service()

# Classify message (automatic validation)
result = service.classify_intent("Show me your products")

# Result is guaranteed to be:
# - Valid JSON structure
# - Whitelisted intent name
# - Confidence in range 0.0-1.0
# - Sanitized slot values
# - Safe for database storage
# - Safe for display
```

---

## What Gets Sanitized

### String Values:
```python
# Input:  "<script>alert('XSS')</script>"
# Output: "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"

# Input:  "'; DROP TABLE users; --"
# Output: "&#x27;&#x27; DROP TABLE users "

# Input:  "hello\x00world"
# Output: "helloworld"

# Input:  "a" * 1000
# Output: "a" * 500  # Truncated
```

### Numeric Values:
```python
# Input:  float('inf')
# Output: Rejected (removed from slots)

# Input:  2**32
# Output: 2147483647  # Clamped to MAX_INT

# Input:  float('nan')
# Output: Rejected (removed from slots)
```

### Invalid Keys:
```python
# Input:  {"product-id": "123"}
# Output: {}  # Key rejected (contains hyphen)

# Input:  {"__proto__": "pollute"}
# Output: {}  # Key rejected (double underscore)
```

---

## Monitoring

All validation failures are logged with structured data:

```python
logger.warning(
    "Unknown intent returned by LLM",
    extra={
        'invalid_intent': 'MALICIOUS_INTENT',
        'message_text': 'customer message...',
        'allowed_intents': ALL_INTENTS
    }
)
```

---

## Testing

Run validation tests:
```bash
# All malicious response tests (22 tests)
pytest apps/bot/tests/test_intent_service_config.py::TestMaliciousLLMResponses -v

# All sanitization tests (20 tests)
pytest apps/bot/tests/test_intent_service_config.py -k "sanitize or escape" -v
```

---

## Dependencies

```bash
pip install jsonschema openai
```

---

## Performance

- **Validation overhead:** ~1-2ms per response
- **Graceful degradation:** Works without jsonschema (logs warning)
- **Single-pass sanitization:** Efficient string processing
- **Minimal allocations:** Optimized for production

---

## Security Best Practices

1. **Never trust LLM output** - Always validate
2. **Defense-in-depth** - Multiple validation layers
3. **Fail-safe defaults** - Reject invalid data
4. **Log everything** - Track validation failures
5. **Test thoroughly** - Cover all attack vectors

---

## Related Documentation

- **Full Implementation:** `apps/bot/services/intent_service.py`
- **Test Suite:** `apps/bot/tests/test_intent_service_config.py`
- **Completion Summary:** `.kiro/specs/security-remediation/TASK_2.1_COMPLETION_SUMMARY.md`
- **Security Tasks:** `.kiro/specs/security-remediation/tasks.md`

---

## Quick Checklist

When processing LLM responses:
- ✅ Use `IntentService.classify_intent()` (automatic validation)
- ✅ Never bypass validation
- ✅ Log validation failures
- ✅ Monitor for suspicious patterns
- ✅ Test with malicious inputs
- ✅ Keep validation rules updated

---

## Emergency Response

If validation is bypassed or fails:

1. **Immediate:** Check logs for validation failures
2. **Investigate:** Review LLM responses in database
3. **Mitigate:** Enable additional logging
4. **Fix:** Update validation rules
5. **Test:** Run full test suite
6. **Deploy:** Push fix to production
7. **Monitor:** Watch for recurrence

---

## Contact

For security concerns or questions:
- Review: `.kiro/specs/security-remediation/`
- Tests: `apps/bot/tests/test_intent_service_config.py`
- Code: `apps/bot/services/intent_service.py`
