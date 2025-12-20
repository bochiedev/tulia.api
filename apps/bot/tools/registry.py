"""
Tool registry for LangGraph orchestration.

This module registers all available tools and provides access to their schemas and implementations.
"""

from apps.bot.tools.base import ToolRegistry
from apps.bot.tools.tenant_tools import TenantGetContextTool
from apps.bot.tools.customer_tools import CustomerGetOrCreateTool, CustomerUpdatePreferencesTool
from apps.bot.tools.catalog_tools import CatalogSearchTool, CatalogGetItemTool
from apps.bot.tools.order_tools import OrderCreateTool, OrderGetStatusTool
from apps.bot.tools.offers_tools import OffersGetApplicableTool, OrderApplyCouponTool
from apps.bot.tools.payment_tools import (
    PaymentGetMethodsTool,
    PaymentGetC2BInstructionsTool,
    PaymentInitiateStkPushTool,
    PaymentCreatePesapalCheckoutTool
)
from apps.bot.tools.knowledge_tools import KbRetrieveTool
from apps.bot.tools.handoff_tools import HandoffCreateTicketTool


def register_all_tools():
    """Register all available tools with the registry."""
    
    # Tenant context tools
    ToolRegistry.register("tenant_get_context", TenantGetContextTool())
    
    # Customer management tools
    ToolRegistry.register("customer_get_or_create", CustomerGetOrCreateTool())
    ToolRegistry.register("customer_update_preferences", CustomerUpdatePreferencesTool())
    
    # Catalog and product tools
    ToolRegistry.register("catalog_search", CatalogSearchTool())
    ToolRegistry.register("catalog_get_item", CatalogGetItemTool())
    
    # Order management tools
    ToolRegistry.register("order_create", OrderCreateTool())
    ToolRegistry.register("order_get_status", OrderGetStatusTool())
    
    # Offers and coupons tools
    ToolRegistry.register("offers_get_applicable", OffersGetApplicableTool())
    ToolRegistry.register("order_apply_coupon", OrderApplyCouponTool())
    
    # Payment processing tools
    ToolRegistry.register("payment_get_methods", PaymentGetMethodsTool())
    ToolRegistry.register("payment_get_c2b_instructions", PaymentGetC2BInstructionsTool())
    ToolRegistry.register("payment_initiate_stk_push", PaymentInitiateStkPushTool())
    ToolRegistry.register("payment_create_pesapal_checkout", PaymentCreatePesapalCheckoutTool())
    
    # Knowledge base tools
    ToolRegistry.register("kb_retrieve", KbRetrieveTool())
    
    # Human handoff tools
    ToolRegistry.register("handoff_create_ticket", HandoffCreateTicketTool())


def get_tool_schemas():
    """Get JSON schemas for all registered tools."""
    return ToolRegistry.get_schemas()


def get_tool(name: str):
    """Get a tool by name."""
    return ToolRegistry.get_tool(name)


def execute_tool(name: str, **kwargs):
    """Execute a tool by name with given parameters."""
    tool = ToolRegistry.get_tool(name)
    if not tool:
        return {
            "success": False,
            "error": f"Tool '{name}' not found",
            "error_code": "TOOL_NOT_FOUND"
        }
    
    try:
        response = tool.execute(**kwargs)
        return {
            "success": response.success,
            "data": response.data,
            "error": response.error,
            "error_code": response.error_code
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool execution failed: {str(e)}",
            "error_code": "TOOL_EXECUTION_ERROR"
        }


def list_available_tools():
    """List all available tools with their descriptions."""
    tools = ToolRegistry.get_all_tools()
    return {
        name: {
            "name": name,
            "schema": tool.get_schema(),
            "description": tool.get_schema().get("description", "No description available")
        }
        for name, tool in tools.items()
    }


# Auto-register tools when module is imported
register_all_tools()