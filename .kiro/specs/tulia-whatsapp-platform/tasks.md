# Implementation Plan

This implementation plan breaks down the Tulia AI WhatsApp Commerce & Services platform into discrete, actionable coding tasks. Each task builds incrementally on previous work, with all code integrated and functional at each step.

## Task List

- [x] 1. Set up Django project structure and core configuration
  - Create Django project with apps: core, tenants, messaging, catalog, orders, services, analytics, integrations, bot
  - Configure PostgreSQL database with connection pooling
  - Configure Redis for caching and Celery broker
  - Set up Celery with separate queues for different task priorities
  - Configure environment variables and settings for dev/prod
  - Set up logging with structured JSON format and Sentry integration
  - Create BaseModel with UUID primary keys, soft delete, and timestamp fields
  - _Requirements: 1.1, 1.2, 23.1, 23.2, 23.3, 23.4, 25.1, 25.2, 25.3, 25.4_

- [x] 2. Implement tenant and identity models with multi-tenant isolation
  - [x] 2.1 Create Tenant model with subscription and Twilio configuration fields
    - Implement Tenant model with status, subscription_tier, trial dates, Twilio credentials
    - Add encrypted fields for twilio_sid, twilio_token, webhook_secret
    - Create tenant-scoped manager and queryset
    - _Requirements: 1.1, 1.8, 2.1, 2.2, 20.1, 20.2_
  
  - [x] 2.2 Create GlobalParty and Customer models with encryption
    - Implement GlobalParty model with encrypted phone_e164
    - Implement Customer model with unique constraint on (tenant_id, phone_e164)
    - Add encrypted phone_e164 field with transparent encryption/decryption
    - Create indexes for efficient tenant-scoped queries
    - _Requirements: 1.1, 3.1, 3.2, 20.1, 20.2, 20.3_
  
  - [x] 2.3 Create Conversation and Message models
    - Implement Conversation model with status tracking and tenant scoping
    - Implement Message model with direction and message_type fields
    - Add indexes for conversation history queries
    - _Requirements: 3.1, 3.2, 3.3, 24.3_
  
  - [x] 2.4 Implement tenant context middleware
    - Create middleware to extract X-TENANT-ID and X-TENANT-API-KEY headers
    - Validate API key against tenant's api_keys list
    - Inject tenant context into request for use in views
    - Add request_id injection for tracing
    - _Requirements: 1.8, 21.4_


- [x] 3. Implement subscription and billing system
  - [x] 3.1 Create SubscriptionTier model with feature limits
    - Define three tiers: Starter, Growth, Enterprise with pricing and limits
    - Add fields for monthly_messages, max_products, max_services, payment_facilitation
    - Add transaction_fee_percentage, ab_test_variants, and feature flags
    - Create seed data for the three subscription tiers
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5, 26.6_
  
  - [x] 3.2 Create Subscription, SubscriptionDiscount, and SubscriptionEvent models ✓
    - Implement Subscription model with billing_cycle, status, and dates
    - Implement SubscriptionDiscount model with percentage and fixed_amount types
    - Implement SubscriptionEvent model for audit trail
    - Migration applied: 0002_subscription_subscriptionevent_subscriptiondiscount_and_more
    - _Requirements: 28.1, 28.2, 28.3, 29.1, 29.2, 29.3, 40.1, 40.2, 40.3_
  
  - [x] 3.3 Implement SubscriptionService for status checks and feature enforcement
    - Create check_subscription_status() method to validate active/trial/expired
    - Create enforce_feature_limit() method to check products, services, messages
    - Create apply_discounts() method to calculate final subscription price
    - Implement free trial logic with configurable duration
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 38.1, 38.2, 38.3, 38.4, 38.5_
  
  - [x] 3.4 Implement subscription billing and payment failure handling
    - Create process_billing() Celery task for recurring charges
    - Implement retry logic for failed payments (3 attempts over 7 days)
    - Create notification system for billing reminders and failures
    - Update subscription status based on payment results
    - _Requirements: 28.4, 28.5, 28.6, 39.1, 39.2, 39.3, 39.4, 39.5_
  
  - [x] 3.5 Add subscription status check to webhook middleware
    - Check subscription status before processing inbound messages
    - Block bot processing if subscription is inactive
    - Send "business temporarily unavailable" message to customer
    - Log blocked attempts with subscription_inactive status
    - _Requirements: 31.1, 31.2, 31.3, 31.4, 31.5_

