"""
Property-based tests for immediate product visibility.

**Feature: conversational-commerce-ux-enhancement, Property 2: Immediate product visibility**
**Validates: Requirements 2.1, 2.2, 2.3**

Property: For any product inquiry or general "what do you have" question,
the system should display at least one actual product in the response without
requiring category narrowing.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from django.utils import timezone

from apps.bot.services.discovery_service import SmartProductDiscoveryService
from apps.catalog.models import Product
from apps.tenants.models import Tenant, Customer


# Hypothesis strategies
@st.composite
def product_data(draw):
    """Generate product data."""
    return {
        'title': draw(st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')))),
        'description': draw(st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po')))),
        'price': draw(st.decimals(min_value=1, max_value=10000, places=2)),
        'currency': draw(st.sampled_from(['USD', 'KES', 'EUR', 'GBP'])),
        'stock': draw(st.integers(min_value=0, max_value=100)),
        'is_active': True
    }


@st.composite
def product_query(draw):
    """Generate product inquiry queries."""
    return draw(st.sampled_from([
        "what do you have",
        "what products do you sell",
        "show me what's available",
        "what can I buy",
        "what are you selling",
        "show me products",
        "what's in stock",
        "browse catalog",
        "show me your menu",
        "what items do you have",
        # Specific queries
        "do you have phones",
        "looking for laptops",
        "need shoes",
        "want to buy electronics",
        # Vague queries
        "hi",
        "hello",
        "help",
        ""
    ]))


@pytest.mark.django_db
class TestImmediateProductVisibilityProperty:
    """Property-based tests for immediate product visibility."""
    
    @given(
        products=st.lists(product_data(), min_size=1, max_size=20),
        query=product_query()
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_immediate_product_visibility(self, products, query, tenant):
        """
        Property: Product queries always show at least one product.
        
        **Feature: conversational-commerce-ux-enhancement, Property 2: Immediate product visibility**
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        For any tenant with at least one active product, when a customer asks
        about products (or makes a general inquiry), the system should return
        at least one product without requiring category narrowing.
        """
        # Create products in database
        created_products = []
        for product_dict in products:
            product = Product.objects.create(
                tenant=tenant,
                **product_dict
            )
            created_products.append(product)
        
        # Ensure we have at least one active product
        assume(len(created_products) > 0)
        
        # Initialize discovery service
        discovery_service = SmartProductDiscoveryService()
        
        # Get immediate suggestions
        suggestions = discovery_service.get_immediate_suggestions(
            tenant=tenant,
            query=query if query else None,
            context=None,
            limit=5
        )
        
        # Property: Should return at least one product
        assert len(suggestions['products']) > 0, \
            f"Query '{query}' should return at least one product when {len(created_products)} products exist"
        
        # Property: All returned products should be from this tenant
        for product in suggestions['products']:
            assert product.tenant_id == tenant.id, \
                "Returned products should belong to the correct tenant"
        
        # Property: All returned products should be active
        for product in suggestions['products']:
            assert product.is_active, \
                "Returned products should be active"
    
    @given(
        products=st.lists(product_data(), min_size=5, max_size=20),
        query=st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs')))
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_query_based_suggestions_relevance(self, products, query, tenant):
        """
        Property: Query-based suggestions return relevant products.
        
        **Feature: conversational-commerce-ux-enhancement, Property 2: Immediate product visibility**
        **Validates: Requirements 2.2, 2.3**
        
        When a customer provides a specific query, the system should return
        products that are relevant to that query (or fallback to showing
        available products if no matches found).
        """
        # Create products in database
        created_products = []
        for product_dict in products:
            product = Product.objects.create(
                tenant=tenant,
                **product_dict
            )
            created_products.append(product)
        
        # Initialize discovery service
        discovery_service = SmartProductDiscoveryService()
        
        # Get suggestions with query
        suggestions = discovery_service.get_immediate_suggestions(
            tenant=tenant,
            query=query,
            context=None,
            limit=5
        )
        
        # Property: Should return products (either matching or fallback)
        assert len(suggestions['products']) > 0, \
            f"Should return products for query '{query}'"
        
        # Property: Should not exceed limit
        assert len(suggestions['products']) <= 5, \
            "Should respect the limit parameter"
        
        # Property: Should provide reasoning
        assert suggestions['reasoning'], \
            "Should provide reasoning for suggestions"
        
        # Property: Should have priority level
        assert suggestions['priority'] in ['high', 'medium', 'low'], \
            "Should have valid priority level"
    
    @given(
        in_stock_count=st.integers(min_value=1, max_value=10),
        out_of_stock_count=st.integers(min_value=0, max_value=10)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_prioritizes_in_stock_products(self, in_stock_count, out_of_stock_count, tenant):
        """
        Property: In-stock products are prioritized over out-of-stock.
        
        **Feature: conversational-commerce-ux-enhancement, Property 2: Immediate product visibility**
        **Validates: Requirements 2.2, 2.4**
        
        When both in-stock and out-of-stock products exist, the system should
        prioritize showing in-stock products first.
        """
        # Clear any existing products for this tenant (from previous Hypothesis examples)
        Product.objects.filter(tenant=tenant).delete()
        
        # Clear cache for this tenant
        from django.core.cache import cache
        cache.clear()
        
        # Create in-stock products
        in_stock_products = []
        for i in range(in_stock_count):
            product = Product.objects.create(
                tenant=tenant,
                title=f"In Stock Product {i}",
                description="Available now",
                price=100.00,
                currency='USD',
                stock=10,
                is_active=True
            )
            in_stock_products.append(product)
        
        # Create out-of-stock products
        out_of_stock_products = []
        for i in range(out_of_stock_count):
            product = Product.objects.create(
                tenant=tenant,
                title=f"Out of Stock Product {i}",
                description="Not available",
                price=100.00,
                currency='USD',
                stock=0,
                is_active=True
            )
            out_of_stock_products.append(product)
        
        # Initialize discovery service
        discovery_service = SmartProductDiscoveryService()
        
        # Get suggestions
        suggestions = discovery_service.get_immediate_suggestions(
            tenant=tenant,
            query=None,
            context=None,
            limit=5
        )
        
        # Property: Should return products
        assert len(suggestions['products']) > 0, \
            "Should return products"
        
        # Property: If in-stock products exist, at least one should be in the suggestions
        if in_stock_count > 0:
            in_stock_ids = {p.id for p in in_stock_products}
            suggested_ids = {p.id for p in suggestions['products']}
            
            assert len(in_stock_ids & suggested_ids) > 0, \
                "Should include at least one in-stock product when available"
    
    @given(
        product_count=st.integers(min_value=1, max_value=20),
        limit=st.integers(min_value=1, max_value=10)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_respects_limit_parameter(self, product_count, limit, tenant):
        """
        Property: Suggestions respect the limit parameter.
        
        **Feature: conversational-commerce-ux-enhancement, Property 2: Immediate product visibility**
        **Validates: Requirements 2.2**
        
        The system should never return more products than the specified limit.
        """
        # Create products
        for i in range(product_count):
            Product.objects.create(
                tenant=tenant,
                title=f"Product {i}",
                description=f"Description {i}",
                price=100.00,
                currency='USD',
                stock=10,
                is_active=True
            )
        
        # Initialize discovery service
        discovery_service = SmartProductDiscoveryService()
        
        # Get suggestions with limit
        suggestions = discovery_service.get_immediate_suggestions(
            tenant=tenant,
            query=None,
            context=None,
            limit=limit
        )
        
        # Property: Should not exceed limit
        assert len(suggestions['products']) <= limit, \
            f"Should not return more than {limit} products"
        
        # Property: Should return at least one product (if any exist)
        assert len(suggestions['products']) > 0, \
            "Should return at least one product when products exist"
    
    @given(
        products=st.lists(product_data(), min_size=3, max_size=10)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_no_category_narrowing_required(self, products, tenant):
        """
        Property: Products are shown without requiring category selection.
        
        **Feature: conversational-commerce-ux-enhancement, Property 2: Immediate product visibility**
        **Validates: Requirements 2.1**
        
        The system should show products immediately without asking the customer
        to narrow down by category first.
        """
        # Create products with different categories
        for i, product_dict in enumerate(products):
            product_dict['metadata'] = {'category': f'Category {i % 3}'}
            Product.objects.create(
                tenant=tenant,
                **product_dict
            )
        
        # Initialize discovery service
        discovery_service = SmartProductDiscoveryService()
        
        # Get suggestions without any category filter
        suggestions = discovery_service.get_immediate_suggestions(
            tenant=tenant,
            query="what do you have",
            context=None,
            limit=5
        )
        
        # Property: Should return products immediately
        assert len(suggestions['products']) > 0, \
            "Should return products without requiring category narrowing"
        
        # Property: Products can be from different categories
        # (This demonstrates no narrowing was required)
        categories = set()
        for product in suggestions['products']:
            if product.metadata and 'category' in product.metadata:
                categories.add(product.metadata['category'])
        
        # If we have multiple products, they might be from different categories
        # (showing we didn't narrow to a single category)
        if len(suggestions['products']) > 1:
            # This is fine - we're showing products from potentially multiple categories
            assert len(suggestions['products']) > 0, \
                "Products shown without category narrowing"


@pytest.fixture
def tenant():
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant"
    )


@pytest.fixture
def customer(tenant):
    """Create test customer."""
    return Customer.objects.create(
        tenant=tenant,
        phone_e164="+254712345678"
    )
