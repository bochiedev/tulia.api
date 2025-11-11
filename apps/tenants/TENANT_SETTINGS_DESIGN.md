# TenantSettings Model Design

## Overview
Centralized, secure storage for all tenant-specific configuration including credentials, integrations, payment methods, and preferences.

## Security Requirements

### 1. Encryption Strategy
- **Sensitive fields**: Use `EncryptedCharField` or `EncryptedTextField` for:
  - API keys, tokens, secrets
  - Payment card tokens (never store raw card numbers)
  - OAuth credentials
- **Non-sensitive fields**: Use regular JSONField for preferences
- **Encryption at rest**: Django field-level encryption (already implemented in `core.fields`)
- **Encryption in transit**: HTTPS only (enforce in production)

### 2. PCI-DSS Compliance (Payment Cards)
- **NEVER store**: Full card numbers, CVV, PIN
- **DO store**: Tokenized card references from payment processor (Stripe/PayPal)
- **Pattern**: Store `payment_method_id` from Stripe, not actual card data
- **Audit**: Log all access to payment methods

### 3. Access Control
- **RBAC integration**: Only users with `integrations:manage` or `finance:manage` scopes
- **Audit logging**: Track all reads/writes to sensitive settings
- **Rate limiting**: Prevent brute force on credential endpoints

## Model Structure

```python
class TenantSettings(BaseModel):
    """
    Secure storage for tenant configuration and credentials.
    
    Separates concerns:
    - Integration credentials (encrypted)
    - Payment methods (tokenized references)
    - Notification preferences (plain JSON)
    - Feature flags (plain JSON)
    """
    
    tenant = OneToOneField(Tenant, primary_key=True)
    
    # === INTEGRATION CREDENTIALS (Encrypted) ===
    
    # Twilio (moved from Tenant model)
    twilio_sid = EncryptedCharField(max_length=500, null=True, blank=True)
    twilio_token = EncryptedCharField(max_length=500, null=True, blank=True)
    twilio_webhook_secret = EncryptedCharField(max_length=500, null=True, blank=True)
    
    # WooCommerce
    woo_store_url = models.URLField(null=True, blank=True)
    woo_consumer_key = EncryptedCharField(max_length=500, null=True, blank=True)
    woo_consumer_secret = EncryptedCharField(max_length=500, null=True, blank=True)
    woo_webhook_secret = EncryptedCharField(max_length=500, null=True, blank=True)
    
    # Shopify
    shopify_shop_domain = models.CharField(max_length=255, null=True, blank=True)
    shopify_access_token = EncryptedCharField(max_length=500, null=True, blank=True)
    shopify_webhook_secret = EncryptedCharField(max_length=500, null=True, blank=True)
    
    # WhatsApp Business API (if different from Twilio)
    whatsapp_business_id = EncryptedCharField(max_length=500, null=True, blank=True)
    whatsapp_access_token = EncryptedCharField(max_length=500, null=True, blank=True)
    
    # OpenAI / LLM
    openai_api_key = EncryptedCharField(max_length=500, null=True, blank=True)
    openai_org_id = EncryptedCharField(max_length=500, null=True, blank=True)
    
    # === PAYMENT METHODS (Tokenized) ===
    
    # Stripe payment method IDs (NOT raw card data)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_payment_methods = models.JSONField(
        default=list,
        help_text="List of Stripe PaymentMethod IDs: [{id, last4, brand, exp_month, exp_year, is_default}]"
    )
    
    # Payout account (for tenant earnings)
    payout_method = models.CharField(
        max_length=50,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('mobile_money', 'Mobile Money'),
            ('paypal', 'PayPal'),
        ],
        null=True,
        blank=True
    )
    payout_details = EncryptedTextField(
        null=True,
        blank=True,
        help_text="Encrypted JSON with account details"
    )
    
    # === NOTIFICATION PREFERENCES (Plain JSON) ===
    
    notification_settings = models.JSONField(
        default=dict,
        help_text="""
        {
            "email": {
                "order_received": true,
                "low_stock": true,
                "daily_summary": true,
                "weekly_report": false
            },
            "sms": {
                "critical_alerts": true,
                "payment_failed": true
            },
            "in_app": {
                "new_message": true,
                "handoff_request": true
            },
            "quiet_hours": {
                "enabled": true,
                "start": "22:00",
                "end": "08:00",
                "timezone": "Africa/Nairobi"
            }
        }
        """
    )
    
    # === FEATURE FLAGS & PREFERENCES ===
    
    feature_flags = models.JSONField(
        default=dict,
        help_text="""
        {
            "ai_responses_enabled": true,
            "auto_handoff_enabled": false,
            "product_recommendations": true,
            "appointment_reminders": true,
            "abandoned_cart_recovery": false,
            "multi_language_support": false
        }
        """
    )
    
    business_hours = models.JSONField(
        default=dict,
        help_text="""
        {
            "monday": {"open": "09:00", "close": "17:00", "closed": false},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": false},
            ...
            "sunday": {"closed": true}
        }
        """
    )
    
    # === INTEGRATION STATUS ===
    
    integrations_status = models.JSONField(
        default=dict,
        help_text="""
        {
            "woocommerce": {
                "enabled": true,
                "last_sync": "2024-01-15T10:30:00Z",
                "sync_status": "success",
                "product_count": 150
            },
            "shopify": {
                "enabled": false
            }
        }
        """
    )
    
    # === BRANDING & CUSTOMIZATION ===
    
    branding = models.JSONField(
        default=dict,
        help_text="""
        {
            "business_name": "Acme Store",
            "logo_url": "https://...",
            "primary_color": "#007bff",
            "welcome_message": "Hi! Welcome to Acme Store...",
            "footer_text": "Powered by Acme"
        }
        """
    )
    
    # === COMPLIANCE & LEGAL ===
    
    compliance_settings = models.JSONField(
        default=dict,
        help_text="""
        {
            "gdpr_enabled": true,
            "data_retention_days": 365,
            "consent_required": true,
            "privacy_policy_url": "https://...",
            "terms_url": "https://..."
        }
        """
    )
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"
    
    # === HELPER METHODS ===
    
    def has_woocommerce_configured(self) -> bool:
        """Check if WooCommerce credentials are set."""
        return bool(
            self.woo_store_url and 
            self.woo_consumer_key and 
            self.woo_consumer_secret
        )
    
    def has_shopify_configured(self) -> bool:
        """Check if Shopify credentials are set."""
        return bool(
            self.shopify_shop_domain and 
            self.shopify_access_token
        )
    
    def get_default_payment_method(self):
        """Get default Stripe payment method."""
        for pm in self.stripe_payment_methods:
            if pm.get('is_default'):
                return pm
        return self.stripe_payment_methods[0] if self.stripe_payment_methods else None
    
    def is_notification_enabled(self, channel: str, event: str) -> bool:
        """Check if notification is enabled for channel and event."""
        return self.notification_settings.get(channel, {}).get(event, False)
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if feature flag is enabled."""
        return self.feature_flags.get(feature, False)
```