- [x] 4. Implement wallet and transaction system
  - [x] 4.1 Create TenantWallet, Transaction, and WalletAudit models
    - Implement TenantWallet model with balance and currency
    - Implement Transaction model with types: customer_payment, platform_fee, withdrawal
    - Implement WalletAudit model for balance change tracking
    - Add indexes for transaction queries
    - _Requirements: 32.1, 32.5, 33.3_
  
  - [x] 4.2 Implement WalletService for credits, debits, and fee calculation
    - Create credit_wallet() method with audit trail
    - Create debit_wallet() method with balance validation
    - Create calculate_transaction_fee() based on subscription tier
    - Implement process_customer_payment() to handle payment flow
    - _Requirements: 32.2, 32.3, 32.4, 35.1, 35.2, 35.3, 35.4, 35.5_
  
  - [x] 4.3 Implement wallet withdrawal functionality
    - Create request_withdrawal() method with minimum amount validation
    - Implement immediate debit from wallet on withdrawal request
    - Create admin endpoint to process/complete withdrawals
    - Handle failed withdrawals with balance credit-back
    - _Requirements: 34.1, 34.2, 34.3, 34.4, 34.5, 34.6_
  
  - [x] 4.4 Create wallet REST API endpoints
    - Implement GET /v1/wallet/balance endpoint
    - Implement GET /v1/wallet/transactions with pagination and filtering
    - Implement POST /v1/wallet/withdraw endpoint
    - Add tenant scoping and permission checks
    - _Requirements: 33.1, 33.2, 33.4, 33.5_


- [x] 5. Implement catalog models and services for products
  - [x] 5.1 Create Product and ProductVariant models
    - Implement Product model with external_source, external_id, and catalog fields
    - Implement ProductVariant model with SKU, price, stock, and attributes
    - Add unique constraint on (tenant, external_source, external_id)
    - Create indexes for search and tenant-scoped queries
    - _Requirements: 1.4, 8.3, 8.4, 9.3, 9.4_
  
  - [x] 5.2 Implement CatalogService for product operations
    - Create search_products() with full-text search
    - Create get_product() with variant loading
    - Implement check_feature_limit() for max_products enforcement
    - Add tenant scoping to all queries
    - _Requirements: 4.2, 4.3, 5.2, 5.3, 38.1_
  
  - [x] 5.3 Create product REST API endpoints
    - Implement GET /v1/products with search, filtering, and pagination
    - Implement GET /v1/products/{id} with variant details
    - Implement POST /v1/products for manual product creation
    - Implement PUT /v1/products/{id} and DELETE /v1/products/{id}
    - Add feature limit enforcement on product creation
    - _Requirements: 4.4, 5.4, 5.5, 38.4_

