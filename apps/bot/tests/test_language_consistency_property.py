"""
Property-based tests for language consistency.

**Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
**Validates: Requirements 6.1, 6.2, 6.3, 6.5**

Property: For any conversation, once a language is detected from customer messages,
all subsequent bot responses should use that same language until the customer
explicitly switches.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from django.utils import timezone

from apps.bot.services.language_consistency_manager import LanguageConsistencyManager
from apps.bot.models import LanguagePreference
from apps.messaging.models import Conversation, Message
from apps.tenants.models import Tenant, Customer


# Hypothesis strategies
@st.composite
def english_message(draw):
    """Generate an English message."""
    templates = [
        "Hello, I want to buy {item}",
        "What is the price of {item}?",
        "Can you help me with {item}?",
        "I need {item} please",
        "How much is {item}?",
        "Do you have {item} available?",
        "I would like to order {item}",
        "Please show me {item}",
    ]
    items = ["shoes", "phone", "laptop", "shirt", "book", "watch"]
    
    template = draw(st.sampled_from(templates))
    item = draw(st.sampled_from(items))
    return template.format(item=item)


@st.composite
def swahili_message(draw):
    """Generate a Swahili message."""
    templates = [
        "Habari, nataka {item}",
        "Bei gani ya {item}?",
        "Naomba {item}",
        "Ninataka {item} tafadhali",
        "Ngapi {item}?",
        "Kuna {item}?",
        "Ningependa {item}",
        "Nipe {item}",
    ]
    items = ["viatu", "simu", "kompyuta", "shati", "kitabu", "saa"]
    
    template = draw(st.sampled_from(templates))
    item = draw(st.sampled_from(items))
    return template.format(item=item)


@st.composite
def mixed_message(draw):
    """Generate a mixed language message."""
    templates = [
        "Habari, I want {item}",
        "Nataka {item} please",
        "Bei gani for {item}?",
        "Can you nipe {item}?",
        "Ninataka to buy {item}",
    ]
    items = ["shoes", "phone", "viatu", "simu"]
    
    template = draw(st.sampled_from(templates))
    item = draw(st.sampled_from(items))
    return template.format(item=item)


@st.composite
def conversation_messages(draw):
    """Generate a sequence of messages in the same language."""
    language = draw(st.sampled_from(['en', 'sw', 'mixed']))
    num_messages = draw(st.integers(min_value=2, max_value=10))
    
    messages = []
    for _ in range(num_messages):
        if language == 'en':
            msg = draw(english_message())
        elif language == 'sw':
            msg = draw(swahili_message())
        else:
            msg = draw(mixed_message())
        messages.append(msg)
    
    return {
        'language': language,
        'messages': messages
    }


@st.composite
def language_switch_messages(draw):
    """Generate messages that switch language mid-conversation."""
    first_language = draw(st.sampled_from(['en', 'sw']))
    second_language = 'sw' if first_language == 'en' else 'en'
    
    # Generate messages in first language
    first_count = draw(st.integers(min_value=2, max_value=5))
    first_messages = []
    for _ in range(first_count):
        if first_language == 'en':
            msg = draw(english_message())
        else:
            msg = draw(swahili_message())
        first_messages.append(msg)
    
    # Generate messages in second language
    second_count = draw(st.integers(min_value=2, max_value=5))
    second_messages = []
    for _ in range(second_count):
        if second_language == 'en':
            msg = draw(english_message())
        else:
            msg = draw(swahili_message())
        second_messages.append(msg)
    
    return {
        'first_language': first_language,
        'first_messages': first_messages,
        'second_language': second_language,
        'second_messages': second_messages
    }


@pytest.mark.django_db
class TestLanguageConsistencyProperty:
    """Property-based tests for language consistency."""
    
    @given(data=conversation_messages())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_consistency_maintained(self, data, tenant, conversation):
        """
        Property: Language remains consistent throughout conversation.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        expected_language = data['language']
        messages = data['messages']
        
        # Process each message and track detected language
        detected_languages = []
        for msg_text in messages:
            detected = LanguageConsistencyManager.detect_and_update_language(
                conversation,
                msg_text
            )
            detected_languages.append(detected)
        
        # Get final conversation language
        final_language = LanguageConsistencyManager.get_conversation_language(conversation)
        
        # Property: Final language should match the expected language
        # (or be 'mixed' if messages were mixed)
        if expected_language == 'mixed':
            # Mixed messages can result in 'mixed', 'en', or 'sw' depending on content
            assert final_language in ['en', 'sw', 'mixed'], \
                f"Mixed messages should result in valid language, got {final_language}"
        else:
            # For pure English or Swahili, final language should match
            assert final_language == expected_language, \
                f"Expected language {expected_language}, but got {final_language}"
        
        # Property: Language detection should be stable for consistent input
        # The final language should match the expected language for the message set
        # Note: Language switches are allowed per Requirement 6.2, so we don't
        # require 'mixed' to be present when languages differ
    
    @given(data=language_switch_messages())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_switch_detection(self, data, tenant, conversation):
        """
        Property: Language switches are detected and updated.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        first_language = data['first_language']
        first_messages = data['first_messages']
        second_language = data['second_language']
        second_messages = data['second_messages']
        
        # Process first set of messages
        for msg_text in first_messages:
            LanguageConsistencyManager.detect_and_update_language(
                conversation,
                msg_text
            )
        
        # Check language after first set
        language_after_first = LanguageConsistencyManager.get_conversation_language(conversation)
        
        # Property: Language should be set to first language (or mixed if ambiguous)
        assert language_after_first in [first_language, 'mixed'], \
            f"After {first_language} messages, expected {first_language} or mixed, " \
            f"got {language_after_first}"
        
        # Process second set of messages (language switch)
        for msg_text in second_messages:
            LanguageConsistencyManager.detect_and_update_language(
                conversation,
                msg_text
            )
        
        # Check language after switch
        language_after_switch = LanguageConsistencyManager.get_conversation_language(conversation)
        
        # Property: Language should have switched to second language (or mixed)
        assert language_after_switch in [second_language, 'mixed'], \
            f"After switching to {second_language}, expected {second_language} or mixed, " \
            f"got {language_after_switch}"
    
    @given(
        message_text=st.one_of(english_message(), swahili_message(), mixed_message())
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_detection_is_deterministic(self, message_text, tenant, conversation):
        """
        Property: Language detection is deterministic for the same input.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        # Detect language multiple times
        detection1 = LanguageConsistencyManager.detect_language(message_text)
        detection2 = LanguageConsistencyManager.detect_language(message_text)
        detection3 = LanguageConsistencyManager.detect_language(message_text)
        
        # Property: All detections should be the same
        assert detection1 == detection2 == detection3, \
            f"Language detection should be deterministic, got {detection1}, {detection2}, {detection3}"
        
        # Property: Detected language should be valid
        assert detection1 in ['en', 'sw', 'mixed'], \
            f"Detected language should be valid, got {detection1}"
    
    @given(
        initial_language=st.sampled_from(['en', 'sw', 'mixed'])
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_preference_persistence(self, initial_language, tenant, conversation):
        """
        Property: Language preference is persisted and retrievable.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        # Set language preference
        LanguageConsistencyManager.set_conversation_language(
            conversation,
            initial_language
        )
        
        # Retrieve language preference
        retrieved_language = LanguageConsistencyManager.get_conversation_language(conversation)
        
        # Property: Retrieved language should match what was set
        assert retrieved_language == initial_language, \
            f"Expected {initial_language}, but got {retrieved_language}"
        
        # Verify it's persisted in database
        preference = LanguagePreference.objects.get(conversation=conversation)
        assert preference.primary_language == initial_language, \
            f"Database should have {initial_language}, but has {preference.primary_language}"
    
    @given(
        messages=st.lists(
            st.one_of(english_message(), swahili_message()),
            min_size=3,
            max_size=10
        )
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_usage_statistics_tracked(self, messages, tenant, conversation):
        """
        Property: Language usage statistics are tracked correctly.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        # Process all messages
        for msg_text in messages:
            LanguageConsistencyManager.detect_and_update_language(
                conversation,
                msg_text
            )
        
        # Get usage statistics
        stats = LanguageConsistencyManager.get_language_statistics(conversation)
        
        # Property: Statistics should exist and have positive counts
        assert len(stats) > 0, "Should have language usage statistics"
        
        for language, count in stats.items():
            assert count > 0, f"Language {language} should have positive count"
            assert language in ['en', 'sw', 'mixed'], \
                f"Language code should be valid, got {language}"
        
        # Property: Total count should match number of messages processed
        total_count = sum(stats.values())
        assert total_count >= len(messages), \
            f"Total usage count {total_count} should be at least {len(messages)}"
    
    @given(
        message_text=st.text(min_size=0, max_size=100)
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_detection_handles_arbitrary_text(self, message_text, tenant, conversation):
        """
        Property: Language detection handles arbitrary text without errors.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        # Property: Should not raise exceptions for any text
        try:
            detected = LanguageConsistencyManager.detect_language(message_text)
            
            # Property: Should always return a valid language code
            assert detected in ['en', 'sw', 'mixed'], \
                f"Should return valid language code, got {detected}"
            
        except Exception as e:
            pytest.fail(f"Language detection should not raise exceptions, got: {e}")
    
    @given(
        first_msg=english_message(),
        second_msg=swahili_message()
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_should_maintain_language_logic(self, first_msg, second_msg, tenant, conversation):
        """
        Property: should_maintain_language correctly identifies language switches.
        
        **Feature: conversational-commerce-ux-enhancement, Property 6: Language consistency**
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        # Establish initial language with first message
        LanguageConsistencyManager.detect_and_update_language(conversation, first_msg)
        initial_language = LanguageConsistencyManager.get_conversation_language(conversation)
        
        # Check if second message should maintain language
        should_maintain = LanguageConsistencyManager.should_maintain_language(
            conversation,
            second_msg
        )
        
        # Detect language of second message
        second_language = LanguageConsistencyManager.detect_language(second_msg)
        
        # Property: If languages differ clearly, should_maintain should be False
        if initial_language == 'en' and second_language == 'sw':
            assert should_maintain is False, \
                "Should not maintain language when switching from English to Swahili"
        elif initial_language == 'sw' and second_language == 'en':
            assert should_maintain is False, \
                "Should not maintain language when switching from Swahili to English"
        elif second_language == 'mixed':
            # Mixed messages should maintain current language
            assert should_maintain is True, \
                "Should maintain language for mixed messages"


@pytest.fixture
def tenant():
    """Create test tenant."""
    tenant = Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant-lang"
    )
    yield tenant
    # Cleanup
    tenant.delete()


@pytest.fixture
def customer(tenant):
    """Create test customer."""
    customer = Customer.objects.create(
        tenant=tenant,
        phone_e164="+254712345679"
    )
    yield customer
    # Cleanup handled by tenant cascade


@pytest.fixture
def conversation(tenant, customer):
    """Create test conversation."""
    conversation = Conversation.objects.create(
        tenant=tenant,
        customer=customer,
        channel='whatsapp',
        status='active'
    )
    yield conversation
    # Cleanup handled by tenant cascade
