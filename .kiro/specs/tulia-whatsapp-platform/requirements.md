# Requirements Document

## Introduction

This document defines the requirements for Tulia AI, a multi-tenant WhatsApp-based commerce and services platform. Tulia enables businesses to sell both physical products and bookable services through WhatsApp conversations powered by AI. The system integrates with Twilio for WhatsApp messaging, WooCommerce and Shopify for product catalogs, and provides native service booking capabilities with availability management. The platform enforces strict multi-tenant isolation, ensuring each business operates independently with separate customer data, catalogs, and analytics.

The platform implements comprehensive Role-Based Access Control (RBAC) allowing tenant owners to invite team members and assign granular permissions. A single user can work across multiple tenants with different roles, and the system enforces four-eyes approval for sensitive financial operations. All RBAC changes are audited for compliance and security.

## Glossary

- **Tulia System**: The complete multi-tenant WhatsApp commerce and services backend platform
- **Tenant**: An isolated business account with unique WhatsApp number, API keys, catalogs, and customer data
- **Customer**: A WhatsApp user identified uniquely by (tenant_id, phone_e164) within a Tenant
- **GlobalParty**: An internal-only entity linking the same phone number across multiple Tenants for deduplication
- **Conversation**: A chat session between a Customer and a Tenant through WhatsApp with state tracking
- **Message**: An individual text or media communication within a Conversation
- **Product**: A physical item available for purchase, synchronized from WooCommerce or Shopify
- **ProductVariant**: A specific configuration of a Product with distinct SKU, price, or attributes
- **Service**: A bookable offering (e.g., haircut, consultation) with duration and pricing
- **ServiceVariant**: A specific configuration of a Service with distinct duration, price, or attributes
- **AvailabilityWindow**: A time slot when a Service can be booked, defined by weekday/date, time range, and capacity
- **Appointment**: A confirmed booking for a Service at a specific date and time
- **IntentService**: The AI component that classifies customer messages into actionable intents
- **WebhookHandler**: The component that receives and processes incoming Twilio WhatsApp messages
- **TwilioService**: The integration service for sending and receiving WhatsApp messages via Twilio
- **WooService**: The integration service for synchronizing products from WooCommerce stores
- **ShopifyService**: The integration service for synchronizing products from Shopify stores
- **AnalyticsService**: The component that aggregates metrics for messages, orders, bookings, and conversions
- **Cart**: A temporary collection of Products that a Customer intends to purchase
- **Order**: A completed purchase transaction containing Products with payment and fulfillment status
- **WebhookLog**: An audit record of all incoming webhook requests with payload and processing status
- **IntentEvent**: A record of AI intent classification results with confidence scores and extracted slots
- **Subscription**: A recurring payment plan that grants a Tenant access to platform features based on tier
- **SubscriptionTier**: A pricing level (Starter, Growth, Enterprise) with specific feature limits and capabilities
- **FreeTrial**: A time-limited period during which a Tenant can use the platform without payment
- **TenantWallet**: A financial account holding funds from facilitated transactions available for withdrawal
- **Transaction**: A record of money movement including customer payments, platform fees, and tenant payouts
- **TransactionFee**: A percentage or fixed amount charged by the platform for facilitating payments
- **BillingCycle**: The recurring period (monthly or yearly) for subscription charges
- **SubscriptionDiscount**: A percentage or fixed reduction applied to subscription pricing
- **AutomatedMessage**: A system-triggered message sent based on events like payment status, shipment updates, or booking reminders
- **ScheduledMessage**: A message planned for future delivery, typically for marketing campaigns or promotional offers
- **MessageTemplate**: A reusable message format with placeholders for personalization
- **CustomerPreferences**: Settings that control what types of messages a Customer consents to receive
- **ConsentType**: A category of messaging that requires explicit customer opt-in (transactional, promotional, reminders)
- **MessageCampaign**: A scheduled broadcast to multiple Customers with tracking for delivery and engagement
- **User**: A global identity representing a person who can access one or more Tenants with different roles
- **TenantUser**: An association record linking a User to a Tenant with invite status and activity tracking
- **Permission**: A global capability definition identified by a unique code (e.g., catalog:view, finance:withdraw:approve)
- **Role**: A per-tenant collection of Permissions that can be assigned to TenantUsers
- **RolePermission**: A mapping that grants a specific Permission to a Role
- **UserPermission**: A per-user override that grants or denies a specific Permission, overriding Role assignments
- **AuditLog**: A record of RBAC changes and sensitive actions including who, what, when, and context details
- **Scope**: A permission code that a User has been granted through Roles or UserPermissions for a specific Tenant
- **TenantContextMiddleware**: Middleware that resolves tenant context, validates membership, and assembles user scopes
- **HasTenantScopes**: A DRF permission class that enforces scope requirements on API endpoints
- **FourEyes**: A security pattern requiring two different users to initiate and approve sensitive operations

## Requirements

### Requirement 1

**User Story:** As a platform operator, I want strict multi-tenant isolation by (tenant_id, phone_e164), so that customer data never leaks across businesses

#### Acceptance Criteria

1. WHEN a Customer record is created, THE Tulia System SHALL enforce uniqueness by the combination of tenant_id and phone_e164
2. WHEN a query retrieves Customer records, THE Tulia System SHALL filter results to include only records matching the authenticated Tenant
3. WHEN a query retrieves Conversation records, THE Tulia System SHALL filter results to include only records matching the authenticated Tenant
4. WHEN a query retrieves Product records, THE Tulia System SHALL filter results to include only records matching the authenticated Tenant
5. WHEN a query retrieves Service records, THE Tulia System SHALL filter results to include only records matching the authenticated Tenant
6. WHEN a query retrieves Order records, THE Tulia System SHALL filter results to include only records matching the authenticated Tenant
7. WHEN a query retrieves Appointment records, THE Tulia System SHALL filter results to include only records matching the authenticated Tenant
8. WHEN an API request includes X-TENANT-ID header, THE Tulia System SHALL validate the corresponding X-TENANT-API-KEY before processing

### Requirement 2

**User Story:** As a business owner, I want inbound WhatsApp messages automatically routed to my tenant account, so that my customers reach the correct business context

#### Acceptance Criteria

1. WHEN the WebhookHandler receives a Twilio webhook with a "To" number mapped to a Tenant, THE Tulia System SHALL resolve the request to that Tenant
2. WHEN the WebhookHandler receives a Twilio webhook with an unmapped "To" number, THE Tulia System SHALL attempt resolution using the webhook URL path mapping
3. WHEN the WebhookHandler cannot resolve a Tenant from either method, THE Tulia System SHALL return HTTP status code 404
4. WHEN the WebhookHandler resolves a Tenant successfully, THE Tulia System SHALL verify the Twilio signature using the Tenant's webhook_secret
5. WHEN the Twilio signature verification fails, THE Tulia System SHALL return HTTP status code 401

### Requirement 3

**User Story:** As a customer, I want my conversation history maintained separately per business, so that my interactions with different businesses remain independent

#### Acceptance Criteria

1. WHEN a Customer sends a message to Tenant A, THE Tulia System SHALL create or retrieve a Conversation scoped to (Tenant A, Customer)
2. WHEN the same phone number sends a message to Tenant B, THE Tulia System SHALL create or retrieve a separate Conversation scoped to (Tenant B, Customer)
3. WHEN retrieving Conversation history, THE Tulia System SHALL return only Messages associated with the specific (Tenant, Customer) Conversation
4. WHEN a GlobalParty links the same phone number across Tenants, THE Tulia System SHALL NOT expose cross-tenant Conversation data through any API

### Requirement 4

**User Story:** As a customer, I want to browse available products through natural language WhatsApp messages, so that I can discover items to purchase

#### Acceptance Criteria

1. WHEN a Customer sends a message with BROWSE_PRODUCTS intent, THE IntentService SHALL classify the intent with confidence score above 0.7
2. WHEN the BROWSE_PRODUCTS intent is detected, THE Tulia System SHALL query active Products for the Tenant
3. WHEN Products are found matching the query, THE Tulia System SHALL return a formatted list with product names and prices
4. WHEN no Products match the query, THE Tulia System SHALL return a message indicating no results found
5. WHEN the BROWSE_PRODUCTS handler completes, THE Tulia System SHALL create an IntentEvent record with intent name and extracted slots

### Requirement 5

**User Story:** As a customer, I want to check product details and pricing through WhatsApp, so that I can make informed purchase decisions

#### Acceptance Criteria

