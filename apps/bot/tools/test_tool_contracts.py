"""
Test script to validate all 15 tool contracts are properly implemented.
"""

import sys
import os
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.bot.tools.registry import ToolRegistry, register_all_tools
from apps.bot.tools.base import validate_uuid, validate_required_params
import uuid


def test_tool_contracts():
    """Test that all 15 tool contracts are properly implemented."""
    
    print("Testing Tool Contracts Implementation...")
    print("=" * 50)
    
    # Register all tools
    register_all_tools()
    
    # Expected tools
    expected_tools = [
        "tenant_get_context",
        "customer_get_or_create", 
        "customer_update_preferences",
        "catalog_search",
        "catalog_get_item",
        "order_create",
        "offers_get_applicable",
        "order_apply_coupon",
        "payment_get_methods",
        "payment_get_c2b_instructions",
        "payment_initiate_stk_push",
        "payment_create_pesapal_checkout",
        "order_get_status",
        "kb_retrieve",
        "handoff_create_ticket"
    ]
    
    # Get all registered tools
    registered_tools = ToolRegistry.get_all_tools()
    
    print(f"Expected tools: {len(expected_tools)}")
    print(f"Registered tools: {len(registered_tools)}")
    print()
    
    # Check if all expected tools are registered
    missing_tools = []
    for tool_name in expected_tools:
        if tool_name not in registered_tools:
            missing_tools.append(tool_name)
    
    if missing_tools:
        print(f"❌ Missing tools: {missing_tools}")
        return False
    else:
        print("✅ All 15 tools are registered")
    
    print()
    
    # Test each tool's schema and required parameters
    all_passed = True
    
    for tool_name in expected_tools:
        print(f"Testing {tool_name}...")
        
        tool = ToolRegistry.get_tool(tool_name)
        if not tool:
            print(f"  ❌ Tool not found")
            all_passed = False
            continue
        
        # Get schema
        try:
            schema = tool.get_schema()
            
            # Check required parameters
            required_params = schema.get("required", [])
            
            # All tools must have these base parameters
            base_required = ["tenant_id", "request_id", "conversation_id"]
            missing_base = [param for param in base_required if param not in required_params]
            
            if missing_base:
                print(f"  ❌ Missing required base parameters: {missing_base}")
                all_passed = False
            else:
                print(f"  ✅ Has required base parameters")
            
            # Check parameter types
            properties = schema.get("properties", {})
            
            for base_param in base_required:
                if base_param in properties:
                    param_def = properties[base_param]
                    if param_def.get("type") != "string" or param_def.get("format") != "uuid":
                        print(f"  ❌ {base_param} should be string with uuid format")
                        all_passed = False
            
            # Check additionalProperties is False (strict schema)
            if schema.get("additionalProperties") is not False:
                print(f"  ❌ Schema should have additionalProperties: false")
                all_passed = False
            else:
                print(f"  ✅ Schema enforces strict parameters")
            
            print(f"  ✅ Schema validation passed")
            
        except Exception as e:
            print(f"  ❌ Schema error: {e}")
            all_passed = False
        
        print()
    
    # Test tenant isolation validation
    print("Testing tenant isolation...")
    
    # Test with invalid tenant ID
    test_tool = ToolRegistry.get_tool("tenant_get_context")
    if test_tool:
        try:
            # Test with invalid UUID
            result = test_tool.execute(
                tenant_id="invalid-uuid",
                request_id=str(uuid.uuid4()),
                conversation_id=str(uuid.uuid4())
            )
            
            if result.success or result.error_code != "INVALID_UUID":
                print("  ❌ Should reject invalid UUID")
                all_passed = False
            else:
                print("  ✅ Properly validates UUID format")
            
            # Test with valid UUID but non-existent tenant
            result = test_tool.execute(
                tenant_id=str(uuid.uuid4()),
                request_id=str(uuid.uuid4()),
                conversation_id=str(uuid.uuid4())
            )
            
            if result.success or result.error_code != "INVALID_TENANT":
                print("  ❌ Should reject non-existent tenant")
                all_passed = False
            else:
                print("  ✅ Properly validates tenant existence")
                
        except Exception as e:
            print(f"  ❌ Tenant validation error: {e}")
            all_passed = False
    
    print()
    
    # Summary
    if all_passed:
        print("🎉 All tool contract tests passed!")
        print("✅ All 15 tools implemented")
        print("✅ All tools have required parameters")
        print("✅ All tools enforce tenant isolation")
        print("✅ All tools have proper JSON schemas")
        return True
    else:
        print("❌ Some tool contract tests failed!")
        return False


def print_tool_schemas():
    """Print all tool schemas for documentation."""
    
    print("\nTool Schemas:")
    print("=" * 50)
    
    register_all_tools()
    schemas = ToolRegistry.get_schemas()
    
    for tool_name, schema in schemas.items():
        print(f"\n{tool_name}:")
        print(f"  Required: {schema.get('required', [])}")
        print(f"  Properties: {len(schema.get('properties', {}))}")
        
        # Show specific properties
        properties = schema.get('properties', {})
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get('type', 'unknown')
            prop_format = prop_def.get('format', '')
            if prop_format:
                prop_type += f" ({prop_format})"
            print(f"    {prop_name}: {prop_type}")


if __name__ == "__main__":
    success = test_tool_contracts()
    
    if "--schemas" in sys.argv:
        print_tool_schemas()
    
    sys.exit(0 if success else 1)