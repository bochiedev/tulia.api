# Design Document

## Overview

The Tenant Self-Service Onboarding system enables users to register accounts, create multiple tenants, and configure tenant settings through a comprehensive REST API. The design follows WabotIQ's multi-tenant architecture with strict RBAC enforcement, encrypted credential storage, and comprehensive audit logging.

The system consists of three main components:
1. **Authentication & Registration API** - User account creation and JWT-based authentication
2. **Tenant Management API** - Tenant creation, listing, and context switching
3. **Settings Management API** - Secure configuration of credentials, payment methods, and preferences

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Application                     │
│  (Registration, Onboarding Wizard, Settings Dashboard)       │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS/REST
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                       │
│  - Rate Limiting                                             │
│  - Request ID Injection                                      │
│  - CORS Handling                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│   Auth   │  │  Tenant  │  │ Settings │
│   API    │  │   API    │  │   API    │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│   RBAC   │  │ Tenants  │  │  Stripe  │
│ Service  │  │ Service  │  │   API    │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   PostgreSQL DB      │
        │  - Users             │
        │  - Tenants           │
        │  - TenantSettings    │
        │  - RBAC Tables       │
        └──────────────────────┘
```

### Request Flow

#### Registration Flow
```
User → POST /v1/auth/register
  ↓
Validate email/password
  ↓
Create User (hashed password)
  ↓
Create first Tenant (trial status)
  ↓
Create TenantUser (Owner role)
  ↓
Create TenantSettings (defaults)
  ↓
Send verification email
  ↓
Return JWT token + tenant info
```

#### Settings Update Flow
```
User → POST /v1/settings/integrations/twilio
  ↓
Middleware: Validate JWT
  ↓
Middleware: Resolve tenant from X-TENANT-ID
  ↓
Middleware: Assemble scopes from roles
  ↓
Permission Check: integrations:manage
  ↓
Validate credentials with Twilio API
  ↓
Encrypt and store in TenantSettings
  ↓
Update onboarding_status
  ↓
Log to AuditLog
  ↓
Return masked credentials + status
```

## Components and Interfaces

### 1. Authentication API

**Endpoints:**

```python
POST   /v1/auth/register          # Register new user + first tenant
POST   /v1/auth/login             # Login with email/password
POST   /v1/auth/logout            # Invalidate JWT token
POST   /v1/auth/verify-email      # Verify email from link
POST   /v1/auth/forgot-password   # Request password reset
POST   /v1/auth/reset-password    # Reset password with token
POST   /v1/auth/refresh-token     # Refresh JWT token
GET    /v1/auth/me                # Get current user profile
PUT    /v1/auth/me                # Update user profile
```

**Key Classes:**

```python
class AuthService:
    """Handles user authentication and registration."""
    
    @staticmethod
    def register_user(email: str, password: str, first_name: str, 
                     last_name: str, business_name: str) -> tuple[User, Tenant, str]:
        """
        Register new user with first tenant.
        
        Returns:
            (user, tenant, jwt_token)
        """
        pass
    
    @staticmethod
    def login(email: str, password: str) -> tuple[User, str]:
        """
        Authenticate user and return JWT token.
        
        Returns:
            (user, jwt_token)
        """
        pass
    
    @staticmethod
    def verify_email(token: str) -> User:
        """Verify email address from token."""
        pass
    
    @staticmethod
    def generate_jwt(user: User) -> str:
        """Generate JWT token for user."""
        pass
    
    @staticmethod
    def validate_jwt(token: str) -> User:
        """Validate JWT token and return user."""
        pass
