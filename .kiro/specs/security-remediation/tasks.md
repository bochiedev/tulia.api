# Security Remediation Tasks

## Phase 1: Critical Security Fixes (Days 1-2)

### Task 1.1: Fix Insecure Password Hashing 🔴
**Priority:** CRITICAL  
**Estimated Time:** 30 minutes  
**Files:** `apps/rbac/services.py`

**Subtasks:**
- [ ] Remove insecure SHA-256 hash line from `register_user()` method
- [ ] Ensure `set_password()` is called before any save
- [ ] Add test to verify PBKDF2 hashing is used
- [ ] Add test to verify password cannot be retrieved
- [ ] Update documentation

**Acceptance Criteria:**
- Password hashing uses Django's `make_password()` (PBKDF2)
- No intermediate insecure hash is created
- Tests verify secure hashing
- Existing users can still log in

---

### Task 1.2: Implement Twilio Webhook Signature Verification 🔴
**Priority:** CRITICAL  
**Estimated Time:** 2 hours  
**Files:** `apps/integrations/views.py`, `apps/integrations/services/twilio_service.py`

**Subtasks:**
- [ ] Add `verify_twilio_signature()` helper function
- [ ] Update `twilio_webhook()` view to verify signatures
- [ ] Update `twilio_status_callback()` view to verify signatures
- [ ] Add logging for failed signature verifications
- [ ] Add security event for invalid signatures
- [ ] Add tests for valid signatures
- [ ] Add tests for invalid signatures
- [ ] Add tests for missing signatures
- [ ] Update webhook setup documentation

**Acceptance Criteria:**
- All Twilio webhooks verify signatures before processing
- Invalid signatures return 403 Forbidden
- Security events logged for invalid signatures
- Tests cover all signature scenarios
- Documentation updated with signature verification

---

### Task 1.3: Validate JWT Secret Key Configuration 🔴
**Priority:** CRITICAL  
**Estimated Time:** 45 minutes  
**Files:** `config/settings.py`, `.env.example`

**Subtasks:**
- [ ] Remove default fallback to SECRET_KEY
- [ ] Add validation for JWT_SECRET_KEY length (>= 32 chars)
- [ ] Add validation that JWT_SECRET_KEY != SECRET_KEY
- [ ] Add entropy check for JWT_SECRET_KEY
- [ ] Update `.env.example` with strong key generation command
- [ ] Add startup validation
- [ ] Update deployment documentation

**Acceptance Criteria:**
- JWT_SECRET_KEY is required (no default)
- Validation ensures key is strong
- Application fails to start with weak key
- Documentation includes key generation instructions

---

### Task 1.4: Add Rate Limiting to Authentication Endpoints 🟠
**Priority:** HIGH  
**Estimated Time:** 2 hours  
**Files:** `apps/rbac/views_auth.py`, `config/settings.py`

**Subtasks:**
- [ ] Add rate limiting to `LoginView` (5/min per IP, 10/hour per email)
- [ ] Add rate limiting to `RegisterView` (3/hour per IP)
- [ ] Add rate limiting to `ForgotPasswordView` (3/hour per IP)
- [ ] Add rate limiting to `ResetPasswordView` (5/hour per IP)
- [ ] Add rate limiting to `VerifyEmailView` (10/hour per IP)
- [ ] Configure Redis for rate limit storage
- [ ] Add custom rate limit exceeded response
- [ ] Add security logging for rate limit violations
- [ ] Add tests for rate limiting
- [ ] Add tests for rate limit reset
- [ ] Update API documentation with rate limits

**Acceptance Criteria:**
- All auth endpoints have rate limiting
- Rate limits use Redis for distributed tracking
- 429 responses include retry-after header
- Security events logged for violations
- Tests verify rate limiting works
- Documentation lists all rate limits

---

### Task 1.5: Remove Hardcoded Secrets from Repository 🟠
**Priority:** HIGH  
**Estimated Time:** 1 hour  
**Files:** Multiple test files, git history

**Subtasks:**
- [ ] Identify all files with hardcoded secrets
- [ ] Delete test files with real credentials
- [ ] Update `.gitignore` to prevent future commits
- [ ] Use BFG Repo-Cleaner to remove from git history
- [ ] Rotate all exposed JWT tokens
- [ ] Rotate all exposed API keys
- [ ] Update CI/CD to use environment variables
- [ ] Add pre-commit hook to detect secrets
- [ ] Document secret management practices

