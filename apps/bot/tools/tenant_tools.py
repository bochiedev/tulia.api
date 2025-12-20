"""
Tenant context and configuration tools.
"""

from typing import Any, Dict, Optional
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class TenantGetContextTool(BaseTool):
    """
    Fetch tenant configuration and bot persona.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
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
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Fetch tenant configuration and bot persona.
        
        Returns:
            ToolResponse with tenant context data including:
            - tenant_name: Display name
            - bot_name: Bot persona name
            - bot_intro: Introduction message
            - tone_style: Communication style
            - default_language: Default language code
            - allowed_languages: List of permitted languages
            - max_chattiness_level: Cost control level (0-3)
            - catalog_link_base: Web catalog URL
            - payments_enabled: Dict of enabled payment methods
            - compliance: Compliance settings
            - handoff: Escalation rules
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
            tenant = Tenant.objects.select_related('settings').get(id=tenant_id, status__in=['active', 'trial'])
            
            # Build response data
            data = {
                "tenant_name": tenant.name,
                "bot_name": getattr(tenant, 'bot_name', 'Assistant'),
                "bot_intro": getattr(tenant, 'bot_intro', f"Hi! I'm {getattr(tenant, 'bot_name', 'your assistant')} from {tenant.name}. How can I help you today?"),
                "tone_style": getattr(tenant, 'tone_style', 'friendly_concise'),
                "default_language": getattr(tenant, 'default_language', 'en'),
                "allowed_languages": getattr(tenant, 'allowed_languages', ['en', 'sw', 'sheng']),
                "max_chattiness_level": getattr(tenant, 'max_chattiness_level', 2),
                "catalog_link_base": getattr(tenant, 'catalog_link_base', None),
                "payments_enabled": {
                    "mpesa_stk": getattr(tenant.settings, 'mpesa_account_reference', None) is not None,
                    "mpesa_c2b": getattr(tenant.settings, 'mpesa_shortcode', None) is not None,
                    "pesapal": getattr(tenant.settings, 'pesapal_consumer_key', None) is not None
                } if hasattr(tenant, 'settings') and tenant.settings else {},
                "compliance": {
                    "require_consent": getattr(tenant, 'require_consent', True),
                    "data_retention_days": getattr(tenant, 'data_retention_days', 365)
                },
                "handoff": {
                    "enabled": getattr(tenant, 'handoff_enabled', True),
                    "escalation_triggers": getattr(tenant, 'escalation_triggers', [
                        "explicit_request", "payment_dispute", "repeated_failures", 
                        "sensitive_content", "user_frustration"
                    ])
                }
            }
            
            self.log_tool_execution(
                "tenant_get_context", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Exception as e:
            error_msg = f"Failed to fetch tenant context: {str(e)}"
            self.log_tool_execution(
                "tenant_get_context", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="FETCH_ERROR"
            )