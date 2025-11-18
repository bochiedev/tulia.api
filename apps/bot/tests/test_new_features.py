"""
Tests for new AI agent features (Tasks 20-26).

Tests cover:
- Catalog browsing and pagination
- Reference context and positional resolution
- Product intelligence and AI recommendations
- Discovery and intelligent narrowing
- Multi-language support
- Progressive handoff
- Shortened purchase journey
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from apps.bot.models import (
    BrowseSession,
    ReferenceContext,
    ProductAnalysis,
    LanguagePreference,
    AgentConfiguration
)
from apps.bot.services.catalog_browser_service import CatalogBrowserService
from apps.bot.services.reference_context_manager import ReferenceContextManager
from apps.bot.services.product_intelligence import ProductIntelligenceService
from apps.bot.services.discovery_service import DiscoveryService
from apps.bot.services.multi_language_processor import MultiLanguageProcessor
from apps.bot.services.progressive_handoff import ProgressiveHandoffService
from apps.bot.services.direct_action_handler import DirectActionHandler
from apps.messaging.models import Conversation, Message
from apps.catalog.models import Product
from apps.services.models import Service
from apps.tenants.models import Tenant, Customer


@pytest.mark.django_db
class TestCatalogBrowsing:
    """Test catalog browsing and pagination functionality."""
    
    def test_start_browse_session(self, tenant, conversation):
        """Test starting a new browse session."""
        browser = CatalogBrowserService()
        
        # Create test products
        products = []
        for i in range(15):
            products.append(Product.objects.create(
                tenant=tenant,
                title=f"Product {i+1}",
                price=Decimal("10.00"),
                is_active=True
            ))
        
        # Start browse session
        session = browser.start_browse_session(
            conversation=conversation,
            catalog_type='products',
            queryset=Product.objects.filter(tenant=tenant, is_active=True),
            items_per_page=5
        )
        
        assert session is not None
        assert session.catalog_type == 'products'
        assert session.current_page == 1
        assert session.items_per_page == 5
        assert session.total_items == 15
        assert session.is_active is True
    
    def test_get_page(self, tenant, conversation):
        """Test retrieving a specific page."""
        browser = CatalogBrowserService()
        
        # Create test products
        for i in range(15):
            Product.objects.create(
                tenant=tenant,
                title=f"Product {i+1}",
                price=Decimal("10.00"),
                is_active=True
            )
        
        # Start session
        session = browser.start_browse_session(
            conversation=conversation,
            catalog_type='products',
            queryset=Product.objects.filter(tenant=tenant, is_active=True),
            items_per_page=5
        )
        
        # Get page 2
        items, has_next, has_prev = browser.get_page(session, page=2)
        
        assert len(items) == 5
        assert has_next is True
        assert has_prev is True
        assert items[0].title == "Product 6"
    
    def test_pagination_navigation(self, tenant, conversation):
        """Test next/previous page navigation."""
        browser = CatalogBrowserService()
        
        # Create test products
        for i in range(15):
            Product.objects.create(
                tenant=tenant,
                title=f"Product {i+1}",
                price=Decimal("10.00"),
                is_active=True
            )
        
        # Start session
        session = browser.start_browse_session(
            conversation=conversation,
            catalog_type='products',
            queryset=Product.objects.filter(tenant=tenant, is_active=True),
            items_per_page=5
        )
        
        # Navigate to next page
        items, has_next, has_prev = browser.next_page(session)
        assert session.current_page == 2
        assert len(items) == 5
        
        # Navigate to previous page
        items, has_next, has_prev = browser.previous_page(session)
        assert session.current_page == 1
        assert len(items) == 5
    
    def test_session_expiration(self, tenant, conversation):
        """Test that browse sessions expire after timeout."""
        browser = CatalogBrowserService()
        
        # Create expired session
        session = BrowseSession.objects.create(
            tenant=tenant,
            conversation=conversation,
            catalog_type='products',
            current_page=1,
            items_per_page=5,
            total_items=15,
            is_active=True,
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        # Try to get page from expired session
        with pytest.raises(Exception):
            browser.get_page(session, page=1)


@pytest.mark.django_db
class TestReferenceResolution:
    """Test positional reference resolution."""
    
    def test_store_list_context(self, tenant, conversation):
        """Test storing list context."""
        manager = ReferenceContextManager()
        
        items = [
            {'id': '1', 'title': 'Product A', 'type': 'product'},
            {'id': '2', 'title': 'Product B', 'type': 'product'},
            {'id': '3', 'title': 'Product C', 'type': 'product'}
        ]
        
        context = manager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        assert context is not None
        assert context.list_type == 'products'
        assert len(context.items) == 3
    
    def test_resolve_numeric_reference(self, tenant, conversation):
        """Test resolving numeric references like '1', '2', '3'."""
        manager = ReferenceContextManager()
        
        items = [
            {'id': '1', 'title': 'Product A', 'type': 'product'},
            {'id': '2', 'title': 'Product B', 'type': 'product'},
            {'id': '3', 'title': 'Product C', 'type': 'product'}
        ]
        
        context = manager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        # Resolve "2"
        resolved = manager.resolve_reference(conversation, "2")
        assert resolved is not None
        assert resolved['title'] == 'Product B'
    
    def test_resolve_ordinal_reference(self, tenant, conversation):
        """Test resolving ordinal references like 'first', 'second', 'last'."""
        manager = ReferenceContextManager()
        
        items = [
            {'id': '1', 'title': 'Product A', 'type': 'product'},
            {'id': '2', 'title': 'Product B', 'type': 'product'},
            {'id': '3', 'title': 'Product C', 'type': 'product'}
        ]
        
        context = manager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        # Resolve "first"
        resolved = manager.resolve_reference(conversation, "the first one")
        assert resolved is not None
        assert resolved['title'] == 'Product A'
        
        # Resolve "last"
        resolved = manager.resolve_reference(conversation, "the last")
        assert resolved is not None
        assert resolved['title'] == 'Product C'
    
    def test_context_expiration(self, tenant, conversation):
        """Test that reference context expires after timeout."""
        manager = ReferenceContextManager()
        
        # Create expired context
        context = ReferenceContext.objects.create(
            tenant=tenant,
            conversation=conversation,
            list_type='products',
            items=[{'id': '1', 'title': 'Product A'}],
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        # Try to resolve reference from expired context
        resolved = manager.resolve_reference(conversation, "1")
        assert resolved is None


@pytest.mark.django_db
class TestProductIntelligence:
    """Test AI-powered product intelligence."""
    
    def test_analyze_product(self, tenant):
        """Test product analysis generation."""
        service = ProductIntelligenceService()
        
        product = Product.objects.create(
            tenant=tenant,
            title="Organic Face Cream",
            description="Natural moisturizing cream with aloe vera and vitamin E. Perfect for sensitive skin.",
            price=Decimal("25.00"),
            is_active=True
        )
        
        # Mock LLM response for testing
        analysis = service.analyze_product(product, use_cache=False)
        
        # Analysis should be created (even if mocked)
        assert analysis is not None
        assert analysis.product == product
    
    def test_match_need_to_products(self, tenant):
        """Test semantic matching of customer needs to products."""
        service = ProductIntelligenceService()
        
        # Create products
        Product.objects.create(
            tenant=tenant,
            title="Moisturizing Face Cream",
            description="Hydrating cream for dry skin",
            price=Decimal("20.00"),
            is_active=True
        )
        Product.objects.create(
            tenant=tenant,
            title="Anti-Aging Serum",
            description="Reduces wrinkles and fine lines",
            price=Decimal("35.00"),
            is_active=True
        )
        
        # Match customer need
        matches = service.match_need_to_products(
            tenant=tenant,
            customer_need="I need something for dry skin",
            limit=5
        )
        
        # Should return products (exact matching depends on LLM)
        assert isinstance(matches, list)


@pytest.mark.django_db
class TestDiscoveryService:
    """Test discovery and intelligent narrowing."""
    
    def test_should_ask_clarifying_questions(self, tenant):
        """Test detection of when clarification is needed."""
        service = DiscoveryService()
        
        # Create many products
        for i in range(20):
            Product.objects.create(
                tenant=tenant,
                title=f"Product {i+1}",
                price=Decimal("10.00"),
                is_active=True
            )
        
        # Should ask clarifying questions for large result set
        should_ask = service.should_ask_clarifying_questions(
            result_count=20,
            has_filters=False
        )
        
        assert should_ask is True
    
    def test_generate_clarifying_questions(self, tenant):
        """Test generation of clarifying questions."""
        service = DiscoveryService()
        
        questions = service.generate_clarifying_questions(
            customer_message="I need a face cream",
            result_count=15,
            tenant=tenant
        )
        
        # Should generate questions
        assert isinstance(questions, list)
        assert len(questions) > 0


@pytest.mark.django_db
class TestMultiLanguageSupport:
    """Test multi-language and code-switching support."""
    
    def test_detect_english(self):
        """Test English language detection."""
        processor = MultiLanguageProcessor()
        
        languages = processor.detect_languages("I want to buy a product")
        
        assert 'english' in languages
    
    def test_detect_swahili(self):
        """Test Swahili language detection."""
        processor = MultiLanguageProcessor()
        
        languages = processor.detect_languages("Nataka kununua bidhaa")
        
        assert 'swahili' in languages
    
    def test_detect_mixed_language(self):
        """Test mixed language detection."""
        processor = MultiLanguageProcessor()
        
        languages = processor.detect_languages("Nataka to buy hiyo product")
        
        # Should detect both languages
        assert len(languages) > 1
    
    def test_translate_common_phrases(self):
        """Test translation of common Swahili/Sheng phrases."""
        processor = MultiLanguageProcessor()
        
        # Test Swahili phrases
        assert processor.translate_phrase("nataka") == "I want"
        assert processor.translate_phrase("bei gani") == "what price"
        assert processor.translate_phrase("iko") == "is it available"
        
        # Test Sheng phrases
        assert processor.translate_phrase("sawa") == "okay"
        assert processor.translate_phrase("poa") == "cool"
    
    def test_normalize_message(self):
        """Test message normalization to English."""
        processor = MultiLanguageProcessor()
        
        normalized = processor.normalize_message("Nataka kununua product")
        
        # Should contain English translation
        assert "want" in normalized.lower() or "buy" in normalized.lower()


@pytest.mark.django_db
class TestProgressiveHandoff:
    """Test progressive handoff with clarification attempts."""
    
    def test_should_attempt_clarification(self, tenant, conversation):
        """Test that clarification is attempted before handoff."""
        service = ProgressiveHandoffService()
        
        # First low confidence - should clarify
        should_handoff, action = service.evaluate_handoff_need(
            conversation=conversation,
            confidence_score=0.5,
            clarification_count=0,
            max_clarifications=2
        )
        
        assert should_handoff is False
        assert action == 'clarify'
    
    def test_handoff_after_max_clarifications(self, tenant, conversation):
        """Test handoff after maximum clarification attempts."""
        service = ProgressiveHandoffService()
        
        # After 2 clarifications - should handoff
        should_handoff, action = service.evaluate_handoff_need(
            conversation=conversation,
            confidence_score=0.5,
            clarification_count=2,
            max_clarifications=2
        )
        
        assert should_handoff is True
        assert action == 'handoff'
    
    def test_immediate_handoff_on_explicit_request(self, tenant, conversation):
        """Test immediate handoff on explicit customer request."""
        service = ProgressiveHandoffService()
        
        # Create message with explicit request
        message = Message.objects.create(
            conversation=conversation,
            direction='in',
            text="I want to speak to a human agent"
        )
        
        should_handoff = service.detect_explicit_handoff_request(message.text)
        
        assert should_handoff is True


@pytest.mark.django_db
class TestDirectActions:
    """Test shortened purchase journey with direct actions."""
    
    def test_handle_buy_now_action(self, tenant, conversation, customer):
        """Test handling 'Buy Now' button click."""
        handler = DirectActionHandler()
        
        product = Product.objects.create(
            tenant=tenant,
            title="Test Product",
            price=Decimal("25.00"),
            is_active=True
        )
        
        # Handle buy now action
        result = handler.handle_product_action(
            action='buy_now',
            product=product,
            customer=customer,
            conversation=conversation
        )
        
        assert result['success'] is True
        assert 'next_step' in result
    
    def test_handle_book_now_action(self, tenant, conversation, customer):
        """Test handling 'Book Now' button click."""
        handler = DirectActionHandler()
        
        service = Service.objects.create(
            tenant=tenant,
            title="Test Service",
            base_price=Decimal("50.00"),
            duration_minutes=60,
            is_active=True
        )
        
        # Handle book now action
        result = handler.handle_service_action(
            action='book_now',
            service=service,
            customer=customer,
            conversation=conversation
        )
        
        assert result['success'] is True
        assert 'next_step' in result


@pytest.mark.django_db
class TestPromptEngineering:
    """Test updated prompt engineering with new features."""
    
    def test_system_prompt_includes_new_features(self):
        """Test that system prompt includes new feature instructions."""
        from apps.bot.services.prompt_templates import PromptTemplateManager, PromptScenario
        
        prompt = PromptTemplateManager.get_system_prompt(
            scenario=PromptScenario.GENERAL,
            include_language_handling=True,
            include_pagination=True,
            include_reference_resolution=True,
            include_clarifying_questions=True,
            include_product_intelligence=True,
            include_progressive_handoff=True
        )
        
        # Check for new feature keywords
        assert 'multi-language' in prompt.lower() or 'swahili' in prompt.lower()
        assert 'pagination' in prompt.lower() or 'browse' in prompt.lower()
        assert 'reference' in prompt.lower() or 'positional' in prompt.lower()
        assert 'clarifying' in prompt.lower()
        assert 'recommendation' in prompt.lower() or 'intelligence' in prompt.lower()
        assert 'handoff' in prompt.lower()
    
    def test_user_prompt_includes_new_context(self, tenant, conversation):
        """Test that user prompt includes new context types."""
        from apps.bot.services.prompt_templates import PromptTemplateManager
        
        # Create reference context
        ref_context = ReferenceContext.objects.create(
            tenant=tenant,
            conversation=conversation,
            list_type='products',
            items=[
                {'id': '1', 'title': 'Product A'},
                {'id': '2', 'title': 'Product B'}
            ],
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        # Create browse session
        browse_session = BrowseSession.objects.create(
            tenant=tenant,
            conversation=conversation,
            catalog_type='products',
            current_page=1,
            items_per_page=5,
            total_items=15,
            is_active=True,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Build prompt
        prompt = PromptTemplateManager.build_complete_user_prompt(
            current_message="Show me the first one",
            reference_context=ref_context,
            browse_session=browse_session
        )
        
        # Check for new context sections
        assert 'Recent List Context' in prompt or 'reference' in prompt.lower()
        assert 'Browse Session' in prompt or 'browsing' in prompt.lower()


# Fixtures
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
        channel='whatsapp',
        status='active'
    )
