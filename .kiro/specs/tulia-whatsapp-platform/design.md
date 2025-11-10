# Design Document

## Overview

Tulia AI is a multi-tenant WhatsApp commerce and services platform that enables businesses to sell products and bookable services through conversational AI. The system architecture prioritizes strict tenant isolation, scalability, and compliance with data privacy regulations.

### Core Design Principles

1. **Multi-Tenant First**: Every data model, query, and operation is scoped by tenant_id
2. **Identity Isolation**: Customers are unique by (tenant_id, phone_e164) with optional GlobalParty for internal linkage
3. **Service Parity**: Products and Services receive equal treatment in catalogs, analytics, and bot capabilities
4. **Subscription-Driven Access**: Bot functionality and feature limits are controlled by active subscriptions
5. **Consent-Based Messaging**: All non-transactional communications require explicit customer opt-in
6. **Observability**: Comprehensive logging, audit trails, and error tracking via Sentry

### Technology Stack

- **Backend**: Python 3.12, Django 4.2+, Django REST Framework
- **Database**: PostgreSQL with encrypted PII fields
- **Cache & Queue**: Redis for caching and Celery for async tasks
- **AI/LLM**: OpenAI/Claude for intent classification and conversation handling
- **Messaging**: Twilio WhatsApp API (phase 1), Meta WABA upgrade path
- **Integrations**: WooCommerce REST API, Shopify Admin API
- **Observability**: Sentry for error tracking, structured logging
- **API Documentation**: drf-spectacular for OpenAPI 3.0 schema

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WhatsApp Customers                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Twilio WhatsApp API                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Tulia API Gateway Layer                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Webhook Handler → Tenant Resolution → Signature Verify  │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Middleware Layer                             │
│  • Tenant Context Injection (X-TENANT-ID, X-TENANT-API-KEY)     │
│  • Subscription Status Check                                     │
│  • Rate Limiting (per tenant)                                    │
│  • Request ID Injection                                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Application Layer                      │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Intent     │  │   Catalog    │  │   Booking    │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Messaging  │  │ Subscription │  │   Wallet     │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Analytics   │  │  Consent     │  │  Campaign    │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Twilio     │  │  WooCommerce │  │   Shopify    │          │
│  │   Service    │  │   Service    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
│  • PostgreSQL (multi-tenant data with row-level security)       │
│  • Redis (caching, session management, rate limiting)           │
│  • Celery (async tasks: sync, analytics, reminders)            │
└─────────────────────────────────────────────────────────────────┘
```

### Request Flow: Inbound WhatsApp Message

1. **Twilio Webhook** → POST /v1/webhooks/twilio
2. **Tenant Resolution**: Resolve tenant by "To" number or URL path
3. **Signature Verification**: Validate X-Twilio-Signature using tenant's webhook_secret
4. **Subscription Check**: Verify tenant has active subscription or valid free trial
5. **Customer Upsert**: Create or retrieve Customer by (tenant_id, phone_e164)
6. **Conversation Upsert**: Create or retrieve Conversation for (tenant, customer)
7. **Message Persistence**: Store inbound Message with payload
8. **Intent Classification**: IntentService analyzes message and extracts slots
9. **Intent Routing**: Route to appropriate handler (products, services, booking, etc.)
10. **Response Generation**: Handler generates response message
11. **Consent Check**: Verify customer consent for message type (if outbound)
12. **Message Delivery**: TwilioService sends response via WhatsApp
13. **Analytics Update**: Increment message counters, track intent events


## Components and Interfaces

### 1. Webhook Handler Component

**Responsibility**: Receive and validate incoming Twilio WhatsApp webhooks

**Key Methods**:
- `handle_twilio_webhook(request)`: Main entry point for webhook processing
- `resolve_tenant(to_number, url_path)`: Determine tenant from phone number or URL
- `verify_signature(request, tenant)`: Validate Twilio signature
- `create_webhook_log(tenant, payload, status)`: Audit trail for all webhooks

**Dependencies**: TenantRepository, WebhookLogRepository, TwilioService

**Error Handling**:
- 404: Tenant not found
- 401: Invalid signature
- 503: Subscription inactive (with customer notification)

### 2. Intent Service Component

**Responsibility**: Classify customer messages into actionable intents using LLM

**Supported Intents**:
- **Product Intents**: GREETING, BROWSE_PRODUCTS, PRODUCT_DETAILS, PRICE_CHECK, STOCK_CHECK, ADD_TO_CART, CHECKOUT_LINK
- **Service Intents**: BROWSE_SERVICES, SERVICE_DETAILS, CHECK_AVAILABILITY, BOOK_APPOINTMENT, RESCHEDULE_APPOINTMENT, CANCEL_APPOINTMENT
- **Consent Intents**: OPT_IN_PROMOTIONS, OPT_OUT_PROMOTIONS, STOP_ALL, START_ALL
- **Support Intents**: HUMAN_HANDOFF, OTHER

**Key Methods**:
- `classify_intent(message_text, conversation_context)`: Returns intent name, confidence, and extracted slots
- `extract_slots(message_text, intent)`: Parse entities like product_id, date, time, quantity
- `handle_low_confidence(message_text, attempt_count)`: Fallback logic for unclear intents

**Slot Extraction Examples**:
- PRODUCT_DETAILS: {product_query: "sneakers", product_id: null}
- CHECK_AVAILABILITY: {service_id: "svc_123", date: "2025-11-15", time_range: "morning"}
- BOOK_APPOINTMENT: {service_id: "svc_123", variant_id: "var_456", date: "2025-11-15", time: "10:00", notes: "first visit"}

**Dependencies**: OpenAI/Claude API, ConversationRepository, IntentEventRepository


### 3. Catalog Service Component

**Responsibility**: Manage products and services with multi-tenant isolation

**Key Methods**:
- `search_products(tenant_id, query, filters)`: Full-text search across products
- `get_product(tenant_id, product_id)`: Retrieve product with variants
- `search_services(tenant_id, query, filters)`: Full-text search across services
- `get_service(tenant_id, service_id)`: Retrieve service with variants and availability
- `check_feature_limit(tenant_id, resource_type)`: Enforce tier-based limits

**Dependencies**: ProductRepository, ServiceRepository, SubscriptionService

### 4. Booking Service Component

**Responsibility**: Manage service availability and appointment bookings

**Key Methods**:
- `find_availability(tenant_id, service_id, from_dt, to_dt)`: Return available slots
- `create_appointment(tenant_id, customer_id, service_id, variant_id, start_dt, notes)`: Book appointment with capacity validation
- `cancel_appointment(tenant_id, appointment_id)`: Cancel and free up capacity
- `check_capacity(service_id, start_dt, end_dt)`: Validate slot availability
- `propose_alternatives(service_id, requested_dt)`: Suggest 3 nearby slots

**Capacity Calculation**:
```python
available_capacity = window.capacity - count(appointments in window with status in ['pending', 'confirmed'])
```

**Dependencies**: AvailabilityWindowRepository, AppointmentRepository, ServiceRepository


### 5. Subscription Service Component

**Responsibility**: Manage tenant subscriptions, billing, and feature enforcement

**Subscription Tiers**:

| Feature | Starter | Growth | Enterprise |
|---------|---------|--------|------------|
| Monthly Price | $29 | $99 | $299 |
| Yearly Price (20% off) | $278 | $950 | $2,870 |
| Monthly Messages | 1,000 | 10,000 | Unlimited |
| Max Products | 100 | 1,000 | Unlimited |
| Max Services | 10 | 50 | Unlimited |
| Payment Facilitation | No | Yes (3.5% fee) | Yes (2.5% fee) |
| Campaign Sends/Month | 500 | 5,000 | Unlimited |
| A/B Testing Variants | 2 | 2 | 4 |
| Priority Support | No | No | Yes |
| Custom Branding | No | No | Yes |
| API Access | Read-only | Full | Full |

**Key Methods**:
- `check_subscription_status(tenant_id)`: Returns active, trial, expired, suspended
- `enforce_feature_limit(tenant_id, feature_name, current_count)`: Raise error if limit exceeded
- `process_billing(subscription_id)`: Charge payment method and update next_billing_date
- `apply_discounts(subscription_id)`: Calculate final price with active discounts
- `handle_payment_failure(subscription_id, attempt_count)`: Retry logic and suspension

**Free Trial Logic**:
- Default duration: 14 days (configurable globally)
- Per-tenant override available
- Full tier features during trial
- Auto-expire with notification at 3 days remaining

**Dependencies**: SubscriptionRepository, TenantRepository, PaymentGateway, NotificationService


### 6. Wallet Service Component

**Responsibility**: Manage tenant wallets, transactions, and withdrawals

**Key Methods**:
- `credit_wallet(tenant_id, amount, transaction_type, reference_id)`: Add funds to wallet
- `debit_wallet(tenant_id, amount, transaction_type, reference_id)`: Remove funds from wallet
- `calculate_transaction_fee(tenant_id, payment_amount)`: Apply tier-based fee percentage
- `process_customer_payment(order_id, payment_amount)`: Record payment, deduct fee, credit wallet
- `request_withdrawal(tenant_id, amount)`: Create pending withdrawal transaction
- `process_withdrawal(transaction_id, status)`: Complete or fail withdrawal

**Transaction Flow for Customer Payment**:
1. Customer pays $100 for order
2. Calculate fee: Growth tier = 3.5% = $3.50
3. Net amount: $100 - $3.50 = $96.50
4. Create Transaction: type="customer_payment", amount=$100, fee=$3.50, net=$96.50
5. Create Transaction: type="platform_fee", amount=$3.50 (for platform accounting)
6. Credit TenantWallet: balance += $96.50
7. Create audit record with previous_balance, amount, new_balance

**Withdrawal Rules**:
- Minimum withdrawal: $10 (configurable per tenant)
- Immediate debit from wallet (prevents double-spending)
- Admin approval required for amounts > $10,000
- Failed withdrawals credit back to wallet

**Dependencies**: WalletRepository, TransactionRepository, SubscriptionService


### 7. Messaging Service Component

**Responsibility**: Send outbound messages with consent validation and rate limiting

**Message Types**:
- **automated_transactional**: Order/payment updates, booking confirmations (always allowed)
- **automated_reminder**: Appointment reminders (requires reminder_messages consent)
- **automated_reengagement**: Inactive conversation nudges (requires promotional_messages consent)
- **scheduled_promotional**: Planned marketing messages (requires promotional_messages consent)
- **manual_outbound**: Tenant-initiated messages (respects consent)

**Key Methods**:
- `send_message(tenant_id, customer_id, content, message_type, template_id)`: Main send method
- `check_consent(customer_id, message_type)`: Validate customer preferences
- `check_rate_limit(tenant_id)`: Enforce daily message limits
- `apply_template(template_id, context_data)`: Replace placeholders with actual data
- `schedule_message(tenant_id, customer_id, content, scheduled_at)`: Queue for future delivery
- `respect_quiet_hours(customer_id, scheduled_at)`: Adjust delivery time for timezone

**Rate Limiting**:
- Track messages per tenant in 24-hour rolling window
- Starter: 1,000/day, Growth: 10,000/day, Enterprise: unlimited
- Warning at 80% threshold
- Queue excess messages for next day

**Quiet Hours**:
- Default: 10 PM - 8 AM in customer's timezone
- Configurable per tenant
- Override for time-sensitive transactional messages

**Dependencies**: TwilioService, ConsentService, CustomerRepository, MessageTemplateRepository


### 8. Consent Service Component

**Responsibility**: Manage customer communication preferences and consent tracking

**Consent Types**:
- **transactional_messages**: Order updates, payment confirmations (default: true, cannot opt-out)
- **reminder_messages**: Appointment reminders, cart abandonment (default: true, can opt-out)
- **promotional_messages**: Marketing, offers, campaigns (default: false, requires opt-in)

**Key Methods**:
- `get_preferences(tenant_id, customer_id)`: Retrieve all consent settings
- `update_consent(tenant_id, customer_id, consent_type, value, source)`: Change preference with audit
- `check_consent(tenant_id, customer_id, message_type)`: Validate before sending
- `handle_opt_out_intent(customer_id, intent_slots)`: Process "stop promotions" messages
- `handle_opt_in_intent(customer_id, intent_slots)`: Process "start promotions" messages
- `log_consent_event(customer_id, consent_type, old_value, new_value, source)`: Audit trail

**Opt-Out Detection**:
- Keywords: "STOP", "UNSUBSCRIBE", "stop promotions", "no more messages"
- IntentService classifies as OPT_OUT intent
- Updates promotional_messages and reminder_messages to false
- Sends confirmation: "You have been unsubscribed from promotional and reminder messages"

**Compliance**:
- Complete audit trail with timestamps and sources
- Export capability for regulatory requests
- Block messages without proper consent
- Log compliance violations

**Dependencies**: CustomerPreferencesRepository, ConsentEventRepository, IntentService


### 9. Campaign Service Component

**Responsibility**: Create and execute message campaigns with targeting and analytics

**Key Methods**:
- `create_campaign(tenant_id, name, content, target_criteria, scheduled_at)`: Define campaign
- `execute_campaign(campaign_id)`: Send to all matching customers with consent
- `calculate_reach(tenant_id, target_criteria)`: Count eligible customers
- `track_delivery(campaign_id, customer_id, status)`: Record send status
- `generate_report(campaign_id)`: Aggregate engagement metrics
- `create_ab_test(tenant_id, name, variants, target_criteria)`: Set up A/B test

**Targeting Criteria**:
- Customer tags (e.g., "vip", "new_customer")
- Purchase history (e.g., "ordered_in_last_30_days")
- Conversation activity (e.g., "active_in_last_7_days")
- Consent status (automatically filtered)

**A/B Testing**:
- Define 2-4 variants (Enterprise tier allows 4)
- Random assignment with equal distribution
- Track metrics per variant: response_count, conversion_count, avg_response_time
- Statistical significance calculation

**Campaign Metrics**:
- delivery_count: Total customers targeted
- delivered_count: Successfully sent
- failed_count: Send failures
- read_count: Message read receipts
- response_count: Customer replies
- conversion_count: Orders/bookings from campaign
- engagement_rate: responses / delivered

**Dependencies**: MessagingService, ConsentService, CustomerRepository, AnalyticsService


### 10. Analytics Service Component

**Responsibility**: Aggregate and report metrics for messages, orders, bookings, and revenue

**Key Methods**:
- `get_overview(tenant_id, date_range)`: High-level metrics for dashboard
- `get_daily_metrics(tenant_id, date)`: Retrieve AnalyticsDaily record
- `rollup_daily_metrics(date)`: Nightly Celery task to aggregate all tenants
- `calculate_booking_conversion_rate(tenant_id, date_range)`: Bookings / availability checks
- `calculate_no_show_rate(tenant_id, date_range)`: No-shows / confirmed appointments
- `get_messaging_analytics(tenant_id, date_range)`: Metrics by message_type
- `get_revenue_analytics(date_range)`: Platform-wide payment volume and fees

**Metrics Tracked**:
- **Messaging**: msgs_in, msgs_out, conversations, avg_first_response_secs, handoffs
- **Commerce**: orders, revenue, avg_order_value
- **Services**: bookings, booking_conversion_rate, no_show_rate
- **Campaigns**: campaign_sends, campaign_responses, campaign_conversions
- **Platform Revenue**: payment_volume, platform_fees, subscription_revenue

**Nightly Rollup Process** (Celery task at 2 AM):
1. For each tenant:
2. Count messages in/out for previous day
3. Count new conversations, orders, bookings
4. Calculate revenue from paid/fulfilled orders
5. Calculate conversion rates
6. Create or update AnalyticsDaily record
7. Log completion status

**Dependencies**: MessageRepository, OrderRepository, AppointmentRepository, IntentEventRepository


### 11. Integration Services

#### Twilio Service

**Responsibility**: Send and receive WhatsApp messages via Twilio API

**Key Methods**:
- `send_whatsapp(to, from_number, body, media_url)`: Send message
- `send_template(to, from_number, template_sid, variables)`: Send Twilio template
- `verify_signature(url, params, signature, auth_token)`: Validate webhook
- `handle_status_callback(payload)`: Process delivery receipts

**Configuration per Tenant**:
- twilio_sid: Account SID
- twilio_token: Auth token
- whatsapp_number: Sender number (e.g., +14155238886)
- webhook_secret: For signature verification

#### WooCommerce Service

**Responsibility**: Sync products from WooCommerce stores

**Key Methods**:
- `sync_products(tenant_id, store_url, api_key, api_secret)`: Full sync
- `fetch_products_batch(store_url, credentials, page, per_page)`: Paginated fetch
- `transform_product(woo_product)`: Convert to Tulia Product model
- `transform_variations(woo_variations)`: Convert to ProductVariant models

**Sync Process**:
1. Authenticate with WooCommerce REST API
2. Fetch products in batches of 100
3. For each product: upsert Product with external_source="woocommerce", external_id=woo_id
4. For each variation: upsert ProductVariant
5. Mark products not in sync as inactive
6. Log sync status and item count


#### Shopify Service

**Responsibility**: Sync products from Shopify stores

**Key Methods**:
- `sync_products(tenant_id, shop_domain, access_token)`: Full sync
- `fetch_products_batch(shop_domain, access_token, page, limit)`: Paginated fetch
- `transform_product(shopify_product)`: Convert to Tulia Product model
- `transform_variants(shopify_variants)`: Convert to ProductVariant models

**Sync Process**:
1. Authenticate with Shopify Admin API
2. Fetch products in batches of 100
3. For each product: upsert Product with external_source="shopify", external_id=shopify_id
4. For each variant: upsert ProductVariant
5. Mark products not in sync as inactive
6. Log sync status and item count

## Data Models

### Core Tenant & Identity Models

```python
class Tenant(BaseModel):
    id = UUIDField(primary_key=True)
    name = CharField(max_length=255)
    slug = SlugField(unique=True)
    status = CharField(choices=['active', 'trial', 'trial_expired', 'suspended', 'canceled'])
    
    # Subscription
    subscription_tier = ForeignKey(SubscriptionTier)
    subscription_waived = BooleanField(default=False)
    trial_start_date = DateTimeField(null=True)
    trial_end_date = DateTimeField(null=True)
    
    # Twilio Configuration
    whatsapp_number = CharField(max_length=20, unique=True)
    twilio_sid = EncryptedCharField(max_length=255)
    twilio_token = EncryptedCharField(max_length=255)
    webhook_secret = EncryptedCharField(max_length=255)
    
    # API Access
    api_keys = JSONField(default=list)  # [{key_hash, name, created_at}]
    allowed_origins = JSONField(default=list)
    
    # Settings
    timezone = CharField(default='UTC')
    quiet_hours_start = TimeField(default='22:00')
    quiet_hours_end = TimeField(default='08:00')
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

