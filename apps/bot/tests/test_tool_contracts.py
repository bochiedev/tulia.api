"""
Comprehensive tests for tool contracts with tenant isolation.

Tests all 15 tool contracts to ensure:
1. Proper tenant isolation
2. Input validation
3. Error handling
4. Expected output formats
5. Security requirements
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from apps.bot.tools.registry import get_tool, execute_tool, get_tool_schemas
from apps.bot.tools.base import ToolResponse
from apps.tenants.models import Tenant, Customer


class ToolContractsTestCase(TestCase):
    """Base test case for tool contracts."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            whatsapp_number="+254712000000",
            status="active"
        )
        
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164="+254712345678",
            language_preference="en"
        )
        
        self.tenant_id = str(self.tenant.id)
        self.customer_id = str(self.customer.id)
        self.request_id = str(uuid4())
        self.conversation_id = str(uuid4())
    
    def get_base_params(self):
        """Get base parameters required by all tools."""
        return {
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "conversation_id": self.conversation_id
        }


class TestTenantTools(ToolContractsTestCase):
    """Test tenant context tools."""
    
    def test_tenant_get_context_success(self):
        """Test successful tenant context retrieval."""
        tool = get_tool("tenant_get_context")
        self.assertIsNotNone(tool)
        
        response = tool.execute(**self.get_base_params())
        
        self.assertTrue(response.success)
        self.assertIsNotNone(response.data)
        self.assertEqual(response.data["tenant_name"], "Test Tenant")
        self.assertIn("bot_name", response.data)
        self.assertIn("payments_enabled", response.data)
    
    def test_tenant_get_context_invalid_tenant(self):
        """Test tenant context with invalid tenant ID."""
        tool = get_tool("tenant_get_context")
        params = self.get_base_params()
        params["tenant_id"] = str(uuid4())  # Non-existent tenant
        
        response = tool.execute(**params)
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_TENANT")
    
    def test_tenant_get_context_missing_params(self):
        """Test tenant context with missing parameters."""
        tool = get_tool("tenant_get_context")
        
        response = tool.execute(tenant_id=self.tenant_id)  # Missing required params
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "MISSING_PARAMS")
    
    def test_tenant_get_context_invalid_uuid(self):
        """Test tenant context with invalid UUID format."""
        tool = get_tool("tenant_get_context")
        params = self.get_base_params()
        params["tenant_id"] = "invalid-uuid"
        
        response = tool.execute(**params)
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_UUID")


class TestCustomerTools(ToolContractsTestCase):
    """Test customer management tools."""
    
    def test_customer_get_or_create_existing(self):
        """Test getting existing customer."""
        tool = get_tool("customer_get_or_create")
        params = self.get_base_params()
        params["phone_e164"] = "+254712345678"
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertFalse(response.data["created"])
        self.assertEqual(response.data["phone_e164"], "+254712345678")
        self.assertEqual(response.data["customer_id"], self.customer_id)
    
    def test_customer_get_or_create_new(self):
        """Test creating new customer."""
        tool = get_tool("customer_get_or_create")
        params = self.get_base_params()
        params["phone_e164"] = "+254787654321"  # New phone number
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertTrue(response.data["created"])
        self.assertEqual(response.data["phone_e164"], "+254787654321")
        self.assertIsNotNone(response.data["customer_id"])
    
    def test_customer_update_preferences_success(self):
        """Test successful customer preference update."""
        tool = get_tool("customer_update_preferences")
        params = self.get_base_params()
        params.update({
            "customer_id": self.customer_id,
            "preferences": {
                "language_preference": "sw",
                "marketing_opt_in": True,
                "consent_flags": {
                    "marketing": True,
                    "analytics": False
                }
            }
        })
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertEqual(response.data["language_preference"], "sw")
        self.assertTrue(response.data["marketing_opt_in"])
        self.assertIn("changes", response.data)
    
    def test_customer_update_preferences_invalid_customer(self):
        """Test preference update with invalid customer."""
        tool = get_tool("customer_update_preferences")
        params = self.get_base_params()
        params.update({
            "customer_id": str(uuid4()),  # Non-existent customer
            "preferences": {"language_preference": "sw"}
        })
        
        response = tool.execute(**params)
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "CUSTOMER_NOT_FOUND")