**Acceptance Criteria:**
- No hardcoded secrets in current codebase
- Secrets removed from git history
- All exposed credentials rotated
- Pre-commit hooks prevent future commits
- Documentation updated

---

## Phase 2: Input Validation & Encryption (Days 3-4)

### Task 2.1: Add Input Validation for LLM Responses 🟠
**Priority:** HIGH  
**Estimated Time:** 3 hours  
**Files:** `apps/bot/services/intent_service.py`

**Subtasks:**
- [ ] Create JSON schema for intent responses
- [ ] Add schema validation using `jsonschema` library
- [ ] Add intent name whitelist validation
- [ ] Add confidence score range validation (0.0-1.0)
- [ ] Add slot key validation (alphanumeric + underscore only)
- [ ] Add slot value sanitization (length limits, type checks)
- [ ] Add slot value escaping for SQL/XSS prevention
- [ ] Add logging for validation failures
- [ ] Add tests for valid responses
- [ ] Add tests for malicious responses
- [ ] Add tests for malformed JSON
- [ ] Update documentation

**Acceptance Criteria:**
- All LLM responses validated against schema
- Invalid responses rejected with error
- Slots sanitized before use
- Tests cover injection attempts
- Documentation updated

---

### Task 2.2: Validate Encryption Key Strength 🟠
**Priority:** HIGH  
**Estimated Time:** 2 hours  
**Files:** `apps/core/encryption.py`, `config/settings.py`

**Subtasks:**
- [ ] Add `validate_encryption_key()` function
- [ ] Check key length (must be 32 bytes)
- [ ] Check key entropy (at least 16 unique bytes)
- [ ] Check for weak keys (all zeros, repeating patterns)
- [ ] Add support for key rotation (multiple keys)
- [ ] Update `EncryptionService` to try multiple keys for decryption
- [ ] Add key generation script
- [ ] Add tests for key validation
- [ ] Add tests for key rotation
- [ ] Update documentation

**Acceptance Criteria:**
- Encryption key validated on startup
- Weak keys rejected
- Key rotation supported
- Tests verify validation
- Documentation includes key generation

---

### Task 2.3: Add Input Length Limits 🟡
**Priority:** MEDIUM  
**Estimated Time:** 2 hours  
**Files:** Multiple models and serializers

**Subtasks:**
- [ ] Add max length to `Message.content` (10,000 chars)
- [ ] Add max length to `Customer.notes` (5,000 chars)
- [ ] Add max length to intent slots (500 chars per slot)
- [ ] Add max length to template content (5,000 chars)
- [ ] Add validation in serializers
- [ ] Add database constraints
- [ ] Add tests for length limits
- [ ] Update API documentation

**Acceptance Criteria:**
- All user inputs have length limits
- Validation in both serializers and database
- Tests verify limits enforced
- Documentation updated

---

### Task 2.4: Sanitize All User Inputs 🟡
**Priority:** MEDIUM  
**Estimated Time:** 3 hours  
**Files:** Multiple serializers and views

**Subtasks:**
- [ ] Create `sanitize_html()` utility function
- [ ] Create `sanitize_sql()` utility function
- [ ] Add sanitization to message content
- [ ] Add sanitization to customer notes
- [ ] Add sanitization to product descriptions
- [ ] Add sanitization to template content
- [ ] Add tests for XSS prevention
- [ ] Add tests for SQL injection prevention
- [ ] Update documentation

**Acceptance Criteria:**
- All user inputs sanitized
- XSS attempts blocked
- SQL injection attempts blocked
- Tests verify sanitization
- Documentation updated

---

## Phase 3: Race Conditions & Transactions (Days 5-6)

### Task 3.1: Fix Scope Cache Race Condition 🟡
**Priority:** MEDIUM  
**Estimated Time:** 2 hours  
**Files:** `apps/rbac/services.py`

**Subtasks:**
- [ ] Implement cache versioning for scopes
- [ ] Update `resolve_scopes()` to use versioned cache keys
- [ ] Update `invalidate_scope_cache()` to increment version
- [ ] Add tests for concurrent scope resolution
- [ ] Add tests for cache invalidation during resolution
- [ ] Update documentation

**Acceptance Criteria:**
- Cache versioning prevents race conditions
- Concurrent requests use correct scopes
- Tests verify race condition fixed
- Documentation updated

---

### Task 3.2: Fix Four-Eyes Validation Bypass 🟡
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Files:** `apps/rbac/services.py`