1. WHEN a Customer sends a message with PRODUCT_DETAILS intent containing a product_query slot, THE IntentService SHALL extract the product identifier
2. WHEN the PRODUCT_DETAILS intent is detected, THE Tulia System SHALL retrieve the Product matching the query for the Tenant
3. WHEN the Product is found, THE Tulia System SHALL return details including name, description, price, currency, and available ProductVariants
4. WHEN the Product has stock information, THE Tulia System SHALL include stock availability in the response
5. WHEN the Product is not found, THE Tulia System SHALL return a message indicating the product is unavailable

### Requirement 6

**User Story:** As a customer, I want to add products with specific variants to my cart through conversational messages, so that I can build my order naturally

#### Acceptance Criteria

1. WHEN a Customer sends a message with ADD_TO_CART intent, THE IntentService SHALL extract product_id, variant_id, and quantity slots
2. WHEN the ADD_TO_CART intent is detected with valid slots, THE Tulia System SHALL create or update a Cart for the Conversation
3. WHEN adding a ProductVariant to the Cart, THE Tulia System SHALL validate that the variant belongs to the specified Product
4. WHEN the Cart operation succeeds, THE Tulia System SHALL return the updated Cart state with item count and subtotal
5. WHEN the specified ProductVariant is out of stock, THE Tulia System SHALL return an error message and NOT add the item to the Cart

### Requirement 7

**User Story:** As a customer, I want to complete my purchase and receive a checkout link, so that I can pay for my cart items

#### Acceptance Criteria

1. WHEN a Customer sends a message with CHECKOUT_LINK intent, THE Tulia System SHALL retrieve the active Cart for the Conversation
2. WHEN the Cart contains items, THE Tulia System SHALL create an Order with status "draft" containing all Cart items
3. WHEN the Order is created, THE Tulia System SHALL calculate subtotal, shipping, and total amounts in the Tenant's currency
4. WHEN the Order is created, THE Tulia System SHALL generate a payment checkout link
5. WHEN the checkout link is generated, THE Tulia System SHALL return the link to the Customer via WhatsApp message

### Requirement 8

**User Story:** As a business owner, I want my WooCommerce product catalog automatically synchronized to Tulia, so that customers can browse current inventory

#### Acceptance Criteria

1. WHEN the WooService executes a sync operation, THE Tulia System SHALL authenticate using the Tenant's WooCommerce API credentials
2. WHEN the WooService retrieves products, THE Tulia System SHALL fetch products in batches of 100 items
3. WHEN a WooCommerce product is imported, THE Tulia System SHALL create or update a Product record with external_source "woocommerce"
4. WHEN a WooCommerce product has variations, THE Tulia System SHALL create ProductVariant records for each variation
5. WHEN the sync operation completes, THE Tulia System SHALL log the operation status and item count

### Requirement 9

**User Story:** As a business owner, I want my Shopify product catalog automatically synchronized to Tulia, so that customers can browse current inventory

#### Acceptance Criteria

1. WHEN the ShopifyService executes a sync operation, THE Tulia System SHALL authenticate using the Tenant's Shopify access token
2. WHEN the ShopifyService retrieves products, THE Tulia System SHALL fetch products in batches of 100 items
3. WHEN a Shopify product is imported, THE Tulia System SHALL create or update a Product record with external_source "shopify"
4. WHEN a Shopify product has variants, THE Tulia System SHALL create ProductVariant records for each variant
5. WHEN the sync operation completes, THE Tulia System SHALL log the operation status and item count

### Requirement 10

**User Story:** As a service provider, I want to define bookable services with variants, so that customers can book appointments for different service types

#### Acceptance Criteria

1. WHEN a Tenant creates a Service via POST /v1/services, THE Tulia System SHALL validate required fields including title and is_active
2. WHEN a Service is created, THE Tulia System SHALL associate the Service with the authenticated Tenant
3. WHEN a Service is created with ServiceVariants, THE Tulia System SHALL validate that each variant has a title and duration_minutes
4. WHEN a Service is created, THE Tulia System SHALL store optional fields including description, images, base_price, and currency
5. WHEN a Service is retrieved via GET /v1/services/{id}, THE Tulia System SHALL return the Service only if it belongs to the authenticated Tenant

### Requirement 11

**User Story:** As a service provider, I want to define availability windows for my services, so that customers can only book during my operating hours

#### Acceptance Criteria

1. WHEN a Tenant creates an AvailabilityWindow, THE Tulia System SHALL validate that service_id references an existing Service for the Tenant
2. WHEN an AvailabilityWindow is created, THE Tulia System SHALL require weekday or date, start_time, end_time, capacity, and timezone
3. WHEN an AvailabilityWindow is created with weekday, THE Tulia System SHALL validate weekday is an integer between 0 and 6
4. WHEN an AvailabilityWindow is created, THE Tulia System SHALL validate that end_time is after start_time
5. WHEN retrieving availability via GET /v1/services/{id}/availability, THE Tulia System SHALL merge all AvailabilityWindows for the Service within the requested date range

### Requirement 12

**User Story:** As a customer, I want to search for available appointment slots through WhatsApp, so that I can find convenient booking times

#### Acceptance Criteria

1. WHEN a Customer sends a message with CHECK_AVAILABILITY intent, THE IntentService SHALL extract service_id, date, and time_range slots
2. WHEN the CHECK_AVAILABILITY intent is detected, THE Tulia System SHALL query AvailabilityWindows for the specified Service
3. WHEN AvailabilityWindows are found, THE Tulia System SHALL filter slots within the requested date and time range
4. WHEN calculating available slots, THE Tulia System SHALL exclude times with existing Appointments that exceed capacity
5. WHEN available slots are found, THE Tulia System SHALL return up to 5 slot options with start_dt, end_dt, and capacity_left

### Requirement 13

**User Story:** As a customer, I want to book an appointment for a service through WhatsApp, so that I can secure my preferred time slot

#### Acceptance Criteria

1. WHEN a Customer sends a message with BOOK_APPOINTMENT intent, THE IntentService SHALL extract service_id, variant_id, date, time, and notes slots
2. WHEN the BOOK_APPOINTMENT intent is detected, THE Tulia System SHALL validate that the requested slot falls within an AvailabilityWindow
3. WHEN validating the booking, THE Tulia System SHALL verify that existing Appointments for the slot do not exceed capacity
4. WHEN the slot is available, THE Tulia System SHALL create an Appointment with status "pending" or "confirmed"
5. WHEN the Appointment is created, THE Tulia System SHALL return confirmation details including service name, date, time, and appointment ID
6. WHEN the requested slot is unavailable, THE Tulia System SHALL propose up to 3 alternative available slots

### Requirement 14

**User Story:** As a customer, I want to cancel my appointment through WhatsApp, so that I can free up the slot if my plans change

#### Acceptance Criteria

1. WHEN a Customer sends a message with CANCEL_APPOINTMENT intent, THE IntentService SHALL extract the appointment identifier
2. WHEN the CANCEL_APPOINTMENT intent is detected, THE Tulia System SHALL retrieve the Appointment for the Customer and Tenant
3. WHEN the Appointment is found with status "pending" or "confirmed", THE Tulia System SHALL update the status to "canceled"
4. WHEN the Appointment status is updated, THE Tulia System SHALL return a cancellation confirmation message
5. WHEN the Appointment is not found or already canceled, THE Tulia System SHALL return an appropriate error message

### Requirement 15

**User Story:** As a customer, I want to request human assistance when the bot cannot help, so that I can get personalized support

#### Acceptance Criteria

1. WHEN a Customer sends a message with HUMAN_HANDOFF intent, THE IntentService SHALL classify the intent with confidence score above 0.7
2. WHEN the HUMAN_HANDOFF intent is detected, THE Tulia System SHALL update the Conversation status to "handoff"
3. WHEN the Conversation status changes to "handoff", THE Tulia System SHALL send a message to the Customer confirming that an agent will assist
4. WHEN the IntentService fails to classify an intent after 2 attempts, THE Tulia System SHALL automatically trigger HUMAN_HANDOFF
5. WHEN a Conversation is in "handoff" status, THE Tulia System SHALL NOT process further messages with the IntentService

### Requirement 16

**User Story:** As a business owner, I want to view analytics for messages, orders, and bookings, so that I can track business performance

#### Acceptance Criteria

