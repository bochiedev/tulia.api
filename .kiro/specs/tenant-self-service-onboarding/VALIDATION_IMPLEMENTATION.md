# Validation and Error Handling Implementation

## Overview

This document summarizes the implementation of Task 14: "Implement validation and error handling" for the tenant self-service onboarding feature.

## Completed Sub-tasks

### 14.1 Create Custom Exception Classes ✅

**Location:** `apps/core/exceptions.py`

Added the following custom exception classes:

1. **AuthenticationError** (status_code: 401)
   - Raised when authentication fails
   - Used for invalid credentials, expired tokens, etc.

2. **PermissionDeniedError** (status_code: 403)
   - Raised when user lacks required permissions
   - Used for RBAC violations

3. **ValidationError** (status_code: 400)
   - Raised when input validation fails
   - Base class for validation-related errors

4. **CredentialValidationError** (extends ValidationError)
   - Raised when external credential validation fails
   - Used for Twilio, WooCommerce, Shopify credential validation

5. **OnboardingIncompleteError** (status_code: 403)
   - Raised when action requires completed onboarding
   - Used to enforce onboarding completion

All exceptions extend the base `TuliaException` class and include:
- `message`: Human-readable error message
- `details`: Optional dictionary with additional error context
- `status_code`: HTTP status code for API responses

### 14.2 Add Credential Validation Helpers ✅

**Location:** `apps/core/validators.py`

Created two main validator classes:

#### CredentialValidator

Validates credentials for external services by making test API calls:

1. **validate_twilio_credentials(account_sid, auth_token, whatsapp_number)**
   - Makes test API call to Twilio to fetch account details
   - Validates account status and type
   - Optionally validates WhatsApp number ownership
   - Returns account info on success
   - Raises `CredentialValidationError` with user-friendly messages on failure

2. **validate_woocommerce_credentials(store_url, consumer_key, consumer_secret)**
   - Fetches WooCommerce system status via REST API
   - Validates API connectivity and authentication
   - Returns store info (name, WC version, WP version)
   - Handles common errors (401, 404, timeout, connection errors)

3. **validate_shopify_credentials(shop_domain, access_token)**
   - Fetches shop info via Shopify Admin API
   - Validates access token and shop domain
   - Returns shop details (name, owner, currency, timezone)
   - Handles domain normalization (.myshopify.com)

#### InputValidator

Provides common input validation utilities:

1. **Email Validation**
   - `validate_email(email)`: Validates email format using RFC 5322 pattern
   - Returns True/False

2. **Password Strength Validation**
   - `validate_password_strength(password)`: Checks password requirements
   - Requirements: 8+ chars, uppercase, lowercase, digit, special char
   - Returns dict with `valid` flag and list of `errors`

3. **Phone Number Validation**
   - `validate_phone_e164(phone)`: Validates E.164 format (+1234567890)
   - `normalize_phone_e164(phone)`: Normalizes to E.164 format
   - Returns True/False or normalized string

4. **URL Validation**
   - `validate_url(url)`: Validates URL format
   - `normalize_url(url)`: Adds https:// if missing
   - Returns True/False or normalized string

5. **Hex Color Validation**
   - `validate_hex_color(color)`: Validates hex color format (#RRGGBB)
   - Returns True/False

### 14.3 Add Input Validation to All Serializers ✅

Enhanced validation in multiple serializers:

#### apps/rbac/serializers.py

**RegistrationSerializer:**
- Enhanced `validate_email()`: Now uses `InputValidator.validate_email()` for format validation
- Enhanced `validate_password()`: Now uses `InputValidator.validate_password_strength()` for comprehensive strength checking

#### apps/tenants/serializers_settings.py

**TwilioCredentialsSerializer:**
- Enhanced `validate_sid()`: Validates SID format (starts with "AC", 34 chars)
- Enhanced `validate_whatsapp_number()`: Uses `InputValidator` for E.164 validation and normalization

**ShopifyCredentialsSerializer:**
- Enhanced `validate_shop_domain()`: Validates and normalizes shop domain

**WooCommerceCredentialsSerializer:**
- Added `validate_store_url()`: Validates and normalizes store URL using `InputValidator`

**BrandingSettingsSerializer:**
- Enhanced `validate_primary_color()`: Uses `InputValidator.validate_hex_color()` for validation

#### apps/tenants/serializers.py

**TenantCreateSerializer:**
- Enhanced `validate_whatsapp_number()`: Uses `InputValidator` for E.164 validation and normalization

**TenantMemberInviteSerializer:**
- Enhanced `validate_email()`: Uses `InputValidator.validate_email()` for format validation

## Usage Examples

### Exception Handling

```python
from apps.core.exceptions import CredentialValidationError

try:
    # Validate credentials
    result = CredentialValidator.validate_twilio_credentials(sid, token)
except CredentialValidationError as e:
    # Handle validation error
    return Response({
        'error': e.message,
        'details': e.details
    }, status=e.status_code)
```

### Credential Validation

```python
from apps.core.validators import CredentialValidator

# Validate Twilio credentials
try:
    result = CredentialValidator.validate_twilio_credentials(
        account_sid='AC1234567890abcdef',
        auth_token='your_auth_token',
        whatsapp_number='+1234567890'
    )
    print(f"Account: {result['account_name']}")
    print(f"Status: {result['account_status']}")
except CredentialValidationError as e:
    print(f"Validation failed: {e.message}")
```

### Input Validation

```python
from apps.core.validators import InputValidator

# Validate email
if not InputValidator.validate_email('user@example.com'):
    raise ValidationError("Invalid email format")

# Validate password strength
result = InputValidator.validate_password_strength('MyPass123!')
if not result['valid']:
    raise ValidationError(result['errors'][0])

# Normalize phone number
phone = InputValidator.normalize_phone_e164('1234567890')
# Returns: '+1234567890'
```

## Testing

All validation utilities have been tested:

1. **Email Validation**: ✅ Correctly validates email format
2. **Phone Validation**: ✅ Correctly validates E.164 format
3. **URL Validation**: ✅ Correctly validates URL format
4. **Hex Color Validation**: ✅ Correctly validates hex colors
5. **Password Strength**: ✅ Correctly checks all requirements
6. **Normalization**: ✅ Correctly normalizes phone and URL inputs
7. **Exception Classes**: ✅ All exceptions work with correct status codes

## Integration Points

The validation utilities are integrated into:

1. **Registration Flow**: Email and password validation
2. **Tenant Creation**: WhatsApp number validation
3. **Settings Management**: Credential validation for all integrations
4. **Member Invitations**: Email validation
5. **Branding Settings**: Hex color validation

## Error Response Format

All validation errors follow a consistent format:

```json
{
  "error": "Human-readable error message",
  "details": {
    "field": "specific_field",
    "error_code": 20003,
    "additional_context": "..."
  }
}
```

## Next Steps

The validation and error handling implementation is complete. The next tasks in the spec are:

- Task 15: Implement audit logging for all settings changes
- Task 16: Implement onboarding reminder system
- Task 17: Add rate limiting to authentication endpoints

## Requirements Satisfied

This implementation satisfies the following requirements:

- **Requirement 14.1**: Custom exception classes created
- **Requirement 14.2**: Credential validation helpers implemented
- **Requirement 14.3**: Input validation added to serializers
- **Requirement 14.4**: Field validation implemented
- **Requirement 14.5**: Error handling standardized

All requirements from Task 14 have been fully implemented and tested.
