# Requirements Document

## Introduction

This feature enables self-service tenant registration and onboarding for WabotIQ. Users can register accounts, create multiple tenants, and configure tenant settings including integration credentials, payment methods, and business preferences through a guided onboarding flow. The system tracks onboarding completion and reminds users to complete pending setup steps.

**Authentication Model**:
- User registration and login use JWT-based authentication
- Tenant management endpoints (create, list, switch) require JWT token only
- Tenant settings endpoints require JWT + X-TENANT-ID + X-TENANT-API-KEY headers
- All endpoints use RBAC for authorization based on user's role in the tenant

## Glossary

- **User**: An individual with login credentials who can be a member of multiple tenants
- **Tenant**: An isolated business account with its own customers, catalog, and settings
- **TenantUser**: The membership relationship linking a User to a Tenant with assigned roles
- **TenantSettings**: Secure storage for tenant configuration including encrypted credentials
- **Onboarding**: The guided process of configuring essential tenant settings after registration
- **Registration System**: The authentication and tenant creation subsystem
- **Settings API**: The REST API endpoints for managing tenant configuration
- **Payment Method**: Tokenized payment card or bank account for subscription billing
- **Payout Method**: Bank account or mobile money account for receiving tenant earnings
- **Integration Credentials**: API keys and tokens for third-party services (Twilio, WooCommerce, Shopify)

## Requirements

### Requirement 1: User Registration and Authentication

**User Story:** As a new user, I want to register an account with email and password, so that I can create and manage tenants.

#### Acceptance Criteria

1. WHEN a user submits valid registration data (email, password, name), THE Registration System SHALL create a new User account with hashed password
2. WHEN a user registers, THE Registration System SHALL send an email verification link to the provided email address
3. WHEN a user clicks the verification link, THE Registration System SHALL mark the email as verified and enable account access
4. WHEN a user attempts to register with an existing email, THE Registration System SHALL return a validation error indicating the email is already registered
5. WHEN a user logs in with valid credentials, THE Registration System SHALL issue JWT access token (1 hour expiry) and refresh token (7 days expiry)

### Requirement 2: Tenant Creation During Registration

**User Story:** As a newly registered user, I want to automatically create my first tenant during registration, so that I can start using the platform immediately.

#### Acceptance Criteria

1. WHEN a user completes registration, THE Registration System SHALL create a Tenant with status 'trial' and assign the user as Owner
2. WHEN a Tenant is created during registration, THE Registration System SHALL generate a unique slug from the business name
3. WHEN a Tenant is created, THE Registration System SHALL create a TenantSettings record with default values
4. WHEN a Tenant is created, THE Registration System SHALL set trial_start_date to current timestamp and trial_end_date to 14 days from registration
5. WHEN a user is assigned as Owner, THE Registration System SHALL create a TenantUser record with the Owner role and all permissions

### Requirement 3: Multi-Tenant Support Per User

**User Story:** As an existing user, I want to create additional tenants, so that I can manage multiple businesses from one account.

#### Acceptance Criteria

1. WHEN an authenticated user requests to create a new tenant, THE Tenant Management API SHALL create a Tenant with the user as Owner
2. WHEN a user creates a new tenant, THE Tenant Management API SHALL validate that the business name and slug are unique
3. WHEN a user creates a new tenant, THE Tenant Management API SHALL initialize TenantSettings with empty integration credentials
4. WHEN a user requests their tenant list, THE Tenant Management API SHALL return all tenants where the user has a TenantUser membership
5. WHEN a user switches tenant context, THE Tenant Management API SHALL validate the user has membership in the target tenant before allowing access

### Requirement 4: Onboarding Status Tracking

**User Story:** As a tenant owner, I want the system to track my onboarding progress, so that I know which setup steps remain incomplete.

#### Acceptance Criteria

1. WHEN a Tenant is created, THE Onboarding System SHALL initialize onboarding_status in TenantSettings with all steps marked as incomplete
2. WHEN a user completes an onboarding step, THE Onboarding System SHALL update the corresponding step status to 'completed' with completion timestamp
3. WHEN a user requests onboarding status, THE Settings API SHALL return completion percentage and list of pending steps
4. WHEN all required onboarding steps are completed, THE Onboarding System SHALL mark onboarding_completed as true with completion timestamp
5. WHILE onboarding is incomplete, THE Settings API SHALL include onboarding_reminder flag in tenant detail responses

