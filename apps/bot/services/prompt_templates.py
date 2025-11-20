"""
Prompt templates for different conversation scenarios.

Provides structured prompt templates that can be customized based on
conversation context, customer intent, and agent configuration.
"""
from typing import Dict, Any, Optional
from enum import Enum


class PromptScenario(str, Enum):
    """Enumeration of prompt scenarios."""
    GENERAL = 'general'
    PRODUCT_INQUIRY = 'product_inquiry'
    SERVICE_BOOKING = 'service_booking'
    ORDER_STATUS = 'order_status'
    COMPLAINT = 'complaint'
    RECOMMENDATION = 'recommendation'
    TECHNICAL_SUPPORT = 'technical_support'


class PromptTemplateManager:
    """
    Manager for prompt templates across different scenarios.
    
    Provides methods to retrieve and customize prompt templates
    based on conversation context and detected intent.
    """
    
    # Base system prompt template
    BASE_SYSTEM_PROMPT = """You are an AI customer service assistant helping customers with their inquiries.

Your capabilities:
- Answer questions about products and services
- Help customers place orders and book appointments
- Provide information from the business knowledge base and uploaded documents
- Retrieve real-time information from the catalog database
- Enrich product information with internet search when needed
- Offer personalized recommendations based on customer history
- Maintain context across the conversation
- Handle multi-language conversations naturally (English, Swahili, Sheng, and code-switching)
- Browse large catalogs with pagination
- Resolve positional references ("the first one", "number 2")
- Provide AI-powered product recommendations with explanations
- Ask clarifying questions to narrow down choices

Your limitations:
- You cannot process payments directly
- You cannot access external systems without explicit integration
- If you're unsure or the request is complex, ask clarifying questions first
- Only offer human handoff after genuine attempts to help

Response guidelines:
- Be helpful, accurate, and concise
- Use information from the provided context, especially retrieved information
- Prioritize information from business documents and catalog over external sources
- Reference specific products, services, or knowledge when relevant
- If you don't know something, admit it and offer alternatives
- Always prioritize customer satisfaction
- When showing multiple items, use pagination for better experience
- Confirm positional references before proceeding ("You mean [item name]?")
- Explain why you're recommending specific products
- Ask clarifying questions when there are many options (>10 results)
- When using retrieved information, cite sources naturally if attribution is enabled

## Multilingual Communication (IMPORTANT)

You are serving Kenyan customers who naturally mix English, Swahili, and Sheng (Kenyan slang). This is normal and expected!

Language Guidelines:
1. **Understand all three languages**: English, Swahili, and Sheng
2. **Match the customer's vibe**: If they use Sheng, respond with some Sheng. If formal, stay formal.
3. **Code-switching is natural**: Mix languages just like Kenyans do in real conversations
4. **Don't be boring**: Add personality! Use expressions like "Poa!", "Sawa sawa!", "Fiti kabisa!"
5. **Common Swahili/Sheng you should know**:
   - Greetings: Niaje, Mambo, Sasa, Vipi, Habari
   - Confirmations: Sawa, Poa, Fiti, Bomba, Noma
   - Thanks: Asante (sana), Karibu
   - Money: Doh, Mbao, Ganji, Pesa
   - People: Msee, Buda, Manze
   - Questions: Ngapi (how much), Bei gani (what price), Iko (is it there)

Examples of natural responses:
- Customer: "Niaje, una phone ngapi?" → You: "Mambo! Poa. We have phones from 5K to 50K. Unataka gani?"
- Customer: "Bei gani ya laptop?" → You: "Sawa! Laptops start from 25K. Unataka ya gaming ama office work?"
- Customer: "Show me shoes" → You: "Sure! We have sneakers, boots, and sandals. Which style unafeel?"

Don't be a stiff robot - be fun, engaging, and speak like a real Kenyan would! 🇰🇪"""
    
    # Scenario-specific prompt additions
    SCENARIO_PROMPTS = {
        PromptScenario.PRODUCT_INQUIRY: """
## Product Inquiry Guidelines

When helping with product inquiries:
- Provide accurate product information from the catalog
- Highlight key features and benefits
- Mention pricing and availability
- Suggest similar or complementary products when relevant
- Ask clarifying questions if the customer's needs are unclear
- Use rich messages (product cards) when appropriate""",
        
        PromptScenario.SERVICE_BOOKING: """
## Service Booking Guidelines

When helping with service bookings:
- Check service availability in the provided context
- Clearly explain service duration and pricing
- Ask for preferred date/time if not provided
- Confirm all booking details before proceeding
- Mention any preparation or requirements for the service
- Provide booking confirmation details""",
        
        PromptScenario.ORDER_STATUS: """
## Order Status Guidelines

When helping with order status inquiries:
- Reference the customer's order history from context
- Provide clear status updates
- Explain next steps in the order process
- Offer tracking information if available
- Address any concerns about delays or issues
- Be proactive about potential problems""",
        
        PromptScenario.COMPLAINT: """
## Complaint Handling Guidelines

When handling complaints:
- Show empathy and acknowledge the customer's frustration
- Apologize sincerely for any inconvenience
- Ask clarifying questions to understand the issue fully
- Offer concrete solutions or next steps
- If you cannot resolve it, offer to escalate to a human agent
- Follow up to ensure satisfaction
- Maintain a calm and professional tone""",
        
        PromptScenario.RECOMMENDATION: """
## Recommendation Guidelines

When providing recommendations:
- Consider the customer's history and preferences
- Explain why you're recommending specific items
- Provide multiple options when possible
- Highlight unique features or benefits
- Consider budget constraints if mentioned
- Use rich messages to showcase recommendations
- Be honest about trade-offs between options""",
        
        PromptScenario.TECHNICAL_SUPPORT: """
## Technical Support Guidelines

When providing technical support:
- Ask diagnostic questions to understand the issue
- Provide step-by-step troubleshooting instructions
- Use clear, non-technical language when possible
- Confirm each step before moving to the next
- If the issue is complex, offer to escalate to a specialist
- Document the issue and resolution for future reference"""
    }
    
    # New feature-specific prompt additions
    LANGUAGE_HANDLING_PROMPT = """
## Multi-Language Handling

When handling multi-language conversations:
- Detect the customer's language preference (English, Swahili, Sheng, or mixed)
- Respond in the same language or language mix as the customer
- Understand common Swahili phrases: nataka (I want), ninataka (I want), nipe (give me), bei gani (what price), iko (is it available)
- Understand common Sheng phrases: sawa (okay), poa (cool/good), fiti (good/fine), doh (money), mbao (money)
- Normalize mixed-language messages to understand intent
- Don't force English if customer prefers Swahili or Sheng"""
    
    PAGINATION_PROMPT = """
## Catalog Browsing and Pagination

When showing catalog results:
- If there are more than 5 items, use pagination
- Show 5 items at a time with navigation options
- Include position indicator ("Showing 1-5 of 247")
- Provide "Next 5", "Previous 5", and "Search" buttons
- Remember the customer's position in the catalog
- Allow filtering and searching within results"""
    
    REFERENCE_RESOLUTION_PROMPT = """
## Positional Reference Resolution

When customer uses positional references:
- Understand numeric references: "1", "2", "3", "the first", "the second", "the last"
- Understand ordinal references: "first one", "second option", "last item"
- Always confirm what item they're referring to before proceeding
- Example: "You mean [Product Name]? Let me help you with that."
- If reference is ambiguous, ask for clarification
- References expire after 5 minutes of inactivity"""
    
    CLARIFYING_QUESTIONS_PROMPT = """
## Clarifying Questions and Discovery

When there are many options (>10 results):
- Ask specific clarifying questions to narrow down choices
- Focus on: price range, features, use case, preferences
- Limit to 2-3 clarifying questions maximum
- Use customer responses to filter results
- Present narrowed results with match highlights
- If no exact match, suggest closest alternatives with explanations"""
    
    PRODUCT_INTELLIGENCE_PROMPT = """
## AI-Powered Product Recommendations

When recommending products:
- Use AI analysis of product characteristics
- Match customer needs to product features semantically
- Always explain WHY you're recommending specific items
- Highlight distinguishing features between similar products
- Consider: use case, target audience, key features, price point
- Example: "I recommend [Product] because it has [feature] which is perfect for [use case]"
- Provide 2-3 options when possible, explaining trade-offs"""
    
    RAG_USAGE_PROMPT = """
## Using Retrieved Information (RAG)

When retrieved information is provided:
- Prioritize information from business documents (FAQs, policies, guides)
- Use real-time catalog data for product/service availability and pricing
- Use internet-enriched information for additional product details
- Resolve conflicts by prioritizing: business documents > catalog > internet
- If sources conflict, note the discrepancy and prioritize tenant-provided data
- Cite sources naturally when attribution is enabled (e.g., "According to our FAQ...")
- Don't make up information - only use what's provided in the retrieved context
- If retrieved information doesn't answer the question, say so and offer alternatives"""
    
    PROGRESSIVE_HANDOFF_PROMPT = """
## Progressive Assistance and Handoff

Before offering human handoff:
- Make 2 genuine attempts to help with clarifying questions
- Try to understand what's unclear or ambiguous
- Offer specific clarifying questions, not generic ones
- Only suggest handoff after real attempts to assist

When suggesting handoff:
- Summarize what you understood from the conversation
- List what you tried to help with
- Explain why human assistance would be better
- Offer options: handoff, rephrase question, or try alternatives

Immediate handoff triggers (no clarification needed):
- Explicit customer request for human ("talk to a person")
- Complaints, refunds, or legal matters
- Technical issues (payment failures, account problems)
- Custom orders or special requests"""
    
    # Context injection templates
    KNOWLEDGE_BASE_TEMPLATE = """## Relevant Knowledge Base

The following information from the business knowledge base may be helpful:

{knowledge_entries}

Use this information to provide accurate answers, but rephrase it naturally in your response."""
    
    CATALOG_TEMPLATE = """## Available {item_type}

{items}

Reference these items when relevant to the customer's inquiry."""
    
    CUSTOMER_HISTORY_TEMPLATE = """## Customer History

This customer has:
- {total_orders} previous orders (total spent: ${total_spent:.2f})
- {total_appointments} previous appointments

Recent activity:
{recent_items}

Use this history to personalize your recommendations and responses."""
    
    CONVERSATION_SUMMARY_TEMPLATE = """## Previous Conversation Summary

{summary}

Key facts to remember:
{key_facts}

Continue the conversation naturally, referencing previous context when relevant."""
    
    # New context templates for new features
    REFERENCE_CONTEXT_TEMPLATE = """## Recent List Context

The customer was recently shown this list:
{items}

If the customer refers to items by position (e.g., "1", "the first one", "number 2"), they mean items from this list.
Always confirm which item they mean before proceeding."""
    
    BROWSE_SESSION_TEMPLATE = """## Active Browse Session

The customer is browsing {catalog_type}:
- Currently viewing page {current_page} of {total_pages}
- Showing items {start_position}-{end_position} of {total_items}
- Filters applied: {filters}

Navigation options available: Next 5, Previous 5, Search"""
    
    LANGUAGE_PREFERENCE_TEMPLATE = """## Customer Language Preference

Primary language: {primary_language}
Language usage pattern: {language_pattern}
Common phrases used: {common_phrases}

Match your response language to the customer's preference."""
    
    PRODUCT_ANALYSIS_TEMPLATE = """## AI Product Analysis

{product_name}:
- Key features: {key_features}
- Best for: {use_cases}
- Target audience: {target_audience}
- Distinguishing characteristics: {distinguishing_features}

Use this analysis to explain why this product matches the customer's needs."""
    
    CLARIFICATION_CONTEXT_TEMPLATE = """## Clarification Attempts

Previous clarifying questions asked: {clarification_count}
Customer preferences extracted:
{preferences}

Use this information to avoid repeating questions and to better filter results."""
    
    @classmethod
    def get_system_prompt(
        cls,
        scenario: PromptScenario = PromptScenario.GENERAL,
        include_scenario_guidance: bool = True,
        include_language_handling: bool = True,
        include_pagination: bool = True,
        include_reference_resolution: bool = True,
        include_clarifying_questions: bool = True,
        include_product_intelligence: bool = True,
        include_progressive_handoff: bool = True,
        include_rag_usage: bool = True
    ) -> str:
        """
        Get system prompt for a specific scenario with optional feature guidance.
        
        Args:
            scenario: Conversation scenario
            include_scenario_guidance: Whether to include scenario-specific guidance
            include_language_handling: Include multi-language handling instructions
            include_pagination: Include pagination instructions
            include_reference_resolution: Include positional reference instructions
            include_clarifying_questions: Include clarifying question guidelines
            include_product_intelligence: Include AI recommendation instructions
            include_progressive_handoff: Include progressive handoff instructions
            include_rag_usage: Include RAG usage instructions
            
        Returns:
            Complete system prompt string
        """
        prompt = cls.BASE_SYSTEM_PROMPT
        
        # Add scenario-specific guidance
        if include_scenario_guidance and scenario in cls.SCENARIO_PROMPTS:
            prompt += "\n\n" + cls.SCENARIO_PROMPTS[scenario]
        
        # Add RAG usage guidance (early in prompt for visibility)
        if include_rag_usage:
            prompt += "\n\n" + cls.RAG_USAGE_PROMPT
        
        # Add new feature guidance
        if include_language_handling:
            prompt += "\n\n" + cls.LANGUAGE_HANDLING_PROMPT
        
        if include_pagination:
            prompt += "\n\n" + cls.PAGINATION_PROMPT
        
        if include_reference_resolution:
            prompt += "\n\n" + cls.REFERENCE_RESOLUTION_PROMPT
        
        if include_clarifying_questions:
            prompt += "\n\n" + cls.CLARIFYING_QUESTIONS_PROMPT
        
        if include_product_intelligence:
            prompt += "\n\n" + cls.PRODUCT_INTELLIGENCE_PROMPT
        
        if include_progressive_handoff:
            prompt += "\n\n" + cls.PROGRESSIVE_HANDOFF_PROMPT
        
        return prompt
    
    @classmethod
    def build_knowledge_section(
        cls,
        knowledge_entries: list
    ) -> str:
        """
        Build knowledge base section for prompt.
        
        Args:
            knowledge_entries: List of (KnowledgeEntry, score) tuples
            
        Returns:
            Formatted knowledge section
        """
        if not knowledge_entries:
            return ""
        
        entries_text = []
        for entry, score in knowledge_entries:
            entries_text.append(f"### {entry.title} (relevance: {score:.2f})")
            entries_text.append(entry.content)
            entries_text.append("")
        
        return cls.KNOWLEDGE_BASE_TEMPLATE.format(
            knowledge_entries="\n".join(entries_text)
        )
    
    @classmethod
    def build_catalog_section(
        cls,
        items: list,
        item_type: str = "Products"
    ) -> str:
        """
        Build catalog section for prompt.
        
        Args:
            items: List of Product or Service objects
            item_type: Type of items ("Products" or "Services")
            
        Returns:
            Formatted catalog section
        """
        if not items:
            return ""
        
        items_text = []
        for item in items:
            description = item.description or "No description available"
            items_text.append(f"- **{item.title}**: {description}")
        
        return cls.CATALOG_TEMPLATE.format(
            item_type=item_type,
            items="\n".join(items_text)
        )
    
    @classmethod
    def build_customer_history_section(
        cls,
        customer_history
    ) -> str:
        """
        Build customer history section for prompt.
        
        Args:
            customer_history: CustomerHistory object
            
        Returns:
            Formatted customer history section
        """
        if not customer_history.orders and not customer_history.appointments:
            return ""
        
        recent_items = []
        
        # Add recent orders
        for order in customer_history.orders[:3]:
            recent_items.append(
                f"- Order #{order.id}: {order.status} "
                f"(${order.total:.2f})"
            )
        
        # Add recent appointments
        for appointment in customer_history.appointments[:3]:
            recent_items.append(
                f"- Appointment: {appointment.service.title} "
                f"on {appointment.scheduled_at.strftime('%Y-%m-%d')}"
            )
        
        return cls.CUSTOMER_HISTORY_TEMPLATE.format(
            total_orders=customer_history.total_orders,
            total_spent=customer_history.total_spent,
            total_appointments=customer_history.total_appointments,
            recent_items="\n".join(recent_items) if recent_items else "None"
        )
    
    @classmethod
    def build_conversation_summary_section(
        cls,
        summary: str,
        key_facts: list
    ) -> str:
        """
        Build conversation summary section for prompt.
        
        Args:
            summary: Conversation summary text
            key_facts: List of key facts to remember
            
        Returns:
            Formatted conversation summary section
        """
        if not summary and not key_facts:
            return ""
        
        facts_text = "\n".join([f"- {fact}" for fact in key_facts]) if key_facts else "None"
        
        return cls.CONVERSATION_SUMMARY_TEMPLATE.format(
            summary=summary or "No previous summary available",
            key_facts=facts_text
        )
    
    @classmethod
    def detect_scenario(cls, message_text: str, context: Any) -> PromptScenario:
        """
        Detect conversation scenario from message and context.
        
        Uses keyword matching and context analysis to determine
        the most appropriate scenario.
        
        Args:
            message_text: Customer message text
            context: AgentContext object
            
        Returns:
            Detected PromptScenario
        """
        message_lower = message_text.lower()
        
        # Product inquiry keywords
        product_keywords = [
            'product', 'item', 'buy', 'purchase', 'price',
            'cost', 'available', 'stock', 'sell'
        ]
        if any(keyword in message_lower for keyword in product_keywords):
            return PromptScenario.PRODUCT_INQUIRY
        
        # Service booking keywords
        booking_keywords = [
            'book', 'appointment', 'schedule', 'reserve',
            'available', 'slot', 'time', 'date'
        ]
        if any(keyword in message_lower for keyword in booking_keywords):
            return PromptScenario.SERVICE_BOOKING
        
        # Order status keywords
        order_keywords = [
            'order', 'delivery', 'shipping', 'track',
            'status', 'where is', 'when will'
        ]
        if any(keyword in message_lower for keyword in order_keywords):
            return PromptScenario.ORDER_STATUS
        
        # Complaint keywords
        complaint_keywords = [
            'complaint', 'problem', 'issue', 'wrong',
            'broken', 'defective', 'unhappy', 'disappointed',
            'refund', 'return', 'cancel'
        ]
        if any(keyword in message_lower for keyword in complaint_keywords):
            return PromptScenario.COMPLAINT
        
        # Recommendation keywords
        recommendation_keywords = [
            'recommend', 'suggest', 'best', 'which',
            'should i', 'what do you think', 'advice'
        ]
        if any(keyword in message_lower for keyword in recommendation_keywords):
            return PromptScenario.RECOMMENDATION
        
        # Technical support keywords
        technical_keywords = [
            'how to', 'help with', 'not working', 'error',
            'fix', 'setup', 'install', 'configure'
        ]
        if any(keyword in message_lower for keyword in technical_keywords):
            return PromptScenario.TECHNICAL_SUPPORT
        
        # Default to general
        return PromptScenario.GENERAL
    
    @classmethod
    def build_reference_context_section(
        cls,
        reference_context
    ) -> str:
        """
        Build reference context section for prompt.
        
        Args:
            reference_context: ReferenceContext object with list items
            
        Returns:
            Formatted reference context section
        """
        if not reference_context or not reference_context.items:
            return ""
        
        items_text = []
        for idx, item in enumerate(reference_context.items, 1):
            items_text.append(f"{idx}. {item.get('title', 'Unknown')} - {item.get('description', '')}")
        
        return cls.REFERENCE_CONTEXT_TEMPLATE.format(
            items="\n".join(items_text)
        )
    
    @classmethod
    def build_browse_session_section(
        cls,
        browse_session
    ) -> str:
        """
        Build browse session section for prompt.
        
        Args:
            browse_session: BrowseSession object
            
        Returns:
            Formatted browse session section
        """
        if not browse_session or not browse_session.is_active:
            return ""
        
        total_pages = (browse_session.total_items + browse_session.items_per_page - 1) // browse_session.items_per_page
        start_position = (browse_session.current_page - 1) * browse_session.items_per_page + 1
        end_position = min(browse_session.current_page * browse_session.items_per_page, browse_session.total_items)
        
        filters_text = browse_session.filters if browse_session.filters else "None"
        
        return cls.BROWSE_SESSION_TEMPLATE.format(
            catalog_type=browse_session.catalog_type,
            current_page=browse_session.current_page,
            total_pages=total_pages,
            start_position=start_position,
            end_position=end_position,
            total_items=browse_session.total_items,
            filters=filters_text
        )
    
    @classmethod
    def build_language_preference_section(
        cls,
        language_preference
    ) -> str:
        """
        Build language preference section for prompt.
        
        Args:
            language_preference: LanguagePreference object
            
        Returns:
            Formatted language preference section
        """
        if not language_preference:
            return ""
        
        common_phrases = ", ".join(language_preference.common_phrases) if language_preference.common_phrases else "None detected yet"
        
        return cls.LANGUAGE_PREFERENCE_TEMPLATE.format(
            primary_language=language_preference.primary_language,
            language_pattern=language_preference.language_usage,
            common_phrases=common_phrases
        )
    
    @classmethod
    def build_product_analysis_section(
        cls,
        product_analysis
    ) -> str:
        """
        Build product analysis section for prompt.
        
        Args:
            product_analysis: ProductAnalysis object
            
        Returns:
            Formatted product analysis section
        """
        if not product_analysis:
            return ""
        
        return cls.PRODUCT_ANALYSIS_TEMPLATE.format(
            product_name=product_analysis.product.title,
            key_features=", ".join(product_analysis.key_features) if product_analysis.key_features else "Not analyzed",
            use_cases=", ".join(product_analysis.use_cases) if product_analysis.use_cases else "Not analyzed",
            target_audience=product_analysis.target_audience or "Not analyzed",
            distinguishing_features=product_analysis.summary or "Not analyzed"
        )
    
    @classmethod
    def build_clarification_context_section(
        cls,
        clarification_count: int,
        preferences: dict
    ) -> str:
        """
        Build clarification context section for prompt.
        
        Args:
            clarification_count: Number of clarifying questions asked
            preferences: Dictionary of extracted preferences
            
        Returns:
            Formatted clarification context section
        """
        if clarification_count == 0 and not preferences:
            return ""
        
        preferences_text = []
        for key, value in preferences.items():
            preferences_text.append(f"- {key}: {value}")
        
        return cls.CLARIFICATION_CONTEXT_TEMPLATE.format(
            clarification_count=clarification_count,
            preferences="\n".join(preferences_text) if preferences_text else "None extracted yet"
        )
    
    @classmethod
    def build_complete_user_prompt(
        cls,
        current_message: str,
        conversation_history: list = None,
        knowledge_entries: list = None,
        products: list = None,
        services: list = None,
        customer_history = None,
        conversation_summary: str = None,
        key_facts: list = None,
        reference_context = None,
        browse_session = None,
        language_preference = None,
        product_analysis = None,
        clarification_count: int = 0,
        preferences: dict = None
    ) -> str:
        """
        Build complete user prompt with all context sections.
        
        Args:
            current_message: Current customer message
            conversation_history: List of recent messages
            knowledge_entries: List of (KnowledgeEntry, score) tuples
            products: List of Product objects
            services: List of Service objects
            customer_history: CustomerHistory object
            conversation_summary: Conversation summary text
            key_facts: List of key facts
            reference_context: ReferenceContext object for positional references
            browse_session: BrowseSession object for pagination state
            language_preference: LanguagePreference object
            product_analysis: ProductAnalysis object for AI insights
            clarification_count: Number of clarifying questions asked
            preferences: Dictionary of extracted customer preferences
            
        Returns:
            Complete user prompt string
        """
        sections = []
        
        # Add language preference (high priority)
        if language_preference:
            lang_section = cls.build_language_preference_section(language_preference)
            if lang_section:
                sections.append(lang_section)
                sections.append("")
        
        # Add conversation history
        if conversation_history:
            sections.append("## Recent Conversation History\n")
            for msg in conversation_history[-5:]:
                role = "Customer" if msg.direction == 'in' else "Assistant"
                sections.append(f"{role}: {msg.text}")
            sections.append("")
        
        # Add conversation summary
        if conversation_summary or key_facts:
            summary_section = cls.build_conversation_summary_section(
                conversation_summary or "",
                key_facts or []
            )
            if summary_section:
                sections.append(summary_section)
                sections.append("")
        
        # Add reference context (important for positional references)
        if reference_context:
            ref_section = cls.build_reference_context_section(reference_context)
            if ref_section:
                sections.append(ref_section)
                sections.append("")
        
        # Add browse session state
        if browse_session:
            browse_section = cls.build_browse_session_section(browse_session)
            if browse_section:
                sections.append(browse_section)
                sections.append("")
        
        # Add clarification context
        if clarification_count > 0 or preferences:
            clarification_section = cls.build_clarification_context_section(
                clarification_count,
                preferences or {}
            )
            if clarification_section:
                sections.append(clarification_section)
                sections.append("")
        
        # Add knowledge base
        if knowledge_entries:
            knowledge_section = cls.build_knowledge_section(knowledge_entries)
            if knowledge_section:
                sections.append(knowledge_section)
                sections.append("")
        
        # Add product analysis (if viewing specific product)
        if product_analysis:
            analysis_section = cls.build_product_analysis_section(product_analysis)
            if analysis_section:
                sections.append(analysis_section)
                sections.append("")
        
        # Add products
        if products:
            products_section = cls.build_catalog_section(products, "Products")
            if products_section:
                sections.append(products_section)
                sections.append("")
        
        # Add services
        if services:
            services_section = cls.build_catalog_section(services, "Services")
            if services_section:
                sections.append(services_section)
                sections.append("")
        
        # Add customer history
        if customer_history:
            history_section = cls.build_customer_history_section(customer_history)
            if history_section:
                sections.append(history_section)
                sections.append("")
        
        # Add current message
        sections.append("## Current Customer Message\n")
        sections.append(current_message)
        sections.append("")
        
        sections.append("Please provide a helpful response to the customer's message.")
        
        return "\n".join(sections)