- [-] 6. Implement RBAC (Role-Based Access Control) system
  - [x] 6.1 Create RBAC models for users, roles, and permissions
    - Implement User model with email, password_hash, is_active, two_factor_enabled
    - Implement TenantUser model with invite_status, joined_at, last_seen_at
    - Implement Permission model with unique code, label, description, category
    - Implement Role model with per-tenant name, description, is_system flag
    - Implement RolePermission model linking roles to permissions
    - Implement UserPermission model for per-user overrides with granted flag
    - Implement AuditLog model with tenant, user, action, target_type, diff, ip, user_agent
    - Add unique constraints: Permission.code, Role(tenant, name), RolePermission(role, permission), UserPermission(tenant_user, permission)
    - Add indexes for efficient queries on all models
    - _Requirements: 55.1, 55.2, 55.3, 56.1, 57.1, 57.4, 58.3, 58.4, 74.3_
  
  - [x] 6.2 Implement RBACService for scope resolution and permission management
    - Create resolve_scopes(tenant_user) method that aggregates permissions from roles
    - Implement deny-overrides-allow pattern where UserPermission.granted=False wins
    - Create grant_permission() method to add user-level permission override
    - Create deny_permission() method to add user-level permission denial
    - Create validate_four_eyes() method to ensure initiator ≠ approver
    - Create assign_role() method with audit logging
    - Create remove_role() method with audit logging
    - Add caching for scope resolution (5-minute TTL)
    - _Requirements: 59.3, 60.4, 62.2, 62.3, 63.2, 63.3, 63.4, 64.4, 64.5, 71.1, 71.2, 72.2, 72.3_
  
  - [x] 6.3 Enhance TenantContextMiddleware for RBAC
    - Update middleware to validate TenantUser membership exists
    - Return 403 if no TenantUser record found for user and tenant
    - Call RBACService.resolve_scopes() to get user's permission codes
    - Attach request.tenant, request.membership, request.scopes to request
    - Update last_seen_at timestamp on TenantUser
    - Add request_id to all audit logs
    - _Requirements: 64.1, 64.2, 64.3, 64.4, 64.5, 73.3, 73.4_
  
  - [x] 6.4 Create HasTenantScopes DRF permission class and decorator
    - Implement HasTenantScopes permission class that checks view.required_scopes
    - Verify all required scopes are present in request.scopes
    - Return 403 if any required scope is missing
    - Implement has_object_permission to verify object belongs to request.tenant
    - Create @requires_scopes() decorator to set required_scopes on views
    - Log permission denials with missing scopes for debugging
    - _Requirements: 65.1, 65.2, 65.3, 65.4, 65.5_
  
  - [x] 6.5 Create management commands for RBAC seeding
    - Implement seed_permissions command to create all canonical permissions
    - Implement seed_tenant_roles command to create default roles per tenant
    - Implement create_owner command to assign Owner role to a user
    - Implement seed_demo command to create demo tenant with users and roles
    - Ensure all commands are idempotent (safe to re-run)
    - Add --tenant and --all flags to seed_tenant_roles
    - _Requirements: 5View7.1, 57.2, 58.1, 58.2, 58.5, 59.1, 59.2, 60.1, 60.2, 61.1, 61.2, 61.3, 61.4, 75.1, 75.2, 75.3, 75.4, 75.5_
  
  - [x] 6.6 Wire RBAC signals for automatic role seeding
    - Create post_save signal on Tenant model
    - Automatically run seed_tenant_roles when new tenant is created
    - Assign Owner role to creating user if specified
    - Log seeding completion to audit log
    - _Requirements: 58.1, 59.4_
  
  - [x] 6.7 Apply scope requirements to existing catalog endpoints
    - Add @requires_scopes("catalog:view") to GET /v1/products
    - Add @requires_scopes("catalog:view") to GET /v1/products/{id}
    - Add @requires_scopes("catalog:edit") to POST /v1/products
    - Add @requires_scopes("catalog:edit") to PUT /v1/products/{id}
    - Add @requires_scopes("catalog:edit") to DELETE /v1/products/{id}
    - Create AuditLog entries for catalog create/update/delete actions
    - _Requirements: 66.1, 66.2, 66.3, 66.4, 66.5, 67.1, 67.2, 67.3, 67.4, 67.5_
  
  - [x] 6.8 Create RBAC REST API endpoints
    - Implement GET /v1/memberships/me to list user's tenant memberships with roles
    - Implement POST /v1/memberships/{tenant_id}/invite with users:manage scope
    - Implement POST /v1/memberships/{tenant_id}/{user_id}/roles with users:manage scope
    - Implement DELETE /v1/memberships/{tenant_id}/{user_id}/roles/{role_id} with users:manage scope
    - Implement GET /v1/roles (tenant-scoped)
    - Implement POST /v1/roles with users:manage scope
    - Implement GET /v1/roles/{id}/permissions
    - Implement POST /v1/roles/{id}/permissions with users:manage scope
    - Implement GET /v1/users/{id}/permissions (user overrides)
    - Implement POST /v1/users/{id}/permissions with users:manage scope
    - Implement GET /v1/permissions (list all available)
    - Implement GET /v1/audit-logs with analytics:view scope
    - _Requirements: 56.1, 56.2, 56.3, 56.5, 62.1, 62.5, 63.1, 63.5, 73.1, 73.2, 76.3_
  
  - [x] 6.9 Implement four-eyes approval for finance withdrawals
    - Update POST /v1/wallet/withdraw to require finance:withdraw:initiate scope
    - Store initiating user ID in Transaction record
    - Create POST /v1/wallet/withdrawals/{id}/approve endpoint
    - Require finance:withdraw:approve scope for approval
    - Call validate_four_eyes() to ensure approver ≠ initiator
    - Return 409 if same user attempts approval
    - Create AuditLog entries for both initiate and approve actions
    - _Requirements: 70.1, 70.2, 70.4, 70.5, 71.1, 71.2, 71.3, 71.4, 71.5_
  
  - [x] 6.10 Generate comprehensive RBAC tests
    - Unit tests: scope resolution with multiple roles
    - Unit tests: deny override wins over role grant
    - Unit tests: four-eyes validation rejects same user
    - API tests: GET /v1/products with/without catalog:view (200/403)
    - API tests: POST /v1/products with/without catalog:edit (200/403)
    - API tests: finance withdrawal initiate and approve with different users
    - API tests: finance withdrawal approval by same user returns 409
    - API tests: user permission override denies access despite role grant
    - API tests: switching X-TENANT-ID without membership returns 403
    - API tests: user with membership in multiple tenants sees correct data per tenant
    - API tests: same phone number in different tenants creates separate Customer records
    - Seeder tests: seed_permissions is idempotent
    - Seeder tests: seed_tenant_roles is idempotent
    - _Requirements: 66.1, 66.2, 67.1, 67.2, 70.1, 70.2, 71.1, 71.2, 71.3, 72.1, 72.2, 72.3, 73.3, 73.4, 73.5, 75.5, 77.1, 77.2, 77.3, 77.4, 77.5_
  
  - [x] 6.11 Update OpenAPI schema with RBAC documentation
    - Document all RBAC endpoints with request/response schemas
    - Include required scopes in endpoint descriptions
    - Add security scheme for X-TENANT-ID header
    - Provide example curl commands for invite, assign role, grant permission
    - Document permission codes with descriptions
    - Document default roles and their permission mappings
    - _Requirements: 76.1, 76.2, 76.3, 76.4, 76.5_

