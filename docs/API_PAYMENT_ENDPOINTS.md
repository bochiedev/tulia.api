# Payment API Endpoints Documentation

## Overview

Complete API documentation for customer payment preferences and tenant withdrawal management.

**Key Concepts**:
- **Customers** pay for products/services using their preferred payment methods
- **Tenants** withdraw their earnings from the wallet (four-eyes approval required)
- **Transaction fees** are paid by tenants, not customers

---

## Customer Payment Preferences

Customers can save payment preferences for faster checkout when paying for products/services.

### Base URL
```
/api/v1/
```

### Authentication
All endpoints require:
- `X-TENANT-ID` header
- `X-TENANT-API-KEY` header
- Valid JWT token (for user authentication)

---

### 1. Get Customer Payment Preferences

Get customer's saved payment preferences.

**Endpoint**: `GET /customers/{customer_id}/payment-preferences`

**Required Scope**: `conversations:view`

**Response**:
```json
{
  "preferred_provider": "mpesa",
  "saved_methods": [
    {
      "provider": "mpesa",
      "details": {"phone_number": "254712345678"},
      "saved_at": "2025-11-13T10:30:00Z",
      "is_default": true
    }
  ],
  "available_providers": ["mpesa", "paystack", "pesapal"]
}
```

**Example**:
```bash
curl -X GET "https://api.wabotiq.com/v1/customers/123e4567-e89b-12d3-a456-426614174000/payment-preferences" \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Authorization: Bearer your-jwt-token"
```

---

### 2. Get Checkout Options

Get checkout options with customer preferences for a specific amount.

**Endpoint**: `GET /customers/{customer_id}/checkout-options?amount=1000`

**Required Scope**: `conversations:view`

**Query Parameters**:
- `amount` (required): Payment amount

**Response**:
```json
{
  "preferred_provider": "mpesa",
  "preferred_method": {
    "provider": "mpesa",
    "details": {"phone_number": "254712345678"},
    "is_default": true
  },
  "available_providers": ["mpesa", "paystack", "pesapal"],
  "saved_methods": [...],
  "can_change_provider": true,
  "amount": 1000.0
}
```

**Example**:
```bash
curl -X GET "https://api.wabotiq.com/v1/customers/123e4567-e89b-12d3-a456-426614174000/checkout-options?amount=1000" \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Authorization: Bearer your-jwt-token"
```

---

### 3. Set Preferred Provider

Set customer's preferred payment provider.

**Endpoint**: `PUT /customers/{customer_id}/preferred-provider`

**Required Scope**: `conversations:view`

**Request Body**:
```json
{
  "provider": "mpesa"
}
```

**Response**:
```json
{
  "message": "Preferred provider updated successfully",
  "preferences": {...}
}
```

**Example**:
```bash
curl -X PUT "https://api.wabotiq.com/v1/customers/123e4567-e89b-12d3-a456-426614174000/preferred-provider" \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{"provider": "mpesa"}'
```

---

### 4. Save Payment Method

Save a payment method for future use.

**Endpoint**: `POST /customers/{customer_id}/payment-methods`

**Required Scope**: `conversations:view`

**Request Body**:
```json
{
  "provider": "mpesa",
  "details": {
    "phone_number": "254712345678"
  },
  "set_as_default": true
}
```

**Provider-Specific Details**:

**M-Pesa**:
```json
{
  "provider": "mpesa",
  "details": {"phone_number": "254712345678"}
}
```

**Paystack**:
```json
{
  "provider": "paystack",
  "details": {
    "authorization_code": "AUTH_xxx",
    "last4": "1234",
    "bank": "Access Bank"
  }
}
```

**Pesapal**:
```json
{
  "provider": "pesapal",
  "details": {
    "payment_method": "card",
    "last4": "1234"
  }
}
```

**Stripe**:
```json
{
  "provider": "stripe",
  "details": {
    "payment_method_id": "pm_xxx",
    "last4": "1234",
    "brand": "visa"
  }
}
```

**Response**:
```json
{
  "message": "Payment method saved successfully",
  "preferences": {...}
}
```

---

### 5. Remove Payment Method

Remove a saved payment method.

**Endpoint**: `DELETE /customers/{customer_id}/payment-methods/{method_id}`

**Required Scope**: `conversations:view`

**Response**:
```json
{
  "message": "Payment method removed successfully",
  "preferences": {...}
}
```

---

### 6. Set Default Payment Method

