"""
Offers and coupon management tools for LangGraph orchestration.
"""

from typing import Any, Dict, Optional, List
from decimal import Decimal
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class OffersGetApplicableTool(BaseTool):
    """
    Get applicable offers and discounts for customer or order.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - customer_id: UUID of the customer
    
    Optional parameters:
    - order_total: Order total to check minimum thresholds
    - product_ids: List of product IDs to check product-specific offers
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
                "order_total": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Order total to check minimum thresholds (optional)"
                },
                "product_ids": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "format": "uuid"
                    },
                    "description": "List of product IDs to check product-specific offers (optional)"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "customer_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Get applicable offers and discounts.
        
        Returns:
            ToolResponse with applicable offers including:
            - offers: List of applicable offers
            - coupons: List of available coupon codes
            - automatic_discounts: List of automatic discounts that will be applied
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "customer_id"])
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
        order_total = kwargs.get("order_total")
        product_ids = kwargs.get("product_ids", [])
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Customer
            from django.utils import timezone
            
            # Validate customer belongs to tenant
            customer = Customer.objects.get(id=customer_id, tenant_id=tenant_id)
            
            # For now, return a basic structure - this can be enhanced with actual offer models
            # when they are implemented in the catalog or orders app
            
            offers = []
            coupons = []
            automatic_discounts = []
            
            # Example offers based on customer tags or order total
            if 'vip' in customer.tags:
                offers.append({
                    "offer_id": "vip_discount",
                    "title": "VIP Customer Discount",
                    "description": "10% off for VIP customers",
                    "discount_type": "percentage",
                    "discount_value": 10,
                    "minimum_order": 0,
                    "applicable": True
                })
            
            if 'new_customer' in customer.tags:
                offers.append({
                    "offer_id": "new_customer_welcome",
                    "title": "Welcome Discount",
                    "description": "15% off your first order",
                    "discount_type": "percentage",
                    "discount_value": 15,
                    "minimum_order": 500,
                    "applicable": order_total is None or order_total >= 500
                })
            
            # Order total based offers
            if order_total:
                if order_total >= 1000:
                    offers.append({
                        "offer_id": "bulk_discount",
                        "title": "Bulk Order Discount",
                        "description": "5% off orders over KES 1,000",
                        "discount_type": "percentage",
                        "discount_value": 5,
                        "minimum_order": 1000,
                        "applicable": True
                    })
                
                if order_total >= 2000:
                    offers.append({
                        "offer_id": "free_delivery",
                        "title": "Free Delivery",
                        "description": "Free delivery on orders over KES 2,000",
                        "discount_type": "fixed",
                        "discount_value": 200,  # Delivery fee
                        "minimum_order": 2000,
                        "applicable": True
                    })
            
            # Available coupon codes (these would come from a Coupon model)
            coupons = [
                {
                    "coupon_code": "SAVE10",
                    "title": "Save 10%",
                    "description": "10% off any order",
                    "discount_type": "percentage",
                    "discount_value": 10,
                    "minimum_order": 0,
                    "expires_at": "2025-12-31T23:59:59Z",
                    "usage_limit": None,
                    "applicable": True
                },
                {
                    "coupon_code": "FIRST20",
                    "title": "First Order 20% Off",
                    "description": "20% off your first order",
                    "discount_type": "percentage",
                    "discount_value": 20,
                    "minimum_order": 300,
                    "expires_at": "2025-12-31T23:59:59Z",
                    "usage_limit": 1,
                    "applicable": 'new_customer' in customer.tags and (order_total is None or order_total >= 300)
                }
            ]
            
            # Automatic discounts that don't require codes
            if order_total and order_total >= 1500:
                automatic_discounts.append({
                    "discount_id": "auto_loyalty",
                    "title": "Loyalty Discount",
                    "description": "Automatic 3% loyalty discount",
                    "discount_type": "percentage",
                    "discount_value": 3,
                    "applied_automatically": True
                })
            
            # Build response data
            data = {
                "offers": offers,
                "coupons": coupons,
                "automatic_discounts": automatic_discounts,
                "customer_tags": customer.tags,
                "order_total_checked": order_total,
                "product_ids_checked": product_ids
            }
            
            self.log_tool_execution(
                "offers_get_applicable", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Customer.DoesNotExist:
            error_msg = f"Customer {customer_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "offers_get_applicable", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="CUSTOMER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to get applicable offers: {str(e)}"
            self.log_tool_execution(
                "offers_get_applicable", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="OFFERS_ERROR"
            )


class OrderApplyCouponTool(BaseTool):
    """
    Apply a coupon code to an order.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - order_id: UUID of the order
    - coupon_code: Coupon code to apply
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
                    "description": "UUID of the order"
                },
                "coupon_code": {
                    "type": "string",
                    "description": "Coupon code to apply"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "order_id", "coupon_code"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Apply a coupon code to an order.
        
        Returns:
            ToolResponse with updated order totals including:
            - order_id: UUID of the order
            - coupon_applied: Details of applied coupon
            - discount_amount: Amount discounted
            - new_subtotal: Updated subtotal
            - new_tax: Updated tax
            - new_total: Updated total
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "order_id", "coupon_code"])
        if error:
            return ToolResponse(success=False, error=error, error_code="MISSING_PARAMS")
        
        # Validate UUIDs
        for field in ["tenant_id", "request_id", "conversation_id", "order_id"]:
            error = validate_uuid(kwargs[field], field)
            if error:
                return ToolResponse(success=False, error=error, error_code="INVALID_UUID")
        
        tenant_id = kwargs["tenant_id"]
        request_id = kwargs["request_id"]
        conversation_id = kwargs["conversation_id"]
        order_id = kwargs["order_id"]
        coupon_code = kwargs["coupon_code"].upper().strip()
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.orders.models import Order
            from django.db import transaction
            
            # Get order with tenant scoping
            order = Order.objects.get(id=order_id, tenant_id=tenant_id)
            
            # Check if order is in a state that allows coupon application
            if order.status not in ['pending', 'confirmed']:
                return ToolResponse(
                    success=False,
                    error="Cannot apply coupon to order in current status",
                    error_code="INVALID_ORDER_STATUS"
                )
            
            # Validate coupon code (simplified validation - would use actual Coupon model)
            valid_coupons = {
                'SAVE10': {'type': 'percentage', 'value': 10, 'min_order': 0},
                'FIRST20': {'type': 'percentage', 'value': 20, 'min_order': 300},
                'WELCOME15': {'type': 'percentage', 'value': 15, 'min_order': 500},
                'FIXED50': {'type': 'fixed', 'value': 50, 'min_order': 200}
            }
            
            if coupon_code not in valid_coupons:
                return ToolResponse(
                    success=False,
                    error=f"Invalid coupon code: {coupon_code}",
                    error_code="INVALID_COUPON"
                )
            
            coupon_info = valid_coupons[coupon_code]
            
            # Check minimum order requirement
            if order.subtotal < coupon_info['min_order']:
                return ToolResponse(
                    success=False,
                    error=f"Order total must be at least KES {coupon_info['min_order']} to use this coupon",
                    error_code="MINIMUM_ORDER_NOT_MET"
                )
            
            # Calculate discount
            if coupon_info['type'] == 'percentage':
                discount_amount = order.subtotal * (Decimal(coupon_info['value']) / 100)
            else:  # fixed
                discount_amount = Decimal(coupon_info['value'])
            
            # Ensure discount doesn't exceed order total
            discount_amount = min(discount_amount, order.subtotal)
            
            # Apply discount in transaction
            with transaction.atomic():
                # Update order with discount
                new_subtotal = order.subtotal - discount_amount
                new_tax = new_subtotal * Decimal('0.16')  # Recalculate tax on discounted amount
                new_total = new_subtotal + new_tax
                
                order.subtotal = new_subtotal
                order.tax = new_tax
                order.total = new_total
                
                # Store coupon information in metadata
                if not order.metadata:
                    order.metadata = {}
                
                order.metadata['applied_coupons'] = order.metadata.get('applied_coupons', [])
                order.metadata['applied_coupons'].append({
                    'coupon_code': coupon_code,
                    'discount_type': coupon_info['type'],
                    'discount_value': coupon_info['value'],
                    'discount_amount': float(discount_amount),
                    'applied_at': timezone.now().isoformat()
                })
                
                order.save(update_fields=['subtotal', 'tax', 'total', 'metadata'])
            
            # Build response data
            data = {
                "order_id": str(order.id),
                "coupon_applied": {
                    "coupon_code": coupon_code,
                    "discount_type": coupon_info['type'],
                    "discount_value": coupon_info['value'],
                    "discount_amount": float(discount_amount)
                },
                "discount_amount": float(discount_amount),
                "new_subtotal": float(order.subtotal),
                "new_tax": float(order.tax),
                "new_total": float(order.total),
                "currency": order.currency,
                "savings": float(discount_amount)
            }
            
            self.log_tool_execution(
                "order_apply_coupon", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Order.DoesNotExist:
            error_msg = f"Order {order_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "order_apply_coupon", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="ORDER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to apply coupon: {str(e)}"
            self.log_tool_execution(
                "order_apply_coupon", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="COUPON_APPLICATION_ERROR"
            )