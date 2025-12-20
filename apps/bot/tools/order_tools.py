"""
Order management tools for LangGraph orchestration.
"""

from typing import Any, Dict, Optional, List
from decimal import Decimal
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class OrderCreateTool(BaseTool):
    """
    Create a new order with cart items.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - customer_id: UUID of the customer
    - items: List of order items with product_id and quantity
    
    Optional parameters:
    - delivery_address: Delivery address object
    - notes: Order notes
    """
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tenant_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the tenant"
                },
                "request_id": {
                    "type": "string", 
                    "format": "uuid",
                    "description": "UUID for request tracing"
                },
                "conversation_id": {
                    "type": "string",
                    "format": "uuid", 
                    "description": "UUID for conversation context"
                },
                "customer_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the customer"
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "format": "uuid",
                                "description": "UUID of the product"
                            },
                            "quantity": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Quantity to order"
                            },
                            "variant_id": {
                                "type": "string",
                                "format": "uuid",
                                "description": "UUID of product variant (optional)"
                            }
                        },
                        "required": ["product_id", "quantity"]
                    },
                    "minItems": 1,
                    "description": "List of items to order"
                },
                "delivery_address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                        "country": {"type": "string"},
                        "phone": {"type": "string"}
                    },
                    "description": "Delivery address (optional)"
                },
                "notes": {
                    "type": "string",
                    "description": "Order notes (optional)"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "customer_id", "items"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Create a new order with cart items.
        
        Returns:
            ToolResponse with order details including:
            - order_id: UUID of the created order
            - order_reference: Human-readable order reference
            - items: List of order items with details
            - subtotal: Order subtotal
            - tax: Tax amount
            - total: Total order amount
            - currency: Order currency
            - status: Order status
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "customer_id", "items"])
        if error:
            return ToolResponse(success=False, error=error, error_code="MISSING_PARAMS")
        
        # Validate UUIDs
        for field in ["tenant_id", "request_id", "conversation_id", "customer_id"]:
            error = validate_uuid(kwargs[field], field)
            if error:
                return ToolResponse(success=False, error=error, error_code="INVALID_UUID")
        
        tenant_id = kwargs["tenant_id"]
        request_id = kwargs["request_id"]
        conversation_id = kwargs["conversation_id"]
        customer_id = kwargs["customer_id"]
        items = kwargs["items"]
        delivery_address = kwargs.get("delivery_address")
        notes = kwargs.get("notes")
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.orders.models import Order, OrderItem
            from apps.catalog.models import Product, ProductVariant
            from apps.tenants.models import Customer
            from django.db import transaction
            from django.utils import timezone
            import uuid
            
            # Validate customer belongs to tenant
            customer = Customer.objects.get(id=customer_id, tenant_id=tenant_id)
            
            # Validate items and calculate totals
            order_items_data = []
            subtotal = Decimal('0.00')
            
            for item in items:
                # Validate product
                product = Product.objects.get(
                    id=item["product_id"],
                    tenant_id=tenant_id,
                    status__in=['active', 'trial']
                )
                
                quantity = item["quantity"]
                variant_id = item.get("variant_id")
                
                # Check if variant is specified
                if variant_id:
                    variant = ProductVariant.objects.get(
                        id=variant_id,
                        product=product,
                        status__in=['active', 'trial']
                    )
                    unit_price = variant.price
                    item_name = f"{product.name} - {variant.name}"
                    sku = getattr(variant, 'sku', None)
                else:
                    unit_price = product.price
                    item_name = product.name
                    sku = getattr(product, 'sku', None)
                
                # Check stock availability
                available_stock = variant.stock_quantity if variant_id else product.stock_quantity
                if available_stock < quantity:
                    return ToolResponse(
                        success=False,
                        error=f"Insufficient stock for {item_name}. Available: {available_stock}, Requested: {quantity}",
                        error_code="INSUFFICIENT_STOCK"
                    )
                
                line_total = unit_price * quantity
                subtotal += line_total
                
                order_items_data.append({
                    "product": product,
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "name": item_name,
                    "sku": sku
                })
            
            # Calculate tax (simple 16% VAT - can be made configurable)
            tax_rate = Decimal('0.16')
            tax = subtotal * tax_rate
            total = subtotal + tax
            
            # Create order in transaction
            with transaction.atomic():
                # Generate order reference
                order_reference = f"ORD-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
                
                # Create order
                order = Order.objects.create(
                    tenant_id=tenant_id,
                    customer=customer,
                    order_reference=order_reference,
                    status='pending',
                    subtotal=subtotal,
                    tax=tax,
                    total=total,
                    currency='KES',  # Can be made configurable per tenant
                    delivery_address=delivery_address or {},
                    notes=notes or '',
                    metadata={
                        'conversation_id': conversation_id,
                        'request_id': request_id,
                        'created_via': 'langgraph_agent'
                    }
                )
                
                # Create order items
                created_items = []
                for item_data in order_items_data:
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=item_data["product"],
                        variant_id=item_data["variant_id"],
                        quantity=item_data["quantity"],
                        unit_price=item_data["unit_price"],
                        line_total=item_data["line_total"],
                        name=item_data["name"],
                        sku=item_data["sku"]
                    )
                    created_items.append(order_item)
                
                # Update stock quantities
                for item_data in order_items_data:
                    if item_data["variant_id"]:
                        variant = ProductVariant.objects.get(id=item_data["variant_id"])
                        variant.stock_quantity -= item_data["quantity"]
                        variant.save(update_fields=['stock_quantity'])
                    else:
                        product = item_data["product"]
                        product.stock_quantity -= item_data["quantity"]
                        product.save(update_fields=['stock_quantity'])
            
            # Build response data
            items_response = []
            for order_item in created_items:
                items_response.append({
                    "order_item_id": str(order_item.id),
                    "product_id": str(order_item.product.id),
                    "variant_id": str(order_item.variant_id) if order_item.variant_id else None,
                    "name": order_item.name,
                    "sku": order_item.sku,
                    "quantity": order_item.quantity,
                    "unit_price": float(order_item.unit_price),
                    "line_total": float(order_item.line_total)
                })
            
            data = {
                "order_id": str(order.id),
                "order_reference": order.order_reference,
                "items": items_response,
                "subtotal": float(order.subtotal),
                "tax": float(order.tax),
                "total": float(order.total),
                "currency": order.currency,
                "status": order.status,
                "delivery_address": order.delivery_address,
                "notes": order.notes,
                "created_at": order.created_at.isoformat()
            }
            
            self.log_tool_execution(
                "order_create", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Customer.DoesNotExist:
            error_msg = f"Customer {customer_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "order_create", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="CUSTOMER_NOT_FOUND"
            )
        except Product.DoesNotExist:
            error_msg = "One or more products not found"
            self.log_tool_execution(
                "order_create", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="PRODUCT_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to create order: {str(e)}"
            self.log_tool_execution(
                "order_create", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="ORDER_CREATE_ERROR"
            )


class OrderGetStatusTool(BaseTool):
    """
    Get order status and details by order ID or reference.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    
    One of:
    - order_id: UUID of the order
    - order_reference: Order reference string
    - customer_id: UUID to get customer's recent orders
    """
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tenant_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the tenant"
                },
                "request_id": {
                    "type": "string", 
                    "format": "uuid",
                    "description": "UUID for request tracing"
                },
                "conversation_id": {
                    "type": "string",
                    "format": "uuid", 
                    "description": "UUID for conversation context"
                },
                "order_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the order (optional)"
                },
                "order_reference": {
                    "type": "string",
                    "description": "Order reference string (optional)"
                },
                "customer_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of customer to get recent orders (optional)"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Get order status and details.
        
        Returns:
            ToolResponse with order details or list of orders
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id"])
        if error:
            return ToolResponse(success=False, error=error, error_code="MISSING_PARAMS")
        
        # Validate UUIDs
        for field in ["tenant_id", "request_id", "conversation_id"]:
            error = validate_uuid(kwargs[field], field)
            if error:
                return ToolResponse(success=False, error=error, error_code="INVALID_UUID")
        
        tenant_id = kwargs["tenant_id"]
        request_id = kwargs["request_id"]
        conversation_id = kwargs["conversation_id"]
        order_id = kwargs.get("order_id")
        order_reference = kwargs.get("order_reference")
        customer_id = kwargs.get("customer_id")
        
        # Validate that at least one identifier is provided
        if not any([order_id, order_reference, customer_id]):
            return ToolResponse(
                success=False,
                error="Must provide order_id, order_reference, or customer_id",
                error_code="MISSING_IDENTIFIER"
            )
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.orders.models import Order
            from apps.tenants.models import Customer
            
            # Build query with tenant scoping
            queryset = Order.objects.filter(tenant_id=tenant_id).select_related('customer')
            
            if order_id:
                # Get specific order by ID
                order = queryset.get(id=order_id)
                orders = [order]
            elif order_reference:
                # Get specific order by reference
                order = queryset.get(order_reference=order_reference)
                orders = [order]
            elif customer_id:
                # Get customer's recent orders
                customer = Customer.objects.get(id=customer_id, tenant_id=tenant_id)
                orders = queryset.filter(customer=customer).order_by('-created_at')[:5]
            
            # Build response data
            orders_data = []
            for order in orders:
                # Get order items
                items = []
                for item in order.items.all():
                    items.append({
                        "order_item_id": str(item.id),
                        "product_id": str(item.product.id),
                        "variant_id": str(item.variant_id) if item.variant_id else None,
                        "name": item.name,
                        "sku": item.sku,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price),
                        "line_total": float(item.line_total)
                    })
                
                order_data = {
                    "order_id": str(order.id),
                    "order_reference": order.order_reference,
                    "status": order.status,
                    "items": items,
                    "subtotal": float(order.subtotal),
                    "tax": float(order.tax),
                    "total": float(order.total),
                    "currency": order.currency,
                    "delivery_address": order.delivery_address,
                    "notes": order.notes,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat(),
                    "customer_id": str(order.customer.id)
                }
                orders_data.append(order_data)
            
            # Return single order or list
            if len(orders_data) == 1 and (order_id or order_reference):
                data = orders_data[0]
            else:
                data = {
                    "orders": orders_data,
                    "count": len(orders_data)
                }
            
            self.log_tool_execution(
                "order_get_status", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Order.DoesNotExist:
            error_msg = "Order not found"
            self.log_tool_execution(
                "order_get_status", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="ORDER_NOT_FOUND"
            )
        except Customer.DoesNotExist:
            error_msg = f"Customer {customer_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "order_get_status", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="CUSTOMER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to get order status: {str(e)}"
            self.log_tool_execution(
                "order_get_status", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="FETCH_ERROR"
            )