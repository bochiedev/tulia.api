# Tulia AI API - Quick Reference Card

## Base URL
```
Development: http://localhost:8000
Production:  https://api.tulia.ai
```

## Authentication Headers
```
X-TENANT-ID: your-tenant-uuid
X-TENANT-API-KEY: your-api-key
```

## Common Endpoints

### Health & Status
```http
GET /v1/health/                    # System health check (no auth)
```

### Products
```http
GET    /v1/products/               # List products (catalog:view)
GET    /v1/products/{id}           # Get product details (catalog:view)
POST   /v1/products/               # Create product (catalog:edit)
PUT    /v1/products/{id}           # Update product (catalog:edit)
DELETE /v1/products/{id}           # Delete product (catalog:edit)
```

### Services & Appointments
```http
GET    /v1/services/                           # List services (services:view)
POST   /v1/services/                           # Create service (services:edit)
GET    /v1/services/{id}/availability          # Get availability (services:view)
GET    /v1/services/appointments                # List appointments (appointments:view)
POST   /v1/services/appointments                # Book appointment (appointments:edit)
POST   /v1/services/appointments/{id}/cancel   # Cancel appointment (appointments:edit)
```

### Orders
```http
GET    /v1/orders/                 # List orders (orders:view)
GET    /v1/orders/{id}             # Get order details (orders:view)
POST   /v1/orders/                 # Create order (orders:edit)
PUT    /v1/orders/{id}             # Update order status (orders:edit)
```

### Messaging
```http
GET    /v1/messages/conversations                      # List conversations (conversations:view)
GET    /v1/messages/conversations/{id}/messages       # Get messages (conversations:view)
POST   /v1/messages/send                              # Send message (conversations:view)
POST   /v1/messages/conversations/{id}/handoff       # Human handoff (handoff:perform)
POST   /v1/messages/templates                         # Create template (conversations:view)
POST   /v1/messages/schedule                          # Schedule message (conversations:view)
```

### Campaigns
```http
GET    /v1/messages/campaigns                  # List campaigns (conversations:view)
POST   /v1/messages/campaigns                  # Create campaign (conversations:view)
POST   /v1/messages/campaigns/{id}/execute    # Execute campaign (conversations:view)
GET    /v1/messages/campaigns/{id}/report     # Get report (analytics:view)
```

### Customers
```http
GET    /v1/customers                           # List customers (conversations:view)
GET    /v1/customers/{id}                      # Get customer (conversations:view)
GET    /v1/customers/{id}/preferences          # Get preferences (conversations:view)
PUT    /v1/customers/{id}/preferences          # Update preferences (conversations:view)
```

### Wallet & Finance
```http
GET    /v1/wallet/balance                      # Get balance (finance:view)
GET    /v1/wallet/transactions                 # List transactions (finance:view)
POST   /v1/wallet/withdraw                     # Initiate withdrawal (finance:withdraw:initiate)
POST   /v1/wallet/withdrawals/{id}/approve    # Approve withdrawal (finance:withdraw:approve)
```

### Analytics
```http
GET    /v1/analytics/overview?range=30d        # Overview analytics (analytics:view)
GET    /v1/analytics/daily                     # Daily metrics (analytics:view)
GET    /v1/analytics/messaging                 # Messaging analytics (analytics:view)
GET    /v1/analytics/funnel                    # Funnel analytics (analytics:view)
```

### RBAC
```http
GET    /v1/memberships/me                              # My memberships (authenticated)
POST   /v1/memberships/{tenant_id}/invite             # Invite user (users:manage)
GET    /v1/roles                                       # List roles (users:manage)
POST   /v1/roles                                       # Create role (users:manage)
POST   /v1/memberships/{tenant_id}/{user_id}/roles   # Assign role (users:manage)
GET    /v1/permissions                                 # List permissions (users:manage)
POST   /v1/users/{user_id}/permissions                # Grant permission (users:manage)
GET    /v1/audit-logs                                  # Audit logs (analytics:view)
```

### Admin (Platform Operators)
```http
GET    /v1/admin/tenants                              # List tenants (admin)
POST   /v1/admin/tenants/{id}/subscription           # Change subscription (admin)
POST   /v1/admin/tenants/{id}/waive                  # Waive subscription (admin)
GET    /v1/admin/analytics/revenue                    # Platform revenue (admin)
POST   /v1/admin/wallet/withdrawals/{id}/process    # Process withdrawal (admin)
```

### Integrations
```http
POST   /v1/webhooks/catalog/sync/woocommerce   # Sync WooCommerce (integrations:manage)
POST   /v1/webhooks/catalog/sync/shopify       # Sync Shopify (integrations:manage)
POST   /v1/webhooks/twilio/                     # Twilio webhook (signature verified)
```

## Permission Scopes

