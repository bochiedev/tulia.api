"""
Payment processing tools for LangGraph orchestration.
"""

from typing import Any, Dict, Optional, List
from decimal import Decimal
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class PaymentGetMethodsTool(BaseTool):
    """
    Get available payment methods for tenant.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    
    Optional parameters:
    - order_total: Order total to check method-specific limits
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
                "order_total": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Order total to check method limits (optional)"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Get available payment methods for tenant.
        
        Returns:
            ToolResponse with payment methods including:
            - methods: List of available payment methods
            - recommended: Recommended method based on order total
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
        order_total = kwargs.get("order_total")
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Tenant
            
            # Get tenant with settings
            tenant = Tenant.objects.select_related('settings').get(id=tenant_id, is_active=True)
            
            # Check enabled payment methods from tenant configuration
            payment_methods_enabled = getattr(tenant, 'payment_methods_enabled', {})
            if not payment_methods_enabled:
                # Default configuration if not set
                payment_methods_enabled = {
                    'mpesa_stk': True,
                    'mpesa_c2b': True,
                    'pesapal_card': True,
                    'bank_transfer': False
                }
            
            methods = []
            
            # M-Pesa STK Push
            if payment_methods_enabled.get('mpesa_stk', False) and hasattr(tenant, 'settings'):
                if getattr(tenant.settings, 'mpesa_consumer_key', None):
                    methods.append({
                        "method_id": "mpesa_stk",
                        "name": "M-Pesa STK Push",
                        "description": "Pay directly from your M-Pesa account",
                        "type": "mobile_money",
                        "currency": "KES",
                        "min_amount": 10,
                        "max_amount": 150000,
                        "available": True,
                        "processing_fee": 0,
                        "instructions": "You will receive a prompt on your phone to complete payment"
                    })
            
            # M-Pesa C2B (Customer to Business)
            if payment_methods_enabled.get('mpesa_c2b', False) and hasattr(tenant, 'settings'):
                if getattr(tenant.settings, 'mpesa_shortcode', None):
                    methods.append({
                        "method_id": "mpesa_c2b",
                        "name": "M-Pesa Paybill",
                        "description": "Pay via M-Pesa Paybill",
                        "type": "mobile_money",
                        "currency": "KES",
                        "min_amount": 1,
                        "max_amount": 999999,
                        "available": True,
                        "processing_fee": 0,
                        "instructions": f"Send money to Paybill {getattr(tenant.settings, 'mpesa_shortcode', 'XXXXX')}"
                    })
            
            # Pesapal (Card payments)
            if payment_methods_enabled.get('pesapal_card', False) and hasattr(tenant, 'settings'):
                if getattr(tenant.settings, 'pesapal_consumer_key', None):
                    methods.append({
                        "method_id": "pesapal_card",
                        "name": "Credit/Debit Card",
                        "description": "Pay with Visa, Mastercard, or other cards",
                        "type": "card",
                        "currency": "KES",
                        "min_amount": 50,
                        "max_amount": 1000000,
                        "available": True,
                        "processing_fee": 3.5,  # Percentage
                        "instructions": "You will be redirected to secure payment page"
                    })
            
            # Bank Transfer (if configured)
            if payment_methods_enabled.get('bank_transfer', False):
                methods.append({
                    "method_id": "bank_transfer",
                    "name": "Bank Transfer",
                    "description": "Direct bank transfer",
                    "type": "bank_transfer",
                    "currency": "KES",
                    "min_amount": 100,
                    "max_amount": 10000000,
                    "available": True,
                    "processing_fee": 0,
                    "instructions": "Transfer to provided bank account details"
                })
            
            # Filter methods by order total if provided
            if order_total:
                available_methods = []
                for method in methods:
                    if method["min_amount"] <= order_total <= method["max_amount"]:
                        available_methods.append(method)
                methods = available_methods
            
            # Determine recommended method
            recommended = None
            if methods:
                if order_total:
                    # Recommend based on amount
                    if order_total <= 5000:
                        # Small amounts - prefer M-Pesa STK
                        recommended = next((m for m in methods if m["method_id"] == "mpesa_stk"), methods[0])
                    elif order_total <= 50000:
                        # Medium amounts - prefer card or M-Pesa
                        recommended = next((m for m in methods if m["method_id"] in ["pesapal_card", "mpesa_stk"]), methods[0])
                    else:
                        # Large amounts - prefer bank transfer or card
                        recommended = next((m for m in methods if m["method_id"] in ["bank_transfer", "pesapal_card"]), methods[0])
                else:
                    # Default to first available method
                    recommended = methods[0]
            
            # Build response data
            data = {
                "methods": methods,
                "recommended": recommended,
                "order_total_checked": order_total,
                "currency": "KES",
                "methods_count": len(methods)
            }
            
            self.log_tool_execution(
                "payment_get_methods", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Exception as e:
            error_msg = f"Failed to get payment methods: {str(e)}"
            self.log_tool_execution(
                "payment_get_methods", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="PAYMENT_METHODS_ERROR"
            )


class PaymentGetC2BInstructionsTool(BaseTool):
    """
    Get M-Pesa C2B payment instructions.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - order_id: UUID of the order
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
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "order_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Get M-Pesa C2B payment instructions.
        
        Returns:
            ToolResponse with C2B instructions including:
            - paybill_number: Paybill number
            - account_number: Account number (order reference)
            - amount: Amount to pay
            - instructions: Step-by-step instructions
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "order_id"])
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
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Tenant
            from apps.orders.models import Order
            
            # Get tenant with settings
            tenant = Tenant.objects.select_related('settings').get(id=tenant_id, status__in=['active', 'trial'])
            
            # Get order
            order = Order.objects.get(id=order_id, tenant_id=tenant_id)
            
            # Check if M-Pesa C2B is enabled
            if not hasattr(tenant, 'settings') or not getattr(tenant.settings, 'mpesa_shortcode', None):
                return ToolResponse(
                    success=False,
                    error="M-Pesa C2B payment not configured for this tenant",
                    error_code="PAYMENT_METHOD_NOT_AVAILABLE"
                )
            
            paybill_number = getattr(tenant.settings, 'mpesa_shortcode')
            account_number = order.order_reference
            amount = int(order.total)  # M-Pesa amounts are in whole numbers
            
            # Build instructions
            instructions = [
                "1. Go to M-Pesa on your phone",
                "2. Select 'Lipa na M-Pesa'",
                "3. Select 'Pay Bill'",
                f"4. Enter Business No: {paybill_number}",
                f"5. Enter Account No: {account_number}",
                f"6. Enter Amount: {amount}",
                "7. Enter your M-Pesa PIN",
                "8. Confirm the payment",
                "9. You will receive a confirmation SMS"
            ]
            
            # Build response data
            data = {
                "paybill_number": paybill_number,
                "account_number": account_number,
                "amount": amount,
                "currency": "KES",
                "order_reference": order.order_reference,
                "instructions": instructions,
                "formatted_instructions": f"""
*M-Pesa Payment Instructions*

💰 *Amount:* KES {amount:,}
🏢 *Paybill:* {paybill_number}
📋 *Account:* {account_number}

*Steps:*
{chr(10).join(instructions)}

⚠️ *Important:* Use the exact account number above to ensure your payment is processed correctly.
                """.strip()
            }
            
            self.log_tool_execution(
                "payment_get_c2b_instructions", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Order.DoesNotExist:
            error_msg = f"Order {order_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "payment_get_c2b_instructions", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="ORDER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to get C2B instructions: {str(e)}"
            self.log_tool_execution(
                "payment_get_c2b_instructions", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="C2B_INSTRUCTIONS_ERROR"
            )


class PaymentInitiateStkPushTool(BaseTool):
    """
    Initiate M-Pesa STK Push payment.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - order_id: UUID of the order
    - phone_number: Customer phone number for STK push
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
                "phone_number": {
                    "type": "string",
                    "pattern": "^\\+254[0-9]{9}$",
                    "description": "Customer phone number in format +254XXXXXXXXX"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "order_id", "phone_number"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Initiate M-Pesa STK Push payment.
        
        Returns:
            ToolResponse with STK push details including:
            - payment_request_id: UUID of payment request
            - checkout_request_id: M-Pesa checkout request ID
            - merchant_request_id: M-Pesa merchant request ID
            - status: Payment request status
            - message: User-friendly message
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "order_id", "phone_number"])
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
        phone_number = kwargs["phone_number"]
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Tenant
            from apps.orders.models import Order
            import uuid
            
            # Get tenant with settings
            tenant = Tenant.objects.select_related('settings').get(id=tenant_id, status__in=['active', 'trial'])
            
            # Get order
            order = Order.objects.get(id=order_id, tenant_id=tenant_id)
            
            # Check if M-Pesa STK is enabled and configured
            if not hasattr(tenant, 'settings') or not getattr(tenant.settings, 'mpesa_consumer_key', None):
                return ToolResponse(
                    success=False,
                    error="M-Pesa STK Push not configured for this tenant",
                    error_code="PAYMENT_METHOD_NOT_AVAILABLE"
                )
            
            # Validate order status
            if order.status not in ['pending', 'confirmed']:
                return ToolResponse(
                    success=False,
                    error="Order is not in a payable state",
                    error_code="INVALID_ORDER_STATUS"
                )
            
            # Generate payment request ID
            payment_request_id = str(uuid.uuid4())
            
            # For now, simulate STK push initiation
            # In production, this would integrate with actual M-Pesa API
            checkout_request_id = f"ws_CO_{uuid.uuid4().hex[:20]}"
            merchant_request_id = f"mr_{uuid.uuid4().hex[:15]}"
            
            # Update order with payment request info
            if not order.metadata:
                order.metadata = {}
            
            order.metadata['payment_requests'] = order.metadata.get('payment_requests', [])
            order.metadata['payment_requests'].append({
                'payment_request_id': payment_request_id,
                'method': 'mpesa_stk',
                'phone_number': phone_number,
                'amount': float(order.total),
                'checkout_request_id': checkout_request_id,
                'merchant_request_id': merchant_request_id,
                'status': 'initiated',
                'initiated_at': timezone.now().isoformat()
            })
            
            order.save(update_fields=['metadata'])
            
            # Build response data
            data = {
                "payment_request_id": payment_request_id,
                "checkout_request_id": checkout_request_id,
                "merchant_request_id": merchant_request_id,
                "status": "initiated",
                "message": f"Payment request sent to {phone_number}. Please check your phone and enter your M-Pesa PIN to complete the payment.",
                "amount": float(order.total),
                "currency": "KES",
                "phone_number": phone_number,
                "order_reference": order.order_reference,
                "expires_in_seconds": 120  # STK push typically expires in 2 minutes
            }
            
            self.log_tool_execution(
                "payment_initiate_stk_push", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Order.DoesNotExist:
            error_msg = f"Order {order_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "payment_initiate_stk_push", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="ORDER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to initiate STK push: {str(e)}"
            self.log_tool_execution(
                "payment_initiate_stk_push", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="STK_PUSH_ERROR"
            )


class PaymentCreatePesapalCheckoutTool(BaseTool):
    """
    Create Pesapal checkout session for card payments.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - order_id: UUID of the order
    - customer_email: Customer email for checkout
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
                "customer_email": {
                    "type": "string",
                    "format": "email",
                    "description": "Customer email for checkout"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "order_id", "customer_email"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Create Pesapal checkout session for card payments.
        
        Returns:
            ToolResponse with checkout details including:
            - checkout_url: URL to redirect customer for payment
            - checkout_session_id: Pesapal checkout session ID
            - expires_at: Checkout session expiration time
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "order_id", "customer_email"])
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
        customer_email = kwargs["customer_email"]
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Tenant
            from apps.orders.models import Order
            from django.utils import timezone
            import uuid
            from datetime import timedelta
            
            # Get tenant with settings
            tenant = Tenant.objects.select_related('settings').get(id=tenant_id, status__in=['active', 'trial'])
            
            # Get order
            order = Order.objects.get(id=order_id, tenant_id=tenant_id)
            
            # Check if Pesapal is enabled and configured
            if not hasattr(tenant, 'settings') or not getattr(tenant.settings, 'pesapal_consumer_key', None):
                return ToolResponse(
                    success=False,
                    error="Pesapal card payments not configured for this tenant",
                    error_code="PAYMENT_METHOD_NOT_AVAILABLE"
                )
            
            # Validate order status
            if order.status not in ['pending', 'confirmed']:
                return ToolResponse(
                    success=False,
                    error="Order is not in a payable state",
                    error_code="INVALID_ORDER_STATUS"
                )
            
            # Generate checkout session ID
            checkout_session_id = f"ps_{uuid.uuid4().hex[:20]}"
            
            # Calculate expiration (30 minutes from now)
            expires_at = timezone.now() + timedelta(minutes=30)
            
            # For now, simulate Pesapal checkout creation
            # In production, this would integrate with actual Pesapal API
            checkout_url = f"https://checkout.pesapal.com/session/{checkout_session_id}"
            
            # Update order with payment request info
            if not order.metadata:
                order.metadata = {}
            
            order.metadata['payment_requests'] = order.metadata.get('payment_requests', [])
            order.metadata['payment_requests'].append({
                'payment_request_id': str(uuid.uuid4()),
                'method': 'pesapal_card',
                'customer_email': customer_email,
                'amount': float(order.total),
                'checkout_session_id': checkout_session_id,
                'checkout_url': checkout_url,
                'status': 'initiated',
                'initiated_at': timezone.now().isoformat(),
                'expires_at': expires_at.isoformat()
            })
            
            order.save(update_fields=['metadata'])
            
            # Build response data
            data = {
                "checkout_url": checkout_url,
                "checkout_session_id": checkout_session_id,
                "expires_at": expires_at.isoformat(),
                "amount": float(order.total),
                "currency": "KES",
                "customer_email": customer_email,
                "order_reference": order.order_reference,
                "message": "Click the link below to complete your payment with credit/debit card",
                "expires_in_minutes": 30
            }
            
            self.log_tool_execution(
                "payment_create_pesapal_checkout", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Order.DoesNotExist:
            error_msg = f"Order {order_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "payment_create_pesapal_checkout", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="ORDER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to create Pesapal checkout: {str(e)}"
            self.log_tool_execution(
                "payment_create_pesapal_checkout", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="PESAPAL_CHECKOUT_ERROR"
            )