1. WHEN a Tenant requests GET /v1/analytics/overview, THE Tulia System SHALL return metrics aggregated for the authenticated Tenant only
2. WHEN analytics are requested with range parameter "7d", THE Tulia System SHALL aggregate data from the past 7 days
3. WHEN analytics are requested with range parameter "30d", THE Tulia System SHALL aggregate data from the past 30 days
4. WHEN returning analytics, THE Tulia System SHALL include msgs_in, msgs_out, conversations, orders, revenue, and bookings counts
5. WHEN returning analytics for services, THE Tulia System SHALL include booking_conversion_rate and no_show_rate metrics
6. WHEN returning analytics, THE Tulia System SHALL include avg_first_response_secs and handoffs counts

### Requirement 17

**User Story:** As a business owner, I want daily analytics rollup executed automatically, so that I can access historical performance data efficiently

#### Acceptance Criteria

1. WHEN the nightly analytics rollup task executes, THE Tulia System SHALL aggregate metrics for each Tenant independently
2. WHEN aggregating daily metrics, THE Tulia System SHALL create or update AnalyticsDaily records with date and tenant_id
3. WHEN calculating daily metrics, THE Tulia System SHALL count msgs_in, msgs_out, enquiries, orders, and bookings
4. WHEN calculating revenue, THE Tulia System SHALL sum Order totals with status "paid" or "fulfilled"
5. WHEN calculating booking_conversion_rate, THE Tulia System SHALL divide confirmed bookings by total CHECK_AVAILABILITY intents
6. WHEN calculating no_show_rate, THE Tulia System SHALL divide Appointments with status "no_show" by total confirmed Appointments

### Requirement 18

**User Story:** As a platform operator, I want all webhook requests logged with payload and status, so that I can audit and troubleshoot integration issues

#### Acceptance Criteria

1. WHEN the WebhookHandler receives a Twilio request, THE Tulia System SHALL create a WebhookLog record before processing
2. WHEN creating a WebhookLog, THE Tulia System SHALL store provider "twilio", event type, full payload, and received_at timestamp
3. WHEN webhook processing succeeds, THE Tulia System SHALL update the WebhookLog status to "success"
4. WHEN webhook processing fails, THE Tulia System SHALL update the WebhookLog status to "error" and store the error message
5. WHEN a WebhookLog is created, THE Tulia System SHALL associate it with the resolved Tenant if available

### Requirement 19

**User Story:** As a platform operator, I want Twilio webhook signatures verified, so that only authentic WhatsApp messages are processed

#### Acceptance Criteria

1. WHEN the WebhookHandler receives a request, THE Tulia System SHALL extract the X-Twilio-Signature header
2. WHEN verifying the signature, THE Tulia System SHALL use the Tenant's twilio_token as the secret key
3. WHEN the computed signature matches the X-Twilio-Signature header, THE Tulia System SHALL proceed with message processing
4. WHEN the computed signature does not match, THE Tulia System SHALL return HTTP status code 401
5. WHEN signature verification fails, THE Tulia System SHALL log the failure in the WebhookLog with status "unauthorized"

### Requirement 20

**User Story:** As a platform operator, I want PII data encrypted at rest, so that customer phone numbers are protected from unauthorized access

#### Acceptance Criteria

1. WHEN a Customer record is created with phone_e164, THE Tulia System SHALL encrypt the phone number before storing in the database
2. WHEN a Customer record is retrieved, THE Tulia System SHALL decrypt the phone_e164 field transparently
3. WHEN querying Customers by phone_e164, THE Tulia System SHALL support encrypted field lookups
4. WHEN audit logs include Customer data, THE Tulia System SHALL mask or exclude encrypted PII fields
5. WHEN exporting data, THE Tulia System SHALL provide options to exclude or mask PII fields

### Requirement 21

**User Story:** As a developer, I want comprehensive REST API documentation with OpenAPI schema, so that I can integrate with Tulia efficiently

#### Acceptance Criteria

1. THE Tulia System SHALL generate an OpenAPI 3.0 schema at /schema endpoint
2. WHEN accessing /schema/swagger/, THE Tulia System SHALL render an interactive Swagger UI documentation
3. WHEN the OpenAPI schema is generated, THE Tulia System SHALL include all public API endpoints with request and response schemas
4. WHEN the OpenAPI schema is generated, THE Tulia System SHALL document required headers including X-TENANT-ID and X-TENANT-API-KEY
5. WHEN the OpenAPI schema is generated, THE Tulia System SHALL include example requests and responses for each endpoint

### Requirement 22

**User Story:** As a platform operator, I want rate limiting applied per tenant, so that no single business can overwhelm the system

#### Acceptance Criteria

1. WHEN a Tenant makes API requests, THE Tulia System SHALL track request count per tenant per time window
2. WHEN a Tenant exceeds the rate limit threshold, THE Tulia System SHALL return HTTP status code 429
3. WHEN returning a 429 response, THE Tulia System SHALL include Retry-After header indicating when requests can resume
4. WHEN rate limiting is applied, THE Tulia System SHALL use the X-TENANT-ID header to identify the Tenant
5. WHEN a Tenant is rate limited, THE Tulia System SHALL log the event for monitoring and alerting

### Requirement 23

**User Story:** As a developer, I want health check endpoints, so that I can monitor system availability and dependencies

#### Acceptance Criteria

1. WHEN GET /v1/health is requested, THE Tulia System SHALL return HTTP status code 200 if all critical services are operational
2. WHEN checking health, THE Tulia System SHALL verify database connectivity
3. WHEN checking health, THE Tulia System SHALL verify Redis connectivity
4. WHEN checking health, THE Tulia System SHALL verify Celery worker availability
5. WHEN any critical dependency is unavailable, THE Tulia System SHALL return HTTP status code 503 with details

### Requirement 24

**User Story:** As a business owner, I want to send outbound WhatsApp messages to customers, so that I can proactively communicate updates

#### Acceptance Criteria

1. WHEN a Tenant calls POST /v1/messages/send, THE Tulia System SHALL validate that the recipient Customer belongs to the Tenant
2. WHEN sending an outbound message, THE Tulia System SHALL use the TwilioService to deliver the message via the Tenant's WhatsApp number
3. WHEN the message is sent successfully, THE Tulia System SHALL create a Message record with direction "out"
4. WHEN the message send fails, THE Tulia System SHALL return an error response with the failure reason
5. WHEN sending a message, THE Tulia System SHALL support both plain text and Twilio message templates

### Requirement 25

**User Story:** As a platform operator, I want background jobs to log start, stop, and status, so that I can monitor asynchronous operations

#### Acceptance Criteria

1. WHEN a Celery task starts execution, THE Tulia System SHALL log the task name, task_id, and start timestamp
2. WHEN a Celery task completes successfully, THE Tulia System SHALL log the task_id, completion timestamp, and result summary
3. WHEN a Celery task fails, THE Tulia System SHALL log the task_id, failure timestamp, and error details
4. WHEN a Celery task fails, THE Tulia System SHALL send the error to Sentry for alerting
5. WHEN a Celery task is retried, THE Tulia System SHALL log the retry attempt number and reason


### Requirement 26

**User Story:** As a platform operator, I want to define subscription tiers with different feature limits, so that I can offer pricing options that match business needs

#### Acceptance Criteria

1. THE Tulia System SHALL support three SubscriptionTiers named "Starter", "Growth", and "Enterprise"
2. WHEN a SubscriptionTier is defined, THE Tulia System SHALL specify monthly_price, yearly_price, and feature limits
3. WHEN the "Starter" tier is configured, THE Tulia System SHALL limit monthly_messages to 1000, max_products to 100, max_services to 10, and payment_facilitation to false
4. WHEN the "Growth" tier is configured, THE Tulia System SHALL limit monthly_messages to 10000, max_products to 1000, max_services to 50, and payment_facilitation to true
5. WHEN the "Enterprise" tier is configured, THE Tulia System SHALL set monthly_messages to unlimited, max_products to unlimited, max_services to unlimited, and payment_facilitation to true
6. WHEN a SubscriptionTier is defined, THE Tulia System SHALL include additional features such as priority_support, custom_branding, and api_access

### Requirement 27

**User Story:** As a new business owner, I want a free trial period to test the platform, so that I can evaluate if Tulia meets my needs before committing to payment

#### Acceptance Criteria