```python
class GlobalParty(BaseModel):
    """Internal-only linkage of same phone across tenants"""
    id = UUIDField(primary_key=True)
    phone_e164 = EncryptedCharField(max_length=20, unique=True)
    created_at = DateTimeField(auto_now_add=True)

class Customer(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    phone_e164 = EncryptedCharField(max_length=20)
    name = CharField(max_length=255, null=True)
    timezone = CharField(max_length=50, null=True)
    tags = JSONField(default=list)
    last_seen_at = DateTimeField(null=True)
    global_party = ForeignKey(GlobalParty, null=True)  # Internal only
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('tenant', 'phone_e164')]
        indexes = [
            Index(fields=['tenant', 'phone_e164']),
            Index(fields=['tenant', 'last_seen_at']),
        ]

class Conversation(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    customer = ForeignKey(Customer)
    status = CharField(choices=['open', 'bot', 'handoff', 'closed', 'dormant'])
    channel = CharField(default='whatsapp')
    last_intent = CharField(max_length=100, null=True)
    last_agent = ForeignKey(User, null=True)
    metadata = JSONField(default=dict)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'customer', 'status']),
            Index(fields=['tenant', 'updated_at']),
        ]
```

```python
class Message(BaseModel):
    id = UUIDField(primary_key=True)
    conversation = ForeignKey(Conversation)
    direction = CharField(choices=['in', 'out'])
    message_type = CharField(choices=[
        'customer_inbound',
        'bot_response',
        'automated_transactional',
        'automated_reminder',
        'automated_reengagement',
        'scheduled_promotional',
        'manual_outbound'
    ])
    text = TextField()
    payload = JSONField(default=dict)  # Media, buttons, etc.
    provider_msg_id = CharField(max_length=255, null=True)
    template_id = ForeignKey(MessageTemplate, null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['conversation', 'created_at']),
            Index(fields=['provider_msg_id']),
        ]
```

