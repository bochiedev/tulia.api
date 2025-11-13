# Tenant Self-Service Onboarding API Guide

## Overview

This guide covers the complete tenant self-service onboarding flow, from user registration to tenant configuration. The onboarding system enables users to:

- Register accounts with email/password authentication
- Create and manage multiple tenants
- Configure integration credentials (Twilio, WooCommerce, Shopify)
- Set up payment methods and payout accounts
- Configure business settings and preferences
- Generate API keys for external integrations

## Table of Contents

1. [Authentication Flow](#authentication-flow)
2. [Tenant Management](#tenant-management)
3. [Settings Configuration](#settings-configuration)
4. [Onboarding Tracking](#onboarding-tracking)
5. [API Key Management](#api-key-management)
6. [Complete Examples](#complete-examples)

---

## Authentication Flow

### Base URL

```
Development: http://localhost:8000
Production:  https://api.yourdomain.com
```

### 1. User Registration

Register a new user account and automatically create their first tenant.

**Endpoint:** `POST /v1/auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "business_name": "Acme Corp"
}
```

**Response:** `201 Created`
```json
{
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "email_verified": false
  },
  "tenant": {
    "id": "tenant-uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "status": "trial",
    "trial_end_date": "2025-11-27T00:00:00Z"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```


**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe",
    "business_name": "Acme Corp"
  }'
```

**Notes:**
- Password must be at least 8 characters
- Email must be unique across all users
- Business name is used to create the first tenant
- A verification email is sent automatically
- JWT tokens are returned immediately (1 hour expiry for access, 7 days for refresh)
- User is assigned as Owner with all permissions

### 2. Email Verification

Verify email address using the token sent via email.

**Endpoint:** `POST /v1/auth/verify-email`

**Request:**
```json
{
  "token": "verification-token-from-email"
}
```

**Response:** `200 OK`
```json
{
  "message": "Email verified successfully",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "email_verified": true
  }
}
```

**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123def456"
  }'
```


### 3. User Login

Authenticate with email and password to receive JWT tokens.

**Endpoint:** `POST /v1/auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

### 4. Get Current User Profile

Retrieve the authenticated user's profile information.

**Endpoint:** `GET /v1/auth/me`

**Headers:**
```
Authorization: Bearer <access-token>
```

**Response:** `200 OK`
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "email_verified": true,
  "created_at": "2025-11-13T10:00:00Z"
}
```

**curl Example:**
```bash
curl -X GET http://localhost:8000/v1/auth/me \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```


### 5. Password Reset Flow

Request a password reset and reset the password using the token.

**Step 1: Request Password Reset**

**Endpoint:** `POST /v1/auth/forgot-password`

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset email sent"
}
```

**Step 2: Reset Password**

**Endpoint:** `POST /v1/auth/reset-password`

**Request:**
```json
{
  "token": "reset-token-from-email",
  "new_password": "NewSecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset successfully"
}
```

**curl Examples:**
```bash
# Request reset
curl -X POST http://localhost:8000/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# Reset password
curl -X POST http://localhost:8000/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123def456",
    "new_password": "NewSecurePass123!"
  }'
```

---

## Tenant Management

All tenant management endpoints require JWT authentication.

### 1. List User's Tenants

Get all tenants where the user has membership.

**Endpoint:** `GET /v1/tenants`

**Headers:**
```
Authorization: Bearer <access-token>
```


**Response:** `200 OK`
```json
{
  "count": 2,
  "results": [
    {
      "id": "tenant-uuid-1",
      "name": "Acme Corp",
      "slug": "acme-corp",
      "status": "trial",
      "role": "Owner",
      "onboarding_completed": false,
      "onboarding_completion_percentage": 33,
      "trial_end_date": "2025-11-27T00:00:00Z"
    },
    {
      "id": "tenant-uuid-2",
      "name": "Beta Inc",
      "slug": "beta-inc",
      "status": "active",
      "role": "Admin",
      "onboarding_completed": true,
      "onboarding_completion_percentage": 100,
      "subscription_tier": "Growth"
    }
  ]
}
```

**curl Example:**
```bash
curl -X GET http://localhost:8000/v1/tenants \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### 2. Create New Tenant

Create an additional tenant for the authenticated user.

**Endpoint:** `POST /v1/tenants`

**Headers:**
```
Authorization: Bearer <access-token>
```

**Request:**
```json
{
  "name": "New Business",
  "whatsapp_number": "+14155551234"
}
```

**Response:** `201 Created`
```json
{
  "id": "new-tenant-uuid",
  "name": "New Business",
  "slug": "new-business",
  "status": "trial",
  "whatsapp_number": "+14155551234",
  "trial_start_date": "2025-11-13T00:00:00Z",
  "trial_end_date": "2025-11-27T00:00:00Z",
  "onboarding_completed": false
}
```


**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/tenants \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Business",
    "whatsapp_number": "+14155551234"
  }'
```

**Notes:**
- User is automatically assigned as Owner
- Tenant starts in trial status (14 days by default)
- TenantSettings are created with default values
- Onboarding tracking is initialized

### 3. Get Tenant Details

Retrieve detailed information about a specific tenant.

**Endpoint:** `GET /v1/tenants/{tenant_id}`

**Headers:**
```
Authorization: Bearer <access-token>
```

**Response:** `200 OK`
```json
{
  "id": "tenant-uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "status": "trial",
  "whatsapp_number": "+14155551234",
  "trial_start_date": "2025-11-13T00:00:00Z",
  "trial_end_date": "2025-11-27T00:00:00Z",
  "subscription_tier": null,
  "onboarding_completed": false,
  "onboarding_completion_percentage": 33,
  "pending_onboarding_steps": [
    "payment_method_added",
    "business_settings_configured"
  ],
  "created_at": "2025-11-13T10:00:00Z"
}
```

**curl Example:**
```bash
curl -X GET http://localhost:8000/v1/tenants/tenant-uuid \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```


### 4. Tenant Context Switching

To access tenant-specific resources, include the tenant context headers:

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Example:**
```bash
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key"
```

**Notes:**
- JWT token identifies the user
- X-TENANT-ID specifies which tenant context to use
- X-TENANT-API-KEY authenticates the tenant
- Middleware validates user has membership in the tenant
- User's scopes are assembled from their roles in that tenant

---

## Settings Configuration

All settings endpoints require tenant context headers.

### 1. Twilio Integration

Configure Twilio credentials for WhatsApp messaging.

**Endpoint:** `PUT /v1/settings/integrations/twilio`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `integrations:manage`

**Request:**
```json
{
  "twilio_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "twilio_token": "your-auth-token",
  "webhook_secret": "your-webhook-secret",
  "whatsapp_number": "+14155551234"
}
```

**Response:** `200 OK`
```json
{
  "twilio_sid": "AC****************************xxxx",
  "whatsapp_number": "+14155551234",
  "configured": true,
  "last_validated": "2025-11-13T10:30:00Z"
}
```


**curl Example:**
```bash
curl -X PUT http://localhost:8000/v1/settings/integrations/twilio \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "twilio_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "twilio_token": "your-auth-token",
    "webhook_secret": "your-webhook-secret",
    "whatsapp_number": "+14155551234"
  }'
```

**Notes:**
- Credentials are validated with Twilio API before saving
- Credentials are encrypted at rest
- Only masked values are returned in responses
- Onboarding status is automatically updated

### 2. WooCommerce Integration

Configure WooCommerce store credentials.

**Endpoint:** `PUT /v1/settings/integrations/woocommerce`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `integrations:manage`

**Request:**
```json
{
  "store_url": "https://mystore.com",
  "consumer_key": "ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "consumer_secret": "cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Response:** `200 OK`
```json
{
  "store_url": "https://mystore.com",
  "consumer_key": "ck_************************************xxxx",
  "configured": true,
  "last_sync": "2025-11-13T10:30:00Z"
}
```

**curl Example:**
```bash
curl -X PUT http://localhost:8000/v1/settings/integrations/woocommerce \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "store_url": "https://mystore.com",
    "consumer_key": "ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "consumer_secret": "cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }'
