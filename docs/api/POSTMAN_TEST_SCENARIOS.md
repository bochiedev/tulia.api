# Postman Collection - Test Scenarios

## Overview

This document describes comprehensive test scenarios included in the Tulia AI Postman collection. Each scenario validates specific functionality, error handling, and security controls.

## Test Scenario Categories

### 1. Authentication & Authorization Tests
### 2. CRUD Operation Tests
### 3. Business Logic Tests
### 4. Rate Limiting Tests
### 5. Pagination Tests
### 6. Tenant Isolation Tests
### 7. RBAC Enforcement Tests
### 8. Four-Eyes Approval Tests
### 9. Consent Management Tests
### 10. Integration Tests

---

## 1. Authentication & Authorization Tests

### Scenario 1.1: Missing API Key
**Objective:** Verify that requests without API key are rejected

**Steps:**
1. Remove `X-TENANT-API-KEY` header
2. Send GET request to `/v1/products/`

**Expected Result:**
- Status: 401 Unauthorized
- Response includes error message about missing API key

**Test Assertions:**
```javascript
pm.test('Returns 401 without API key', function () {
    pm.response.to.have.status(401);
});
```

### Scenario 1.2: Invalid API Key
**Objective:** Verify that requests with invalid API key are rejected

**Steps:**
1. Set `X-TENANT-API-KEY` to invalid value
2. Send GET request to `/v1/products/`

**Expected Result:**
- Status: 401 Unauthorized
- Response includes error message about invalid API key

### Scenario 1.3: Missing Tenant ID
**Objective:** Verify that requests without tenant ID are rejected

**Steps:**
1. Remove `X-TENANT-ID` header
2. Send GET request to `/v1/products/`

**Expected Result:**
- Status: 400 Bad Request
- Response includes error message about missing tenant ID

### Scenario 1.4: Wrong Tenant ID
**Objective:** Verify tenant isolation

**Steps:**
1. Set `X-TENANT-ID` to a different tenant's UUID
2. Send GET request to `/v1/products/`

**Expected Result:**
- Status: 403 Forbidden or 404 Not Found
- Never returns data from another tenant

---

## 2. CRUD Operation Tests

### Scenario 2.1: Product CRUD Workflow
**Objective:** Test complete product lifecycle

**Steps:**
1. **Create:** POST `/v1/products/` with valid data
2. **Read:** GET `/v1/products/{id}` to verify creation
3. **Update:** PUT `/v1/products/{id}` with modified data
4. **Read:** GET `/v1/products/{id}` to verify update
5. **Delete:** DELETE `/v1/products/{id}`
6. **Verify:** GET `/v1/products/{id}` should return 404

**Expected Results:**
- Create: 201 Created with product ID
- Read: 200 OK with product details
- Update: 200 OK with updated data
- Delete: 204 No Content
- Verify: 404 Not Found

**Test Assertions:**
```javascript
// After create
pm.test('Product created successfully', function () {
    pm.response.to.have.status(201);
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('id');
    pm.variables.set('product_id', jsonData.id);
});

// After update
pm.test('Product updated successfully', function () {
    pm.response.to.have.status(200);
    const jsonData = pm.response.json();
    pm.expect(jsonData.title).to.include('Updated');
});
```

### Scenario 2.2: Service and Appointment Workflow
**Objective:** Test service booking flow

**Steps:**
1. Create service with POST `/v1/services/`
2. Get availability with GET `/v1/services/{id}/availability`
3. Book appointment with POST `/v1/services/appointments`
4. Verify appointment created
5. Cancel appointment with POST `/v1/services/appointments/{id}/cancel`

**Expected Results:**
- Service created: 201
- Availability returned: 200 with available slots
- Appointment booked: 201 with confirmation
- Cancellation: 200 with updated status

---

## 3. Business Logic Tests

### Scenario 3.1: Feature Limit Enforcement
**Objective:** Verify subscription tier limits are enforced

**Steps:**
1. Create products until reaching tier limit (e.g., 100 for Starter)
2. Attempt to create one more product

**Expected Result:**
- Status: 403 Forbidden
- Response includes message about max_products limit
- Suggests upgrading subscription tier

**Test Assertions:**
```javascript
pm.test('Feature limit enforced', function () {
    pm.response.to.have.status(403);
    const jsonData = pm.response.json();
    pm.expect(jsonData.detail).to.include('max_products');
});
```

### Scenario 3.2: Appointment Capacity Validation
**Objective:** Verify capacity limits prevent overbooking

**Steps:**
1. Create service with capacity=2
2. Create availability window
3. Book first appointment
4. Book second appointment
5. Attempt to book third appointment (should fail)