1. WHEN a new Tenant is created, THE Tulia System SHALL automatically assign a FreeTrial with configurable duration in days
2. WHEN a FreeTrial is active, THE Tulia System SHALL allow the Tenant to access all features of their assigned SubscriptionTier
3. WHEN the FreeTrial expires, THE Tulia System SHALL change the Tenant status to "trial_expired" if no Subscription is active
4. WHEN a platform administrator configures the default trial duration, THE Tulia System SHALL apply the setting to all new Tenants
5. WHEN a platform administrator creates a Tenant, THE Tulia System SHALL allow overriding the trial duration for that specific Tenant
6. WHEN a FreeTrial is active, THE Tulia System SHALL display the remaining trial days in the Tenant dashboard

### Requirement 28

**User Story:** As a business owner, I want to subscribe to a tier with monthly or yearly billing, so that I can choose a payment schedule that fits my cash flow

#### Acceptance Criteria

1. WHEN a Tenant selects a Subscription, THE Tulia System SHALL offer BillingCycle options of "monthly" or "yearly"
2. WHEN a Tenant selects yearly billing, THE Tulia System SHALL apply a 20% discount to the total annual cost
3. WHEN a Subscription is created, THE Tulia System SHALL store the tier, billing_cycle, start_date, next_billing_date, and status
4. WHEN the next_billing_date arrives, THE Tulia System SHALL generate an invoice and attempt to charge the Tenant's payment method
5. WHEN a billing charge succeeds, THE Tulia System SHALL update next_billing_date by adding one billing_cycle period
6. WHEN a billing charge fails, THE Tulia System SHALL retry up to 3 times over 7 days before suspending the Subscription

### Requirement 29

**User Story:** As a platform operator, I want to apply custom discounts to tenant subscriptions, so that I can offer promotional pricing or accommodate special partnerships

#### Acceptance Criteria

1. WHEN a platform administrator creates a SubscriptionDiscount, THE Tulia System SHALL specify discount_type as "percentage" or "fixed_amount"
2. WHEN a SubscriptionDiscount with type "percentage" is applied, THE Tulia System SHALL reduce the subscription price by the specified percentage
3. WHEN a SubscriptionDiscount with type "fixed_amount" is applied, THE Tulia System SHALL reduce the subscription price by the specified currency amount
4. WHEN a SubscriptionDiscount is created, THE Tulia System SHALL allow optional expiry_date and usage_limit fields
5. WHEN calculating a Subscription charge, THE Tulia System SHALL apply all active SubscriptionDiscounts for the Tenant
6. WHEN a SubscriptionDiscount expires or reaches usage_limit, THE Tulia System SHALL exclude it from future billing calculations

### Requirement 30

**User Story:** As a platform operator, I want to waive subscription fees for specific tenants, so that I can support strategic partnerships or charitable organizations

#### Acceptance Criteria

1. WHEN a platform administrator sets subscription_waived to true for a Tenant, THE Tulia System SHALL not generate invoices for that Tenant
2. WHEN subscription_waived is true, THE Tulia System SHALL maintain the Tenant's Subscription status as "active"
3. WHEN subscription_waived is true, THE Tulia System SHALL grant the Tenant access to all features of their assigned SubscriptionTier
4. WHEN a platform administrator sets subscription_waived to false, THE Tulia System SHALL resume normal billing on the next billing cycle
5. WHEN subscription_waived is true, THE Tulia System SHALL display "Subscription Waived" in the Tenant dashboard

### Requirement 31

**User Story:** As a business owner, I want the WhatsApp bot to stop responding when my subscription is inactive, so that I understand the consequence of non-payment

#### Acceptance Criteria

1. WHEN the WebhookHandler receives a message for a Tenant, THE Tulia System SHALL check if the Tenant's Subscription status is "active" or FreeTrial is valid
2. WHEN the Subscription status is "suspended", "canceled", or "expired" and no valid FreeTrial exists, THE Tulia System SHALL not invoke the IntentService
3. WHEN the Subscription is inactive, THE Tulia System SHALL send a single automated message to the Customer stating "This business is temporarily unavailable"
4. WHEN the Subscription is inactive, THE Tulia System SHALL log the blocked message attempt in WebhookLog with status "subscription_inactive"
5. WHEN a Tenant's Subscription becomes active again, THE Tulia System SHALL immediately resume normal message processing

### Requirement 32

**User Story:** As a business owner, I want a wallet to hold funds from customer payments, so that I can track my earnings and request withdrawals

#### Acceptance Criteria

1. WHEN a Tenant is created, THE Tulia System SHALL automatically create a TenantWallet with initial balance of zero
2. WHEN a Customer completes a payment for an Order or Appointment, THE Tulia System SHALL record a Transaction with type "customer_payment"
3. WHEN a customer_payment Transaction is recorded, THE Tulia System SHALL calculate the platform TransactionFee based on the Tenant's SubscriptionTier
4. WHEN the TransactionFee is calculated, THE Tulia System SHALL credit the net amount (payment minus fee) to the TenantWallet balance
5. WHEN a TenantWallet balance is updated, THE Tulia System SHALL create an audit record with previous_balance, amount, new_balance, and transaction_id

### Requirement 33

**User Story:** As a business owner, I want to view my wallet balance and transaction history, so that I can track my revenue and platform fees

#### Acceptance Criteria

1. WHEN a Tenant requests GET /v1/wallet/balance, THE Tulia System SHALL return the current TenantWallet balance and currency
2. WHEN a Tenant requests GET /v1/wallet/transactions, THE Tulia System SHALL return a paginated list of Transactions for that Tenant
3. WHEN returning Transactions, THE Tulia System SHALL include transaction_type, amount, fee, net_amount, status, and created_at
4. WHEN returning Transactions, THE Tulia System SHALL support filtering by transaction_type, date_range, and status
5. WHEN a Tenant views transaction details, THE Tulia System SHALL display the associated Order or Appointment reference

### Requirement 34

**User Story:** As a business owner, I want to request withdrawals from my wallet, so that I can access my earned revenue

#### Acceptance Criteria

1. WHEN a Tenant requests POST /v1/wallet/withdraw, THE Tulia System SHALL validate that the withdrawal amount does not exceed the available TenantWallet balance
2. WHEN a withdrawal request is valid, THE Tulia System SHALL create a Transaction with type "withdrawal" and status "pending"
3. WHEN a withdrawal Transaction is created, THE Tulia System SHALL deduct the amount from the TenantWallet balance immediately
4. WHEN a withdrawal is processed by a platform administrator, THE Tulia System SHALL update the Transaction status to "completed"
5. WHEN a withdrawal fails, THE Tulia System SHALL update the Transaction status to "failed" and credit the amount back to the TenantWallet balance
6. WHEN a Tenant has a minimum_withdrawal_amount configured, THE Tulia System SHALL reject withdrawal requests below that threshold

### Requirement 35

**User Story:** As a platform operator, I want to charge transaction fees on facilitated payments, so that I can generate revenue beyond subscriptions

#### Acceptance Criteria

1. WHEN a SubscriptionTier has payment_facilitation enabled, THE Tulia System SHALL define a transaction_fee_percentage for that tier
2. WHEN the "Growth" tier is configured, THE Tulia System SHALL set transaction_fee_percentage to 3.5%
3. WHEN the "Enterprise" tier is configured, THE Tulia System SHALL set transaction_fee_percentage to 2.5%
4. WHEN a customer_payment Transaction is processed, THE Tulia System SHALL calculate the fee as payment_amount multiplied by transaction_fee_percentage
5. WHEN the TransactionFee is calculated, THE Tulia System SHALL create a separate Transaction record with type "platform_fee" for accounting
6. WHEN a Tenant views their Transaction history, THE Tulia System SHALL clearly display the fee amount deducted from each payment

### Requirement 36

**User Story:** As a platform operator, I want analytics on facilitated payment volume and fees collected, so that I can track platform revenue

#### Acceptance Criteria

1. WHEN aggregating daily analytics, THE Tulia System SHALL calculate total_payment_volume as the sum of all customer_payment Transactions
2. WHEN aggregating daily analytics, THE Tulia System SHALL calculate total_platform_fees as the sum of all platform_fee Transactions
3. WHEN a platform administrator requests GET /v1/admin/analytics/revenue, THE Tulia System SHALL return payment_volume, platform_fees, and subscription_revenue
4. WHEN returning revenue analytics, THE Tulia System SHALL support grouping by date, SubscriptionTier, and Tenant
5. WHEN calculating subscription_revenue, THE Tulia System SHALL sum all successful Subscription billing charges for the period

### Requirement 37

**User Story:** As a business owner, I want payment facilitation to be optional based on my subscription tier, so that I can choose whether to use the platform's payment processing

