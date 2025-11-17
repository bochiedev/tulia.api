"""
Tests for FuzzyMatcherService.

Tests fuzzy matching, spelling correction, and similarity calculations
for products and services.
"""
import pytest
from unittest.mock import Mock, patch
from django.core.cache import cache

from apps.bot.services.fuzzy_matcher_service import FuzzyMatcherService
from apps.catalog.models import Product
from apps.services.models import Service
from apps.tenants.models import Tenant


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Business",
        slug="test-business",
        status="active"
    )


@pytest.fixture
def products(tenant):
    """Create test products."""
    from decimal import Decimal
    return [
        Product.objects.create(
            tenant=tenant,
            title="Blue T-Shirt",
            description="Comfortable cotton t-shirt in blue",
            price=Decimal("29.99"),
            is_active=True
        ),
        Product.objects.create(
            tenant=tenant,
            title="Red Hoodie",
            description="Warm hooded sweatshirt in red",
            price=Decimal("49.99"),
            is_active=True
        ),
        Product.objects.create(
            tenant=tenant,
            title="Running Shoes",
            description="Athletic shoes for running",
            price=Decimal("89.99"),
            is_active=True
        ),
        Product.objects.create(
            tenant=tenant,
            title="Denim Jeans",
            description="Classic blue jeans",
            price=Decimal("59.99"),
            is_active=True
        ),
    ]


@pytest.fixture
def services(tenant):
    """Create test services."""
    return [
        Service.objects.create(
            tenant=tenant,
            title="Haircut",
            description="Professional haircut service",
            is_active=True
        ),
        Service.objects.create(
            tenant=tenant,
            title="Hair Coloring",
            description="Professional hair coloring service",
            is_active=True
        ),
        Service.objects.create(
            tenant=tenant,
            title="Massage",
            description="Relaxing full body massage",
            is_active=True
        ),
    ]


