# Security Remediation Design Document

## Architecture Overview

This security remediation addresses vulnerabilities across multiple layers:
- Authentication & Authorization Layer
- Input Validation Layer
- Data Encryption Layer
- API Security Layer
- Database Transaction Layer

## Component Design

### 1. Secure Password Hashing

**Current Issue:**
```python
# INSECURE - uses SHA-256
password_hash=hashlib.sha256(password.encode()).hexdigest()
```

**Fixed Design:**
```python
# Use Django's secure password hashing (PBKDF2)
user = User.objects.create(
    email=email,
    first_name=first_name,
    last_name=last_name,
)
user.set_password(password)  # Uses PBKDF2 with salt
user.save()
```

**Security Properties:**
- PBKDF2 with 260,000 iterations
- Unique salt per password
- Resistant to rainbow table attacks
- Configurable work factor

---

### 2. Webhook Signature Verification

**Architecture:**
```
Twilio → HTTPS → Signature Verification → Webhook Handler
                      ↓ (if invalid)
                   403 Forbidden
```

**Implementation:**
```python
from twilio.request_validator import RequestValidator

def verify_twilio_signature(request, tenant):
    """Verify Twilio webhook signature."""
    validator = RequestValidator(tenant.settings.twilio_token)
    signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
    url = request.build_absolute_uri()
    
    # Get POST data as dict
    post_data = dict(request.POST.items())
    
    return validator.validate(url, post_data, signature)
```

**Security Properties:**
- HMAC-SHA1 signature verification
- Prevents message injection
- Validates request origin
- Protects against replay attacks (with timestamp)

---

### 3. JWT Secret Key Validation

**Configuration Hierarchy:**
```
1. JWT_SECRET_KEY (required, separate from SECRET_KEY)
2. Validation: length >= 32, high entropy
3. No fallback to SECRET_KEY
```

**Implementation:**
```python
# settings.py
JWT_SECRET_KEY = env('JWT_SECRET_KEY')  # No default!

# Validation
if not JWT_SECRET_KEY:
    raise ImproperlyConfigured("JWT_SECRET_KEY must be set")

if len(JWT_SECRET_KEY) < 32:
    raise ImproperlyConfigured("JWT_SECRET_KEY must be at least 32 characters")

if JWT_SECRET_KEY == SECRET_KEY:
    raise ImproperlyConfigured("JWT_SECRET_KEY must differ from SECRET_KEY")
```

---

### 4. Rate Limiting Architecture

**Multi-Layer Rate Limiting:**
```
Request → IP Rate Limit → Email Rate Limit → Endpoint Handler
            ↓ (if exceeded)      ↓ (if exceeded)
         429 Response         429 Response
```

**Configuration:**
```python
# Per-IP limits (prevent distributed attacks)
@ratelimit(key='ip', rate='10/m', method='POST')

# Per-email limits (prevent credential stuffing)
@ratelimit(key='post:email', rate='5/h', method='POST')

# Per-user limits (prevent account abuse)
@ratelimit(key='user', rate='100/h', method='POST')
```

**Storage:** Redis for fast, distributed rate limiting

---

### 5. Input Validation for LLM Responses

**Validation Pipeline:**
```
LLM Response → JSON Parse → Schema Validation → Sanitization → Use
                  ↓              ↓                  ↓
              (malformed)    (invalid)         (dangerous)
                  ↓              ↓                  ↓
              Reject         Reject             Sanitize
```

**Schema:**
```python
INTENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ALL_INTENTS  # Whitelist only
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "slots": {
            "type": "object",
            "maxProperties": 20,
            "patternProperties": {
                "^[a-z_]+$": {  # Only lowercase + underscore
                    "type": ["string", "number", "boolean"],
                    "maxLength": 500  # Limit string length
                }
            }
        }
    },
    "required": ["intent", "confidence"]
}
```

---

### 6. Encryption Key Management

**Key Hierarchy:**
```
Master Key (ENCRYPTION_KEY)
    ↓
Current Key (active encryption)
    ↓
Old Keys (decryption only, for rotation)
```

**Validation:**
```python
def validate_encryption_key(key_b64: str) -> bytes:
    """Validate encryption key strength."""
    key = base64.b64decode(key_b64)
    
    # Length check
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes")
    
    # Entropy check
    if len(set(key)) < 16:
        raise ValueError("Key has insufficient entropy")
    
    # Weak key check
    if key == b'\x00' * 32:
        raise ValueError("Key is all zeros")
    
    return key
```

**Rotation Strategy:**
```python
# Support multiple keys for rotation
ENCRYPTION_KEY = env('ENCRYPTION_KEY')  # Current
ENCRYPTION_OLD_KEYS = env.list('ENCRYPTION_OLD_KEYS', default=[])

# Decrypt with current key first, fall back to old keys
# Encrypt always uses current key
```

---

### 7. Race Condition Resolution

**Problem:** Cache invalidation race
```
Thread A: Read cache (old scopes)
Thread B: Update role
Thread B: Invalidate cache
Thread A: Use old scopes ❌
```

**Solution:** Cache versioning
```
Thread A: Read cache v1
Thread B: Update role
Thread B: Increment version to v2
Thread A: Use cache v1 (still valid for this request)
Next request: Read cache v2 (new scopes)
```

