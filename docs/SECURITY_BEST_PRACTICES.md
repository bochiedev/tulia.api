# Security Best Practices - WabotIQ Platform

**Last Updated:** November 17, 2025  
**Version:** 1.0

---

## Table of Contents

1. [Password Security](#password-security)
2. [Authentication & Authorization](#authentication--authorization)
3. [Input Validation](#input-validation)
4. [Encryption & Key Management](#encryption--key-management)
5. [API Security](#api-security)
6. [Webhook Security](#webhook-security)
7. [Database Security](#database-security)
8. [Logging & Monitoring](#logging--monitoring)
9. [Deployment Security](#deployment-security)
10. [Incident Response](#incident-response)

---

## Password Security

### ✅ DO: Use Django's Built-in Password Hashing

**Always use Django's `set_password()` method for password hashing:**

```python
# ✅ CORRECT: Secure password hashing
user = User(
    email=email,
    first_name=first_name,
    last_name=last_name,
)
user.set_password(password)  # Uses PBKDF2 with 260,000 iterations
user.save()
```

**Security Properties:**
- PBKDF2 algorithm with 260,000 iterations
- Unique salt per password
- Resistant to rainbow table attacks
- Resistant to brute force attacks
- Configurable work factor

### ❌ DON'T: Use Weak Hashing Algorithms

```python
# ❌ WRONG: Insecure hashing
import hashlib
password_hash = hashlib.sha256(password.encode()).hexdigest()  # NO SALT!
password_hash = hashlib.md5(password.encode()).hexdigest()     # BROKEN!
password_hash = password  # NEVER STORE PLAINTEXT!
```

**Why These Are Insecure:**
- No salt = vulnerable to rainbow tables
- Too fast = vulnerable to brute force
- Plaintext = immediate compromise

### Password Requirements

Enforce strong password requirements:

```python
from django.core.validators import MinLengthValidator
from django.contrib.auth.password_validation import validate_password

def register_user(email, password, ...):
    # Validate password strength
    try:
        validate_password(password)
    except ValidationError as e:
        raise ValueError(f"Password too weak: {e.messages}")
    
    # Minimum requirements:
    # - At least 8 characters
    # - Not entirely numeric
    # - Not too common
    # - Not too similar to user info
```

### Password Reset Security

```python
# Generate secure reset tokens
reset_token = secrets.token_urlsafe(32)  # 32 bytes = 256 bits

# Set expiration (24 hours)
user.password_reset_token = reset_token
user.password_reset_sent_at = timezone.now()
user.save()

# Validate expiration
age = timezone.now() - user.password_reset_sent_at
if age.total_seconds() > 24 * 3600:
    raise ValueError("Reset token expired")

# Clear token after use
user.password_reset_token = None
user.password_reset_sent_at = None
user.save()
```

---

## Authentication & Authorization

### JWT Token Security

**Token Generation:**

```python
import jwt
from datetime import datetime, timedelta

def generate_jwt(user):
    """Generate secure JWT token."""
    payload = {
        'user_id': str(user.id),
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow(),
    }
    
    # Use separate JWT secret (NOT Django SECRET_KEY)
    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm='HS256'
    )
    
    return token
```

**Token Validation:**

```python
def validate_jwt(token):
    """Validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=['HS256']
        )
        
        # Verify user still exists and is active
        user = User.objects.get(
            id=payload['user_id'],
            is_active=True
        )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")
    except User.DoesNotExist:
        raise AuthenticationError("User not found")
```

### RBAC Enforcement

**Always check scopes, never hardcode role names:**

```python
# ✅ CORRECT: Check scopes
from apps.core.permissions import HasTenantScopes

class ProductListView(APIView):
    permission_classes = [HasTenantScopes]
    required_scopes = {'catalog:view'}
    
    def get(self, request):
        # User's scopes already validated by middleware
        products = Product.objects.filter(tenant=request.tenant)
        return Response(...)

# ❌ WRONG: Check role names
if request.membership.roles.filter(name='Owner').exists():
    # This violates RBAC principles!
```

### Four-Eyes Principle

**For sensitive operations (withdrawals, deletions):**

```python
def validate_four_eyes(initiator_user_id, approver_user_id):
    """Validate four-eyes principle."""
    # Both must be provided
    if not initiator_user_id or not approver_user_id:
        raise ValueError("Both initiator and approver required")
    
    # Must be different users
    if initiator_user_id == approver_user_id:
        raise ValueError("Initiator and approver must be different")
    
    # Both must exist and be active
    users = User.objects.filter(
        id__in=[initiator_user_id, approver_user_id],
        is_active=True
    )
    if users.count() != 2:
        raise ValueError("Both users must exist and be active")
    
    return True
```

---

## Input Validation

### Validate All User Inputs

```python
from django.core.validators import MaxLengthValidator
from rest_framework import serializers

class MessageSerializer(serializers.ModelSerializer):
    content = serializers.CharField(
        max_length=10000,
        required=True,
        allow_blank=False
    )
    
    def validate_content(self, value):
        # Length check
        if len(value) > 10000:
            raise serializers.ValidationError(
                "Message too long (max 10,000 characters)"
            )
        
        # Sanitize HTML
        value = self.sanitize_html(value)
        
        return value
    
    def sanitize_html(self, text):
        """Remove potentially dangerous HTML."""
        import bleach
        
        # Allow only safe tags
        allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'a']
        allowed_attrs = {'a': ['href', 'title']}
        
        return bleach.clean(
            text,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )
```

### Validate LLM Responses

**Status**: ✅ Implemented in IntentService

Large Language Model (LLM) responses must be validated and sanitized to prevent injection attacks and ensure data integrity. The platform implements comprehensive validation for all LLM-generated content.

#### Why LLM Validation Matters

LLMs can generate unexpected or malicious content:
- **Injection Attacks**: SQL injection, XSS, command injection
- **Data Integrity**: Invalid JSON, out-of-range values, unexpected types
- **Resource Exhaustion**: Extremely long strings, excessive properties
- **Schema Violations**: Missing required fields, unknown intents

#### Validation Pipeline

```
LLM Response → JSON Parse → Schema Validation → Sanitization → Use
                  ↓              ↓                  ↓
              (malformed)    (invalid)         (dangerous)
                  ↓              ↓                  ↓
              Reject         Reject             Sanitize
```

#### JSON Schema Validation

**Implementation** (apps/bot/services/intent_service.py):

```python
import jsonschema
from jsonschema import validate, ValidationError

INTENT_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["intent", "confidence"],
    "properties": {
        "intent": {
            "type": "string",
            "description": "The classified intent name"
            # Validated against whitelist separately
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence score between 0.0 and 1.0"
        },
        "slots": {
            "type": "object",
            "description": "Extracted entities/slots from the message",
            "maxProperties": 20,  # Prevent excessive slot extraction
            "patternProperties": {
                # Slot keys must be alphanumeric with underscores only
                "^[a-zA-Z0-9_]+$": {
                    "oneOf": [
                        {"type": "string", "maxLength": 500},
                        {"type": "number"},
                        {"type": "boolean"},
                        {"type": "null"}
                    ]
                }
            },
            "additionalProperties": False  # Reject unknown properties
        },
        "reasoning": {
            "type": "string",
            "maxLength": 1000,
            "description": "Brief explanation of the classification"
        }
    },
    "additionalProperties": False  # Reject unknown fields
}

def _validate_intent_response(self, response: Dict[str, Any]) -> None:
    """
    Validate LLM response against JSON schema.
    
    Performs multi-layer validation:
    1. JSON schema structure validation
    2. Intent whitelist validation
    3. Confidence range validation
    4. Slot key pattern validation
    
    Args:
        response: Parsed JSON response from LLM
        
    Raises:
        ValidationError: If response doesn't match schema
    """
    # Validate against base schema
    validate(instance=response, schema=self.INTENT_RESPONSE_SCHEMA)
    
    # Additional validation: intent must be in whitelist
    intent = response.get('intent')
    if intent and intent not in self.ALL_INTENTS:
        raise ValidationError(
            f"Intent '{intent}' not in allowed intents list"
        )
    
    # Additional validation: confidence must be in range
    confidence = response.get('confidence')
    if confidence is not None and not (0.0 <= confidence <= 1.0):
        raise ValidationError(
            f"Confidence {confidence} must be between 0.0 and 1.0"
        )
    
    # Additional validation: slot keys must be alphanumeric + underscore
    slots = response.get('slots', {})
    if slots:
        import re
        slot_key_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
        invalid_keys = [k for k in slots.keys() if not slot_key_pattern.match(k)]
        
        if invalid_keys:
            raise ValidationError(
                f"Slot keys {invalid_keys} contain invalid characters. "
                f"Only alphanumeric and underscore allowed."
            )
```

#### Intent Whitelist Validation

All intents must be in the predefined whitelist:

```python
# Supported intents (apps/bot/services/intent_service.py)
PRODUCT_INTENTS = [
    'GREETING', 'BROWSE_PRODUCTS', 'PRODUCT_DETAILS',
    'PRICE_CHECK', 'STOCK_CHECK', 'ADD_TO_CART', 'CHECKOUT_LINK'
]

SERVICE_INTENTS = [
    'BROWSE_SERVICES', 'SERVICE_DETAILS', 'CHECK_AVAILABILITY',
    'BOOK_APPOINTMENT', 'RESCHEDULE_APPOINTMENT', 'CANCEL_APPOINTMENT'
]

CONSENT_INTENTS = [
    'OPT_IN_PROMOTIONS', 'OPT_OUT_PROMOTIONS', 'STOP_ALL', 'START_ALL'
]

SUPPORT_INTENTS = ['HUMAN_HANDOFF', 'OTHER']

ALL_INTENTS = PRODUCT_INTENTS + SERVICE_INTENTS + CONSENT_INTENTS + SUPPORT_INTENTS

# Validation
if intent_name not in self.ALL_INTENTS:
    logger.warning(f"Unknown intent '{intent_name}', defaulting to OTHER")
    intent_name = 'OTHER'
    confidence_score = 0.5
```

#### Slot Value Sanitization

**Comprehensive sanitization prevents injection attacks:**

```python
def _sanitize_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize slot values to prevent injection attacks.
    
    Performs:
    - Length limits (500 chars for strings)
    - Type validation and coercion
    - Numeric bounds checking
    - Removal of dangerous characters
    - Prevention of NaN/Infinity values
    - SQL/XSS escaping for string values
    
    Args:
        slots: Raw slots from LLM response
        
    Returns:
        dict: Sanitized slots with validated types and values
    """
    sanitized = {}
    
    # Maximum values for numeric types
    MAX_INT = 2**31 - 1
    MIN_INT = -(2**31)
    MAX_FLOAT = 1e308
    MIN_FLOAT = -1e308
    
    for key, value in slots.items():
        # Validate key pattern
        if not re.match(r'^[a-zA-Z0-9_]+$', key):
            logger.warning(f"Skipping slot with invalid key: {key}")
            continue
        
        # Sanitize based on type
        if isinstance(value, str):
            # Enforce length limit
            if len(value) > 500:
                value = value[:500]
            
            # Remove null bytes
            value = value.replace('\x00', '')
            
            # Strip whitespace
            value = value.strip()
            
            # Skip empty strings
            if not value:
                continue
            
            # Apply SQL/XSS escaping
            value = self._escape_slot_value(value)
            sanitized[key] = value
        
        elif isinstance(value, bool):
            sanitized[key] = value
        
        elif isinstance(value, int):
            # Validate integer bounds
            if value > MAX_INT or value < MIN_INT:
                value = max(MIN_INT, min(MAX_INT, value))
            sanitized[key] = value
        
        elif isinstance(value, float):
            # Prevent NaN and Infinity
            if math.isnan(value) or math.isinf(value):
                continue
            
            # Validate float bounds
            if value > MAX_FLOAT or value < MIN_FLOAT:
                value = max(MIN_FLOAT, min(MAX_FLOAT, value))
            sanitized[key] = value
        
        elif value is None:
            sanitized[key] = None
        
        else:
            # Convert unknown types to string
            str_value = str(value)[:500]
            str_value = str_value.replace('\x00', '').strip()
            if str_value:
                sanitized[key] = str_value
    
    return sanitized
```

#### SQL/XSS Escaping

**Defense-in-depth escaping for string values:**

```python
def _escape_slot_value(self, value: str) -> str:
    """
    Escape slot value to prevent SQL injection and XSS attacks.
    
    This provides defense-in-depth even though Django ORM
    and templates provide their own protection.
    
    Escaping rules:
    - HTML: Escape <, >, &, ", ' to prevent XSS
    - SQL: Escape single quotes, backslashes
    - Control characters: Remove dangerous control chars
    - SQL comments: Remove --, /*, */
    - Statement terminators: Remove semicolons
    
    Args:
        value: Raw string value from LLM
        
    Returns:
        str: Escaped string safe for database and display
    """
    import html
    import re
    
    # Escape HTML entities to prevent XSS
    value = html.escape(value, quote=True)
    
    # Remove control characters (except tab, newline, carriage return)
    value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', value)
    
    # Escape backslashes and single quotes (SQL injection prevention)
    if '\\' in value:
        value = value.replace('\\', '\\\\')
    if "'" in value:
        value = value.replace("'", "''")
    
    # Remove SQL comment markers
    value = value.replace('--', '')
    value = value.replace('/*', '')
    value = value.replace('*/', '')
    
    # Remove semicolons (statement terminators)
    value = value.replace(';', '')
    
    return value
```

#### Security Features

1. **JSON Schema Validation**
   - Validates structure and types
   - Enforces required fields
   - Rejects unknown properties
   - Limits property counts

2. **Intent Whitelist**
   - Only predefined intents allowed
   - Unknown intents default to 'OTHER'
   - Prevents arbitrary intent injection

3. **Confidence Range Validation**
   - Must be between 0.0 and 1.0
   - Prevents invalid probability values

4. **Slot Key Validation**
   - Only alphanumeric and underscore allowed
   - Prevents special characters in keys
   - Maximum 20 slots per response

5. **Slot Value Sanitization**
   - Length limits (500 chars for strings)
   - Type validation and coercion
   - Numeric bounds checking
   - NaN/Infinity prevention
   - Null byte removal

6. **SQL/XSS Escaping**
   - HTML entity escaping
   - SQL quote escaping
   - Control character removal
   - SQL comment removal
   - Statement terminator removal

7. **Comprehensive Logging**
   - All validation failures logged
   - Sanitization operations tracked
   - Security events sent to Sentry
   - Detailed error context

#### Usage Example

```python
from apps.bot.services.intent_service import IntentService

# Initialize service
service = IntentService()

# Classify intent with automatic validation
result = service.classify_intent(
    message_text="I want to book a haircut for tomorrow",
    conversation_context={'last_intent': 'GREETING'}
)

# Result is validated and sanitized
print(result['intent_name'])      # 'BOOK_APPOINTMENT'
print(result['confidence_score']) # 0.95
print(result['slots'])            # {'service_query': 'haircut', 'date': 'tomorrow'}

# All slots are sanitized and safe to use
for key, value in result['slots'].items():
    # Safe to store in database
    # Safe to display in templates
    # No SQL injection risk
    # No XSS risk
    pass
```

#### Testing LLM Validation

```python
# Test valid response
def test_valid_llm_response():
    service = IntentService()
    result = service.classify_intent("Show me your products")
    assert result['intent_name'] in service.ALL_INTENTS
    assert 0.0 <= result['confidence_score'] <= 1.0

# Test malicious slot values
def test_malicious_slot_sanitization():
    service = IntentService()
    
    # SQL injection attempt
    result = service.classify_intent("'; DROP TABLE products; --")
    slots = result['slots']
    
    # Should be escaped/sanitized
    for value in slots.values():
        if isinstance(value, str):
            assert "DROP TABLE" not in value
            assert "--" not in value

# Test XSS attempt
def test_xss_slot_sanitization():
    service = IntentService()
    result = service.classify_intent("<script>alert('xss')</script>")
    slots = result['slots']
    
    # Should be HTML-escaped
    for value in slots.values():
        if isinstance(value, str):
            assert "<script>" not in value
            assert "&lt;script&gt;" in value or "script" not in value.lower()

# Test invalid JSON
def test_invalid_json_response():
    # Should raise IntentServiceError
    with pytest.raises(IntentServiceError):
        service._validate_intent_response("not json")

# Test unknown intent
def test_unknown_intent_defaults_to_other():
    # Unknown intents should default to 'OTHER'
    result = service.classify_intent("random gibberish")
    assert result['intent_name'] == 'OTHER'
```

#### Monitoring & Alerts

Monitor these metrics for LLM validation:

```python
# Log validation failures
logger.error(
    "LLM response failed schema validation",
    extra={
        'validation_error': str(e),
        'response': response,
        'message_text': message_text[:100]
    }
)

# Alert on Sentry for critical issues
if validation_failures > threshold:
    sentry_sdk.capture_message(
        "High rate of LLM validation failures",
        level='error',
        extras={'failure_rate': failure_rate}
    )
```

#### Best Practices

1. **Always Validate**: Never trust LLM output without validation
2. **Fail Secure**: Reject invalid responses, don't try to fix them
3. **Log Everything**: Track all validation failures for analysis
4. **Defense in Depth**: Multiple layers of validation and sanitization
5. **Test Thoroughly**: Include injection attempts in test suite
6. **Monitor Continuously**: Alert on validation failure spikes
7. **Update Regularly**: Keep validation rules current with threats

#### Future Enhancements

- ⚠️ **Content Filtering**: Detect and block inappropriate content
- ⚠️ **Semantic Validation**: Verify logical consistency of responses
- ⚠️ **Rate Limiting**: Limit LLM API calls per tenant
- ⚠️ **Response Caching**: Cache validated responses for common queries
- ⚠️ **A/B Testing**: Compare validation strategies

### SQL Injection Prevention

```python
# ✅ CORRECT: Use Django ORM (parameterized queries)
products = Product.objects.filter(
    tenant=tenant,
    name__icontains=search_term  # Automatically escaped
)

# ✅ CORRECT: If you must use raw SQL, use parameters
from django.db import connection
cursor = connection.cursor()
cursor.execute(
    "SELECT * FROM products WHERE tenant_id = %s AND name LIKE %s",
    [tenant_id, f"%{search_term}%"]
)

# ❌ WRONG: String concatenation
query = f"SELECT * FROM products WHERE name = '{search_term}'"  # VULNERABLE!
```

---

## Encryption & Key Management

### Encryption Key Requirements

```python
import base64
import secrets

def generate_encryption_key():
    """Generate secure 256-bit encryption key."""
    key = secrets.token_bytes(32)  # 32 bytes = 256 bits
    return base64.b64encode(key).decode('utf-8')

def validate_encryption_key(key_b64):
    """Validate encryption key strength."""
    try:
        key = base64.b64decode(key_b64)
    except Exception:
        raise ValueError("Key must be valid base64")
    
    # Length check
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes (256 bits)")
    
    # Entropy check
    if len(set(key)) < 16:
        raise ValueError("Key has insufficient entropy")
    
    # Weak key check
    if key == b'\x00' * 32:
        raise ValueError("Key is all zeros")
    
    return key
```

### Key Rotation

```python
class EncryptionService:
    """Encryption service with key rotation support."""
    
    def __init__(self):
        # Current key for encryption
        self.current_key = validate_encryption_key(
            settings.ENCRYPTION_KEY
        )
        
        # Old keys for decryption only
        self.old_keys = [
            validate_encryption_key(k)
            for k in settings.ENCRYPTION_OLD_KEYS
        ]
        
        self.cipher = AESGCM(self.current_key)
        self.old_ciphers = [AESGCM(k) for k in self.old_keys]
    
    def encrypt(self, plaintext):
        """Encrypt with current key."""
        # Always use current key
        return self._encrypt_with_cipher(self.cipher, plaintext)
    
    def decrypt(self, ciphertext):
        """Decrypt with current or old keys."""
        # Try current key first
        try:
            return self._decrypt_with_cipher(self.cipher, ciphertext)
        except Exception:
            pass
        
        # Try old keys
        for cipher in self.old_ciphers:
            try:
                return self._decrypt_with_cipher(cipher, ciphertext)
            except Exception:
                continue
        
        raise ValueError("Decryption failed with all keys")
```

### Environment Variable Security

```bash
# .env file (NEVER commit to git!)

# Django Secret (for sessions, CSRF, etc.)
SECRET_KEY=django-insecure-CHANGE-THIS-IN-PRODUCTION-64-chars-minimum

# JWT Secret (MUST be different from SECRET_KEY)
JWT_SECRET_KEY=jwt-secret-CHANGE-THIS-IN-PRODUCTION-64-chars-minimum

# Encryption Key (32 bytes base64-encoded)
ENCRYPTION_KEY=base64-encoded-32-byte-key-here

# Old encryption keys (for rotation)
ENCRYPTION_OLD_KEYS=old-key-1,old-key-2
```

---

## API Security

### Rate Limiting

```python
from django_ratelimit.decorators import ratelimit

class LoginView(APIView):
    """Login endpoint with rate limiting."""
    
    @ratelimit(key='ip', rate='5/m', method='POST')
    @ratelimit(key='post:email', rate='10/h', method='POST')
    def post(self, request):
        # Check if rate limited
        if getattr(request, 'limited', False):
            return Response(
                {
                    'error': 'Too many attempts',
                    'retry_after': 60  # seconds
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Process login...
```

**Rate Limit Guidelines:**
- Login: 5/min per IP, 10/hour per email
- Registration: 3/hour per IP
- Password reset: 3/hour per IP
- API endpoints: 100/hour per user
- Webhook endpoints: 1000/hour per tenant

### CORS Configuration

```python
# config/settings.py

if DEBUG:
    # Development: allow all origins
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # Production: explicit whitelist
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
    
    # Validate configuration
    if not CORS_ALLOWED_ORIGINS:
        raise ValueError("CORS_ALLOWED_ORIGINS required in production")
    
    # Validate HTTPS
    for origin in CORS_ALLOWED_ORIGINS:
        if not origin.startswith('https://'):
            raise ValueError(f"CORS origin must use HTTPS: {origin}")

# CORS settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'x-tenant-id',
    'x-request-id',
]
```

### HTTPS Enforcement

```python
# config/settings.py

if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    
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

## Webhook Security

### Signature Verification

**Status**: ✅ Implemented for Twilio webhooks

All webhook endpoints MUST verify cryptographic signatures to prevent unauthorized access and message injection attacks.

#### Twilio Webhook Signature Verification (HMAC-SHA1)

**Implementation** (apps/integrations/views.py):

```python
import hmac
import hashlib
import base64

def verify_twilio_signature(url, params, signature, auth_token):
    """
    Verify Twilio webhook signature using HMAC-SHA1.
    
    Args:
        url: Full webhook URL (including protocol, domain, path)
        params: POST parameters as dict
        signature: X-Twilio-Signature header value
        auth_token: Twilio Auth Token for the tenant
        
    Returns:
        bool: True if signature is valid, False otherwise
        
    Security Features:
        - HMAC-SHA1 with Auth Token as secret key
        - Constant-time comparison prevents timing attacks
        - Fails securely (returns False on any exception)
        - Logs all verification failures
    """
    try:
        # Step 1: Concatenate URL with sorted POST parameters
        # Format: URL + key1value1 + key2value2 + ...
        sorted_params = sorted(params.items())
        data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
        
        # Step 2: Compute HMAC-SHA1 signature
        computed_signature = hmac.new(
            auth_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Step 3: Base64 encode the computed signature
        computed_signature_b64 = base64.b64encode(computed_signature).decode('utf-8')
        
        # Step 4: Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(computed_signature_b64, signature)
        
        if not is_valid:
            logger.warning(
                "Twilio signature verification failed",
                extra={
                    'url': url,
                    'expected_signature': signature[:10] + '...',
                    'computed_signature': computed_signature_b64[:10] + '...'
                }
            )
        
        return is_valid
        
    except Exception as e:
        logger.error(
            "Error verifying Twilio signature",
            extra={'url': url, 'error': str(e)},
            exc_info=True
        )
        # Fail securely - return False on any exception
        return False


@csrf_exempt
@require_http_methods(["POST"])
def twilio_webhook(request):
    """
    Twilio webhook with signature verification.
    
    Security Features:
    - Signature verification (HMAC-SHA1)
    - Tenant resolution from phone number
    - Security event logging
    - WebhookLog audit trail
    """
    # Parse webhook payload
    payload = dict(request.POST.items())
    
    # Resolve tenant from phone number
    tenant = resolve_tenant_from_twilio(payload)
    if not tenant:
        return HttpResponse('Tenant not found', status=404)
    
    # Verify Twilio signature
    signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
    full_url = request.build_absolute_uri()
    
    # Get Twilio credentials from TenantSettings
    twilio_token = tenant.settings.twilio_token
    
    # Verify signature using the helper function
    if not verify_twilio_signature(full_url, payload, signature, twilio_token):
        # Log as critical security event
        SecurityLogger.log_invalid_webhook_signature(
            provider='twilio',
            tenant_id=str(tenant.id),
            ip_address=request.META.get('REMOTE_ADDR'),
            url=full_url,
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        return HttpResponse('Unauthorized', status=403)
    
    # Process webhook...
```

#### Security Features

1. **HMAC-SHA1 Signature Verification**
   - Uses Twilio Auth Token as secret key
   - Concatenates URL with sorted POST parameters
   - Base64-encoded signature comparison

2. **Constant-Time Comparison**
   - Uses `hmac.compare_digest()` to prevent timing attacks
   - Attackers cannot determine correct signature by measuring response time

3. **Fail-Secure Design**
   - Returns 403 Forbidden on any verification failure
   - Returns False on any exception during verification
   - Never processes webhook without valid signature

4. **Security Event Logging**
   - All failed verifications logged to application logs
   - Critical events sent to Sentry for real-time alerting
   - WebhookLog records all attempts with status='unauthorized'
   - Includes IP address, user agent, and tenant information

5. **Audit Trail**
   - Every webhook attempt logged in WebhookLog model
   - Includes full payload, headers, and processing status
   - Enables forensic analysis of security incidents

#### Testing Signature Verification

```bash
# This should fail with 403 Forbidden (no valid signature)
curl -X POST https://your-domain.com/v1/webhooks/twilio \
  -d "From=whatsapp:+1234567890" \
  -d "To=whatsapp:+14155238886" \
  -d "Body=Test"

# Only requests from Twilio with valid signatures will succeed
```

#### Troubleshooting

If legitimate Twilio webhooks are being rejected:

1. **Verify Auth Token** - Check that Twilio Auth Token in TenantSettings is correct
2. **Check URL** - Webhook URL in Twilio Console must match exactly (including https://)
3. **No Proxy Modification** - Ensure no proxy or CDN is modifying the request
4. **Review Logs** - Check application logs for detailed signature verification errors

#### Future Enhancements

- ⚠️ **WooCommerce**: Implement HMAC-SHA256 signature verification
- ⚠️ **Shopify**: Implement HMAC-SHA256 signature verification
- ⚠️ **Timestamp Validation**: Reject requests older than 5 minutes (replay protection)
- ⚠️ **IP Whitelisting**: Optional restriction to known provider IPs

For complete Twilio webhook setup documentation, see [Twilio Webhook Setup Guide](TWILIO_WEBHOOK_SETUP.md).
```

### Idempotency

```python
def process_webhook(webhook_id, data):
    """Process webhook with idempotency."""
    
    # Check if already processed
    cache_key = f"webhook:processed:{webhook_id}"
    if cache.get(cache_key):
        logger.info(f"Webhook {webhook_id} already processed")
        return
    
    # Process webhook
    try:
        # ... processing logic
        
        # Mark as processed (24 hour TTL)
        cache.set(cache_key, True, 86400)
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise
```

---

## Database Security

### Atomic Operations

```python
from django.db.models import F
from django.db import transaction

# ✅ CORRECT: Atomic counter increment
Conversation.objects.filter(id=conv_id).update(
    low_confidence_count=F('low_confidence_count') + 1
)

# ✅ CORRECT: Transaction for multiple operations
@transaction.atomic
def process_order(order_data):
    # Lock tenant for update
    tenant = Tenant.objects.select_for_update().get(id=tenant_id)
    
    # Create order
    order = Order.objects.create(...)
    
    # Update inventory
    for item in order.items.all():
        item.product.quantity = F('quantity') - item.quantity
        item.product.save()
    
    # All operations commit together or rollback
```

### Prevent Race Conditions

```python
# Cache versioning to prevent race conditions
def resolve_scopes(tenant_user):
    """Resolve scopes with cache versioning."""
    # Get current version
    version = cache.get(f"scope_version:{tenant_user.id}", 0)
    cache_key = f"scopes:{tenant_user.id}:v{version}"
    
    # Try cache
    scopes = cache.get(cache_key)
    if scopes is None:
        # Compute scopes
        scopes = _compute_scopes(tenant_user)
        cache.set(cache_key, scopes, 300)
    
    return scopes

def invalidate_scopes(tenant_user):
    """Invalidate scope cache."""
    # Increment version to invalidate all cached versions
    cache.incr(f"scope_version:{tenant_user.id}", default=0)
```

---

## Logging & Monitoring

### Security Event Logging

```python
import logging
import sentry_sdk

logger = logging.getLogger(__name__)

class SecurityLogger:
    """Centralized security event logging."""
    
    @staticmethod
    def log_failed_login(email, ip_address, user_agent):
        """Log failed login attempt."""
        logger.warning(
            "Failed login attempt",
            extra={
                'event_type': 'failed_login',
                'email': email,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'timestamp': timezone.now().isoformat(),
            }
        )
        
        # Alert on Sentry for monitoring
        sentry_sdk.capture_message(
            f"Failed login: {email} from {ip_address}",
            level='warning'
        )
    
    @staticmethod
    def log_permission_denied(user, tenant, required_scopes, ip_address):
        """Log permission denial."""
        logger.warning(
            "Permission denied",
            extra={
                'event_type': 'permission_denied',
                'user_email': user.email,
                'tenant_id': str(tenant.id),
                'required_scopes': list(required_scopes),
                'ip_address': ip_address,
            }
        )
    
    @staticmethod
    def log_invalid_webhook_signature(tenant, provider, ip_address):
        """Log invalid webhook signature."""
        logger.error(
            "Invalid webhook signature",
            extra={
                'event_type': 'invalid_webhook_signature',
                'tenant_id': str(tenant.id),
                'provider': provider,
                'ip_address': ip_address,
            }
        )
        
        # Critical alert
        sentry_sdk.capture_message(
            f"Invalid webhook signature from {provider}",
            level='error'
        )
```

### Sanitize Logs

```python
import re
import logging

class SanitizingFormatter(logging.Formatter):
    """Formatter that sanitizes sensitive data from logs."""
    
    PATTERNS = [
        (r'sk-[A-Za-z0-9]{48}', 'sk-***REDACTED***'),
        (r'api_key["\']?\s*[:=]\s*["\']?[A-Za-z0-9_-]+', 'api_key=***REDACTED***'),
        (r'password["\']?\s*[:=]\s*["\']?[^"\']+', 'password=***REDACTED***'),
        (r'token["\']?\s*[:=]\s*["\']?[A-Za-z0-9_-]+', 'token=***REDACTED***'),
    ]
    
    def format(self, record):
        """Format log record with sanitization."""
        message = super().format(record)
        
        # Apply all sanitization patterns
        for pattern, replacement in self.PATTERNS:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        
        return message

# Configure in settings.py
LOGGING = {
    'formatters': {
        'sanitizing': {
            '()': 'apps.core.logging.SanitizingFormatter',
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/tulia.log',
            'formatter': 'sanitizing',
        },
    },
}
```

---

## Deployment Security

### Pre-Deployment Checklist

```bash
# 1. Environment Variables
✓ SECRET_KEY set (64+ random characters)
✓ JWT_SECRET_KEY set (different from SECRET_KEY)
✓ ENCRYPTION_KEY set (32 bytes base64)
✓ DEBUG=False
✓ ALLOWED_HOSTS configured
✓ CORS_ALLOWED_ORIGINS configured (HTTPS only)

# 2. Database
✓ Database encryption at rest enabled
✓ Database backups configured
✓ Database credentials rotated
✓ Connection pooling configured

# 3. Security Features
✓ HTTPS enforcement enabled
✓ Secure cookie settings enabled
✓ HSTS headers configured
✓ Rate limiting configured
✓ Webhook signature verification enabled

# 4. Monitoring
✓ Sentry configured
✓ Log aggregation configured
✓ Security alerts configured
✓ Uptime monitoring configured

# 5. Testing
✓ All security tests passing
✓ Penetration testing completed
✓ Load testing completed
✓ Backup restoration tested
```

### Secret Management

```bash
# Generate secure secrets
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate encryption key
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Store in environment (not in code!)
export SECRET_KEY="your-secret-here"
export JWT_SECRET_KEY="your-jwt-secret-here"
export ENCRYPTION_KEY="your-encryption-key-here"
```

---

## Incident Response

### Security Incident Procedure

1. **Detect**: Monitor logs and alerts
2. **Assess**: Determine severity and scope
3. **Contain**: Isolate affected systems
4. **Eradicate**: Remove threat
5. **Recover**: Restore normal operations
6. **Learn**: Post-incident review

### Key Rotation Procedure

```bash
# 1. Generate new key
NEW_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# 2. Add new key as current, move old to ENCRYPTION_OLD_KEYS
ENCRYPTION_KEY=$NEW_KEY
ENCRYPTION_OLD_KEYS=$OLD_KEY

# 3. Deploy with both keys
# 4. Re-encrypt all data with new key (background job)
python manage.py rotate_encryption_keys

# 5. After all data re-encrypted, remove old key
ENCRYPTION_OLD_KEYS=""
```

### Breach Response

If credentials are compromised:

1. **Immediately rotate all secrets**
2. **Invalidate all JWT tokens** (change JWT_SECRET_KEY)
3. **Force password reset** for all users
4. **Review audit logs** for unauthorized access
5. **Notify affected users** (if required by law)
6. **Document incident** for compliance

---

## Summary

### Key Principles

1. **Defense in Depth**: Multiple layers of security
2. **Least Privilege**: Grant minimum necessary permissions
3. **Fail Secure**: Default to deny, not allow
4. **Validate Everything**: Never trust user input
5. **Monitor Continuously**: Log and alert on security events
6. **Update Regularly**: Keep dependencies current
7. **Test Thoroughly**: Security tests in CI/CD
8. **Document Everything**: Security procedures and incidents

### Regular Security Tasks

- **Daily**: Monitor security alerts
- **Weekly**: Review failed login attempts
- **Monthly**: Update dependencies
- **Quarterly**: Security audit and penetration testing
- **Annually**: Disaster recovery drill

---

**For questions or security concerns, contact: security@tulia.ai**