**Expected Result:**
- First two bookings: 201 Created
- Third booking: 400 Bad Request
- Response indicates capacity exceeded

### Scenario 3.3: Stock Validation
**Objective:** Verify out-of-stock products cannot be added to cart

**Steps:**
1. Create product with stock=0
2. Attempt to add to cart via bot or API

**Expected Result:**
- Status: 400 Bad Request
- Response indicates product out of stock

### Scenario 3.4: Order Status Workflow
**Objective:** Verify order status transitions trigger automated messages

**Steps:**
1. Create order with status="draft"
2. Update status to "paid" (should trigger payment confirmation)
3. Update status to "shipped" (should trigger shipment notification)
4. Verify messages were created

**Expected Result:**
- Each status update: 200 OK
- Automated messages created with correct message_type
- Messages sent to customer via Twilio

---

## 4. Rate Limiting Tests

### Scenario 4.1: API Rate Limit
**Objective:** Verify rate limiting per tenant

**Steps:**
1. Send rapid requests to `/v1/products/` (50+ requests)
2. Monitor for 429 response

**Expected Result:**
- First N requests: 200 OK (N depends on tier)
- After limit: 429 Too Many Requests
- Response includes `Retry-After` header
- After waiting, requests succeed again

**Test Assertions:**
```javascript
pm.test('Rate limit enforced', function () {
    if (pm.response.code === 429) {
        pm.test('Has Retry-After header', function () {
            pm.response.to.have.header('Retry-After');
        });
    }
});
```

### Scenario 4.2: Message Rate Limit
**Objective:** Verify daily message limits

**Steps:**
1. Send messages until reaching daily limit (e.g., 1000 for Starter)
2. Attempt to send one more message

**Expected Result:**
- Status: 429 Too Many Requests
- Response indicates daily message limit reached
- Messages queued for next day

### Scenario 4.3: Rate Limit Warning
**Objective:** Verify warning at 80% of limit

**Steps:**
1. Send messages until reaching 80% of daily limit
2. Check for warning notification

**Expected Result:**
- Warning notification sent to tenant
- Includes current usage and limit

---

## 5. Pagination Tests

### Scenario 5.1: Basic Pagination
**Objective:** Verify pagination works correctly

**Steps:**
1. Create 150 products
2. GET `/v1/products/?page=1&page_size=50`
3. Verify response structure
4. Follow `next` link to page 2
5. Verify page 2 has different products

**Expected Result:**
- Response includes: count, next, previous, results
- count = 150
- results.length = 50
- next URL points to page 2
- previous = null on page 1

**Test Assertions:**
```javascript
pm.test('Pagination metadata present', function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('count');
    pm.expect(jsonData).to.have.property('next');
    pm.expect(jsonData).to.have.property('previous');
    pm.expect(jsonData).to.have.property('results');
});

pm.test('Page size respected', function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData.results.length).to.be.at.most(50);
});
```

### Scenario 5.2: Custom Page Size
**Objective:** Verify custom page_size parameter

**Steps:**
1. GET `/v1/products/?page_size=10`
2. Verify only 10 items returned

**Expected Result:**
- results.length = 10
- Pagination links adjusted accordingly

### Scenario 5.3: Maximum Page Size
**Objective:** Verify page_size limit enforced

**Steps:**
1. GET `/v1/products/?page_size=200`

**Expected Result:**
- Maximum 100 items returned (enforced limit)
- Or 400 Bad Request if validation rejects

---

## 6. Tenant Isolation Tests

### Scenario 6.1: Cross-Tenant Data Access
**Objective:** Verify tenants cannot access each other's data

**Steps:**
1. Create product in Tenant A
2. Switch to Tenant B credentials
3. Attempt to GET product from Tenant A

