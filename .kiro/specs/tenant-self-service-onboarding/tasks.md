# Implementation Plan

- [x] 1. Set up authentication infrastructure
  - Create User model enhancements for email verification
  - Create PasswordResetToken model for password reset flow
  - Add database migrations for new fields
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Implement JWT authentication service
  - [x] 2.1 Create AuthService class with JWT generation and validation methods
    - Implement generate_jwt() using PyJWT library
    - Implement validate_jwt() with expiration checking
    - Add JWT configuration to settings (secret key, algorithm, expiration)
    - _Requirements: 1.5_
  
  - [x] 2.2 Create user registration logic
    - Implement register_user() method in AuthService
    - Hash password using Django's make_password
    - Generate email verification token
    - Create User, Tenant, TenantUser, and TenantSettings in transaction
    - Assign Owner role with all permissions
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [x] 2.3 Create email verification logic
    - Implement verify_email() method in AuthService
    - Send verification email with token link
    - Handle token validation and expiration
    - _Requirements: 1.2, 1.3_

- [x] 3. Create authentication API endpoints
  - [x] 3.1 Implement registration endpoint (POST /v1/auth/register)
    - Create RegistrationSerializer with validation
    - Validate email uniqueness
    - Call AuthService.register_user()
    - Return JWT token and tenant info
    - _Requirements: 1.1, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [x] 3.2 Implement login endpoint (POST /v1/auth/login)
    - Create LoginSerializer
    - Validate credentials using User.check_password()
    - Generate JWT token
    - Update last_login_at timestamp
    - _Requirements: 1.5_
  
  - [x] 3.3 Implement email verification endpoint (POST /v1/auth/verify-email)
    - Accept verification token
    - Call AuthService.verify_email()
    - Return success response
    - _Requirements: 1.2, 1.3_
  
  - [x] 3.4 Implement password reset endpoints
    - POST /v1/auth/forgot-password - generate reset token
    - POST /v1/auth/reset-password - reset password with token
    - _Requirements: 1.1_
  
  - [x] 3.5 Implement user profile endpoints
    - GET /v1/auth/me - get current user
    - PUT /v1/auth/me - update user profile
    - _Requirements: 1.1_

- [x] 4. Enhance TenantContextMiddleware for JWT authentication
  - [x] 4.1 Add JWT token extraction from Authorization header
    - Parse "Bearer <token>" format
    - Validate JWT and extract user
    - Handle token expiration errors
    - _Requirements: 1.5, 12.3, 12.4, 12.5_
  
  - [x] 4.2 Add tenant context resolution
    - Extract tenant ID from X-TENANT-ID header
    - Validate user has TenantUser membership
    - Assemble scopes from user's roles in tenant
    - Attach user, tenant, membership, scopes to request
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 5. Implement tenant management service
  - [x] 5.1 Create TenantService class
    - Implement create_tenant() method
    - Implement get_user_tenants() method
    - Implement validate_tenant_access() method
    - Implement invite_user() method
    - Implement soft_delete_tenant() method
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 12.1, 12.2, 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 6. Create tenant management API endpoints
  - [x] 6.1 Implement tenant list endpoint (GET /v1/tenants)
    - Return all tenants where user has membership
    - Include tenant name, slug, status, role, onboarding status
    - _Requirements: 12.1, 12.2_
  
  - [x] 6.2 Implement tenant creation endpoint (POST /v1/tenants)
    - Create TenantSerializer with validation
    - Validate unique business name and slug
    - Call TenantService.create_tenant()
    - Return tenant details
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [x] 6.3 Implement tenant detail endpoint (GET /v1/tenants/{id})
    - Validate user has membership
    - Return full tenant details with onboarding status
    - _Requirements: 12.1, 12.2_
  
  - [x] 6.4 Implement tenant update endpoint (PUT /v1/tenants/{id})
    - Require users:manage scope
    - Update tenant basic info
    - _Requirements: 11.3_
  
  - [x] 6.5 Implement tenant deletion endpoint (DELETE /v1/tenants/{id})
    - Require users:manage scope and Owner role
    - Call TenantService.soft_delete_tenant()
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 6.6 Implement tenant member management endpoints
    - GET /v1/tenants/{id}/members - list members
    - POST /v1/tenants/{id}/members - invite user
    - DELETE /v1/tenants/{id}/members/{user_id} - remove member
    - _Requirements: 3.5_

