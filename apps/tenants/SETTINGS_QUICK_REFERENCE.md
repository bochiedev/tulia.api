# TenantSettings Quick Reference

## Always Use TenantSettings (Not Tenant Model)

### ❌ WRONG (Deprecated)
```python
# DON'T DO THIS
service = TwilioService(
    account_sid=tenant.twilio_sid,  # ❌ OLD
    auth_token=tenant.twilio_token,  # ❌ OLD
    from_number=tenant.whatsapp_number
)
```

### ✅ CORRECT (Use TenantSettings)
```python
# DO THIS
service = TwilioService(
    account_sid=tenant.settings.twilio_sid,  # ✅ NEW
    auth_token=tenant.settings.twilio_token,  # ✅ NEW
    from_number=tenant.whatsapp_number
)
```

## Common Patterns

### Check if Integration is Configured
```python
if tenant.settings.has_woocommerce_configured():
    service = create_woo_service_for_tenant(tenant)
    service.sync_products(tenant)
```

### Check Feature Flags
```python
if tenant.settings.is_feature_enabled('ai_responses_enabled'):
    # Use AI responses
    pass
```

### Check Notification Preferences
```python
if tenant.settings.is_notification_enabled('email', 'order_received'):
    # Send email notification
    pass
```

### Update Integration Status
```python
tenant.settings.update_integration_status('woocommerce', {
    'last_sync': timezone.now().isoformat(),
    'product_count': 150,
    'status': 'success'
})
```

## API Usage

### Get Settings
```bash
curl -H "X-TENANT-ID: <uuid>" \
     -H "X-TENANT-API-KEY: <key>" \
     https://api.example.com/v1/tenants/settings
```

### Set WooCommerce Credentials
```bash
curl -X POST \
  -H "X-TENANT-ID: <uuid>" \
  -H "X-TENANT-API-KEY: <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "store_url": "https://mystore.com",
    "consumer_key": "ck_...",
    "consumer_secret": "cs_...",
    "test_connection": true
  }' \
  https://api.example.com/v1/tenants/settings/integrations/woocommerce
```

## Migration

### Run Data Migration
```bash
# Dry run first
python manage.py migrate_tenant_credentials --dry-run

# Actual migration
python manage.py migrate_tenant_credentials
```

## Testing

### Run Tests
```bash
# Unit tests
python -m pytest apps/tenants/tests/test_tenant_settings.py -v

# Integration tests
python -m pytest apps/tenants/tests/test_settings_integration.py -v
```

## Files to Reference

- **Design**: `apps/tenants/TENANT_SETTINGS_DESIGN.md`
- **Migration**: `apps/tenants/MIGRATION_GUIDE.md`
- **Complete Summary**: `.kiro/notes/TENANT_SETTINGS_COMPLETE.md`
