"""
Human handoff and escalation tools with tenant isolation.
"""

from typing import Any, Dict, List, Optional
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class HandoffCreateTicketTool(BaseTool):
    """
    Create human handoff with context.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - customer_id: UUID of the customer
    - reason: Escalation reason
    - priority: Ticket priority (low, medium, high, urgent)
    - category: Issue category
    - context: Conversation context and details
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
                "reason": {
                    "type": "string",
                    "enum": [
                        "explicit_request",
                        "payment_dispute", 
                        "missing_information",
                        "repeated_failures",
                        "sensitive_content",
                        "user_frustration",
                        "technical_issue",
                        "policy_question",
                        "complex_request",
                        "other"
                    ],
                    "description": "Escalation reason"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "default": "medium",
                    "description": "Ticket priority"
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "sales_support",
                        "technical_support", 
                        "payment_issue",
                        "order_inquiry",
                        "product_question",
                        "complaint",
                        "refund_request",
                        "general_inquiry"
                    ],
                    "description": "Issue category"
                },
                "context": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Brief summary of the issue"
                        },
                        "conversation_history": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "timestamp": {"type": "string"},
                                    "role": {"type": "string", "enum": ["user", "assistant"]},
                                    "message": {"type": "string"}
                                }
                            },
                            "description": "Recent conversation messages"
                        },
                        "current_journey": {
                            "type": "string",
                            "description": "Current conversation journey"
                        },
                        "current_step": {
                            "type": "string", 
                            "description": "Current step in the journey"
                        },
                        "order_id": {
                            "type": "string",
                            "description": "Related order ID (if applicable)"
                        },
                        "product_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Related product IDs (if applicable)"
                        },
                        "error_details": {
                            "type": "string",
                            "description": "Technical error details (if applicable)"
                        }
                    },
                    "required": ["summary"],
                    "description": "Conversation context and details"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "customer_id", "reason", "category", "context"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Create human handoff with context.
        
        Returns:
            ToolResponse with ticket details including:
            - ticket_id: UUID of created ticket
            - ticket_number: Human-readable ticket number
            - status: Ticket status
            - priority: Assigned priority
            - estimated_response_time: Expected response time
            - agent_info: Assigned agent information (if available)
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "customer_id", "reason", "category", "context"])
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
        reason = kwargs["reason"]
        priority = kwargs.get("priority", "medium")
        category = kwargs["category"]
        context = kwargs["context"]
        
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
            import uuid
            
            # Validate customer belongs to tenant
            try:
                customer = Customer.objects.get(id=customer_id, tenant_id=tenant_id)
            except Customer.DoesNotExist:
                return ToolResponse(
                    success=False,
                    error="Customer not found or access denied",
                    error_code="CUSTOMER_NOT_FOUND"
                )
            
            # Check if handoff/ticket models exist
            try:
                from apps.bot.models import HandoffTicket
                
                # Generate ticket number
                ticket_number = f"TKT-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
                
                # Determine priority based on reason if not specified
                if reason in ["payment_dispute", "sensitive_content", "user_frustration"]:
                    priority = "high"
                elif reason in ["explicit_request", "repeated_failures"]:
                    priority = "medium"
                
                # Calculate estimated response time based on priority
                response_times = {
                    "urgent": "15 minutes",
                    "high": "1 hour", 
                    "medium": "4 hours",
                    "low": "24 hours"
                }
                
                # Calculate estimated response time based on priority
                response_times = {
                    "urgent": "15 minutes",
                    "high": "1 hour", 
                    "medium": "4 hours",
                    "low": "24 hours"
                }
                
                # Create handoff ticket
                ticket = HandoffTicket.objects.create(
                    tenant_id=tenant_id,
                    customer=customer,
                    ticket_number=ticket_number,
                    reason=reason,
                    priority=priority,
                    category=category,
                    status='open',
                    context=context,
                    metadata={
                        'request_id': request_id,
                        'conversation_id': conversation_id,
                        'created_via': 'whatsapp_bot',
                        'escalation_timestamp': timezone.now().isoformat()
                    }
                )
                
                # Try to assign to available agent (simplified logic)
                assigned_agent = None
                try:
                    from apps.rbac.models import TenantUser
                    from apps.rbac.services import RBACService
                    
                    # Find users with handoff:perform scope
                    potential_agents = TenantUser.objects.filter(
                        tenant_id=tenant_id,
                        is_active=True
                    )
                    
                    for tenant_user in potential_agents:
                        if RBACService.has_scope(tenant_user, 'handoff:perform'):
                            assigned_agent = {
                                "agent_id": str(tenant_user.user.id),
                                "name": tenant_user.user.get_full_name() or tenant_user.user.username,
                                "email": tenant_user.user.email
                            }
                            ticket.assigned_to = tenant_user.user
                            ticket.save(update_fields=['assigned_to'])
                            break
                
                except ImportError:
                    # RBAC not available, skip agent assignment
                    pass
                
                # Create audit log entry
                from apps.core.models import AuditLog
                AuditLog.objects.create(
                    tenant_id=tenant_id,
                    user_id=None,  # System action
                    action="handoff_ticket_created",
                    resource_type="HandoffTicket",
                    resource_id=str(ticket.id),
                    changes={
                        "reason": reason,
                        "priority": priority,
                        "category": category,
                        "customer_phone": customer.phone_e164
                    },
                    request_id=request_id,
                    conversation_id=conversation_id
                )
                
                # Build response data
                data = {
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "category": ticket.category,
                    "reason": ticket.reason,
                    "estimated_response_time": response_times.get(priority, "4 hours"),
                    "created_at": ticket.created_at.isoformat(),
                    "customer": {
                        "customer_id": str(customer.id),
                        "phone_e164": customer.phone_e164
                    },
                    "assigned_agent": assigned_agent,
                    "context_preserved": True,
                    "next_steps": [
                        "A human agent will review your request",
                        f"Expected response time: {response_times.get(priority, '4 hours')}",
                        "You will be notified when an agent responds",
                        f"Reference number: {ticket.ticket_number}"
                    ]
                }
                
            except ImportError:
                # HandoffTicket model doesn't exist, create simplified ticket
                ticket_id = str(uuid.uuid4())
                ticket_number = f"TKT-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
                
                # Calculate estimated response time based on priority
                response_times = {
                    "urgent": "15 minutes",
                    "high": "1 hour", 
                    "medium": "4 hours",
                    "low": "24 hours"
                }
                
                # Store ticket info in customer metadata for now
                customer.metadata = customer.metadata or {}
                customer.metadata['pending_tickets'] = customer.metadata.get('pending_tickets', [])
                customer.metadata['pending_tickets'].append({
                    'ticket_id': ticket_id,
                    'ticket_number': ticket_number,
                    'reason': reason,
                    'priority': priority,
                    'category': category,
                    'context': context,
                    'created_at': timezone.now().isoformat(),
                    'status': 'open'
                })
                customer.save(update_fields=['metadata'])
                
                data = {
                    "ticket_id": ticket_id,
                    "ticket_number": ticket_number,
                    "status": "open",
                    "priority": priority,
                    "category": category,
                    "reason": reason,
                    "estimated_response_time": response_times.get(priority, "4 hours"),
                    "created_at": timezone.now().isoformat(),
                    "customer": {
                        "customer_id": str(customer.id),
                        "phone_e164": customer.phone_e164
                    },
                    "assigned_agent": None,
                    "context_preserved": True,
                    "next_steps": [
                        "Your request has been escalated to our support team",
                        f"Expected response time: {response_times.get(priority, '4 hours')}",
                        "Please keep this reference number for follow-up",
                        f"Reference number: {ticket_number}"
                    ]
                }
            
            self.log_tool_execution(
                "handoff_create_ticket", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Exception as e:
            error_msg = f"Failed to create handoff ticket: {str(e)}"
            self.log_tool_execution(
                "handoff_create_ticket", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False,
                error=error_msg,
                error_code="HANDOFF_CREATE_ERROR"
            )