### Catalog Models

```python
class Product(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    external_source = CharField(choices=['woocommerce', 'shopify', 'manual'], null=True)
    external_id = CharField(max_length=255, null=True)
    
    title = CharField(max_length=500)
    description = TextField(null=True)
    images = JSONField(default=list)
    price = DecimalField(max_digits=10, decimal_places=2)
    currency = CharField(max_length=3, default='USD')
    sku = CharField(max_length=255, null=True)
    stock = IntegerField(null=True)
    is_active = BooleanField(default=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('tenant', 'external_source', 'external_id')]
        indexes = [
            Index(fields=['tenant', 'is_active']),
            Index(fields=['tenant', 'title']),  # For search
        ]
```

```python
class ProductVariant(BaseModel):
    id = UUIDField(primary_key=True)
    product = ForeignKey(Product)
    title = CharField(max_length=255)
    sku = CharField(max_length=255, null=True)
    price = DecimalField(max_digits=10, decimal_places=2, null=True)
    stock = IntegerField(null=True)
    attrs = JSONField(default=dict)  # {size: "42", color: "red"}
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class Service(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    
    title = CharField(max_length=500)
    description = TextField(null=True)
    images = JSONField(default=list)
    base_price = DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = CharField(max_length=3, default='USD')
    is_active = BooleanField(default=True)
    requires_slot = BooleanField(default=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'is_active']),
            Index(fields=['tenant', 'title']),
        ]

class ServiceVariant(BaseModel):
    id = UUIDField(primary_key=True)
    service = ForeignKey(Service)
    title = CharField(max_length=255)
    duration_minutes = IntegerField()
    price = DecimalField(max_digits=10, decimal_places=2, null=True)
    attrs = JSONField(default=dict)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

```python
class AvailabilityWindow(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    service = ForeignKey(Service)
    
    # Either weekday (recurring) or specific date
    weekday = IntegerField(null=True)  # 0=Monday, 6=Sunday
    date = DateField(null=True)
    
    start_time = TimeField()
    end_time = TimeField()
    capacity = IntegerField(default=1)
    timezone = CharField(max_length=50)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'service', 'weekday']),
            Index(fields=['tenant', 'service', 'date']),
        ]

class Appointment(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    customer = ForeignKey(Customer)
    service = ForeignKey(Service)
    variant = ForeignKey(ServiceVariant, null=True)
    
    start_dt = DateTimeField()
    end_dt = DateTimeField()
    status = CharField(choices=['pending', 'confirmed', 'done', 'canceled', 'no_show'])
    notes = TextField(null=True)
    provider_ref = CharField(max_length=255, null=True)  # External calendar ID
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'customer', 'status']),
            Index(fields=['tenant', 'service', 'start_dt']),
            Index(fields=['tenant', 'start_dt', 'status']),
        ]