- [x] 7. Add onboarding tracking to TenantSettings model
  - [x] 7.1 Add onboarding fields to TenantSettings ✓
    - Add onboarding_status JSONField
    - Add onboarding_completed BooleanField
    - Add onboarding_completed_at DateTimeField
    - Create migration
    - Migration applied: 0006_add_onboarding_tracking
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [x] 7.2 Create OnboardingService class
    - Implement get_onboarding_status() method
    - Implement mark_step_complete() method
    - Implement check_completion() method
    - Implement send_reminder() method
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 8. Create onboarding API endpoints
  - [x] 8.1 Implement onboarding status endpoint (GET /v1/settings/onboarding)
    - Call OnboardingService.get_onboarding_status()
    - Return completion percentage and pending steps
    - URL routing wired to /v1/settings/onboarding
    - _Requirements: 4.3, 10.1, 10.2_
  
  - [x] 8.2 Implement onboarding completion endpoint (POST /v1/settings/onboarding/complete)
    - Accept step name
    - Call OnboardingService.mark_step_complete()
    - Check if all required steps complete
    - URL routing wired to /v1/settings/onboarding/complete
    - _Requirements: 4.2, 4.4_

- [x] 9. Implement settings management service
  - [x] 9.1 Create SettingsService class with credential management
    - Implement get_or_create_settings() method
    - Implement update_twilio_credentials() with Twilio API validation
    - Implement update_woocommerce_credentials() with WooCommerce API validation
    - Implement update_shopify_credentials() with Shopify API validation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 9.2 Add payment method management to SettingsService
    - Implement add_payment_method() with Stripe tokenization
    - Implement set_default_payment_method()
    - Implement remove_payment_method()
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [x] 9.3 Add payout method management to SettingsService
    - Implement update_payout_method() with encryption
    - Validate required fields based on method type
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [x] 9.4 Add API key management to SettingsService
    - Implement generate_api_key() with secure random generation
    - Implement revoke_api_key()
    - Store only key hashes (SHA-256)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 10. Create integration credentials API endpoints
  - [x] 10.1 Implement Twilio settings endpoints
    - GET /v1/settings/integrations/twilio - return masked credentials
    - PUT /v1/settings/integrations/twilio - update credentials
    - DELETE /v1/settings/integrations/twilio - remove credentials
    - Require integrations:manage scope
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1, 11.5_
  
  - [x] 10.2 Implement WooCommerce settings endpoints
    - GET /v1/settings/integrations/woocommerce
    - PUT /v1/settings/integrations/woocommerce
    - DELETE /v1/settings/integrations/woocommerce
    - Require integrations:manage scope
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.5_
  
  - [x] 10.3 Implement Shopify settings endpoints
    - GET /v1/settings/integrations/shopify
    - PUT /v1/settings/integrations/shopify
    - DELETE /v1/settings/integrations/shopify
    - Require integrations:manage scope
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.5_
  
  - [x] 10.4 Implement integrations list endpoint
    - GET /v1/settings/integrations - list all integrations with status
    - Return masked credentials and last sync status
    - _Requirements: 6.5, 11.1_