Set a saved payment method as default.

**Endpoint**: `PUT /customers/{customer_id}/payment-methods/{method_id}/default`

**Required Scope**: `conversations:view`

**Response**:
```json
{
  "message": "Default payment method updated successfully",
  "preferences": {...}
}
```

---

## Tenant Withdrawals

Tenants withdraw their earnings from the wallet. All withdrawals require four-eyes approval.

---

### 1. Get Withdrawal Options

Get available withdrawal methods, fees, and wallet balance.

**Endpoint**: `GET /wallet/withdrawal-options`

**Required Scope**: `finance:view`

**Response**:
```json
{
  "available_methods": ["mpesa", "till", "bank_transfer"],
  "configured_method": {
    "method_type": "mpesa",
    "details": {"phone_number": "254712345678"}
  },
  "minimum_amounts": {
    "mpesa": 10.0,
    "bank_transfer": 100.0,
    "till": 10.0
  },
  "fees": {
    "mpesa": 33.0,
    "bank_transfer": 50.0,
    "till": 27.0
  },
  "wallet_balance": 10000.0,
  "currency": "KES"
}
```

**Example**:
```bash
curl -X GET "https://api.wabotiq.com/v1/wallet/withdrawal-options" \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Authorization: Bearer your-jwt-token"
```

---

### 2. Initiate Withdrawal

Create a withdrawal request (requires approval).

**Endpoint**: `POST /wallet/withdrawals`

**Required Scope**: `finance:withdraw:initiate`

**Request Body**:
```json
{
  "amount": 1000.00,
  "method_type": "mpesa",
  "method_details": {
    "phone_number": "254712345678"
  },
  "notes": "Monthly withdrawal"
}
```

**Method Types & Details**:

**M-Pesa B2C**:
```json
{
  "method_type": "mpesa",
  "method_details": {"phone_number": "254712345678"}
}
```

**Bank Transfer (Paystack)**:
```json
{
  "method_type": "bank_transfer",
  "method_details": {
    "account_number": "1234567890",
    "bank_code": "063",
    "account_name": "Business Account"
  }
}
```

**Till (M-Pesa B2B)**:
```json
{
  "method_type": "till",
  "method_details": {"till_number": "123456"}
}
```

**Response**:
```json
{
  "message": "Withdrawal request initiated successfully",
  "transaction_id": "uuid",
  "status": "pending",
  "amount": 1000.00,
  "fee": 33.00,
  "net_amount": 967.00,
  "requires_approval": true
}
```

**Fee Calculation**:
- **Gross Amount**: Amount requested (e.g., 1000.00)
- **Fee**: Withdrawal fee (e.g., 33.00 for M-Pesa)
- **Net Amount**: What tenant receives (e.g., 967.00)
- **Wallet Debit**: Gross amount (1000.00)

**Example**:
```bash
curl -X POST "https://api.wabotiq.com/v1/wallet/withdrawals" \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "method_type": "mpesa",
    "method_details": {"phone_number": "254712345678"},
    "notes": "Monthly withdrawal"
  }'
```

---

### 3. Approve Withdrawal

Approve and process a pending withdrawal (four-eyes approval).

**Endpoint**: `POST /wallet/withdrawals/{transaction_id}/approve`

**Required Scope**: `finance:withdraw:approve`

**Four-Eyes Rule**: Approver MUST be different from initiator.

**Response**:
```json
{
  "success": true,
  "message": "Withdrawal approved and processed successfully",
  "transaction_id": "uuid",
  "amount": 1000.00,
  "net_amount": 967.00,
  "fee": 33.00,
  "provider_response": {
    "provider": "mpesa",
    "conversation_id": "AG_20231113_xxx",
    "response_code": "0"
  }
}
```

**Example**:
```bash
curl -X POST "https://api.wabotiq.com/v1/wallet/withdrawals/123e4567-e89b-12d3-a456-426614174000/approve" \
  -H "X-TENANT-ID: tenant-uuid" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -H "Authorization: Bearer your-jwt-token"
```

**Error - Four-Eyes Violation**:
```json
{
  "error": "Approver must be different from initiator (four-eyes approval)"
}
```

---

### 4. Cancel Withdrawal

Cancel a pending withdrawal.

**Endpoint**: `POST /wallet/withdrawals/{transaction_id}/cancel`

**Required Scope**: `finance:withdraw:initiate` OR `finance:withdraw:approve`

**Request Body**:
```json
{
  "reason": "Changed mind"
}
```

