# Tulia AI OpenAPI RBAC Documentation Guide

## Quick Start

### Accessing the API Documentation

1. **Swagger UI (Interactive):**
   ```
   http://localhost:8000/schema/swagger/
   ```
   - Try out endpoints directly
   - View request/response examples
   - Test authentication

2. **OpenAPI Schema (JSON/YAML):**
   ```
   http://localhost:8000/schema/
   ```
   - Download for Postman/Insomnia
   - Generate client SDKs
   - Share with team

3. **Generate Static Schema:**
   ```bash
   python manage.py spectacular --file schema.yml
   ```

## Authentication

All API requests require two headers:

```bash
X-TENANT-ID: <tenant-uuid>
X-TENANT-API-KEY: <api-key>
```

Example:
```bash
curl -X GET https://api.tulia.ai/v1/memberships/me \
  -H "X-TENANT-ID: 123e4567-e89b-12d3-a456-426614174000" \
  -H "X-TENANT-API-KEY: your-api-key-here"
```

## RBAC Concepts

### Permissions
Granular capabilities like `catalog:view`, `finance:withdraw:approve`

### Roles
Collections of permissions:
- **Owner**: All permissions
- **Admin**: All except `finance:withdraw:approve`
- **Finance Admin**: Finance operations
- **Catalog Manager**: Product/service management
- **Support Lead**: Customer support
- **Analyst**: Read-only analytics

### Scopes
Effective permissions for a user in a tenant, resolved from:
1. Roles assigned to user
2. User-specific overrides (grants/denies)

**Rule:** Deny overrides always win over role grants

## Common Workflows

### 1. Invite a User

```bash
POST /v1/memberships/{tenant_id}/invite
```

**Required scope:** `users:manage`

```bash
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/invite \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "role_ids": ["role-uuid-1"]
  }'
```

### 2. Assign Roles to User

```bash
POST /v1/memberships/{tenant_id}/{user_id}/roles
```

**Required scope:** `users:manage`

```bash
curl -X POST https://api.tulia.ai/v1/memberships/{tenant_id}/{user_id}/roles \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_ids": ["role-uuid-2", "role-uuid-3"]
  }'
```

### 3. Grant User-Specific Permission

```bash
POST /v1/users/{user_id}/permissions
```

**Required scope:** `users:manage`

**Grant permission:**
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

**Deny permission (overrides role):**
```bash
curl -X POST https://api.tulia.ai/v1/users/{user_id}/permissions \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "catalog:edit",
    "granted": false,
    "reason": "Suspended pending investigation"
  }'
```

### 4. Four-Eyes Withdrawal Approval

**Step 1: Initiate Withdrawal**

```bash
POST /v1/wallet/withdraw
```

**Required scope:** `finance:withdraw:initiate`

```bash
curl -X POST https://api.tulia.ai/v1/wallet/withdraw \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000.00,
    "currency": "USD",
    "bank_account": "****1234",
    "notes": "Monthly payout"
  }'
```

**Response:**
```json
{
  "id": "txn-uuid",
  "status": "pending_approval",
  "amount": 1000.00,
  "initiated_by": {
    "id": "user-uuid-1",
    "email": "finance@example.com"
  }
}
```

**Step 2: Approve Withdrawal (Different User)**

```bash
POST /v1/wallet/withdrawals/{transaction_id}/approve
```

**Required scope:** `finance:withdraw:approve`

```bash
curl -X POST https://api.tulia.ai/v1/wallet/withdrawals/{transaction_id}/approve \
  -H "X-TENANT-ID: {tenant_id}" \
  -H "X-TENANT-API-KEY: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Approved for monthly payout"
  }'
```

**Success Response:**
```json
{
  "id": "txn-uuid",
  "status": "approved",
  "amount": 1000.00,
  "initiated_by": {
    "id": "user-uuid-1",
    "email": "finance@example.com"
  },
  "approved_by": {
    "id": "user-uuid-2",
    "email": "manager@example.com"
  }
}
```

**Failure (Same User):**
```json
{
  "error": "Four-eyes validation failed",
  "details": {
    "message": "Initiator and approver must be different users"
  }
}
```

## Permission Codes Reference

| Code | Description | Category |
|------|-------------|----------|
| `catalog:view` | View products and catalog | Catalog |
| `catalog:edit` | Create, update, delete products | Catalog |
| `services:view` | View services | Services |
| `services:edit` | Create, update, delete services | Services |
| `availability:edit` | Manage service availability | Services |
| `conversations:view` | View customer conversations | Messaging |
| `handoff:perform` | Perform human handoff | Messaging |
| `orders:view` | View orders | Orders |
| `orders:edit` | Create, update orders | Orders |
| `appointments:view` | View appointments | Appointments |
| `appointments:edit` | Manage appointments | Appointments |
| `analytics:view` | View analytics and reports | Analytics |
| `finance:view` | View wallet and transactions | Finance |
| `finance:withdraw:initiate` | Initiate withdrawals | Finance |
| `finance:withdraw:approve` | Approve withdrawals | Finance |
| `finance:reconcile` | Financial reconciliation | Finance |
| `integrations:manage` | Manage integrations | Integrations |
| `users:manage` | Manage users and permissions | Users |

## Useful Endpoints

### List Available Permissions
```bash
GET /v1/permissions
```
No scope required - all users can view available permissions.

### List Tenant Roles
```bash
GET /v1/roles
```
No scope required - all users can view roles.

### View User's Memberships
```bash
GET /v1/memberships/me
```
No scope required - users can always see their own memberships.

### View Audit Logs
```bash
GET /v1/audit-logs
```
**Required scope:** `analytics:view`

Filter by:
- `action`: Action type (e.g., 'user_invited', 'role_assigned')
- `target_type`: Target type (e.g., 'TenantUser', 'Role')
- `user_id`: User who performed the action
- `from_date`: Start date (ISO 8601)
- `to_date`: End date (ISO 8601)

## Error Responses

### 401 Unauthorized
Missing or invalid authentication headers.

### 403 Forbidden
User lacks required scope for the operation.

```json
{
  "error": "Permission denied",
  "details": {
    "required_scopes": ["users:manage"],
    "user_scopes": ["catalog:view", "catalog:edit"]
  }
}
```

### 404 Not Found
Resource doesn't exist or doesn't belong to the tenant.

### 409 Conflict
Four-eyes validation failed (same user attempting approval).

```json
{
  "error": "Four-eyes validation failed",
  "details": {
    "message": "Initiator and approver must be different users"
  }
}
```

## Testing in Swagger UI

1. Navigate to `http://localhost:8000/schema/swagger/`
2. Click "Authorize" button
3. Enter your X-TENANT-ID and X-TENANT-API-KEY
4. Browse endpoints by tag (RBAC - Memberships, etc.)
5. Click "Try it out" to test endpoints
6. View request/response examples

## Importing to Postman

1. Generate schema: `python manage.py spectacular --file schema.yml`
2. Open Postman
3. Click "Import" → "Upload Files"
4. Select `schema.yml`
5. Postman will create a collection with all endpoints
6. Set environment variables for X-TENANT-ID and X-TENANT-API-KEY

## Multi-Tenant Considerations

- Users can be members of multiple tenants
- Each tenant has separate roles and permissions
- Switch context by changing X-TENANT-ID header
- Data is strictly isolated by tenant
- Same phone number in different tenants = different Customer records

## Support

For questions or issues:
- View full schema: `http://localhost:8000/schema/`
- Check audit logs: `GET /v1/audit-logs`
- Review RBAC documentation: `apps/core/RBAC_USAGE.md`