#### Acceptance Criteria

1. WHEN a Tenant's SubscriptionTier has payment_facilitation set to false, THE Tulia System SHALL not display wallet or payment features in the dashboard
2. WHEN payment_facilitation is false, THE Tulia System SHALL allow the Tenant to provide external checkout links for Orders
3. WHEN payment_facilitation is true, THE Tulia System SHALL enable the TenantWallet and process payments through the platform
4. WHEN a Tenant upgrades to a tier with payment_facilitation, THE Tulia System SHALL automatically create a TenantWallet if one does not exist
5. WHEN a Tenant downgrades to a tier without payment_facilitation, THE Tulia System SHALL require the TenantWallet balance to be zero before allowing the change

### Requirement 38

**User Story:** As a platform operator, I want to enforce feature limits based on subscription tiers, so that tenants use resources appropriate to their plan

#### Acceptance Criteria

1. WHEN a Tenant attempts to create a Product, THE Tulia System SHALL check if the current product count is below max_products for their SubscriptionTier
2. WHEN a Tenant attempts to create a Service, THE Tulia System SHALL check if the current service count is below max_services for their SubscriptionTier
3. WHEN a Tenant exceeds monthly_messages limit, THE Tulia System SHALL send a notification and optionally suspend bot responses until the next billing cycle
4. WHEN a feature limit is reached, THE Tulia System SHALL return HTTP status code 403 with a message indicating the limit and suggesting an upgrade
5. WHEN a Tenant upgrades their SubscriptionTier, THE Tulia System SHALL immediately apply the new feature limits

### Requirement 39

**User Story:** As a business owner, I want to receive notifications before my subscription expires, so that I can renew without service interruption

#### Acceptance Criteria

1. WHEN a Subscription next_billing_date is 7 days away, THE Tulia System SHALL send an email notification to the Tenant's contact email
2. WHEN a Subscription next_billing_date is 3 days away, THE Tulia System SHALL send a second reminder notification
3. WHEN a Subscription billing charge fails, THE Tulia System SHALL immediately send a notification with payment update instructions
4. WHEN a FreeTrial has 3 days remaining, THE Tulia System SHALL send a notification encouraging the Tenant to subscribe
5. WHEN a Subscription is suspended due to payment failure, THE Tulia System SHALL send a final notification with reactivation steps

### Requirement 40

**User Story:** As a platform operator, I want to track subscription lifecycle events, so that I can analyze churn and retention metrics

#### Acceptance Criteria

1. WHEN a Subscription is created, THE Tulia System SHALL log a SubscriptionEvent with event_type "created"
2. WHEN a Subscription is upgraded or downgraded, THE Tulia System SHALL log a SubscriptionEvent with event_type "tier_changed" and include previous and new tiers
3. WHEN a Subscription is canceled, THE Tulia System SHALL log a SubscriptionEvent with event_type "canceled" and optional cancellation_reason
4. WHEN a Subscription billing succeeds, THE Tulia System SHALL log a SubscriptionEvent with event_type "renewed"
5. WHEN a Subscription is suspended, THE Tulia System SHALL log a SubscriptionEvent with event_type "suspended"
6. WHEN analyzing retention, THE Tulia System SHALL calculate monthly churn rate as canceled Subscriptions divided by total active Subscriptions


### Requirement 41

**User Story:** As a business owner, I want to send automated transactional messages for order and payment updates, so that customers stay informed without manual effort

#### Acceptance Criteria

1. WHEN an Order status changes to "paid", THE Tulia System SHALL automatically send a payment confirmation message to the Customer
2. WHEN an Order status changes to "shipped", THE Tulia System SHALL automatically send a shipment notification message with tracking information if available
3. WHEN a payment transaction fails, THE Tulia System SHALL automatically send a payment failed message with retry instructions
4. WHEN an Appointment is confirmed, THE Tulia System SHALL automatically send a booking confirmation message with appointment details
5. WHEN an AutomatedMessage is sent, THE Tulia System SHALL create a Message record with direction "out" and message_type "automated_transactional"
6. WHEN an AutomatedMessage fails to send, THE Tulia System SHALL log the failure and retry up to 3 times with exponential backoff

### Requirement 42

**User Story:** As a business owner, I want to send automated reminder messages for upcoming appointments, so that customers don't miss their bookings

#### Acceptance Criteria

1. WHEN an Appointment start_dt is 24 hours away, THE Tulia System SHALL automatically send a reminder message to the Customer
2. WHEN an Appointment start_dt is 2 hours away, THE Tulia System SHALL send a second reminder message
3. WHEN sending an appointment reminder, THE Tulia System SHALL include the service name, date, time, and location if configured
4. WHEN a Customer has opted out of reminder messages, THE Tulia System SHALL NOT send appointment reminders to that Customer
5. WHEN an Appointment is canceled before a scheduled reminder, THE Tulia System SHALL cancel the pending reminder message

### Requirement 43

**User Story:** As a business owner, I want to send automated re-engagement messages to inactive conversations, so that I can recapture customer attention

#### Acceptance Criteria

1. WHEN a Conversation has been inactive for 7 days with no Customer response, THE Tulia System SHALL send a re-engagement message
2. WHEN sending a re-engagement message, THE Tulia System SHALL include a personalized greeting and a call-to-action such as "Check out our new arrivals"
3. WHEN a Customer responds to a re-engagement message, THE Tulia System SHALL update the Conversation status to "open"
4. WHEN a Customer has opted out of promotional messages, THE Tulia System SHALL NOT send re-engagement messages
5. WHEN a re-engagement message receives no response after 14 days, THE Tulia System SHALL update the Conversation status to "dormant"

### Requirement 44

**User Story:** As a business owner, I want to schedule promotional messages for future delivery, so that I can plan marketing campaigns in advance

#### Acceptance Criteria

1. WHEN a Tenant creates a ScheduledMessage via POST /v1/messages/schedule, THE Tulia System SHALL validate the scheduled_at timestamp is in the future
2. WHEN a ScheduledMessage is created, THE Tulia System SHALL store the message content, recipient criteria, and scheduled_at timestamp
3. WHEN the scheduled_at time arrives, THE Tulia System SHALL send the message to all Customers matching the recipient criteria
4. WHEN sending a ScheduledMessage, THE Tulia System SHALL respect each Customer's consent preferences for promotional messages
5. WHEN a ScheduledMessage is sent, THE Tulia System SHALL create Message records with message_type "scheduled_promotional"
6. WHEN a Tenant cancels a ScheduledMessage before delivery, THE Tulia System SHALL update the status to "canceled" and prevent sending

### Requirement 45

**User Story:** As a business owner, I want to create message campaigns to broadcast offers to multiple customers, so that I can promote sales and discounts efficiently

#### Acceptance Criteria

1. WHEN a Tenant creates a MessageCampaign via POST /v1/campaigns, THE Tulia System SHALL require campaign_name, message_content, and target_audience criteria
2. WHEN a MessageCampaign is created, THE Tulia System SHALL allow targeting by customer tags, purchase history, or conversation activity
3. WHEN a MessageCampaign is executed, THE Tulia System SHALL send messages only to Customers who have consented to promotional messages
4. WHEN a MessageCampaign is executed, THE Tulia System SHALL track delivery_count, delivered_count, failed_count, and read_count
5. WHEN a MessageCampaign completes, THE Tulia System SHALL generate a report with engagement metrics including response rate
6. WHEN a Tenant's SubscriptionTier limits campaign sends per month, THE Tulia System SHALL enforce the limit and return an error if exceeded

### Requirement 46

**User Story:** As a customer, I want to control what types of messages I receive from a business, so that I only get communications I find valuable

#### Acceptance Criteria

1. WHEN a Customer first interacts with a Tenant, THE Tulia System SHALL create CustomerPreferences with all ConsentTypes set to default values
2. WHEN CustomerPreferences are created, THE Tulia System SHALL set transactional_messages consent to true by default
3. WHEN CustomerPreferences are created, THE Tulia System SHALL set promotional_messages consent to false by default, requiring explicit opt-in
4. WHEN CustomerPreferences are created, THE Tulia System SHALL set reminder_messages consent to true by default
5. WHEN a Customer sends a message containing "stop promotions" or similar opt-out language, THE IntentService SHALL detect the intent and update promotional_messages consent to false
6. WHEN a Customer sends a message containing "start promotions" or similar opt-in language, THE IntentService SHALL detect the intent and update promotional_messages consent to true

### Requirement 47