- [ ] 11. Create payment and payout API endpoints
  - [x] 11.1 Implement payment methods endpoints
    - GET /v1/settings/payment-methods - list payment methods
    - POST /v1/settings/payment-methods - add payment method
    - PUT /v1/settings/payment-methods/{id}/default - set default
    - DELETE /v1/settings/payment-methods/{id} - remove payment method
    - Require finance:manage scope
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 11.5_
  
  - [x] 11.2 Implement payout method endpoints
    - GET /v1/settings/payout-method - get payout method
    - PUT /v1/settings/payout-method - update payout method
    - DELETE /v1/settings/payout-method - remove payout method
    - Require finance:manage scope
    - Check payment facilitation enabled
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 11.2, 11.5_

- [x] 12. Create business settings API endpoints
  - [x] 12.1 Implement business settings endpoint (GET /v1/settings/business)
    - Return timezone, business hours, quiet hours, notification preferences
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 12.2 Implement business settings update endpoint (PUT /v1/settings/business)
    - Validate timezone against IANA database
    - Validate business hours format
    - Validate quiet hours ranges
    - Update notification preferences
    - Require users:manage OR integrations:manage scope
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 11.3, 11.5_

- [ ] 13. Create API key management endpoints
  - [ ] 13.1 Implement API keys list endpoint (GET /v1/settings/api-keys)
    - Return masked keys (first 8 characters) with metadata
    - _Requirements: 13.3_
  
  - [ ] 13.2 Implement API key generation endpoint (POST /v1/settings/api-keys)
    - Generate 32-character random key
    - Store hash in Tenant.api_keys
    - Return plain key once
    - Log to AuditLog
    - _Requirements: 13.1, 13.2, 11.5_
  
  - [ ] 13.3 Implement API key revocation endpoint (DELETE /v1/settings/api-keys/{id})
    - Remove key from Tenant.api_keys
    - Log to AuditLog
    - _Requirements: 13.4, 11.5_

- [ ] 14. Implement validation and error handling
  - [ ] 14.1 Create custom exception classes
    - AuthenticationError
    - PermissionDeniedError
    - ValidationError
    - CredentialValidationError
    - OnboardingIncompleteError
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [ ] 14.2 Add credential validation helpers
    - Validate Twilio credentials by making test API call
    - Validate WooCommerce credentials by fetching store info
    - Validate Shopify credentials by fetching shop info
    - Return detailed error messages from external APIs
    - _Requirements: 5.2, 5.3, 6.2, 6.3, 6.4, 14.2_
  
  - [ ] 14.3 Add input validation to all serializers
    - Email format validation
    - Password strength validation
    - Phone number format validation
    - URL format validation
    - Required field validation
    - _Requirements: 14.1, 14.3, 14.4_

- [ ] 15. Implement audit logging for all settings changes
  - [ ] 15.1 Add AuditLog calls to AuthService
    - Log user registration
    - Log user login
    - Log email verification
    - Log password reset
    - _Requirements: 11.5_
  
  - [ ] 15.2 Add AuditLog calls to SettingsService
    - Log credential updates (Twilio, WooCommerce, Shopify)
    - Log payment method changes
    - Log payout method changes
    - Log API key generation and revocation
    - Log business settings updates
    - _Requirements: 5.5, 6.5, 11.5_
  
  - [ ] 15.3 Add AuditLog calls to TenantService
    - Log tenant creation
    - Log tenant deletion
    - Log member invitations
    - Log member removals
    - _Requirements: 11.5_

- [ ] 16. Implement onboarding reminder system
  - [ ] 16.1 Create Celery task for onboarding reminders
    - Query tenants with incomplete onboarding
    - Send reminder emails at 3 days and 7 days
    - Include completion percentage and pending steps
    - _Requirements: 10.3, 10.4_
  
  - [ ] 16.2 Schedule periodic task in Celery beat
    - Run daily to check for tenants needing reminders
    - _Requirements: 10.3, 10.4_

- [ ] 17. Add rate limiting to authentication endpoints
  - [ ] 17.1 Configure django-ratelimit for auth endpoints
    - POST /v1/auth/register - 10 requests/minute per IP
    - POST /v1/auth/login - 10 requests/minute per IP
    - POST /v1/auth/forgot-password - 5 requests/minute per IP
    - _Requirements: 1.1, 1.5_
  
  - [ ] 17.2 Configure rate limiting for settings endpoints
    - All POST/PUT/DELETE - 60 requests/minute per user
    - _Requirements: 11.5_