```


### 3. Shopify Integration

Configure Shopify store credentials.

**Endpoint:** `PUT /v1/settings/integrations/shopify`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `integrations:manage`

**Request:**
```json
{
  "shop_domain": "mystore.myshopify.com",
  "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Response:** `200 OK`
```json
{
  "shop_domain": "mystore.myshopify.com",
  "access_token": "shpat_****************************xxxx",
  "configured": true,
  "last_sync": "2025-11-13T10:30:00Z"
}
```

**curl Example:**
```bash
curl -X PUT http://localhost:8000/v1/settings/integrations/shopify \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_domain": "mystore.myshopify.com",
    "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }'
```

### 4. Business Settings

Configure timezone, business hours, and notification preferences.

**Endpoint:** `PUT /v1/settings/business`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `users:manage` OR `integrations:manage`

**Request:**
```json
{
  "timezone": "America/New_York",
  "business_hours": {
    "monday": {"open": "09:00", "close": "17:00"},
    "tuesday": {"open": "09:00", "close": "17:00"},
    "wednesday": {"open": "09:00", "close": "17:00"},
    "thursday": {"open": "09:00", "close": "17:00"},
    "friday": {"open": "09:00", "close": "17:00"},
    "saturday": null,
    "sunday": null
  },
  "quiet_hours": {
    "start": "22:00",
    "end": "08:00"
  },
  "notification_preferences": {
    "email": {
      "new_order": true,
      "new_message": true,
      "low_balance": true
    },
    "sms": {
      "urgent_only": true
    }
  }
}
```


**Response:** `200 OK`
```json
{
  "timezone": "America/New_York",
  "business_hours": {...},
  "quiet_hours": {...},
  "notification_preferences": {...},
  "updated_at": "2025-11-13T10:30:00Z"
}
```

**curl Example:**
```bash
curl -X PUT http://localhost:8000/v1/settings/business \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "timezone": "America/New_York",
    "business_hours": {
      "monday": {"open": "09:00", "close": "17:00"}
    }
  }'
```

### 5. Payment Methods

Add payment methods for subscription billing (Stripe integration).

**Endpoint:** `POST /v1/settings/payment-methods`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `finance:manage`

**Request:**
```json
{
  "stripe_token": "tok_visa"
}
```

**Response:** `201 Created`
```json
{
  "id": "pm_xxxxxxxxxxxxxxxxxxxxxxxx",
  "card": {
    "brand": "visa",
    "last4": "4242",
    "exp_month": 12,
    "exp_year": 2025
  },
  "is_default": true,
  "created_at": "2025-11-13T10:30:00Z"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/settings/payment-methods \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "stripe_token": "tok_visa"
  }'
```

**Notes:**
- Stripe token should be generated client-side using Stripe.js
- Full card numbers are never stored
- Only Stripe PaymentMethod IDs and metadata are stored


### 6. Payout Methods

Configure payout method for receiving earnings (payment facilitation).

**Endpoint:** `PUT /v1/settings/payout-method`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `finance:manage`

**Request (Bank Transfer):**
```json
{
  "method": "bank_transfer",
  "details": {
    "account_number": "123456789",
    "routing_number": "021000021",
    "account_holder_name": "Acme Corp",
    "bank_name": "Chase Bank"
  }
}
```

**Request (Mobile Money):**
```json
{
  "method": "mobile_money",
  "details": {
    "phone_number": "+254712345678",
    "provider": "mpesa",
    "account_name": "John Doe"
  }
}
```

**Response:** `200 OK`
```json
{
  "method": "bank_transfer",
  "details": {
    "account_number": "*****6789",
    "routing_number": "021000021",
    "account_holder_name": "Acme Corp",
    "bank_name": "Chase Bank"
  },
  "configured": true,
  "updated_at": "2025-11-13T10:30:00Z"
}
```

**curl Example:**
```bash
curl -X PUT http://localhost:8000/v1/settings/payout-method \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "bank_transfer",
    "details": {
      "account_number": "123456789",
      "routing_number": "021000021",
      "account_holder_name": "Acme Corp"
    }
  }'
```

**Notes:**
- Payout details are encrypted at rest
- Only masked values are returned
- Available only if payment facilitation is enabled for tenant tier

---

## Onboarding Tracking


### 1. Get Onboarding Status

Check the current onboarding progress and pending steps.

**Endpoint:** `GET /v1/settings/onboarding`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Response:** `200 OK`
```json
{
  "completed": false,
  "completion_percentage": 33,
  "required_steps": {
    "twilio_configured": {
      "completed": true,
      "completed_at": "2025-11-13T10:30:00Z"
    },
    "payment_method_added": {
      "completed": false,
      "completed_at": null
    },
    "business_settings_configured": {
      "completed": false,
      "completed_at": null
    }
  },
  "optional_steps": {
    "woocommerce_configured": {
      "completed": false,
      "completed_at": null
    },
    "shopify_configured": {
      "completed": false,
      "completed_at": null
    },
    "payout_method_configured": {
      "completed": false,
      "completed_at": null
    }
  },
  "pending_steps": [
    "payment_method_added",
    "business_settings_configured"
  ]
}
```

**curl Example:**
```bash
curl -X GET http://localhost:8000/v1/settings/onboarding \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key"
```

**Notes:**
- Required steps must be completed for full onboarding
- Optional steps enhance functionality but aren't required
- Completion percentage is based on required steps only
- Steps are automatically marked complete when configured


### 2. Mark Step Complete (Manual)

Manually mark an onboarding step as complete (usually done automatically).

**Endpoint:** `POST /v1/settings/onboarding/complete`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Request:**
```json
{
  "step": "business_settings_configured"
}
```

**Response:** `200 OK`
```json
{
  "step": "business_settings_configured",
  "completed": true,
  "completed_at": "2025-11-13T10:30:00Z",
  "onboarding_completed": false,
  "completion_percentage": 67
}
```

**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/settings/onboarding/complete \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "business_settings_configured"
  }'