### Requirement 5: Twilio Credentials Management

**User Story:** As a tenant owner, I want to securely add my Twilio credentials, so that I can send and receive WhatsApp messages.

#### Acceptance Criteria

1. WHEN a user submits Twilio credentials (SID, token, webhook secret, WhatsApp number), THE Settings API SHALL encrypt and store them in TenantSettings
2. WHEN Twilio credentials are saved, THE Settings API SHALL validate the credentials by making a test API call to Twilio
3. WHEN Twilio credentials are invalid, THE Settings API SHALL return a validation error with details from Twilio API
4. WHEN a user requests Twilio settings, THE Settings API SHALL return masked credentials (last 4 characters only) and configuration status
5. WHEN Twilio credentials are updated, THE Settings API SHALL log the change in AuditLog with the user who made the change

### Requirement 6: E-Commerce Integration Credentials

**User Story:** As a tenant owner, I want to connect my WooCommerce or Shopify store, so that I can sync products and orders automatically.

#### Acceptance Criteria

1. WHEN a user submits WooCommerce credentials (store URL, consumer key, consumer secret), THE Settings API SHALL encrypt and store them in TenantSettings
2. WHEN a user submits Shopify credentials (shop domain, access token), THE Settings API SHALL encrypt and store them in TenantSettings
3. WHEN integration credentials are saved, THE Settings API SHALL validate connectivity by fetching store information from the platform API
4. WHEN integration credentials are invalid, THE Settings API SHALL return a validation error with details from the platform API
5. WHEN a user requests integration settings, THE Settings API SHALL return masked credentials and last sync status with timestamp

### Requirement 7: Payment Method Management

**User Story:** As a tenant owner, I want to add a payment method for subscription billing, so that I can upgrade from trial to a paid plan.

#### Acceptance Criteria

1. WHEN a user adds a payment method, THE Settings API SHALL tokenize the card details via Stripe and store only the payment method ID
2. WHEN a payment method is added, THE Settings API SHALL store card metadata (last4, brand, exp_month, exp_year) in stripe_payment_methods array
3. WHEN a user sets a default payment method, THE Settings API SHALL mark it as is_default and unmark other payment methods
4. WHEN a user requests payment methods, THE Settings API SHALL return the list with masked card details (no full card numbers)
5. WHEN a user removes a payment method, THE Settings API SHALL delete the Stripe PaymentMethod and remove it from stripe_payment_methods array

### Requirement 8: Payout Method Configuration

**User Story:** As a tenant owner, I want to configure my payout method, so that I can receive earnings from facilitated payments.

#### Acceptance Criteria

1. WHEN a user submits payout details (method type, account details), THE Settings API SHALL encrypt and store them in TenantSettings.payout_details
2. WHEN payout method is 'bank_transfer', THE Settings API SHALL validate required fields (account_number, routing_number, account_holder_name)
3. WHEN payout method is 'mobile_money', THE Settings API SHALL validate required fields (phone_number, provider)
4. WHEN a user requests payout settings, THE Settings API SHALL return masked account details (last 4 digits only)
5. WHERE payment facilitation is enabled for the tenant tier, THE Settings API SHALL allow payout method configuration

### Requirement 9: Business Settings Configuration

**User Story:** As a tenant owner, I want to configure business settings like timezone and operating hours, so that automated messages respect my business schedule.

#### Acceptance Criteria

1. WHEN a user updates timezone, THE Settings API SHALL validate the timezone string against IANA timezone database
2. WHEN a user updates business hours, THE Settings API SHALL store them as JSON with day-of-week keys and time ranges
3. WHEN a user updates quiet hours, THE Settings API SHALL validate that start time is before end time or handle overnight ranges
4. WHEN a user updates notification preferences, THE Settings API SHALL store them by channel (email, sms) and event type
5. WHEN business settings are updated, THE Settings API SHALL apply changes immediately to scheduled message processing

### Requirement 10: Onboarding Completion and Reminders

**User Story:** As a tenant owner, I want to see reminders to complete onboarding, so that I don't forget essential setup steps.

#### Acceptance Criteria

