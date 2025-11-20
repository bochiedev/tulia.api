"""
Branded Persona Builder Service for creating tenant-specific bot personas.

This service builds system prompts that incorporate tenant branding,
business identity, and agent capabilities/limitations.
"""
import logging
from typing import Optional
from apps.bot.models import AgentConfiguration
from apps.tenants.models import Tenant


logger = logging.getLogger(__name__)


class BrandedPersonaBuilder:
    """
    Service for building branded bot personas.
    
    Creates system prompts that:
    - Use tenant's business name in bot identity
    - Include agent capabilities (what bot CAN do)
    - Include agent limitations (what bot CANNOT do)
    - Maintain consistent branding throughout conversation
    """
    
    def build_system_prompt(
        self,
        tenant: Tenant,
        agent_config: AgentConfiguration,
        language: str = 'en'
    ) -> str:
        """
        Build system prompt with tenant branding.
        
        Creates a branded system prompt that identifies the bot with the
        tenant's business name and includes clear capabilities and limitations.
        
        Args:
            tenant: Tenant instance with business information
            agent_config: AgentConfiguration with persona settings
            language: Language code for the prompt ('en' or 'sw')
            
        Returns:
            Complete branded system prompt string
        """
        sections = []
        
        # Build bot identity with business name
        identity = self._build_identity_section(tenant, agent_config, language)
        sections.append(identity)
        
        # Add capabilities section
        if agent_config.agent_can_do:
            capabilities = self._build_capabilities_section(
                agent_config.agent_can_do,
                language
            )
            sections.append(capabilities)
        
        # Add limitations section
        if agent_config.agent_cannot_do:
            limitations = self._build_limitations_section(
                agent_config.agent_cannot_do,
                language
            )
            sections.append(limitations)
        
        # Add tone and personality guidance
        personality = self._build_personality_section(agent_config, language)
        sections.append(personality)
        
        # Add response guidelines
        guidelines = self._build_response_guidelines(agent_config, language)
        sections.append(guidelines)
        
        # Combine all sections
        prompt = "\n\n".join(sections)
        
        logger.debug(
            f"Built branded system prompt for tenant {tenant.id} "
            f"(business: {tenant.name}, language: {language})"
        )
        
        return prompt
    
    def _build_identity_section(
        self,
        tenant: Tenant,
        agent_config: AgentConfiguration,
        language: str
    ) -> str:
        """
        Build bot identity section with business name.
        
        Args:
            tenant: Tenant instance
            agent_config: AgentConfiguration instance
            language: Language code
            
        Returns:
            Identity section text
        """
        business_name = tenant.name
        business_mention = False
        
        # Determine bot name
        if agent_config.use_business_name_as_identity:
            # Use business name + "Assistant" if custom name not set
            if agent_config.agent_name == 'Assistant':
                bot_name = f"{business_name} Assistant"
            else:
                # Use custom bot name but mention business
                bot_name = agent_config.agent_name
                business_mention = True
        else:
            # Use custom agent name without business name
            bot_name = agent_config.agent_name
        
        if language == 'sw':
            if agent_config.use_business_name_as_identity and business_mention:
                return (
                    f"Wewe ni {bot_name}, msaidizi wa AI wa {business_name}. "
                    f"Unasaidia wateja kupata bidhaa na huduma kutoka {business_name}."
                )
            else:
                return (
                    f"Wewe ni {bot_name}, msaidizi wa AI wa {business_name}. "
                    f"Unasaidia wateja kupata bidhaa na huduma."
                )
        else:
            if agent_config.use_business_name_as_identity and business_mention:
                return (
                    f"You are {bot_name}, an AI assistant for {business_name}. "
                    f"You help customers discover products and services from {business_name}."
                )
            else:
                return (
                    f"You are {bot_name}, an AI assistant for {business_name}. "
                    f"You help customers discover products and services."
                )
    
    def _build_capabilities_section(
        self,
        capabilities: str,
        language: str
    ) -> str:
        """
        Build capabilities section.
        
        Args:
            capabilities: Text describing what agent CAN do
            language: Language code
            
        Returns:
            Capabilities section text
        """
        if language == 'sw':
            header = "## Unachoweza Kufanya"
        else:
            header = "## What You CAN Do"
        
        return f"{header}\n\n{capabilities}"
    
    def _build_limitations_section(
        self,
        limitations: str,
        language: str
    ) -> str:
        """
        Build limitations section.
        
        Args:
            limitations: Text describing what agent CANNOT do
            language: Language code
            
        Returns:
            Limitations section text
        """
        if language == 'sw':
            header = "## Unachokosa Kufanya"
        else:
            header = "## What You CANNOT Do"
        
        return f"{header}\n\n{limitations}"
    
    def _build_personality_section(
        self,
        agent_config: AgentConfiguration,
        language: str
    ) -> str:
        """
        Build personality and tone section.
        
        Args:
            agent_config: AgentConfiguration instance
            language: Language code
            
        Returns:
            Personality section text
        """
        sections = []
        
        # Add tone guidance
        tone_guidance = {
            'professional': {
                'en': "Maintain a professional and business-like tone.",
                'sw': "Tumia lugha ya kitaaluma na ya kibiashara."
            },
            'friendly': {
                'en': "Be warm, friendly, and approachable in your responses.",
                'sw': "Kuwa rafiki, wa kupendeza na wa karibu katika majibu yako."
            },
            'casual': {
                'en': "Use a casual, conversational tone. Feel free to be informal.",
                'sw': "Tumia lugha ya kawaida na ya mazungumzo. Unaweza kuwa wa kawaida."
            },
            'formal': {
                'en': "Use formal language and maintain proper etiquette at all times.",
                'sw': "Tumia lugha rasmi na shika adabu sahihi wakati wote."
            }
        }
        
        if agent_config.tone in tone_guidance:
            tone_text = tone_guidance[agent_config.tone].get(language, 
                                                              tone_guidance[agent_config.tone]['en'])
            sections.append(tone_text)
        
        # Add personality traits
        if agent_config.personality_traits:
            traits_list = [
                f"{trait}: {value}"
                for trait, value in agent_config.personality_traits.items()
            ]
            if traits_list:
                if language == 'sw':
                    sections.append(f"Sifa zako za utu: {', '.join(traits_list)}")
                else:
                    sections.append(f"Your personality traits: {', '.join(traits_list)}")
        
        # Add behavioral restrictions
        if agent_config.behavioral_restrictions:
            restrictions = ', '.join(agent_config.behavioral_restrictions)
            if language == 'sw':
                sections.append(
                    f"Mada za kuepuka: {restrictions}. "
                    "Ikiwa unaulizwa kuhusu mada hizi, kataa kwa upole na toa msaada kwa kitu kingine."
                )
            else:
                sections.append(
                    f"Topics to avoid: {restrictions}. "
                    "If asked about these topics, politely decline and offer to help with something else."
                )
        
        return "\n\n".join(sections)
    
    def _build_response_guidelines(
        self,
        agent_config: AgentConfiguration,
        language: str
    ) -> str:
        """
        Build response guidelines section.
        
        Args:
            agent_config: AgentConfiguration instance
            language: Language code
            
        Returns:
            Guidelines section text
        """
        sections = []
        
        # Response length guidance
        if language == 'sw':
            sections.append(
                f"Weka majibu yako mafupi, chini ya herufi {agent_config.max_response_length} inapowezekana."
            )
        else:
            sections.append(
                f"Keep responses concise, under {agent_config.max_response_length} characters when possible."
            )
        
        # Handoff guidance
        if language == 'sw':
            sections.append(
                f"Ikiwa ujuzi wako ni chini ya {agent_config.confidence_threshold:.0%}, "
                "au ikiwa mada inahitaji ujuzi wa binadamu, toa kuunganisha mteja na wakala wa binadamu."
            )
        else:
            sections.append(
                f"If your confidence is below {agent_config.confidence_threshold:.0%}, "
                "or if the topic requires human expertise, offer to connect the customer with a human agent."
            )
        
        # Required disclaimers
        if agent_config.required_disclaimers:
            disclaimers = '\n'.join([f"- {d}" for d in agent_config.required_disclaimers])
            if language == 'sw':
                sections.append(f"Daima jumuisha maelezo haya yanapohusika:\n{disclaimers}")
            else:
                sections.append(f"Always include these disclaimers when relevant:\n{disclaimers}")
        
        return "\n\n".join(sections)
    
    def get_bot_name(
        self,
        tenant: Tenant,
        agent_config: AgentConfiguration
    ) -> str:
        """
        Get the bot's display name for this tenant.
        
        Args:
            tenant: Tenant instance
            agent_config: AgentConfiguration instance
            
        Returns:
            Bot display name
        """
        if agent_config.use_business_name_as_identity:
            if agent_config.agent_name == 'Assistant':
                return f"{tenant.name} Assistant"
            else:
                return agent_config.agent_name
        else:
            return agent_config.agent_name
    
    def get_introduction_message(
        self,
        tenant: Tenant,
        agent_config: AgentConfiguration,
        language: str = 'en'
    ) -> str:
        """
        Get branded introduction message for first contact.
        
        Args:
            tenant: Tenant instance
            agent_config: AgentConfiguration instance
            language: Language code
            
        Returns:
            Introduction message text
        """
        bot_name = self.get_bot_name(tenant, agent_config)
        business_name = tenant.name
        
        # Use custom greeting if configured
        if agent_config.custom_bot_greeting:
            return agent_config.custom_bot_greeting
        
        # Generate default greeting
        if language == 'sw':
            return (
                f"Habari! Mimi ni {bot_name}. "
                f"Ninasaidia wateja wa {business_name} kupata bidhaa na huduma. "
                f"Naweza kukusaidia vipi leo?"
            )
        else:
            return (
                f"Hello! I'm {bot_name}. "
                f"I help {business_name} customers discover products and services. "
                f"How can I assist you today?"
            )


def create_branded_persona_builder() -> BrandedPersonaBuilder:
    """
    Factory function to create BrandedPersonaBuilder instance.
    
    Returns:
        BrandedPersonaBuilder instance
    """
    return BrandedPersonaBuilder()
