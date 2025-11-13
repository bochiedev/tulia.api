# WabotIQ Postman Collection Guide

This guide explains how to use the WabotIQ Postman collection for API testing and development.

## Quick Start

### 1. Generate Collection

```bash
python scripts/generate_postman_collection.py
```

This creates two files:
- `postman_collection.json` - The API request collection
- `postman_environment_template.json` - Environment variables template

### 2. Import into Postman

1. Open Postman
2. Click **Import** button
3. Select `postman_collection.json`
4. Select `postman_environment_template.json`
5. Select the "WabotIQ Development" environment from the dropdown

### 3. Configure Environment Variables

Before making requests, you need to set up your environment variables:

#### Initial Setup (No Account Yet)

1. **base_url**: Already set to `http://localhost:8000`
2. Leave other variables empty for now

#### After Registration

Use the **Authentication > Register** request to create your account:

```json
{
  "email": "your@email.com",
  "password": "SecurePassword123!",
  "business_name": "My Business",
  "first_name": "John",
  "last_name": "Doe"
}
```

The response will include:
- `token` - Copy this to `jwt_token` variable
- `tenant.id` - Copy this to `tenant_id` variable

#### Generate API Key

After registration, use **Settings > Generate API Key**:

```json
{
  "name": "Development Key"
}
```

Copy the returned `key` to the `tenant_api_key` variable.

## Authentication Patterns

WabotIQ supports multiple authentication patterns depending on the endpoint:

### Pattern 1: Public Endpoints (No Auth)

Used for: Health checks, webhooks

**Headers**: None required

**Example**: Health Check

### Pattern 2: JWT Only

Used for: User registration, login, profile management

**Headers**:
```
Authorization: Bearer {{jwt_token}}
```

**Example**: Get Profile, Update Profile

### Pattern 3: Tenant API Key

Used for: Most tenant-scoped operations

**Headers**:
```
X-TENANT-ID: {{tenant_id}}
X-TENANT-API-KEY: {{tenant_api_key}}
```

**Example**: List Products, Create Order

### Pattern 4: JWT + Tenant Headers

Used for: Tenant management, multi-tenant operations

**Headers**:
```
Authorization: Bearer {{jwt_token}}
X-TENANT-ID: {{tenant_id}}
```

**Example**: List My Tenants, Invite Member

## Collection Structure

The collection is organized into folders matching the API structure:

### 1. Authentication
- Register - Create new user and tenant
- Login - Get JWT token
- Get Profile - View current user
- Update Profile - Modify user details
- Verify Email - Confirm email address
- Forgot Password - Request reset token
- Reset Password - Change password with token

### 2. Tenant Management
- List My Tenants - View all accessible tenants
- Create Tenant - Add new tenant
- Get Tenant Details - View tenant info
- List Tenant Members - View team members
- Invite Member - Add user to tenant (requires `users:manage`)

### 3. Catalog
- List Products - View all products (requires `catalog:view`)
- Get Product - View product details (requires `catalog:view`)
- Create Product - Add new product (requires `catalog:edit`)
- Update Product - Modify product (requires `catalog:edit`)
- Delete Product - Remove product (requires `catalog:edit`)
- Sync WooCommerce - Import from WooCommerce (requires `integrations:manage`)
- Sync Shopify - Import from Shopify (requires `integrations:manage`)

### 4. Orders
- List Orders - View all orders (requires `orders:view`)
- Get Order - View order details (requires `orders:view`)
- Create Order - Place new order (requires `orders:edit`)
- Update Order Status - Change order status (requires `orders:edit`)

### 5. RBAC
- List Permissions - View available permissions
- List Roles - View tenant roles
- Get Role Details - View role with permissions
- Create Role - Add custom role (requires `users:manage`)
- Add Permissions to Role - Assign permissions (requires `users:manage`)
- Assign Roles to User - Grant roles (requires `users:manage`)
- Grant User Permission - Override permission (requires `users:manage`)
- List Audit Logs - View audit trail (requires `analytics:view`)

### 6. Settings
- Get Business Settings - View tenant settings
- Update Business Settings - Modify settings (requires `users:manage` or `integrations:manage`)
- List API Keys - View API keys (requires `users:manage`)
- Generate API Key - Create new key (requires `users:manage`)
- Get Onboarding Status - View onboarding progress
- Complete Onboarding Step - Mark step complete
- Update Twilio Credentials - Configure Twilio (requires `integrations:manage`)

### 7. Analytics
- Get Analytics Overview - View metrics (requires `analytics:view`)
- Get Daily Analytics - View time-series data (requires `analytics:view`)

## RBAC and Permissions

Many endpoints require specific permissions (scopes). The required scope is documented in each request's description.

### Common Permission Scopes