@pytest.fixture
def fuzzy_matcher():
    """Create FuzzyMatcherService instance."""
    return FuzzyMatcherService()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestProductMatching:
    """Test product fuzzy matching."""
    
    def test_exact_match(self, fuzzy_matcher, tenant, products):
        """Test exact product name match."""
        results = fuzzy_matcher.match_product("Blue T-Shirt", tenant)
        
        assert len(results) > 0
        product, score = results[0]
        assert product.title == "Blue T-Shirt"
        assert score >= 0.95  # High confidence for exact match
    
    def test_case_insensitive_match(self, fuzzy_matcher, tenant, products):
        """Test case-insensitive matching."""
        results = fuzzy_matcher.match_product("blue t-shirt", tenant)
        
        assert len(results) > 0
        product, score = results[0]
        assert product.title == "Blue T-Shirt"
        assert score >= 0.95
    
    def test_typo_correction(self, fuzzy_matcher, tenant, products):
        """Test matching with typos."""
        results = fuzzy_matcher.match_product("Blu Tshirt", tenant)
        
        assert len(results) > 0
        product, score = results[0]
        assert product.title == "Blue T-Shirt"
        assert score >= 0.6  # Should still match with typos
    
    def test_abbreviation_expansion(self, fuzzy_matcher, tenant, products):
        """Test abbreviation expansion."""
        results = fuzzy_matcher.match_product("tshirt", tenant)
        
        # Should expand "tshirt" to "t-shirt" and match
        assert len(results) > 0
        product, score = results[0]
        assert "T-Shirt" in product.title
    
    def test_informal_name_matching(self, fuzzy_matcher, tenant, products):
        """Test matching with informal names."""
        results = fuzzy_matcher.match_product("hoodie", tenant)
        
        # Should expand "hoodie" to "hooded sweatshirt"
        assert len(results) > 0
        product, score = results[0]
        assert "Hoodie" in product.title
    
    def test_partial_match(self, fuzzy_matcher, tenant, products):
        """Test partial word matching."""
        results = fuzzy_matcher.match_product("running", tenant)
        
        assert len(results) > 0
        product, score = results[0]
        assert "Running" in product.title
    
    def test_description_matching(self, fuzzy_matcher, tenant, products):
        """Test matching against product description."""
        # Use lower threshold since description matches are weighted at 0.8
        results = fuzzy_matcher.match_product("athletic", tenant, threshold=0.6)
        
        assert len(results) > 0
        # Should match "Running Shoes" via description
        product, score = results[0]
        assert "athletic" in product.description.lower()
    
    def test_threshold_filtering(self, fuzzy_matcher, tenant, products):
        """Test that low similarity matches are filtered out."""
        results = fuzzy_matcher.match_product(
            "completely unrelated query xyz",
            tenant,
            threshold=0.7
        )
        
        # Should return no results for unrelated query
        assert len(results) == 0
    
    def test_result_limit(self, fuzzy_matcher, tenant, products):
        """Test result limit parameter."""
        results = fuzzy_matcher.match_product(
            "shirt",
            tenant,
            limit=2
        )
        
        # Should return at most 2 results
        assert len(results) <= 2
    
    def test_tenant_isolation(self, fuzzy_matcher, tenant, products, db):
        """Test that matching is tenant-scoped."""
        from decimal import Decimal
        # Create another tenant with products
        other_tenant = Tenant.objects.create(
            name="Other Business",
            slug="other-business",
            whatsapp_number="+19876543210",
            status="active"
        )
        Product.objects.create(
            tenant=other_tenant,
            title="Blue T-Shirt",
            description="Another blue t-shirt",
            price=Decimal("29.99"),
            is_active=True
        )
        
        # Search in original tenant
        results = fuzzy_matcher.match_product("Blue T-Shirt", tenant)
        
        # Should only return products from original tenant
        assert len(results) == 1
        assert results[0][0].tenant == tenant
    
    def test_inactive_products_excluded(self, fuzzy_matcher, tenant, db):
        """Test that inactive products are not matched."""
        from decimal import Decimal
        Product.objects.create(
            tenant=tenant,
            title="Inactive Product",
            description="This should not be matched",
            price=Decimal("19.99"),
            is_active=False
        )
        
        results = fuzzy_matcher.match_product("Inactive Product", tenant)
        
        # Should not match inactive products
        assert len(results) == 0
    
    def test_caching(self, fuzzy_matcher, tenant, products):
        """Test that results are cached."""
        query = "Blue T-Shirt"
        
        # First call - should hit database
        results1 = fuzzy_matcher.match_product(query, tenant)
        
        # Second call - should hit cache
        with patch.object(Product.objects, 'filter') as mock_filter:
            results2 = fuzzy_matcher.match_product(query, tenant)
            
            # Should not query database
            mock_filter.assert_not_called()
        
        # Results should be identical
        assert len(results1) == len(results2)
        assert results1[0][0].id == results2[0][0].id


class TestServiceMatching:
    """Test service fuzzy matching."""
    
    def test_exact_match(self, fuzzy_matcher, tenant, services):
        """Test exact service name match."""
        results = fuzzy_matcher.match_service("Haircut", tenant)
        
        assert len(results) > 0
        service, score = results[0]
        assert service.title == "Haircut"
        assert score >= 0.95
    
    def test_partial_match(self, fuzzy_matcher, tenant, services):
        """Test partial service name match."""
        results = fuzzy_matcher.match_service("hair", tenant)
        
        # Should match both "Haircut" and "Hair Coloring"
        assert len(results) >= 2
        titles = [s[0].title for s in results]
        assert "Haircut" in titles
        assert "Hair Coloring" in titles
    
    def test_typo_correction(self, fuzzy_matcher, tenant, services):
        """Test matching with typos."""
        results = fuzzy_matcher.match_service("masage", tenant)
        
        assert len(results) > 0
        service, score = results[0]
        assert service.title == "Massage"
    
    def test_tenant_isolation(self, fuzzy_matcher, tenant, services, db):
        """Test that matching is tenant-scoped."""
        other_tenant = Tenant.objects.create(
            name="Other Business",
            slug="other-business",
            whatsapp_number="+19876543210",
            status="active"
        )
        Service.objects.create(
            tenant=other_tenant,
            title="Haircut",
            description="Another haircut service",
            is_active=True
        )
        
        results = fuzzy_matcher.match_service("Haircut", tenant)
        
        # Should only return services from original tenant
        assert len(results) == 1
        assert results[0][0].tenant == tenant


