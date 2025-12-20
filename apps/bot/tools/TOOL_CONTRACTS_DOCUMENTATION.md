# Tool Contracts Documentation

This document provides comprehensive documentation for all 15 tool contracts implemented for the Tulia AI V2 LangGraph orchestration system.

## Overview

All tool contracts enforce strict tenant isolation and include the following required parameters:
- `tenant_id`: UUID of the tenant (string, uuid format)
- `request_id`: UUID for request tracing (string, uuid format)  
- `conversation_id`: UUID for conversation context (string, uuid format)

## Tool Contracts

### 1. tenant_get_context

**Purpose**: Fetch tenant configuration and bot persona

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`

**Returns**:
- `tenant_name`: Display name
- `bot_name`: Bot persona name
- `bot_intro`: Introduction message
- `tone_style`: Communication style
- `default_language`: Default language code
- `allowed_languages`: List of permitted languages
- `max_chattiness_level`: Cost control level (0-3)
- `catalog_link_base`: Web catalog URL
- `payments_enabled`: Dict of enabled payment methods
- `compliance`: Compliance settings
- `handoff`: Escalation rules

### 2. customer_get_or_create

**Purpose**: Get or create customer by phone number within tenant scope

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `phone_e164`: Phone number in E.164 format

**Optional Parameters**:
- `name`: Customer name
- `language_preference`: Preferred language code

**Returns**:
- `customer_id`: UUID of the customer
- `phone_e164`: Phone number
- `name`: Customer name (if available)
- `language_preference`: Preferred language
- `marketing_opt_in`: Marketing consent status
- `consent_flags`: Detailed consent flags
- `tags`: Customer tags
- `created`: Whether customer was newly created

### 3. customer_update_preferences

**Purpose**: Update customer preferences and consent flags

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `customer_id`: UUID of the customer

**Optional Parameters**:
- `language_preference`: Preferred language code
- `marketing_opt_in`: Marketing consent (true/false)
- `consent_flags`: Detailed consent flags object
- `tags`: Customer tags array

**Returns**:
- Updated customer data with changed fields

### 4. catalog_search

**Purpose**: Search products in tenant catalog with semantic search and filters

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `query`: Search query string

**Optional Parameters**:
- `category`: Product category filter
- `min_price`: Minimum price filter
- `max_price`: Maximum price filter
- `in_stock`: Filter by stock availability
- `limit`: Maximum number of results (default: 6, max: 50)

**Returns**:
- `products`: List of matching products
- `total_matches_estimate`: Estimated total matches
- `query_used`: The search query that was used
- `filters_applied`: Filters that were applied

### 5. catalog_get_item

**Purpose**: Get detailed product information by product ID

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `product_id`: UUID of the product

**Returns**:
- Complete product details including variants, specifications, and images

### 6. order_create

**Purpose**: Create a new order with cart items

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `customer_id`: UUID of the customer
- `items`: List of order items with product_id and quantity

**Optional Parameters**:
- `delivery_address`: Delivery address object
- `notes`: Order notes

**Returns**:
- `order_id`: UUID of the created order
- `order_reference`: Human-readable order reference
- `items`: List of order items with details
- `subtotal`: Order subtotal
- `tax`: Tax amount
- `total`: Total order amount
- `currency`: Order currency
- `status`: Order status

### 7. offers_get_applicable

**Purpose**: Get applicable offers and discounts for customer or order

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `customer_id`: UUID of the customer

**Optional Parameters**:
- `order_total`: Order total to check minimum thresholds
- `product_ids`: List of product IDs to check product-specific offers

**Returns**:
- `offers`: List of applicable offers
- `coupons`: List of available coupon codes
- `automatic_discounts`: List of automatic discounts that will be applied

### 8. order_apply_coupon

**Purpose**: Apply a coupon code to an order

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `order_id`: UUID of the order
- `coupon_code`: Coupon code to apply

**Returns**:
- Updated order totals with discount applied

### 9. payment_get_methods

**Purpose**: Get available payment methods for tenant

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`

**Optional Parameters**:
- `order_total`: Order total to check method-specific limits

**Returns**:
- `methods`: List of available payment methods
- `recommended`: Recommended method based on order total

### 10. payment_get_c2b_instructions

**Purpose**: Get M-Pesa C2B payment instructions

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `order_id`: UUID of the order

**Returns**:
- `paybill_number`: Paybill number
- `account_number`: Account number (order reference)
- `amount`: Amount to pay
- `instructions`: Step-by-step instructions