**User Story:** As a customer, I want to easily opt out of all non-essential messages, so that I can stop receiving unwanted communications

#### Acceptance Criteria

1. WHEN a Customer sends a message containing "STOP" or "UNSUBSCRIBE", THE Tulia System SHALL update all optional ConsentTypes to false
2. WHEN a Customer opts out of all messages, THE Tulia System SHALL send a confirmation message stating "You have been unsubscribed from promotional and reminder messages"
3. WHEN a Customer has opted out, THE Tulia System SHALL continue to send transactional_messages as they are essential for service delivery
4. WHEN a Customer sends "START" after opting out, THE Tulia System SHALL re-enable promotional_messages and reminder_messages consent
5. WHEN a Customer opts out, THE Tulia System SHALL log a ConsentEvent with event_type "opt_out" and timestamp

### Requirement 48

**User Story:** As a business owner, I want to view customer consent preferences, so that I understand my audience's communication preferences

#### Acceptance Criteria

1. WHEN a Tenant requests GET /v1/customers/{id}/preferences, THE Tulia System SHALL return the Customer's consent settings for all ConsentTypes
2. WHEN a Tenant views customer lists, THE Tulia System SHALL display consent status indicators for promotional and reminder messages
3. WHEN a Tenant exports customer data, THE Tulia System SHALL include consent preferences in the export file
4. WHEN calculating campaign reach, THE Tulia System SHALL show the count of Customers who have consented to promotional messages
5. WHEN a Tenant attempts to manually update a Customer's consent preferences, THE Tulia System SHALL require a reason and log the change

### Requirement 49

**User Story:** As a business owner, I want to use message templates with personalization, so that I can send consistent branded messages efficiently

#### Acceptance Criteria

1. WHEN a Tenant creates a MessageTemplate via POST /v1/templates, THE Tulia System SHALL validate the template contains valid placeholder syntax
2. WHEN a MessageTemplate is created, THE Tulia System SHALL support placeholders including {{customer_name}}, {{product_name}}, {{order_id}}, and {{appointment_time}}
3. WHEN sending a message using a MessageTemplate, THE Tulia System SHALL replace all placeholders with actual Customer or order data
4. WHEN a placeholder cannot be resolved, THE Tulia System SHALL either use a default value or return an error based on template configuration
5. WHEN a MessageTemplate is used, THE Tulia System SHALL track usage_count for analytics
6. WHEN a Tenant's SubscriptionTier includes custom_branding, THE Tulia System SHALL allow uploading custom message templates with brand styling

### Requirement 50

**User Story:** As a platform operator, I want to enforce messaging rate limits per tenant, so that the platform remains compliant with WhatsApp policies

#### Acceptance Criteria

1. WHEN a Tenant sends outbound messages, THE Tulia System SHALL track the message count per 24-hour rolling window
2. WHEN a Tenant's SubscriptionTier defines max_daily_outbound_messages, THE Tulia System SHALL enforce the limit
3. WHEN a Tenant reaches 80% of their daily message limit, THE Tulia System SHALL send a warning notification
4. WHEN a Tenant exceeds their daily message limit, THE Tulia System SHALL queue additional messages for the next day
5. WHEN a Tenant consistently exceeds limits, THE Tulia System SHALL flag the account for review and potential tier upgrade recommendation

### Requirement 51

**User Story:** As a business owner, I want to track the performance of my automated and scheduled messages, so that I can optimize my communication strategy

#### Acceptance Criteria

1. WHEN a Tenant requests GET /v1/analytics/messaging, THE Tulia System SHALL return metrics grouped by message_type
2. WHEN returning messaging analytics, THE Tulia System SHALL include sent_count, delivered_count, failed_count, and read_count for each message_type
3. WHEN returning messaging analytics, THE Tulia System SHALL calculate delivery_rate as delivered_count divided by sent_count
4. WHEN returning messaging analytics, THE Tulia System SHALL calculate engagement_rate as responses received divided by messages delivered
5. WHEN a MessageCampaign completes, THE Tulia System SHALL store campaign-specific metrics including conversion_count if orders resulted from the campaign

### Requirement 52

**User Story:** As a platform operator, I want to ensure compliance with data privacy regulations, so that customer consent is properly documented and auditable

#### Acceptance Criteria

1. WHEN a Customer's consent preference changes, THE Tulia System SHALL create a ConsentEvent record with timestamp, previous_value, new_value, and source
2. WHEN a ConsentEvent is created, THE Tulia System SHALL store the source as "customer_initiated", "tenant_updated", or "system_default"
3. WHEN a regulatory audit is requested, THE Tulia System SHALL provide a complete consent history for any Customer
4. WHEN a Customer requests data deletion, THE Tulia System SHALL include all ConsentEvents in the deletion process
5. WHEN a Tenant attempts to send a message to a Customer without proper consent, THE Tulia System SHALL block the message and log a compliance violation

### Requirement 53

**User Story:** As a business owner, I want automated messages to respect customer timezone, so that messages arrive at appropriate local times

#### Acceptance Criteria

1. WHEN a Customer's timezone is detected from their first interaction, THE Tulia System SHALL store the timezone in the Customer record
2. WHEN scheduling an AutomatedMessage or ScheduledMessage, THE Tulia System SHALL convert the delivery time to the Customer's local timezone
3. WHEN a Tenant configures "quiet hours" (e.g., 10 PM - 8 AM), THE Tulia System SHALL delay message delivery until after quiet hours in the Customer's timezone
4. WHEN a timezone cannot be determined, THE Tulia System SHALL use the Tenant's configured timezone as a fallback
5. WHEN sending time-sensitive messages like appointment reminders, THE Tulia System SHALL override quiet hours to ensure timely delivery

### Requirement 54

**User Story:** As a business owner, I want to A/B test different message templates, so that I can optimize message effectiveness

#### Acceptance Criteria

1. WHEN a Tenant creates a MessageCampaign with A/B testing enabled, THE Tulia System SHALL allow defining variant_a and variant_b message templates
2. WHEN executing an A/B test campaign, THE Tulia System SHALL randomly assign Customers to variant_a or variant_b with equal distribution
3. WHEN an A/B test campaign completes, THE Tulia System SHALL calculate engagement_rate for each variant
4. WHEN comparing variants, THE Tulia System SHALL track response_count, conversion_count, and average_response_time for each variant
5. WHEN a Tenant's SubscriptionTier is "Enterprise", THE Tulia System SHALL allow A/B testing with up to 4 variants


## RBAC — Multi-Tenant Admin Access

### Requirement 55

**User Story:** As a platform operator, I want a global User identity system, so that a single person can work across multiple tenants with different roles

#### Acceptance Criteria

1. WHEN a User account is created, THE Tulia System SHALL store email, password_hash, is_active, and 2fa_enabled globally
2. WHEN a User logs in, THE Tulia System SHALL authenticate against the global User table
3. WHEN a User is associated with multiple Tenants, THE Tulia System SHALL maintain separate TenantUser records for each association
4. WHEN a User's global account is deactivated, THE Tulia System SHALL prevent access to all associated Tenants
5. WHEN a User enables 2FA, THE Tulia System SHALL require two-factor authentication for all tenant access

### Requirement 56

**User Story:** As a tenant owner, I want to invite team members to my tenant, so that I can delegate specific responsibilities

#### Acceptance Criteria

1. WHEN a Tenant owner invites a User via POST /v1/memberships/{tenant_id}/invite, THE Tulia System SHALL create a TenantUser record with invite_status "pending"
2. WHEN an invitation is created, THE Tulia System SHALL send an email to the invited User with an acceptance link
3. WHEN a User accepts an invitation, THE Tulia System SHALL update the TenantUser invite_status to "accepted" and set joined_at timestamp
4. WHEN a User declines or an invitation expires, THE Tulia System SHALL update invite_status to "revoked"
5. WHEN a TenantUser is created, THE Tulia System SHALL require the inviting User to have the "users:manage" permission

### Requirement 57

**User Story:** As a platform operator, I want a canonical set of permissions, so that all tenants have consistent access control options

#### Acceptance Criteria

1. WHEN the Tulia System is deployed, THE Tulia System SHALL seed global Permission records for all canonical permissions
2. WHEN a new Permission is added to the canon, THE Tulia System SHALL allow running seed_permissions command without duplicating existing permissions
3. THE Tulia System SHALL include the following canonical permissions: catalog:view, catalog:edit, services:view, services:edit, availability:edit, conversations:view, handoff:perform, orders:view, orders:edit, appointments:view, appointments:edit, analytics:view, finance:view, finance:withdraw:initiate, finance:withdraw:approve, finance:reconcile, integrations:manage, users:manage
4. WHEN a Permission is created, THE Tulia System SHALL enforce uniqueness on the code field
5. WHEN listing permissions via GET /v1/permissions, THE Tulia System SHALL return all available permission codes with labels and descriptions

