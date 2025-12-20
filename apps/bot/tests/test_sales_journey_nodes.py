"""
Tests for Sales Journey LLM nodes.

This module tests the core LLM nodes for the sales journey:
- SalesNarrowQueryNode
- CatalogPresentOptionsNode  
- ProductDisambiguateNode
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from apps.bot.langgraph.sales_journey_nodes import (
    SalesNarrowQueryNode,
    CatalogPresentOptionsNode,
    ProductDisambiguateNode
)
from apps.bot.conversation_state import ConversationState


@pytest.fixture
def sample_state():
    """Create a sample conversation state for testing."""
    return ConversationState(
        tenant_id="123e4567-e89b-12d3-a456-426614174000",
        conversation_id="123e4567-e89b-12d3-a456-426614174001",
        request_id="123e4567-e89b-12d3-a456-426614174002",
        customer_id="123e4567-e89b-12d3-a456-426614174003",
        bot_name="TestBot",
        incoming_message="I'm looking for a phone"
    )


@pytest.fixture
def sample_products():
    """Create sample product data for testing."""
    return [
        {
            "product_id": "prod-1",
            "name": "iPhone 13 Pro",
            "price": 85000,
            "in_stock": True,
            "description": "Latest iPhone with excellent camera"
        },
        {
            "product_id": "prod-2", 
            "name": "Samsung Galaxy S22",
            "price": 65000,
            "in_stock": True,
            "description": "Great Android phone with amazing display"
        }
    ]


class TestSalesNarrowQueryNode:
    """Test SalesNarrowQueryNode functionality."""
    
    @pytest.mark.asyncio
    async def test_search_ready_intent(self, sample_state):
        """Test node identifies search-ready intent."""
        sample_state.incoming_message = "I want to buy an iPhone 13"
        
        node = SalesNarrowQueryNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "action": "search",
                "search_query": "iPhone 13",
                "category": "electronics",
                "min_price": None,
                "max_price": None,
                "reasoning": "Specific product mentioned"
            }
            
            result = await node.execute(sample_state)
            
            assert result.sales_step == "catalog_search"
            assert result.last_catalog_query == "iPhone 13"
            assert result.last_catalog_filters.get("category") == "electronics"
    
    @pytest.mark.asyncio
    async def test_clarification_needed(self, sample_state):
        """Test node requests clarification for vague queries."""
        sample_state.incoming_message = "I want something nice"
        
        node = SalesNarrowQueryNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "action": "clarify",
                "clarification_question": "What type of product are you looking for?",
                "reasoning": "Query too vague"
            }
            
            result = await node.execute(sample_state)
            
            assert result.sales_step == "awaiting_clarification"
            assert "What type of product" in result.response_text
    
    @pytest.mark.asyncio
    async def test_heuristic_fallback(self, sample_state):
        """Test heuristic analysis when LLM fails."""
        sample_state.incoming_message = "laptop"
        
        node = SalesNarrowQueryNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            
            result = await node.execute(sample_state)
            
            # Should use heuristic analysis
            assert result.sales_step == "catalog_search"
            assert "laptop" in result.last_catalog_query
    
    def test_heuristic_specific_product(self):
        """Test heuristic identifies specific products."""
        node = SalesNarrowQueryNode()
        
        result = node._analyze_query_heuristic("I want to buy an iPhone")
        
        assert result["action"] == "search"
        assert "iphone" in result["search_query"]
    
    def test_heuristic_vague_query(self):
        """Test heuristic requests clarification for vague queries."""
        node = SalesNarrowQueryNode()
        
        result = node._analyze_query_heuristic("hi")
        
        assert result["action"] == "clarify"
        assert "specific product" in result["clarification_question"]


class TestCatalogPresentOptionsNode:
    """Test CatalogPresentOptionsNode functionality."""
    
    @pytest.mark.asyncio
    async def test_present_products(self, sample_state, sample_products):
        """Test node presents products in WhatsApp format."""
        sample_state.last_catalog_results = sample_products
        sample_state.last_catalog_query = "phone"
        
        node = CatalogPresentOptionsNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = "Here are some great phones:\n\n1. iPhone 13 Pro - KES 85,000\n✅ In Stock"
            
            result = await node.execute(sample_state)
            
            assert result.sales_step == "awaiting_selection"
            assert "iPhone 13 Pro" in result.response_text
            assert "KES 85,000" in result.response_text
            assert len(result.selected_item_ids) == 2
    
    @pytest.mark.asyncio
    async def test_no_products_found(self, sample_state):
        """Test node handles empty search results."""
        sample_state.last_catalog_results = []
        sample_state.last_catalog_query = "nonexistent"
        
        node = CatalogPresentOptionsNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            
            result = await node.execute(sample_state)
            
            assert "couldn't find any products" in result.response_text
    
    @pytest.mark.asyncio
    async def test_template_fallback(self, sample_state, sample_products):
        """Test template-based presentation when LLM fails."""
        sample_state.last_catalog_results = sample_products
        sample_state.catalog_total_matches_estimate = 10
        
        node = CatalogPresentOptionsNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            
            result = await node.execute(sample_state)
            
            assert "Here are some great options" in result.response_text
            assert "1. **iPhone 13 Pro**" in result.response_text
            assert "2. **Samsung Galaxy S22**" in result.response_text
            assert "Reply with the number" in result.response_text
    
    def test_max_six_products_constraint(self, sample_state):
        """Test node respects WhatsApp 6-item limit."""
        # Create 8 products
        many_products = []
        for i in range(8):
            many_products.append({
                "product_id": f"prod-{i}",
                "name": f"Product {i}",
                "price": 1000 + i * 100,
                "in_stock": True
            })
        
        sample_state.last_catalog_results = many_products
        sample_state.catalog_total_matches_estimate = 8  # Set total matches
        
        node = CatalogPresentOptionsNode()
        presentation = node._generate_presentation_template(sample_state)
        
        # Should only show 6 products (numbered 1-6)
        assert "6. **Product 5**" in presentation
        assert "7. **Product 6**" not in presentation
        # Check for remaining items message (8 total - 6 shown = 2 remaining)
        assert "more items available" in presentation


class TestProductDisambiguateNode:
    """Test ProductDisambiguateNode functionality."""
    
    @pytest.mark.asyncio
    async def test_number_selection_ready(self, sample_state, sample_products):
        """Test node handles clear number selection."""
        sample_state.incoming_message = "I want number 1"
        sample_state.last_catalog_results = sample_products
        sample_state.selected_item_ids = ["prod-1", "prod-2"]
        
        node = ProductDisambiguateNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "action": "ready_for_order",
                "selected_product_id": "prod-1",
                "quantity": 1,
                "missing_info": [],
                "response_message": "Perfect! I'll add iPhone 13 Pro to your order.",
                "reasoning": "Clear selection"
            }
            
            result = await node.execute(sample_state)
            
            assert result.sales_step == "ready_for_order"
            assert len(result.cart) == 1
            assert result.cart[0]["product_id"] == "prod-1"
            assert result.cart[0]["quantity"] == 1
    
    @pytest.mark.asyncio
    async def test_need_variant_selection(self, sample_state, sample_products):
        """Test node requests variant selection for products with variants."""
        sample_state.incoming_message = "2"
        sample_state.last_catalog_results = sample_products
        sample_state.selected_item_ids = ["prod-1", "prod-2"]
        
        node = ProductDisambiguateNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "action": "need_more_info",
                "selected_product_id": "prod-2",
                "quantity": 1,
                "missing_info": ["variant_selection"],
                "response_message": "Which variant would you like?",
                "reasoning": "Product has variants"
            }
            
            result = await node.execute(sample_state)
            
            assert result.sales_step == "awaiting_info"
            assert "variant" in result.response_text
    
    @pytest.mark.asyncio
    async def test_provide_details_request(self, sample_state):
        """Test node handles requests for more product details."""
        sample_state.incoming_message = "tell me more about option 1"
        
        node = ProductDisambiguateNode()
        
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "action": "provide_details",
                "missing_info": ["product_details"],
                "response_message": "I'd be happy to provide more details!",
                "reasoning": "Customer requested details"
            }
            
            result = await node.execute(sample_state)
            
            assert result.sales_step == "providing_details"
            assert "more details" in result.response_text
    
    def test_heuristic_number_selection(self, sample_state, sample_products):
        """Test heuristic analysis identifies number selection."""
        sample_state.incoming_message = "I want 2"
        sample_state.last_catalog_results = sample_products
        sample_state.selected_item_ids = ["prod-1", "prod-2"]
        
        node = ProductDisambiguateNode()
        result = node._analyze_selection_heuristic(sample_state)
        
        assert result["action"] == "ready_for_order"
        assert result["selected_product_id"] == "prod-2"
        assert result["quantity"] == 1
    
    def test_heuristic_quantity_extraction(self, sample_state, sample_products):
        """Test heuristic extracts quantity from message."""
        sample_state.incoming_message = "I want 3 pieces of number 1"
        sample_state.last_catalog_results = sample_products
        sample_state.selected_item_ids = ["prod-1", "prod-2"]
        
        node = ProductDisambiguateNode()
        result = node._analyze_selection_heuristic(sample_state)
        
        assert result["action"] == "ready_for_order"
        assert result["quantity"] == 3
    
    def test_heuristic_details_request(self, sample_state):
        """Test heuristic identifies details requests."""
        sample_state.incoming_message = "tell me more details about this"
        
        node = ProductDisambiguateNode()
        result = node._analyze_selection_heuristic(sample_state)
        
        assert result["action"] == "provide_details"
        assert "details" in result["response_message"]
    
    def test_heuristic_unclear_selection(self, sample_state):
        """Test heuristic handles unclear selections."""
        sample_state.incoming_message = "maybe something else"
        
        node = ProductDisambiguateNode()
        result = node._analyze_selection_heuristic(sample_state)
        
        assert result["action"] == "need_more_info"
        assert "number of the product" in result["response_message"]


@pytest.mark.asyncio
async def test_node_error_handling(sample_state):
    """Test nodes handle errors gracefully."""
    node = SalesNarrowQueryNode()
    
    # Mock tenant lookup failure
    with patch('apps.tenants.models.Tenant.objects.aget') as mock_tenant:
        mock_tenant.side_effect = Exception("Database error")
        
        result = await node.execute(sample_state)
        
        # Should fall back to heuristic analysis
        assert result is not None
        assert hasattr(result, 'sales_step')


@pytest.mark.asyncio
async def test_llm_budget_check(sample_state):
    """Test nodes respect LLM budget limits."""
    node = CatalogPresentOptionsNode()
    
    with patch('apps.tenants.models.Tenant.objects.aget') as mock_tenant, \
         patch('apps.bot.services.llm_router.LLMRouter') as mock_router_class:
        
        mock_tenant.return_value = Mock()
        mock_router = Mock()
        mock_router._check_budget.return_value = False
        mock_router_class.return_value = mock_router
        
        result = await node.execute(sample_state)
        
        # Should use template fallback when budget exceeded
        assert result.response_text is not None