- [-] 7. Implement catalog models and services for bookable services
  - [x] 7.1 Create Service, ServiceVariant, and AvailabilityWindow models
    - Implement Service model with title, description, pricing
    - Implement ServiceVariant model with duration_minutes and pricing
    - Implement AvailabilityWindow model with weekday/date, time range, capacity
    - Add validation for weekday (0-6) and end_time > start_time
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3, 11.4_
  
  - [x] 7.2 Create Appointment model with status tracking
    - Implement Appointment model with start_dt, end_dt, status
    - Add indexes for capacity calculation queries
    - Add tenant and customer scoping
    - _Requirements: 13.4, 14.3_
  
  - [x] 7.3 Implement BookingService for availability and appointments
    - Create find_availability() to return available slots with capacity
    - Create check_capacity() to validate slot availability
    - Create create_appointment() with capacity validation
    - Create cancel_appointment() to free up capacity
    - Implement propose_alternatives() for unavailable slots
    - _Requirements: 11.5, 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2, 13.3, 13.5, 13.6, 14.1, 14.2_
  
  - [x] 7.4 Create service and booking REST API endpoints
    - Implement POST /v1/services and GET /v1/services
    - Implement GET /v1/services/{id} and GET /v1/services/{id}/availability
    - Implement POST /v1/appointments with capacity validation
    - Implement GET /v1/appointments and POST /v1/appointments/{id}/cancel
    - Add feature limit enforcement on service creation
    - _Requirements: 10.5, 13.5, 14.4, 14.5, 38.2_


- [x] 8. Implement Twilio integration service
  - [x] 8.1 Create TwilioService for sending and receiving messages
    - Implement send_whatsapp() method using Twilio API
    - Implement send_template() for Twilio message templates
    - Implement verify_signature() for webhook validation
    - Add error handling and retry logic for API failures
    - _Requirements: 2.4, 2.5, 19.1, 19.2, 19.3, 19.4, 24.2, 24.5_
  
  - [x] 8.2 Create WebhookLog model and logging functionality
    - Implement WebhookLog model with provider, event, payload, status
    - Create logging before and after webhook processing
    - Store error messages for failed webhooks
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 19.5_
  
  - [x] 8.3 Implement webhook handler with tenant resolution
    - Create POST /v1/webhooks/twilio endpoint
    - Implement tenant resolution by "To" number or URL path
    - Verify Twilio signature using tenant's webhook_secret
    - Create or update Customer and Conversation records
    - Store inbound Message record
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2_

- [x] 9. Implement intent classification service
  - [x] 9.1 Create IntentEvent model for tracking classifications
    - Implement IntentEvent model with intent_name, confidence_score, slots
    - Add indexes for intent analytics queries
    - _Requirements: 4.5, 15.4_
  
  - [x] 9.2 Implement IntentService with LLM integration
    - Create classify_intent() method using OpenAI/Claude API
    - Define system prompt with all supported intents
    - Implement extract_slots() for entity extraction
    - Add confidence threshold validation (0.7 minimum)
    - Implement handle_low_confidence() with automatic handoff after 2 attempts
    - _Requirements: 4.1, 5.1, 6.1, 12.1, 13.1, 14.1, 15.1, 15.4_
  
  - [x] 9.3 Implement intent handlers for products
    - Create handler for BROWSE_PRODUCTS intent
    - Create handler for PRODUCT_DETAILS intent
    - Create handler for PRICE_CHECK intent
    - Create handler for ADD_TO_CART intent
    - Create handler for CHECKOUT_LINK intent
    - Each handler queries catalog, generates response, sends via Twilio
    - _Requirements: 4.2, 4.3, 5.2, 5.3, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4_
  
  - [x] 9.4 Implement intent handlers for services
    - Create handler for BROWSE_SERVICES intent
    - Create handler for SERVICE_DETAILS intent
    - Create handler for CHECK_AVAILABILITY intent
    - Create handler for BOOK_APPOINTMENT intent
    - Create handler for CANCEL_APPOINTMENT intent
    - Each handler queries services/bookings, generates response, sends via Twilio
    - _Requirements: 12.2, 12.3, 12.4, 12.5, 13.2, 13.3, 13.4, 13.5, 14.2, 14.3, 14.4_
  
  - [x] 9.5 Implement HUMAN_HANDOFF intent handler
    - Create handler to update Conversation status to "handoff"
    - Send confirmation message to customer
    - Prevent further bot processing for handoff conversations
    - _Requirements: 15.2, 15.3, 15.5_