### Requirement 58

**User Story:** As a tenant owner, I want default roles automatically created for my tenant, so that I can quickly assign team members to common positions

#### Acceptance Criteria

1. WHEN a new Tenant is created, THE Tulia System SHALL automatically seed default Role records for that Tenant
2. WHEN seeding roles, THE Tulia System SHALL create the following roles: Owner, Admin, Finance Admin, Catalog Manager, Support Lead, and Analyst
3. WHEN a Role is created, THE Tulia System SHALL mark system-seeded roles with is_system=True
4. WHEN a Role is created, THE Tulia System SHALL enforce uniqueness on (tenant_id, name)
5. WHEN running seed_tenant_roles command for an existing Tenant, THE Tulia System SHALL not duplicate existing roles

### Requirement 59

**User Story:** As a tenant owner, I want the Owner role to have all permissions, so that I maintain full control over my tenant

#### Acceptance Criteria

1. WHEN the Owner role is seeded for a Tenant, THE Tulia System SHALL create RolePermission records linking the Owner role to all canonical permissions
2. WHEN a new permission is added to the canon, THE Tulia System SHALL allow updating the Owner role to include the new permission
3. WHEN a User with the Owner role makes an API request, THE Tulia System SHALL resolve request.scopes to include all permission codes
4. WHEN the creating User of a Tenant is assigned, THE Tulia System SHALL automatically assign them the Owner role via TenantUser
5. WHEN a Tenant has multiple Owners, THE Tulia System SHALL allow all Owners equal access to all permissions

### Requirement 60

**User Story:** As a tenant owner, I want the Admin role to have most permissions except withdrawal approval, so that I can delegate day-to-day management safely

#### Acceptance Criteria

1. WHEN the Admin role is seeded for a Tenant, THE Tulia System SHALL create RolePermission records for all permissions except finance:withdraw:approve
2. WHEN the setting RBAC_ADMIN_CAN_APPROVE is set to True, THE Tulia System SHALL include finance:withdraw:approve in the Admin role permissions
3. WHEN a User with the Admin role attempts an action requiring finance:withdraw:approve, THE Tulia System SHALL return HTTP status code 403 if the setting is False
4. WHEN a User with the Admin role makes an API request, THE Tulia System SHALL resolve request.scopes based on the Admin role's RolePermission mappings
5. WHEN the Admin role is updated, THE Tulia System SHALL immediately affect all Users assigned to that role

### Requirement 61

**User Story:** As a tenant owner, I want specialized roles for finance, catalog, support, and analytics, so that I can assign focused responsibilities

#### Acceptance Criteria

1. WHEN the Finance Admin role is seeded, THE Tulia System SHALL grant permissions: analytics:view, finance:view, finance:withdraw:initiate, finance:withdraw:approve, finance:reconcile, orders:view
2. WHEN the Catalog Manager role is seeded, THE Tulia System SHALL grant permissions: analytics:view, catalog:view, catalog:edit, services:view, services:edit, availability:edit
3. WHEN the Support Lead role is seeded, THE Tulia System SHALL grant permissions: conversations:view, handoff:perform, orders:view, appointments:view
4. WHEN the Analyst role is seeded, THE Tulia System SHALL grant permissions: analytics:view, catalog:view, services:view, orders:view, appointments:view
5. WHEN a User is assigned a specialized role, THE Tulia System SHALL restrict their access to only the permissions granted by that role

### Requirement 62

**User Story:** As a tenant owner, I want to assign roles to team members, so that they receive appropriate permissions

#### Acceptance Criteria

1. WHEN a User with users:manage permission calls POST /v1/memberships/{tenant_id}/{user_id}/roles, THE Tulia System SHALL assign the specified Role to the TenantUser
2. WHEN a Role is assigned to a TenantUser, THE Tulia System SHALL immediately grant all permissions associated with that Role
3. WHEN a TenantUser has multiple Roles, THE Tulia System SHALL aggregate permissions from all assigned Roles
4. WHEN a Role is removed from a TenantUser, THE Tulia System SHALL immediately revoke permissions unique to that Role
5. WHEN assigning a Role, THE Tulia System SHALL create an AuditLog entry recording the action, actor, and target

### Requirement 63

**User Story:** As a tenant owner, I want to grant or deny individual permissions to specific users, so that I can handle exceptions to role-based access

#### Acceptance Criteria

1. WHEN a User with users:manage permission calls POST /v1/users/{id}/permissions, THE Tulia System SHALL create a UserPermission record for the TenantUser
2. WHEN a UserPermission is created with granted=True, THE Tulia System SHALL add the permission to the User's resolved scopes
3. WHEN a UserPermission is created with granted=False (deny), THE Tulia System SHALL remove the permission from the User's resolved scopes even if granted by a Role
4. WHEN resolving scopes, THE Tulia System SHALL apply the deny-overrides-allow pattern where UserPermission denies win over Role grants
5. WHEN a UserPermission is created or updated, THE Tulia System SHALL create an AuditLog entry with the change details

### Requirement 64

**User Story:** As a developer, I want middleware to automatically resolve tenant context and user scopes, so that permission checks are consistent across all endpoints

#### Acceptance Criteria

1. WHEN an API request includes X-TENANT-ID header, THE TenantContextMiddleware SHALL resolve the Tenant and attach it to request.tenant
2. WHEN the Tenant is resolved, THE TenantContextMiddleware SHALL verify that a TenantUser record exists for the authenticated User and Tenant
3. WHEN no TenantUser record exists, THE TenantContextMiddleware SHALL return HTTP status code 403
4. WHEN a TenantUser is found, THE TenantContextMiddleware SHALL resolve all scopes from the User's Roles and UserPermissions
5. WHEN scopes are resolved, THE TenantContextMiddleware SHALL attach the Set[str] of permission codes to request.scopes

### Requirement 65

**User Story:** As a developer, I want a DRF permission class to enforce scope requirements, so that views are automatically protected

#### Acceptance Criteria

1. WHEN a view is decorated with @requires_scopes("catalog:view"), THE HasTenantScopes permission class SHALL check if "catalog:view" is in request.scopes
2. WHEN the required scope is present, THE HasTenantScopes permission class SHALL allow the request to proceed
3. WHEN the required scope is missing, THE HasTenantScopes permission class SHALL return HTTP status code 403
4. WHEN multiple scopes are required, THE HasTenantScopes permission class SHALL verify that all required scopes are present in request.scopes
5. WHEN a view has no required_scopes attribute, THE HasTenantScopes permission class SHALL deny access by default

### Requirement 66

**User Story:** As a catalog manager, I want to view products only if I have catalog:view permission, so that access is properly controlled

#### Acceptance Criteria

1. WHEN a User with catalog:view scope calls GET /v1/products, THE Tulia System SHALL return the tenant-scoped product list
2. WHEN a User without catalog:view scope calls GET /v1/products, THE Tulia System SHALL return HTTP status code 403
3. WHEN a User with catalog:view scope calls GET /v1/products/{id}, THE Tulia System SHALL return the product details if it belongs to the Tenant
4. WHEN a User attempts to access a product from a different Tenant, THE Tulia System SHALL return HTTP status code 404
5. WHEN a User's catalog:view permission is revoked, THE Tulia System SHALL immediately deny access to product endpoints

### Requirement 67

**User Story:** As a catalog manager, I want to create and edit products only if I have catalog:edit permission, so that modifications are controlled

#### Acceptance Criteria

1. WHEN a User with catalog:edit scope calls POST /v1/products, THE Tulia System SHALL create the product for the authenticated Tenant
2. WHEN a User without catalog:edit scope calls POST /v1/products, THE Tulia System SHALL return HTTP status code 403
3. WHEN a User with catalog:edit scope calls PUT /v1/products/{id}, THE Tulia System SHALL update the product if it belongs to the Tenant
4. WHEN a User with catalog:edit scope calls DELETE /v1/products/{id}, THE Tulia System SHALL soft-delete the product if it belongs to the Tenant
5. WHEN a product is created, updated, or deleted, THE Tulia System SHALL create an AuditLog entry with the action and diff

