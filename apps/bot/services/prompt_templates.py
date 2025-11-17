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
- Provide information from the business knowledge base
- Offer personalized recommendations based on customer history
- Maintain context across the conversation

Your limitations:
- You cannot process payments directly
- You cannot access external systems without explicit integration
- If you're unsure or the request is complex, offer to connect with a human agent

Response guidelines:
- Be helpful, accurate, and concise
- Use information from the provided context
- Reference specific products, services, or knowledge when relevant
- If you don't know something, admit it and offer alternatives
- Always prioritize customer satisfaction"""
    
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
    
    @classmethod
    def get_system_prompt(
        cls,
        scenario: PromptScenario = PromptScenario.GENERAL,
        include_scenario_guidance: bool = True
    ) -> str:
        """
        Get system prompt for a specific scenario.
        
        Args:
            scenario: Conversation scenario
            include_scenario_guidance: Whether to include scenario-specific guidance
            
        Returns:
            Complete system prompt string
        """
        prompt = cls.BASE_SYSTEM_PROMPT
        
        if include_scenario_guidance and scenario in cls.SCENARIO_PROMPTS:
            prompt += "\n\n" + cls.SCENARIO_PROMPTS[scenario]
        
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
                f"(${order.total_amount:.2f})"
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
    def build_complete_user_prompt(
        cls,
        current_message: str,
        conversation_history: list = None,
        knowledge_entries: list = None,
        products: list = None,
        services: list = None,
        customer_history = None,
        conversation_summary: str = None,
        key_facts: list = None
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
            
        Returns:
            Complete user prompt string
        """
        sections = []
        
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
        
        # Add knowledge base
        if knowledge_entries:
            knowledge_section = cls.build_knowledge_section(knowledge_entries)
            if knowledge_section:
                sections.append(knowledge_section)
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