```

### Order & Cart Models

```python
class Cart(BaseModel):
    id = UUIDField(primary_key=True)
    conversation = ForeignKey(Conversation, unique=True)
    items = JSONField(default=list)  # [{product_id, variant_id, qty, price}]
    subtotal = DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class Order(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    customer = ForeignKey(Customer)
    
    currency = CharField(max_length=3)
    subtotal = DecimalField(max_digits=10, decimal_places=2)
    shipping = DecimalField(max_digits=10, decimal_places=2, default=0)
    total = DecimalField(max_digits=10, decimal_places=2)
    
    status = CharField(choices=['draft', 'placed', 'paid', 'fulfilled', 'canceled'])
    items = JSONField(default=list)
    payment_ref = CharField(max_length=255, null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'customer', 'status']),
            Index(fields=['tenant', 'status', 'created_at']),
        ]
```

### Subscription & Billing Models

```python
class SubscriptionTier(BaseModel):
    id = UUIDField(primary_key=True)
    name = CharField(max_length=50, unique=True)  # Starter, Growth, Enterprise
    monthly_price = DecimalField(max_digits=10, decimal_places=2)
    yearly_price = DecimalField(max_digits=10, decimal_places=2)
    
    # Feature Limits
    monthly_messages = IntegerField(null=True)  # null = unlimited
    max_products = IntegerField(null=True)
    max_services = IntegerField(null=True)
    max_campaign_sends = IntegerField(null=True)
    max_daily_outbound = IntegerField(null=True)
    
    # Features
    payment_facilitation = BooleanField(default=False)
    transaction_fee_percentage = DecimalField(max_digits=5, decimal_places=2, default=0)
    ab_test_variants = IntegerField(default=2)
    priority_support = BooleanField(default=False)
    custom_branding = BooleanField(default=False)
    api_access = CharField(choices=['none', 'read', 'full'], default='read')
```

```python
class Subscription(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant, unique=True)
    tier = ForeignKey(SubscriptionTier)
    
    billing_cycle = CharField(choices=['monthly', 'yearly'])
    status = CharField(choices=['active', 'suspended', 'canceled', 'expired'])
    
    start_date = DateField()
    next_billing_date = DateField()
    canceled_at = DateTimeField(null=True)
    
    payment_method_id = CharField(max_length=255, null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class SubscriptionDiscount(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    discount_type = CharField(choices=['percentage', 'fixed_amount'])
    value = DecimalField(max_digits=10, decimal_places=2)
    
    expiry_date = DateField(null=True)
    usage_limit = IntegerField(null=True)
    usage_count = IntegerField(default=0)
    
    created_at = DateTimeField(auto_now_add=True)

class SubscriptionEvent(BaseModel):
    id = UUIDField(primary_key=True)
    subscription = ForeignKey(Subscription)
    event_type = CharField(choices=[
        'created', 'tier_changed', 'renewed', 'suspended', 'canceled', 'reactivated'
    ])
    metadata = JSONField(default=dict)  # {previous_tier, new_tier, reason, etc.}
    
    created_at = DateTimeField(auto_now_add=True)
```

### Wallet & Transaction Models

```python
class TenantWallet(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant, unique=True)
    balance = DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = CharField(max_length=3, default='USD')
    minimum_withdrawal = DecimalField(max_digits=10, decimal_places=2, default=10)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class Transaction(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    wallet = ForeignKey(TenantWallet)
    
    transaction_type = CharField(choices=[
        'customer_payment', 'platform_fee', 'withdrawal', 'refund', 'adjustment'
    ])
    amount = DecimalField(max_digits=12, decimal_places=2)
    fee = DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = DecimalField(max_digits=12, decimal_places=2)
    
    status = CharField(choices=['pending', 'completed', 'failed', 'canceled'])
    reference_type = CharField(max_length=50, null=True)  # 'order', 'appointment'
    reference_id = UUIDField(null=True)
    
    metadata = JSONField(default=dict)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'transaction_type', 'created_at']),
            Index(fields=['wallet', 'status']),
        ]

class WalletAudit(BaseModel):
    id = UUIDField(primary_key=True)
    wallet = ForeignKey(TenantWallet)
    transaction = ForeignKey(Transaction)
    
    previous_balance = DecimalField(max_digits=12, decimal_places=2)
    amount = DecimalField(max_digits=12, decimal_places=2)
    new_balance = DecimalField(max_digits=12, decimal_places=2)
    
    created_at = DateTimeField(auto_now_add=True)
```

### Messaging & Consent Models

```python
class MessageTemplate(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    name = CharField(max_length=255)
    content = TextField()  # Supports {{placeholder}} syntax
    message_type = CharField(choices=[
        'transactional', 'reminder', 'promotional', 'reengagement'
    ])
    usage_count = IntegerField(default=0)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

class ScheduledMessage(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    customer = ForeignKey(Customer, null=True)  # null = campaign
    
    content = TextField()
    template = ForeignKey(MessageTemplate, null=True)
    scheduled_at = DateTimeField()
    status = CharField(choices=['pending', 'sent', 'failed', 'canceled'])
    
    created_at = DateTimeField(auto_now_add=True)
    sent_at = DateTimeField(null=True)

class MessageCampaign(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    name = CharField(max_length=255)
    
    message_content = TextField()
    template = ForeignKey(MessageTemplate, null=True)
    target_criteria = JSONField(default=dict)  # {tags, purchase_history, etc.}
    
    # A/B Testing
    is_ab_test = BooleanField(default=False)
    variants = JSONField(default=list)  # [{name, content, customer_ids}]
    
    # Metrics
    delivery_count = IntegerField(default=0)
    delivered_count = IntegerField(default=0)
    failed_count = IntegerField(default=0)
    read_count = IntegerField(default=0)
    response_count = IntegerField(default=0)
    conversion_count = IntegerField(default=0)
    
    status = CharField(choices=['draft', 'scheduled', 'sending', 'completed', 'canceled'])
    scheduled_at = DateTimeField(null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    completed_at = DateTimeField(null=True)
```

```python
class CustomerPreferences(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    customer = ForeignKey(Customer)
    
    transactional_messages = BooleanField(default=True)  # Cannot opt-out
    reminder_messages = BooleanField(default=True)
    promotional_messages = BooleanField(default=False)  # Requires opt-in
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('tenant', 'customer')]

class ConsentEvent(BaseModel):
    id = UUIDField(primary_key=True)
    customer = ForeignKey(Customer)
    consent_type = CharField(max_length=50)  # 'promotional_messages', etc.
    
    previous_value = BooleanField()
    new_value = BooleanField()
    source = CharField(choices=['customer_initiated', 'tenant_updated', 'system_default'])
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['customer', 'created_at']),
        ]
```

### Analytics & Audit Models

```python
class AnalyticsDaily(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant)
    date = DateField()
    
    # Messaging
    msgs_in = IntegerField(default=0)
    msgs_out = IntegerField(default=0)
    conversations = IntegerField(default=0)
    avg_first_response_secs = FloatField(null=True)
    handoffs = IntegerField(default=0)
    
    # Commerce
    enquiries = IntegerField(default=0)
    orders = IntegerField(default=0)
    revenue = DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Services
    bookings = IntegerField(default=0)
    booking_conversion_rate = FloatField(null=True)
    no_show_rate = FloatField(null=True)
    
    # Campaigns
    campaign_sends = IntegerField(default=0)
    campaign_responses = IntegerField(default=0)
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('tenant', 'date')]
        indexes = [
            Index(fields=['tenant', 'date']),
        ]
```

```python
class IntentEvent(BaseModel):
    id = UUIDField(primary_key=True)
    conversation = ForeignKey(Conversation)
    intent_name = CharField(max_length=100)
    confidence_score = FloatField()
    slots = JSONField(default=dict)
    model = CharField(max_length=50)  # 'gpt-4', 'claude-3', etc.
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['conversation', 'created_at']),
            Index(fields=['intent_name', 'created_at']),
        ]

class WebhookLog(BaseModel):
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant, null=True)
    provider = CharField(max_length=50)  # 'twilio'
    event = CharField(max_length=100)
    payload = JSONField()
    status = CharField(choices=[
        'success', 'error', 'unauthorized', 'subscription_inactive'
    ])
    error_message = TextField(null=True)
    
    received_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'received_at']),
            Index(fields=['provider', 'status', 'received_at']),
        ]
