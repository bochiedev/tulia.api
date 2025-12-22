"""
Base classes and utilities for tool contracts with strict tenant isolation.

All tools must enforce tenant isolation and include required parameters:
- tenant_id: UUID for tenant scoping
- request_id: UUID for request tracing
- conversation_id: UUID for conversation context
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
from uuid import UUID
import asyncio
import logging

from apps.bot.services.error_handling import (
    ErrorHandlingService, ErrorContext, ComponentType, 
    with_error_handling, error_handling_service
)

logger = logging.getLogger(__name__)


@dataclass
class ToolRequest:
    """Base request structure for all tools."""
    tenant_id: str
    request_id: str
    conversation_id: str


@dataclass
class ToolResponse:
    """Base response structure for all tools."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class BaseTool(ABC):
    """
    Base class for all tool implementations.
    
    Enforces tenant isolation and provides common functionality with
    comprehensive error handling and graceful degradation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_service = error_handling_service
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this tool."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResponse:
        """Execute the tool with given parameters."""
        pass
    
    def execute_with_fallback(self, **kwargs) -> ToolResponse:
        """
        Execute tool with comprehensive error handling and fallback.
        
        This method wraps the execute method with error handling,
        retry logic, and fallback responses to ensure conversation continuity.
        """
        context = ErrorContext(
            tenant_id=kwargs.get('tenant_id', 'unknown'),
            conversation_id=kwargs.get('conversation_id', 'unknown'),
            request_id=kwargs.get('request_id', 'unknown'),
            component_type=ComponentType.TOOL_CALL,
            operation=self.__class__.__name__.replace('Tool', '').lower()
        )
        
        try:
            # Create fallback function
            def fallback():
                return self._get_fallback_response(context, kwargs)
            
            # Execute with error handling - use sync version since tools are sync
            return asyncio.run(self.error_service.execute_with_error_handling(
                lambda: self.execute(**kwargs),
                context,
                fallback
            ))
            
        except Exception as e:
            # Final fallback - return error response
            self.logger.error(
                f"Tool execution failed completely: {self.__class__.__name__}",
                extra={
                    'tenant_id': context.tenant_id,
                    'conversation_id': context.conversation_id,
                    'request_id': context.request_id,
                    'error': str(e)
                },
                exc_info=True
            )
            
            return ToolResponse(
                success=False,
                error="I'm experiencing technical difficulties. Let me connect you with support.",
                error_code="TOOL_EXECUTION_FAILED"
            )
    
    def _get_fallback_response(self, context: ErrorContext, kwargs: Dict[str, Any]) -> ToolResponse:
        """
        Get fallback response for this tool.
        
        Subclasses can override this to provide tool-specific fallbacks.
        """
        fallback_data = self.error_service.get_fallback_response(
            ComponentType.TOOL_CALL,
            context.operation,
            context
        )
        
        return ToolResponse(
            success=fallback_data["success"],
            data=fallback_data.get("data"),
            error=fallback_data.get("error"),
            error_code=fallback_data.get("error_code")
        )
    
    def validate_tenant_access(self, tenant_id: str) -> bool:
        """
        Validate that the tenant exists and is active.
        
        Args:
            tenant_id: The tenant ID to validate
            
        Returns:
            bool: True if tenant is valid and active
        """
        from apps.tenants.models import Tenant
        
        try:
            tenant = Tenant.objects.get(id=tenant_id, status__in=['active', 'trial'])
            return True
        except Tenant.DoesNotExist:
            self.logger.warning(f"Invalid or inactive tenant: {tenant_id}")
            return False
    
    def log_tool_execution(self, tool_name: str, tenant_id: str, request_id: str, 
                          conversation_id: str, success: bool, error: Optional[str] = None):
        """Log tool execution for observability."""
        log_data = {
            'tool_name': tool_name,
            'tenant_id': tenant_id,
            'request_id': request_id,
            'conversation_id': conversation_id,
            'success': success
        }
        
        if error:
            log_data['error'] = error
            self.logger.error(f"Tool execution failed: {log_data}")
        else:
            self.logger.info(f"Tool execution completed: {log_data}")


class ToolRegistry:
    """Registry for all available tools."""
    
    _tools: Dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, name: str, tool: BaseTool):
        """Register a tool with the given name."""
        cls._tools[name] = tool
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def get_all_tools(cls) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return cls._tools.copy()
    
    @classmethod
    def get_schemas(cls) -> Dict[str, Dict[str, Any]]:
        """Get schemas for all registered tools."""
        return {name: tool.get_schema() for name, tool in cls._tools.items()}


def validate_required_params(params: Dict[str, Any], required: list) -> Optional[str]:
    """
    Validate that all required parameters are present.
    
    Args:
        params: Parameters to validate
        required: List of required parameter names
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    missing = [param for param in required if param not in params or params[param] is None]
    if missing:
        return f"Missing required parameters: {', '.join(missing)}"
    return None


def validate_uuid(value: Any, field_name: str) -> Optional[str]:
    """
    Validate that a value is a valid UUID string.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(value, str):
        return f"{field_name} must be a string"
    
    try:
        UUID(value)
        return None
    except ValueError:
        return f"{field_name} must be a valid UUID"