| Scope | Description |
|-------|-------------|
| `catalog:view` | View products and catalog |
| `catalog:edit` | Create, update, delete products |
| `services:view` | View services |
| `services:edit` | Manage services |
| `availability:edit` | Manage availability windows |
| `appointments:view` | View appointments |
| `appointments:edit` | Manage appointments |
| `orders:view` | View orders |
| `orders:edit` | Create, update orders |
| `conversations:view` | View conversations and messages |
| `handoff:perform` | Perform human handoff |
| `finance:view` | View wallet and transactions |
| `finance:withdraw:initiate` | Initiate withdrawals |
| `finance:withdraw:approve` | Approve withdrawals (four-eyes) |
| `finance:reconcile` | Reconcile transactions |
| `analytics:view` | View analytics and reports |
| `integrations:manage` | Manage integrations |
| `users:manage` | Manage users, roles, permissions |

## Default Roles

| Role | Permissions |
|------|-------------|
| **Owner** | ALL permissions |
| **Admin** | ALL except `finance:withdraw:approve` |
| **Finance Admin** | `analytics:view`, `finance:*`, `orders:view` |
| **Catalog Manager** | `analytics:view`, `catalog:*`, `services:*`, `availability:edit` |
| **Support Lead** | `conversations:view`, `handoff:perform`, `orders:view`, `appointments:view` |
| **Analyst** | `analytics:view`, `catalog:view`, `services:view`, `orders:view`, `appointments:view` |

## HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created |
| 204 | No Content | Delete successful |
| 400 | Bad Request | Invalid data |
| 401 | Unauthorized | Missing/invalid API key |
| 403 | Forbidden | Missing scope or tenant access |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Business rule violation |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Dependency down |

## Rate Limits (per tenant)

| Tier | Requests/Hour | Messages/Day |
|------|---------------|--------------|
| Starter | 1,000 | 1,000 |
| Growth | 10,000 | 10,000 |
| Enterprise | Unlimited | Unlimited |

## Pagination

All list endpoints support:
```
?page=1              # Page number (default: 1)
?page_size=50        # Items per page (default: 50, max: 100)
```

Response format:
```json
{
  "count": 150,
  "next": "http://api.tulia.ai/v1/products/?page=2",
  "previous": null,
  "results": [...]
}
```

## Common Query Parameters

### Products
```
?search=keyword          # Search by title/description
?is_active=true          # Filter by active status
?external_source=manual  # Filter by source (woocommerce, shopify, manual)
```

### Orders
```
?status=paid             # Filter by status (draft, placed, paid, fulfilled, canceled)
?customer={uuid}         # Filter by customer
?from_date=2025-11-01    # Filter by date range
?to_date=2025-11-30
```

### Appointments
```
?status=confirmed        # Filter by status (pending, confirmed, done, canceled, no_show)
?service={uuid}          # Filter by service
?from_date=2025-11-01    # Filter by date range
```

### Conversations
```
?status=open             # Filter by status (open, bot, handoff, closed, dormant)
?customer={uuid}         # Filter by customer
```

### Transactions
```
?transaction_type=customer_payment  # Filter by type
?status=completed                    # Filter by status
?from_date=2025-11-01               # Filter by date range
```

## Example Requests

### Create Product
```bash
curl -X POST http://localhost:8000/v1/products/ \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: your-tenant-id" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -d '{
    "title": "Wireless Headphones",
    "price": "199.99",
    "currency": "USD",
    "is_active": true
  }'
```

### Book Appointment
```bash
curl -X POST http://localhost:8000/v1/services/appointments \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: your-tenant-id" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -d '{
    "service": "service-uuid",
    "customer": "customer-uuid",
    "start_dt": "2025-11-15T10:00:00Z",
    "end_dt": "2025-11-15T11:00:00Z"
  }'
```

### Send Message
```bash
curl -X POST http://localhost:8000/v1/messages/send \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: your-tenant-id" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -d '{
    "customer": "customer-uuid",
    "text": "Your order has shipped!",
    "message_type": "manual_outbound"
  }'
```

### Initiate Withdrawal
```bash
curl -X POST http://localhost:8000/v1/wallet/withdraw \
  -H "Content-Type: application/json" \
  -H "X-TENANT-ID: your-tenant-id" \
  -H "X-TENANT-API-KEY: your-api-key" \
  -d '{
    "amount": "500.00",
    "bank_account": "****1234"
  }'
```

## Error Response Format

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "field_errors": {
    "field_name": ["Error message"]
  }
}
```

## Webhooks

### Twilio Webhook
```
POST /v1/webhooks/twilio/
Content-Type: application/x-www-form-urlencoded
X-Twilio-Signature: computed-signature

From=whatsapp:+1234567890
To=whatsapp:+14155238886
Body=Hello
MessageSid=SM1234567890
```

**Note:** Signature verification required. Called by Twilio, not API clients.

## Documentation

- **Interactive API Docs:** `/schema/swagger/`
- **OpenAPI Schema:** `/schema/`
- **Postman Collection:** `postman_collection.json`
- **Full Guide:** `POSTMAN_GUIDE.md`

## Support

- **GitHub:** Report issues and feature requests
- **Documentation:** See README.md for setup and deployment
- **API Status:** Check `/v1/health/` endpoint