```

### 2. Tenant Management API

**Endpoints:**

```python
GET    /v1/tenants                # List user's tenants
POST   /v1/tenants                # Create new tenant
GET    /v1/tenants/{id}           # Get tenant details
PUT    /v1/tenants/{id}           # Update tenant info
DELETE /v1/tenants/{id}           # Delete tenant (soft delete)
GET    /v1/tenants/{id}/members   # List tenant members
POST   /v1/tenants/{id}/members   # Invite user to tenant
DELETE /v1/tenants/{id}/members/{user_id}  # Remove member
```

**Key Classes:**

```python
class TenantService:
    """Handles tenant lifecycle and membership."""
    
    @staticmethod
    def create_tenant(user: User, name: str, slug: str, 
                     whatsapp_number: str) -> Tenant:
        """
        Create new tenant with user as Owner.
        
        Automatically creates:
        - Tenant record (trial status)
        - TenantSettings with defaults
        - TenantUser with Owner role
        - Onboarding status tracking
        """
        pass
    
    @staticmethod
    def get_user_tenants(user: User) -> QuerySet[Tenant]:
        """Get all tenants where user has membership."""
        pass
    
    @staticmethod
    def validate_tenant_access(user: User, tenant: Tenant) -> TenantUser:
        """
        Validate user has access to tenant.
        
        Raises:
            PermissionDenied if no membership
        """
        pass
    
    @staticmethod
    def invite_user(tenant: Tenant, email: str, role_names: list[str], 
                   invited_by: User) -> TenantUser:
        """Invite user to tenant with specified roles."""
        pass
    
    @staticmethod
    def soft_delete_tenant(tenant: Tenant, user: User):
        """Soft delete tenant and cascade to related records."""
        pass
```

### 3. Settings Management API

**Endpoints:**

```python
# Onboarding Status
GET    /v1/settings/onboarding              # Get onboarding status
POST   /v1/settings/onboarding/complete     # Mark step as complete

# Integration Credentials
GET    /v1/settings/integrations            # List all integrations
GET    /v1/settings/integrations/twilio    # Get Twilio settings
POST   /v1/settings/integrations/twilio    # Create/update Twilio credentials
DELETE /v1/settings/integrations/twilio    # Remove Twilio credentials
GET    /v1/settings/integrations/woocommerce
POST   /v1/settings/integrations/woocommerce  # Create/update WooCommerce credentials
DELETE /v1/settings/integrations/woocommerce
GET    /v1/settings/integrations/shopify
POST   /v1/settings/integrations/shopify   # Create/update Shopify credentials
DELETE /v1/settings/integrations/shopify

# Payment Methods
GET    /v1/settings/payment-methods         # List payment methods
POST   /v1/settings/payment-methods         # Add payment method
PUT    /v1/settings/payment-methods/{id}/default  # Set default
DELETE /v1/settings/payment-methods/{id}    # Remove payment method

# Payout Methods
GET    /v1/settings/payout-method           # Get payout method
PUT    /v1/settings/payout-method           # Update payout method
DELETE /v1/settings/payout-method           # Remove payout method

# Business Settings
GET    /v1/settings/business                # Get business settings
PUT    /v1/settings/business                # Update business settings

# API Keys
GET    /v1/settings/api-keys                # List API keys (masked)
POST   /v1/settings/api-keys                # Generate new API key
DELETE /v1/settings/api-keys/{id}           # Revoke API key

# Notifications
GET    /v1/settings/notifications           # Get notification preferences
PUT    /v1/settings/notifications           # Update notification preferences
```

**Key Classes:**

```python
class SettingsService:
    """Handles tenant settings management."""
    
    @staticmethod
    def get_or_create_settings(tenant: Tenant) -> TenantSettings:
        """Get or create TenantSettings for tenant."""
        pass
    
    @staticmethod
    def update_twilio_credentials(tenant: Tenant, sid: str, token: str, 
                                  webhook_secret: str, whatsapp_number: str) -> TenantSettings:
        """
        Update Twilio credentials with validation.
        
        Steps:
        1. Validate credentials with Twilio API
        2. Encrypt and store in TenantSettings
        3. Update onboarding status
        4. Log to AuditLog
        """
        pass
    
    @staticmethod
    def update_woocommerce_credentials(tenant: Tenant, store_url: str, 
                                       consumer_key: str, consumer_secret: str) -> TenantSettings:
        """Update WooCommerce credentials with validation."""
        pass
    
    @staticmethod
    def update_shopify_credentials(tenant: Tenant, shop_domain: str, 
                                   access_token: str) -> TenantSettings:
        """Update Shopify credentials with validation."""
        pass
    
    @staticmethod
    def add_payment_method(tenant: Tenant, stripe_token: str) -> dict:
        """
        Add payment method via Stripe.
        
        Steps:
        1. Create/get Stripe customer
        2. Attach payment method
        3. Store payment method ID and metadata
        4. Return masked card details
        """
        pass
    
    @staticmethod
    def set_default_payment_method(tenant: Tenant, payment_method_id: str):
        """Set default payment method."""
        pass
    
    @staticmethod
    def update_payout_method(tenant: Tenant, method: str, details: dict) -> TenantSettings:
        """
        Update payout method with encrypted details.
        
        Validates required fields based on method type.
        """
        pass
    
    @staticmethod
    def generate_api_key(tenant: Tenant, name: str, created_by: User) -> tuple[str, dict]:
        """
        Generate new API key.
        
        Returns:
            (plain_key, metadata)
        """
        pass
    
    @staticmethod
    def revoke_api_key(tenant: Tenant, key_hash: str):
        """Revoke API key by removing from tenant.api_keys."""
        pass


