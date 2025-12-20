"""
Tool contracts for LangGraph orchestration.

This module provides all 15 required tools with strict tenant isolation:
1. tenant_get_context - Fetch tenant configuration and bot persona
2. customer_get_or_create - Get or create customer by phone number
3. customer_update_preferences - Update customer preferences and consent
4. catalog_search - Search products with semantic search and filters
5. catalog_get_item - Get detailed product information by ID
6. order_create - Create new order with cart items
7. offers_get_applicable - Get applicable offers and discounts
8. order_apply_coupon - Apply coupon code to order
9. payment_get_methods - Get available payment methods
10. payment_get_c2b_instructions - Get M-Pesa C2B payment instructions
11. payment_initiate_stk_push - Initiate M-Pesa STK Push payment
12. payment_create_pesapal_checkout - Create Pesapal checkout session
13. order_get_status - Get order status and details
14. kb_retrieve - Retrieve from knowledge base using RAG
15. handoff_create_ticket - Create human handoff ticket
"""

from .base import BaseTool, ToolResponse, ToolRegistry
from .tenant_tools import TenantGetContextTool
from .customer_tools import CustomerGetOrCreateTool, CustomerUpdatePreferencesTool
from .catalog_tools import CatalogSearchTool, CatalogGetItemTool
from .order_tools import OrderCreateTool, OrderGetStatusTool
from .offers_tools import OffersGetApplicableTool, OrderApplyCouponTool
from .payment_tools import (
    PaymentGetMethodsTool,
    PaymentGetC2BInstructionsTool,
    PaymentInitiateStkPushTool,
    PaymentCreatePesapalCheckoutTool
)
from .knowledge_tools import KbRetrieveTool
from .handoff_tools import HandoffCreateTicketTool


# Register all tools
def register_all_tools():
    """Register all tools with the ToolRegistry."""
    
    # Tenant tools
    ToolRegistry.register("tenant_get_context", TenantGetContextTool())
    
    # Customer tools
    ToolRegistry.register("customer_get_or_create", CustomerGetOrCreateTool())
    ToolRegistry.register("customer_update_preferences", CustomerUpdatePreferencesTool())
    
    # Catalog tools
    ToolRegistry.register("catalog_search", CatalogSearchTool())
    ToolRegistry.register("catalog_get_item", CatalogGetItemTool())
    
    # Order tools
    ToolRegistry.register("order_create", OrderCreateTool())
    ToolRegistry.register("order_get_status", OrderGetStatusTool())
    
    # Offers tools
    ToolRegistry.register("offers_get_applicable", OffersGetApplicableTool())
    ToolRegistry.register("order_apply_coupon", OrderApplyCouponTool())
    
    # Payment tools
    ToolRegistry.register("payment_get_methods", PaymentGetMethodsTool())
    ToolRegistry.register("payment_get_c2b_instructions", PaymentGetC2BInstructionsTool())
    ToolRegistry.register("payment_initiate_stk_push", PaymentInitiateStkPushTool())
    ToolRegistry.register("payment_create_pesapal_checkout", PaymentCreatePesapalCheckoutTool())
    
    # Knowledge and support tools
    ToolRegistry.register("kb_retrieve", KbRetrieveTool())
    ToolRegistry.register("handoff_create_ticket", HandoffCreateTicketTool())


# Auto-register tools when module is imported
register_all_tools()


# Export all tools and utilities
__all__ = [
    'BaseTool',
    'ToolResponse', 
    'ToolRegistry',
    'TenantGetContextTool',
    'CustomerGetOrCreateTool',
    'CustomerUpdatePreferencesTool',
    'CatalogSearchTool',
    'CatalogGetItemTool',
    'OrderCreateTool',
    'OrderGetStatusTool',
    'OffersGetApplicableTool',
    'OrderApplyCouponTool',
    'PaymentGetMethodsTool',
    'PaymentGetC2BInstructionsTool',
    'PaymentInitiateStkPushTool',
    'PaymentCreatePesapalCheckoutTool',
    'KbRetrieveTool',
    'HandoffCreateTicketTool',
    'register_all_tools'
]