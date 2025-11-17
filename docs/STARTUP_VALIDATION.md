# Startup Security Validation

## Overview

Tulia AI implements comprehensive startup validation to ensure critical security configurations are properly set before the application starts. This fail-fast approach prevents deployment with insecure settings.

## Validation Process

The application performs validation during Django's initialization phase, before any requests are processed. If validation fails, the application **will not start** and will display a clear error message indicating what needs to be fixed.

## Validated Security Settings

### 1. JWT Secret Key Validation

**Environment Variable**: `JWT_SECRET_KEY`

**Requirements**:
- Must be explicitly set (no default fallback to SECRET_KEY)
- Minimum length: 32 characters
- Must be different from SECRET_KEY
- Must have high entropy (at least 16 unique characters)
- Cannot be simple repeating patterns (e.g., "aaaaaaa..." or "123123123...")

**Why This Matters**:
- JWT tokens are used for tenant authentication in the self-service onboarding flow
- A weak JWT secret key allows attackers to forge authentication tokens
- Using the same key for both Django sessions and JWT tokens creates a single point of failure
- Insufficient entropy makes keys vulnerable to brute-force attacks

**Validation Code Location**: `config/settings.py` (lines 640-701)

**Example Validation Errors**:

```python
# Error: Key not set
django.core.exceptions.ImproperlyConfigured: Set the JWT_SECRET_KEY environment variable

# Error: Key too short
django.core.exceptions.ImproperlyConfigured: JWT_SECRET_KEY must be at least 32 characters long for security.
Current length: 20. Generate a strong key with: python -c "import secrets; print(secrets.token_urlsafe(32))"

# Error: Same as SECRET_KEY
django.core.exceptions.ImproperlyConfigured: JWT_SECRET_KEY must be different from SECRET_KEY for security.
Using the same key for both purposes weakens security. Generate a separate JWT key with: python -c "import secrets; print(secrets.token_urlsafe(32))"

# Error: Insufficient entropy
django.core.exceptions.ImproperlyConfigured: JWT_SECRET_KEY has insufficient entropy.
Found only 8 unique characters, need at least 16. Generate a strong key with: python -c "import secrets; print(secrets.token_urlsafe(32))"

# Error: Repeating pattern
django.core.exceptions.ImproperlyConfigured: JWT_SECRET_KEY is a repeating character pattern.
Generate a strong key with: python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Encryption Key Validation

**Environment Variable**: `ENCRYPTION_KEY`

**Requirements**:
- Must be exactly 32 bytes (base64-encoded)
- Must be valid base64 format

**Why This Matters**:
- Used for AES-256 encryption of PII data (phone numbers, customer data)
- Invalid key format will cause encryption/decryption failures
- Changing the key makes existing encrypted data unreadable

## Generating Secure Keys

### Automated Key Generation (Recommended)

Use the provided script to generate all required keys at once:

```bash
python scripts/generate_secrets.py
```

This script generates:
- `SECRET_KEY` (50 characters, high entropy)
- `JWT_SECRET_KEY` (50 characters, high entropy, different from SECRET_KEY)
- `ENCRYPTION_KEY` (32 bytes, base64-encoded)

### Manual Key Generation

Generate individual keys using these commands:

```bash
# SECRET_KEY (50+ characters recommended)
python -c "import secrets; print(secrets.token_urlsafe(50))"

# JWT_SECRET_KEY (32+ characters required, must differ from SECRET_KEY)
python -c "import secrets; print(secrets.token_urlsafe(50))"

# ENCRYPTION_KEY (32 bytes, base64-encoded)
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode('utf-8'))"
```

**Alternative methods**:

```bash
# Using openssl
openssl rand -base64 50  # For SECRET_KEY or JWT_SECRET_KEY
openssl rand -base64 32  # For ENCRYPTION_KEY

# Using Python secrets module (Python 3.6+)
python -c "import secrets; print(secrets.token_hex(32))"
```

## Configuration Examples

### Development Environment

```bash
# .env file for development
SECRET_KEY=dev-secret-key-at-least-50-chars-high-entropy-random-string
JWT_SECRET_KEY=dev-jwt-secret-key-at-least-32-chars-different-from-secret
ENCRYPTION_KEY=dev-base64-encoded-32-byte-encryption-key-here==
```

### Production Environment

```bash
# .env file for production (NEVER commit to version control)
SECRET_KEY=prod-secret-key-at-least-50-chars-high-entropy-random-string-unique
JWT_SECRET_KEY=prod-jwt-secret-key-at-least-32-chars-different-from-secret-unique
ENCRYPTION_KEY=prod-base64-encoded-32-byte-encryption-key-here==
```

**Production Best Practices**:
1. Generate unique keys for each environment (dev, staging, production)
2. Store keys in secrets management systems (AWS Secrets Manager, HashiCorp Vault, etc.)
3. Never commit keys to version control
4. Rotate keys regularly (every 90 days)
5. Use different keys for different environments

## Testing Validation

### Test Startup Validation

You can test the validation by intentionally using weak keys:

```bash
# Test 1: Key too short
export JWT_SECRET_KEY="short"
python manage.py check
# Expected: ImproperlyConfigured error about key length