**Response**:
```json
{
  "message": "Withdrawal canceled successfully",
  "transaction_id": "uuid",
  "status": "canceled"
}
```

---

### 5. List Withdrawals

List withdrawal transactions with filtering.

**Endpoint**: `GET /wallet/withdrawals?status=pending&limit=50`

**Required Scope**: `finance:view`

**Query Parameters**:
- `status` (optional): Filter by status (pending, completed, failed, canceled)
- `limit` (optional): Number of results (default 50)

**Response**:
```json
{
  "count": 10,
  "results": [
    {
      "id": "uuid",
      "amount": 1000.00,
      "fee": 33.00,
      "net_amount": 967.00,
      "status": "pending",
      "method_type": "mpesa",
      "initiated_by": "user-uuid",
      "approved_by": null,
      "created_at": "2025-11-13T10:30:00Z",
      "notes": "Monthly withdrawal"
    }
  ]
}
```

---

## RBAC Permissions

### Customer Payment Endpoints

| Endpoint | Required Scope |
|----------|---------------|
| Get preferences | `conversations:view` |
| Get checkout options | `conversations:view` |
| Set preferred provider | `conversations:view` |
| Save payment method | `conversations:view` |
| Remove payment method | `conversations:view` |
| Set default method | `conversations:view` |

### Tenant Withdrawal Endpoints

| Endpoint | Required Scope |
|----------|---------------|
| Get withdrawal options | `finance:view` |
| List withdrawals | `finance:view` |
| Initiate withdrawal | `finance:withdraw:initiate` |
| Approve withdrawal | `finance:withdraw:approve` |
| Cancel withdrawal | `finance:withdraw:initiate` OR `finance:withdraw:approve` |

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid amount"
}
```

### 403 Forbidden
```json
{
  "detail": "Missing required scope: finance:withdraw:approve"
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 500 Internal Server Error
```json
{
  "error": "Failed to process withdrawal",
  "details": {"message": "..."}
}
```

---

## Workflow Examples

### Customer Payment Flow

```
1. Customer browses products
2. Customer adds items to cart
3. GET /customers/{id}/checkout-options?amount=1000
   → Returns preferred method and available providers
4. Customer selects payment method (or uses preferred)
5. POST /orders/{id}/checkout
   → Initiates payment with selected provider
6. After successful payment:
   POST /customers/{id}/payment-methods
   → Save method for future use
```

### Tenant Withdrawal Flow

```
1. Finance user checks balance:
   GET /wallet/withdrawal-options
   → Returns balance: 10000.00, fees, minimums

2. Finance user initiates withdrawal:
   POST /wallet/withdrawals
   Body: {amount: 1000, method_type: "mpesa", ...}
   → Creates pending transaction
   → Gross: 1000, Fee: 33, Net: 967

3. Finance manager (different user) approves:
   POST /wallet/withdrawals/{id}/approve
   → Processes M-Pesa B2C payment (967.00)
   → Debits wallet (1000.00)
   → Transaction status: completed

4. View withdrawal history:
   GET /wallet/withdrawals?status=completed
   → Returns list of completed withdrawals
```

---

## Testing

### Test Customer Payment Preferences

```bash
# 1. Get preferences
curl -X GET "http://localhost:8000/api/v1/customers/{customer_id}/payment-preferences" \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}"

# 2. Set preferred provider
curl -X PUT "http://localhost:8000/api/v1/customers/{customer_id}/preferred-provider" \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"provider": "mpesa"}'

# 3. Save payment method
curl -X POST "http://localhost:8000/api/v1/customers/{customer_id}/payment-methods" \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "mpesa",
    "details": {"phone_number": "254712345678"}
  }'
```

### Test Tenant Withdrawals

```bash
# 1. Get withdrawal options
curl -X GET "http://localhost:8000/api/v1/wallet/withdrawal-options" \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}"

# 2. Initiate withdrawal (User 1)
curl -X POST "http://localhost:8000/api/v1/wallet/withdrawals" \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Authorization: Bearer {user1_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "method_type": "mpesa",
    "method_details": {"phone_number": "254712345678"}
  }'

# 3. Approve withdrawal (User 2 - different from User 1)
curl -X POST "http://localhost:8000/api/v1/wallet/withdrawals/{transaction_id}/approve" \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Authorization: Bearer {user2_token}"
```

---

**Last Updated**: 2025-11-13
**Version**: 1.0