```

---

## API Key Management

### 1. Generate API Key

Create a new API key for tenant authentication.

**Endpoint:** `POST /v1/settings/api-keys`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <existing-api-key>
```

**Required Scope:** `users:manage`

**Request:**
```json
{
  "name": "Production API Key"
}
```

**Response:** `201 Created`
```json
{
  "id": "key-uuid",
  "name": "Production API Key",
  "key": "tulia_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "key_preview": "tulia_live_xxxxxxxx",
  "created_at": "2025-11-13T10:30:00Z",
  "created_by": "user@example.com"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:8000/v1/settings/api-keys \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key"
  }'
```


**IMPORTANT:**
- The full API key is shown only once during generation
- Store it securely - it cannot be retrieved later
- Only the hash is stored in the database
- The key is used in the X-TENANT-API-KEY header

### 2. List API Keys

Get all API keys for the tenant (masked).

**Endpoint:** `GET /v1/settings/api-keys`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Response:** `200 OK`
```json
{
  "count": 2,
  "results": [
    {
      "id": "key-uuid-1",
      "name": "Production API Key",
      "key_preview": "tulia_live_xxxxxxxx",
      "created_at": "2025-11-13T10:30:00Z",
      "created_by": "user@example.com",
      "last_used": "2025-11-13T11:00:00Z"
    },
    {
      "id": "key-uuid-2",
      "name": "Development API Key",
      "key_preview": "tulia_test_xxxxxxxx",
      "created_at": "2025-11-12T09:00:00Z",
      "created_by": "user@example.com",
      "last_used": null
    }
  ]
}
```

