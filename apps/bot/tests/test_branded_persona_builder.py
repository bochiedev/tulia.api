"""
Unit tests for BrandedPersonaBuilder service.

Tests the branded persona builder functionality without property-based testing
to ensure basic functionality works correctly.
"""
import pytest
from django.utils import timezone

from apps.bot.services.branded_persona_builder import BrandedPersonaBuilder
from apps.bot.models import AgentConfiguration
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestBrandedPersonaBuilder:
    """Unit tests for BrandedPersonaBuilder."""
    
    def test_business_name_in_system_prompt(self):
        """Test that business name appears in system prompt."""
        # Create tenant
        tenant = Tenant.objects.create(
            name="TechMart Store",
            slug=f"techmart-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            # Create agent configuration
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            # Build branded persona
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            
            # Assert business name appears
            assert "TechMart Store" in system_prompt
            
        finally:
            tenant.delete()
    
    def test_bot_name_includes_business_name(self):
        """Test that bot name includes business name when using default Assistant."""
        tenant = Tenant.objects.create(
            name="FashionHub",
            slug=f"fashionhub-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            builder = BrandedPersonaBuilder()
            bot_name = builder.get_bot_name(tenant, agent_config)
            
            # Should be "FashionHub Assistant"
            assert "FashionHub" in bot_name
            assert bot_name == "FashionHub Assistant"
            
        finally:
            tenant.delete()
    
    def test_introduction_message_includes_business_name(self):
        """Test that introduction message includes business name."""
        tenant = Tenant.objects.create(
            name="BookWorld",
            slug=f"bookworld-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            builder = BrandedPersonaBuilder()
            intro = builder.get_introduction_message(tenant, agent_config, 'en')
            
            # Should mention BookWorld
            assert "BookWorld" in intro
            
        finally:
            tenant.delete()
    
    def test_capabilities_included_in_prompt(self):
        """Test that agent capabilities are included in system prompt."""
        tenant = Tenant.objects.create(
            name="GadgetZone",
            slug=f"gadgetzone-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            capabilities = "I can help you with:\n- Browse products\n- Check prices\n- Place orders"
            
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True,
                agent_can_do=capabilities
            )
            
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            
            # Should include capabilities section
            assert "What You CAN Do" in system_prompt or "CAN" in system_prompt
            assert "Browse products" in system_prompt
            
        finally:
            tenant.delete()
    
    def test_limitations_included_in_prompt(self):
        """Test that agent limitations are included in system prompt."""
        tenant = Tenant.objects.create(
            name="StyleCorner",
            slug=f"stylecorner-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            limitations = "I cannot:\n- Process refunds\n- Modify orders"
            
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True,
                agent_cannot_do=limitations
            )
            
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            
            # Should include limitations section
            assert "What You CANNOT Do" in system_prompt or "CANNOT" in system_prompt
            assert "Process refunds" in system_prompt
            
        finally:
            tenant.delete()
    
    def test_swahili_language_support(self):
        """Test that Swahili language is supported."""
        tenant = Tenant.objects.create(
            name="Duka Langu",
            slug=f"dukalangu-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'sw')
            intro = builder.get_introduction_message(tenant, agent_config, 'sw')
            
            # Should have Swahili keywords
            assert "Wewe ni" in system_prompt or "msaidizi" in system_prompt
            assert "Habari" in intro or "Mimi ni" in intro
            assert "Duka Langu" in intro
            
        finally:
            tenant.delete()
    
    def test_custom_greeting_used(self):
        """Test that custom greeting is used when configured."""
        tenant = Tenant.objects.create(
            name="PetCare",
            slug=f"petcare-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            custom_greeting = "Welcome to PetCare! How can I help your furry friend today?"
            
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True,
                custom_bot_greeting=custom_greeting
            )
            
            builder = BrandedPersonaBuilder()
            intro = builder.get_introduction_message(tenant, agent_config, 'en')
            
            # Should use custom greeting
            assert intro == custom_greeting
            
        finally:
            tenant.delete()
    
    def test_tone_reflected_in_prompt(self):
        """Test that configured tone is reflected in system prompt."""
        tenant = Tenant.objects.create(
            name="AutoParts",
            slug=f"autoparts-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True,
                tone='professional'
            )
            
            builder = BrandedPersonaBuilder()
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            
            # Should mention professional tone
            assert "professional" in system_prompt.lower()
            
        finally:
            tenant.delete()
    
    def test_no_generic_assistant_alone(self):
        """Test that we don't use 'Assistant' alone without business context."""
        tenant = Tenant.objects.create(
            name="GreenGarden",
            slug=f"greengarden-{timezone.now().timestamp()}",
            whatsapp_number=f"+254712345{timezone.now().microsecond % 10000:04d}"
        )
        
        try:
            agent_config = AgentConfiguration.objects.create(
                tenant=tenant,
                agent_name="Assistant",
                use_business_name_as_identity=True
            )
            
            builder = BrandedPersonaBuilder()
            bot_name = builder.get_bot_name(tenant, agent_config)
            system_prompt = builder.build_system_prompt(tenant, agent_config, 'en')
            intro = builder.get_introduction_message(tenant, agent_config, 'en')
            
            # Bot name should include business name
            assert "GreenGarden" in bot_name
            
            # Business name should appear in prompt and intro
            assert "GreenGarden" in system_prompt
            assert "GreenGarden" in intro
            
        finally:
            tenant.delete()
