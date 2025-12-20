# Tool Contracts for LangGraph Orchestration

This module implements all 15 required tool contracts with strict tenant isolation for the Tulia AI V2 LangGraph refactor.

## Overview

The tool contracts provide a standardized interface for LangGraph nodes to interact with backend services while enforcing:

- **Strict Tenant Isolation**: All tools require `tenant_id` and validate tenant access
- **Request Tracing**: All tools require `request_id` and `conversation_id` for observability
- **Input Validation**: Comprehensive validation of UUIDs, parameters, and business rules
- **Error Handling**: Structured error responses with error codes
- **Security**: No cross-tenant data leakage, proper authentication checks

## Tool Contracts

### 1. Tenant Context Tools

#### `tenant_get_context`
Fetch tenant configuration and bot persona.

**Parameters:**
- `tenant_id` (UUID): Tenant identifier
- `request_id` (UUID): Request tracing ID
- `conversation_id` (UUID): Conversation context ID

**Returns:**
- Tenant name, bot persona, payment methods, compliance settings

### 2. Customer Management Tools

#### `customer_get_or_create`
Get or create tenant-scoped customer profile by phone number.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id` (UUIDs)
- `phone_e164` (string): Customer phone in E164 format

**Returns:**
- Customer profile with preferences and consent flags

#### `customer_update_preferences`
Update customer preferences with audit trail.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `customer_id` (UUIDs)
- `preferences` (object): Preferences to update

**Returns:**
- Updated customer data with change audit

### 3. Catalog Tools

#### `catalog_search`
Search tenant catalog with semantic search and filters.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id` (UUIDs)
- `query` (string): Search query
- `filters` (object, optional): Category, price, stock filters
- `limit` (integer, optional): Max results (default 6, max 20)

**Returns:**
- Product results with variants and availability

#### `catalog_get_item`
Fetch authoritative item details by product ID.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id` (UUIDs)
- `product_id` (UUID): Product identifier
- `variant_id` (UUID, optional): Specific variant

**Returns:**
- Complete product details with variants and pricing

### 4. Order Management Tools

#### `order_create`
Create order draft with totals calculation.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `customer_id` (UUIDs)
- `items` (array): Order items with product_id, quantity, variant_id
- `delivery_address` (object, optional): Delivery information
- `notes` (string, optional): Order notes

**Returns:**
- Created order with totals breakdown

#### `order_get_status`
Fetch order and payment status.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id` (UUIDs)
- `order_identifier` (string): Order ID, number, or customer phone
- `customer_phone` (string, optional): Additional filtering

**Returns:**
- Order details with payment and delivery status

### 5. Offers & Coupons Tools

#### `offers_get_applicable`
Fetch applicable offers/coupons for customer or order.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `customer_id` (UUIDs)
- `order_total` (number, optional): Order total for calculations
- `product_ids` (array, optional): Products for targeted offers

**Returns:**
- Available offers, coupons, and recommendations

#### `order_apply_coupon`
Apply coupon code and return updated totals.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `order_id` (UUIDs)
- `coupon_code` (string): Coupon code to apply

**Returns:**
- Updated order totals with discount applied

### 6. Payment Processing Tools

#### `payment_get_methods`
Get enabled payment methods for tenant.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id` (UUIDs)

**Returns:**
- Available payment methods with configurations

#### `payment_get_c2b_instructions`
Generate MPESA C2B payment instructions.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `order_id` (UUIDs)

**Returns:**
- Step-by-step payment instructions with reference

#### `payment_initiate_stk_push`
Initiate MPESA STK push payment.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `order_id` (UUIDs)
- `phone_e164` (string): Customer phone (Kenya format)

**Returns:**
- STK push status and tracking information

#### `payment_create_pesapal_checkout`
Create PesaPal checkout URL for card payments.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `order_id` (UUIDs)
- `customer_email` (string, optional): Customer email

**Returns:**
- Secure checkout URL and payment details

### 7. Knowledge Base Tools

#### `kb_retrieve`
Tenant-scoped vector search for support queries.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id` (UUIDs)
- `query` (string): Search query
- `document_types` (array, optional): Filter by doc types
- `max_results` (integer, optional): Max results (default 8)
- `min_confidence` (number, optional): Confidence threshold

**Returns:**
- Relevant knowledge snippets with sources and confidence

### 8. Human Handoff Tools