- [x] 10. Implement consent management system
  - [x] 10.1 Create CustomerPreferences and ConsentEvent models
    - Implement CustomerPreferences model with three consent types
    - Set default values: transactional=true, reminder=true, promotional=false
    - Implement ConsentEvent model for audit trail
    - Add unique constraint on (tenant, customer)
    - _Requirements: 46.1, 46.2, 46.3, 46.4, 52.1, 52.2_
  
  - [x] 10.2 Implement ConsentService for preference management
    - Create get_preferences() method
    - Create update_consent() method with audit logging
    - Create check_consent() method for message validation
    - Implement automatic preference creation on first customer interaction
    - _Requirements: 46.1, 48.1, 52.1_
  
  - [x] 10.3 Add consent intent handlers to IntentService
    - Create handler for OPT_OUT_PROMOTIONS intent (keywords: "stop promotions")
    - Create handler for OPT_IN_PROMOTIONS intent (keywords: "start promotions")
    - Create handler for STOP_ALL intent (keywords: "STOP", "UNSUBSCRIBE")
    - Create handler for START_ALL intent (keyword: "START")
    - Each handler updates preferences and sends confirmation
    - _Requirements: 46.5, 46.6, 47.1, 47.2, 47.3, 47.4, 47.5_
  
  - [x] 10.4 Create customer preferences REST API endpoints
    - Implement GET /v1/customers/{id}/preferences
    - Implement PUT /v1/customers/{id}/preferences with reason logging
    - Add consent indicators to customer list views
    - _Requirements: 48.1, 48.2, 48.5_

- [-] 11. Implement messaging service with consent and rate limiting
  - [x] 11.1 Create MessageTemplate and ScheduledMessage models
    - Implement MessageTemplate model with placeholder support
    - Implement ScheduledMessage model with scheduled_at and status
    - Add usage_count tracking for templates
    - _Requirements: 49.1, 49.5, 44.1, 44.2_
  
  - [x] 11.2 Implement MessagingService for outbound messages
    - Create send_message() method with consent validation
    - Create check_rate_limit() using Redis sliding window
    - Create apply_template() for placeholder replacement
    - Create schedule_message() for future delivery
    - Implement respect_quiet_hours() with timezone handling
    - _Requirements: 24.1, 44.3, 44.4, 49.2, 49.3, 49.4, 50.1, 50.2, 53.1, 53.2, 53.3, 53.4, 53.5_
  
  - [x] 11.3 Implement rate limiting with warnings
    - Track message count per tenant in 24-hour rolling window
    - Send warning notification at 80% of daily limit
    - Queue excess messages for next day
    - Flag accounts consistently exceeding limits
    - _Requirements: 50.3, 50.4, 50.5_
  
  - [x] 11.4 Create messaging REST API endpoints
    - Implement POST /v1/messages/send with consent checks
    - Implement POST /v1/messages/schedule
    - Implement POST /v1/templates and GET /v1/templates
    - Add rate limit enforcement to all endpoints
    - _Requirements: 24.1, 24.4, 44.6, 49.6_