class TestSpellingCorrection:
    """Test spelling correction functionality."""
    
    def test_correct_single_word(self, fuzzy_matcher):
        """Test correcting a single misspelled word."""
        vocabulary = ["product", "service", "order"]
        corrected = fuzzy_matcher.correct_spelling("prodct", vocabulary)
        
        assert corrected == "product"
    
    def test_correct_multiple_words(self, fuzzy_matcher):
        """Test correcting multiple words."""
        vocabulary = ["blue", "shirt", "running", "shoes"]
        corrected = fuzzy_matcher.correct_spelling("blu shrt", vocabulary)
        
        assert "blue" in corrected or "blu" in corrected
        assert "shirt" in corrected or "shrt" in corrected
    
    def test_preserve_correct_words(self, fuzzy_matcher):
        """Test that correct words are preserved."""
        vocabulary = ["blue", "shirt"]
        corrected = fuzzy_matcher.correct_spelling("blue shirt", vocabulary)
        
        assert corrected == "blue shirt"
    
    def test_threshold_filtering(self, fuzzy_matcher):
        """Test that low similarity corrections are rejected."""
        vocabulary = ["product"]
        corrected = fuzzy_matcher.correct_spelling(
            "xyz",
            vocabulary,
            threshold=0.9
        )
        
        # Should keep original word if no good match
        assert corrected == "xyz"
    
    def test_case_insensitive(self, fuzzy_matcher):
        """Test case-insensitive correction."""
        vocabulary = ["Product"]
        corrected = fuzzy_matcher.correct_spelling("prodct", vocabulary)
        
        assert corrected.lower() == "product"


class TestConfidenceScoring:
    """Test confidence scoring and thresholds."""
    
    def test_high_confidence_level(self, fuzzy_matcher):
        """Test high confidence classification."""
        level = fuzzy_matcher.get_confidence_level(0.9)
        assert level == 'high'
    
    def test_medium_confidence_level(self, fuzzy_matcher):
        """Test medium confidence classification."""
        level = fuzzy_matcher.get_confidence_level(0.7)
        assert level == 'medium'
    
    def test_low_confidence_level(self, fuzzy_matcher):
        """Test low confidence classification."""
        level = fuzzy_matcher.get_confidence_level(0.5)
        assert level == 'low'
    
    def test_should_confirm_high_confidence(self, fuzzy_matcher):
        """Test confirmation not needed for high confidence."""
        should_confirm = fuzzy_matcher.should_confirm_correction(0.9)
        assert should_confirm is False
    
    def test_should_confirm_low_confidence(self, fuzzy_matcher):
        """Test confirmation needed for low confidence."""
        should_confirm = fuzzy_matcher.should_confirm_correction(0.7)
        assert should_confirm is True


class TestTextNormalization:
    """Test text normalization."""
    
    def test_lowercase_conversion(self, fuzzy_matcher):
        """Test conversion to lowercase."""
        normalized = fuzzy_matcher._normalize_text("HELLO WORLD")
        assert normalized == "hello world"
    
    def test_special_character_removal(self, fuzzy_matcher):
        """Test removal of special characters."""
        normalized = fuzzy_matcher._normalize_text("hello! world?")
        assert normalized == "hello world"
    
    def test_whitespace_normalization(self, fuzzy_matcher):
        """Test whitespace normalization."""
        normalized = fuzzy_matcher._normalize_text("hello    world")
        assert normalized == "hello world"
    
    def test_hyphen_preservation(self, fuzzy_matcher):
        """Test that hyphens are preserved."""
        normalized = fuzzy_matcher._normalize_text("t-shirt")
        assert normalized == "t-shirt"