- [ ] 18. Create serializers for all API endpoints
  - [ ] 18.1 Create authentication serializers
    - RegistrationSerializer
    - LoginSerializer
    - EmailVerificationSerializer
    - PasswordResetRequestSerializer
    - PasswordResetSerializer
    - UserProfileSerializer
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [ ] 18.2 Create tenant serializers
    - TenantListSerializer
    - TenantDetailSerializer
    - TenantCreateSerializer
    - TenantUpdateSerializer
    - TenantMemberSerializer
    - _Requirements: 3.1, 3.2, 12.1, 12.2_
  
  - [ ] 18.3 Create settings serializers
    - TwilioCredentialsSerializer
    - WooCommerceCredentialsSerializer
    - ShopifyCredentialsSerializer
    - PaymentMethodSerializer
    - PayoutMethodSerializer
    - BusinessSettingsSerializer
    - APIKeySerializer
    - OnboardingStatusSerializer
    - _Requirements: 5.1, 5.4, 6.1, 6.4, 7.1, 7.4, 8.1, 8.4, 9.1, 9.4, 13.1, 13.3, 4.3_

- [ ] 19. Add OpenAPI documentation with drf-spectacular
  - [ ] 19.1 Add schema decorators to all endpoints
    - Add @extend_schema with summary, description, examples
    - Document request/response formats
    - Document error responses (400, 401, 403, 404, 500)
    - Document required scopes
    - _Requirements: All_
  
  - [ ] 19.2 Configure spectacular settings
    - Set API title, version, description
    - Configure authentication schemes (JWT)
    - Configure servers (dev, staging, prod)
    - _Requirements: All_