| Scope | Description |
|-------|-------------|
| `catalog:view` | View products and catalog |
| `catalog:edit` | Create, update, delete products |
| `orders:view` | View orders |
| `orders:edit` | Create, update orders |
| `analytics:view` | View analytics and reports |
| `integrations:manage` | Manage external integrations |
| `users:manage` | Manage users, roles, and permissions |

### Testing RBAC

To test RBAC enforcement:

1. Create a user with limited permissions
2. Try accessing an endpoint without the required scope
3. Expected result: `403 Forbidden`
4. Grant the required permission
5. Try again - should succeed

## Common Workflows

### Workflow 1: Complete Onboarding

1. **Register** - Create account
2. **Login** - Get JWT token
3. **Generate API Key** - Get tenant API key
4. **Update Twilio Credentials** - Configure WhatsApp
5. **Sync WooCommerce** - Import products
6. **Complete Onboarding Step** - Mark steps complete

### Workflow 2: Team Management

1. **List My Tenants** - View accessible tenants
2. **Invite Member** - Add team member
3. **List Roles** - View available roles
4. **Assign Roles to User** - Grant permissions
5. **List Audit Logs** - Review changes

### Workflow 3: Product Management

1. **List Products** - View current catalog
2. **Create Product** - Add new product
3. **Update Product** - Modify details
4. **Sync WooCommerce** - Import from store
5. **List Orders** - View sales

### Workflow 4: Custom RBAC

1. **List Permissions** - View available permissions
2. **Create Role** - Define custom role
3. **Add Permissions to Role** - Assign capabilities
4. **Assign Roles to User** - Grant to team member
5. **Grant User Permission** - Override specific permission

## Troubleshooting

### 401 Unauthorized

**Cause**: Missing or invalid authentication

**Solution**:
- Check that `jwt_token` or `tenant_api_key` is set
- Verify token hasn't expired (JWT expires after 24 hours)
- Re-login to get fresh token

### 403 Forbidden

**Cause**: Missing required permission scope

**Solution**:
- Check request description for required scope
- Verify your user has the required permission
- Use **List Roles** to see your permissions
- Contact tenant owner to grant permission

### 404 Not Found

**Cause**: Resource doesn't exist or wrong tenant context

**Solution**:
- Verify `tenant_id` is correct
- Check resource ID in URL
- Ensure resource belongs to your tenant

### 422 Validation Error

**Cause**: Invalid request body

**Solution**:
- Check request body format
- Review required fields
- Verify data types match schema

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `base_url` | API base URL | `http://localhost:8000` |
| `tenant_id` | Current tenant UUID | `123e4567-e89b-12d3-a456-426614174000` |
| `tenant_api_key` | Tenant API key | `a96b73152af3e755...` |
| `jwt_token` | JWT authentication token | `eyJhbGciOiJIUzI1NiIs...` |
| `product_id` | Product UUID for testing | `123e4567-e89b-12d3-a456-426614174001` |
| `order_id` | Order UUID for testing | `123e4567-e89b-12d3-a456-426614174002` |
| `role_id` | Role UUID for testing | `123e4567-e89b-12d3-a456-426614174003` |
| `user_id` | User UUID for testing | `123e4567-e89b-12d3-a456-426614174004` |

## Tips and Best Practices

### 1. Use Environment Variables

Always use `{{variable}}` syntax instead of hardcoding values. This makes it easy to switch between environments.

### 2. Save Responses

After creating resources, save the returned IDs to environment variables:

```javascript
// In Tests tab of a request
pm.environment.set("product_id", pm.response.json().id);
```

### 3. Test Scripts

Add test scripts to verify responses:

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has data", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('id');
});
```

### 4. Pre-request Scripts

Use pre-request scripts for dynamic data:

```javascript
// Generate unique email
pm.environment.set("unique_email", `test${Date.now()}@example.com`);
```

### 5. Multiple Environments

Create separate environments for:
- Local development (`http://localhost:8000`)
- Staging (`https://api-staging.tulia.ai`)
- Production (`https://api.tulia.ai`)

## Security Notes

⚠️ **Important Security Considerations**:

1. **Never commit** environment files with real credentials
2. **Use separate API keys** for development and production
3. **Rotate API keys** regularly
4. **Revoke unused keys** via Settings > List API Keys
5. **Don't share** JWT tokens or API keys
6. **Use HTTPS** in production (not HTTP)

## Support

For issues or questions:
- Check API documentation: `/schema/swagger/`
- Review error messages in response body
- Check audit logs for permission issues
- Contact support: support@tulia.ai

## Regenerating Collection

If the API changes, regenerate the collection:

```bash
python scripts/generate_postman_collection.py
```

Then re-import the updated `postman_collection.json` in Postman.