class OnboardingService:
    """Handles onboarding status tracking."""
    
    REQUIRED_STEPS = [
        'twilio_configured',
        'payment_method_added',
        'business_settings_configured',
    ]
    
    OPTIONAL_STEPS = [
        'woocommerce_configured',
        'shopify_configured',
        'payout_method_configured',
    ]
    
    @staticmethod
    def get_onboarding_status(tenant: Tenant) -> dict:
        """
        Get onboarding status with completion percentage.
        
        Returns:
            {
                'completed': bool,
                'completion_percentage': int,
                'required_steps': {...},
                'optional_steps': {...},
                'pending_steps': [...]
            }
        """
        pass
    
    @staticmethod
    def mark_step_complete(tenant: Tenant, step: str):
        """Mark onboarding step as complete."""
        pass
    
    @staticmethod
    def check_completion(tenant: Tenant) -> bool:
        """Check if all required steps are complete."""
        pass
    
    @staticmethod
    def send_reminder(tenant: Tenant):
        """Send onboarding reminder email."""
        pass
```

### 4. Middleware Enhancement

**TenantContextMiddleware** (existing, needs enhancement):

```python
class TenantContextMiddleware(MiddlewareMixin):
    """
    Resolve tenant context and assemble user scopes.
    
    Enhanced to support:
    - JWT authentication
    - Tenant context switching
    - Scope assembly from roles
    """
    
    def process_request(self, request):
        """
        Process incoming request:
        1. Extract JWT from Authorization header
        2. Validate JWT and get user
        3. Extract tenant ID from X-TENANT-ID header
        4. Validate user has membership in tenant
        5. Assemble scopes from user's roles
        6. Attach to request: user, tenant, membership, scopes
        """
        pass
```

## Data Models

### Enhanced Models

**TenantSettings** (existing, add onboarding tracking):

```python
class TenantSettings(BaseModel):
    # ... existing fields ...
    
    # Onboarding Status
    onboarding_status = models.JSONField(
        default=dict,
        blank=True,
        help_text="Onboarding step completion status"
    )
    onboarding_completed = models.BooleanField(
        default=False,
        help_text="Whether onboarding is fully complete"
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was completed"
    )
    
    def initialize_onboarding_status(self):
        """Initialize onboarding status with all steps incomplete."""
        self.onboarding_status = {
            'twilio_configured': {'completed': False, 'completed_at': None},
            'payment_method_added': {'completed': False, 'completed_at': None},
            'business_settings_configured': {'completed': False, 'completed_at': None},
            'woocommerce_configured': {'completed': False, 'completed_at': None},
            'shopify_configured': {'completed': False, 'completed_at': None},
            'payout_method_configured': {'completed': False, 'completed_at': None},
        }
        self.save(update_fields=['onboarding_status'])
```

**User** (existing, add email verification):

```python
class User(BaseModel):
    # ... existing fields ...
    
    # Email Verification
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether email has been verified"
    )
    email_verification_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Email verification token"
    )
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When verification email was sent"
    )
