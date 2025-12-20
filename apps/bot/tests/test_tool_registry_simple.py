"""
Simple test for tool registry functionality.
"""

import pytest
from django.test import TestCase
from apps.bot.tools.registry import get_tool_schemas, get_tool, execute_tool


class TestToolRegistrySimple(TestCase):
    """Simple test for tool registry."""
    
    def test_all_tools_registered(self):
        """Test that all 15 tools are registered."""
        schemas = get_tool_schemas()
        
        expected_tools = [
            "tenant_get_context",
            "customer_get_or_create", 
            "customer_update_preferences",
            "catalog_search",
            "catalog_get_item",
            "order_create",
            "order_get_status",
            "offers_get_applicable",
            "order_apply_coupon",
            "payment_get_methods",
            "payment_get_c2b_instructions",
            "payment_initiate_stk_push",
            "payment_create_pesapal_checkout",
            "kb_retrieve",
            "handoff_create_ticket"
        ]
        
        self.assertEqual(len(schemas), 15)
        for tool_name in expected_tools:
            self.assertIn(tool_name, schemas)
    
    def test_tool_schemas_valid(self):
        """Test that all tool schemas are valid JSON schemas."""
        schemas = get_tool_schemas()
        
        for tool_name, schema in schemas.items():
            # Basic schema validation
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema)
            self.assertIn("required", schema)
            
            # All tools must require tenant_id, request_id, conversation_id
            required_fields = schema["required"]
            self.assertIn("tenant_id", required_fields)
            self.assertIn("request_id", required_fields)
            self.assertIn("conversation_id", required_fields)
    
    def test_get_tool_function(self):
        """Test getting individual tools."""
        # Test existing tool
        tool = get_tool("tenant_get_context")
        self.assertIsNotNone(tool)
        
        # Test non-existent tool
        tool = get_tool("non_existent_tool")
        self.assertIsNone(tool)
    
    def test_execute_tool_function(self):
        """Test the execute_tool helper function."""
        # Test non-existent tool
        result = execute_tool("non_existent_tool")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "TOOL_NOT_FOUND")
    
    def test_tool_validation_functions(self):
        """Test input validation functions."""
        from apps.bot.tools.base import validate_uuid, validate_required_params
        from uuid import uuid4
        
        # Test UUID validation
        self.assertIsNone(validate_uuid(str(uuid4()), "test_field"))
        self.assertIsNotNone(validate_uuid("invalid-uuid", "test_field"))
        
        # Test required params validation
        params = {"param1": "value1", "param2": "value2"}
        required = ["param1", "param2"]
        
        self.assertIsNone(validate_required_params(params, required))
        
        error = validate_required_params(params, ["param1", "param3"])
        self.assertIsNotNone(error)
        self.assertIn("param3", error)