**Implementation:**
```python
def resolve_scopes(tenant_user):
    version = cache.get(f"scope_version:{tenant_user.id}", 0)
    cache_key = f"scopes:{tenant_user.id}:v{version}"
    
    scopes = cache.get(cache_key)
    if scopes is None:
        scopes = _compute_scopes(tenant_user)
        cache.set(cache_key, scopes, 300)
    
    return scopes

def invalidate_scopes(tenant_user):
    # Increment version to invalidate all cached versions
    cache.incr(f"scope_version:{tenant_user.id}", default=0)
```

---

### 8. Atomic Counter Operations

**Problem:** Race condition in counter increment
```
Thread A: Read count = 5
Thread B: Read count = 5
Thread A: Write count = 6
Thread B: Write count = 6  ❌ (should be 7)
```

**Solution:** Database-level atomic operations
```python
from django.db.models import F

# Atomic increment
Conversation.objects.filter(id=conv_id).update(
    low_confidence_count=F('low_confidence_count') + 1
)

# Atomic reset
Conversation.objects.filter(id=conv_id).update(
    low_confidence_count=0
)
```

---

### 9. Transaction Management for Celery

**Pattern:**
```python
from django.db import transaction

@shared_task(bind=True, max_retries=3)
def sync_products_task(self, tenant_id):
    try:
        with transaction.atomic():
            # All database operations
            tenant = Tenant.objects.select_for_update().get(id=tenant_id)
            # ... sync logic
            # Commit happens automatically if no exception
    except Exception as exc:
        # Rollback happens automatically
        logger.error(f"Task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
```

**Benefits:**
- All-or-nothing execution
- Automatic rollback on failure
- Prevents partial updates
- Supports retries

---

### 10. Security Event Logging

**Event Types:**
```python
class SecurityEvent(Enum):
    FAILED_LOGIN = "failed_login"
    PERMISSION_DENIED = "permission_denied"
    INVALID_WEBHOOK_SIGNATURE = "invalid_webhook_signature"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    FOUR_EYES_VIOLATION = "four_eyes_violation"
```

**Logging Architecture:**
```
Security Event → Structured Logger → Multiple Destinations
                                          ↓
                        ┌─────────────────┼─────────────────┐
                        ↓                 ↓                 ↓
                    File Log          Sentry          SIEM System
```

**Implementation:**
```python
class SecurityLogger:
    @staticmethod
    def log_event(event_type, **context):
        logger.warning(
            f"Security event: {event_type}",
            extra={
                'event_type': event_type,
                'timestamp': timezone.now().isoformat(),
                'ip_address': context.get('ip_address'),
                'user_email': context.get('user_email'),
                'tenant_id': context.get('tenant_id'),
                **context
            }
        )
        
        # Send to Sentry for alerting
        if event_type in CRITICAL_EVENTS:
            sentry_sdk.capture_message(
                f"Critical security event: {event_type}",
                level='error',
                extras=context
            )
```

---

### 11. HTTPS Enforcement

**Configuration:**
```python
if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Additional security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
```

---

### 12. Four-Eyes Validation

**Strict Validation:**
```python
def validate_four_eyes(initiator_user_id: UUID, approver_user_id: UUID) -> bool:
    """
    Validate four-eyes principle with strict checks.
    
    Raises:
        ValueError: If validation fails
    """
    # Both must be provided
    if not initiator_user_id:
        raise ValueError("Initiator user ID is required")
    
    if not approver_user_id:
        raise ValueError("Approver user ID is required")
    
    # Must be different users
    if initiator_user_id == approver_user_id:
        raise ValueError(
            "Four-eyes validation failed: "
            "initiator and approver must be different users"
        )
    
    # Both users must exist and be active
    if not User.objects.filter(
        id__in=[initiator_user_id, approver_user_id],
        is_active=True
    ).count() == 2:
        raise ValueError("Both users must exist and be active")
    
    return True
```

---

## Security Testing Strategy

### 1. Unit Tests
- Test each security fix in isolation
- Mock external dependencies
- Test edge cases and error conditions

### 2. Integration Tests
- Test complete authentication flow
- Test webhook signature verification
- Test rate limiting behavior
- Test transaction rollback

### 3. Security Tests
- Attempt to bypass authentication
- Test SQL injection vectors
- Test XSS vectors
- Test CSRF protection
- Test rate limit bypass

### 4. Load Tests
- Concurrent authentication requests
- Race condition scenarios
- Cache invalidation under load

### 5. Penetration Testing
- OWASP Top 10 checks
- Automated security scanning
- Manual security review

---

## Monitoring & Alerting

### Metrics to Track
- Failed login attempts per IP
- Rate limit violations
- Invalid webhook signatures
- Permission denials
- Four-eyes violations
- Encryption errors

### Alerts
- 10+ failed logins from same IP in 5 minutes
- 100+ rate limit violations in 1 hour
- Any invalid webhook signature
- Any four-eyes violation attempt
- Any encryption key error

### Dashboards
- Security events timeline
- Failed authentication heatmap
- Rate limiting statistics
- Webhook verification status

---

## Rollback Plan

If issues are detected after deployment:

1. **Immediate:** Revert to previous version
2. **Investigate:** Review logs and error reports
3. **Fix:** Address root cause
4. **Test:** Comprehensive testing in staging
5. **Redeploy:** With additional monitoring

---

## Documentation Updates

1. Security best practices guide
2. Incident response procedures
3. Key rotation procedures
4. Rate limiting configuration
5. Webhook setup guide
6. Security monitoring setup
7. Penetration testing results

---

## Success Metrics

- Zero critical vulnerabilities in security scan
- 100% webhook signature verification
- < 0.1% false positive rate on rate limiting
- Zero race condition incidents
- 100% transaction rollback on task failure
- < 1 second p95 latency impact from security features