## Migration Strategy

### Phase 1: Create TenantSettings model
- Add model with all fields
- Create migration
- Add signal to auto-create settings for new tenants

### Phase 2: Migrate existing data
- Copy Twilio credentials from Tenant to TenantSettings
- Migrate any existing metadata to appropriate fields

### Phase 3: Update service factories
- Update `create_woo_service_for_tenant()` to use TenantSettings
- Update `create_shopify_service_for_tenant()` to use TenantSettings
- Update `create_twilio_service_for_tenant()` to use TenantSettings

### Phase 4: Deprecate old fields
- Mark Tenant.twilio_* fields as deprecated
- Remove in future version

## API Endpoints

```python
# GET /v1/tenants/settings
# Required scope: integrations:manage OR tenant:admin
# Returns: Non-sensitive settings only (no credentials)

# PATCH /v1/tenants/settings
# Required scope: integrations:manage
# Updates: Specific setting groups

# POST /v1/tenants/settings/integrations/woocommerce
# Required scope: integrations:manage
# Sets: WooCommerce credentials (encrypted)

# POST /v1/tenants/settings/integrations/woocommerce/test
# Required scope: integrations:manage
# Tests: Connection with provided credentials

# GET /v1/tenants/settings/payment-methods
# Required scope: finance:view
# Returns: List of payment methods (tokenized, no sensitive data)

# POST /v1/tenants/settings/payment-methods
# Required scope: finance:manage
# Creates: New payment method via Stripe (returns token)
```

## Security Best Practices

### 1. Never Return Encrypted Values
```python
class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSettings
        exclude = [
            'twilio_token', 'woo_consumer_secret', 
            'shopify_access_token', 'openai_api_key',
            'payout_details'
        ]
    
    # Only return masked versions
    woo_consumer_key_masked = serializers.SerializerMethodField()
    
    def get_woo_consumer_key_masked(self, obj):
        if obj.woo_consumer_key:
            return f"ck_****{obj.woo_consumer_key[-4:]}"
        return None
```

### 2. Audit All Access
```python
@audit_log(action='settings.credentials.read')
def get_settings(request):
    # Log who accessed credentials
    pass
```

### 3. Separate Write Permissions
```python
# Reading settings: integrations:view
# Writing credentials: integrations:manage
# Payment methods: finance:manage
```

### 4. Validate on Write
```python
def set_woocommerce_credentials(self, store_url, key, secret):
    # Test connection before saving
    service = WooService(store_url, key, secret)
    try:
        service.fetch_products_batch(page=1, per_page=1)
    except WooServiceError:
        raise ValidationError("Invalid WooCommerce credentials")
    
    # Save if valid
    self.woo_store_url = store_url
    self.woo_consumer_key = key
    self.woo_consumer_secret = secret
    self.save()
```

## Payment Card Handling (PCI-DSS)

### Stripe Integration Pattern
```python
# Frontend: Use Stripe.js to tokenize card
# Never send raw card data to your backend

# Backend: Store only the token
def add_payment_method(tenant_settings, stripe_payment_method_id):
    # Verify with Stripe
    pm = stripe.PaymentMethod.retrieve(stripe_payment_method_id)
    
    # Store only non-sensitive metadata
    tenant_settings.stripe_payment_methods.append({
        'id': pm.id,  # Token, not card number
        'last4': pm.card.last4,
        'brand': pm.card.brand,
        'exp_month': pm.card.exp_month,
        'exp_year': pm.card.exp_year,
        'is_default': len(tenant_settings.stripe_payment_methods) == 0
    })
    tenant_settings.save()
```

## Additional Settings to Consider

1. **Rate Limiting**: Per-tenant API rate limits
2. **Webhooks**: Custom webhook URLs for events
3. **Localization**: Default language, currency, date format
4. **Analytics**: Data retention, anonymization preferences
5. **AI/Bot**: Response tone, fallback behavior, confidence thresholds
6. **Catalog**: Auto-sync schedule, price rounding rules
7. **Orders**: Auto-confirm, payment grace period
8. **Messaging**: Template library, quick replies
9. **Appointments**: Buffer time, cancellation policy
10. **Integrations**: Sync frequency, error notification thresholds

## Testing Requirements

- Test encryption/decryption of all sensitive fields
- Test credential validation before saving
- Test RBAC enforcement on settings endpoints
- Test audit logging for credential access
- Test payment method tokenization flow
- Test settings migration from Tenant model