**curl Example:**
```bash
curl -X GET http://localhost:8000/v1/settings/api-keys \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key"
```

### 3. Revoke API Key

Revoke an API key to prevent further use.

**Endpoint:** `DELETE /v1/settings/api-keys/{key_id}`

**Headers:**
```
Authorization: Bearer <access-token>
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

**Required Scope:** `users:manage`

**Response:** `204 No Content`

**curl Example:**
```bash
curl -X DELETE http://localhost:8000/v1/settings/api-keys/key-uuid \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key"
```

**Notes:**
- Revoked keys cannot be restored
- All requests using the revoked key will fail immediately
- Action is logged in audit log

---

## Complete Examples


### Example 1: Complete Registration and Onboarding Flow

This example shows the complete flow from registration to full onboarding.

```bash
#!/bin/bash

# Step 1: Register new user
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "SecurePass123!",
    "first_name": "Jane",
    "last_name": "Smith",
    "business_name": "Smith Enterprises"
  }')

# Extract tokens and tenant ID
ACCESS_TOKEN=$(echo $REGISTER_RESPONSE | jq -r '.tokens.access')
TENANT_ID=$(echo $REGISTER_RESPONSE | jq -r '.tenant.id')

echo "Registered! Tenant ID: $TENANT_ID"

# Step 2: Generate API key
API_KEY_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/settings/api-keys \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Initial API Key"
  }')

API_KEY=$(echo $API_KEY_RESPONSE | jq -r '.key')
echo "API Key generated: $API_KEY"