### 11. payment_initiate_stk_push

**Purpose**: Initiate M-Pesa STK Push payment

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `order_id`: UUID of the order
- `phone_number`: Customer phone number for STK push

**Returns**:
- `payment_request_id`: UUID of payment request
- `checkout_request_id`: M-Pesa checkout request ID
- `merchant_request_id`: M-Pesa merchant request ID
- `status`: Payment request status
- `message`: User-friendly message

### 12. payment_create_pesapal_checkout

**Purpose**: Create Pesapal checkout session for card payments

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `order_id`: UUID of the order
- `customer_email`: Customer email for checkout

**Returns**:
- `checkout_url`: URL to redirect customer for payment
- `checkout_session_id`: Pesapal checkout session ID
- `expires_at`: Checkout session expiration time

### 13. order_get_status

**Purpose**: Get order status and details by order ID or reference

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`

**One of**:
- `order_id`: UUID of the order
- `order_reference`: Order reference string
- `customer_id`: UUID to get customer's recent orders

**Returns**:
- Order details or list of orders with status information

### 14. kb_retrieve

**Purpose**: Retrieve relevant information from tenant knowledge base using RAG

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `query`: Search query for knowledge base

**Optional Parameters**:
- `top_k`: Number of results to return (default: 3, max: 10)
- `min_relevance_score`: Minimum relevance score (default: 0.7)

**Returns**:
- `snippets`: List of relevant text snippets
- `sources`: Source documents for the snippets
- `query_used`: The search query that was used
- `total_results`: Total number of results found

### 15. handoff_create_ticket

**Purpose**: Create human handoff ticket with conversation context

**Required Parameters**:
- `tenant_id`, `request_id`, `conversation_id`
- `customer_id`: UUID of the customer
- `reason`: Reason for escalation
- `category`: Issue category
- `context`: Conversation context and details

**Optional Parameters**:
- `priority`: Ticket priority (low, medium, high, urgent)

**Returns**:
- `ticket_id`: UUID of created ticket
- `ticket_number`: Human-readable ticket number
- `status`: Ticket status
- `priority`: Assigned priority
- `estimated_response_time`: Expected response time
- `agent_info`: Assigned agent information (if available)

## Tenant Isolation

All tools enforce tenant isolation through:

1. **Parameter Validation**: All tools require `tenant_id` as a UUID parameter
2. **Tenant Existence Check**: Tools validate that the tenant exists and is active
3. **Data Scoping**: All database queries are scoped to the tenant
4. **Error Handling**: Invalid or non-existent tenants return appropriate error codes

## Error Codes

Common error codes returned by tools:

- `MISSING_PARAMS`: Required parameters are missing
- `INVALID_UUID`: Parameter is not a valid UUID format
- `INVALID_TENANT`: Tenant does not exist or is inactive
- `CUSTOMER_NOT_FOUND`: Customer not found in tenant scope
- `PRODUCT_NOT_FOUND`: Product not found in tenant catalog
- `ORDER_NOT_FOUND`: Order not found in tenant scope
- `INSUFFICIENT_STOCK`: Not enough stock for requested quantity
- `PAYMENT_METHOD_NOT_AVAILABLE`: Payment method not configured
- `TOOL_EXECUTION_ERROR`: General execution error

## Usage Example

```python
from apps.bot.tools.registry import ToolRegistry

# Get a tool
tool = ToolRegistry.get_tool("catalog_search")

# Execute with required parameters
result = tool.execute(
    tenant_id="550e8400-e29b-41d4-a716-446655440000",
    request_id="550e8400-e29b-41d4-a716-446655440001", 
    conversation_id="550e8400-e29b-41d4-a716-446655440002",
    query="laptop computers",
    limit=5
)

if result.success:
    products = result.data["products"]
    print(f"Found {len(products)} products")
else:
    print(f"Error: {result.error} (Code: {result.error_code})")
```

## Integration with LangGraph

These tools are designed to be used within LangGraph nodes as backend service interfaces. Each tool provides:

1. **Strict JSON Schema**: For LangGraph tool calling
2. **Tenant Isolation**: Ensures data security
3. **Error Handling**: Graceful failure modes
4. **Observability**: Comprehensive logging
5. **Validation**: Input parameter validation

The tools serve as the authoritative data layer for the LangGraph orchestrated commerce agent, ensuring all business operations are properly scoped and validated.