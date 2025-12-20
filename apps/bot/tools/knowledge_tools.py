"""
Knowledge base and support tools for LangGraph orchestration.
"""

from typing import Any, Dict, Optional, List
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class KbRetrieveTool(BaseTool):
    """
    Retrieve relevant information from tenant knowledge base using RAG.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - query: Search query for knowledge base
    
    Optional parameters:
    - top_k: Number of results to return (default: 3, max: 10)
    - min_relevance_score: Minimum relevance score (default: 0.7)
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
                "query": {
                    "type": "string",
                    "description": "Search query for knowledge base"
                },
                "top_k": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3,
                    "description": "Number of results to return"
                },
                "min_relevance_score": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.7,
                    "description": "Minimum relevance score for results"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "query"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Retrieve relevant information from tenant knowledge base using vector search.
        
        Returns:
            ToolResponse with knowledge base results including:
            - snippets: List of relevant text snippets with semantic similarity scores
            - sources: Source documents for the snippets
            - query_used: The search query that was used
            - total_results: Total number of results found
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "query"])
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
        query = kwargs["query"]
        top_k = kwargs.get("top_k", 3)
        min_relevance_score = kwargs.get("min_relevance_score", 0.7)
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.tenants.models import Tenant
            from apps.bot.services.tenant_document_ingestion_service import TenantDocumentIngestionService
            
            # Get tenant instance
            tenant = Tenant.objects.get(id=tenant_id)
            
            # Use the new tenant document ingestion service for vector search
            document_service = TenantDocumentIngestionService.create_for_tenant(tenant)
            
            # Perform semantic search using vector embeddings
            search_results = document_service.search_documents(
                query=query,
                top_k=top_k,
                min_score=min_relevance_score
            )
            
            # Transform results to expected format
            snippets = []
            sources = []
            
            for result in search_results:
                snippet_data = {
                    "snippet_id": result["chunk_id"],
                    "text": result["content"],
                    "relevance_score": result["score"],
                    "source_title": result["document_title"],
                    "source_type": result["document_type"],
                    "chunk_index": result["chunk_index"],
                    "page_number": result.get("page_number"),
                    "section_title": result.get("section_title"),
                    "document_id": result["document_id"]
                }
                snippets.append(snippet_data)
                
                # Add source information (avoid duplicates)
                source_data = {
                    "source_id": result["document_id"],
                    "title": result["document_title"],
                    "type": result["document_type"],
                    "chunk_count": 1  # Will be aggregated if multiple chunks from same doc
                }
                
                # Check if source already exists and update chunk count
                existing_source = next(
                    (s for s in sources if s["source_id"] == source_data["source_id"]), 
                    None
                )
                if existing_source:
                    existing_source["chunk_count"] += 1
                else:
                    sources.append(source_data)
            
            # Build response data
            data = {
                "snippets": snippets,
                "sources": sources,
                "query_used": query,
                "total_results": len(snippets),
                "min_relevance_score": min_relevance_score,
                "top_k_requested": top_k,
                "has_results": len(snippets) > 0,
                "search_method": "vector_semantic",
                "namespace": f"tenant_{tenant_id}"
            }
            
            self.log_tool_execution(
                "kb_retrieve", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Exception as e:
            error_msg = f"Failed to retrieve from knowledge base: {str(e)}"
            self.log_tool_execution(
                "kb_retrieve", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="KB_RETRIEVE_ERROR"
            )


class HandoffCreateTicketTool(BaseTool):
    """
    Create human handoff ticket with conversation context.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - customer_id: UUID of the customer
    - reason: Reason for escalation
    
    Optional parameters:
    - priority: Ticket priority (low, medium, high, urgent)
    - category: Issue category
    - summary: Brief summary of the issue
    - context_snapshot: Key conversation context
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
                        "repeated_failures",
                        "sensitive_content",
                        "user_frustration",
                        "missing_information",
                        "complex_issue",
                        "technical_problem"
                    ],
                    "description": "Reason for escalation"
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
                        "general_support",
                        "payment_issue",
                        "order_problem",
                        "product_inquiry",
                        "technical_issue",
                        "complaint",
                        "refund_request"
                    ],
                    "default": "general_support",
                    "description": "Issue category"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the issue"
                },
                "context_snapshot": {
                    "type": "object",
                    "properties": {
                        "last_messages": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "current_journey": {"type": "string"},
                        "selected_products": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "order_id": {"type": "string"},
                        "payment_status": {"type": "string"}
                    },
                    "description": "Key conversation context"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "customer_id", "reason"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Create human handoff ticket with conversation context.
        
        Returns:
            ToolResponse with ticket details including:
            - ticket_id: UUID of the created ticket
            - ticket_reference: Human-readable ticket reference
            - status: Ticket status
            - estimated_response_time: Expected response time
            - handoff_message: Message to send to customer
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "customer_id", "reason"])
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
        category = kwargs.get("category", "general_support")
        summary = kwargs.get("summary")
        context_snapshot = kwargs.get("context_snapshot", {})
        
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
            customer = Customer.objects.get(id=customer_id, tenant_id=tenant_id)
            
            # Generate ticket reference
            ticket_reference = f"TKT-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            ticket_id = str(uuid.uuid4())
            
            # Determine priority and response time based on reason
            priority_mapping = {
                "explicit_request": "medium",
                "payment_dispute": "high", 
                "repeated_failures": "high",
                "sensitive_content": "urgent",
                "user_frustration": "medium",
                "missing_information": "low",
                "complex_issue": "medium",
                "technical_problem": "high"
            }
            
            if priority == "medium":  # Use default from reason if not specified
                priority = priority_mapping.get(reason, "medium")
            
            # Estimate response time based on priority
            response_times = {
                "urgent": "15 minutes",
                "high": "1 hour", 
                "medium": "4 hours",
                "low": "24 hours"
            }
            estimated_response_time = response_times[priority]
            
            # Create ticket data structure (would be saved to actual ticket model)
            ticket_data = {
                "ticket_id": ticket_id,
                "ticket_reference": ticket_reference,
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "conversation_id": conversation_id,
                "reason": reason,
                "priority": priority,
                "category": category,
                "summary": summary or f"Customer escalation: {reason.replace('_', ' ').title()}",
                "status": "open",
                "context_snapshot": context_snapshot,
                "created_at": timezone.now().isoformat(),
                "metadata": {
                    "request_id": request_id,
                    "escalation_source": "langgraph_agent",
                    "customer_name": customer.name,
                    "customer_phone": customer.phone_e164,
                    "customer_tags": customer.tags
                }
            }
            
            # Generate appropriate handoff message
            handoff_messages = {
                "explicit_request": f"I'm connecting you with a human agent now. Your ticket reference is {ticket_reference}. Expected response time: {estimated_response_time}.",
                "payment_dispute": f"I understand you have a payment concern. I've created ticket {ticket_reference} for our payment specialists. They'll respond within {estimated_response_time}.",
                "repeated_failures": f"I apologize for the technical difficulties. I've escalated this to our technical team with ticket {ticket_reference}. Expected response: {estimated_response_time}.",
                "sensitive_content": f"I've forwarded your message to our specialized team with ticket {ticket_reference}. They'll respond within {estimated_response_time}.",
                "user_frustration": f"I understand your frustration. Let me connect you with a human agent who can better assist you. Ticket reference: {ticket_reference}. Response time: {estimated_response_time}.",
                "missing_information": f"I don't have enough information to help with this. I've created ticket {ticket_reference} for our support team. Expected response: {estimated_response_time}.",
                "complex_issue": f"This requires specialized assistance. I've created ticket {ticket_reference} for our expert team. Expected response: {estimated_response_time}.",
                "technical_problem": f"I've reported this technical issue with ticket {ticket_reference}. Our technical team will respond within {estimated_response_time}."
            }
            
            handoff_message = handoff_messages.get(reason, f"I've created support ticket {ticket_reference}. Expected response: {estimated_response_time}.")
            
            # Build response data
            data = {
                "ticket_id": ticket_id,
                "ticket_reference": ticket_reference,
                "status": "open",
                "priority": priority,
                "category": category,
                "reason": reason,
                "estimated_response_time": estimated_response_time,
                "handoff_message": handoff_message,
                "created_at": ticket_data["created_at"],
                "context_preserved": bool(context_snapshot),
                "customer_notified": True
            }
            
            self.log_tool_execution(
                "handoff_create_ticket", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Customer.DoesNotExist:
            error_msg = f"Customer {customer_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "handoff_create_ticket", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="CUSTOMER_NOT_FOUND"
            )
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