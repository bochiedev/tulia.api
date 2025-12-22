"""
Tests for CatalogFallbackService.

Validates catalog fallback logic and URL generation with tenant scoping.
"""
import pytest
from apps.bot.services.catalog_fallback_service import CatalogFallbackService
from apps.bot.conversation_state import ConversationState


@pytest.fixture
def base_state():
    """Create base conversation state for testing."""
    return ConversationState(
        tenant_id="test-tenant-123",
        conversation_id="conv-123",
        request_id="req-123",
        customer_id="cust-123",
        catalog_link_base="https://catalog.example.com",
        catalog_total_matches_estimate=0,
        shortlist_rejections=0
    )


class TestShouldShowCatalogLink:
    """Test catalog link decision logic."""
    
    def test_large_catalog_with_vague_query_after_clarification(self, base_state):
        """Test condition 1: Large catalog + vague query after clarification."""
        base_state.catalog_total_matches_estimate = 50
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(
            state=base_state,
            message="something nice",
            clarifying_questions_asked=1
        )
        
        assert should_show is True
        assert "Large catalog with vague query" in reason
    
    def test_see_all_request(self, base_state):
        """Test condition 2: User requests to see all items."""
        test_messages = [
            "show me all items",
            "I want to see the full catalog",
            "list everything you have",
            "browse all products",
            "show all",
            "view catalog"
        ]
        
        for message in test_messages:
            should_show, reason = CatalogFallbackService.should_show_catalog_link(
                state=base_state,
                message=message
            )
            
            assert should_show is True, f"Failed for message: {message}"
            assert "User requested to see all items" in reason
    
    def test_repeated_shortlist_rejections(self, base_state):
        """Test condition 5: User rejects multiple shortlists."""
        base_state.shortlist_rejections = 2
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(
            state=base_state
        )
        
        assert should_show is True
        assert "rejected multiple shortlists" in reason


class TestCatalogUrlGeneration:
    """Test catalog URL generation with tenant scoping."""
    
    def test_basic_url_generation(self, base_state):
        """Test basic URL generation with tenant ID."""
        url = CatalogFallbackService.generate_catalog_url(base_state)
        
        assert url is not None
        assert "tenant_id=test-tenant-123" in url
        assert "conversation_id=conv-123" in url
        assert "return_context=whatsapp" in url
    
    def test_url_with_product_id(self, base_state):
        """Test URL generation with product deep-linking."""
        url = CatalogFallbackService.generate_catalog_url(
            base_state,
            selected_product_id="prod-456"
        )
        
        assert "product_id=prod-456" in url
        assert "tenant_id=test-tenant-123" in url
    
    def test_tenant_isolation_in_url(self, base_state):
        """Test that tenant_id is always included for isolation."""
        # Test with different tenant
        base_state.tenant_id = "different-tenant-789"
        
        url = CatalogFallbackService.generate_catalog_url(base_state)
        
        assert "tenant_id=different-tenant-789" in url
        assert "test-tenant-123" not in url


class TestTenantIsolation:
    """Test tenant isolation in catalog fallback service."""
    
    def test_different_tenants_different_urls(self):
        """Test that different tenants get different URLs."""
        state1 = ConversationState(
            tenant_id="tenant-1",
            conversation_id="conv-1",
            request_id="req-1",
            catalog_link_base="https://catalog.example.com"
        )
        
        state2 = ConversationState(
            tenant_id="tenant-2",
            conversation_id="conv-2",
            request_id="req-2",
            catalog_link_base="https://catalog.example.com"
        )
        
        url1 = CatalogFallbackService.generate_catalog_url(state1)
        url2 = CatalogFallbackService.generate_catalog_url(state2)
        
        assert "tenant_id=tenant-1" in url1
        assert "tenant_id=tenant-2" in url2
        assert url1 != url2