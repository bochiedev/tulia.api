"""
Customer management tools for LangGraph orchestration.
"""

from typing import Any, Dict, Optional
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class CustomerGetOrCreateTool(BaseTool):
    """
    Get or create customer by phone number within tenant scope.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - phone_e164: Phone number in E.164 format
    
    Optional parameters:
    - name: Customer name
    - language_preference: Preferred language code
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
                "phone_e164": {
                    "type": "string",
                    "pattern": "^\\+[1-9]\\d{1,14}$",
                    "description": "Phone number in E.164 format"
                },
                "name": {
                    "type": "string",
                    "description": "Customer name (optional)"
                },
                "language_preference": {
                    "type": "string",
                    "enum": ["en", "sw", "sheng", "mixed"],
                    "description": "Preferred language code (optional)"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "phone_e164"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Get or create customer by phone number within tenant scope.
        
        Returns:
            ToolResponse with customer data including:
            - customer_id: UUID of the customer
            - phone_e164: Phone number
            - name: Customer name (if available)
            - language_preference: Preferred language
            - marketing_opt_in: Marketing consent status
            - consent_flags: Detailed consent flags
            - tags: Customer tags
            - created: Whether customer was newly created
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "phone_e164"])
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
        phone_e164 = kwargs["phone_e164"]
        name = kwargs.get("name")
        language_preference = kwargs.get("language_preference")
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Tenant, Customer
            from django.utils import timezone
            
            # Get tenant
            tenant = Tenant.objects.get(id=tenant_id, status__in=['active', 'trial'])
            
            # Get or create customer with composite key (tenant_id, phone_e164)
            customer, created = Customer.objects.get_or_create(
                tenant=tenant,
                phone_e164=phone_e164,
                defaults={
                    'name': name,
                    'language_preference': language_preference,
                    'first_interaction_at': timezone.now(),
                    'last_seen_at': timezone.now(),
                }
            )
            
            # Update last seen for existing customers
            if not created:
                customer.update_last_seen()
                
                # Update name if provided and not already set
                if name and not customer.name:
                    customer.name = name
                    customer.save(update_fields=['name'])
                
                # Update language preference if provided
                if language_preference and customer.language_preference != language_preference:
                    customer.language_preference = language_preference
                    customer.save(update_fields=['language_preference'])
            
            # Build response data
            data = {
                "customer_id": str(customer.id),
                "phone_e164": phone_e164,
                "name": customer.name,
                "language_preference": customer.language_preference,
                "marketing_opt_in": customer.marketing_opt_in,
                "consent_flags": customer.consent_flags,
                "tags": customer.tags,
                "created": created,
                "first_interaction_at": customer.first_interaction_at.isoformat() if customer.first_interaction_at else None,
                "last_seen_at": customer.last_seen_at.isoformat() if customer.last_seen_at else None,
            }
            
            self.log_tool_execution(
                "customer_get_or_create", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Exception as e:
            error_msg = f"Failed to get or create customer: {str(e)}"
            self.log_tool_execution(
                "customer_get_or_create", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="OPERATION_ERROR"
            )


class CustomerUpdatePreferencesTool(BaseTool):
    """
    Update customer preferences and consent flags.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - customer_id: UUID of the customer
    
    Optional parameters:
    - language_preference: Preferred language code
    - marketing_opt_in: Marketing consent (true/false)
    - consent_flags: Detailed consent flags object
    - tags: Customer tags array
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
                "language_preference": {
                    "type": "string",
                    "enum": ["en", "sw", "sheng", "mixed"],
                    "description": "Preferred language code"
                },
                "marketing_opt_in": {
                    "type": "boolean",
                    "description": "Marketing consent status"
                },
                "consent_flags": {
                    "type": "object",
                    "properties": {
                        "marketing": {"type": "boolean"},
                        "notifications": {"type": "boolean"},
                        "data_processing": {"type": "boolean"}
                    },
                    "description": "Detailed consent flags"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Customer tags for segmentation"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "customer_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Update customer preferences and consent flags.
        
        Returns:
            ToolResponse with updated customer data
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
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Customer
            
            # Get customer with tenant scoping
            customer = Customer.objects.get(
                id=customer_id,
                tenant_id=tenant_id
            )
            
            # Update fields if provided
            update_fields = []
            
            if "language_preference" in kwargs:
                customer.language_preference = kwargs["language_preference"]
                update_fields.append("language_preference")
            
            if "marketing_opt_in" in kwargs:
                customer.marketing_opt_in = kwargs["marketing_opt_in"]
                update_fields.append("marketing_opt_in")
            
            if "consent_flags" in kwargs:
                # Merge with existing consent flags
                existing_flags = customer.consent_flags or {}
                new_flags = kwargs["consent_flags"]
                customer.consent_flags = {**existing_flags, **new_flags}
                update_fields.append("consent_flags")
            
            if "tags" in kwargs:
                customer.tags = kwargs["tags"]
                update_fields.append("tags")
            
            # Save changes
            if update_fields:
                customer.save(update_fields=update_fields)
            
            # Build response data
            data = {
                "customer_id": str(customer.id),
                "language_preference": customer.language_preference,
                "marketing_opt_in": customer.marketing_opt_in,
                "consent_flags": customer.consent_flags,
                "tags": customer.tags,
                "updated_fields": update_fields
            }
            
            self.log_tool_execution(
                "customer_update_preferences", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Customer.DoesNotExist:
            error_msg = f"Customer {customer_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "customer_update_preferences", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="CUSTOMER_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to update customer preferences: {str(e)}"
            self.log_tool_execution(
                "customer_update_preferences", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="UPDATE_ERROR"
            )