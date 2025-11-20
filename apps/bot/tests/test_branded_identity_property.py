"""
Property-based tests for branded identity.

**Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
**Validates: Requirements 7.1, 7.2, 7.3**

Property: For any bot introduction or identity question, the response should
include the tenant's business name and never use generic terms like "Assistant" alone.
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from django.utils import timezone

from apps.bot.services.branded_persona_builder import BrandedPersonaBuilder
from apps.bot.models import AgentConfiguration
from apps.tenants.models import Tenant


# Hypothesis strategies
@st.composite
def business_name(draw):
    """Generate a business name."""
    prefixes = ["", "The ", ""]
    suffixes = ["", " Inc", " Ltd", " Co", " Store", " Shop", " Services"]
    
    names = [
        "TechMart", "FashionHub", "FoodDelight", "BookWorld", "GadgetZone",
        "StyleCorner", "HomeEssentials", "BeautyPalace", "SportsPro", "PetCare",
        "AutoParts", "GreenGarden", "CoffeeHouse", "BakeryBliss", "PharmaCare"
    ]
    
    prefix = draw(st.sampled_from(prefixes))
    name = draw(st.sampled_from(names))
    suffix = draw(st.sampled_from(suffixes))
    
    return f"{prefix}{name}{suffix}".strip()


@st.composite
def agent_name(draw):
    """Generate an agent name."""
    names = [
        "Assistant", "Helper", "Sarah", "John", "Alex", "Maya", "David",
        "Emma", "Bot", "Agent", "Support", "Advisor"
    ]
    return draw(st.sampled_from(names))


@st.composite
def language_code(draw):
    """Generate a language code."""
    return draw(st.sampled_from(['en', 'sw']))


@st.composite
def agent_capabilities(draw):
    """Generate agent capabilities text."""
    capabilities = [
        "Browse products and services",
        "Answer questions about pricing and availability",
        "Help with order placement",
        "Provide product recommendations",
        "Check order status",
        "Book appointments",
        "Process payments"
    ]
    
    num_capabilities = draw(st.integers(min_value=2, max_value=5))
    selected = draw(st.lists(
        st.sampled_from(capabilities),
        min_size=num_capabilities,
        max_size=num_capabilities,
        unique=True
    ))
    
    return "I can help you with:\n" + "\n".join([f"- {cap}" for cap in selected])


@st.composite
def agent_limitations(draw):
    """Generate agent limitations text."""
    limitations = [
        "Process refunds (please contact support)",
        "Modify existing orders (please contact support)",
        "Provide medical advice",
        "Make legal recommendations",
        "Access your account password",
        "Cancel subscriptions"
    ]
    
    num_limitations = draw(st.integers(min_value=2, max_value=4))
    selected = draw(st.lists(
        st.sampled_from(limitations),
        min_size=num_limitations,
        max_size=num_limitations,
        unique=True
    ))
    
    return "I cannot:\n" + "\n".join([f"- {lim}" for lim in selected])


@pytest.mark.django_db(transaction=True)
class TestBrandedIdentityProperty:
    """Property-based tests for branded identity."""
    
    @given(
        biz_name=business_name(),
        bot_name=agent_name(),
        lang=language_code()
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_business_name_in_identity(self, biz_name, bot_name, lang, django_db_blocker):
        """
        Property: Bot identity always includes business name.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        with django_db_blocker.unblock():
            # Create tenant with business name
            tenant = Tenant.objects.create(
                name=biz_name,
                slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
                whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
            )
            
            try:
                # Create agent configuration
                agent_config = AgentConfiguration.objects.create(
                    tenant=tenant,
                    agent_name=bot_name,
                    use_business_name_as_identity=True
                )
                
                # Build branded persona
                builder = BrandedPersonaBuilder()
                system_prompt = builder.build_system_prompt(tenant, agent_config, lang)
                
                # Property: Business name MUST appear in the system prompt
                assert biz_name in system_prompt, \
                    f"Business name '{biz_name}' should appear in system prompt"
                
                # Property: Should not use generic "Assistant" alone without business context
                # (unless that's the actual business name)
                if bot_name == "Assistant" and "Assistant" not in biz_name:
                    # Should use "BusinessName Assistant" format
                    expected_name = f"{biz_name} Assistant"
                    assert expected_name in system_prompt, \
                        f"Should use '{expected_name}' format, not 'Assistant' alone"
                
                # Property: Introduction message should also include business name
                intro = builder.get_introduction_message(tenant, agent_config, lang)
                assert biz_name in intro, \
                    f"Business name '{biz_name}' should appear in introduction message"
                
            finally:
                # Cleanup
                tenant.delete()
    
    @given(
        biz_name=business_name(),
        bot_name=agent_name(),
        capabilities=agent_capabilities(),
        limitations=agent_limitations(),
        lang=language_code()
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_capabilities_and_limitations_included(
        self,
        biz_name,
        bot_name,
        capabilities,
        limitations,
        lang
    ):
        """
        Property: Agent capabilities and limitations are included in prompt.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        # Create tenant
        tenant = Tenant.objects.create(
            name=biz_name,
            slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration with capabilities and limitations
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name=bot_name,
                use_business_name_as_identity=True,
                agent_can_do=capabilities,
                agent_cannot_do=limitations
            )
            
            # Build branded persona
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, lang)
            
            # Property: Capabilities section should be present
            if lang == 'sw':
                assert "Unachoweza Kufanya" in system_prompt or "CAN" in system_prompt, \
                    "Capabilities section should be present"
            else:
                assert "What You CAN Do" in system_prompt or "CAN" in system_prompt, \
                    "Capabilities section should be present"
            
            # Property: Limitations section should be present
            if lang == 'sw':
                assert "Unachokosa Kufanya" in system_prompt or "CANNOT" in system_prompt, \
                    "Limitations section should be present"
            else:
                assert "What You CANNOT Do" in system_prompt or "CANNOT" in system_prompt, \
                    "Limitations section should be present"
            
            # Property: Actual capabilities text should be included
            # (at least some keywords from it)
            capability_keywords = ["help", "Browse", "Answer", "Check", "Book", "Process"]
            has_capability_keyword = any(
                keyword.lower() in system_prompt.lower()
                for keyword in capability_keywords
            )
            assert has_capability_keyword, \
                "System prompt should include capability keywords"
            
        finally:
            # Cleanup
            tenant.delete()
    
    @given(
        biz_name=business_name(),
        use_business_identity=st.booleans()
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_business_identity_flag_respected(self, biz_name, use_business_identity):
        """
        Property: use_business_name_as_identity flag is respected.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        # Create tenant
        tenant = Tenant.objects.create(
            name=biz_name,
            slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="CustomBot",
                use_business_name_as_identity=use_business_identity
            )
            
            # Build branded persona
            builder = BrandedPersonaBuilder()
            bot_display_name = builder.get_bot_name(tenant, agent_config)
            
            # Property: If use_business_name_as_identity is True, name should reference business
            # If False, should use custom name
            if use_business_identity:
                # Should use custom name but business name should still appear in prompt
                system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
                assert biz_name in system_prompt, \
                    "Business name should appear even with custom bot name"
            else:
                # Custom bot name should be used
                assert bot_display_name == "CustomBot", \
                    f"Should use custom bot name, got {bot_display_name}"
            
        finally:
            # Cleanup
            tenant.delete()
    
    @given(
        biz_name=business_name(),
        lang=language_code()
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_language_specific_branding(self, biz_name, lang):
        """
        Property: Branding adapts to conversation language.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        # Create tenant
        tenant = Tenant.objects.create(
            name=biz_name,
            slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            # Build branded persona in specified language
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, lang)
            intro = builder.get_introduction_message(tenant, agent_config, lang)
            
            # Property: Business name should appear regardless of language
            assert biz_name in system_prompt, \
                f"Business name should appear in {lang} prompt"
            assert biz_name in intro, \
                f"Business name should appear in {lang} introduction"
            
            # Property: Language-specific keywords should be present
            if lang == 'sw':
                # Swahili keywords
                swahili_keywords = ["Wewe ni", "msaidizi", "Habari", "Mimi ni"]
                has_swahili = any(keyword in intro or keyword in system_prompt 
                                 for keyword in swahili_keywords)
                assert has_swahili, \
                    "Swahili language prompt should contain Swahili keywords"
            else:
                # English keywords
                english_keywords = ["You are", "assistant", "Hello", "I'm", "I am"]
                has_english = any(keyword in intro or keyword in system_prompt 
                                 for keyword in english_keywords)
                assert has_english, \
                    "English language prompt should contain English keywords"
            
        finally:
            # Cleanup
            tenant.delete()
    
    @given(
        biz_name=business_name(),
        custom_greeting=st.text(min_size=10, max_size=200)
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_custom_greeting_used(self, biz_name, custom_greeting):
        """
        Property: Custom greeting is used when configured.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        # Create tenant
        tenant = Tenant.objects.create(
            name=biz_name,
            slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration with custom greeting
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True,
                custom_bot_greeting=custom_greeting
            )
            
            # Get introduction message
            builder = BrandedPersonaBuilder()
            intro = builder.get_introduction_message(tenant, agent_config, 'en')
            
            # Property: Custom greeting should be used
            assert intro == custom_greeting, \
                f"Should use custom greeting, got: {intro}"
            
        finally:
            # Cleanup
            tenant.delete()
    
    @given(
        biz_name=business_name(),
        tone=st.sampled_from(['professional', 'friendly', 'casual', 'formal'])
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_tone_reflected_in_prompt(self, biz_name, tone):
        """
        Property: Configured tone is reflected in system prompt.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        # Create tenant
        tenant = Tenant.objects.create(
            name=biz_name,
            slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration with specific tone
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True,
                tone=tone
            )
            
            # Build branded persona
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            
            # Property: Tone keyword should appear in prompt
            tone_keywords = {
                'professional': ['professional', 'business'],
                'friendly': ['friendly', 'warm', 'approachable'],
                'casual': ['casual', 'conversational', 'informal'],
                'formal': ['formal', 'etiquette']
            }
            
            expected_keywords = tone_keywords[tone]
            has_tone_keyword = any(
                keyword.lower() in system_prompt.lower()
                for keyword in expected_keywords
            )
            
            assert has_tone_keyword, \
                f"System prompt should reflect {tone} tone with keywords: {expected_keywords}"
            
        finally:
            # Cleanup
            tenant.delete()
    
    @given(
        biz_name=business_name()
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_no_generic_assistant_alone(self, biz_name):
        """
        Property: Never use "Assistant" alone without business context.
        
        **Feature: conversational-commerce-ux-enhancement, Property 7: Branded identity**
        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        # Create tenant
        tenant = Tenant.objects.create(
            name=biz_name,
            slug=f"test-{biz_name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            whatsapp_number=f"+25471234{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration with default "Assistant" name
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            # Build branded persona
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            intro = builder.get_introduction_message(tenant, agent_config, 'en')
            
            # Property: Should NOT have "Assistant" without business name context
            # Check that business name appears near "Assistant"
            assert biz_name in system_prompt, \
                "Business name must appear in prompt"
            assert biz_name in intro, \
                "Business name must appear in introduction"
            
            # Property: Bot name should include business name
            bot_name = builder.get_bot_name(tenant, agent_config)
            assert biz_name in bot_name, \
                f"Bot name '{bot_name}' should include business name '{biz_name}'"
            
        finally:
            # Cleanup
            tenant.delete()
