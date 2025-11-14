# TuliaAI Postman Collection

Complete Postman collection for testing the TuliaAI WhatsApp Commerce Platform API.

## Files

- `TuliaAI.postman_collection.json` - Main API collection with all endpoints
- `TuliaAI.postman_environment.json` - Environment variables for development

## Quick Start

### 1. Import into Postman

1. Open Postman
2. Click **Import** button
3. Drag and drop both JSON files or click **Upload Files**
4. Select both files:
   - `TuliaAI.postman_collection.json`
   - `TuliaAI.postman_environment.json`

### 2. Select Environment

1. Click the environment dropdown (top right)
2. Select **TuliaAI Development**

### 3. Configure Environment Variables

Update these variables in the environment:

**Required:**
- `base_url` - Your API base URL (default: `http://localhost:8000`)
- `tenant_id` - Your tenant UUID (already set from .env)
- `tenant_api_key` - Your tenant API key (already set from .env)

**For Authentication:**
- `user_email` - Your user email
- `user_password` - Your user password

**Auto-populated (after login):**
- `access_token` - JWT access token (set automatically after login)
- `refresh_token` - JWT refresh token (set automatically after login)

### 4. Authenticate (REQUIRED)

**All user endpoints now require JWT authentication.**

#### Option A: Register New User (First Time)

1. Go to **Authentication → Register**
2. Update email to something unique in the request body
3. Click **Send**
4. ✅ Token and Tenant ID automatically saved to environment
5. Check console: "Token saved: ..."

#### Option B: Login Existing User

1. Go to **Authentication → Login**
2. Enter your email and password in the request body
3. Click **Send**
4. ✅ Token automatically saved to environment
5. Check console: "Token saved: ..."

### 5. Verify Authentication

1. Go to **Authentication → Get Profile**
2. Click **Send**
3. Should return 200 with your user profile
4. If 401, check environment (eye icon) - `access_token` should have a value

### 6. Test Tenant-Scoped Endpoints

Most endpoints require both JWT token AND tenant ID:

1. Verify `tenant_id` is set in environment (eye icon)
2. Go to **Products → List Products**
3. Click **Send**
4. Should return 200 with products list

**Headers automatically included:**
- `Authorization: Bearer {{access_token}}` (from collection auth)
- `X-TENANT-ID: {{tenant_id}}` (from request headers)

## Important Authentication Changes

⚠️ **API Keys are deprecated for user operations**

**Old way (deprecated):**
```
X-TENANT-API-KEY: abc123...
```

**New way (required):**
```
Authorization: Bearer eyJhbGc...
X-TENANT-ID: tenant-uuid
```

**Exceptions (still use API keys):**
- Webhooks (verified by signature, not API key)
- Health check (no auth)
- Public endpoints (register, login, etc.)

## Setting Twilio Credentials

To configure Twilio for WhatsApp messaging:

1. Go to **Tenant Settings → Integrations → Set Twilio Credentials**
2. Update the request body:
   ```json
   {
     "sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
     "token": "your_twilio_auth_token",
     "whatsapp_number": "whatsapp:+14155238886",
     "test_connection": true
   }
   ```
3. Click **Send**
4. If successful, you'll see a 200 response with masked credentials

**Get your Twilio credentials:**
- Login to [Twilio Console](https://console.twilio.com/)
- Copy your Account SID and Auth Token
- Get your WhatsApp number from Twilio Sandbox or approved number

## API Endpoints Overview

### Authentication
- `POST /v1/auth/register` - Register new user
- `POST /v1/auth/login` - Login and get tokens
- `GET /v1/auth/me` - Get user profile
- `POST /v1/auth/refresh-token` - Refresh access token
- `POST /v1/auth/logout` - Logout

### Tenant Management
- `GET /v1/tenants` - List my tenants
- `POST /v1/tenants/create` - Create new tenant
- `GET /v1/tenants/{id}` - Get tenant details

### Tenant Settings
- `GET /v1/settings/integrations` - List all integrations
- `POST /v1/settings/integrations/twilio` - Set Twilio credentials
- `GET /v1/settings/integrations/twilio` - Get Twilio status
- `DELETE /v1/settings/integrations/twilio` - Remove Twilio
- `POST /v1/settings/integrations/woocommerce` - Set WooCommerce
- `POST /v1/settings/integrations/shopify` - Set Shopify
- `GET /v1/settings/api-keys` - List API keys
- `POST /v1/settings/api-keys` - Create API key

### Catalog & Products
- `GET /v1/products/` - List products (scope: `catalog:view`)
- `POST /v1/products/` - Create product (scope: `catalog:edit`)
- `POST /v1/products/sync/woocommerce` - Sync from WooCommerce

### Conversations & Messages
- `GET /v1/messages/conversations` - List conversations (scope: `conversations:view`)
- `GET /v1/messages/conversations/{id}/messages` - Get messages
- `POST /v1/messages/send` - Send WhatsApp message

### Orders
- `GET /v1/orders/` - List orders (scope: `orders:view`)
- `GET /v1/orders/{id}` - Get order details

### Wallet & Finance
- `GET /v1/wallet/balance` - Get balance (scope: `finance:view`)
- `GET /v1/wallet/transactions` - List transactions

### Analytics
- `GET /v1/analytics/overview` - Get overview (scope: `analytics:view`)
- `GET /v1/analytics/daily` - Get daily analytics

### Utilities
- `GET /v1/health/` - Health check (no auth)
- `POST /v1/test/send-whatsapp/` - Test WhatsApp sending

## RBAC Scopes

All endpoints enforce Role-Based Access Control. Common scopes:

- `catalog:view` / `catalog:edit` - Product management
- `orders:view` / `orders:edit` - Order management
- `conversations:view` - Message viewing
- `finance:view` / `finance:withdraw:initiate` / `finance:withdraw:approve` - Finance
- `analytics:view` - Analytics access
- `integrations:manage` - Integration configuration
- `users:manage` - User and role management

## Troubleshooting

### 401 Unauthorized
- Check that `X-TENANT-ID` and `X-TENANT-API-KEY` headers are set
- Verify your API key is correct in the environment
- For JWT endpoints, ensure `access_token` is set (login first)

### 403 Forbidden
- Your user lacks the required RBAC scope
- Check the endpoint description for required scopes
- Contact tenant owner to assign appropriate roles

### 404 Not Found
- Verify the endpoint URL is correct
- Check that tenant_id or resource ID exists
- Ensure trailing slashes match the API definition

### Twilio Signature Verification Failed
- Make sure you're using the correct auth token
- Verify your ngrok URL matches what's configured in Twilio
- Check that `USE_X_FORWARDED_HOST` is enabled in Django settings

## Using with ngrok

If testing webhooks with ngrok:

1. Start ngrok: `ngrok http 8000`
2. Update environment variable: `ngrok_url` = your ngrok URL
3. Configure Twilio webhook URL: `https://your-subdomain.ngrok-free.app/v1/webhooks/twilio/`
4. Send a WhatsApp message to test

## Support

For issues or questions:
- Check API documentation: `http://localhost:8000/schema/swagger/`
- Review Django logs for detailed error messages
- See `.kiro/steering/` for RBAC and architecture docs
