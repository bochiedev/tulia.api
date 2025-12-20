"""
Tests for Sales Journey subgraph implementation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.sales_journey import (
    SalesNarrowQueryNode,
    CatalogPresentOptionsNode,
    ProductDisambiguateNode,
    SalesJourneySubgraph
)


@pytest.fixture
def sample_state():
    """Create a sample conversation state for testing."""
    return ConversationState(
        tenant_id="test-tenant-id",
        conversation_id="test-conversation-id",
        request_id="test-request-id",
        customer_id="test-customer-id",
        incoming_message="I'm looking for a laptop",
        bot_name="TestBot",
        turn_count=1
    )


@pytest.fixture
def sample_catalog_results():
    """Sample catalog search results."""
    return [
        {
            "product_id": "product-1",
            "name": "MacBook Pro 13",
            "price": 150000,
            "description": "Apple MacBook Pro 13-inch",
            "in_stock": True
        },
        {
            "product_id": "product-2", 
            "name": "Dell XPS 13",
            "price": 120000,
            "description": "Dell XPS 13 laptop",
            "in_stock": True
        }
    ]


class TestSalesNarrowQueryNode:
    """Test sales narrow query node."""
    
    @pytest.mark.asyncio
    async def test_search_decision_for_specific_query(self, sample_state):
        """Test that specific queries result in search action."""
        node = SalesNarrowQueryNode()
        
        # Mock LLM call to return search action
        with patch.object(node, '_call_llm', return_value={
            "action": "search",
            "search_query": "laptop",
            "search_filters": {},
            "reasoning": "Specific product mentioned"
        }):
            result_state = await node.execute(sample_state)
            
            assert result_state.last_catalog_query == "laptop"
            assert result_state.sales_step == "catalog_search"
    
    @pytest.mark.asyncio
    async def test_clarify_decision_for_vague_query(self, sample_state):
        """Test that vague queries result in clarification."""
        sample_state.incoming_message = "show me products"
        node = SalesNarrowQueryNode()
        
        # Mock LLM call to return clarify action
        with patch.object(node, '_call_llm', return_value={
            "action": "clarify",
            "clarification_question": "What type of product are you looking for?",
            "reasoning": "Query too vague"
        }):
            result_state = await node.execute(sample_state)
            
            assert "What type of product" in result_state.response_text
            assert result_state.sales_step == "awaiting_clarification"
    
    def test_heuristic_fallback_for_specific_terms(self, sample_state):
        """Test heuristic analysis for specific product terms."""
        node = SalesNarrowQueryNode()
        
        result = node._analyze_query_heuristic("I need a phone")
        
        assert result["action"] == "search"
        assert result["search_query"] == "I need a phone"
    
    def test_heuristic_fallback_for_vague_terms(self, sample_state):
        """Test heuristic analysis for vague terms."""
        node = SalesNarrowQueryNode()
        
        result = node._analyze_query_heuristic("show me something")
        
        assert result["action"] == "clarify"
        assert "What type of product" in result["clarification_question"]


class TestCatalogPresentOptionsNode:
    """Test catalog present options node."""
    
    @pytest.mark.asyncio
    async def test_format_search_results(self, sample_state, sample_catalog_results):
        """Test formatting of catalog search results."""
        sample_state.last_catalog_results = sample_catalog_results
        sample_state.catalog_total_matches_estimate = 2
        
        node = CatalogPresentOptionsNode()
        
        # Mock LLM call to return formatted presentation
        with patch.object(node, '_call_llm', return_value={
            "presentation_text": "Here are some laptops:\n1. MacBook Pro 13 - KES 150,000\n2. Dell XPS 13 - KES 120,000",
            "show_catalog_link": False,
            "selected_products": [
                {"product_id": "product-1", "position": 1, "name": "MacBook Pro 13", "price": 150000},
                {"product_id": "product-2", "position": 2, "name": "Dell XPS 13", "price": 120000}
            ],
            "total_shown": 2,
            "has_more_results": False
        }):
            result_state = await node.execute(sample_state)
            
            assert "MacBook Pro 13" in result_state.response_text
            assert "Dell XPS 13" in result_state.response_text
            assert result_state.sales_step == "awaiting_selection"
            assert len(result_state.presented_products) == 2
    
    def test_simple_formatting_fallback(self, sample_state, sample_catalog_results):
        """Test simple formatting fallback when LLM fails."""
        sample_state.last_catalog_results = sample_catalog_results
        
        node = CatalogPresentOptionsNode()
        
        result = node._format_results_simple(sample_state)
        
        assert result["total_shown"] == 2
        assert "MacBook Pro 13" in result["presentation_text"]
        assert "Dell XPS 13" in result["presentation_text"]
    
    def test_empty_results_handling(self, sample_state):
        """Test handling of empty search results."""
        sample_state.last_catalog_results = []
        
        node = CatalogPresentOptionsNode()
        
        result = node._format_results_simple(sample_state)
        
        assert result["total_shown"] == 0
        assert result["show_catalog_link"] == True
        assert "couldn't find any products" in result["presentation_text"]


class TestProductDisambiguateNode:
    """Test product disambiguate node."""
    
    @pytest.mark.asyncio
    async def test_proceed_with_complete_info(self, sample_state):
        """Test proceeding when all info is available."""
        sample_state.selected_product_details = {
            "product_id": "product-1",
            "name": "MacBook Pro 13",
            "price": 150000,
            "variants": []
        }
        sample_state.incoming_message = "I want 1"
        
        node = ProductDisambiguateNode()
        
        # Mock LLM call to return proceed action
        with patch.object(node, '_call_llm', return_value={
            "action": "proceed",
            "confirmed_product": {
                "product_id": "product-1",
                "name": "MacBook Pro 13",
                "price": 150000,
                "quantity": 1,
                "variant_selection": {}
            },
            "ready_for_order": True,
            "reasoning": "All info available"
        }):
            result_state = await node.execute(sample_state)
            
            assert result_state.sales_step == "ready_for_order"
            assert len(result_state.cart) == 1
            assert result_state.cart[0]["product_id"] == "product-1"
    
    def test_simple_disambiguation_with_variants(self, sample_state):
        """Test simple disambiguation when variants exist."""
        sample_state.selected_product_details = {
            "product_id": "product-1",
            "name": "MacBook Pro",
            "price": 150000,
            "variants": [
                {"name": "13-inch", "price": 150000},
                {"name": "16-inch", "price": 200000}
            ]
        }
        
        node = ProductDisambiguateNode()
        
        result = node._disambiguate_simple(sample_state)
        
        assert result["action"] == "gather_info"
        assert "Which option would you like" in result["question_to_ask"]
        assert "variant" in result["missing_info"]


class TestSalesJourneySubgraph:
    """Test complete sales journey subgraph."""
    
    @pytest.mark.asyncio
    async def test_journey_start_step(self, sample_state):
        """Test sales journey starting step."""
        journey = SalesJourneySubgraph()
        
        # Mock the narrow query step
        with patch.object(journey, '_step_narrow_query') as mock_narrow:
            mock_narrow.return_value = sample_state
            
            result_state = await journey.execute_sales_journey(sample_state)
            
            mock_narrow.assert_called_once_with(sample_state)
    
    @pytest.mark.asyncio
    async def test_catalog_search_step(self, sample_state):
        """Test catalog search step execution."""
        sample_state.sales_step = 'catalog_search'
        sample_state.last_catalog_query = "laptop"
        
        journey = SalesJourneySubgraph()
        
        # Mock tool execution
        mock_tool = MagicMock()
        mock_tool.execute.return_value = MagicMock(
            success=True,
            data={
                "products": [{"product_id": "1", "name": "Test Laptop", "price": 100000}],
                "total_matches_estimate": 1
            }
        )
        
        with patch('apps.bot.tools.registry.get_tool', return_value=mock_tool):
            with patch.object(journey, '_step_present_options') as mock_present:
                mock_present.return_value = sample_state
                
                result_state = await journey.execute_sales_journey(sample_state)
                
                mock_tool.execute.assert_called_once()
                mock_present.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_product_selection_handling(self, sample_state):
        """Test handling of product selection."""
        sample_state.sales_step = 'awaiting_selection'
        sample_state.incoming_message = "1"
        sample_state.presented_products = [
            {"product_id": "product-1", "position": 1, "name": "Test Product", "price": 100000}
        ]
        
        journey = SalesJourneySubgraph()
        
        with patch.object(journey, '_step_get_item_details') as mock_get_item:
            mock_get_item.return_value = sample_state
            
            result_state = await journey.execute_sales_journey(sample_state)
            
            assert result_state.selected_item_ids == ["product-1"]
            mock_get_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_state):
        """Test error handling in sales journey."""
        journey = SalesJourneySubgraph()
        
        # Mock an exception in narrow query
        with patch.object(journey, '_step_narrow_query', side_effect=Exception("Test error")):
            result_state = await journey.execute_sales_journey(sample_state)
            
            assert result_state.escalation_required == True
            assert "having trouble processing" in result_state.response_text


@pytest.mark.asyncio
async def test_sales_journey_node_integration(sample_state):
    """Test sales journey node integration with LangGraph."""
    from apps.bot.langgraph.sales_journey import execute_sales_journey_node
    
    # Convert state to dict
    state_dict = sample_state.to_dict()
    
    # Mock the sales journey execution
    with patch('apps.bot.langgraph.sales_journey.SalesJourneySubgraph') as mock_journey_class:
        mock_journey = MagicMock()
        mock_journey_class.return_value = mock_journey
        
        # Mock execute_sales_journey to return updated state (async mock)
        updated_state = sample_state
        updated_state.response_text = "Test response"
        mock_journey.execute_sales_journey = AsyncMock(return_value=updated_state)
        
        result_dict = await execute_sales_journey_node(state_dict)
        
        assert result_dict["response_text"] == "Test response"
        mock_journey.execute_sales_journey.assert_called_once()