#### `handoff_create_ticket`
Create human handoff ticket with context preservation.

**Parameters:**
- `tenant_id`, `request_id`, `conversation_id`, `customer_id` (UUIDs)
- `reason` (enum): Escalation reason
- `priority` (enum): Ticket priority (low/medium/high/urgent)
- `category` (enum): Issue category
- `context` (object): Conversation context and details

**Returns:**
- Ticket details with estimated response time

## Architecture

### Base Classes

- **`BaseTool`**: Abstract base class with tenant validation and logging
- **`ToolResponse`**: Standardized response format
- **`ToolRegistry`**: Central registry for tool discovery and execution

### Validation

- **UUID Validation**: All IDs must be valid UUIDs
- **Tenant Isolation**: All queries scoped to tenant_id
- **Parameter Validation**: Required fields, formats, and business rules
- **Error Handling**: Structured errors with codes and messages

### Security Features

- **Tenant Access Validation**: Verify tenant exists and is active
- **Composite Key Isolation**: Customer lookups use (tenant_id, phone_e164)
- **No Cross-Tenant Leakage**: All database queries include tenant filtering
- **Audit Logging**: All tool executions logged with context

## Usage

### Tool Registration

```python
from apps.bot.tools import get_tool, execute_tool

# Get tool instance
tool = get_tool("catalog_search")

# Execute tool
result = execute_tool("catalog_search", 
                     tenant_id="...", 
                     request_id="...", 
                     conversation_id="...",
                     query="laptops")
```

### LangGraph Integration

```python
from apps.bot.tools.registry import get_tool_schemas

# Get all tool schemas for LangGraph
schemas = get_tool_schemas()

# Use in LangGraph node
def catalog_search_node(state):
    tool = get_tool("catalog_search")
    response = tool.execute(**state.get_tool_params())
    return {"catalog_results": response.data}
```

## Testing

The tool contracts include comprehensive tests covering:

- **Functionality**: All 15 tools with success/error scenarios
- **Tenant Isolation**: Cross-tenant access prevention
- **Input Validation**: Parameter validation and error handling
- **Schema Validation**: JSON schema compliance
- **Registry**: Tool discovery and execution

Run tests:
```bash
python -m pytest apps/bot/tests/test_tool_registry_simple.py -v
```

## Error Codes

Common error codes returned by tools:

- `MISSING_PARAMS`: Required parameters missing
- `INVALID_UUID`: Invalid UUID format
- `INVALID_TENANT`: Tenant not found or inactive
- `CUSTOMER_NOT_FOUND`: Customer access denied
- `PRODUCT_NOT_FOUND`: Product not found or access denied
- `ORDER_NOT_FOUND`: Order not found or access denied
- `INSUFFICIENT_INVENTORY`: Not enough stock
- `PAYMENT_ERROR`: Payment processing failed
- `TOOL_NOT_FOUND`: Tool not registered
- `TOOL_EXECUTION_ERROR`: Unexpected execution error

## Integration Points

The tool contracts integrate with:

- **Tenant Models**: `apps.tenants.models.Tenant`, `Customer`
- **Catalog Models**: `apps.catalog.models.Product`, `ProductVariant`
- **Order Models**: `apps.orders.models.Order`, `OrderItem`
- **Payment Services**: `apps.integrations.services.MpesaService`, `PesapalService`
- **Knowledge Base**: `apps.bot.models.TenantDocument`
- **RBAC System**: Scope-based permission checking

## Performance Considerations

- **Database Queries**: Optimized with select_related and prefetch_related
- **Caching**: Tool results can be cached at the LangGraph level
- **Pagination**: Large result sets are paginated
- **Timeouts**: Tools have reasonable execution timeouts
- **Connection Pooling**: Database connections are pooled

## Monitoring & Observability

All tool executions are logged with:

- **Request Tracing**: request_id and conversation_id
- **Performance Metrics**: Execution time and success rates
- **Error Tracking**: Detailed error information
- **Tenant Context**: All logs include tenant_id
- **Audit Trail**: Customer preference changes and order creation

## Future Enhancements

Planned improvements:

- **Caching Layer**: Redis caching for frequently accessed data
- **Rate Limiting**: Per-tenant rate limiting for expensive operations
- **Async Support**: Async tool execution for better performance
- **Batch Operations**: Bulk operations for multiple items
- **Webhooks**: Real-time notifications for state changes