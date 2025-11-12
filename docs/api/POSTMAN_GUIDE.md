# Tulia AI API - Postman Collection Guide

## Overview

This Postman collection provides comprehensive API testing coverage for the Tulia AI WhatsApp Commerce Platform. It includes all REST API endpoints with authentication examples, test cases for success and error scenarios, rate limiting tests, and pagination validation.

## Quick Start

### 1. Import the Collection

1. Open Postman
2. Click **Import** button
3. Select `postman_collection.json`
4. The collection will appear in your Collections sidebar

### 2. Set Up Environment Variables

Create a new environment in Postman with these variables:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `base_url` | API base URL | `http://localhost:8000` |
| `tenant_id` | Your tenant UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `api_key` | Your API key | `test-api-key-12345` |

**To set up:**
1. Click the gear icon (⚙️) in top right
2. Click **Add** to create new environment
3. Name it "Tulia AI - Development"
4. Add the three variables above
5. Click **Save**
6. Select the environment from the dropdown in top right

### 3. Run Your First Request

1. Navigate to **Health & Status** → **Health Check**
2. Click **Send**
3. You should receive a 200 OK response with system health status

## Authentication

### API Key Authentication

All endpoints (except webhooks and health check) require two headers:

```
X-TENANT-ID: your-tenant-uuid
X-TENANT-API-KEY: your-api-key
```

These are automatically added by the collection using environment variables.

### RBAC Scopes

Each endpoint requires specific permission scopes. The collection includes tests that verify:
- ✅ 200/201 responses when user has required scope
- ❌ 403 responses when user lacks required scope

## Collection Structure

### 1. Health & Status
- System health check (no auth required)
- Database and Redis connectivity validation

### 2. Catalog - Products
- List, create, update, delete products
- Product variant management
- WooCommerce and Shopify sync
- **Scopes:** `catalog:view`, `catalog:edit`, `integrations:manage`

### 3. Services & Appointments
- Service management
- Availability window configuration
- Appointment booking with capacity validation
- Appointment cancellation
- **Scopes:** `services:view`, `services:edit`, `appointments:view`, `appointments:edit`

### 4. Orders
- Order creation and management
- Status updates (triggers automated messages)
- Order history with filtering
- **Scopes:** `orders:view`, `orders:edit`

### 5. Messaging & Conversations
- Conversation listing and message history
- Send outbound messages (respects consent)
- Human handoff
- Message templates
- Scheduled messages
- **Scopes:** `conversations:view`, `handoff:perform`

### 6. Campaigns
- Campaign creation and execution
- A/B testing support
- Campaign performance reports
- **Scopes:** `conversations:view`, `analytics:view`

### 7. Customers & Preferences
- Customer listing and details
- Consent preference management
- Customer data export
- **Scopes:** `conversations:view`

### 8. Wallet & Finance
- Wallet balance and transaction history
- Withdrawal initiation (four-eyes approval)
- Withdrawal approval (must be different user)
- **Scopes:** `finance:view`, `finance:withdraw:initiate`, `finance:withdraw:approve`

### 9. Analytics
- Overview analytics (7d, 30d, 90d ranges)
- Daily metrics breakdown
- Messaging analytics by type
- Conversion funnel tracking
- **Scopes:** `analytics:view`

### 10. RBAC - Roles & Permissions
- User membership management
- Role assignment
- Custom role creation
- Permission overrides
- Audit log access
- **Scopes:** `users:manage`, `analytics:view`

### 11. Admin - Platform Operators
- Tenant management
- Subscription tier changes
- Subscription waivers
- Platform revenue analytics
- Withdrawal processing
- **Requires:** Platform admin authentication

### 12. Webhooks
- Twilio WhatsApp webhook (signature verification)
- **Note:** Called by external services, not API clients

### 13. Test Scenarios
- Rate limiting validation
- Pagination testing
- RBAC enforcement (403 errors)
- Tenant isolation verification