# Step 3: Configure Twilio
curl -X PUT http://localhost:8000/v1/settings/integrations/twilio \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "twilio_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "twilio_token": "your-auth-token",
    "webhook_secret": "your-webhook-secret",
    "whatsapp_number": "+14155551234"
  }'

echo "Twilio configured"

# Step 4: Add payment method
curl -X POST http://localhost:8000/v1/settings/payment-methods \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "stripe_token": "tok_visa"
  }'

echo "Payment method added"

# Step 5: Configure business settings
curl -X PUT http://localhost:8000/v1/settings/business \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "timezone": "America/New_York",
    "business_hours": {
      "monday": {"open": "09:00", "close": "17:00"},
      "tuesday": {"open": "09:00", "close": "17:00"},
      "wednesday": {"open": "09:00", "close": "17:00"},
      "thursday": {"open": "09:00", "close": "17:00"},
      "friday": {"open": "09:00", "close": "17:00"}
    }
  }'

echo "Business settings configured"

# Step 6: Check onboarding status
curl -X GET http://localhost:8000/v1/settings/onboarding \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-TENANT-ID: $TENANT_ID" \
  -H "X-TENANT-API-KEY: $API_KEY"

echo "Onboarding complete!"
```


### Example 2: Multi-Tenant User Flow

This example shows a user managing multiple tenants.

```bash
#!/bin/bash

# Step 1: Login
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }')

ACCESS_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.tokens.access')