```

## Error Handling

### Error Response Format

All API errors follow a consistent JSON structure:

```json
{
  "error": {
    "code": "SUBSCRIPTION_INACTIVE",
    "message": "Your subscription is inactive. Please update your payment method.",
    "details": {
      "subscription_status": "suspended",
      "next_billing_date": "2025-11-01"
    }
  }
}
```

### Error Categories

**Authentication Errors (401)**:
- INVALID_API_KEY: X-TENANT-API-KEY is invalid
- INVALID_SIGNATURE: Twilio signature verification failed
- MISSING_CREDENTIALS: Required auth headers missing

**Authorization Errors (403)**:
- FEATURE_LIMIT_EXCEEDED: Tenant exceeded tier limit (products, services, messages)
- SUBSCRIPTION_INACTIVE: Subscription expired or suspended
- INSUFFICIENT_PERMISSIONS: API key lacks required permissions

**Validation Errors (400)**:
- INVALID_INPUT: Request data validation failed
- MISSING_REQUIRED_FIELD: Required field not provided
- INVALID_SLOT_TIME: Appointment time outside availability window
- CAPACITY_EXCEEDED: No available capacity for booking
```

**Resource Errors (404)**:
- TENANT_NOT_FOUND: Tenant resolution failed
- RESOURCE_NOT_FOUND: Requested resource doesn't exist or doesn't belong to tenant

**Rate Limiting (429)**:
- RATE_LIMIT_EXCEEDED: Too many requests in time window
- DAILY_MESSAGE_LIMIT: Exceeded daily outbound message limit

**Server Errors (500, 503)**:
- INTERNAL_ERROR: Unexpected server error (logged to Sentry)
- SERVICE_UNAVAILABLE: Dependency unavailable (database, Redis, Celery)
- EXTERNAL_API_ERROR: Third-party API failure (Twilio, WooCommerce, Shopify)

### Retry Strategy

**Webhook Processing**:
- Twilio retries failed webhooks automatically
- Log all attempts in WebhookLog
- Return 200 to prevent retries for business logic errors

**Outbound Messages**:
- Retry up to 3 times with exponential backoff (1s, 5s, 15s)
- Log failures after final attempt
- Send to dead letter queue for manual review

**Background Jobs**:
- Celery auto-retry with exponential backoff
- Max retries: 3 for sync jobs, 5 for critical jobs (billing)
- Alert via Sentry after final failure

**External API Calls**:
- Retry transient errors (timeouts, 5xx) up to 3 times
- Do not retry client errors (4xx)
- Circuit breaker pattern for repeated failures

## Testing Strategy

### Unit Tests

**Coverage Requirements**: 80% minimum for core business logic

**Key Test Areas**:
- Tenant resolution logic (by phone number, URL path)
- Signature verification (valid, invalid, missing)
- Intent classification and slot extraction
- Subscription status checks and feature limits
- Capacity calculation for appointment booking
- Transaction fee calculation
- Consent validation before message sending
- Template placeholder replacement

**Mocking Strategy**:
- Mock external APIs (Twilio, OpenAI, WooCommerce, Shopify)
- Use in-memory database for repository tests
- Mock Redis for rate limiting tests
```

### Integration Tests

**Test Scenarios**:
- End-to-end webhook flow: Twilio → Intent → Handler → Response
- Product sync from WooCommerce/Shopify test stores
- Appointment booking with capacity validation
- Order creation and wallet credit flow
- Campaign execution with consent filtering
- Subscription billing and status updates

**Test Environment**:
- Isolated test database
- Test Twilio account with sandbox numbers
- Mock WooCommerce/Shopify stores
- Test payment gateway (Stripe test mode)

### API Tests

**Automated API Testing**:
- Postman collection with all endpoints
- Test authentication (valid/invalid API keys)
- Test tenant isolation (cross-tenant access attempts)
- Test rate limiting
- Test pagination and filtering
- Test error responses

**Load Testing**:
- Simulate 100 concurrent webhook requests
- Test message throughput (1000 messages/minute)
- Test database query performance under load
- Identify bottlenecks and optimize

### Acceptance Tests

**Critical User Flows**:
1. Customer browses products and adds to cart
2. Customer checks service availability and books appointment
3. Customer opts out of promotional messages
4. Tenant syncs products from WooCommerce
5. Tenant creates and executes campaign
6. Tenant requests wallet withdrawal
7. Subscription billing succeeds/fails
8. Bot hands off to human agent

**Test Data**:
- Seed script with 3 test tenants (Starter, Growth, Enterprise)
- 50 products, 10 services per tenant
- 100 customers with varied consent preferences
- Historical messages and orders for analytics


## Security Considerations

### Multi-Tenant Data Isolation

**Database Level**:
- All queries MUST include tenant_id filter
- Use Django middleware to inject tenant context
- Row-level security policies in PostgreSQL
- Separate database schemas per tenant (future enhancement)

**Application Level**:
- Validate tenant_id in every API request
- Use tenant-scoped querysets in all repositories
- Prevent cross-tenant resource access via URL manipulation
- Audit log all cross-tenant access attempts

### PII Encryption

**Encrypted Fields**:
- Customer.phone_e164
- Tenant.twilio_sid, twilio_token, webhook_secret
- GlobalParty.phone_e164

**Encryption Method**:
- AES-256-GCM symmetric encryption
- Key rotation every 90 days
- Keys stored in environment variables or secrets manager
- Transparent encryption/decryption at ORM level

### API Security

**Authentication**:
- X-TENANT-ID + X-TENANT-API-KEY headers required
- API keys hashed with bcrypt before storage
- Support multiple API keys per tenant with names
- Key rotation without service interruption

**Rate Limiting**:
- Per-tenant limits based on subscription tier
- Redis-backed sliding window algorithm
- Separate limits for webhook vs. REST API
- Exponential backoff for repeated violations

**CORS**:
- Validate Origin header against tenant.allowed_origins
- Support wildcard for development environments
- Strict mode for production


### Webhook Security

**Signature Verification**:
- Validate X-Twilio-Signature on every webhook
- Use tenant-specific webhook_secret
- Reject requests with invalid or missing signatures
- Log all verification failures for security monitoring

**Replay Attack Prevention**:
- Track processed webhook IDs in Redis (24-hour TTL)
- Reject duplicate webhook deliveries
- Timestamp validation (reject if > 5 minutes old)

### Compliance

**GDPR/Privacy**:
- Customer data export API
- Right to be forgotten (data deletion)
- Consent audit trail with timestamps
- Data retention policies (configurable per tenant)

**WhatsApp Business Policy**:
- 24-hour messaging window enforcement
- Template message approval workflow
- Opt-out handling (STOP keyword)
- Spam prevention (rate limits, consent checks)

## Performance Optimization

### Caching Strategy

**Redis Cache**:
- Tenant configuration (TTL: 1 hour)
- Product/Service catalog (TTL: 15 minutes)
- Customer preferences (TTL: 5 minutes)
- Rate limit counters (TTL: 24 hours)
- Availability windows (TTL: 1 hour)

**Cache Invalidation**:
- Invalidate on write operations
- Use cache tags for bulk invalidation
- Lazy loading with cache-aside pattern

### Database Optimization

**Indexes**:
- Composite indexes on (tenant_id, frequently_queried_field)
- Covering indexes for common queries
- Partial indexes for filtered queries (e.g., is_active=true)

**Query Optimization**:
- Use select_related() for foreign keys
- Use prefetch_related() for reverse relations
- Avoid N+1 queries with eager loading
- Paginate large result sets (default: 50 items)

**Connection Pooling**:
- PgBouncer for connection pooling
- Max connections: 100
- Pool mode: transaction
```

### Async Processing

**Celery Tasks**:
- Product sync (WooCommerce, Shopify): 5-10 minutes
- Nightly analytics rollup: 30 minutes
- Campaign execution: 10-60 minutes depending on size
- Appointment reminders: Scheduled tasks
- Subscription billing: Daily at 2 AM