1. WHILE onboarding is incomplete, THE Tenant Detail API SHALL include onboarding_incomplete flag and list of pending steps
2. WHEN a user logs in with incomplete onboarding, THE Dashboard API SHALL return onboarding reminder with completion percentage
3. WHEN onboarding has been incomplete for 3 days, THE Notification System SHALL send an email reminder with pending steps
4. WHEN onboarding has been incomplete for 7 days, THE Notification System SHALL send a second email reminder with setup assistance offer
5. WHEN all required steps are completed, THE Onboarding System SHALL mark onboarding as complete and stop sending reminders

### Requirement 11: Settings Access Control

**User Story:** As a tenant admin, I want settings access to be controlled by RBAC scopes, so that only authorized users can modify sensitive configuration.

#### Acceptance Criteria

1. WHEN a user requests to view integration credentials, THE Settings API SHALL require 'integrations:manage' scope
2. WHEN a user requests to view payment methods, THE Settings API SHALL require 'finance:manage' scope
3. WHEN a user requests to update business settings, THE Settings API SHALL require 'users:manage' OR 'integrations:manage' scope
4. WHEN a user without required scope attempts to access settings, THE Settings API SHALL return 403 Forbidden with scope requirement details
5. WHEN any settings are modified, THE Settings API SHALL log the action in AuditLog with user, tenant, and changed fields

### Requirement 12: Tenant List and Context Switching

**User Story:** As a user with multiple tenants, I want to view all my tenants and switch between them, so that I can manage different businesses.

#### Acceptance Criteria

1. WHEN a user requests their tenant list, THE Tenant API SHALL return all tenants where the user has TenantUser membership
2. WHEN a tenant is returned in the list, THE Tenant API SHALL include tenant name, slug, status, role, and onboarding completion status
3. WHEN a user switches tenant context by setting X-TENANT-ID header, THE Middleware SHALL validate membership before allowing access
4. WHEN a user attempts to access a tenant without membership, THE Middleware SHALL return 403 Forbidden
5. WHEN a user switches tenant context, THE Middleware SHALL assemble scopes from the user's roles in that tenant

### Requirement 13: API Key Generation for Tenants

**User Story:** As a tenant owner, I want to generate API keys for my tenant, so that I can integrate with external systems.

#### Acceptance Criteria

1. WHEN a user requests to generate an API key, THE Settings API SHALL create a random 32-character key and store its hash in Tenant.api_keys
2. WHEN an API key is generated, THE Settings API SHALL return the plain key once and store metadata (name, created_at, created_by)
3. WHEN a user lists API keys, THE Settings API SHALL return masked keys (first 8 characters only) with metadata
4. WHEN a user revokes an API key, THE Settings API SHALL remove it from Tenant.api_keys array
5. WHEN an API request uses an API key, THE Middleware SHALL validate the key hash against Tenant.api_keys before granting access

### Requirement 14: Settings Validation and Error Handling

**User Story:** As a tenant owner, I want clear validation errors when I submit invalid settings, so that I can correct issues quickly.

#### Acceptance Criteria

1. WHEN a user submits invalid data, THE Settings API SHALL return 400 Bad Request with field-specific error messages
2. WHEN credential validation fails, THE Settings API SHALL return the error message from the external service (Twilio, Stripe, etc.)
3. WHEN a required field is missing, THE Settings API SHALL return a validation error indicating which field is required
4. WHEN a field exceeds maximum length, THE Settings API SHALL return a validation error with the maximum allowed length
5. WHEN an unexpected error occurs, THE Settings API SHALL log the error to Sentry and return 500 Internal Server Error with a generic message

### Requirement 15: Tenant Deletion and Data Cleanup

**User Story:** As a tenant owner, I want to delete my tenant account, so that I can remove my data when I no longer need the service.

#### Acceptance Criteria

1. WHEN a user requests to delete a tenant, THE Tenant API SHALL require 'users:manage' scope and Owner role
2. WHEN a tenant is deleted, THE Tenant API SHALL soft-delete the Tenant record by setting deleted_at timestamp
3. WHEN a tenant is deleted, THE Tenant API SHALL cascade soft-delete to all related records (Customers, Orders, Messages, etc.)
4. WHEN a tenant is deleted, THE Tenant API SHALL revoke all API keys and invalidate active sessions
5. WHEN a deleted tenant is accessed, THE Middleware SHALL return 404 Not Found as if the tenant never existed