# Step 2: List all tenants
TENANTS_RESPONSE=$(curl -s -X GET http://localhost:8000/v1/tenants \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "My Tenants:"
echo $TENANTS_RESPONSE | jq '.results[] | {name: .name, id: .id, role: .role}'

# Step 3: Create new tenant
NEW_TENANT_RESPONSE=$(curl -s -X POST http://localhost:8000/v1/tenants \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Second Business",
    "whatsapp_number": "+14155552345"
  }')

NEW_TENANT_ID=$(echo $NEW_TENANT_RESPONSE | jq -r '.id')
echo "Created new tenant: $NEW_TENANT_ID"

# Step 4: Generate API key for new tenant
# (First, we need an initial API key - this would be done through admin or first setup)

# Step 5: Switch context to new tenant
curl -X GET http://localhost:8000/v1/products \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-TENANT-ID: $NEW_TENANT_ID" \
  -H "X-TENANT-API-KEY: new-tenant-api-key"

echo "Switched to new tenant context"
```

### Example 3: Python SDK Usage

Example using Python requests library:

```python
import requests

BASE_URL = "http://localhost:8000"

class TuliaClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.access_token = None
        self.tenant_id = None
        self.api_key = None
    
    def register(self, email, password, first_name, last_name, business_name):
        """Register new user and create first tenant."""
        response = requests.post(
            f"{self.base_url}/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "business_name": business_name
            }
        )
        response.raise_for_status()
        data = response.json()
        
        self.access_token = data["tokens"]["access"]
        self.tenant_id = data["tenant"]["id"]
        
        return data
    
    def login(self, email, password):
        """Login and get access token."""
        response = requests.post(
            f"{self.base_url}/v1/auth/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        
        self.access_token = data["tokens"]["access"]
        
        return data
    
    def get_headers(self):
        """Get headers for authenticated requests."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        if self.tenant_id and self.api_key:
            headers["X-TENANT-ID"] = self.tenant_id
            headers["X-TENANT-API-KEY"] = self.api_key
        
        return headers
    
    def list_tenants(self):
        """List all tenants for current user."""
        response = requests.get(
            f"{self.base_url}/v1/tenants",
            headers=self.get_headers()
        )
        response.raise_for_status()
        return response.json()
    
    def configure_twilio(self, sid, token, webhook_secret, whatsapp_number):
        """Configure Twilio integration."""
        response = requests.put(
            f"{self.base_url}/v1/settings/integrations/twilio",
            headers=self.get_headers(),
            json={
                "twilio_sid": sid,
                "twilio_token": token,
                "webhook_secret": webhook_secret,
                "whatsapp_number": whatsapp_number
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_onboarding_status(self):
        """Get onboarding status."""
        response = requests.get(
            f"{self.base_url}/v1/settings/onboarding",
            headers=self.get_headers()
        )
        response.raise_for_status()
        return response.json()

# Usage example
client = TuliaClient()

# Register
result = client.register(
    email="newuser@example.com",
    password="SecurePass123!",
    first_name="John",
    last_name="Doe",
    business_name="Doe Enterprises"
)

print(f"Registered! Tenant ID: {client.tenant_id}")

# List tenants
tenants = client.list_tenants()
print(f"My tenants: {tenants}")

# Configure Twilio (after setting api_key)
client.api_key = "your-api-key"
twilio_config = client.configure_twilio(
    sid="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    token="your-auth-token",
    webhook_secret="your-webhook-secret",
    whatsapp_number="+14155551234"
)

print("Twilio configured!")

# Check onboarding
status = client.get_onboarding_status()
print(f"Onboarding: {status['completion_percentage']}% complete")
```


---

## Error Handling

### Common Error Responses

#### 400 Bad Request - Validation Error
```json
{
  "detail": "Validation failed",
  "code": "INVALID_INPUT",
  "field_errors": {
    "email": ["This field must be a valid email address"],
    "password": ["Password must be at least 8 characters"]
  }
}
```

#### 401 Unauthorized - Invalid Token
```json
{
  "detail": "Invalid or expired token",
  "code": "INVALID_TOKEN"
}
```

#### 403 Forbidden - Insufficient Permissions
```json
{
  "detail": "You do not have permission to perform this action",
  "code": "INSUFFICIENT_PERMISSIONS",
  "required_scopes": ["integrations:manage"]
}
```

#### 403 Forbidden - Tenant Access Denied
```json
{
  "detail": "You do not have access to this tenant",
  "code": "TENANT_ACCESS_DENIED"
}
```

#### 409 Conflict - Email Already Exists
```json
{
  "detail": "A user with this email already exists",
  "code": "EMAIL_ALREADY_EXISTS"
}
```

#### 422 Unprocessable Entity - Credential Validation Failed
```json
{
  "detail": "Failed to validate Twilio credentials",
  "code": "CREDENTIAL_VALIDATION_FAILED",
  "provider_error": "Invalid Account SID or Auth Token"
}
```

#### 429 Too Many Requests - Rate Limit Exceeded
```json
{
  "detail": "Rate limit exceeded. Please try again later.",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

### Error Handling Best Practices

1. **Always check HTTP status codes** before parsing response
2. **Handle rate limiting** with exponential backoff
3. **Store API keys securely** - never commit to version control
4. **Validate input** before sending requests
5. **Log errors** for debugging and monitoring
6. **Implement retry logic** for transient failures
7. **Handle token expiration** by refreshing tokens

---

## Rate Limits

### Authentication Endpoints

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| POST /v1/auth/register | 10 requests | per minute per IP |
| POST /v1/auth/login | 10 requests | per minute per IP |
| POST /v1/auth/forgot-password | 5 requests | per minute per IP |

### Settings Endpoints

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| All POST/PUT/DELETE | 60 requests | per minute per user |
| All GET | 120 requests | per minute per user |

### Handling Rate Limits

When rate limited, wait for the duration specified in the `Retry-After` header before retrying.

```python
import time
import requests

def make_request_with_retry(url, **kwargs):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        response = requests.request(**kwargs, url=url)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            retry_count += 1
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

---

## Security Best Practices

1. **Use HTTPS** in production - never send credentials over HTTP
2. **Store tokens securely** - use secure storage mechanisms
3. **Rotate API keys** regularly (every 90 days recommended)
4. **Never log sensitive data** - credentials, tokens, full card numbers
5. **Validate SSL certificates** - don't disable certificate verification
6. **Use environment variables** for configuration
7. **Implement proper error handling** - don't expose internal errors
8. **Monitor API usage** - detect unusual patterns
9. **Revoke compromised keys** immediately
10. **Use separate keys** for development and production

---

## Additional Resources

- **Interactive API Documentation**: `/schema/swagger/`
- **OpenAPI Schema**: `/schema/`
- **Postman Collection**: `postman_collection.json`
- **Environment Variables Guide**: `docs/ENVIRONMENT_VARIABLES.md`
- **Deployment Guide**: `docs/DEPLOYMENT.md`
- **RBAC Quick Reference**: `apps/core/RBAC_QUICK_REFERENCE.md`

---

## Support

For API support and questions:

- **Documentation**: Check `/schema/swagger/` for interactive docs
- **GitHub Issues**: Report bugs and request features
- **Email**: support@yourdomain.com

---

**Last Updated**: 2025-11-13
**API Version**: 1.0.0