**Subtasks:**
- [ ] Remove optional parameters from `validate_four_eyes()`
- [ ] Make both user IDs required
- [ ] Add validation that both users exist and are active
- [ ] Add validation that users are different
- [ ] Add tests for None values
- [ ] Add tests for same user
- [ ] Add tests for inactive users
- [ ] Update documentation

**Acceptance Criteria:**
- Four-eyes validation cannot be bypassed
- All edge cases handled
- Tests verify validation
- Documentation updated

---

### Task 3.3: Add Atomic Operations for Counters 🟡
**Priority:** MEDIUM  
**Estimated Time:** 2 hours  
**Files:** `apps/bot/models.py`, `apps/bot/services/intent_service.py`

**Subtasks:**
- [ ] Update `increment_low_confidence()` to use F() expressions
- [ ] Update `reset_low_confidence()` to use F() expressions
- [ ] Add atomic increment for message counts
- [ ] Add atomic increment for campaign metrics
- [ ] Add tests for concurrent increments
- [ ] Add tests for race conditions
- [ ] Update documentation

**Acceptance Criteria:**
- All counter operations are atomic
- Concurrent updates don't lose counts
- Tests verify atomicity
- Documentation updated

---

### Task 3.4: Add Transaction Management to Celery Tasks 🟡
**Priority:** MEDIUM  
**Estimated Time:** 3 hours  
**Files:** Multiple `tasks.py` files

**Subtasks:**
- [ ] Add `@transaction.atomic` to `sync_products_task()`
- [ ] Add `@transaction.atomic` to `sync_orders_task()`
- [ ] Add `@transaction.atomic` to `process_scheduled_messages_task()`
- [ ] Add `@transaction.atomic` to `rollup_analytics_task()`
- [ ] Add proper exception handling and retry logic
- [ ] Add tests for transaction rollback
- [ ] Add tests for retry behavior
- [ ] Update documentation

**Acceptance Criteria:**
- All Celery tasks use transactions
- Failed tasks roll back changes
- Retry logic works correctly
- Tests verify rollback
- Documentation updated

---

### Task 3.5: Fix Email Verification Token Expiration 🟡
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Files:** `apps/rbac/services.py`

**Subtasks:**
- [ ] Add token expiration check in `verify_email()`
- [ ] Invalidate expired tokens
- [ ] Clear token after successful verification
- [ ] Add tests for expired tokens
- [ ] Add tests for missing sent_at timestamp
- [ ] Update documentation

**Acceptance Criteria:**
- Expired tokens are rejected
- Tokens cleared after use
- Tests verify expiration
- Documentation updated

---

## Phase 4: Security Hardening (Days 7-8)

### Task 4.1: Enable HTTPS Enforcement 🟡
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Files:** `config/settings.py`

**Subtasks:**
- [ ] Add `SECURE_SSL_REDIRECT = True` for production
- [ ] Add secure cookie settings
- [ ] Add HSTS headers
- [ ] Add security headers (XSS, Content-Type, Frame)
- [ ] Add tests for HTTPS redirect
- [ ] Update deployment documentation

**Acceptance Criteria:**
- HTTPS enforced in production
- Secure cookies enabled
- HSTS headers configured
- Tests verify HTTPS enforcement
- Documentation updated

---

### Task 4.2: Configure Secure CORS 🟡
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Files:** `config/settings.py`, `.env.example`

**Subtasks:**
- [ ] Require explicit CORS origins in production
- [ ] Validate origins are HTTPS
- [ ] Add origin validation on startup
- [ ] Add tests for CORS configuration
- [ ] Update deployment documentation

**Acceptance Criteria:**
- CORS requires explicit origins in production
- Only HTTPS origins allowed
- Tests verify CORS configuration
- Documentation updated

---

### Task 4.3: Add Security Event Logging 🟡
**Priority:** MEDIUM  
**Estimated Time:** 3 hours  
**Files:** `apps/core/security.py` (new), multiple views

**Subtasks:**
- [ ] Create `SecurityLogger` class
- [ ] Add logging for failed login attempts
- [ ] Add logging for permission denials
- [ ] Add logging for rate limit violations
- [ ] Add logging for invalid webhook signatures
- [ ] Add logging for four-eyes violations
- [ ] Configure Sentry for critical events
- [ ] Add tests for security logging
- [ ] Create security monitoring dashboard
- [ ] Update documentation

**Acceptance Criteria:**
- All security events logged
- Critical events sent to Sentry
- Logs include IP, user, timestamp
- Tests verify logging
- Documentation updated

