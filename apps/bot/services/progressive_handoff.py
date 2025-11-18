"""
Progressive handoff service with clarifying questions.
"""
import logging
from typing import Tuple, Optional, Dict, Any
from apps.messaging.models import Conversation
from apps.bot.models import AgentConfiguration
from apps.bot.services.llm.factory import LLMProviderFactory

logger = logging.getLogger(__name__)


class ProgressiveHandoffService:
    """
    Service for progressive handoff with clarifying attempts.
    
    Before offering handoff, attempts to clarify customer needs
    through intelligent questions. Only offers handoff after
    genuine attempts to help.
    """
    
    MAX_CLARIFICATION_ATTEMPTS = 2
    
    # Topics that trigger immediate handoff
    IMMEDIATE_HANDOFF_TOPICS = [
        'complaint',
        'refund',
        'dispute',
        'fraud',
        'legal',
        'emergency',
        'account locked',
        'payment failed',
        'unauthorized charge',
    ]
    
    @classmethod
    def should_attempt_clarification(cls, conversation: Conversation, confidence_score: float) -> bool:
        """
        Determine if we should try clarifying before handoff.
        
        Args:
            conversation: Conversation instance
            confidence_score: Current response confidence
        
        Returns:
            bool - True if should attempt clarification
        """
        # Check clarification attempt count
        clarification_count = conversation.context.clarification_attempts if hasattr(conversation, 'context') else 0
        
        if clarification_count >= cls.MAX_CLARIFICATION_ATTEMPTS:
            logger.info(f"Max clarification attempts reached ({clarification_count})")
            return False
        
        # Only clarify if confidence is moderate (not extremely low)
        if confidence_score < 0.3:
            logger.info(f"Confidence too low for clarification: {confidence_score}")
            return False
        
        return True
    
    @classmethod
    def generate_clarifying_questions(
        cls,
        tenant,
        customer_message: str,
        conversation_context: str
    ) -> list:
        """
        Generate specific clarifying questions using LLM.
        
        Args:
            tenant: Tenant instance
            customer_message: Customer's message
            conversation_context: Recent conversation context
        
        Returns:
            List of 2-3 clarifying questions
        """
        prompt = f"""
        The customer said: "{customer_message}"
        
        Recent context:
        {conversation_context}
        
        I'm not fully confident I understand their need. Generate 2-3 specific clarifying questions to help me understand better.
        
        Questions should:
        - Address specific ambiguities in their message
        - Be easy to answer
        - Help narrow down their exact need
        - Show I'm trying to help
        
        Examples:
        - "Are you looking for [option A] or [option B]?"
        - "Could you tell me more about [specific aspect]?"
        - "Do you mean [interpretation 1] or [interpretation 2]?"
        
        Return only the questions, one per line.
        """
        
        try:
            provider = LLMProviderFactory.get_provider(tenant, model_name='gpt-4o-mini')
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a helpful assistant trying to understand customer needs.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            # Parse questions
            questions = [
                q.strip().lstrip('-•*').strip()
                for q in response['content'].strip().split('\n')
                if q.strip()
            ]
            
            return questions[:3]
            
        except Exception as e:
            logger.error(f"Error generating clarifying questions: {e}")
            return [
                "Could you provide more details about what you're looking for?",
                "What's the main thing you need help with?",
            ]
    
    @classmethod
    def generate_handoff_explanation(
        cls,
        tenant,
        customer_message: str,
        attempts_made: list,
        reason: str
    ) -> str:
        """
        Generate explanation for why handoff is being offered.
        
        Args:
            tenant: Tenant instance
            customer_message: Customer's message
            attempts_made: List of attempts made to help
            reason: Handoff reason code
        
        Returns:
            Explanation message
        """
        prompt = f"""
        I need to explain to a customer why I'm suggesting they speak with a human agent.
        
        Customer's request: "{customer_message}"
        
        What I tried:
        {chr(10).join(f"- {attempt}" for attempt in attempts_made)}
        
        Reason for handoff: {reason}
        
        Generate a friendly, honest explanation (2-3 sentences) that:
        - Acknowledges what I understood
        - Explains what I tried
        - Suggests human agent can help better
        - Maintains positive tone
        
        Don't apologize excessively. Be helpful and solution-oriented.
        """
        
        try:
            provider = LLMProviderFactory.get_provider(tenant, model_name='gpt-4o-mini')
            
            response = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'You are a helpful AI assistant.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            return response['content'].strip()
            
        except Exception as e:
            logger.error(f"Error generating handoff explanation: {e}")
            return (
                "I want to make sure you get the best help possible. "
                "Let me connect you with one of our team members who can assist you better."
            )
    
    @classmethod
    def detect_immediate_handoff_topic(cls, message_text: str) -> Optional[str]:
        """
        Detect if message contains topic requiring immediate handoff.
        
        Args:
            message_text: Customer message
        
        Returns:
            Topic name if detected, None otherwise
        """
        message_lower = message_text.lower()
        
        for topic in cls.IMMEDIATE_HANDOFF_TOPICS:
            if topic in message_lower:
                logger.info(f"Detected immediate handoff topic: {topic}")
                return topic
        
        return None
    
    @classmethod
    def should_handoff_with_progressive_logic(
        cls,
        tenant,
        conversation: Conversation,
        customer_message: str,
        confidence_score: float,
        agent_config: AgentConfiguration
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Determine if handoff should occur with progressive logic.
        
        Args:
            tenant: Tenant instance
            conversation: Conversation instance
            customer_message: Customer's message
            confidence_score: Response confidence
            agent_config: Agent configuration
        
        Returns:
            Tuple of (should_handoff, reason, clarification_data)
            clarification_data contains questions if should try clarifying first
        """
        # 1. Check for immediate handoff topics
        immediate_topic = cls.detect_immediate_handoff_topic(customer_message)
        if immediate_topic:
            explanation = cls.generate_handoff_explanation(
                tenant,
                customer_message,
                ["Identified this as a sensitive topic requiring human attention"],
                f"immediate_handoff_{immediate_topic}"
            )
            return True, f"immediate_handoff_{immediate_topic}", {
                'explanation': explanation,
                'skip_clarification': True
            }
        
        # 2. Check for explicit human request
        human_request_phrases = [
            'speak to a human',
            'talk to a person',
            'human agent',
            'real person',
            'live agent',
            'customer service',
            'speak to someone',
            'talk to someone',
        ]
        
        message_lower = customer_message.lower()
        for phrase in human_request_phrases:
            if phrase in message_lower:
                return True, 'customer_requested_human', {
                    'explanation': "I'll connect you with a team member right away.",
                    'skip_clarification': True
                }
        
        # 3. Check confidence and clarification attempts
        if confidence_score < agent_config.confidence_threshold:
            # Should we try clarifying first?
            if cls.should_attempt_clarification(conversation, confidence_score):
                # Generate clarifying questions
                context = cls._get_conversation_context(conversation)
                questions = cls.generate_clarifying_questions(
                    tenant,
                    customer_message,
                    context
                )
                
                return False, 'attempting_clarification', {
                    'questions': questions,
                    'should_clarify': True
                }
            else:
                # Max attempts reached, offer handoff
                attempts_made = [
                    "Asked clarifying questions",
                    "Searched our catalog",
                    "Tried to understand your specific need"
                ]
                explanation = cls.generate_handoff_explanation(
                    tenant,
                    customer_message,
                    attempts_made,
                    'max_clarification_attempts'
                )
                
                return True, 'max_clarification_attempts', {
                    'explanation': explanation,
                    'attempts_made': attempts_made
                }
        
        # 4. No handoff needed
        return False, '', None
    
    @classmethod
    def _get_conversation_context(cls, conversation: Conversation, max_messages: int = 5) -> str:
        """Get recent conversation context."""
        recent_messages = conversation.messages.order_by('-created_at')[:max_messages]
        
        context_lines = []
        for msg in reversed(list(recent_messages)):
            role = "Customer" if msg.direction == 'in' else "Agent"
            context_lines.append(f"{role}: {msg.text[:100]}")
        
        return '\n'.join(context_lines)
    
    @classmethod
    def record_clarification_attempt(cls, conversation: Conversation):
        """Record that a clarification attempt was made."""
        if hasattr(conversation, 'context'):
            context = conversation.context
            if not hasattr(context, 'clarification_attempts'):
                context.clarification_attempts = 0
            context.clarification_attempts += 1
            context.save(update_fields=['clarification_attempts'])
    
    @classmethod
    def reset_clarification_attempts(cls, conversation: Conversation):
        """Reset clarification attempts (after successful interaction)."""
        if hasattr(conversation, 'context'):
            context = conversation.context
            context.clarification_attempts = 0
            context.save(update_fields=['clarification_attempts'])