- [ ] 20. Wire up URL routing
  - [ ] 20.1 Create apps/auth/urls.py with authentication routes
    - /v1/auth/register
    - /v1/auth/login
    - /v1/auth/logout
    - /v1/auth/verify-email
    - /v1/auth/forgot-password
    - /v1/auth/reset-password
    - /v1/auth/refresh-token
    - /v1/auth/me
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [ ] 20.2 Create apps/tenants/urls_management.py with tenant routes
    - /v1/tenants
    - /v1/tenants/{id}
    - /v1/tenants/{id}/members
    - /v1/tenants/{id}/members/{user_id}
    - _Requirements: 3.1, 3.2, 3.5, 12.1, 12.2, 15.1_
  
  - [ ] 20.3 Create apps/tenants/urls_settings.py with settings routes
    - /v1/settings/onboarding
    - /v1/settings/integrations/*
    - /v1/settings/payment-methods
    - /v1/settings/payout-method
    - /v1/settings/business
    - /v1/settings/api-keys
    - _Requirements: 4.3, 5.1, 5.4, 6.1, 6.4, 7.1, 7.4, 8.1, 8.4, 9.1, 9.4, 13.1, 13.2, 13.3_
  
  - [ ] 20.4 Include all URL patterns in config/urls.py
    - Include apps.auth.urls
    - Include apps.tenants.urls_management
    - Include apps.tenants.urls_settings
    - _Requirements: All_

- [ ] 21. Create database migrations
  - [ ] 21.1 Create migration for User model enhancements
    - Add email_verified field
    - Add email_verification_token field
    - Add email_verification_sent_at field
    - _Requirements: 1.2, 1.3_
  
  - [ ] 21.2 Create migration for PasswordResetToken model
    - Create new model with all fields
    - Add indexes
    - _Requirements: 1.1_
  
  - [ ] 21.3 Create migration for TenantSettings enhancements
    - Add onboarding_status field
    - Add onboarding_completed field
    - Add onboarding_completed_at field
    - _Requirements: 4.1, 4.2_
  
  - [ ] 21.4 Run migrations and verify schema
    - python manage.py makemigrations
    - python manage.py migrate
    - Verify all fields created correctly
    - _Requirements: All_

- [ ] 22. Write comprehensive tests
  - [ ] 22.1 Write authentication unit tests
    - Test user registration creates user + tenant
    - Test login with valid/invalid credentials
    - Test email verification flow
    - Test password reset flow
    - Test JWT generation and validation
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [ ] 22.2 Write tenant management unit tests
    - Test tenant creation assigns Owner role
    - Test user can list only their tenants
    - Test tenant context switching validates membership
    - Test soft delete cascades correctly
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 12.1, 12.2, 12.3, 12.4, 12.5, 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [ ] 22.3 Write settings management unit tests
    - Test credential encryption and validation
    - Test payment method tokenization
    - Test payout method encryption
    - Test API key generation and hashing
    - Test onboarding status tracking
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 22.4 Write RBAC integration tests
    - Test integrations:manage scope required for credentials
    - Test finance:manage scope required for payment methods
    - Test users:manage scope required for tenant deletion
    - Test 403 responses without required scopes
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 22.5 Write tenant isolation tests
    - Test user cannot access other tenant's settings
    - Test API key from one tenant cannot access another
    - Test no cross-tenant data leakage
    - _Requirements: 12.3, 12.4_
  
  - [ ] 22.6 Write security tests
    - Test credentials stored encrypted
    - Test payment methods stored as tokens only
    - Test API keys stored as hashes only
    - Test passwords hashed with bcrypt
    - Test rate limiting on auth endpoints
    - _Requirements: 5.1, 5.5, 7.1, 7.5, 13.1, 13.5_
  
  - [ ] 22.7 Write integration tests for complete flows
    - Test registration → login → create tenant → add settings
    - Test multi-tenant flow with context switching
    - Test onboarding completion flow
    - _Requirements: All_

- [ ] 23. Update environment configuration
  - [ ] 23.1 Add JWT configuration to settings.py
    - JWT_SECRET_KEY
    - JWT_ALGORITHM
    - JWT_EXPIRATION_HOURS
    - _Requirements: 1.5_
  
  - [ ] 23.2 Add Stripe configuration to settings.py
    - STRIPE_SECRET_KEY
    - STRIPE_PUBLISHABLE_KEY
    - _Requirements: 7.1_
  
  - [ ] 23.3 Add email configuration to settings.py
    - EMAIL_BACKEND
    - EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS
    - EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
    - DEFAULT_FROM_EMAIL
    - _Requirements: 1.2, 10.3, 10.4_
  
  - [ ] 23.4 Add frontend URL configuration
    - FRONTEND_URL for email links
    - _Requirements: 1.2, 1.3_
  
  - [ ] 23.5 Update .env.example with all new variables
    - Document all required environment variables
    - _Requirements: All_

- [ ] 24. Create management commands
  - [ ] 24.1 Create seed_demo_tenant command
    - Create demo user with verified email
    - Create demo tenant with all settings configured
    - Useful for development and testing
    - _Requirements: All_
  
  - [ ] 24.2 Create send_onboarding_reminders command
    - Query tenants with incomplete onboarding
    - Send reminder emails
    - Can be run manually or via Celery
    - _Requirements: 10.3, 10.4_

- [ ] 25. Update documentation
  - [ ] 25.1 Create API usage guide
    - Document registration and login flow
    - Document tenant creation and switching
    - Document settings configuration
    - Include example curl commands
    - _Requirements: All_
  
  - [ ] 25.2 Create onboarding guide for tenants
    - Step-by-step setup instructions
    - Screenshots of each step
    - Troubleshooting common issues
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.1, 10.2_
  
  - [ ] 25.3 Update deployment documentation
    - Add new environment variables
    - Add migration steps
    - Add Celery task configuration
    - _Requirements: All_
