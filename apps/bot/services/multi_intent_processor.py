"""
Multi-Intent Processor Service for handling message bursts and multiple intents.

Handles scenarios where customers send multiple messages rapidly or include
multiple intents in a single message. Provides intelligent batching, intent
detection, prioritization, and structured response generation.
"""
import logging
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from django.utils import timezone
from django.db import transaction

from apps.messaging.models import Message, Conversation, MessageQueue
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.llm.base import LLMResponse
from apps.bot.services.context_builder_service import (
    ContextBuilderService,
    AgentContext,
    create_context_builder_service
)

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """
    Represents a detected intent with metadata.
    """
    name: str
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher = more urgent
    category: str = ''  # product, service, support, etc.
    reasoning: str = ''
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert intent to dictionary."""
        return {
            'name': self.name,
            'confidence': self.confidence,
            'slots': self.slots,
            'priority': self.priority,
            'category': self.category,
            'reasoning': self.reasoning,
        }


@dataclass
class MessageBurst:
    """
    Represents a burst of messages from a customer.
    """
    messages: List[Message]
    conversation: Conversation
    combined_text: str
    detected_intents: List[Intent] = field(default_factory=list)
    
    def get_message_ids(self) -> List[str]:
        """Get list of message IDs in burst."""
        return [str(msg.id) for msg in self.messages]
    
    def get_message_count(self) -> int:
        """Get number of messages in burst."""
        return len(self.messages)


class MultiIntentProcessorError(Exception):
    """Base exception for multi-intent processor errors."""
    pass


class MultiIntentProcessor:
    """
    Service for detecting and handling multiple intents in messages.
    
    Capabilities:
    - Detect multiple intents in a single message
    - Process message bursts (multiple rapid messages)
    - Prioritize intents based on urgency and logic
    - Generate structured responses addressing all intents
    - Prevent duplicate intent processing
    
    This service works with the MessageQueue model to batch process
    rapid message sequences and provide coherent responses.
    """
    
    # Intent categories for prioritization
    INTENT_CATEGORIES = {
        'urgent': ['HUMAN_HANDOFF', 'CANCEL_APPOINTMENT', 'STOP_ALL'],
        'transactional': ['CHECKOUT_LINK', 'BOOK_APPOINTMENT', 'ADD_TO_CART'],
        'informational': ['PRODUCT_DETAILS', 'SERVICE_DETAILS', 'CHECK_AVAILABILITY', 'PRICE_CHECK'],
        'browsing': ['BROWSE_PRODUCTS', 'BROWSE_SERVICES', 'GREETING'],
        'support': ['OTHER', 'OPT_IN_PROMOTIONS', 'OPT_OUT_PROMOTIONS'],
    }
    
    # Priority scores by category (higher = more urgent)
    CATEGORY_PRIORITIES = {
        'urgent': 100,
        'transactional': 80,
        'informational': 60,
        'browsing': 40,
        'support': 50,
    }
    
    def __init__(
        self,
        tenant,
        llm_provider: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize multi-intent processor.
        
        Args:
            tenant: Tenant instance
            llm_provider: LLM provider name (defaults to 'openai')
            model: Model to use (defaults to tenant's agent config or gpt-4o)
        """
        self.tenant = tenant
        
        # Get LLM provider from tenant settings
        provider_factory = LLMProviderFactory()
        self.llm_provider = provider_factory.create_from_tenant_settings(
            tenant=tenant,
            provider_name=llm_provider
        )
        
        # Get model from tenant config or use default
        if model:
            self.model = model
        elif hasattr(tenant, 'agent_configuration'):
            self.model = tenant.agent_configuration.default_model
        else:
            self.model = 'gpt-4o'
        
        # Initialize context builder
        self.context_builder = create_context_builder_service()
        
        logger.info(
            f"MultiIntentProcessor initialized for tenant {tenant.id}",
            extra={
                'tenant_id': str(tenant.id),
                'model': self.model
            }
        )
    
    def detect_intents(
        self,
        message_text: str,
        context: Optional[AgentContext] = None
    ) -> List[Intent]:
        """
        Detect all intents in a message using LLM with conversation context.
        
        CHANGED: Now uses conversation context to infer intent from vague messages
        (Requirements 10.1, 10.4, 10.5). Context helps resolve ambiguous messages
        like "I want that", "yes", "how much?" by looking at recent conversation.
        
        Args:
            message_text: Customer message text (can be combined from multiple messages)
            context: Optional agent context for better detection (RECOMMENDED)
            
        Returns:
            List of detected Intent objects
            
        Example:
            >>> processor = MultiIntentProcessor(tenant)
            >>> # Without context - may be ambiguous
            >>> intents = processor.detect_intents("I want that")
            >>> # With context - can infer from recent conversation
            >>> intents = processor.detect_intents("I want that", context=agent_context)
            >>> intents[0].name  # 'PRODUCT_DETAILS' (inferred from context)
        """
        start_time = time.time()
        
        try:
            # Build system prompt for multi-intent detection
            system_prompt = self._build_multi_intent_system_prompt()
            
            # Build user prompt with context (CHANGED: now includes richer context)
            user_prompt = self._build_multi_intent_user_prompt(message_text, context)
            
            # Log context usage for debugging
            has_context = context is not None
            has_history = has_context and len(context.conversation_history) > 0
            has_last_viewed = has_context and (
                context.last_product_viewed is not None or 
                context.last_service_viewed is not None
            )
            
            logger.debug(
                f"Detecting intents with context: history={has_history}, "
                f"last_viewed={has_last_viewed}",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'message_preview': message_text[:50],
                    'has_context': has_context,
                    'has_history': has_history,
                    'has_last_viewed': has_last_viewed
                }
            )
            
            # Call LLM
            response = self.llm_provider.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse response
            result = self._parse_multi_intent_response(response.content)
            
            # Convert to Intent objects
            intents = []
            for intent_data in result.get('intents', []):
                intent = Intent(
                    name=intent_data.get('intent', 'OTHER'),
                    confidence=float(intent_data.get('confidence', 0.0)),
                    slots=intent_data.get('slots', {}),
                    reasoning=intent_data.get('reasoning', ''),
                    category=self._get_intent_category(intent_data.get('intent', 'OTHER')),
                    priority=0  # Will be set by prioritize_intents
                )
                intents.append(intent)
            
            # Log detection with context info
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Detected {len(intents)} intents in message (context_used={has_context})",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'intent_count': len(intents),
                    'intents': [i.name for i in intents],
                    'processing_time_ms': processing_time_ms,
                    'context_used': has_context,
                    'context_helped': has_context and len(intents) > 0
                }
            )
            
            return intents
            
        except Exception as e:
            logger.error(
                f"Error detecting intents",
                extra={'tenant_id': str(self.tenant.id)},
                exc_info=True
            )
            raise MultiIntentProcessorError(f"Intent detection failed: {str(e)}")
    
    def process_message_burst(
        self,
        conversation: Conversation,
        delay_seconds: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Process a burst of queued messages together.
        
        Retrieves all messages that have been queued for at least delay_seconds,
        combines them, detects all intents, and generates a structured response.
        
        Args:
            conversation: Conversation instance
            delay_seconds: How long to wait before processing burst (default: 5)
            
        Returns:
            dict: Processing result with response and metadata, or None if no messages ready
            
        Example:
            >>> processor = MultiIntentProcessor(tenant)
            >>> result = processor.process_message_burst(conversation)
            >>> if result:
            ...     print(result['response'])
            ...     print(result['intents_addressed'])
        """
        try:
            # Get messages ready for batch processing
            queued_messages = MessageQueue.objects.ready_for_batch(
                conversation=conversation,
                delay_seconds=delay_seconds
            )
            
            if not queued_messages.exists():
                logger.debug(
                    f"No messages ready for batch processing",
                    extra={'conversation_id': str(conversation.id)}
                )
                return None
            
            # Mark messages as processing
            with transaction.atomic():
                queued_messages.update(status='processing')
            
            # Load actual messages
            message_ids = [qm.message_id for qm in queued_messages]
            messages = Message.objects.filter(id__in=message_ids).order_by('created_at')
            
            # Create message burst
            combined_text = "\n".join([msg.text for msg in messages])
            burst = MessageBurst(
                messages=list(messages),
                conversation=conversation,
                combined_text=combined_text
            )
            
            logger.info(
                f"Processing message burst with {burst.get_message_count()} messages",
                extra={
                    'conversation_id': str(conversation.id),
                    'message_count': burst.get_message_count(),
                    'message_ids': burst.get_message_ids()
                }
            )
            
            # Build context
            context = self.context_builder.build_context(
                conversation=conversation,
                message=messages[0],  # Use first message for context building
                tenant=self.tenant
            )
            
            # Detect intents
            intents = self.detect_intents(combined_text, context)
            burst.detected_intents = intents
            
            # Prioritize intents
            prioritized_intents = self.prioritize_intents(intents)
            
            # Generate structured response
            response = self.generate_structured_response(
                burst=burst,
                intents=prioritized_intents,
                context=context
            )
            
            # Mark messages as processed
            with transaction.atomic():
                for qm in queued_messages:
                    qm.mark_processed()
            
            logger.info(
                f"Message burst processed successfully",
                extra={
                    'conversation_id': str(conversation.id),
                    'intents_addressed': len(prioritized_intents),
                    'response_length': len(response)
                }
            )
            
            return {
                'response': response,
                'intents_addressed': [i.to_dict() for i in prioritized_intents],
                'message_count': burst.get_message_count(),
                'message_ids': burst.get_message_ids(),
                'combined_text': combined_text
            }
            
        except Exception as e:
            logger.error(
                f"Error processing message burst",
                extra={'conversation_id': str(conversation.id)},
                exc_info=True
            )
            
            # Mark messages as failed
            with transaction.atomic():
                queued_messages.update(
                    status='failed',
                    error_message=str(e)
                )
            
            raise MultiIntentProcessorError(f"Message burst processing failed: {str(e)}")
    
    def prioritize_intents(self, intents: List[Intent]) -> List[Intent]:
        """
        Prioritize intents based on urgency and logical flow.
        
        Priority rules:
        1. Urgent intents (HUMAN_HANDOFF, CANCEL, STOP) come first
        2. Transactional intents (CHECKOUT, BOOK) come next
        3. Informational intents (DETAILS, PRICE) follow
        4. Browsing intents (BROWSE, GREETING) come last
        5. Within same category, higher confidence comes first
        
        Args:
            intents: List of Intent objects
            
        Returns:
            List of Intent objects sorted by priority
            
        Example:
            >>> intents = [
            ...     Intent(name='BROWSE_PRODUCTS', confidence=0.9, category='browsing'),
            ...     Intent(name='HUMAN_HANDOFF', confidence=0.8, category='urgent'),
            ...     Intent(name='PRICE_CHECK', confidence=0.85, category='informational')
            ... ]
            >>> prioritized = processor.prioritize_intents(intents)
            >>> prioritized[0].name  # 'HUMAN_HANDOFF' (urgent)
            >>> prioritized[1].name  # 'PRICE_CHECK' (informational)
            >>> prioritized[2].name  # 'BROWSE_PRODUCTS' (browsing)
        """
        # Assign priority scores
        for intent in intents:
            category_priority = self.CATEGORY_PRIORITIES.get(intent.category, 50)
            # Combine category priority with confidence (scaled to 0-20)
            intent.priority = category_priority + int(intent.confidence * 20)
        
        # Sort by priority (descending) and confidence (descending)
        sorted_intents = sorted(
            intents,
            key=lambda i: (i.priority, i.confidence),
            reverse=True
        )
        
        logger.debug(
            f"Prioritized {len(intents)} intents",
            extra={
                'tenant_id': str(self.tenant.id),
                'intent_order': [i.name for i in sorted_intents]
            }
        )
        
        return sorted_intents
    
    def generate_structured_response(
        self,
        burst: MessageBurst,
        intents: List[Intent],
        context: AgentContext
    ) -> str:
        """
        Generate a structured response addressing all intents.
        
        Creates a coherent response that addresses each intent in priority order,
        using appropriate formatting and transitions between topics.
        
        Args:
            burst: MessageBurst object with messages and intents
            intents: Prioritized list of Intent objects
            context: AgentContext for response generation
            
        Returns:
            str: Structured response text
            
        Example:
            >>> response = processor.generate_structured_response(burst, intents, context)
            >>> print(response)
            # "I can help you with that! Let me address each of your questions:
            #
            # 1. Regarding booking a haircut...
            # 2. About the shampoo price..."
        """
        try:
            # Build system prompt
            system_prompt = self._build_response_generation_system_prompt()
            
            # Build user prompt with all intents
            user_prompt = self._build_response_generation_user_prompt(
                burst=burst,
                intents=intents,
                context=context
            )
            
            # Generate response
            response = self.llm_provider.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=1500
            )
            
            return response.content
            
        except Exception as e:
            logger.error(
                f"Error generating structured response",
                extra={
                    'tenant_id': str(self.tenant.id),
                    'conversation_id': str(burst.conversation.id)
                },
                exc_info=True
            )
            raise MultiIntentProcessorError(f"Response generation failed: {str(e)}")
    
    def _get_intent_category(self, intent_name: str) -> str:
        """Get category for an intent name."""
        for category, intents in self.INTENT_CATEGORIES.items():
            if intent_name in intents:
                return category
        return 'support'  # Default category
    
    def _build_multi_intent_system_prompt(self) -> str:
        """Build system prompt for multi-intent detection with context awareness."""
        return """You are an AI assistant that detects multiple intents in customer messages.

Your task is to identify ALL distinct intents in a message, even if there are multiple.
IMPORTANT: Use conversation context to infer intent when messages are vague or ambiguous.

SUPPORTED INTENTS:
- GREETING: Customer greets or starts conversation
- BROWSE_PRODUCTS: Customer wants to see products
- PRODUCT_DETAILS: Customer asks about specific product
- PRICE_CHECK: Customer asks about pricing
- STOCK_CHECK: Customer asks about availability
- ADD_TO_CART: Customer wants to add to cart
- CHECKOUT_LINK: Customer wants to complete purchase
- BROWSE_SERVICES: Customer wants to see services
- SERVICE_DETAILS: Customer asks about specific service
- CHECK_AVAILABILITY: Customer wants to see appointment slots
- BOOK_APPOINTMENT: Customer wants to book appointment
- RESCHEDULE_APPOINTMENT: Customer wants to change appointment
- CANCEL_APPOINTMENT: Customer wants to cancel appointment
- OPT_IN_PROMOTIONS: Customer wants promotional messages
- OPT_OUT_PROMOTIONS: Customer wants to stop promotions
- STOP_ALL: Customer wants to stop all messages
- START_ALL: Customer wants to resume messages
- HUMAN_HANDOFF: Customer requests human assistance
- OTHER: Doesn't match specific intent

CONTEXT-BASED INFERENCE:
When the message is vague (e.g., "I want that", "yes", "how much?"), use the provided context:
- Recent conversation history: What was just discussed?
- Last viewed items: What product/service was the customer looking at?
- Current topic: What is the ongoing conversation about?
- Key facts: What has been established in the conversation?

Examples of context-based inference:
- "I want that" + Last Product Viewed: "Blue Shirt" → PRODUCT_DETAILS or ADD_TO_CART
- "Yes" + Last Question: "Would you like to book?" → BOOK_APPOINTMENT
- "How much?" + Current Topic: "haircut service" → PRICE_CHECK for service
- "That one" + Recent conversation about products → PRODUCT_DETAILS

RESPONSE FORMAT:
Return a JSON object with an array of intents:
{
  "intents": [
    {
      "intent": "INTENT_NAME",
      "confidence": 0.0-1.0,
      "slots": {"key": "value"},
      "reasoning": "Why this intent was detected (mention context if used)"
    }
  ]
}

GUIDELINES:
- Detect ALL intents, even if there are 3-4 in one message
- Each intent should be distinct (don't duplicate)
- Extract relevant slots for each intent
- Use HIGH confidence (>0.8) when context makes intent clear
- Use MODERATE confidence (0.5-0.8) when inferring from context
- Use LOW confidence (<0.5) only when context is insufficient
- ALWAYS explain your reasoning, especially when using context
- If message is simple with one intent, return array with one item
- Prefer inferring from context over asking for clarification
"""
    
    def _build_multi_intent_user_prompt(
        self,
        message_text: str,
        context: Optional[AgentContext] = None
    ) -> str:
        """
        Build user prompt for multi-intent detection with conversation context.
        
        CHANGED: Now includes richer context from conversation history to support
        intent inference from context (Requirements 10.1, 10.4, 10.5).
        
        Context helps resolve vague messages like:
        - "I want that" -> infer from recently viewed products
        - "Yes" -> infer from last question asked
        - "How much?" -> infer from recently discussed items
        """
        prompt = f"Detect all intents in this customer message:\n\n\"{message_text}\""
        
        # Add conversation context if available
        if context:
            context_parts = []
            
            # Include recent conversation history (last 3 messages)
            if context.conversation_history:
                recent_messages = context.conversation_history[-3:]
                if recent_messages:
                    context_parts.append("\n## Recent Conversation:")
                    for msg in recent_messages:
                        role = "Customer" if msg.direction == 'in' else "Assistant"
                        context_parts.append(f"{role}: {msg.text}")
            
            # Include last viewed items for reference resolution
            if context.last_product_viewed:
                context_parts.append(
                    f"\n## Last Product Viewed: {context.last_product_viewed.title}"
                )
            
            if context.last_service_viewed:
                context_parts.append(
                    f"\n## Last Service Viewed: {context.last_service_viewed.title}"
                )
            
            # Include current topic from conversation context
            if context.context and context.context.current_topic:
                context_parts.append(
                    f"\n## Current Topic: {context.context.current_topic}"
                )
            
            # Include key facts from conversation
            if context.context and context.context.key_facts:
                recent_facts = context.context.key_facts[-3:]  # Last 3 facts
                if recent_facts:
                    context_parts.append("\n## Key Facts from Conversation:")
                    for fact in recent_facts:
                        context_parts.append(f"- {fact}")
            
            # Add context to prompt
            if context_parts:
                prompt += "\n" + "\n".join(context_parts)
                prompt += "\n\nUse this context to infer intent when the message is vague or ambiguous."
        
        return prompt
    
    def _build_response_generation_system_prompt(self) -> str:
        """Build system prompt for structured response generation."""
        return """You are an AI customer service assistant generating responses to customer messages.

When a customer has multiple questions or requests, address each one clearly and systematically.

RESPONSE STRUCTURE:
1. Start with a friendly acknowledgment
2. Address each intent/question in order of priority
3. Use clear transitions between topics
4. Be concise but complete
5. End with an offer to help further

FORMATTING:
- Use numbered lists when addressing multiple items
- Use clear section breaks for different topics
- Keep each section focused and actionable
- Maintain a conversational, helpful tone

GUIDELINES:
- Address ALL intents provided
- Don't skip or combine intents inappropriately
- Provide specific information from context when available
- If you can't fully address an intent, explain why
- Offer next steps or alternatives when appropriate
"""
    
    def _build_response_generation_user_prompt(
        self,
        burst: MessageBurst,
        intents: List[Intent],
        context: AgentContext
    ) -> str:
        """Build user prompt for response generation."""
        prompt_parts = []
        
        # Add customer messages
        prompt_parts.append("## Customer Messages\n")
        for i, msg in enumerate(burst.messages, 1):
            prompt_parts.append(f"Message {i}: {msg.text}")
        prompt_parts.append("")
        
        # Add detected intents
        prompt_parts.append("## Detected Intents (in priority order)\n")
        for i, intent in enumerate(intents, 1):
            prompt_parts.append(f"{i}. {intent.name} (confidence: {intent.confidence:.2f})")
            if intent.slots:
                prompt_parts.append(f"   Slots: {json.dumps(intent.slots)}")
            if intent.reasoning:
                prompt_parts.append(f"   Reasoning: {intent.reasoning}")
        prompt_parts.append("")
        
        # Add relevant context
        if context.knowledge_entries:
            prompt_parts.append("## Relevant Knowledge\n")
            for entry, score in context.knowledge_entries[:3]:
                prompt_parts.append(f"- {entry.title}: {entry.content[:200]}...")
            prompt_parts.append("")
        
        if context.products:
            prompt_parts.append("## Available Products\n")
            for product in context.products[:5]:
                prompt_parts.append(f"- {product.title}: {product.description or 'No description'}...")
            prompt_parts.append("")
        
        if context.services:
            prompt_parts.append("## Available Services\n")
            for service in context.services[:5]:
                prompt_parts.append(f"- {service.title}: {service.description or 'No description'}...")
            prompt_parts.append("")
        
        prompt_parts.append("Generate a structured response that addresses all detected intents in priority order.")
        
        return "\n".join(prompt_parts)
    
    def _parse_multi_intent_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response for multi-intent detection."""
        try:
            # Try direct JSON parse
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            match = re.search(code_block_pattern, response_text, re.DOTALL)
            
            if match:
                return json.loads(match.group(1))
            
            # Look for JSON object directly
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            match = re.search(json_pattern, response_text, re.DOTALL)
            
            if match:
                return json.loads(match.group(0))
            
            # If nothing found, return empty result
            logger.warning(
                f"Could not parse multi-intent response as JSON",
                extra={'response_text': response_text[:200]}
            )
            return {'intents': []}


def create_multi_intent_processor(
    tenant,
    llm_provider: Optional[str] = None,
    model: Optional[str] = None
) -> MultiIntentProcessor:
    """
    Factory function to create MultiIntentProcessor instance.
    
    Args:
        tenant: Tenant instance
        llm_provider: LLM provider name (defaults to 'openai')
        model: Model to use (defaults to tenant's agent config)
        
    Returns:
        MultiIntentProcessor: Configured processor instance
        
    Example:
        >>> processor = create_multi_intent_processor(tenant)
        >>> intents = processor.detect_intents("I want to book a haircut and check prices")
    """
    return MultiIntentProcessor(
        tenant=tenant,
        llm_provider=llm_provider,
        model=model
    )