## Running Tests

### Individual Request Tests

Each request includes automatic tests that run after the response is received:

```javascript
pm.test('Status code is 200', function () {
    pm.response.to.have.status(200);
});

pm.test('Response has required fields', function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('id');
});
```

### Collection-Level Tests

The collection includes pre-request and test scripts that run for all requests:

**Pre-request Script:**
- Automatically adds `X-TENANT-ID` header from environment variable

**Test Script:**
- Validates no 500 errors
- Checks for `Retry-After` header on 429 responses

### Running All Tests

1. Click the **...** menu next to the collection name
2. Select **Run collection**
3. Configure:
   - Select all folders or specific ones
   - Set delay between requests (e.g., 100ms)
   - Choose environment
4. Click **Run Tulia AI WhatsApp Commerce Platform API**

### Test Results

Postman will show:
- ✅ Passed tests (green)
- ❌ Failed tests (red)
- Total requests executed
- Average response time
- Test coverage percentage

## Common Test Scenarios

### 1. Testing Rate Limiting

Navigate to **Test Scenarios** → **Test Rate Limiting**

1. Click **Send** button repeatedly (10-20 times)
2. Eventually you'll receive a 429 response
3. Check the `Retry-After` header value
4. Wait the specified time before retrying

**Expected Results:**
- First N requests: 200 OK
- After limit: 429 Too Many Requests
- Response includes `Retry-After` header

### 2. Testing Pagination

Navigate to **Test Scenarios** → **Test Pagination**

1. Adjust `page_size` query parameter (try 10, 50, 100)
2. Click **Send**
3. Verify response includes pagination metadata

**Expected Results:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/v1/products/?page=2",
  "previous": null,
  "results": [...]
}
```

### 3. Testing RBAC Enforcement

Navigate to **Test Scenarios** → **Test Missing Scope (403)**

1. Ensure your user lacks `finance:withdraw:initiate` scope
2. Click **Send**
3. Should receive 403 Forbidden

**Expected Results:**
```json
{
  "detail": "Missing required scope: finance:withdraw:initiate"
}
```

### 4. Testing Tenant Isolation

Navigate to **Test Scenarios** → **Test Tenant Isolation**

1. Temporarily change `X-TENANT-ID` header to a different tenant
2. Click **Send**
3. Should receive 403 or 404

**Expected Results:**
- Never returns data from another tenant
- Returns 403 (forbidden) or 404 (not found)

### 5. Testing Four-Eyes Approval

**Step 1: Initiate Withdrawal**
1. Navigate to **Wallet & Finance** → **Initiate Withdrawal**
2. Set amount to 500.00
3. Click **Send**
4. Note the `withdrawal_id` in response (saved to variable)

**Step 2: Attempt Self-Approval (Should Fail)**
1. Navigate to **Wallet & Finance** → **Approve Withdrawal**
2. Click **Send** (using same user)
3. Should receive 409 Conflict

**Step 3: Approve with Different User**
1. Change to a different user with `finance:withdraw:approve` scope
2. Click **Send**
3. Should receive 200 OK

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Delete successful |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Missing required scope or tenant access |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Business rule violation (e.g., four-eyes) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error (should not happen) |
| 503 | Service Unavailable | Dependency down (database, Redis) |

### Error Response Format

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "field_errors": {
    "email": ["This field is required"]
  }
}
```

## Advanced Usage

### Using Collection Variables

The collection automatically saves certain IDs for chaining requests:

```javascript
// After creating a product
pm.variables.set('created_product_id', jsonData.id);

// Use in subsequent requests
{{created_product_id}}
```

**Saved Variables:**
- `created_product_id`
- `created_service_id`
- `created_appointment_id`
- `created_campaign_id`
- `withdrawal_id`

### Custom Test Scripts

Add custom tests to any request:

```javascript
pm.test('Custom validation', function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData.price).to.be.above(0);
    pm.expect(jsonData.currency).to.equal('USD');
});
```