- [x] 12. Implement automated messaging system
  - [x] 12.1 Create Celery tasks for transactional messages
    - Create task to send payment confirmation on Order status="paid"
    - Create task to send shipment notification on Order status="shipped"
    - Create task to send payment failed message on transaction failure
    - Create task to send booking confirmation on Appointment creation
    - Add retry logic with exponential backoff (3 attempts)
    - _Requirements: 41.1, 41.2, 41.3, 41.4, 41.5, 41.6_
  
  - [x] 12.2 Create Celery tasks for appointment reminders
    - Create scheduled task to send 24-hour appointment reminders
    - Create scheduled task to send 2-hour appointment reminders
    - Check reminder_messages consent before sending
    - Cancel reminders if appointment is canceled
    - _Requirements: 42.1, 42.2, 42.3, 42.4, 42.5_
  
  - [x] 12.3 Create Celery task for re-engagement messages
    - Create task to identify conversations inactive for 7 days
    - Send personalized re-engagement message with call-to-action
    - Check promotional_messages consent before sending
    - Update conversation status to "dormant" after 14 days no response
    - _Requirements: 43.1, 43.2, 43.3, 43.4, 43.5_
  
  - [x] 12.4 Integrate automated messages with order and appointment workflows
    - Trigger transactional messages on status changes
    - Schedule appointment reminders on booking creation
    - Wire all automated messages through MessagingService for consent checks
    - _Requirements: 41.5, 42.3_

- [x] 13. Implement campaign management system
  - [x] 13.1 Create MessageCampaign model with targeting and metrics
    - Implement MessageCampaign model with target_criteria and status
    - Add fields for A/B testing: is_ab_test, variants
    - Add metric fields: delivery_count, delivered_count, failed_count, read_count, response_count, conversion_count
    - _Requirements: 45.1, 45.4, 54.1_
  
  - [x] 13.2 Implement CampaignService for execution and targeting
    - Create create_campaign() method with validation
    - Create calculate_reach() to count eligible customers
    - Create execute_campaign() to send to all matching customers with consent
    - Implement A/B test variant assignment with equal distribution
    - Track delivery status and engagement metrics
    - _Requirements: 45.2, 45.3, 45.5, 48.4, 54.2_
  
  - [x] 13.3 Implement campaign analytics and reporting
    - Create generate_report() method with engagement metrics
    - Calculate delivery_rate, engagement_rate, conversion tracking
    - Implement A/B test comparison with statistical metrics
    - _Requirements: 45.5, 51.5, 54.3, 54.4_
  
  - [x] 13.4 Create campaign REST API endpoints
    - Implement POST /v1/campaigns with tier limit enforcement
    - Implement GET /v1/campaigns and GET /v1/campaigns/{id}
    - Implement POST /v1/campaigns/{id}/execute
    - Implement GET /v1/campaigns/{id}/report
    - _Requirements: 45.6, 54.5_


- [x] 14. Implement WooCommerce and Shopify integration services
  - [x] 14.1 Implement WooService for product synchronization
    - Create sync_products() method with WooCommerce REST API authentication
    - Implement fetch_products_batch() with pagination (100 items per page)
    - Create transform_product() to convert WooCommerce format to Tulia Product
    - Create transform_variations() to convert to ProductVariant
    - Mark products not in sync as inactive
    - Log sync status and item count
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [x] 14.2 Implement ShopifyService for product synchronization
    - Create sync_products() method with Shopify Admin API authentication
    - Implement fetch_products_batch() with pagination (100 items per page)
    - Create transform_product() to convert Shopify format to Tulia Product
    - Create transform_variants() to convert to ProductVariant
    - Mark products not in sync as inactive
    - Log sync status and item count
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 14.3 Create Celery tasks for scheduled syncs
    - Create task for WooCommerce sync with error handling
    - Create task for Shopify sync with error handling
    - Add retry logic for transient API failures
    - Log all sync operations to WebhookLog or IntegrationLog
    - _Requirements: 8.5, 9.5_
  
  - [x] 14.4 Create catalog sync REST API endpoints
    - Implement POST /v1/catalog/sync/woocommerce
    - Implement POST /v1/catalog/sync/shopify
    - Return sync status and item counts
    - Add authentication error handling
    - _Requirements: 8.1, 9.1_

- [x] 15. Implement analytics service and reporting
  - [x] 15.1 Create AnalyticsDaily model for aggregated metrics ✓
    - Implement AnalyticsDaily model with all metric fields
    - Add unique constraint on (tenant, date)
    - Create indexes for date range queries
    - Migration applied: 0001_initial
    - _Requirements: 17.2_
  
  - [x] 15.2 Implement AnalyticsService for metric calculation
    - Create get_overview() method with date range aggregation
    - Create get_daily_metrics() method
    - Create calculate_booking_conversion_rate() method
    - Create calculate_no_show_rate() method
    - Create get_messaging_analytics() grouped by message_type
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 17.5, 17.6, 51.1, 51.2, 51.3, 51.4_
  
  - [x] 15.3 Create nightly analytics rollup Celery task
    - Implement task to aggregate metrics for each tenant
    - Count messages, conversations, orders, bookings
    - Calculate revenue from paid/fulfilled orders
    - Calculate conversion rates and no-show rates
    - Create or update AnalyticsDaily records
    - Log completion status
    - _Requirements: 17.1, 17.3, 17.4, 36.1, 36.2_
  
  - [x] 15.4 Create analytics REST API endpoints
    - Implement GET /v1/analytics/overview with range parameter
    - Implement GET /v1/analytics/daily
    - Implement GET /v1/analytics/messaging
    - Implement GET /v1/analytics/funnel for conversion tracking
    - Implement GET /v1/admin/analytics/revenue for platform operators
    - _Requirements: 16.1, 36.3, 36.4, 36.5_