**Task Priorities**:
- High: Transactional messages, appointment reminders
- Medium: Campaign sends, analytics rollup
- Low: Product sync, data exports

**Queue Configuration**:
- Separate queues for different task types
- Dedicated workers for high-priority tasks
- Auto-scaling based on queue depth

### Monitoring & Observability

**Metrics (Prometheus)**:
- Request rate, latency, error rate per endpoint
- Webhook processing time
- Intent classification latency
- Message delivery success rate
- Database query performance
- Celery task execution time
- Cache hit/miss ratio

**Logging (Structured JSON)**:
- Request ID for tracing
- Tenant ID for filtering
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Sensitive data masking (phone numbers, API keys)

**Error Tracking (Sentry)**:
- Automatic error capture with stack traces
- User context (tenant_id, customer_id)
- Breadcrumbs for debugging
- Release tracking for deployments
- Performance monitoring

**Alerting**:
- High error rate (> 5% in 5 minutes)
- Slow response time (p95 > 2 seconds)
- Celery queue backlog (> 1000 tasks)
- Database connection pool exhaustion
- External API failures (Twilio, payment gateway)


## Deployment Architecture

### Infrastructure

**Application Servers**:
- Django app running on Gunicorn
- Horizontal scaling with load balancer
- Auto-scaling based on CPU/memory (min: 2, max: 10)
- Health check endpoint: /v1/health

**Background Workers**:
- Celery workers for async tasks
- Separate worker pools for different queues
- Auto-scaling based on queue depth

**Database**:
- PostgreSQL 14+ with replication
- Primary for writes, replicas for reads
- Automated backups (daily full, hourly incremental)
- Point-in-time recovery

**Cache & Queue**:
- Redis cluster for caching and Celery broker
- Sentinel for high availability
- Persistence enabled for critical data

**Storage**:
- S3-compatible object storage for media files
- CDN for static assets and images

### Environment Configuration

**Environment Variables**:
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/tulia
DATABASE_REPLICA_URL=postgresql://user:pass@replica:5432/tulia

# Redis
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/1

# Encryption
ENCRYPTION_KEY=base64-encoded-key

# External APIs
TWILIO_ACCOUNT_SID=default-sid
TWILIO_AUTH_TOKEN=default-token
OPENAI_API_KEY=sk-...

# Sentry
SENTRY_DSN=https://...

# Feature Flags
ENABLE_PAYMENT_FACILITATION=true
DEFAULT_TRIAL_DAYS=14
```

### Deployment Process

1. **Build**: Docker image with application code
2. **Test**: Run unit and integration tests
3. **Deploy**: Rolling deployment with zero downtime
4. **Migrate**: Run database migrations
5. **Verify**: Health checks and smoke tests
6. **Rollback**: Automatic rollback on failure


## API Endpoints Summary

### Webhooks
- `POST /v1/webhooks/twilio` - Receive inbound WhatsApp messages

### Messaging
- `POST /v1/messages/send` - Send outbound message
- `POST /v1/messages/schedule` - Schedule message for future delivery
- `GET /v1/messages/{id}` - Get message details

### Conversations
- `GET /v1/conversations` - List conversations
- `GET /v1/conversations/{id}` - Get conversation details
- `GET /v1/conversations/{id}/messages` - Get conversation messages
- `POST /v1/conversations/{id}/handoff` - Hand off to human agent

### Catalog - Products
- `POST /v1/catalog/sync/woocommerce` - Sync from WooCommerce
- `POST /v1/catalog/sync/shopify` - Sync from Shopify
- `GET /v1/products` - List products
- `GET /v1/products/{id}` - Get product details
- `POST /v1/products` - Create product (manual)
- `PUT /v1/products/{id}` - Update product
- `DELETE /v1/products/{id}` - Delete product

### Catalog - Services
- `POST /v1/services` - Create service
- `GET /v1/services` - List services
- `GET /v1/services/{id}` - Get service details
- `PUT /v1/services/{id}` - Update service
- `DELETE /v1/services/{id}` - Delete service
- `GET /v1/services/{id}/availability` - Get available slots

### Bookings
- `POST /v1/appointments` - Create appointment
- `GET /v1/appointments` - List appointments
- `GET /v1/appointments/{id}` - Get appointment details
- `POST /v1/appointments/{id}/cancel` - Cancel appointment
- `PUT /v1/appointments/{id}` - Update appointment

### Orders
- `POST /v1/orders` - Create order
- `GET /v1/orders` - List orders
- `GET /v1/orders/{id}` - Get order details
- `PUT /v1/orders/{id}` - Update order status

### Wallet
- `GET /v1/wallet/balance` - Get wallet balance
- `GET /v1/wallet/transactions` - List transactions
- `POST /v1/wallet/withdraw` - Request withdrawal

### Campaigns
- `POST /v1/campaigns` - Create campaign
- `GET /v1/campaigns` - List campaigns
- `GET /v1/campaigns/{id}` - Get campaign details
- `POST /v1/campaigns/{id}/execute` - Execute campaign
- `GET /v1/campaigns/{id}/report` - Get campaign report

### Templates
- `POST /v1/templates` - Create message template
- `GET /v1/templates` - List templates
- `GET /v1/templates/{id}` - Get template details
- `PUT /v1/templates/{id}` - Update template
- `DELETE /v1/templates/{id}` - Delete template

### Customers
- `GET /v1/customers` - List customers
- `GET /v1/customers/{id}` - Get customer details
- `GET /v1/customers/{id}/preferences` - Get consent preferences
- `PUT /v1/customers/{id}/preferences` - Update consent preferences

### Analytics
- `GET /v1/analytics/overview` - Get overview metrics
- `GET /v1/analytics/daily` - Get daily metrics
- `GET /v1/analytics/messaging` - Get messaging analytics
- `GET /v1/analytics/funnel` - Get conversion funnel

### Admin (Platform Operator)
- `GET /v1/admin/analytics/revenue` - Platform revenue analytics
- `GET /v1/admin/tenants` - List all tenants
- `POST /v1/admin/tenants/{id}/subscription` - Update tenant subscription
- `POST /v1/admin/wallet/withdrawals/{id}/process` - Process withdrawal

### Utilities
- `GET /v1/health` - Health check
- `GET /schema` - OpenAPI schema
- `GET /schema/swagger/` - Swagger UI
- `POST /v1/test/send-whatsapp` - Test message sending

### RBAC (Role-Based Access Control)
- `GET /v1/memberships/me` - List user's tenant memberships
- `POST /v1/memberships/{tenant_id}/invite` - Invite user to tenant (requires users:manage)
- `POST /v1/memberships/{tenant_id}/{user_id}/roles` - Assign role to user (requires users:manage)
- `DELETE /v1/memberships/{tenant_id}/{user_id}/roles/{role_id}` - Remove role from user (requires users:manage)
- `GET /v1/roles` - List tenant roles
- `POST /v1/roles` - Create custom role (requires users:manage)
- `GET /v1/roles/{id}` - Get role details
- `PUT /v1/roles/{id}` - Update role (requires users:manage)
- `DELETE /v1/roles/{id}` - Delete custom role (requires users:manage)
- `GET /v1/roles/{id}/permissions` - List role permissions
- `POST /v1/roles/{id}/permissions` - Add permission to role (requires users:manage)
- `DELETE /v1/roles/{id}/permissions/{permission_id}` - Remove permission from role (requires users:manage)
- `GET /v1/users/{id}/permissions` - List user permission overrides
- `POST /v1/users/{id}/permissions` - Grant/deny permission to user (requires users:manage)
- `DELETE /v1/users/{id}/permissions/{permission_id}` - Remove permission override (requires users:manage)
- `GET /v1/permissions` - List all available permissions
- `GET /v1/audit-logs` - List audit logs (requires analytics:view or dedicated audit:view)

## RBAC Architecture & Design

### Overview

The RBAC system provides multi-tenant admin access control with the following key features:
- **Global User Identity**: A single person can work across multiple tenants
- **Per-Tenant Roles**: Each tenant has its own set of roles with customizable permissions
- **Granular Permissions**: Fine-grained control over catalog, services, orders, finance, etc.
- **User-Level Overrides**: Grant or deny specific permissions to individual users
- **Four-Eyes Approval**: Financial operations require separate initiator and approver
- **Complete Audit Trail**: All RBAC changes and sensitive actions are logged

### Core RBAC Models

```python
class User(BaseModel):
    """Global user identity - can belong to multiple tenants"""
    id = UUIDField(primary_key=True)
    email = EmailField(unique=True)
    phone = EncryptedCharField(max_length=20, null=True)
    password_hash = CharField(max_length=255)
    is_active = BooleanField(default=True)
    is_superuser = BooleanField(default=False)  # Platform admin only
    two_factor_enabled = BooleanField(default=False)
    two_factor_secret = EncryptedCharField(max_length=255, null=True)
    last_login_at = DateTimeField(null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            Index(fields=['email']),
            Index(fields=['is_active']),
        ]