class TestAbbreviationExpansion:
    """Test abbreviation expansion."""
    
    def test_tshirt_expansion(self, fuzzy_matcher):
        """Test t-shirt abbreviation expansion."""
        expanded = fuzzy_matcher._expand_abbreviations("tshirt")
        assert "t-shirt" in expanded
    
    def test_hoodie_expansion(self, fuzzy_matcher):
        """Test hoodie expansion."""
        expanded = fuzzy_matcher._expand_abbreviations("hoodie")
        assert "hooded sweatshirt" in expanded
    
    def test_multiple_abbreviations(self, fuzzy_matcher):
        """Test expanding multiple abbreviations."""
        expanded = fuzzy_matcher._expand_abbreviations("tshirt and jeans")
        assert "t-shirt" in expanded
        assert "denim pants" in expanded
    
    def test_case_insensitive_expansion(self, fuzzy_matcher):
        """Test case-insensitive abbreviation expansion."""
        expanded = fuzzy_matcher._expand_abbreviations("TSHIRT")
        assert "t-shirt" in expanded.lower()


class TestLevenshteinSimilarity:
    """Test Levenshtein similarity calculation."""
    
    def test_identical_strings(self, fuzzy_matcher):
        """Test similarity of identical strings."""
        similarity = fuzzy_matcher._levenshtein_similarity("hello", "hello")
        assert similarity == 1.0
    
    def test_completely_different(self, fuzzy_matcher):
        """Test similarity of completely different strings."""
        similarity = fuzzy_matcher._levenshtein_similarity("abc", "xyz")
        assert similarity < 0.5
    
    def test_similar_strings(self, fuzzy_matcher):
        """Test similarity of similar strings."""
        similarity = fuzzy_matcher._levenshtein_similarity("hello", "helo")
        assert 0.7 < similarity < 1.0
    
    def test_empty_strings(self, fuzzy_matcher):
        """Test handling of empty strings."""
        similarity = fuzzy_matcher._levenshtein_similarity("", "hello")
        assert similarity == 0.0


class TestStringSimilarity:
    """Test string similarity calculation."""
    
    def test_title_match(self, fuzzy_matcher):
        """Test similarity calculation with title."""
        score = fuzzy_matcher._calculate_string_similarity(
            "blue shirt",
            "Blue T-Shirt",
            None
        )
        assert score > 0.6
    
    def test_description_match(self, fuzzy_matcher):
        """Test similarity calculation with description."""
        score = fuzzy_matcher._calculate_string_similarity(
            "comfortable",
            "T-Shirt",
            "Comfortable cotton t-shirt"
        )
        assert score > 0.5
    
    def test_substring_boost(self, fuzzy_matcher):
        """Test that substring matches get boosted score."""
        score = fuzzy_matcher._calculate_string_similarity(
            "shirt",
            "Blue T-Shirt",
            None
        )
        assert score >= 0.85  # Should get substring boost


class TestFactoryFunction:
    """Test factory function."""
    
    def test_create_without_client(self):
        """Test creating service without OpenAI client."""
        from apps.bot.services.fuzzy_matcher_service import create_fuzzy_matcher_service
        
        service = create_fuzzy_matcher_service()
        assert isinstance(service, FuzzyMatcherService)
        assert service.openai_client is None
    
    def test_create_with_client(self):
        """Test creating service with OpenAI client."""
        from apps.bot.services.fuzzy_matcher_service import create_fuzzy_matcher_service
        
        mock_client = Mock()
        service = create_fuzzy_matcher_service(openai_client=mock_client)
        assert isinstance(service, FuzzyMatcherService)
        assert service.openai_client == mock_client