- [x] 16. Implement order and cart management
  - [x] 16.1 Create Cart and Order models
    - Implement Cart model with items JSON field and subtotal
    - Implement Order model with status, items, payment_ref
    - Add indexes for order queries by tenant and status
    - _Requirements: 7.2, 7.3_
  
  - [x] 16.2 Implement cart operations in intent handlers
    - Update ADD_TO_CART handler to create/update Cart
    - Validate ProductVariant belongs to Product
    - Check stock availability before adding to cart
    - Return updated cart state with item count and subtotal
    - _Requirements: 6.2, 6.3, 6.4, 6.5_
  
  - [x] 16.3 Implement order creation in CHECKOUT_LINK handler
    - Create Order with status="draft" from Cart items
    - Calculate subtotal, shipping, and total
    - Generate payment checkout link (stub or integration)
    - Clear cart after order creation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [x] 16.4 Create order REST API endpoints
    - Implement POST /v1/orders
    - Implement GET /v1/orders with filtering by status
    - Implement GET /v1/orders/{id}
    - Implement PUT /v1/orders/{id} for status updates
    - Trigger automated messages on status changes
    - _Requirements: 41.1, 41.2_

- [ ] 17. Implement payment facilitation integration
  - [ ] 17.1 Add payment processing to order workflow
    - Integrate payment gateway (Pesapal/Mpesa/Stripe) for checkout links
    - Handle payment webhooks for order status updates
    - Trigger wallet credit on successful payment
    - Calculate and apply transaction fees based on tier
    - _Requirements: 32.2, 32.3, 32.4, 35.4, 35.5, 37.3_
  
  - [ ] 17.2 Add payment facilitation checks based on subscription tier
    - Check payment_facilitation flag before enabling wallet features
    - Allow external checkout links for tiers without facilitation
    - Auto-create wallet on tier upgrade
    - Require zero balance before tier downgrade
    - _Requirements: 37.1, 37.2, 37.4, 37.5_

- [ ] 18. Implement rate limiting and security features
  - [ ] 18.1 Implement Redis-based rate limiting
    - Create rate limiter using Redis sliding window algorithm
    - Apply per-tenant limits based on subscription tier
    - Track API requests and webhook calls separately
    - Return 429 with Retry-After header when limit exceeded
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5_
  
  - [ ] 18.2 Implement CORS validation
    - Validate Origin header against tenant.allowed_origins
    - Support wildcard for development environments
    - Apply strict mode for production
    - _Requirements: 1.8_
  
  - [ ] 18.3 Implement PII encryption utilities
    - Create encryption/decryption functions using AES-256-GCM
    - Implement custom Django field for encrypted data
    - Support encrypted field lookups in queries
    - Mask PII in audit logs and exports
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_


- [ ] 19. Implement API documentation and utilities
  - [ ] 19.1 Configure drf-spectacular for OpenAPI schema generation
    - Install and configure drf-spectacular
    - Add schema decorators to all API views
    - Document request/response schemas
    - Document required headers (X-TENANT-ID, X-TENANT-API-KEY)
    - Include example requests and responses
    - _Requirements: 21.1, 21.3, 21.4, 21.5_
  
  - [ ] 19.2 Create Swagger UI endpoint
    - Configure Swagger UI at /schema/swagger/
    - Enable interactive API testing
    - _Requirements: 21.2_
  
  - [ ] 19.3 Create health check endpoint
    - Implement GET /v1/health endpoint
    - Check PostgreSQL connectivity
    - Check Redis connectivity
    - Check Celery worker availability
    - Return 200 if all healthy, 503 if any dependency down
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_
  
  - [ ] 19.4 Create test utilities endpoint
    - Implement POST /v1/test/send-whatsapp for testing
    - Add authentication and tenant scoping
    - _Requirements: None (utility)_