class TenantUser(BaseModel):
    """Association between User and Tenant with invite tracking"""
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant, on_delete=CASCADE)
    user = ForeignKey(User, on_delete=CASCADE)
    is_active = BooleanField(default=True)
    invite_status = CharField(
        max_length=20,
        choices=['pending', 'accepted', 'revoked'],
        default='pending'
    )
    invited_by = ForeignKey(User, null=True, related_name='invitations_sent')
    invited_at = DateTimeField(auto_now_add=True)
    joined_at = DateTimeField(null=True)
    last_seen_at = DateTimeField(null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('tenant', 'user')]
        indexes = [
            Index(fields=['tenant', 'user', 'is_active']),
            Index(fields=['user', 'is_active']),
            Index(fields=['invite_status']),
        ]

class Permission(BaseModel):
    """Global permission definitions - shared across all tenants"""
    id = UUIDField(primary_key=True)
    code = CharField(max_length=100, unique=True)  # e.g., "catalog:view"
    label = CharField(max_length=255)  # e.g., "View Catalog"
    description = TextField(null=True)
    category = CharField(max_length=50)  # e.g., "catalog", "finance", "users"
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['code']),
            Index(fields=['category']),
        ]

class Role(BaseModel):
    """Per-tenant role definitions"""
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant, on_delete=CASCADE)
    name = CharField(max_length=100)  # e.g., "Owner", "Catalog Manager"
    description = TextField(null=True)
    is_system = BooleanField(default=False)  # True for seeded default roles
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('tenant', 'name')]
        indexes = [
            Index(fields=['tenant', 'is_system']),
        ]

class RolePermission(BaseModel):
    """Maps permissions to roles"""
    id = UUIDField(primary_key=True)
    role = ForeignKey(Role, on_delete=CASCADE)
    permission = ForeignKey(Permission, on_delete=CASCADE)
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('role', 'permission')]
        indexes = [
            Index(fields=['role']),
            Index(fields=['permission']),
        ]

class UserPermission(BaseModel):
    """Per-user permission overrides (grant or deny)"""
    id = UUIDField(primary_key=True)
    tenant_user = ForeignKey(TenantUser, on_delete=CASCADE)
    permission = ForeignKey(Permission, on_delete=CASCADE)
    granted = BooleanField()  # True = grant, False = deny
    reason = TextField(null=True)  # Why this override was applied
    granted_by = ForeignKey(User, null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('tenant_user', 'permission')]
        indexes = [
            Index(fields=['tenant_user', 'granted']),
        ]

class AuditLog(BaseModel):
    """Comprehensive audit trail for RBAC and sensitive operations"""
    id = UUIDField(primary_key=True)
    tenant = ForeignKey(Tenant, null=True)  # Null for platform-level actions
    user = ForeignKey(User, null=True)  # Null for system actions
    action = CharField(max_length=100)  # e.g., "role_assigned", "permission_denied"
    target_type = CharField(max_length=50)  # e.g., "Role", "Product", "Withdrawal"
    target_id = UUIDField(null=True)
    diff = JSONField(default=dict)  # Before/after changes
    ip_address = GenericIPAddressField(null=True)
    user_agent = TextField(null=True)
    request_id = UUIDField(null=True)
    metadata = JSONField(default=dict)
    
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            Index(fields=['tenant', 'created_at']),
            Index(fields=['user', 'created_at']),
            Index(fields=['action', 'created_at']),
            Index(fields=['target_type', 'target_id']),
            Index(fields=['request_id']),
        ]
```

### RBAC Service Component

**Responsibility**: Resolve user scopes, manage permissions, validate four-eyes

**Key Methods**:

```python
class RBACService:
    def resolve_scopes(self, tenant_user: TenantUser) -> Set[str]:
        """
        Resolve all permission codes for a TenantUser.
        
        Algorithm:
        1. Get all roles assigned to tenant_user
        2. Aggregate permissions from all roles
        3. Apply user-level overrides:
           - granted=True: add permission
           - granted=False: remove permission (deny wins)
        4. Return set of permission codes
        """
        scopes = set()
        
        # Get permissions from roles
        roles = tenant_user.roles.all()
        for role in roles:
            role_perms = RolePermission.objects.filter(role=role).select_related('permission')
            scopes.update(rp.permission.code for rp in role_perms)
        
        # Apply user-level overrides
        user_perms = UserPermission.objects.filter(tenant_user=tenant_user).select_related('permission')
        for up in user_perms:
            if up.granted:
                scopes.add(up.permission.code)
            else:
                scopes.discard(up.permission.code)  # Deny wins
        
        return scopes
    
    def grant_permission(self, tenant_user: TenantUser, permission_code: str, granted_by: User, reason: str = None):
        """Grant a permission to a specific user (override)"""
        permission = Permission.objects.get(code=permission_code)
        UserPermission.objects.update_or_create(
            tenant_user=tenant_user,
            permission=permission,
            defaults={'granted': True, 'granted_by': granted_by, 'reason': reason}
        )
        
        # Audit log
        AuditLog.objects.create(
            tenant=tenant_user.tenant,
            user=granted_by,
            action='permission_granted',
            target_type='UserPermission',
            target_id=tenant_user.id,
            diff={'permission': permission_code, 'reason': reason}
        )
    
    def deny_permission(self, tenant_user: TenantUser, permission_code: str, granted_by: User, reason: str):
        """Deny a permission for a specific user (override)"""
        permission = Permission.objects.get(code=permission_code)
        UserPermission.objects.update_or_create(
            tenant_user=tenant_user,
            permission=permission,
            defaults={'granted': False, 'granted_by': granted_by, 'reason': reason}
        )
        
        # Audit log
        AuditLog.objects.create(
            tenant=tenant_user.tenant,
            user=granted_by,
            action='permission_denied',
            target_type='UserPermission',
            target_id=tenant_user.id,
            diff={'permission': permission_code, 'reason': reason}
        )
    
    def validate_four_eyes(self, initiator: User, approver: User, action: str):
        """
        Validate four-eyes control for sensitive operations.
        Raises ValidationError if same user or other violations.
        """
        if initiator.id == approver.id:
            raise ValidationError(
                f"Cannot approve own {action}. Four-eyes control requires different users.",
                code='same_user_approval'
            )
        
        # Additional checks can be added here
        # e.g., check if approver has required permission
    
    def assign_role(self, tenant_user: TenantUser, role: Role, assigned_by: User):
        """Assign a role to a tenant user"""
        tenant_user.roles.add(role)
        
        # Audit log
        AuditLog.objects.create(
            tenant=tenant_user.tenant,
            user=assigned_by,
            action='role_assigned',
            target_type='TenantUser',
            target_id=tenant_user.id,
            diff={'role_id': str(role.id), 'role_name': role.name}
        )
    
    def remove_role(self, tenant_user: TenantUser, role: Role, removed_by: User):
        """Remove a role from a tenant user"""
        tenant_user.roles.remove(role)
        
        # Audit log
        AuditLog.objects.create(
            tenant=tenant_user.tenant,
            user=removed_by,
            action='role_removed',
            target_type='TenantUser',
            target_id=tenant_user.id,
            diff={'role_id': str(role.id), 'role_name': role.name}
        )