### Pre-request Scripts

Modify requests before sending:

```javascript
// Generate dynamic data
const timestamp = new Date().toISOString();
pm.variables.set('current_timestamp', timestamp);

// Add custom headers
pm.request.headers.add({
    key: 'X-Request-ID',
    value: pm.variables.replaceIn('{{$guid}}')
});
```

## CI/CD Integration

### Newman (Postman CLI)

Run the collection from command line:

```bash
# Install Newman
npm install -g newman

# Run collection
newman run postman_collection.json \
  --environment tulia-dev.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export results.json

# Run with specific folder
newman run postman_collection.json \
  --folder "Catalog - Products" \
  --environment tulia-dev.postman_environment.json
```

### GitHub Actions Example

```yaml
name: API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Install Newman
        run: npm install -g newman
      
      - name: Run API Tests
        run: |
          newman run postman_collection.json \
            --environment tulia-dev.postman_environment.json \
            --reporters cli,junit \
            --reporter-junit-export results.xml
      
      - name: Publish Test Results
        uses: EnricoMi/publish-unit-test-result-action@v1
        if: always()
        with:
          files: results.xml
```

## Troubleshooting

### Issue: 401 Unauthorized

**Cause:** Missing or invalid API key

**Solution:**
1. Verify `api_key` environment variable is set
2. Check that `X-TENANT-API-KEY` header is being sent
3. Confirm API key is valid for the tenant

### Issue: 403 Forbidden

**Cause:** Missing required scope or wrong tenant

**Solution:**
1. Check the endpoint's required scope in description
2. Verify your user has the required scope
3. Confirm `tenant_id` environment variable matches your access

### Issue: 429 Too Many Requests

**Cause:** Rate limit exceeded

**Solution:**
1. Check `Retry-After` header for wait time
2. Reduce request frequency
3. Consider upgrading subscription tier for higher limits

### Issue: Variables Not Saving

**Cause:** Collection variables not persisting

**Solution:**
1. Use environment variables instead of collection variables
2. Ensure environment is selected in dropdown
3. Save environment after making changes

### Issue: Tests Failing

**Cause:** Various reasons

**Solution:**
1. Check response body in Postman console
2. Verify test assertions match actual response structure
3. Ensure test data exists (e.g., products, customers)
4. Check server logs for errors

## Best Practices

### 1. Use Environments

Create separate environments for:
- **Development:** `http://localhost:8000`
- **Staging:** `https://staging-api.tulia.ai`
- **Production:** `https://api.tulia.ai`

### 2. Organize Requests

Use folders to group related endpoints:
- Keep CRUD operations together
- Group by resource type
- Separate admin endpoints

### 3. Write Descriptive Tests

```javascript
// ❌ Bad
pm.test('Test 1', function () {
    pm.expect(pm.response.code).to.equal(200);
});

// ✅ Good
pm.test('Returns 200 OK when user has catalog:view scope', function () {
    pm.expect(pm.response.code).to.equal(200);
});
```

### 4. Chain Requests

Use saved variables to create workflows:
1. Create product → Save product_id
2. Create order with product_id
3. Update order status
4. Verify automated message sent

### 5. Clean Up Test Data

Add cleanup requests to delete test resources:
```javascript
// In test script
if (pm.response.code === 201) {
    // Save ID for cleanup
    pm.environment.set('cleanup_product_id', jsonData.id);
}
```

## Support

For issues or questions:
- **Documentation:** See main README.md
- **API Docs:** Visit `/schema/swagger/` on your server
- **GitHub Issues:** Report bugs and feature requests

## Version History

- **v1.0.0** (2025-11-12): Initial release
  - Complete API coverage
  - RBAC testing
  - Rate limiting tests
  - Pagination validation
  - Four-eyes approval scenarios
  - Tenant isolation tests

## License

This Postman collection is part of the Tulia AI platform and follows the same license as the main project.