- [ ] 20. Implement admin endpoints for platform operators
  - [ ] 20.1 Create admin analytics endpoints
    - Implement GET /v1/admin/analytics/revenue
    - Support grouping by date, tier, and tenant
    - Calculate payment_volume, platform_fees, subscription_revenue
    - _Requirements: 36.3, 36.4, 36.5_
  
  - [ ] 20.2 Create admin tenant management endpoints
    - Implement GET /v1/admin/tenants
    - Implement POST /v1/admin/tenants/{id}/subscription for tier changes
    - Implement subscription waiver functionality
    - _Requirements: 30.1, 30.2, 30.3, 30.4, 30.5_
  
  - [ ] 20.3 Create admin withdrawal processing endpoint
    - Implement POST /v1/admin/wallet/withdrawals/{id}/process
    - Update transaction status to completed or failed
    - Handle balance credit-back on failure
    - _Requirements: 34.4, 34.5_

- [ ] 21. Implement conversation and customer management endpoints
  - [ ] 21.1 Create conversation REST API endpoints
    - Implement GET /v1/conversations with filtering and pagination
    - Implement GET /v1/conversations/{id}
    - Implement GET /v1/conversations/{id}/messages
    - Implement POST /v1/conversations/{id}/handoff
    - _Requirements: 15.2, 15.3_
  
  - [ ] 21.2 Create customer REST API endpoints
    - Implement GET /v1/customers with filtering
    - Implement GET /v1/customers/{id}
    - Display consent status indicators in list view
    - Support customer data export with PII masking options
    - _Requirements: 48.2, 48.3, 20.5_


- [ ] 22. Implement caching and performance optimizations
  - [ ] 22.1 Add Redis caching for frequently accessed data
    - Cache tenant configuration (TTL: 1 hour)
    - Cache product/service catalog (TTL: 15 minutes)
    - Cache customer preferences (TTL: 5 minutes)
    - Cache availability windows (TTL: 1 hour)
    - Implement cache invalidation on write operations
    - _Requirements: None (performance)_
  
  - [ ] 22.2 Optimize database queries
    - Add select_related() for foreign key queries
    - Add prefetch_related() for reverse relations
    - Review and optimize N+1 query patterns
    - Add database query logging in development
    - _Requirements: None (performance)_
  
  - [ ] 22.3 Implement pagination for all list endpoints
    - Use DRF pagination with default page size of 50
    - Support page_size query parameter
    - Return pagination metadata (count, next, previous)
    - _Requirements: None (performance)_

- [ ] 23. Implement monitoring and observability
  - [ ] 23.1 Configure structured logging
    - Set up JSON logging format
    - Include request_id, tenant_id in all logs
    - Mask sensitive data (phone numbers, API keys)
    - Configure log levels per environment
    - _Requirements: 25.1, 25.2, 25.3_
  
  - [ ] 23.2 Configure Sentry error tracking
    - Install and configure Sentry SDK
    - Add user context (tenant_id, customer_id)
    - Add breadcrumbs for debugging
    - Configure release tracking
    - Set up performance monitoring
    - _Requirements: 25.4_
  
  - [ ] 23.3 Add Celery task logging
    - Log task start with task_id and parameters
    - Log task completion with result summary
    - Log task failures with error details
    - Log retry attempts with reason
    - Send failures to Sentry
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_

- [ ] 24. Create seed data and demo fixtures
  - Create seed script for 3 subscription tiers
  - Create 3 demo tenants (one per tier)
  - Seed 50 products and 10 services per tenant
  - Create 100 demo customers with varied consent preferences
  - Generate historical messages and orders for analytics
  - Create availability windows for demo services
  - _Requirements: None (demo/testing)_

- [ ] 25. Write integration tests for critical flows
  - Test end-to-end webhook flow: Twilio → Intent → Handler → Response
  - Test product sync from mock WooCommerce/Shopify
  - Test appointment booking with capacity validation
  - Test order creation and wallet credit flow
  - Test campaign execution with consent filtering
  - Test subscription billing and status updates
  - Test tenant isolation (cross-tenant access attempts)
  - _Requirements: None (testing)_

- [ ] 26. Create Postman collection for API testing
  - Document all REST API endpoints
  - Include authentication examples
  - Add test cases for success and error scenarios
  - Test rate limiting and pagination
  - Export collection for distribution
  - _Requirements: 21.5 (documentation)_

- [ ] 27. Write deployment documentation
  - Document environment variables and configuration
  - Create Docker Compose setup for local development
  - Document database migration process
  - Create deployment checklist
  - Document monitoring and alerting setup
  - _Requirements: None (documentation)_