```

### Middleware Enhancement

**TenantContextMiddleware** (enhanced for RBAC):

```python
class TenantContextMiddleware:
    def __call__(self, request):
        # Extract tenant ID from header
        tenant_id = request.headers.get('X-TENANT-ID')
        
        if not tenant_id:
            return JsonResponse({'error': 'X-TENANT-ID header required'}, status=400)
        
        # Resolve tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id, status='active')
        except Tenant.DoesNotExist:
            return JsonResponse({'error': 'Invalid tenant'}, status=404)
        
        # Validate API key (existing logic)
        # ...
        
        # Validate membership
        try:
            tenant_user = TenantUser.objects.get(
                tenant=tenant,
                user=request.user,
                is_active=True,
                invite_status='accepted'
            )
        except TenantUser.DoesNotExist:
            return JsonResponse({'error': 'Not a member of this tenant'}, status=403)
        
        # Resolve scopes
        rbac_service = RBACService()
        scopes = rbac_service.resolve_scopes(tenant_user)
        
        # Attach to request
        request.tenant = tenant
        request.membership = tenant_user
        request.scopes = scopes
        
        # Update last_seen_at
        tenant_user.last_seen_at = timezone.now()
        tenant_user.save(update_fields=['last_seen_at'])
        
        return self.get_response(request)
```

### Permission Class

**HasTenantScopes** DRF permission class:

```python
class HasTenantScopes(BasePermission):
    """
    DRF permission class that checks if user has required scopes.
    Views must define required_scopes attribute.
    """
    
    def has_permission(self, request, view):
        # Get required scopes from view
        required_scopes = getattr(view, 'required_scopes', None)
        
        if required_scopes is None:
            # No scopes defined = deny by default
            return False
        
        # Get user's scopes from request (set by middleware)
        user_scopes = getattr(request, 'scopes', set())
        
        # Check if all required scopes are present
        if isinstance(required_scopes, str):
            required_scopes = [required_scopes]
        
        missing_scopes = set(required_scopes) - user_scopes
        
        if missing_scopes:
            # Log the denial
            logger.warning(
                f"Permission denied: user {request.user.id} missing scopes {missing_scopes}",
                extra={'request_id': request.request_id, 'tenant_id': request.tenant.id}
            )
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Ensure object belongs to request.tenant
        if hasattr(obj, 'tenant_id'):
            return obj.tenant_id == request.tenant.id
        if hasattr(obj, 'tenant'):
            return obj.tenant.id == request.tenant.id
        return True

def requires_scopes(*scopes):
    """Decorator to set required_scopes on a view"""
    def decorator(view_class):
        view_class.required_scopes = scopes
        view_class.permission_classes = [HasTenantScopes]
        return view_class
    return decorator
```

### Seeder Implementation

**Management Commands**:

```python
# management/commands/seed_permissions.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        permissions = [
            ('catalog:view', 'View Catalog', 'View products and services', 'catalog'),
            ('catalog:edit', 'Edit Catalog', 'Create and edit products and services', 'catalog'),
            ('services:view', 'View Services', 'View bookable services', 'services'),
            ('services:edit', 'Edit Services', 'Create and edit services', 'services'),
            ('availability:edit', 'Edit Availability', 'Manage service availability windows', 'services'),
            ('conversations:view', 'View Conversations', 'View customer conversations', 'conversations'),
            ('handoff:perform', 'Perform Handoff', 'Transfer conversations to human agents', 'conversations'),
            ('orders:view', 'View Orders', 'View customer orders', 'orders'),
            ('orders:edit', 'Edit Orders', 'Update order status and details', 'orders'),
            ('appointments:view', 'View Appointments', 'View service bookings', 'appointments'),
            ('appointments:edit', 'Edit Appointments', 'Manage service bookings', 'appointments'),
            ('analytics:view', 'View Analytics', 'Access analytics and reports', 'analytics'),
            ('finance:view', 'View Finance', 'View wallet and transactions', 'finance'),
            ('finance:withdraw:initiate', 'Initiate Withdrawal', 'Request wallet withdrawals', 'finance'),
            ('finance:withdraw:approve', 'Approve Withdrawal', 'Approve withdrawal requests', 'finance'),
            ('finance:reconcile', 'Reconcile Finance', 'Perform financial reconciliation', 'finance'),
            ('integrations:manage', 'Manage Integrations', 'Configure external integrations', 'integrations'),
            ('users:manage', 'Manage Users', 'Invite users and assign roles', 'users'),
        ]
        
        for code, label, description, category in permissions:
            Permission.objects.get_or_create(
                code=code,
                defaults={
                    'label': label,
                    'description': description,
                    'category': category
                }
            )
        
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(permissions)} permissions'))

# management/commands/seed_tenant_roles.py
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Tenant ID')
        parser.add_argument('--all', action='store_true', help='Seed all tenants')
    
    def handle(self, *args, **options):
        if options['all']:
            tenants = Tenant.objects.filter(status='active')
        elif options['tenant']:
            tenants = [Tenant.objects.get(id=options['tenant'])]
        else:
            raise CommandError('Specify --tenant=<id> or --all')
        
        for tenant in tenants:
            self.seed_roles_for_tenant(tenant)
    
    def seed_roles_for_tenant(self, tenant):
        # Get all permissions
        all_perms = set(Permission.objects.values_list('code', flat=True))
        
        # Define role mappings
        role_mappings = {
            'Owner': all_perms,
            'Admin': all_perms - {'finance:withdraw:approve'},  # Configurable
            'Finance Admin': {'analytics:view', 'finance:view', 'finance:withdraw:initiate', 
                             'finance:withdraw:approve', 'finance:reconcile', 'orders:view'},
            'Catalog Manager': {'analytics:view', 'catalog:view', 'catalog:edit', 
                               'services:view', 'services:edit', 'availability:edit'},
            'Support Lead': {'conversations:view', 'handoff:perform', 'orders:view', 'appointments:view'},
            'Analyst': {'analytics:view', 'catalog:view', 'services:view', 'orders:view', 'appointments:view'},
        }
        
        for role_name, perm_codes in role_mappings.items():
            role, created = Role.objects.get_or_create(
                tenant=tenant,
                name=role_name,
                defaults={'is_system': True, 'description': f'System-seeded {role_name} role'}
            )
            
            if created or not role.permissions.exists():
                # Add permissions
                permissions = Permission.objects.filter(code__in=perm_codes)
                for perm in permissions:
                    RolePermission.objects.get_or_create(role=role, permission=perm)
        
        self.stdout.write(self.style.SUCCESS(f'Seeded roles for tenant {tenant.name}'))
```

### Testing Strategy

**Unit Tests**:
- Scope resolution with multiple roles
- Deny overrides win over role grants
- Four-eyes validation (same user rejection)
- Permission inheritance and aggregation

**API Tests**:
- GET /v1/products requires catalog:view (403 without)
- POST /v1/products requires catalog:edit (403 without)
- Finance withdrawal initiate/approve with different users
- Cross-tenant access attempts return 403
- User with membership in multiple tenants sees correct data per tenant

**Integration Tests**:
- Complete user journey: invite → accept → assign role → access resources
- Role change immediately affects permissions
- User permission override immediately affects access
- Audit logs created for all RBAC changes

## Future Enhancements

### Phase 2: Meta WABA Migration
- Direct integration with Meta WhatsApp Business API
- Cloud API for better reliability and features
- Message templates management
- Business profile configuration

### Phase 3: Advanced Features
- Multi-agent support with routing rules
- Voice message transcription
- Image recognition for product search
- Payment gateway integration (Stripe, PayPal)
- Inventory management sync
- Customer segmentation and cohort analysis
- Predictive analytics for churn prevention

### Phase 4: Platform Expansion
- SMS channel support
- Telegram integration
- Web chat widget
- Mobile app for tenant dashboard
- White-label solution for agencies
