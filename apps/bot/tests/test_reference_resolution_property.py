"""
Property-based tests for reference context resolution.

**Feature: conversational-commerce-ux-enhancement, Property 1: Recent context priority**
**Validates: Requirements 1.1, 1.2, 1.3**

Property: For any conversation and customer reference (like "1", "first", "the blue one"),
the system should resolve the reference using the most recent list context (within last 5 minutes)
before considering older contexts.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import timedelta
from django.utils import timezone

from apps.bot.services.reference_context_manager import ReferenceContextManager
from apps.bot.models import ReferenceContext
from apps.messaging.models import Conversation
from apps.tenants.models import Tenant, Customer


# Hypothesis strategies
@st.composite
def reference_context_data(draw):
    """Generate reference context data."""
    num_items = draw(st.integers(min_value=1, max_value=10))
    list_type = draw(st.sampled_from(['products', 'services', 'appointments', 'orders']))
    
    items = []
    for i in range(num_items):
        items.append({
            'id': str(i + 1),
            'title': f"Item {i + 1}",
            'name': f"Item {i + 1}",
            'type': list_type
        })
    
    return {
        'list_type': list_type,
        'items': items
    }


@st.composite
def multiple_contexts(draw):
    """Generate multiple reference contexts with different timestamps."""
    num_contexts = draw(st.integers(min_value=2, max_value=5))
    contexts = []
    base_time = timezone.now()
    
    for i in range(num_contexts):
        context_data = draw(reference_context_data())
        # Each context is older than the previous
        minutes_ago = (num_contexts - i) * draw(st.floats(min_value=0.5, max_value=2.0))
        
        contexts.append({
            'data': context_data,
            'created_at': base_time - timedelta(minutes=minutes_ago),
            'expires_at': base_time + timedelta(minutes=5 - minutes_ago)
        })
    
    return contexts


@st.composite
def positional_reference(draw):
    """Generate a positional reference string."""
    return draw(st.sampled_from([
        "1", "2", "3", "4", "5",
        "first", "second", "third", "last",
        "the first one", "the last one", "number 2"
    ]))


@pytest.mark.django_db
class TestReferenceResolutionProperty:
    """Property-based tests for reference resolution."""
    
    @given(
        contexts=multiple_contexts(),
        reference=positional_reference()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_recent_context_priority(self, contexts, reference, tenant, conversation):
        """
        Property: Most recent context is always used for resolution.
        
        **Feature: conversational-commerce-ux-enhancement, Property 1: Recent context priority**
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # Create contexts in the database (oldest to newest)
        created_contexts = []
        for ctx_data in contexts:
            ctx = ReferenceContext.objects.create(
                conversation=conversation,
                context_id=f"ctx-{len(created_contexts)}",
                list_type=ctx_data['data']['list_type'],
                items=ctx_data['data']['items'],
                created_at=ctx_data['created_at'],
                expires_at=ctx_data['expires_at']
            )
            created_contexts.append(ctx)
        
        # Get the most recent non-expired context
        now = timezone.now()
        valid_contexts = [ctx for ctx in created_contexts if ctx.expires_at > now]
        
        # Skip if no valid contexts
        assume(len(valid_contexts) > 0)
        
        most_recent = max(valid_contexts, key=lambda x: x.created_at)
        
        # Resolve the reference
        result = ReferenceContextManager.resolve_reference(conversation, reference)
        
        # Property: If resolution succeeds, it should use the most recent context
        if result is not None:
            assert result['context_id'] == most_recent.context_id, \
                f"Should resolve from most recent context {most_recent.context_id}, " \
                f"but got {result['context_id']}"
            
            # Verify the item comes from the most recent context
            assert result['item'] in most_recent.items, \
                "Resolved item should be from the most recent context"
    
    @given(
        context_data=reference_context_data(),
        reference=positional_reference()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_positional_reference_resolution(self, context_data, reference, tenant, conversation):
        """
        Property: Valid positional references resolve to correct items.
        
        **Feature: conversational-commerce-ux-enhancement, Property 1: Recent context priority**
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # Store the context
        context_id = ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type=context_data['list_type'],
            items=context_data['items']
        )
        
        # Resolve the reference
        result = ReferenceContextManager.resolve_reference(conversation, reference)
        
        # Property: If reference is valid for this list size, it should resolve
        num_items = len(context_data['items'])
        
        # Determine if reference should be valid
        is_valid_reference = False
        expected_position = None
        
        if reference.isdigit():
            pos = int(reference)
            if 1 <= pos <= num_items:
                is_valid_reference = True
                expected_position = pos
        elif 'first' in reference.lower() or reference == '1':
            is_valid_reference = True
            expected_position = 1
        elif 'last' in reference.lower():
            is_valid_reference = True
            expected_position = num_items
        elif 'second' in reference.lower() or '2' in reference:
            if num_items >= 2:
                is_valid_reference = True
                expected_position = 2
        elif 'third' in reference.lower() or '3' in reference:
            if num_items >= 3:
                is_valid_reference = True
                expected_position = 3
        
        if is_valid_reference and expected_position:
            assert result is not None, \
                f"Valid reference '{reference}' should resolve for list of {num_items} items"
            
            # Verify correct item was resolved
            expected_item = context_data['items'][expected_position - 1]
            assert result['item']['id'] == expected_item['id'], \
                f"Reference '{reference}' should resolve to position {expected_position}"
    
    @given(
        context_data=reference_context_data()
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_expired_context_not_used(self, context_data, tenant, conversation):
        """
        Property: Expired contexts are not used for resolution.
        
        **Feature: conversational-commerce-ux-enhancement, Property 1: Recent context priority**
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # Create an expired context
        expired_context = ReferenceContext.objects.create(
            conversation=conversation,
            context_id="expired-ctx",
            list_type=context_data['list_type'],
            items=context_data['items'],
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        # Try to resolve a reference
        result = ReferenceContextManager.resolve_reference(conversation, "1")
        
        # Property: Should not resolve from expired context
        assert result is None, \
            "Should not resolve references from expired contexts"
    
    @given(
        items=st.lists(
            st.fixed_dictionaries({
                'id': st.text(min_size=1, max_size=10),
                'title': st.text(min_size=1, max_size=50),
                'color': st.sampled_from(['blue', 'red', 'green', 'yellow', 'black', 'white'])
            }),
            min_size=2,
            max_size=5
        )
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_descriptive_reference_resolution(self, items, tenant, conversation):
        """
        Property: Descriptive references match items with matching attributes.
        
        **Feature: conversational-commerce-ux-enhancement, Property 1: Recent context priority**
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # Store the context
        context_id = ReferenceContextManager.store_list_context(
            conversation=conversation,
            list_type='products',
            items=items
        )
        
        # Pick a color from the items
        test_color = items[0]['color']
        
        # Try to resolve by color
        result = ReferenceContextManager.resolve_reference(
            conversation,
            f"the {test_color} one"
        )
        
        # Property: Should resolve to an item with that color
        if result is not None:
            assert result['item']['color'] == test_color, \
                f"Descriptive reference 'the {test_color} one' should resolve to item with color {test_color}"


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
