# Task 6.11 Implementation Summary: OpenAPI Schema with RBAC Documentation

## Overview
Successfully updated the OpenAPI schema with comprehensive RBAC documentation including:
- All RBAC endpoints with detailed descriptions
- Required scopes for each endpoint
- Security scheme for X-TENANT-ID header
- Example curl commands for key workflows
- Complete permission code documentation
- Default role mappings
- Four-eyes approval workflow examples

## Changes Made

### 1. Enhanced SPECTACULAR_SETTINGS in config/settings.py

Added comprehensive API documentation including:

**Extended Description:**
- Authentication requirements (X-TENANT-ID, X-TENANT-API-KEY headers)
- RBAC authorization model explanation
- Permission codes and categories
- Role definitions with permission mappings
- Scopes resolution logic
- Four-eyes approval pattern
- Multi-tenant isolation principles

**Canonical Permissions Table:**
```
| Code | Description | Category |
|------|-------------|----------|
| catalog:view | View products and catalog | Catalog |
| catalog:edit | Create, update, delete products | Catalog |
| services:view | View services | Services |
| services:edit | Create, update, delete services | Services |
| availability:edit | Manage service availability windows | Services |
| conversations:view | View customer conversations | Messaging |
| handoff:perform | Perform human handoff | Messaging |
| orders:view | View orders | Orders |
| orders:edit | Create, update orders | Orders |
| appointments:view | View appointments | Appointments |
| appointments:edit | Create, update, cancel appointments | Appointments |
| analytics:view | View analytics and reports | Analytics |
| finance:view | View wallet and transactions | Finance |
| finance:withdraw:initiate | Initiate withdrawal requests | Finance |
| finance:withdraw:approve | Approve withdrawal requests | Finance |
| finance:reconcile | Perform financial reconciliation | Finance |
| integrations:manage | Manage external integrations | Integrations |
| users:manage | Invite users, assign roles, manage permissions | Users |
```

**Default Roles:**
- **Owner**: All permissions
- **Admin**: All permissions except `finance:withdraw:approve`
- **Finance Admin**: `analytics:view`, `finance:*`, `orders:view`
- **Catalog Manager**: `analytics:view`, `catalog:*`, `services:*`, `availability:edit`
- **Support Lead**: `conversations:view`, `handoff:perform`, `orders:view`, `appointments:view`
- **Analyst**: `analytics:view`, `catalog:view`, `services:view`, `orders:view`, `appointments:view`

**Example Workflows:**

1. **Invite User and Assign Roles**
```bash
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/invite \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "role_ids": ["role-uuid-1", "role-uuid-2"]
  }'
```

2. **Grant User-Specific Permission Override**
```bash
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "finance:reconcile",
    "granted": true,
    "reason": "Temporary access for Q4 audit"
  }'
```

3. **Four-Eyes Withdrawal Approval**
```bash
# Step 1: User A initiates withdrawal
curl -X POST https://api.tulia.ai/v1/wallet/withdraw \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "destination": "bank_account_123"
  }'

# Step 2: User B approves withdrawal (must be different user)
curl -X POST https://api.tulia.ai/v1/wallet/withdrawals/{transaction_id}/approve \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Approved for monthly payout"
  }'
```

**Security Schemes:**
- Added `TenantAuth` security scheme for X-TENANT-ID header
- Documented requirement for X-TENANT-API-KEY companion header

**Tags:**
- RBAC - Memberships
- RBAC - Roles
- RBAC - Permissions
- RBAC - Audit
- Finance - Wallet
- Finance - Withdrawals
- Catalog
- Services
- Orders
- Appointments
- Messaging
- Analytics
- Integrations

**Swagger UI Settings:**
- Deep linking enabled
- Authorization persistence
- Operation ID display
- Filter enabled

### 2. Added OpenAPI Decorators to RBAC Views (apps/rbac/views.py)

Added `@extend_schema_view` decorators to all RBAC endpoints:

**Membership Endpoints:**
- `GET /v1/memberships/me` - List user memberships (no scope required)
- `POST /v1/memberships/{tenant_id}/invite` - Invite user (requires `users:manage`)
- `POST /v1/memberships/{tenant_id}/{user_id}/roles` - Assign roles (requires `users:manage`)
- `DELETE /v1/memberships/{tenant_id}/{user_id}/roles/{role_id}` - Remove role (requires `users:manage`)

**Role Endpoints:**
- `GET /v1/roles` - List tenant roles (no scope required)
- `POST /v1/roles` - Create custom role (requires `users:manage`)
- `GET /v1/roles/{id}` - Get role details (no scope required)
- `GET /v1/roles/{id}/permissions` - List role permissions (no scope required)
- `POST /v1/roles/{id}/permissions` - Add permissions to role (requires `users:manage`)

**Permission Endpoints:**
- `GET /v1/permissions` - List all permissions (no scope required)
- `GET /v1/users/{id}/permissions` - List user overrides (self or `users:manage`)
- `POST /v1/users/{id}/permissions` - Grant/deny permission (requires `users:manage`)