**Expected Result:**
- Status: 404 Not Found (product doesn't exist in Tenant B context)
- Never returns Tenant A's data

**Test Assertions:**
```javascript
pm.test('Cannot access other tenant data', function () {
    pm.expect(pm.response.code).to.be.oneOf([403, 404]);
});
```

### Scenario 6.2: Customer Phone Number Isolation
**Objective:** Verify same phone number creates separate customers per tenant

**Steps:**
1. Create customer with phone +1234567890 in Tenant A
2. Create customer with phone +1234567890 in Tenant B
3. Verify two separate Customer records exist
4. Verify conversations are isolated

**Expected Result:**
- Two Customer records with same phone but different tenant_id
- Each tenant sees only their own customer
- Messages and conversations isolated

### Scenario 6.3: Conversation Isolation
**Objective:** Verify conversation history is tenant-scoped

**Steps:**
1. Create conversation in Tenant A
2. Switch to Tenant B
3. Attempt to access Tenant A's conversation

**Expected Result:**
- Status: 404 Not Found
- Conversation not visible to Tenant B

---

## 7. RBAC Enforcement Tests

### Scenario 7.1: Catalog View Permission
**Objective:** Verify catalog:view scope required

**Steps:**
1. Create user WITHOUT catalog:view scope
2. Attempt GET `/v1/products/`

**Expected Result:**
- Status: 403 Forbidden
- Response indicates missing catalog:view scope

**Test Assertions:**
```javascript
pm.test('Requires catalog:view scope', function () {
    pm.response.to.have.status(403);
    const jsonData = pm.response.json();
    pm.expect(jsonData.detail).to.include('catalog:view');
});
```

### Scenario 7.2: Catalog Edit Permission
**Objective:** Verify catalog:edit scope required for modifications

**Steps:**
1. Create user WITH catalog:view but WITHOUT catalog:edit
2. Attempt POST `/v1/products/`

**Expected Result:**
- Status: 403 Forbidden
- Response indicates missing catalog:edit scope

### Scenario 7.3: Finance Permissions
**Objective:** Verify finance permissions hierarchy

**Steps:**
1. User with finance:view can GET `/v1/wallet/balance` ✓
2. User without finance:view gets 403 ✗
3. User with finance:withdraw:initiate can POST `/v1/wallet/withdraw` ✓
4. User without scope gets 403 ✗

**Expected Results:**
- Each action requires specific scope
- Missing scope returns 403

### Scenario 7.4: Permission Override (Deny)
**Objective:** Verify user permission override denies access

**Steps:**
1. Assign user to role with catalog:edit
2. Add user permission override: catalog:edit = false (deny)
3. Attempt POST `/v1/products/`

**Expected Result:**
- Status: 403 Forbidden
- Deny override wins over role grant

### Scenario 7.5: Multi-Tenant User Access
**Objective:** Verify user can access multiple tenants with different roles

**Steps:**
1. Create user with Owner role in Tenant A
2. Add same user with Analyst role in Tenant B
3. Switch X-TENANT-ID to Tenant A, verify full access
4. Switch X-TENANT-ID to Tenant B, verify limited access

**Expected Result:**
- Tenant A: All permissions available
- Tenant B: Only analytics:view and read-only scopes
- Scopes change based on tenant context

---

## 8. Four-Eyes Approval Tests

### Scenario 8.1: Withdrawal Four-Eyes Success
**Objective:** Verify four-eyes approval works correctly

**Steps:**
1. User A initiates withdrawal: POST `/v1/wallet/withdraw`
2. Save withdrawal_id from response
3. User B approves: POST `/v1/wallet/withdrawals/{id}/approve`
4. Verify withdrawal status = "approved"

**Expected Result:**
- Initiation: 201 Created
- Approval: 200 OK
- Withdrawal processed

**Test Assertions:**
```javascript
// After approval
pm.test('Withdrawal approved by different user', function () {
    pm.response.to.have.status(200);
    const jsonData = pm.response.json();
    pm.expect(jsonData.status).to.equal('approved');
});
```

### Scenario 8.2: Withdrawal Self-Approval Blocked
**Objective:** Verify same user cannot approve their own withdrawal

**Steps:**
1. User A initiates withdrawal
2. User A attempts to approve their own withdrawal

**Expected Result:**
- Status: 409 Conflict
- Response indicates initiator cannot approve

**Test Assertions:**
```javascript
pm.test('Self-approval blocked', function () {
    pm.response.to.have.status(409);
    const jsonData = pm.response.json();
    pm.expect(jsonData.detail).to.include('same user');
});
```

### Scenario 8.3: Approval Without Permission
**Objective:** Verify approval requires finance:withdraw:approve scope

**Steps:**
1. User A initiates withdrawal
2. User B (without finance:withdraw:approve) attempts approval

**Expected Result:**
- Status: 403 Forbidden
- Response indicates missing scope

---

## 9. Consent Management Tests

### Scenario 9.1: Promotional Message Consent
**Objective:** Verify promotional messages respect consent

**Steps:**
1. Create customer with promotional_messages = false
2. Attempt to send promotional message
3. Verify message blocked

**Expected Result:**
- Message not sent
- Consent violation logged
- Customer not charged for blocked message

### Scenario 9.2: Transactional Messages Always Allowed
**Objective:** Verify transactional messages bypass consent

**Steps:**
1. Create customer with all consent = false
2. Update order status to "paid" (triggers transactional message)
3. Verify message sent

**Expected Result:**
- Message sent successfully
- message_type = "automated_transactional"

### Scenario 9.3: Opt-Out Intent Handling
**Objective:** Verify bot handles opt-out messages

**Steps:**
1. Send message "STOP" via webhook
2. Verify customer preferences updated
3. Verify confirmation message sent

**Expected Result:**
- promotional_messages = false
- reminder_messages = false
- transactional_messages = true (cannot opt-out)
- Confirmation sent

### Scenario 9.4: Campaign Consent Filtering
**Objective:** Verify campaigns only target consented customers

**Steps:**
1. Create campaign targeting 100 customers
2. 50 customers have promotional_messages = true
3. Execute campaign
4. Verify only 50 messages sent

**Expected Result:**
- delivery_count = 50
- Customers without consent not contacted

---

## 10. Integration Tests

### Scenario 10.1: WooCommerce Sync
**Objective:** Verify WooCommerce product sync

**Steps:**
1. POST `/v1/webhooks/catalog/sync/woocommerce` with credentials
2. Verify products created
3. Check external_source = "woocommerce"
4. Verify variants created

**Expected Result:**
- Status: 200 OK
- Response includes products_synced count
- Products visible in catalog

### Scenario 10.2: Shopify Sync
**Objective:** Verify Shopify product sync

**Steps:**
1. POST `/v1/webhooks/catalog/sync/shopify` with credentials
2. Verify products created
3. Check external_source = "shopify"

**Expected Result:**
- Status: 200 OK
- Products synced successfully

### Scenario 10.3: Twilio Webhook Processing
**Objective:** Verify inbound message processing

**Steps:**
1. POST `/v1/webhooks/twilio/` with valid signature
2. Verify customer created/updated
3. Verify conversation created/updated
4. Verify message stored
5. Verify intent classified
6. Verify response sent

**Expected Result:**
- Status: 200 OK
- Complete message processing flow
- Response sent back to customer

---

## Running Test Scenarios

### Individual Scenario
1. Navigate to specific request in collection
2. Click **Send**
3. Review test results in **Test Results** tab

### Folder of Scenarios
1. Right-click folder (e.g., "Test Scenarios")
2. Select **Run folder**
3. Review results in Collection Runner

### Full Collection
1. Click **...** next to collection name
2. Select **Run collection**
3. Configure settings
4. Click **Run**

## Test Result Interpretation

### Green (Passed)
- ✅ Test assertion passed
- Functionality working as expected

### Red (Failed)
- ❌ Test assertion failed
- Review response body and logs
- Check test logic and expected values

### Skipped
- Test not executed (conditional logic)
- May be expected based on response

## Continuous Testing

### Newman CLI
```bash
# Run all tests
newman run postman_collection.json \
  --environment tulia-dev.postman_environment.json

# Run specific folder
newman run postman_collection.json \
  --folder "RBAC Enforcement Tests" \
  --environment tulia-dev.postman_environment.json

# Generate HTML report
newman run postman_collection.json \
  --environment tulia-dev.postman_environment.json \
  --reporters cli,html \
  --reporter-html-export report.html
```

### CI/CD Integration
- Run tests on every commit
- Block merges if tests fail
- Generate test reports
- Track test coverage over time

## Best Practices

1. **Run tests in order** - Some tests depend on previous test data
2. **Clean up test data** - Delete created resources after testing
3. **Use separate test tenant** - Don't test on production data
4. **Monitor rate limits** - Avoid hitting limits during test runs
5. **Review failed tests** - Investigate root cause, don't just re-run
6. **Update tests** - Keep tests in sync with API changes
7. **Document edge cases** - Add tests for discovered bugs

## Troubleshooting

### Tests Failing Unexpectedly
- Check environment variables are set correctly
- Verify test data exists (products, customers, etc.)
- Review server logs for errors
- Ensure database is in clean state

### Rate Limit Issues During Testing
- Add delays between requests in Collection Runner
- Use separate API key for testing
- Request rate limit increase for test tenant

### Inconsistent Test Results
- Check for race conditions in async operations
- Verify test data isolation
- Review test execution order

## Maintenance

### Adding New Test Scenarios
1. Create new request in appropriate folder
2. Add descriptive name and documentation
3. Write test assertions in **Tests** tab
4. Add to this document with scenario details
5. Test locally before committing

### Updating Existing Tests
1. Review test assertions for accuracy
2. Update expected values if API changed
3. Add new assertions for new fields
4. Update documentation
5. Run full collection to verify no regressions