```

### New Models

**PasswordResetToken**:

```python
class PasswordResetToken(BaseModel):
    """
    Password reset tokens for forgot password flow.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True
    )
    expires_at = models.DateTimeField(
        help_text="Token expiration time (24 hours)"
    )
    used = models.BooleanField(
        default=False,
        help_text="Whether token has been used"
    )
    
    class Meta:
        db_table = 'password_reset_tokens'
        indexes = [
            models.Index(fields=['token', 'expires_at', 'used']),
        ]
```

## Error Handling

### Error Response Format

All API errors follow a consistent format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Specific field error",
    "validation_errors": {...}
  }
}
```

### Error Codes

```python
class ErrorCodes:
    # Authentication
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    
    # Authorization
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    
    # Validation
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_CREDENTIALS_FORMAT = "INVALID_CREDENTIALS_FORMAT"
    CREDENTIAL_VALIDATION_FAILED = "CREDENTIAL_VALIDATION_FAILED"
    
    # Business Logic
    ONBOARDING_INCOMPLETE = "ONBOARDING_INCOMPLETE"
    PAYMENT_FACILITATION_NOT_ENABLED = "PAYMENT_FACILITATION_NOT_ENABLED"
    TRIAL_EXPIRED = "TRIAL_EXPIRED"
```

### Exception Classes

```python
class AuthenticationError(TuliaException):
    """Raised when authentication fails."""
    status_code = 401


class PermissionDeniedError(TuliaException):
    """Raised when user lacks required permissions."""
    status_code = 403


class ValidationError(TuliaException):
    """Raised when input validation fails."""
    status_code = 400


class CredentialValidationError(ValidationError):
    """Raised when external credential validation fails."""
    pass


class OnboardingIncompleteError(TuliaException):
    """Raised when action requires completed onboarding."""
    status_code = 403
```

## Testing Strategy

### Unit Tests

**Authentication Tests:**
- User registration with valid data creates user + tenant
- Registration with existing email returns error
- Login with valid credentials returns JWT
- Login with invalid credentials returns error
- Email verification marks email as verified
- Password reset flow generates token and updates password

**Tenant Management Tests:**
- Create tenant assigns user as Owner with all permissions
- User can list only tenants where they have membership
- Tenant context switching validates membership
- Soft delete cascades to related records
- Invite user creates TenantUser with specified roles

**Settings Tests:**
- Twilio credentials are encrypted and validated
- WooCommerce credentials are encrypted and validated
- Shopify credentials are encrypted and validated
- Payment method tokenization via Stripe
- Payout method encryption and validation
- API key generation and revocation
- Onboarding status tracking and completion

### Integration Tests

**Registration Flow:**
1. POST /v1/auth/register with valid data
2. Verify user created with hashed password
3. Verify tenant created with trial status
4. Verify TenantUser created with Owner role
5. Verify TenantSettings created with defaults
6. Verify JWT token returned and valid

**Settings Update Flow:**
1. Login and get JWT token
2. POST /v1/settings/integrations/twilio with credentials
3. Verify credentials validated with Twilio API
4. Verify credentials encrypted in database
5. Verify onboarding status updated
6. Verify AuditLog entry created
7. GET /v1/settings/integrations/twilio returns masked credentials

**Multi-Tenant Flow:**
1. User creates second tenant
2. Switch context to first tenant (X-TENANT-ID)
3. Verify access to first tenant's data
4. Switch context to second tenant
5. Verify access to second tenant's data
6. Verify no cross-tenant data leakage

### RBAC Tests

**Permission Enforcement:**
- User without integrations:manage cannot update Twilio settings (403)
- User with integrations:manage can update Twilio settings (200)
- User without finance:manage cannot add payment method (403)
- User with finance:manage can add payment method (200)
- All settings changes logged to AuditLog

**Tenant Isolation:**
- User A in Tenant 1 cannot access Tenant 2 settings
- User B in Tenant 2 cannot access Tenant 1 settings
- API key from Tenant 1 cannot access Tenant 2 data

### Security Tests

**Credential Security:**
- Twilio credentials stored encrypted in database
- WooCommerce credentials stored encrypted
- Shopify credentials stored encrypted
- Payout details stored encrypted
- Payment methods stored as Stripe tokens only (no full card numbers)
- API keys stored as hashes only

**Authentication Security:**
- Passwords hashed with bcrypt
- JWT tokens expire after 24 hours
- Email verification required before full access
- Password reset tokens expire after 24 hours
- Rate limiting on auth endpoints (10 requests/minute)

## Security Considerations

### Credential Storage

All sensitive credentials are encrypted using `EncryptedCharField` and `EncryptedTextField`:
- Twilio SID, token, webhook secret
- WooCommerce consumer key, consumer secret
- Shopify access token
- Payout account details
- OpenAI API keys

### Payment Card Security (PCI-DSS Compliance)

- Never store full card numbers
- Use Stripe tokenization for all payment methods
- Store only Stripe PaymentMethod IDs and metadata (last4, brand, exp)
- All card processing happens on Stripe's servers

### API Key Security

- API keys are 32-character random strings
- Only key hashes stored in database (SHA-256)
- Plain key shown once during generation
- Keys can be revoked at any time

### Rate Limiting

```python
# Authentication endpoints
@ratelimit(key='ip', rate='10/m', method='POST')
def register_view(request):
    pass

@ratelimit(key='ip', rate='10/m', method='POST')
def login_view(request):
    pass

# Settings endpoints
@ratelimit(key='user_or_ip', rate='60/m', method=['POST', 'PUT', 'DELETE'])
def settings_view(request):
    pass
```

### Audit Logging

All sensitive operations are logged to `AuditLog`:
- User registration and login
- Tenant creation and deletion
- Settings updates (credentials, payment methods)
- API key generation and revocation
- Role assignments and permission changes

## Performance Considerations

### Database Indexing

```python
# TenantSettings
indexes = [
    models.Index(fields=['tenant']),
]

# User
indexes = [
    models.Index(fields=['email']),
    models.Index(fields=['email_verified', 'is_active']),
]

# TenantUser
indexes = [
    models.Index(fields=['tenant', 'user', 'is_active']),
    models.Index(fields=['user', 'is_active']),
]
```

### Caching Strategy

```python
# Cache user's tenant list (5 minutes)
cache_key = f"user_tenants:{user.id}"
tenants = cache.get(cache_key)
if not tenants:
    tenants = TenantService.get_user_tenants(user)
    cache.set(cache_key, tenants, 300)

# Cache tenant settings (10 minutes)
cache_key = f"tenant_settings:{tenant.id}"
settings = cache.get(cache_key)
if not settings:
    settings = SettingsService.get_or_create_settings(tenant)
    cache.set(cache_key, settings, 600)

# Invalidate cache on update
cache.delete(f"tenant_settings:{tenant.id}")
```

### Query Optimization

```python
# Prefetch related data to avoid N+1 queries
tenants = Tenant.objects.filter(
    tenant_users__user=user,
    tenant_users__is_active=True
).select_related(
    'subscription_tier'
).prefetch_related(
    'tenant_users__user_roles__role'
).distinct()
```

## Deployment Considerations

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=<random-secret-key>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Stripe Configuration
STRIPE_SECRET_KEY=<stripe-secret-key>
STRIPE_PUBLISHABLE_KEY=<stripe-publishable-key>

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<sendgrid-api-key>
DEFAULT_FROM_EMAIL=noreply@tulia.ai

# Frontend URL (for email links)
FRONTEND_URL=https://app.tulia.ai
```

### Database Migrations

```bash
# Create migrations for new fields
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Seed canonical permissions
python manage.py seed_permissions

# Seed default roles for existing tenants
python manage.py seed_tenant_roles
```

### Monitoring

- Track registration conversion rate
- Monitor onboarding completion rate
- Alert on credential validation failures
- Track API key usage by tenant
- Monitor JWT token expiration and refresh patterns

## API Documentation

All endpoints are documented using `drf-spectacular`:

```python
@extend_schema(
    summary="Register new user",
    description="Create new user account with first tenant",
    request=RegistrationSerializer,
    responses={
        201: UserSerializer,
        400: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Registration Request',
            value={
                'email': 'user@example.com',
                'password': 'SecurePass123!',
                'first_name': 'John',
                'last_name': 'Doe',
                'business_name': 'Acme Corp'
            }
        )
    ]
)
def register(request):
    pass
```

OpenAPI schema available at:
- `/schema` - YAML format
- `/schema/swagger/` - Swagger UI
- `/schema/redoc/` - ReDoc UI
