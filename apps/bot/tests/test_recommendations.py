"""
Tests for AI agent recommendation functionality.

Tests the proactive suggestion and recommendation features including:
- Suggestion generation based on context
- Complementary product/service recommendations
- History-based personalization
- Rich message presentation of suggestions
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from unittest.mock import Mock, patch

from apps.bot.services.ai_agent_service import AIAgentService
from apps.bot.services.context_builder_service import AgentContext, CatalogContext, CustomerHistory
from apps.bot.models import AgentConfiguration
from apps.catalog.models import Product
from apps.services.models import Service
from apps.messaging.models import Message, Conversation
from apps.tenants.models import Tenant, Customer


@pytest.mark.django_db
class TestRecommendations:
    """Test suite for recommendation functionality."""
    
    @pytest.fixture
    def tenant(self):
        """Create test tenant."""
        return Tenant.objects.create(
            name="Test Business",
            slug="test-business"
        )
    
    @pytest.fixture
    def agent_config(self, tenant):
        """Create test agent configuration."""
        return AgentConfiguration.objects.create(
            tenant=tenant,
            agent_name="TestBot",
            enable_proactive_suggestions=True,
            enable_rich_messages=True
        )
    
    @pytest.fixture
    def products(self, tenant):
        """Create test products."""
        return [
            Product.objects.create(
                tenant=tenant,
                title="Blue Shirt",
                description="Comfortable cotton shirt",
                price=Decimal('29.99'),
                currency='USD',
                stock=10,
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Red Shirt",
                description="Stylish red shirt",
                price=Decimal('34.99'),
                currency='USD',
                stock=5,
                is_active=True
            ),
            Product.objects.create(
                tenant=tenant,
                title="Black Pants",
                description="Classic black pants",
                price=Decimal('49.99'),
                currency='USD',
                stock=0,  # Out of stock
                is_active=True
            )
        ]
    
    @pytest.fixture
    def services(self, tenant):
        """Create test services with availability windows."""
        from apps.services.models import AvailabilityWindow
        from datetime import time
        
        services = [
            Service.objects.create(
                tenant=tenant,
                title="Haircut",
                description="Professional haircut",
                base_price=Decimal('25.00'),
                currency='USD',
                is_active=True
            ),
            Service.objects.create(
                tenant=tenant,
                title="Hair Coloring",
                description="Professional hair coloring",
                base_price=Decimal('75.00'),
                currency='USD',
                is_active=True
            ),
            Service.objects.create(
                tenant=tenant,
                title="Beard Trim",
                description="Professional beard trim",
                base_price=Decimal('15.00'),
                currency='USD',
                is_active=True
            ),
            Service.objects.create(
                tenant=tenant,
                title="Massage",
                description="Relaxing massage",
                base_price=Decimal('60.00'),
                currency='USD',
                is_active=True
            )
        ]
        
        # Add availability windows for each service (Monday-Friday, 9am-5pm)
        for service in services:
            for weekday in range(5):  # Monday to Friday
                AvailabilityWindow.objects.create(
                    tenant=tenant,
                    service=service,
                    weekday=weekday,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    capacity=3,
                    timezone='UTC'
                )
        
        return services
    
    @pytest.fixture
    def ai_agent_service(self):
        """Create AI agent service instance."""
        return AIAgentService()
    
    def test_generate_suggestions_with_viewed_product(
        self,
        ai_agent_service,
        agent_config,
        tenant,
        products
    ):
        """Test suggestion generation when customer viewed a product."""
        # Create mock context with last product viewed
        context = Mock(spec=AgentContext)
        context.last_product_viewed = products[0]  # Blue Shirt
        context.last_service_viewed = None
        context.current_message = Mock(text="Tell me more about this shirt")
        context.customer_history = None
        context.catalog_context = Mock(products=[], services=[])
        
        # Generate suggestions
        suggestions = ai_agent_service.generate_suggestions(
            context=context,
            agent_config=agent_config,
            tenant=tenant
        )
        
        # Verify suggestions were generated
        assert suggestions is not None
        assert 'products' in suggestions
        assert 'services' in suggestions
        assert 'reasoning' in suggestions
        assert 'priority' in suggestions
        
        # Should have complementary products
        assert len(suggestions['products']) > 0
        
        # Should mention the viewed product in reasoning
        assert 'Blue Shirt' in suggestions['reasoning']
        
        # Priority should be high for viewed product context
        assert suggestions['priority'] == 'high'
    
    def test_generate_suggestions_with_viewed_service(
        self,
        ai_agent_service,
        agent_config,
        tenant,
        services
    ):
        """Test suggestion generation when customer viewed a service."""
        # Verify services were created
        assert len(services) >= 2, "Should have at least 2 services"
        
        # Create mock context with last service viewed
        context = Mock(spec=AgentContext)
        context.last_product_viewed = None
        context.last_service_viewed = services[0]  # Haircut
        context.current_message = Mock(text="What time slots are available?")
        context.customer_history = None
        context.catalog_context = Mock(products=[], services=[])
        
        # Generate suggestions
        suggestions = ai_agent_service.generate_suggestions(
            context=context,
            agent_config=agent_config,
            tenant=tenant
        )
        
        # Verify suggestions were generated
        assert suggestions is not None
        
        # Debug output
        print(f"Suggestions: {suggestions}")
        print(f"Services in DB: {Service.objects.filter(tenant=tenant).count()}")
        
        assert len(suggestions['services']) > 0, f"Expected services but got: {suggestions}"
        
        # Should mention the viewed service in reasoning
        assert 'Haircut' in suggestions['reasoning']
        
        # Priority should be high
        assert suggestions['priority'] == 'high'
    
    def test_filter_available_products(
        self,
        ai_agent_service,
        products
    ):
        """Test filtering products by stock availability."""
        # Filter products (should exclude out-of-stock)
        available = ai_agent_service._filter_available_products(
            products=products,
            limit=3
        )
        
        # Should only include in-stock products
        assert len(available) == 2
        assert all(p.is_in_stock for p in available)
        
        # Should not include Black Pants (out of stock)
        assert not any(p.title == "Black Pants" for p in available)
    
    def test_complementary_products(
        self,
        ai_agent_service,
        tenant,
        products
    ):
        """Test getting complementary products."""
        # Get complementary products for Blue Shirt
        complementary = ai_agent_service._get_complementary_products(
            product=products[0],
            tenant=tenant,
            limit=3
        )
        
        # Should return other products
        assert len(complementary) > 0
        
        # Should not include the original product
        assert products[0] not in complementary
    
    def test_suggestions_disabled(
        self,
        ai_agent_service,
        agent_config,
        tenant,
        products
    ):
        """Test that suggestions are not generated when disabled."""
        # Disable proactive suggestions
        agent_config.enable_proactive_suggestions = False
        agent_config.save()
        
        # Create mock context
        context = Mock(spec=AgentContext)
        context.last_product_viewed = products[0]
        context.last_service_viewed = None
        context.current_message = Mock(text="Tell me more")
        context.customer_history = None
        context.catalog_context = Mock(products=[], services=[])
        
        # Generate suggestions
        suggestions = ai_agent_service.generate_suggestions(
            context=context,
            agent_config=agent_config,
            tenant=tenant
        )
        
        # Should return empty suggestions
        assert len(suggestions['products']) == 0
        assert len(suggestions['services']) == 0
        assert suggestions['reasoning'] == ''
    
    def test_deduplicate_items(self, ai_agent_service, products):
        """Test deduplication of items."""
        # Create list with duplicates
        items_with_duplicates = [
            products[0],
            products[1],
            products[0],  # Duplicate
            products[2]
        ]
        
        # Deduplicate
        unique_items = ai_agent_service._deduplicate_items(items_with_duplicates)
        
        # Should have only unique items
        assert len(unique_items) == 3
        assert unique_items[0] == products[0]
        assert unique_items[1] == products[1]
        assert unique_items[2] == products[2]
    
    def test_build_suggestions_section(self, ai_agent_service, products, services):
        """Test building suggestions section for prompt."""
        suggestions = {
            'products': [products[0], products[1]],
            'services': [services[0]],
            'reasoning': 'Based on your interest in shirts',
            'priority': 'high'
        }
        
        # Build section
        section = ai_agent_service._build_suggestions_section(suggestions)
        
        # Verify section content
        assert '## Proactive Suggestions' in section
        assert 'Based on your interest in shirts' in section
        assert '### Suggested Products:' in section
        assert 'Blue Shirt' in section
        assert 'Red Shirt' in section
        assert '### Suggested Services:' in section
        assert 'Haircut' in section
        assert '$29.99' in section
        assert '$25.00' in section