class TestCatalogTools(ToolContractsTestCase):
    """Test catalog and product tools."""
    
    @patch('apps.catalog.models.Product.objects')
    def test_catalog_search_success(self, mock_products):
        """Test successful catalog search."""
        # Mock product data
        mock_product = Mock()
        mock_product.id = uuid4()
        mock_product.name = "Test Product"
        mock_product.description = "Test Description"
        mock_product.price = Decimal('100.00')
        mock_product.category = None
        mock_product.image_url = "http://example.com/image.jpg"
        mock_product.track_inventory = False
        mock_product.tags = ["test"]
        mock_product.variants.count.return_value = 0
        mock_product.variants.filter.return_value.first.return_value = None
        mock_product.variants.first.return_value = None
        
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.select_related.return_value = mock_queryset
        mock_queryset.prefetch_related.return_value = mock_queryset
        mock_queryset.count.return_value = 1
        mock_queryset.__getitem__.return_value = [mock_product]
        
        mock_products.filter.return_value = mock_queryset
        
        tool = get_tool("catalog_search")
        params = self.get_base_params()
        params.update({
            "query": "test product",
            "limit": 6
        })
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertIn("results", response.data)
        self.assertIn("total_matches_estimate", response.data)
    
    @patch('apps.catalog.models.Product.objects')
    def test_catalog_get_item_success(self, mock_products):
        """Test successful item retrieval."""
        # Mock product data
        mock_product = Mock()
        mock_product.id = uuid4()
        mock_product.name = "Test Product"
        mock_product.description = "Test Description"
        mock_product.price = Decimal('100.00')
        mock_product.category = None
        mock_product.image_url = "http://example.com/image.jpg"
        mock_product.track_inventory = False
        mock_product.variants.all.return_value = []
        mock_product.variants.filter.return_value.first.return_value = None
        mock_product.variants.first.return_value = None
        
        mock_queryset = Mock()
        mock_queryset.select_related.return_value = mock_queryset
        mock_queryset.prefetch_related.return_value = mock_queryset
        mock_queryset.get.return_value = mock_product
        
        mock_products.select_related.return_value = mock_queryset
        
        tool = get_tool("catalog_get_item")
        params = self.get_base_params()
        params["product_id"] = str(uuid4())
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertIn("product", response.data)
        self.assertIn("variants", response.data)


class TestOrderTools(ToolContractsTestCase):
    """Test order management tools."""
    
    @patch('apps.orders.models.Order.objects')
    @patch('apps.catalog.models.Product.objects')
    def test_order_create_success(self, mock_products, mock_orders):
        """Test successful order creation."""
        # Mock product
        mock_product = Mock()
        mock_product.id = uuid4()
        mock_product.name = "Test Product"
        mock_product.price = Decimal('100.00')
        mock_product.track_inventory = False
        
        mock_products.get.return_value = mock_product
        
        # Mock order creation
        mock_order = Mock()
        mock_order.id = uuid4()
        mock_order.order_number = "ORD-20241220-ABC123"
        mock_order.status = "draft"
        mock_order.subtotal = Decimal('100.00')
        mock_order.tax_amount = Decimal('16.00')
        mock_order.delivery_fee = Decimal('200.00')
        mock_order.total = Decimal('316.00')
        mock_order.currency = "KES"
        mock_order.created_at = timezone.now()
        
        mock_orders.create.return_value = mock_order
        
        tool = get_tool("order_create")
        params = self.get_base_params()
        params.update({
            "customer_id": self.customer_id,
            "items": [
                {
                    "product_id": str(mock_product.id),
                    "quantity": 1
                }
            ]
        })
        
        with patch('apps.orders.models.OrderItem.objects.create') as mock_item_create:
            mock_item = Mock()
            mock_item.id = uuid4()
            mock_item.quantity = 1
            mock_item.unit_price = Decimal('100.00')
            mock_item.total = Decimal('100.00')
            mock_item_create.return_value = mock_item
            
            response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertIn("order_id", response.data)
        self.assertIn("totals", response.data)


class TestPaymentTools(ToolContractsTestCase):
    """Test payment processing tools."""
    
    def test_payment_get_methods_success(self):
        """Test getting payment methods."""
        tool = get_tool("payment_get_methods")
        
        response = tool.execute(**self.get_base_params())
        
        self.assertTrue(response.success)
        self.assertIn("payment_methods", response.data)
        self.assertIn("default_currency", response.data)
    
    @patch('apps.orders.models.Order.objects')
    def test_payment_get_c2b_instructions_success(self, mock_orders):
        """Test C2B instructions generation."""
        # Mock order
        mock_order = Mock()
        mock_order.id = uuid4()
        mock_order.order_number = "ORD-20241220-ABC123"
        mock_order.total = Decimal('316.00')
        mock_order.currency = "KES"
        mock_order.metadata = {}
        mock_order.save = Mock()
        
        mock_orders.get.return_value = mock_order
        
        # Mock tenant settings
        with patch.object(self.tenant, 'settings') as mock_settings:
            mock_settings.mpesa_shortcode = "123456"
            
            tool = get_tool("payment_get_c2b_instructions")
            params = self.get_base_params()
            params["order_id"] = str(mock_order.id)
            
            response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertIn("instructions", response.data)
        self.assertIn("payment_reference", response.data)


