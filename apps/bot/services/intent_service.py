"""
Intent classification service using LLM for natural language understanding.

Classifies customer messages into actionable intents and extracts relevant
entities/slots for downstream processing.
"""
import logging
import time
import json
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import OpenAI (will be installed as dependency)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not available. Install with: pip install openai")


class IntentServiceError(Exception):
    """Base exception for intent service errors."""
    pass


class IntentService:
    """
    Service for classifying customer intents using LLM.
    
    Supports multiple intents for products, services, bookings, and support.
    Extracts slots/entities from messages for downstream handlers.
    """
    
    # Confidence threshold for accepting intent classification
    CONFIDENCE_THRESHOLD = 0.7
    
    # Maximum consecutive low-confidence attempts before handoff
    MAX_LOW_CONFIDENCE_ATTEMPTS = 2
    
    # Supported intents
    PRODUCT_INTENTS = [
        'GREETING',
        'BROWSE_PRODUCTS',
        'PRODUCT_DETAILS',
        'PRICE_CHECK',
        'STOCK_CHECK',
        'ADD_TO_CART',
        'CHECKOUT_LINK',
    ]
    
    SERVICE_INTENTS = [
        'BROWSE_SERVICES',
        'SERVICE_DETAILS',
        'CHECK_AVAILABILITY',
        'BOOK_APPOINTMENT',
        'RESCHEDULE_APPOINTMENT',
        'CANCEL_APPOINTMENT',
    ]
    
    CONSENT_INTENTS = [
        'OPT_IN_PROMOTIONS',
        'OPT_OUT_PROMOTIONS',
        'STOP_ALL',
        'START_ALL',
    ]
    
    SUPPORT_INTENTS = [
        'HUMAN_HANDOFF',
        'OTHER',
    ]
    
    ALL_INTENTS = PRODUCT_INTENTS + SERVICE_INTENTS + CONSENT_INTENTS + SUPPORT_INTENTS
    
    def __init__(self, api_key: Optional[str] = None, model: str = 'gpt-4'):
        """
        Initialize intent service.
        
        Args:
            api_key: OpenAI API key (uses settings.OPENAI_API_KEY if not provided)
            model: Model to use for classification (default: gpt-4)
        """
        if not OPENAI_AVAILABLE:
            raise IntentServiceError("OpenAI library not installed")
        
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        if not self.api_key:
            raise IntentServiceError("OpenAI API key not configured")
        
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def classify_intent(
        self,
        message_text: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify customer message intent using LLM.
        
        Args:
            message_text: Customer message text
            conversation_context: Optional context (previous intents, customer info)
            
        Returns:
            dict: Classification result with intent_name, confidence_score, slots
            
        Example:
            >>> service = IntentService()
            >>> result = service.classify_intent("I want to book a haircut for tomorrow")
            >>> print(result['intent_name'])  # 'BOOK_APPOINTMENT'
            >>> print(result['slots'])  # {'service_query': 'haircut', 'date': 'tomorrow'}
        """
        start_time = time.time()
        
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt()
            
            # Build user prompt with context
            user_prompt = self._build_user_prompt(message_text, conversation_context)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent classification
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract and validate result
            intent_name = result.get('intent', 'OTHER')
            confidence_score = float(result.get('confidence', 0.0))
            slots = result.get('slots', {})
            reasoning = result.get('reasoning', '')
            
            # Validate intent name
            if intent_name not in self.ALL_INTENTS:
                logger.warning(
                    f"Unknown intent '{intent_name}' returned by LLM, defaulting to OTHER",
                    extra={'message_text': message_text}
                )
                intent_name = 'OTHER'
                confidence_score = 0.5
            
            logger.info(
                f"Intent classified: {intent_name} (confidence: {confidence_score:.2f})",
                extra={
                    'intent': intent_name,
                    'confidence': confidence_score,
                    'processing_time_ms': processing_time_ms,
                    'message_text': message_text[:100]
                }
            )
            
            return {
                'intent_name': intent_name,
                'confidence_score': confidence_score,
                'slots': slots,
                'reasoning': reasoning,
                'model': self.model,
                'processing_time_ms': processing_time_ms,
                'metadata': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM response as JSON",
                extra={'message_text': message_text},
                exc_info=True
            )
            raise IntentServiceError(f"Invalid JSON response from LLM: {str(e)}")
        
        except Exception as e:
            logger.error(
                f"Error classifying intent",
                extra={'message_text': message_text},
                exc_info=True
            )
            raise IntentServiceError(f"Intent classification failed: {str(e)}")
    
    def extract_slots(self, message_text: str, intent: str) -> Dict[str, Any]:
        """
        Extract entities/slots from message for a specific intent.
        
        This is called automatically by classify_intent, but can be used
        standalone for re-extraction or refinement.
        
        Args:
            message_text: Customer message text
            intent: Intent name to extract slots for
            
        Returns:
            dict: Extracted slots/entities
        """
        # This is handled within classify_intent for efficiency
        # But we provide this method for explicit slot extraction if needed
        result = self.classify_intent(message_text)
        return result['slots']
    
    def handle_low_confidence(
        self,
        conversation,
        message_text: str,
        confidence_score: float,
        attempt_count: int
    ) -> Dict[str, Any]:
        """
        Handle low-confidence intent classification.
        
        After MAX_LOW_CONFIDENCE_ATTEMPTS consecutive low-confidence
        classifications, automatically trigger human handoff.
        
        Args:
            conversation: Conversation model instance
            message_text: Customer message text
            confidence_score: Confidence score from classification
            attempt_count: Number of consecutive low-confidence attempts
            
        Returns:
            dict: Action to take (clarify or handoff)
        """
        if attempt_count >= self.MAX_LOW_CONFIDENCE_ATTEMPTS:
            logger.info(
                f"Auto-handoff triggered after {attempt_count} low-confidence attempts",
                extra={
                    'conversation_id': str(conversation.id),
                    'tenant_id': str(conversation.tenant_id)
                }
            )
            
            # Mark conversation for handoff
            conversation.mark_handoff()
            
            return {
                'action': 'handoff',
                'message': "I'm having trouble understanding. Let me connect you with a team member who can help.",
                'reason': 'consecutive_low_confidence',
                'attempt_count': attempt_count
            }
        
        else:
            logger.info(
                f"Low confidence ({confidence_score:.2f}), asking for clarification",
                extra={
                    'conversation_id': str(conversation.id),
                    'attempt_count': attempt_count
                }
            )
            
            return {
                'action': 'clarify',
                'message': "I'm not quite sure what you're looking for. Could you please rephrase or provide more details?",
                'attempt_count': attempt_count
            }
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with intent definitions."""
        return f"""You are an AI assistant for a WhatsApp commerce and services platform.
Your task is to classify customer messages into specific intents and extract relevant information.

SUPPORTED INTENTS:

Product Intents:
- GREETING: Customer greets or starts conversation
- BROWSE_PRODUCTS: Customer wants to see available products
- PRODUCT_DETAILS: Customer asks about a specific product
- PRICE_CHECK: Customer asks about product pricing
- STOCK_CHECK: Customer asks about product availability
- ADD_TO_CART: Customer wants to add product to cart
- CHECKOUT_LINK: Customer wants to complete purchase

Service Intents:
- BROWSE_SERVICES: Customer wants to see available services
- SERVICE_DETAILS: Customer asks about a specific service
- CHECK_AVAILABILITY: Customer wants to see available appointment slots
- BOOK_APPOINTMENT: Customer wants to book an appointment
- RESCHEDULE_APPOINTMENT: Customer wants to change appointment time
- CANCEL_APPOINTMENT: Customer wants to cancel appointment

Consent Intents:
- OPT_IN_PROMOTIONS: Customer wants to receive promotional messages
- OPT_OUT_PROMOTIONS: Customer wants to stop promotional messages
- STOP_ALL: Customer wants to stop all non-essential messages (keywords: STOP, UNSUBSCRIBE)
- START_ALL: Customer wants to resume all messages (keyword: START)

Support Intents:
- HUMAN_HANDOFF: Customer explicitly requests human assistance
- OTHER: Message doesn't match any specific intent

SLOT EXTRACTION:
Extract relevant entities based on the intent:
- product_query, product_id: For product-related intents
- service_query, service_id, variant_id: For service-related intents
- date, time, time_range: For availability and booking intents
- quantity: For cart operations
- notes: Additional customer notes

RESPONSE FORMAT:
Return a JSON object with:
{{
  "intent": "INTENT_NAME",
  "confidence": 0.0-1.0,
  "slots": {{"key": "value"}},
  "reasoning": "Brief explanation of classification"
}}

GUIDELINES:
- Be confident in clear requests (confidence > 0.8)
- Use moderate confidence for ambiguous messages (0.5-0.8)
- Use low confidence when unclear (< 0.5)
- Extract all relevant slots from the message
- Consider context when provided
"""
    
    def _build_user_prompt(
        self,
        message_text: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build user prompt with message and context."""
        prompt = f"Classify this customer message:\n\n\"{message_text}\""
        
        if conversation_context:
            context_parts = []
            
            if conversation_context.get('last_intent'):
                context_parts.append(f"Previous intent: {conversation_context['last_intent']}")
            
            if conversation_context.get('customer_name'):
                context_parts.append(f"Customer name: {conversation_context['customer_name']}")
            
            if conversation_context.get('recent_products'):
                context_parts.append(f"Recently viewed products: {', '.join(conversation_context['recent_products'])}")
            
            if conversation_context.get('recent_services'):
                context_parts.append(f"Recently viewed services: {', '.join(conversation_context['recent_services'])}")
            
            if context_parts:
                prompt += f"\n\nContext:\n" + "\n".join(context_parts)
        
        return prompt
    
    def create_intent_event(
        self,
        conversation,
        message_text: str,
        classification_result: Dict[str, Any]
    ):
        """
        Create IntentEvent record for tracking and analytics.
        
        Args:
            conversation: Conversation model instance
            message_text: Original message text
            classification_result: Result from classify_intent()
            
        Returns:
            IntentEvent: Created intent event instance
        """
        from apps.bot.models import IntentEvent
        
        intent_event = IntentEvent.objects.create(
            conversation=conversation,
            intent_name=classification_result['intent_name'],
            confidence_score=classification_result['confidence_score'],
            slots=classification_result['slots'],
            model=classification_result['model'],
            message_text=message_text,
            processing_time_ms=classification_result.get('processing_time_ms'),
            metadata=classification_result.get('metadata', {})
        )
        
        # Update conversation with last intent
        conversation.last_intent = classification_result['intent_name']
        conversation.intent_confidence = classification_result['confidence_score']
        
        # Handle low confidence
        if classification_result['confidence_score'] < self.CONFIDENCE_THRESHOLD:
            conversation.increment_low_confidence()
        else:
            conversation.reset_low_confidence()
        
        conversation.save(update_fields=['last_intent', 'intent_confidence'])
        
        return intent_event
    
    def is_high_confidence(self, confidence_score: float) -> bool:
        """Check if confidence score meets threshold."""
        return confidence_score >= self.CONFIDENCE_THRESHOLD
    
    def is_low_confidence(self, confidence_score: float) -> bool:
        """Check if confidence score is below threshold."""
        return confidence_score < self.CONFIDENCE_THRESHOLD


def create_intent_service(model: str = 'gpt-4') -> IntentService:
    """
    Factory function to create IntentService instance.
    
    Args:
        model: OpenAI model to use (default: gpt-4)
        
    Returns:
        IntentService: Configured service instance
        
    Example:
        >>> service = create_intent_service()
        >>> result = service.classify_intent("Show me your products")
    """
    return IntentService(model=model)