**Audit Endpoints:**
- `GET /v1/audit-logs` - List audit logs (requires `analytics:view`)

Each endpoint includes:
- Detailed description with scope requirements
- Request/response schemas
- Example curl commands where applicable
- OpenAPI examples for requests and responses
- Query parameter documentation
- Error response codes

### 3. Added OpenAPI Decorators to Wallet Withdrawal Views (apps/tenants/views.py)

**Withdrawal Endpoints:**

1. **POST /v1/wallet/withdraw** - Initiate withdrawal (four-eyes step 1)
   - Required scope: `finance:withdraw:initiate`
   - Detailed four-eyes process explanation
   - Example request/response
   - Documents immediate wallet debit
   - Explains pending_approval status

2. **POST /v1/wallet/withdrawals/{id}/approve** - Approve withdrawal (four-eyes step 2)
   - Required scope: `finance:withdraw:approve`
   - Four-eyes validation documentation
   - Example success and failure responses
   - 409 Conflict response for same-user approval
   - Documents approved status and processing

Both endpoints include:
- Comprehensive descriptions of the four-eyes pattern
- Example curl commands
- Multiple OpenAPI examples (success, failure, validation errors)
- Clear explanation of status transitions
- Security implications

## Schema Generation Results

Successfully generated `schema.yml` with:
- **Size:** 83KB
- **Warnings:** 3 (serializer type hints - non-critical)
- **Errors:** 0
- **Endpoints Documented:** All RBAC and wallet endpoints
- **Tags:** 13 categories
- **Security Schemes:** TenantAuth properly configured

## Verification

Verified schema includes:
- ✅ All RBAC tags (Memberships, Roles, Permissions, Audit)
- ✅ Finance - Withdrawals tag
- ✅ TenantAuth security scheme with description
- ✅ Four-eyes approval documentation in multiple places
- ✅ Permission codes table in description
- ✅ Default role mappings
- ✅ Example curl commands for key workflows
- ✅ Scope requirements for each endpoint

## API Documentation Access

The OpenAPI documentation is available at:
- **Schema JSON/YAML:** `GET /schema/`
- **Swagger UI:** `GET /schema/swagger/`

The Swagger UI includes:
- Interactive API explorer
- Try-it-out functionality
- Authorization persistence
- Deep linking to specific endpoints
- Filtering by tags

## Key Features Documented

### 1. RBAC Authorization Model
- Permission-based access control
- Role composition
- User-specific overrides
- Deny-overrides-allow pattern
- Scope resolution logic

### 2. Four-Eyes Approval Pattern
- Separation of duties
- Initiator vs. approver validation
- Status transitions
- Error handling for same-user attempts

### 3. Multi-Tenant Isolation
- Tenant context via headers
- Data isolation guarantees
- Cross-tenant access prevention

### 4. Permission Management
- Canonical permission set
- Category organization
- Role-based assignment
- User-level overrides

### 5. Audit Trail
- All RBAC changes logged
- Sensitive operation tracking
- Compliance support

## Testing Recommendations

To verify the OpenAPI documentation:

1. **Generate and view schema:**
```bash
python manage.py spectacular --file schema.yml
```

2. **Access Swagger UI:**
```bash
python manage.py runserver
# Navigate to: http://localhost:8000/schema/swagger/
```

3. **Test endpoints in Swagger UI:**
- Set X-TENANT-ID and X-TENANT-API-KEY headers
- Try membership invitation workflow
- Test role assignment
- Verify four-eyes withdrawal approval

4. **Export for external tools:**
- Import schema.yml into Postman
- Use with API testing tools
- Share with frontend developers

## Requirements Satisfied

This implementation satisfies all requirements from task 6.11:
- ✅ Document all RBAC endpoints with request/response schemas
- ✅ Include required scopes in endpoint descriptions
- ✅ Add security scheme for X-TENANT-ID header
- ✅ Provide example curl commands for invite, assign role, grant permission
- ✅ Document permission codes with descriptions
- ✅ Document default roles and their permission mappings

## Files Modified

1. `config/settings.py` - Enhanced SPECTACULAR_SETTINGS
2. `apps/rbac/views.py` - Added OpenAPI decorators to all RBAC views
3. `apps/tenants/views.py` - Added OpenAPI decorators to wallet withdrawal views

## Schema File

Generated: `schema.yml` (83KB)
- Complete OpenAPI 3.0 specification
- Ready for import into API tools
- Includes all RBAC and finance documentation

## Conclusion

The OpenAPI schema now provides comprehensive documentation for the RBAC system, making it easy for:
- Frontend developers to understand authorization requirements
- API consumers to integrate with the platform
- Security auditors to review access control patterns
- Operations teams to understand four-eyes approval workflows

The documentation is production-ready and follows OpenAPI 3.0 best practices.