class TestKnowledgeTools(ToolContractsTestCase):
    """Test knowledge base tools."""
    
    @patch('apps.bot.services.tenant_document_ingestion_service.TenantDocumentIngestionService')
    def test_kb_retrieve_success(self, mock_document_service_class):
        """Test knowledge base retrieval."""
        # Mock the document service
        mock_document_service = Mock()
        mock_document_service.search_documents.return_value = [
            {
                'chunk_id': 'chunk_1',
                'document_id': str(uuid4()),
                'document_title': 'Test Document',
                'document_type': 'faq',
                'content': 'This is a test snippet',
                'chunk_index': 0,
                'score': 0.8,
                'metadata': {},
                'page_number': None,
                'section_title': None,
            }
        ]
        mock_document_service_class.create_for_tenant.return_value = mock_document_service
        
        tool = get_tool("kb_retrieve")
        params = self.get_base_params()
        params["query"] = "test question"
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertIn("snippets", response.data)
        self.assertIn("sources", response.data)
        self.assertEqual(len(response.data["snippets"]), 1)
        self.assertEqual(response.data["snippets"][0]["text"], "This is a test snippet")
        self.assertEqual(response.data["search_method"], "vector_semantic")


class TestHandoffTools(ToolContractsTestCase):
    """Test human handoff tools."""
    
    def test_handoff_create_ticket_success(self):
        """Test handoff ticket creation."""
        tool = get_tool("handoff_create_ticket")
        params = self.get_base_params()
        params.update({
            "customer_id": self.customer_id,
            "reason": "explicit_request",
            "category": "general_inquiry",
            "context": {
                "summary": "Customer requested human agent",
                "current_journey": "sales",
                "current_step": "product_selection"
            }
        })
        
        response = tool.execute(**params)
        
        self.assertTrue(response.success)
        self.assertIn("ticket_id", response.data)
        self.assertIn("ticket_number", response.data)
        self.assertIn("estimated_response_time", response.data)


class TestToolRegistry(TestCase):
    """Test tool registry functionality."""
    
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
    
    def test_execute_tool_function(self):
        """Test the execute_tool helper function."""
        # Test successful execution
        result = execute_tool("tenant_get_context", 
                            tenant_id="invalid-uuid",
                            request_id=str(uuid4()),
                            conversation_id=str(uuid4()))
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        
        # Test non-existent tool
        result = execute_tool("non_existent_tool")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "TOOL_NOT_FOUND")


class TestTenantIsolation(ToolContractsTestCase):
    """Test tenant isolation across all tools."""
    
    def setUp(self):
        """Set up test data with multiple tenants."""
        super().setUp()
        
        # Create second tenant
        self.tenant2 = Tenant.objects.create(
            name="Second Tenant",
            slug="second-tenant",
            whatsapp_number="+254713000000",
            status="active"
        )
        
        self.customer2 = Customer.objects.create(
            tenant=self.tenant2,
            phone_e164="+254787654321",
            language_preference="en"
        )
    
    def test_customer_tools_tenant_isolation(self):
        """Test that customer tools enforce tenant isolation."""
        tool = get_tool("customer_get_or_create")
        
        # Try to access customer from different tenant
        params = {
            "tenant_id": str(self.tenant2.id),  # Different tenant
            "request_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "phone_e164": self.customer.phone_e164  # Customer from tenant1
        }
        
        response = tool.execute(**params)
        
        # Should create new customer, not return existing one from different tenant
        self.assertTrue(response.success)
        self.assertTrue(response.data["created"])  # New customer created
        self.assertNotEqual(response.data["customer_id"], self.customer_id)
    
    def test_preference_update_tenant_isolation(self):
        """Test that preference updates enforce tenant isolation."""
        tool = get_tool("customer_update_preferences")
        
        # Try to update customer from different tenant
        params = {
            "tenant_id": str(self.tenant2.id),  # Different tenant
            "request_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "customer_id": self.customer_id,  # Customer from tenant1
            "preferences": {"language_preference": "sw"}
        }
        
        response = tool.execute(**params)
        
        # Should fail due to tenant isolation
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "CUSTOMER_NOT_FOUND")


class TestInputValidation(TestCase):
    """Test input validation across all tools."""
    
    def test_uuid_validation(self):
        """Test UUID validation for all tools."""
        from apps.bot.tools.base import validate_uuid
        
        # Valid UUID
        self.assertIsNone(validate_uuid(str(uuid4()), "test_field"))
        
        # Invalid UUIDs
        self.assertIsNotNone(validate_uuid("invalid-uuid", "test_field"))
        self.assertIsNotNone(validate_uuid("", "test_field"))
        self.assertIsNotNone(validate_uuid(123, "test_field"))
    
    def test_required_params_validation(self):
        """Test required parameter validation."""
        from apps.bot.tools.base import validate_required_params
        
        params = {"param1": "value1", "param2": "value2"}
        required = ["param1", "param2"]
        
        # All required params present
        self.assertIsNone(validate_required_params(params, required))
        
        # Missing required param
        error = validate_required_params(params, ["param1", "param3"])
        self.assertIsNotNone(error)
        self.assertIn("param3", error)
        
        # None value treated as missing
        params["param2"] = None
        error = validate_required_params(params, required)
        self.assertIsNotNone(error)
        self.assertIn("param2", error)