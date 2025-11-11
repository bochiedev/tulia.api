# TenantSettings Migration Guide

## Problem: Code Duplication (DRY Violation)

Currently, credentials and settings are duplicated across two models:

### Tenant Model (OLD - Deprecated)
- `twilio_sid`
- `twilio_token`
- `webhook_secret`
- `api_keys`

### TenantSettings Model (NEW - Preferred)
- `twilio_sid`
- `twilio_token`
- `twilio_webhook_secret`
- Plus: WooCommerce, Shopify, OpenAI, payment methods, etc.

## Migration Strategy

### Phase 1: Data Migration (REQUIRED)
Migrate existing Tenant credentials to TenantSettings.

```python
# Run this management command
python manage.py migrate_tenant_credentials
```

### Phase 2: Update All Code References
All code should use `tenant.settings.*` instead of `tenant.*`

**Before (OLD):**
```python
service = TwilioService(
    account_sid=tenant.twilio_sid,
    auth_token=tenant.twilio_token,
    from_number=tenant.whatsapp_number
)
```

**After (NEW):**
```python
service = TwilioService(
    account_sid=tenant.settings.twilio_sid,
    auth_token=tenant.settings.twilio_token,
    from_number=tenant.whatsapp_number
)
```

### Phase 3: Deprecate Old Fields
Mark Tenant model fields as deprecated (add warnings).

### Phase 4: Remove Old Fields
After all code is migrated, remove deprecated fields from Tenant model.

## Current Status

### ✅ Completed
- TenantSettings model created
- Auto-creation signal for new tenants
- API endpoints for managing settings
- Integration service factories updated (with fallback)
- Basic tests written

### ⚠️ TODO - Critical
1. **Data Migration Command** - Migrate existing credentials
2. **Comprehensive Tests** - Integration tests with all modules
3. **Update All References** - Search codebase for `tenant.twilio_*`, `tenant.api_keys`
4. **Deprecation Warnings** - Add warnings to old Tenant fields
5. **Documentation** - Update all docs to use TenantSettings

## Files That Need Updates

### Models & Services
- ✅ `apps/integrations/services/twilio_service.py` - Has fallback
- ✅ `apps/integrations/services/woo_service.py` - Uses TenantSettings
- ✅ `apps/integrations/services/shopify_service.py` - Uses TenantSettings
- ⚠️ `apps/integrations/views.py` - May reference tenant.twilio_*
- ⚠️ `apps/messaging/services/messaging_service.py` - Check for direct access
- ⚠️ `apps/bot/services/*.py` - Check for credential access

### Tests
- ⚠️ All test files that create tenants with credentials
- ⚠️ Integration tests between modules

### Admin & Management
- ⚠️ `apps/tenants/admin.py` - Update to show deprecation warnings
- ⚠️ Management commands that access credentials

## Testing Checklist

### Unit Tests
- [x] TenantSettings model methods
- [x] Helper methods (has_*_configured)
- [x] Integration service factories
- [ ] Credential encryption/decryption
- [ ] Signal auto-creation

### Integration Tests
- [ ] Twilio service with TenantSettings
- [ ] WooCommerce sync with TenantSettings
- [ ] Shopify sync with TenantSettings
- [ ] Message sending with TenantSettings credentials
- [ ] Webhook verification with TenantSettings secrets
- [ ] API key authentication with TenantSettings

### End-to-End Tests
- [ ] Create tenant → Settings auto-created
- [ ] Set WooCommerce credentials → Sync products
- [ ] Set Twilio credentials → Send message
- [ ] Update notification settings → Receive notifications
- [ ] Enable feature flag → Feature works

## API Keys Migration

### Current (Tenant model)
```python
tenant.api_keys = [
    {'key_hash': 'hash1', 'name': 'API Key 1', 'created_at': '...'},
    {'key_hash': 'hash2', 'name': 'API Key 2', 'created_at': '...'}
]
```

### Proposed (Keep in Tenant for now)
API keys are tenant-level authentication, not integration settings.
**Decision:** Keep `api_keys` in Tenant model (not duplication).

## Backward Compatibility

### Twilio Service (Current Implementation)
```python
def create_twilio_service_for_tenant(tenant):
    # Try TenantSettings first
    try:
        settings = tenant.settings
        if settings.has_twilio_configured():
            return TwilioService(
                account_sid=settings.twilio_sid,
                auth_token=settings.twilio_token,
                from_number=tenant.whatsapp_number
            )
    except AttributeError:
        pass
    
    # Fallback to Tenant model (backward compatibility)
    return TwilioService(
        account_sid=tenant.twilio_sid,
        auth_token=tenant.twilio_token,
        from_number=tenant.whatsapp_number
    )
```

This ensures no breaking changes during migration.

## Deprecation Timeline

### Week 1-2: Migration & Testing
- Create data migration command
- Run migration on all environments
- Write comprehensive tests
- Update all code references

### Week 3-4: Deprecation Warnings
- Add deprecation warnings to Tenant model fields
- Update documentation
- Notify team of changes

### Week 5+: Cleanup
- Remove deprecated fields from Tenant model
- Remove fallback code from services
- Final testing

## Commands to Run

```bash
# 1. Create migration command
python manage.py create_migration_command

# 2. Run data migration
python manage.py migrate_tenant_credentials --dry-run
python manage.py migrate_tenant_credentials

# 3. Verify migration
python manage.py verify_tenant_settings

# 4. Run all tests
python -m pytest apps/tenants/tests/test_tenant_settings.py -v
python -m pytest apps/integrations/tests/ -v
python -m pytest apps/messaging/tests/ -v

# 5. Check for old references
grep -r "tenant\.twilio_" apps/
grep -r "tenant\.webhook_secret" apps/
```

## Next Steps

1. **Create data migration command** (Priority: HIGH)
2. **Write comprehensive integration tests** (Priority: HIGH)
3. **Search and update all code references** (Priority: MEDIUM)
4. **Add deprecation warnings** (Priority: MEDIUM)
5. **Update steering document** (Priority: LOW)
