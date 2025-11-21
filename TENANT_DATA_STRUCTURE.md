# Tenant Data Structure - Complete Reference

**Purpose**: Understanding tenant configuration, settings, and business data

---

## Table of Contents

1. [Tenant Model](#tenant-model)
2. [Tenant Settings](#tenant-settings)
3. [Subscription & Billing](#subscription--billing)
4. [Integration Credentials](#integration-credentials)
5. [Agent Configuration](#agent-configuration)
6. [Business Data](#business-data)
7. [Analytics & Metrics](#analytics--metrics)
8. [API Access](#api-access)

---

## 1. Tenant Model

### Core Tenant Information

```json
{
  "id": "uuid",
  "name": "Acme Electronics",
  "slug": "acme-electronics",
  "status": "active",  // active, trial, trial_expired, suspended, canceled
  
  // WhatsApp Configuration
  "whatsapp_number": "+254712345678",
  
  // Subscription
  "subscription_tier_id": "uuid",
  "subscription_waived": false,
  "trial_start_date": "2025-11-01T00:00:00Z",
  "trial_end_date": "2025-11-15T00:00:00Z",
  
  // Settings
  "timezone": "Africa/Nairobi",
  "quiet_hours_start": "22:00:00",
  "quiet_hours_end": "08:00:00",
  
  // Contact
  "contact_email": "admin@acme.com",
  "contact_phone": "+254712345678",
  
  // API Access
  "api_keys": [
    {
      "key_hash": "sha256_hash",
      "name": "Production API Key",
      "created_at": "2025-11-01T10:00:00Z",
      "last_used_at": "2025-11-20T15:30:00Z"
    }
  ],
  "allowed_origins": [
    "https://dashboard.acme.com",
    "https://app.acme.com"
  ],
  
  // Encrypted Credentials (stored encrypted)
  "twilio_sid": "AC...",  // Encrypted
  "twilio_token": "...",  // Encrypted
  "webhook_secret": "...",  // Encrypted
  
  // Timestamps
  "created_at": "2025-11-01T00:00:00Z",
  "updated_at": "2025-11-20T10:30:00Z",
  "deleted_at": null
}
```

### Tenant Status States

```
trial → active → suspended → canceled
  ↓       ↓
trial_expired
```

**Status Descriptions:**
- `trial`: Free trial period (14 days default)
- `active`: Paid subscription active
- `trial_expired`: Trial ended, awaiting payment
- `suspended`: Payment failed or policy violation
- `canceled`: Subscription canceled by tenant

---

## 2. Tenant Settings

### TenantSettings Model

**Purpose**: Stores all tenant-specific configuration and preferences

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // === LLM CONFIGURATION ===
  "llm_provider": "openai",  // openai, gemini, together
  "llm_model": "gpt-4o",
  "llm_temperature": 0.7,
  "llm_max_tokens": 1000,
  "llm_timeout": 60.0,
  "llm_max_retries": 3,
  
  // LLM API Keys (Encrypted)
  "openai_api_key": "sk-...",  // Encrypted
  "gemini_api_key": "AIza...",  // Encrypted
  "together_api_key": "...",  // Encrypted
  "anthropic_api_key": "...",  // Encrypted
  
  // === AI AGENT CONFIGURATION ===
  "ai_agent_enabled": true,
  "confidence_threshold": 0.7,
  "max_response_length": 500,
  "enable_spelling_correction": true,
  "enable_context_summarization": true,
  "enable_key_fact_extraction": true,
  
  // === RAG CONFIGURATION ===
  "enable_document_retrieval": true,
  "enable_database_retrieval": true,
  "enable_internet_enrichment": false,
  "enable_source_attribution": true,
  "enable_grounded_validation": true,
  "rag_top_k_results": 5,
  "rag_semantic_weight": 0.7,
  "rag_keyword_weight": 0.3,
  
  // === MESSAGE HARMONIZATION ===
  "enable_message_harmonization": true,
  "harmonization_wait_seconds": 3,
  
  // === LANGUAGE SETTINGS ===
  "enable_language_consistency": true,
  "default_language": "en",
  "supported_languages": ["en", "sw", "sheng"],
  
  // === RICH MESSAGES ===
  "enable_rich_messages": true,
  "enable_product_cards": true,
  "enable_service_cards": true,
  "enable_button_messages": true,
  "enable_list_messages": true,
  
  // === HANDOFF SETTINGS ===
  "enable_progressive_handoff": true,
  "max_clarification_attempts": 3,
  "handoff_on_low_confidence": true,
  "handoff_confidence_threshold": 0.5,
  
  // === FEEDBACK COLLECTION ===
  "enable_feedback_collection": true,
  "feedback_prompt_frequency": 5,  // Every 5 interactions
  
  // === INTEGRATION CREDENTIALS (Encrypted) ===
  // Twilio
  "twilio_sid": "AC...",  // Encrypted
  "twilio_token": "...",  // Encrypted
  "twilio_whatsapp_number": "+254712345678",
  
  // WooCommerce
  "woo_store_url": "https://store.acme.com",
  "woo_consumer_key": "ck_...",  // Encrypted
  "woo_consumer_secret": "cs_...",  // Encrypted
  "woo_webhook_secret": "...",  // Encrypted
  
  // Shopify
  "shopify_shop_domain": "acme.myshopify.com",
  "shopify_access_token": "shpat_...",  // Encrypted
  "shopify_webhook_secret": "...",  // Encrypted
  
  // === PAYMENT CONFIGURATION ===
  // M-Pesa (Kenya)
  "mpesa_consumer_key": "...",  // Encrypted
  "mpesa_consumer_secret": "...",  // Encrypted
  "mpesa_shortcode": "174379",
  "mpesa_passkey": "...",  // Encrypted
  "mpesa_environment": "production",  // sandbox or production
  
  // Paystack (Africa)
  "paystack_secret_key": "sk_...",  // Encrypted
  "paystack_public_key": "pk_...",
  
  // Pesapal (East Africa)
  "pesapal_consumer_key": "...",  // Encrypted
  "pesapal_consumer_secret": "...",  // Encrypted
  "pesapal_ipn_id": "...",
  
  // Stripe (International)
  "stripe_secret_key": "sk_...",  // Encrypted
  "stripe_publishable_key": "pk_...",
  "stripe_webhook_secret": "whsec_...",  // Encrypted
  
  // === PINECONE (Vector Store) ===
  "pinecone_api_key": "...",  // Encrypted
  "pinecone_index_name": "wabotiq-rag",
  "pinecone_namespace": "tenant_uuid",
  
  // === BUSINESS SETTINGS ===
  "business_name": "Acme Electronics",
  "business_description": "Electronics and gadgets store",
  "business_hours": {
    "monday": {"open": "09:00", "close": "18:00"},
    "tuesday": {"open": "09:00", "close": "18:00"},
    "wednesday": {"open": "09:00", "close": "18:00"},
    "thursday": {"open": "09:00", "close": "18:00"},
    "friday": {"open": "09:00", "close": "18:00"},
    "saturday": {"open": "10:00", "close": "16:00"},
    "sunday": {"closed": true}
  },
  "business_location": "Nairobi, Kenya",
  "business_website": "https://acme.com",
  
  // === BRANDING ===
  "brand_color": "#007bff",
  "brand_logo_url": "https://cdn.acme.com/logo.png",
  "welcome_message": "Karibu Acme Electronics! How can I help you today?",
  "bot_name": "Acme Assistant",
  "bot_personality": "friendly",  // friendly, professional, casual
  
  // === NOTIFICATION SETTINGS ===
  "notify_on_handoff": true,
  "notify_on_order": true,
  "notify_on_appointment": true,
  "notification_email": "alerts@acme.com",
  "notification_phone": "+254712345678",
  
  // === ANALYTICS SETTINGS ===
  "enable_analytics": true,
  "analytics_retention_days": 365,
  "enable_customer_segmentation": true,
  
  // === METADATA ===
  "metadata": {
    "industry": "electronics",
    "target_market": "kenya",
    "average_order_value": 15000,
    "preferred_payment_method": "mpesa"
  },
  
  "created_at": "2025-11-01T00:00:00Z",
  "updated_at": "2025-11-20T10:30:00Z"
}
```

### Settings Categories

**1. AI & LLM Settings**
- Provider selection (OpenAI, Gemini, Together AI)
- Model configuration
- Temperature and token limits
- API keys (encrypted)

**2. RAG Settings**
- Document retrieval toggle
- Database retrieval toggle
- Internet enrichment toggle
- Source attribution
- Grounded validation

**3. Conversation Settings**
- Message harmonization
- Language consistency
- Rich messages
- Handoff configuration

**4. Integration Credentials**
- Twilio (WhatsApp)
- WooCommerce
- Shopify
- Payment providers (M-Pesa, Paystack, etc.)

**5. Business Configuration**
- Business hours
- Location and contact
- Branding (colors, logo)
- Bot personality

---

## 3. Subscription & Billing

### Subscription Tiers

**Starter Tier:**
```json
{
  "name": "Starter",
  "monthly_price": 29.99,
  "yearly_price": 299.99,
  "currency": "USD",
  
  // Limits
  "monthly_messages": 1000,
  "max_products": 100,
  "max_services": 10,
  "max_campaign_sends": 500,
  "max_daily_outbound": 100,
  
  // Features
  "payment_facilitation": false,
  "transaction_fee_percentage": 0,
  "ab_test_variants": 2,
  "priority_support": false,
  "custom_branding": false,
  "api_access": "read"
}
```

**Growth Tier:**
```json
{
  "name": "Growth",
  "monthly_price": 99.99,
  "yearly_price": 999.99,
  "currency": "USD",
  
  // Limits
  "monthly_messages": 5000,
  "max_products": 500,
  "max_services": 50,
  "max_campaign_sends": 2500,
  "max_daily_outbound": 500,
  
  // Features
  "payment_facilitation": true,
  "transaction_fee_percentage": 2.5,
  "ab_test_variants": 5,
  "priority_support": true,
  "custom_branding": true,
  "api_access": "full"
}
```

**Enterprise Tier:**
```json
{
  "name": "Enterprise",
  "monthly_price": 299.99,
  "yearly_price": 2999.99,
  "currency": "USD",
  
  // Limits (null = unlimited)
  "monthly_messages": null,
  "max_products": null,
  "max_services": null,
  "max_campaign_sends": null,
  "max_daily_outbound": null,
  
  // Features
  "payment_facilitation": true,
  "transaction_fee_percentage": 1.5,
  "ab_test_variants": 10,
  "priority_support": true,
  "custom_branding": true,
  "api_access": "full"
}
```

### Subscription Model

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "tier_id": "uuid",
  
  "billing_cycle": "monthly",  // monthly or yearly
  "status": "active",  // active, suspended, canceled, expired
  
  "start_date": "2025-11-01",
  "next_billing_date": "2025-12-01",
  "canceled_at": null,
  "cancellation_reason": null,
  
  // Usage Tracking
  "current_period_start": "2025-11-01",
  "current_period_end": "2025-12-01",
  "messages_sent_this_period": 450,
  "campaigns_sent_this_period": 5,
  
  "created_at": "2025-11-01T00:00:00Z",
  "updated_at": "2025-11-20T10:30:00Z"
}
```

---

## 4. Integration Credentials

### Twilio Configuration

```json
{
  "twilio_sid": "AC...",  // Encrypted
  "twilio_token": "...",  // Encrypted
  "twilio_whatsapp_number": "+254712345678",
  "webhook_secret": "...",  // Encrypted
  
  // Webhook URLs (auto-generated)
  "inbound_webhook_url": "https://api.wabotiq.com/v1/webhooks/twilio/inbound/{tenant_id}",
  "status_webhook_url": "https://api.wabotiq.com/v1/webhooks/twilio/status/{tenant_id}"
}
```

### WooCommerce Configuration

```json
{
  "woo_store_url": "https://store.acme.com",
  "woo_consumer_key": "ck_...",  // Encrypted
  "woo_consumer_secret": "cs_...",  // Encrypted
  "woo_webhook_secret": "...",  // Encrypted
  
  // Sync Settings
  "woo_sync_enabled": true,
  "woo_sync_products": true,
  "woo_sync_orders": true,
  "woo_sync_inventory": true,
  "woo_last_sync": "2025-11-20T10:00:00Z"
}
```

### Shopify Configuration

```json
{
  "shopify_shop_domain": "acme.myshopify.com",
  "shopify_access_token": "shpat_...",  // Encrypted
  "shopify_webhook_secret": "...",  // Encrypted
  
  // Sync Settings
  "shopify_sync_enabled": true,
  "shopify_sync_products": true,
  "shopify_sync_orders": true,
  "shopify_sync_inventory": true,
  "shopify_last_sync": "2025-11-20T10:00:00Z"
}
```

### Payment Provider Configuration

**M-Pesa (Kenya):**
```json
{
  "mpesa_consumer_key": "...",  // Encrypted
  "mpesa_consumer_secret": "...",  // Encrypted
  "mpesa_shortcode": "174379",
  "mpesa_passkey": "...",  // Encrypted
  "mpesa_environment": "production",
  "mpesa_callback_url": "https://api.wabotiq.com/v1/webhooks/mpesa/{tenant_id}"
}
```

**Paystack (Africa):**
```json
{
  "paystack_secret_key": "sk_...",  // Encrypted
  "paystack_public_key": "pk_...",
  "paystack_webhook_url": "https://api.wabotiq.com/v1/webhooks/paystack/{tenant_id}"
}
```

---

## 5. Agent Configuration

### AgentConfiguration Model

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  
  // === PERSONA ===
  "bot_name": "Acme Assistant",
  "bot_personality": "friendly",  // friendly, professional, casual, humorous
  "greeting_message": "Karibu! How can I help you today?",
  "fallback_message": "I'm not sure I understand. Could you rephrase that?",
  
  // === BEHAVIOR ===
  "confidence_threshold": 0.7,
  "max_response_length": 500,
  "enable_proactive_suggestions": true,
  "enable_product_recommendations": true,
  
  // === HANDOFF ===
  "enable_progressive_handoff": true,
  "max_clarification_attempts": 3,
  "handoff_on_low_confidence": true,
  "handoff_confidence_threshold": 0.5,
  "handoff_message": "Let me connect you with a team member who can help better.",
  
  // === FEATURES ===
  "enable_spelling_correction": true,
  "enable_context_summarization": true,
  "enable_key_fact_extraction": true,
  "enable_message_harmonization": true,
  "enable_language_consistency": true,
  "enable_rich_messages": true,
  "enable_feedback_collection": true,
  
  // === RAG ===
  "enable_document_retrieval": true,
  "enable_database_retrieval": true,
  "enable_internet_enrichment": false,
  "enable_source_attribution": true,
  "enable_grounded_validation": true,
  
  // === CUSTOM INSTRUCTIONS ===
  "custom_instructions": "Always mention free delivery for orders over 5000 KES. Emphasize our 7-day return policy.",
  
  "created_at": "2025-11-01T00:00:00Z",
  "updated_at": "2025-11-20T10:30:00Z"
}
```

---

## 6. Business Data

### Catalog Data

**Products:**
```json
{
  "total_products": 150,
  "active_products": 145,
  "categories": [
    {"name": "Electronics", "count": 80},
    {"name": "Fashion", "count": 50},
    {"name": "Home & Garden", "count": 20}
  ],
  "average_price": 15000.00,
  "total_inventory_value": 2250000.00
}
```

**Services:**
```json
{
  "total_services": 12,
  "active_services": 10,
  "categories": [
    {"name": "Hair Services", "count": 5},
    {"name": "Spa Services", "count": 5},
    {"name": "Consultations", "count": 2}
  ],
  "average_price": 1500.00,
  "total_bookings_this_month": 45
}
```

### Customer Data

```json
{
  "total_customers": 1250,
  "active_customers": 890,
  "new_customers_this_month": 45,
  "returning_customers": 845,
  
  "customer_segments": [
    {"segment": "VIP", "count": 50, "total_spent": 500000},
    {"segment": "Regular", "count": 400, "total_spent": 800000},
    {"segment": "New", "count": 800, "total_spent": 200000}
  ],
  
  "average_customer_value": 1200.00,
  "customer_retention_rate": 0.68
}
```

### Order Data

```json
{
  "total_orders": 2500,
  "completed_orders": 2300,
  "pending_orders": 150,
  "canceled_orders": 50,
  
  "total_revenue": 3750000.00,
  "average_order_value": 1500.00,
  
  "orders_this_month": 180,
  "revenue_this_month": 270000.00,
  
  "top_products": [
    {"product": "Samsung Galaxy A54", "orders": 45, "revenue": 1575000},
    {"product": "HP Pavilion Gaming", "orders": 30, "revenue": 1440000}
  ]
}
```

---

## 7. Analytics & Metrics

### Daily Analytics

```json
{
  "date": "2025-11-20",
  "tenant_id": "uuid",
  
  // Messages
  "messages_inbound": 450,
  "messages_outbound": 520,
  "messages_total": 970,
  "avg_response_time_seconds": 2.5,
  
  // Conversations
  "conversations_started": 45,
  "conversations_active": 120,
  "conversations_closed": 38,
  "handoff_count": 5,
  "handoff_rate": 0.04,
  
  // Orders
  "orders_created": 12,
  "orders_completed": 10,
  "orders_canceled": 1,
  "revenue": 18000.00,
  "avg_order_value": 1500.00,
  
  // Appointments
  "appointments_booked": 8,
  "appointments_completed": 6,
  "appointments_canceled": 1,
  "appointment_revenue": 12000.00,
  
  // AI Agent
  "ai_interactions": 450,
  "avg_confidence": 0.85,
  "low_confidence_count": 25,
  "total_tokens_used": 125000,
  "total_ai_cost": 1.875,
  
  // Customers
  "new_customers": 5,
  "returning_customers": 40,
  "active_customers": 45
}
```

### Performance Metrics

```json
{
  "period": "2025-11",
  "tenant_id": "uuid",
  
  // Conversion Rates
  "conversation_to_order_rate": 0.15,
  "message_to_order_rate": 0.03,
  "cart_abandonment_rate": 0.25,
  
  // Customer Satisfaction
  "avg_feedback_score": 4.5,
  "positive_feedback_count": 180,
  "negative_feedback_count": 20,
  "feedback_response_rate": 0.45,
  
  // AI Performance
  "avg_ai_confidence": 0.85,
  "handoff_rate": 0.04,
  "resolution_rate": 0.92,
  "avg_response_time_seconds": 2.5,
  
  // Financial
  "total_revenue": 270000.00,
  "total_orders": 180,
  "avg_order_value": 1500.00,
  "transaction_fees_collected": 6750.00
}
```

---

## 8. API Access

### API Keys

```json
{
  "api_keys": [
    {
      "key_hash": "sha256_hash_of_key",
      "name": "Production API Key",
      "scopes": ["read", "write"],
      "created_at": "2025-11-01T10:00:00Z",
      "last_used_at": "2025-11-20T15:30:00Z",
      "expires_at": null,
      "is_active": true
    },
    {
      "key_hash": "sha256_hash_of_key_2",
      "name": "Mobile App Key",
      "scopes": ["read"],
      "created_at": "2025-11-05T14:00:00Z",
      "last_used_at": "2025-11-20T16:00:00Z",
      "expires_at": "2026-11-05T14:00:00Z",
      "is_active": true
    }
  ]
}
```

### CORS Configuration

```json
{
  "allowed_origins": [
    "https://dashboard.acme.com",
    "https://app.acme.com",
    "https://mobile.acme.com"
  ],
  "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
  "allowed_headers": ["Content-Type", "Authorization", "X-TENANT-ID"],
  "max_age": 3600
}
```

---

## Summary

### Tenant Data Categories

1. **Core Tenant Info** - Name, status, contact
2. **Subscription** - Tier, billing, limits
3. **Settings** - AI, RAG, integrations, branding
4. **Credentials** - Twilio, WooCommerce, Shopify, payments (all encrypted)
5. **Agent Config** - Personality, behavior, features
6. **Business Data** - Products, services, customers, orders
7. **Analytics** - Messages, conversions, revenue, AI performance
8. **API Access** - Keys, CORS, permissions

### Key Features

✅ **Multi-tenant isolation** - Strict data separation  
✅ **Encrypted credentials** - All sensitive data encrypted at rest  
✅ **Flexible configuration** - Extensive customization options  
✅ **Subscription management** - Tiered pricing with limits  
✅ **Integration support** - Multiple e-commerce and payment providers  
✅ **AI customization** - Provider selection, model configuration  
✅ **Analytics tracking** - Comprehensive metrics and insights  
✅ **API access control** - Scoped keys with CORS support  

**All tenant data is structured, queryable, and accessible via API with proper RBAC enforcement!** 🔒📊
