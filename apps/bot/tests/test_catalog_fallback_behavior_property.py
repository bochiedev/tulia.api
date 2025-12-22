"""
Property-based tests for catalog fallback behavior.

**Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
**Validates: Requirements 5.2, 5.3**

Property: The system should show catalog links when ANY of the exact conditions
are met: (catalog_total_matches_estimate >= 50 AND user still vague after 1 clarifying question)
OR user asks "see all items/catalog/list everything" OR results are low confidence
(no clear top 3) OR product selection requires visuals/variants beyond WhatsApp UX
OR repeated loop (user rejects 2 shortlists in a row).
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from django.utils import timezone

from apps.bot.services.catalog_fallback_service import CatalogFallbackService
from apps.bot.conversation_state import ConversationState
from apps.tenants.models import Tenant, Customer


# Hypothesis strategies
@st.composite
def conversation_state_data(draw):
    """Generate conversation state data."""
    return {
        'tenant_id': 'test-tenant-123',
        'conversation_id': 'test-conv-456',
        'request_id': 'test-req-789',
        'catalog_link_base': 'https://catalog.example.com',
        'catalog_total_matches_estimate': draw(st.integers(min_value=0, max_value=200)),
        'shortlist_rejections': draw(st.integers(min_value=0, max_value=5)),
        'last_catalog_query': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs')))),
        'metadata': {}
    }


@st.composite
def user_message(draw):
    """Generate user messages."""
    return draw(st.sampled_from([
        # Vague messages
        "anything",
        "whatever",
        "something good",
        "don't know",
        "not sure",
        "show me",
        "what do you have",
        "nice",
        "best",
        "cheap",
        # Specific messages
        "I need a MacBook Pro 13 inch with 16GB RAM",
        "Looking for a red dress in size medium",
        "Want a gaming laptop under $1500 with RTX graphics",
        "Need wireless headphones with noise cancellation",
        # See all requests
        "see all items",
        "show me the catalog",
        "list everything",
        "browse all products",
        "view all options",
        "full catalog please",
        "show everything",
        "complete list",
        # Other messages
        "hello",
        "help me",
        "what's available"
    ]))


@st.composite
def search_results(draw):
    """Generate search results with varying confidence levels."""
    result_count = draw(st.integers(min_value=0, max_value=20))
    results = []
    
    for i in range(result_count):
        result = {
            'product_id': f'product-{i}',
            'name': f'Product {i}',
            'price': draw(st.floats(min_value=1.0, max_value=1000.0)),
            'confidence': draw(st.floats(min_value=0.0, max_value=1.0)),
            'category': draw(st.sampled_from(['electronics', 'clothing', 'books', 'home', 'sports']))
        }
        
        # Add variants for some products
        if draw(st.booleans()):
            variant_count = draw(st.integers(min_value=1, max_value=8))
            result['variants'] = []
            for j in range(variant_count):
                variant = {
                    'id': f'variant-{i}-{j}',
                    'color': draw(st.sampled_from(['red', 'blue', 'green', 'black', 'white'])),
                    'size': draw(st.sampled_from(['S', 'M', 'L', 'XL']))
                }
                result['variants'].append(variant)
        
        results.append(result)
    
    return results


@pytest.mark.django_db
class TestCatalogFallbackBehaviorProperty:
    """Property-based tests for catalog fallback behavior."""
    
    @given(
        state_data=conversation_state_data(),
        message=user_message(),
        clarifying_questions=st.integers(min_value=0, max_value=3)
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_large_catalog_vague_query_condition(self, state_data, message, clarifying_questions):
        """
        Property: Large catalog + vague query after clarification triggers fallback.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        When catalog_total_matches_estimate >= 50 AND user still vague after 1 clarifying question,
        the system should show catalog link.
        """
        state = ConversationState(**state_data)
        
        # Test condition 1: Large catalog + vague query after clarification
        if (state.catalog_total_matches_estimate >= 50 and 
            clarifying_questions >= 1 and 
            CatalogFallbackService._is_user_still_vague(message)):
            
            should_show, reason = CatalogFallbackService.should_show_catalog_link(
                state=state,
                message=message,
                clarifying_questions_asked=clarifying_questions
            )
            
            assert should_show is True, \
                f"Should show catalog link for large catalog ({state.catalog_total_matches_estimate}) " \
                f"with vague message '{message}' after {clarifying_questions} clarifications"
            assert "Large catalog with vague query after clarification" in reason
        
        # Test that condition is not triggered when requirements not met
        elif (state.catalog_total_matches_estimate < 50 or 
              clarifying_questions < 1 or 
              not CatalogFallbackService._is_user_still_vague(message)):
            
            should_show, reason = CatalogFallbackService.should_show_catalog_link(
                state=state,
                message=message,
                clarifying_questions_asked=clarifying_questions
            )
            
            # Should not trigger this specific condition
            if should_show:
                assert "Large catalog with vague query after clarification" not in reason, \
                    f"Should not trigger large catalog condition when requirements not met: " \
                    f"catalog={state.catalog_total_matches_estimate}, clarifications={clarifying_questions}, " \
                    f"vague={CatalogFallbackService._is_user_still_vague(message)}"
    
    @given(
        state_data=conversation_state_data(),
        message=user_message()
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_see_all_request_condition(self, state_data, message):
        """
        Property: "See all" requests always trigger catalog fallback.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        When user asks "see all items/catalog/list everything", the system should
        show catalog link regardless of other conditions.
        """
        state = ConversationState(**state_data)
        
        is_see_all = CatalogFallbackService._is_see_all_request(message)
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(
            state=state,
            message=message
        )
        
        if is_see_all:
            assert should_show is True, \
                f"Should show catalog link for 'see all' request: '{message}'"
            assert "User requested to see all items" in reason
        else:
            # If catalog link is shown, it should not be due to see all condition
            if should_show and "User requested to see all items" in reason:
                assert False, \
                    f"Should not trigger 'see all' condition for non-see-all message: '{message}'"
    
    @given(
        state_data=conversation_state_data(),
        results=search_results()
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_low_confidence_results_condition(self, state_data, results):
        """
        Property: Low confidence results trigger catalog fallback.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        When results are low confidence (no clear top 3), the system should
        show catalog link.
        """
        state = ConversationState(**state_data)
        
        is_low_confidence = CatalogFallbackService._are_results_low_confidence(results)
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(
            state=state,
            search_results=results
        )
        
        if is_low_confidence:
            assert should_show is True, \
                f"Should show catalog link for low confidence results: {len(results)} results"
            assert "Low confidence search results" in reason
        else:
            # If catalog link is shown, it should not be due to low confidence condition
            if should_show and "Low confidence search results" in reason:
                assert False, \
                    f"Should not trigger low confidence condition for high confidence results"
    
    @given(
        state_data=conversation_state_data(),
        results=search_results()
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_visual_selection_required_condition(self, state_data, results):
        """
        Property: Products requiring visual selection trigger catalog fallback.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        When product selection requires visuals/variants beyond WhatsApp UX,
        the system should show catalog link.
        """
        state = ConversationState(**state_data)
        
        requires_visual = CatalogFallbackService._requires_visual_selection(results)
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(
            state=state,
            search_results=results
        )
        
        if requires_visual:
            assert should_show is True, \
                f"Should show catalog link for products requiring visual selection"
            # Note: Multiple conditions can trigger catalog fallback, so we just verify it shows
        else:
            # If catalog link is shown, it should not be due to visual selection condition
            if should_show and "Products require visual selection" in reason:
                assert False, \
                    f"Should not trigger visual selection condition when not required"
    
    @given(
        state_data=conversation_state_data(),
        shortlist_rejections=st.integers(min_value=0, max_value=5)
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_repeated_shortlist_rejections_condition(self, state_data, shortlist_rejections):
        """
        Property: Repeated shortlist rejections trigger catalog fallback.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        When user rejects 2 shortlists in a row, the system should show catalog link.
        """
        state_data['shortlist_rejections'] = shortlist_rejections
        state = ConversationState(**state_data)
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(state=state)
        
        if shortlist_rejections >= 2:
            assert should_show is True, \
                f"Should show catalog link after {shortlist_rejections} shortlist rejections"
            assert "User rejected multiple shortlists" in reason
        else:
            # If catalog link is shown, it should not be due to shortlist rejections
            if should_show and "User rejected multiple shortlists" in reason:
                assert False, \
                    f"Should not trigger shortlist rejection condition with only {shortlist_rejections} rejections"
    
    @given(
        state_data=conversation_state_data(),
        message=user_message(),
        results=search_results(),
        clarifying_questions=st.integers(min_value=0, max_value=3)
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_catalog_fallback_conditions_are_exhaustive(self, state_data, message, results, clarifying_questions):
        """
        Property: All catalog fallback conditions are properly evaluated.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        The system should evaluate all conditions and provide appropriate reasoning
        when showing catalog links.
        """
        state = ConversationState(**state_data)
        
        should_show, reason = CatalogFallbackService.should_show_catalog_link(
            state=state,
            message=message,
            search_results=results,
            clarifying_questions_asked=clarifying_questions
        )
        
        # If catalog link is shown, there should be a valid reason
        if should_show:
            valid_reasons = [
                "Large catalog with vague query after clarification",
                "User requested to see all items",
                "Low confidence search results",
                "Products require visual selection",
                "User rejected multiple shortlists"
            ]
            
            assert any(valid_reason in reason for valid_reason in valid_reasons), \
                f"Catalog link shown but reason '{reason}' is not one of the valid conditions"
        
        # If no catalog link is shown, none of the conditions should be met
        if not should_show:
            # Check that none of the individual conditions are met
            condition_1 = (state.catalog_total_matches_estimate >= 50 and 
                          clarifying_questions >= 1 and 
                          CatalogFallbackService._is_user_still_vague(message))
            
            condition_2 = CatalogFallbackService._is_see_all_request(message)
            
            condition_3 = CatalogFallbackService._are_results_low_confidence(results) if results is not None else False
            
            condition_4 = CatalogFallbackService._requires_visual_selection(results) if results is not None else False
            
            condition_5 = state.shortlist_rejections >= 2
            
            assert not (condition_1 or condition_2 or condition_3 or condition_4 or condition_5), \
                f"No catalog link shown but at least one condition should be met: " \
                f"condition_1={condition_1}, condition_2={condition_2}, condition_3={condition_3}, " \
                f"condition_4={condition_4}, condition_5={condition_5}"
    
    @given(
        state_data=conversation_state_data(),
        selected_product_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        search_query=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs')))
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_catalog_url_generation_properties(self, state_data, selected_product_id, search_query):
        """
        Property: Catalog URL generation follows consistent format.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        Generated catalog URLs should always include tenant_id and conversation_id,
        and optionally include product_id and search query.
        """
        state = ConversationState(**state_data)
        
        # Test basic URL generation
        url = CatalogFallbackService.generate_catalog_url(state)
        
        if state.catalog_link_base:
            assert url is not None, "Should generate URL when catalog_link_base is set"
            assert f"tenant_id={state.tenant_id}" in url, "URL should include tenant_id"
            assert f"conversation_id={state.conversation_id}" in url, "URL should include conversation_id"
            assert "return_context=whatsapp" in url, "URL should include return context"
        else:
            assert url is None, "Should not generate URL when catalog_link_base is None"
        
        # Test URL with product ID
        if state.catalog_link_base:
            url_with_product = CatalogFallbackService.generate_catalog_url(
                state, selected_product_id=selected_product_id
            )
            assert f"product_id={selected_product_id}" in url_with_product, \
                "URL should include product_id when provided"
        
        # Test URL with search query
        if state.catalog_link_base:
            url_with_search = CatalogFallbackService.generate_catalog_url(
                state, search_query=search_query
            )
            # URL encoding may change the query, but it should be present
            assert "search=" in url_with_search, \
                "URL should include search parameter when provided"
    
    @given(
        state_data=conversation_state_data(),
        selected_product_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        return_message=st.text(min_size=0, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs', 'Po')))
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_catalog_return_handling_properties(self, state_data, selected_product_id, return_message):
        """
        Property: Catalog return handling updates state correctly.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        When handling catalog returns, the system should update the conversation
        state appropriately and reset shortlist rejections.
        """
        state = ConversationState(**state_data)
        original_rejections = state.shortlist_rejections
        
        updated_state = CatalogFallbackService.handle_catalog_return(
            state=state,
            selected_product_id=selected_product_id,
            return_message=return_message
        )
        
        # Property: Selected product should be set
        assert updated_state.selected_item_ids == [selected_product_id], \
            "Should set selected product ID"
        
        # Property: Sales step should be updated
        assert updated_state.sales_step == 'get_item_details', \
            "Should update sales step to get item details"
        
        # Property: Shortlist rejections should be reset
        assert updated_state.shortlist_rejections == 0, \
            f"Should reset shortlist rejections from {original_rejections} to 0"
        
        # Property: Metadata should include catalog return info
        assert 'catalog_return' in updated_state.metadata, \
            "Should add catalog return metadata"
        
        catalog_return_data = updated_state.metadata['catalog_return']
        assert catalog_return_data['product_id'] == selected_product_id, \
            "Should store selected product ID in metadata"
        assert catalog_return_data['return_message'] == return_message, \
            "Should store return message in metadata"
    
    @given(
        catalog_url=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Po'))),
        reason=st.sampled_from([
            "Large catalog with vague query after clarification",
            "User requested to see all items",
            "Low confidence search results",
            "Products require visual selection",
            "User rejected multiple shortlists"
        ]),
        context=st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs', 'Po'))))
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_catalog_link_message_formatting_properties(self, catalog_url, reason, context):
        """
        Property: Catalog link messages are properly formatted.
        
        **Feature: product-narrowing-logic, Property 15: Catalog Fallback Behavior**
        **Validates: Requirements 5.2, 5.3**
        
        Catalog link messages should always include the URL, appropriate intro text,
        and optional context.
        """
        message = CatalogFallbackService.format_catalog_link_message(
            catalog_url=catalog_url,
            reason=reason,
            context=context
        )
        
        # Property: Message should include the URL
        assert catalog_url in message, "Message should include the catalog URL"
        
        # Property: Message should include emoji
        assert "🌐" in message, "Message should include web emoji"
        
        # Property: Message should have appropriate intro based on reason
        reason_intros = {
            "Large catalog with vague query after clarification": "I have many options that might interest you!",
            "User requested to see all items": "Here's our complete catalog for you to browse:",
            "Low confidence search results": "I found several options, but you might prefer to browse visually:",
            "Products require visual selection": "These products are best viewed with images. Check out our catalog:",
            "User rejected multiple shortlists": "Let me show you our full catalog so you can browse at your own pace:"
        }
        
        expected_intro = reason_intros.get(reason, "Browse our full catalog:")
        assert expected_intro in message, f"Message should include appropriate intro for reason: {reason}"
        
        # Property: If context is provided, it should be included
        if context:
            assert context in message, "Message should include provided context"
        
        # Property: Message should have helpful closing text
        if not context:
            assert "Once you find something you like" in message, \
                "Message should include helpful closing text when no context provided"


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