---

### Task 4.4: Add API Key Sanitization in Logs 🟡
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Files:** `apps/core/logging.py`

**Subtasks:**
- [ ] Create `SanitizingFormatter` class
- [ ] Add regex patterns for API keys
- [ ] Add regex patterns for tokens
- [ ] Add regex patterns for passwords
- [ ] Configure formatter in logging settings
- [ ] Add tests for sanitization
- [ ] Update documentation

**Acceptance Criteria:**
- API keys redacted in logs
- Tokens redacted in logs
- Passwords never logged
- Tests verify sanitization
- Documentation updated

---

### Task 4.5: Fix Subscription Status Race Condition 🔵
**Priority:** LOW  
**Estimated Time:** 1 hour  
**Files:** `apps/tenants/middleware.py`, critical views

**Subtasks:**
- [ ] Add `select_for_update()` for critical operations
- [ ] Re-check subscription status in transaction
- [ ] Add tests for concurrent subscription changes
- [ ] Update documentation

**Acceptance Criteria:**
- Subscription status locked during critical operations
- Race condition prevented
- Tests verify locking
- Documentation updated

---

### Task 4.6: Fix OpenAI Client Memory Leak 🔵
**Priority:** LOW  
**Estimated Time:** 1 hour  
**Files:** `apps/bot/services/intent_service.py`

**Subtasks:**
- [ ] Implement singleton pattern for OpenAI client
- [ ] Cache clients by API key
- [ ] Add client cleanup on service shutdown
- [ ] Add tests for client reuse
- [ ] Update documentation

**Acceptance Criteria:**
- OpenAI clients reused
- No memory leak
- Tests verify client reuse
- Documentation updated

---

## Testing & Deployment (Days 9-10)

### Task 5.1: Comprehensive Security Testing
**Estimated Time:** 1 day

**Subtasks:**
- [ ] Run all unit tests
- [ ] Run all integration tests
- [ ] Run security regression tests
- [ ] Perform manual security review
- [ ] Run automated security scanner (bandit, safety)
- [ ] Perform load testing
- [ ] Test race conditions under load
- [ ] Document test results

**Acceptance Criteria:**
- All tests pass
- No security vulnerabilities found
- Performance acceptable
- Test coverage > 90%

---

### Task 5.2: Staging Deployment & Validation
**Estimated Time:** 4 hours

**Subtasks:**
- [ ] Deploy to staging environment
- [ ] Run smoke tests
- [ ] Perform penetration testing
- [ ] Test webhook signature verification
- [ ] Test rate limiting
- [ ] Test authentication flow
- [ ] Monitor for errors
- [ ] Document any issues

**Acceptance Criteria:**
- Staging deployment successful
- All features working
- No critical issues found
- Penetration testing passed

---

### Task 5.3: Production Deployment
**Estimated Time:** 4 hours

**Subtasks:**
- [ ] Create deployment checklist
- [ ] Backup production database
- [ ] Deploy to production
- [ ] Run smoke tests
- [ ] Monitor error rates
- [ ] Monitor performance metrics
- [ ] Monitor security events
- [ ] 48-hour observation period
- [ ] Document deployment

**Acceptance Criteria:**
- Production deployment successful
- No increase in error rates
- Performance within acceptable range
- Security monitoring active
- Documentation complete

---

### Task 5.4: Documentation & Training
**Estimated Time:** 4 hours

**Subtasks:**
- [ ] Update security best practices guide
- [ ] Document incident response procedures
- [ ] Document key rotation procedures
- [ ] Document security monitoring setup
- [ ] Create security training materials
- [ ] Train team on new security features
- [ ] Update API documentation
- [ ] Create security checklist for developers

**Acceptance Criteria:**
- All documentation updated
- Team trained on security features
- Security checklist available
- API documentation current

---

## Summary

**Total Tasks:** 30  
**Estimated Time:** 10 working days  
**Critical Tasks:** 5  
**High Priority Tasks:** 7  
**Medium Priority Tasks:** 16  
**Low Priority Tasks:** 2

**Dependencies:**
- Phase 2 depends on Phase 1 completion
- Phase 3 can run parallel to Phase 2
- Phase 4 depends on Phases 1-3
- Testing depends on all phases

**Risk Mitigation:**
- Comprehensive test coverage
- Staged rollout (dev → staging → production)
- Feature flags for risky changes
- Rollback plan documented
- 48-hour monitoring period