# Test 2: Same as SECRET_KEY
export SECRET_KEY="my-secret-key"
export JWT_SECRET_KEY="my-secret-key"
python manage.py check
# Expected: ImproperlyConfigured error about keys being the same

# Test 3: Low entropy
export JWT_SECRET_KEY="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
python manage.py check
# Expected: ImproperlyConfigured error about insufficient entropy
```

### Verify Correct Configuration

```bash
# Generate proper keys
python scripts/generate_secrets.py

# Copy the generated keys to your .env file

# Verify the application starts successfully
python manage.py check
# Expected: System check identified no issues (0 silenced).

# Start the development server
python manage.py runserver
# Expected: Server starts without errors
```

## Deployment Checklist

Before deploying to any environment:

- [ ] Generate unique keys using `python scripts/generate_secrets.py`
- [ ] Set `SECRET_KEY` (at least 50 characters)
- [ ] Set `JWT_SECRET_KEY` (at least 32 characters, different from SECRET_KEY)
- [ ] Set `ENCRYPTION_KEY` (32 bytes, base64-encoded)
- [ ] Verify keys are different across environments
- [ ] Store keys securely (secrets management system)
- [ ] Test startup with `python manage.py check`
- [ ] Verify application starts successfully
- [ ] Document key rotation schedule

## Troubleshooting

### Application Won't Start

**Symptom**: Application fails to start with `ImproperlyConfigured` error

**Solution**:
1. Read the error message carefully - it tells you exactly what's wrong
2. Follow the command provided in the error message to generate a proper key
3. Update your `.env` file with the new key
4. Restart the application

### Keys Not Being Read

**Symptom**: Error says key is not set, but it's in `.env` file

**Solution**:
1. Verify `.env` file is in the project root directory
2. Check for typos in variable names
3. Ensure no extra spaces around the `=` sign
4. Restart the application after changing `.env`
5. For Docker: rebuild the container with `docker-compose up --build`

### Key Rotation

**Symptom**: Need to rotate keys without breaking existing sessions/tokens

**Solution**:
1. **For SECRET_KEY**: Plan for user re-authentication
2. **For JWT_SECRET_KEY**: All existing JWT tokens will be invalidated
3. **For ENCRYPTION_KEY**: Use `ENCRYPTION_OLD_KEYS` for gradual rotation
4. Schedule rotation during maintenance window
5. Notify users of required re-authentication

## Security Impact

### What Happens Without Validation?

Without startup validation, the following security issues could occur:

1. **Weak JWT Keys**: Attackers could forge authentication tokens
2. **Shared Keys**: Single point of failure if one key is compromised
3. **Low Entropy**: Keys vulnerable to brute-force attacks
4. **Production Deployment with Dev Keys**: Insecure production environment

### Defense in Depth

Startup validation is part of a defense-in-depth security strategy:

1. **Startup Validation**: Prevents weak configurations (this document)
2. **Rate Limiting**: Prevents brute-force attacks
3. **Webhook Signature Verification**: Prevents message injection
4. **RBAC**: Prevents unauthorized access
5. **Encryption**: Protects data at rest
6. **HTTPS**: Protects data in transit
7. **Security Monitoring**: Detects and alerts on security events

## Additional Resources

- **Environment Variables Reference**: `docs/ENVIRONMENT_VARIABLES.md`
- **Deployment Guide**: `docs/DEPLOYMENT.md`
- **Security Best Practices**: `docs/SECURITY_BEST_PRACTICES.md`
- **Key Generation Script**: `scripts/generate_secrets.py`

## Related Security Features

- **Webhook Signature Verification**: `docs/TWILIO_WEBHOOK_SETUP.md`
- **Rate Limiting**: `docs/SECURITY_BEST_PRACTICES.md`
- **RBAC**: `.kiro/steering/rbac-enforcement-checklist.md`
- **Encryption**: `apps/core/encryption.py`

---

**Last Updated**: 2025-01-17
**Version**: 1.0.0
**Security Audit**: Task 1.3 - JWT Secret Key Validation