### Requirement 68

**User Story:** As a service manager, I want to create services only if I have services:edit permission, so that service catalog changes are controlled

#### Acceptance Criteria

1. WHEN a User with services:edit scope calls POST /v1/services, THE Tulia System SHALL create the service for the authenticated Tenant
2. WHEN a User without services:edit scope calls POST /v1/services, THE Tulia System SHALL return HTTP status code 403
3. WHEN a User with services:view scope calls GET /v1/services, THE Tulia System SHALL return the tenant-scoped service list
4. WHEN a User without services:view scope calls GET /v1/services, THE Tulia System SHALL return HTTP status code 403
5. WHEN a service is created or updated, THE Tulia System SHALL create an AuditLog entry

### Requirement 69

**User Story:** As a service manager, I want to manage availability windows only if I have availability:edit permission, so that scheduling is controlled

#### Acceptance Criteria

1. WHEN a User with availability:edit scope calls POST /v1/services/{id}/availability, THE Tulia System SHALL create the AvailabilityWindow for the Service
2. WHEN a User without availability:edit scope calls POST /v1/services/{id}/availability, THE Tulia System SHALL return HTTP status code 403
3. WHEN a User with availability:edit scope calls PUT /v1/availability/{id}, THE Tulia System SHALL update the AvailabilityWindow if it belongs to the Tenant
4. WHEN a User with availability:edit scope calls DELETE /v1/availability/{id}, THE Tulia System SHALL delete the AvailabilityWindow if it belongs to the Tenant
5. WHEN an AvailabilityWindow is created, updated, or deleted, THE Tulia System SHALL create an AuditLog entry

### Requirement 70

**User Story:** As a finance admin, I want to initiate withdrawals only if I have finance:withdraw:initiate permission, so that payout requests are controlled

#### Acceptance Criteria

1. WHEN a User with finance:withdraw:initiate scope calls POST /v1/wallet/withdraw, THE Tulia System SHALL create a Transaction with status "pending" and type "withdrawal"
2. WHEN a User without finance:withdraw:initiate scope calls POST /v1/wallet/withdraw, THE Tulia System SHALL return HTTP status code 403
3. WHEN a withdrawal is initiated, THE Tulia System SHALL immediately debit the TenantWallet balance
4. WHEN a withdrawal is initiated, THE Tulia System SHALL store the initiating User's ID in the Transaction record
5. WHEN a withdrawal is initiated, THE Tulia System SHALL create an AuditLog entry with the initiator and amount

### Requirement 71

**User Story:** As a finance admin, I want to approve withdrawals only if I have finance:withdraw:approve permission and I am not the initiator, so that four-eyes control is enforced

#### Acceptance Criteria

1. WHEN a User with finance:withdraw:approve scope calls POST /v1/wallet/withdrawals/{id}/approve, THE Tulia System SHALL verify the User is not the initiator
2. WHEN the approver is the same as the initiator, THE Tulia System SHALL return HTTP status code 409 with message "Cannot approve own withdrawal"
3. WHEN the approver is different from the initiator, THE Tulia System SHALL update the Transaction status to "completed" and execute the payout
4. WHEN a User without finance:withdraw:approve scope attempts approval, THE Tulia System SHALL return HTTP status code 403
5. WHEN a withdrawal is approved, THE Tulia System SHALL create an AuditLog entry with both initiator and approver details

### Requirement 72

**User Story:** As a tenant owner, I want to temporarily restrict a user's permission without changing their role, so that I can handle exceptions

#### Acceptance Criteria

1. WHEN a User with users:manage permission creates a UserPermission with granted=False for a TenantUser, THE Tulia System SHALL deny that permission even if granted by a Role
2. WHEN resolving scopes for a TenantUser, THE Tulia System SHALL apply deny overrides before adding role-granted permissions
3. WHEN a TenantUser has Role "Catalog Manager" (grants catalog:edit) and UserPermission deny for catalog:edit, THE Tulia System SHALL exclude catalog:edit from request.scopes
4. WHEN a deny override is removed, THE Tulia System SHALL immediately restore the permission from the User's Roles
5. WHEN a deny override is created, THE Tulia System SHALL create an AuditLog entry with the reason

### Requirement 73

**User Story:** As a user working for multiple tenants, I want to switch between tenants, so that I can manage different businesses

#### Acceptance Criteria

1. WHEN a User calls GET /v1/memberships/me, THE Tulia System SHALL return all Tenants where the User has an active TenantUser record
2. WHEN the response includes Tenants, THE Tulia System SHALL include the User's assigned Roles for each Tenant
3. WHEN a User switches the X-TENANT-ID header to a different Tenant, THE Tulia System SHALL resolve the new Tenant context and scopes
4. WHEN a User switches to a Tenant where they have no TenantUser record, THE Tulia System SHALL return HTTP status code 403
5. WHEN a User switches Tenants, THE Tulia System SHALL ensure all subsequent queries are scoped to the new Tenant

### Requirement 74

**User Story:** As a platform operator, I want all RBAC changes audited, so that I can track who made what changes and when

#### Acceptance Criteria

1. WHEN a Role is assigned to or removed from a TenantUser, THE Tulia System SHALL create an AuditLog entry with action "role_assigned" or "role_removed"
2. WHEN a UserPermission is granted or denied, THE Tulia System SHALL create an AuditLog entry with action "permission_granted" or "permission_denied"
3. WHEN an AuditLog entry is created, THE Tulia System SHALL include tenant_id, user_id, action, target_type, target_id, diff (JSONB), ip, user_agent, request_id, and created_at
4. WHEN an AuditLog entry includes sensitive data, THE Tulia System SHALL mask secrets and PII
5. WHEN querying audit logs, THE Tulia System SHALL filter by tenant_id to ensure cross-tenant isolation

### Requirement 75

**User Story:** As a platform operator, I want management commands to seed permissions and roles, so that setup is automated and consistent

#### Acceptance Criteria

1. WHEN running `python manage.py seed_permissions`, THE Tulia System SHALL create all canonical Permission records if they do not exist
2. WHEN running `python manage.py seed_tenant_roles --tenant=<id>`, THE Tulia System SHALL create all default Roles and RolePermission mappings for the specified Tenant
3. WHEN running `python manage.py create_owner --tenant=<id> --email=<email>`, THE Tulia System SHALL create a TenantUser with the Owner role for the specified User and Tenant
4. WHEN running `python manage.py seed_demo`, THE Tulia System SHALL create a demo Tenant with Owner, Catalog Manager, and Finance Admin users
5. WHEN any seeder command is run multiple times, THE Tulia System SHALL not duplicate existing records (idempotent)

### Requirement 76

**User Story:** As a developer, I want RBAC endpoints documented in OpenAPI, so that API consumers understand permission requirements

#### Acceptance Criteria

1. WHEN the OpenAPI schema is generated, THE Tulia System SHALL include all RBAC endpoints with request/response schemas
2. WHEN documenting an endpoint, THE Tulia System SHALL list required scopes in the endpoint description
3. WHEN the OpenAPI schema includes RBAC endpoints, THE Tulia System SHALL document: GET /v1/memberships/me, GET /v1/roles, POST /v1/roles, POST /v1/roles/{id}/permissions, POST /v1/memberships/{tenant_id}/invite, POST /v1/memberships/{tenant_id}/{user_id}/roles, GET /v1/permissions
4. WHEN an endpoint requires specific scopes, THE Tulia System SHALL include example curl commands showing the X-TENANT-ID header
5. WHEN the OpenAPI schema is accessed, THE Tulia System SHALL include security scheme definitions for API key and tenant ID headers

### Requirement 77

**User Story:** As a platform operator, I want cross-tenant isolation enforced at the data layer, so that no query can accidentally leak data

#### Acceptance Criteria

1. WHEN a User is a TenantUser in both Tenant A and Tenant B, THE Tulia System SHALL ensure queries with X-TENANT-ID=A return only Tenant A data
2. WHEN the same phone number exists as a Customer in Tenant A and Tenant B, THE Tulia System SHALL maintain separate Customer records with different IDs
3. WHEN a Customer in Tenant A sends messages, THE Tulia System SHALL store Conversations and Messages scoped to Tenant A only
4. WHEN a User switches from Tenant A to Tenant B, THE Tulia System SHALL ensure no Tenant A data is accessible in Tenant B context
5. WHEN testing cross-tenant isolation, THE Tulia System SHALL verify that attempting to access another tenant's resources returns HTTP status code 404 or 403
