# Security Remediation - Developer Quick Reference

## What Changed?

### 1. Input Sanitization (NEW)
**Location**: `apps/core/sanitization.py`

Use these utilities for all user inputs:

```python
from apps.core.sanitization import (
    sanitize_html,
    sanitize_text_input,
    sanitize_dict,
    validate_and_sanitize_json_field,
    sanitize_filename
)

# Sanitize HTML to prevent XSS
safe_text = sanitize_html(user_input)

# General text sanitization
safe_text = sanitize_text_input(user_input, max_length=1000)

# Sanitize dictionary fields
safe_data = sanitize_dict(request.data, fields_to_sanitize=['name', 'bio'])

# Validate JSON fields
safe_json = validate_and_sanitize_json_field(json_data, max_depth=5)

# Sanitize filenames
safe_filename = sanitize_filename(uploaded_file.name)
```

### 2. Four-Eyes Validation (BREAKING CHANGE)
**Location**: `apps/rbac/services.py`

**OLD (INSECURE)**:
```python
# This allowed None values - SECURITY ISSUE!
RBACService.validate_four_eyes(initiator=user1, approver=None)
```

**NEW (SECURE)**:
```python
# Both IDs required, validates users exist and are active
RBACService.validate_four_eyes(
    initiator_user_id=user1.id,
    approver_user_id=user2.id
)
```

### 3. Atomic Counter Operations (BREAKING CHANGE)
**Location**: `apps/messaging/models.py`

**OLD (RACE CONDITION)**:
```python
campaign.delivery_count += 1
campaign.save()
```

**NEW (ATOMIC)**:
```python
campaign.increment_delivery()  # Uses F() expression
```

All counter methods now use atomic operations:
- `Conversation.increment_low_confidence()`
- `Conversation.reset_low_confidence()`
- `MessageCampaign.increment_*()` (all 6 metrics)
- `MessageTemplate.increment_usage()`

### 4. Scope Cache (INTERNAL CHANGE)
**Location**: `apps/rbac/services.py`

No API changes, but cache now uses versioning to prevent race conditions.
Cache keys now include version: `scopes:tenant_user:{id}:v{version}`

### 5. Input Length Limits (NEW)
**Location**: `apps/messaging/models.py`

Database now enforces max lengths:
- Message.text: 10,000 chars
- CustomerPreferences.notes: 5,000 chars
- MessageTemplate.content: 5,000 chars
- Campaign message_content: 10,000 chars
- Intent slots: 500 chars (already enforced)

### 6. Rate Limiting (NEW)
**Location**: `apps/rbac/views_auth.py`

Authentication endpoints now rate limited:
- Login: 5/min per IP + 10/hour per email
- Registration: 3/hour per IP
- Email verification: 10/hour per IP
- Password reset: 3/hour per IP, 5/hour per IP

Returns 429 when exceeded.

## Migration Required

Run this migration:
```bash
python manage.py migrate messaging 0008_add_input_length_limits
```

## Testing Your Code

### Test Input Sanitization
```python
from apps.core.sanitization import sanitize_html

def test_sanitizes_user_input(self):
    malicious = '<script>alert("xss")</script>'
    safe = sanitize_html(malicious)
    self.assertNotIn('<script>', safe)
```

### Test Four-Eyes Validation
```python
from apps.rbac.services import RBACService

def test_four_eyes_validation(self):
    # Should pass
    RBACService.validate_four_eyes(user1.id, user2.id)
    
    # Should fail
    with self.assertRaises(ValueError):
        RBACService.validate_four_eyes(user1.id, user1.id)
```

### Test Atomic Counters
```python
def test_atomic_increment(self):
    campaign = MessageCampaign.objects.create(...)
    campaign.increment_delivery()
    campaign.refresh_from_db()
    self.assertEqual(campaign.delivery_count, 1)
```

## Common Pitfalls

### ❌ DON'T: Use += for counters
```python
campaign.delivery_count += 1  # Race condition!
campaign.save()
```

### ✅ DO: Use atomic increment methods
```python
campaign.increment_delivery()  # Atomic!
```

### ❌ DON'T: Trust user input
```python
product.description = request.data['description']  # XSS risk!
```

### ✅ DO: Sanitize user input
```python
from apps.core.sanitization import sanitize_html
product.description = sanitize_html(request.data['description'])
```

### ❌ DON'T: Allow None in four-eyes
```python
RBACService.validate_four_eyes(user1.id, None)  # Raises ValueError!
```

### ✅ DO: Always provide both user IDs
```python
RBACService.validate_four_eyes(
    initiator_user_id=request.user.id,
    approver_user_id=approver.id
)
```

## Pre-Commit Hook

Install the pre-commit hook to prevent committing secrets:
```bash
./scripts/install_git_hooks.sh
```

This will block commits containing:
- API keys
- Passwords
- JWT tokens
- Private keys
- AWS credentials
- And 30+ other secret patterns

## Need Help?

- Full documentation: `.kiro/specs/security-remediation/`
- Implementation summary: `IMPLEMENTATION_SUMMARY.md`
- Tasks tracking: `tasks.md`
- RBAC quick reference: `.kiro/steering/rbac-quick-reference.md`

## Questions?

Common questions:

**Q: Do I need to sanitize all inputs?**
A: Yes, especially user-provided text that will be displayed or stored.

**Q: What if I need to allow some HTML?**
A: Use `sanitize_html(text, allowed_tags=['b', 'i', 'u'])`

**Q: Can I still use the old four-eyes API?**
A: No, it's been removed for security. Update your code.

**Q: Will atomic counters affect performance?**
A: No, F() expressions are actually more efficient than read-modify-write.

**Q: Do I need to run migrations?**
A: Yes, run `python manage.py migrate` to apply length limits.
