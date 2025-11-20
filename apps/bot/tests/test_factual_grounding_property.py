"""
Property-based tests for factual grounding.

**Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

Property: For any bot response containing product information (price, availability, features),
all stated facts should be verifiable against the actual product data in the database.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from decimal import Decimal

from apps.bot.services.grounded_response_validator import GroundedResponseValidator
from apps.bot.services.context_builder_service import AgentContext, CatalogContext
from apps.catalog.models import Product
from apps.services.models import Service
from apps.tenants.models import Tenant, Customer
from apps.messaging.models import Conversation, Message


# Hypothesis strategies
@st.composite
def product_with_data(draw):
    """Generate a product with specific data."""
    # Use more realistic product names with ASCII letters only
    title_words = draw(st.lists(
        st.text(min_size=3, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'),
        min_size=1,
        max_size=3
    ))
    title = ' '.join(w for w in title_words if w).strip()
    
    # Ensure title is not empty
    if not title:
        title = "Product"
    
    price = draw(st.decimals(min_value=10, max_value=1000, places=2))
    stock = draw(st.integers(min_value=0, max_value=100))
    
    description_words = draw(st.lists(
        st.text(min_size=3, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ '),
        min_size=3,
        max_size=10
    ))
    description = ' '.join(w for w in description_words if w).strip()
    
    # Ensure description is not empty
    if not description:
        description = "A great product"
    
    return {
        'title': title,
        'price': price,
        'stock': stock,
        'description': description,
        'currency': 'USD',
        'is_active': True
    }


@st.composite
def response_with_correct_price(draw, product_data):
    """Generate a response that correctly states the product price."""
    templates = [
        f"The {product_data['title']} costs ${product_data['price']}",
        f"This product is priced at ${product_data['price']}",
        f"The price is ${product_data['price']}",
        f"{product_data['title']} is available for ${product_data['price']}",
    ]
    return draw(st.sampled_from(templates))


@st.composite
def response_with_incorrect_price(draw, product_data):
    """Generate a response with an incorrect price."""
    # Generate a different price
    wrong_price = draw(st.decimals(min_value=10, max_value=1000, places=2))
    assume(abs(wrong_price - product_data['price']) > Decimal('1.00'))
    
    templates = [
        f"The {product_data['title']} costs ${wrong_price}",
        f"This product is priced at ${wrong_price}",
        f"The price is ${wrong_price}",
    ]
    return draw(st.sampled_from(templates))


@st.composite
def response_with_correct_availability(draw, product_data):
    """Generate a response that correctly states availability."""
    is_available = product_data['stock'] > 0
    
    if is_available:
        templates = [
            f"The {product_data['title']} is available",
            f"We have {product_data['title']} in stock",
            f"{product_data['title']} is currently available",
        ]
    else:
        templates = [
            f"The {product_data['title']} is out of stock",
            f"{product_data['title']} is unavailable",
            f"We don't have {product_data['title']} available",
        ]
    
    return draw(st.sampled_from(templates))


@st.composite
def response_with_incorrect_availability(draw, product_data):
    """Generate a response with incorrect availability."""
    is_available = product_data['stock'] > 0
    
    # State the opposite of actual availability
    if is_available:
        templates = [
            f"The {product_data['title']} is out of stock",
            f"{product_data['title']} is unavailable",
        ]
    else:
        templates = [
            f"The {product_data['title']} is available",
            f"We have {product_data['title']} in stock",
        ]
    
    return draw(st.sampled_from(templates))


@st.composite
def response_with_feature_from_description(draw, product_data):
    """Generate a response mentioning a feature from the product description."""
    # Extract a phrase from the description
    words = product_data['description'].split()
    if len(words) < 3:
        feature = product_data['description']
    else:
        start = draw(st.integers(min_value=0, max_value=max(0, len(words) - 3)))
        feature = ' '.join(words[start:start+3])
    
    templates = [
        f"The {product_data['title']} has {feature}",
        f"{product_data['title']} features {feature}",
        f"This product includes {feature}",
    ]
    return draw(st.sampled_from(templates))


@st.composite
def response_with_fabricated_feature(draw, product_data):
    """Generate a response with a fabricated feature."""
    fake_features = [
        "wireless charging",
        "waterproof design",
        "lifetime warranty",
        "free shipping worldwide",
        "24k gold plating"
    ]
    feature = draw(st.sampled_from(fake_features))
    
    # Make sure this feature is NOT in the description
    assume(feature.lower() not in product_data['description'].lower())
    
    templates = [
        f"The {product_data['title']} has {feature}",
        f"{product_data['title']} features {feature}",
        f"This product includes {feature}",
    ]
    return draw(st.sampled_from(templates))


@pytest.mark.django_db
class TestFactualGroundingProperty:
    """Property-based tests for factual grounding validation."""
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_correct_price_validates(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses with correct prices should validate successfully.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3**
        
        For any product with a specific price, a response stating that correct
        price should pass validation.
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate response with correct price
        response = f"The {product.title} costs ${product.price}"
        
        # Validate
        validator = GroundedResponseValidator()
        is_valid, issues = validator.validate_response(response, context)
        
        # Property: Correct price should validate
        assert is_valid, f"Response with correct price should validate. Issues: {issues}"
        assert len(issues) == 0, "Should have no validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_incorrect_price_fails_validation(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses with incorrect prices should fail validation.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3, 8.5**
        
        For any product with a specific price, a response stating a different
        price should fail validation.
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate a wrong price (different by at least $5)
        wrong_price = product.price + Decimal('5.00')
        response = f"The {product.title} costs ${wrong_price}"
        
        # Validate
        validator = GroundedResponseValidator()
        is_valid, issues = validator.validate_response(response, context)
        
        # Property: Incorrect price should fail validation
        assert not is_valid, "Response with incorrect price should fail validation"
        assert len(issues) > 0, "Should have validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_correct_availability_validates(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses with correct availability should validate.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3**
        
        For any product with specific stock status, a response correctly
        stating that status should pass validation.
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate response with correct availability
        if product.stock > 0:
            response = f"The {product.title} is available"
        else:
            response = f"The {product.title} is out of stock"
        
        # Validate
        validator = GroundedResponseValidator()
        is_valid, issues = validator.validate_response(response, context)
        
        # Property: Correct availability should validate
        assert is_valid, f"Response with correct availability should validate. Issues: {issues}"
        assert len(issues) == 0, "Should have no validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_incorrect_availability_fails_validation(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses with incorrect availability should fail validation.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3, 8.5**
        
        For any product with specific stock status, a response stating the
        opposite status should fail validation.
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate response with INCORRECT availability (opposite of actual)
        if product.stock > 0:
            response = f"The {product.title} is out of stock"
        else:
            response = f"The {product.title} is available"
        
        # Validate
        validator = GroundedResponseValidator()
        is_valid, issues = validator.validate_response(response, context)
        
        # Property: Incorrect availability should fail validation
        assert not is_valid, "Response with incorrect availability should fail validation"
        assert len(issues) > 0, "Should have validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_feature_from_description_validates(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses mentioning features from product description should validate.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3**
        
        For any product with a description, a response mentioning text from
        that description should pass validation.
        """
        # Ensure description has meaningful content
        assume(len(product_data['description'].split()) >= 3)
        
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Extract a phrase from description
        words = product.description.split()
        phrase = ' '.join(words[:3])
        response = f"The {product.title} has {phrase}"
        
        # Validate
        validator = GroundedResponseValidator()
        is_valid, issues = validator.validate_response(response, context)
        
        # Property: Feature from description should validate
        assert is_valid, f"Response with feature from description should validate. Issues: {issues}"
        assert len(issues) == 0, "Should have no validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_fabricated_feature_fails_validation(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses with fabricated features should fail validation.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
        
        For any product, a response claiming features not in the product data
        should fail validation.
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate response with fabricated feature
        fake_feature = "wireless charging capability"
        assume(fake_feature.lower() not in product.description.lower())
        
        response = f"The {product.title} has {fake_feature}"
        
        # Validate
        validator = GroundedResponseValidator()
        is_valid, issues = validator.validate_response(response, context)
        
        # Property: Fabricated feature should fail validation
        assert not is_valid, "Response with fabricated feature should fail validation"
        assert len(issues) > 0, "Should have validation issues"
    
    @given(
        products_data=st.lists(product_with_data(), min_size=1, max_size=5)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_multiple_products_all_facts_must_verify(self, products_data, tenant, conversation, context_with_products):
        """
        Property: When multiple products are in context, all facts must verify.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3, 8.5**
        
        For any set of products in context, a response making claims about
        multiple products should only validate if ALL claims are correct.
        """
        # Create products
        products = [Product.objects.create(tenant=tenant, **pd) for pd in products_data]
        
        # Build context with these products
        context = context_with_products(products)
        
        # Generate response with correct info about first product
        # and incorrect info about second (if exists)
        if len(products) >= 2:
            response = (
                f"The {products[0].title} costs ${products[0].price}. "
                f"The {products[1].title} costs ${products[1].price + Decimal('10.00')}"
            )
            
            # Validate
            validator = GroundedResponseValidator()
            is_valid, issues = validator.validate_response(response, context)
            
            # Property: Should fail because one claim is incorrect
            assert not is_valid, "Response with mixed correct/incorrect claims should fail"
            assert len(issues) > 0, "Should have validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_no_factual_claims_always_validates(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Responses without factual claims should always validate.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.2**
        
        For any context, a response that makes no specific factual claims
        should pass validation (nothing to verify).
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate response with no factual claims
        responses = [
            "How can I help you today?",
            "I'd be happy to assist you with that.",
            "Let me check on that for you.",
            "Is there anything else I can help with?",
        ]
        
        validator = GroundedResponseValidator()
        
        for response in responses:
            is_valid, issues = validator.validate_response(response, context)
            
            # Property: No claims means nothing to verify, should validate
            assert is_valid, f"Response without factual claims should validate: '{response}'"
            assert len(issues) == 0, "Should have no validation issues"
    
    @given(
        product_data=product_with_data()
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_generic_existence_claims_validate(self, product_data, tenant, conversation, context_with_product):
        """
        Property: Generic existence claims validate when items exist.
        
        **Feature: conversational-commerce-ux-enhancement, Property 8: Factual grounding**
        **Validates: Requirements 8.1, 8.3**
        
        For any context with products, generic claims like "we have products"
        should validate.
        """
        # Create product
        product = Product.objects.create(tenant=tenant, **product_data)
        
        # Build context with this product
        context = context_with_product(product)
        
        # Generate generic existence claims
        responses = [
            "We have products available",
            "We offer various items",
            "We sell products",
        ]
        
        validator = GroundedResponseValidator()
        
        for response in responses:
            is_valid, issues = validator.validate_response(response, context)
            
            # Property: Generic claims should validate when products exist
            assert is_valid, f"Generic existence claim should validate: '{response}'. Issues: {issues}"


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


@pytest.fixture
def conversation(tenant, customer):
    """Create test conversation."""
    return Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        channel='whatsapp'
    )


@pytest.fixture
def context_with_product(conversation):
    """Factory to create AgentContext with a specific product."""
    def _create_context(product):
        from apps.messaging.models import Message
        
        # Create a dummy message
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text="Tell me about this product"
        )
        
        # Create catalog context with the product
        catalog_context = CatalogContext(
            products=[product],
            total_products=1
        )
        
        # Create agent context
        context = AgentContext(
            conversation=conversation,
            current_message=message,
            catalog_context=catalog_context,
            last_product_viewed=product
        )
        
        return context
    
    return _create_context


@pytest.fixture
def context_with_products(conversation):
    """Factory to create AgentContext with multiple products."""
    def _create_context(products):
        from apps.messaging.models import Message
        
        # Create a dummy message
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            message_type='customer_inbound',
            text="Show me products"
        )
        
        # Create catalog context with the products
        catalog_context = CatalogContext(
            products=products,
            total_products=len(products)
        )
        
        # Create agent context
        context = AgentContext(
            conversation=conversation,
            current_message=message,
            catalog_context=catalog_context
        )
        
        return context
    
    return _create_context
