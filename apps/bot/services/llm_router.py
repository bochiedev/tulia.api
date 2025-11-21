"""
Multi-Model LLM Router for the sales orchestration refactor.

This service selects the cheapest viable model for each task and tracks costs.

Design principles:
- Use small models only (GPT-4o-mini, Qwen 2.5 7B, Gemini Flash)
- Track token usage and costs per tenant
- Enforce budget caps
- Fall back to rules when budget exceeded
"""
import logging
import json
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.db.models import Sum

from apps.tenants.models import Tenant
from apps.bot.models import AgentConfiguration
from apps.bot.models_sales_orchestration import LLMUsageLog
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.llm.base import LLMProvider, LLMResponse
from apps.bot.services.intent_detection_engine import Intent

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Multi-model LLM router with cost tracking and budget enforcement.
    
    Responsibilities:
    - Select the cheapest viable model for each task
    - Track token usage and costs per tenant
    - Enforce monthly budget caps
    - Provide fallback when budget exceeded
    - Log all LLM usage for analytics
    """
    
    # Model preferences by task type (cheapest first)
    TASK_MODEL_PREFERENCES = {
        'intent_classification': [
            ('openai', 'gpt-4o-mini'),
            ('gemini', 'gemini-1.5-flash'),
        ],
        'slot_extraction': [
            ('openai', 'gpt-4o-mini'),
            ('gemini', 'gemini-1.5-flash'),
        ],
        'rag_answer': [
            ('openai', 'gpt-4o-mini'),
            ('gemini', 'gemini-1.5-flash'),
        ],
    }
    
    # Default model if preferences not found
    DEFAULT_MODEL = ('openai', 'gpt-4o-mini')
    
    def __init__(self, tenant: Tenant):
        """
        Initialize LLM router for a tenant.
        
        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant
        self.config = self._get_agent_config()
        self._provider_cache: Dict[str, LLMProvider] = {}
    
    def classify_intent(
        self,
        text: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Classify intent using small model with structured JSON output.
        
        Args:
            text: Message text to classify
            context: Conversation context
            
        Returns:
            Dict with intent, confidence, slots, and metadata
        """
        # Check budget before making call
        if not self._check_budget():
            logger.warning(
                f"Tenant {self.tenant.id} exceeded LLM budget, "
                f"falling back to rule-based classification"
            )
            return {
                'intent': Intent.UNKNOWN.value,
                'confidence': 0.0,
                'slots': {},
                'budget_exceeded': True
            }
        
        # Build prompt for intent classification
        prompt = self._build_intent_classification_prompt(text, context)
        
        # Call LLM
        try:
            response = self._call_llm(
                task_type='intent_classification',
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an intent classifier for a conversational commerce bot. '
                                   'Respond with valid JSON only.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                temperature=0.3,  # Low temperature for consistent classification
                max_tokens=200
            )
            
            # Parse JSON response
            result = json.loads(response.content)
            
            # Validate intent is in allowed set
            intent_value = result.get('intent', 'UNKNOWN')
            try:
                Intent(intent_value)  # Validate it's a valid intent
            except ValueError:
                logger.warning(f"LLM returned invalid intent: {intent_value}, using UNKNOWN")
                result['intent'] = Intent.UNKNOWN.value
            
            # Log usage
            self._log_usage(
                task_type='intent_classification',
                response=response,
                prompt_template='intent_classification',
                metadata={'text_length': len(text)}
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {
                'intent': Intent.UNKNOWN.value,
                'confidence': 0.0,
                'slots': {},
                'error': 'json_parse_error'
            }
        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            return {
                'intent': Intent.UNKNOWN.value,
                'confidence': 0.0,
                'slots': {},
                'error': str(e)
            }
    
    def extract_slots(
        self,
        text: str,
        intent: Intent,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured slots using small model.
        
        Args:
            text: Message text
            intent: Detected intent
            context: Conversation context
            
        Returns:
            Dict with extracted slots
        """
        # Check budget
        if not self._check_budget():
            logger.warning(f"Tenant {self.tenant.id} exceeded LLM budget for slot extraction")
            return {}
        
        # Build prompt for slot extraction
        prompt = self._build_slot_extraction_prompt(text, intent, context)
        
        # Call LLM
        try:
            response = self._call_llm(
                task_type='slot_extraction',
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a slot extractor for a conversational commerce bot. '
                                   'Extract structured information and respond with valid JSON only.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                temperature=0.2,  # Very low temperature for consistent extraction
                max_tokens=150
            )
            
            # Parse JSON response
            slots = json.loads(response.content)
            
            # Log usage
            self._log_usage(
                task_type='slot_extraction',
                response=response,
                prompt_template='slot_extraction',
                metadata={'intent': intent.value, 'text_length': len(text)}
            )
            
            return slots
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse slot extraction response as JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error in LLM slot extraction: {e}")
            return {}
    
    def generate_rag_answer(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        language: List[str]
    ) -> str:
        """
        Generate grounded answer from retrieved chunks.
        
        Args:
            question: Customer's question
            chunks: Retrieved document chunks
            language: Detected language(s)
            
        Returns:
            Generated answer or uncertainty message
        """
        # Check budget
        if not self._check_budget():
            logger.warning(f"Tenant {self.tenant.id} exceeded LLM budget for RAG")
            return "I'm not sure about that. Let me connect you with someone from our team."
        
        # Build prompt for RAG answer generation
        prompt = self._build_rag_prompt(question, chunks, language)
        
        # Call LLM
        try:
            response = self._call_llm(
                task_type='rag_answer',
                messages=[
                    {
                        'role': 'system',
                        'content': f'You are a helpful assistant for {self.tenant.name}. '
                                   f'Answer questions using ONLY the provided context. '
                                   f'If the context does not contain the answer, say you are not sure.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                temperature=0.5,  # Moderate temperature for natural responses
                max_tokens=300
            )
            
            # Log usage
            self._log_usage(
                task_type='rag_answer',
                response=response,
                prompt_template='rag_answer',
                metadata={
                    'question_length': len(question),
                    'chunks_count': len(chunks),
                    'language': language
                }
            )
            
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Error in LLM RAG answer generation: {e}")
            return "I'm not sure about that. Let me connect you with someone from our team."
    
    def _call_llm(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """
        Call LLM with model selection and error handling.
        
        Args:
            task_type: Type of task (for model selection)
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse from provider
            
        Raises:
            Exception: On API errors
        """
        # Select model
        provider_name, model_name = self._select_model(task_type)
        
        # Get or create provider instance
        provider = self._get_provider(provider_name)
        
        # Call provider
        logger.info(
            f"Calling LLM: tenant={self.tenant.id}, task={task_type}, "
            f"provider={provider_name}, model={model_name}"
        )
        
        response = provider.generate(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response
    
    def _select_model(self, task_type: str) -> tuple[str, str]:
        """
        Select model based on task type and availability.
        
        Preference order:
        1. GPT-4o-mini (cheapest, good quality)
        2. Gemini Flash (Google, competitive pricing)
        
        Args:
            task_type: Type of task
            
        Returns:
            Tuple of (provider_name, model_name)
        """
        # Get preferences for this task type
        preferences = self.TASK_MODEL_PREFERENCES.get(
            task_type,
            [self.DEFAULT_MODEL]
        )
        
        # Try each preference in order
        for provider_name, model_name in preferences:
            try:
                # Check if provider is available
                provider = self._get_provider(provider_name)
                if provider:
                    logger.debug(
                        f"Selected model for {task_type}: "
                        f"{provider_name}/{model_name}"
                    )
                    return provider_name, model_name
            except Exception as e:
                logger.warning(
                    f"Provider {provider_name} not available: {e}, "
                    f"trying next preference"
                )
                continue
        
        # Fall back to default
        logger.warning(
            f"All preferred models unavailable for {task_type}, "
            f"using default: {self.DEFAULT_MODEL}"
        )
        return self.DEFAULT_MODEL
    
    def _get_provider(self, provider_name: str) -> LLMProvider:
        """
        Get or create provider instance with caching.
        
        Args:
            provider_name: Provider identifier
            
        Returns:
            LLMProvider instance
        """
        if provider_name not in self._provider_cache:
            self._provider_cache[provider_name] = (
                LLMProviderFactory.create_from_tenant_settings(
                    self.tenant,
                    provider_name=provider_name
                )
            )
        
        return self._provider_cache[provider_name]
    
    def _check_budget(self) -> bool:
        """
        Check if tenant has budget remaining for LLM usage.
        
        Returns:
            True if budget available, False if exceeded
        """
        if not self.config:
            # No config, allow usage
            return True
        
        # Get monthly budget
        monthly_budget = self.config.monthly_llm_budget_usd
        if monthly_budget <= 0:
            # Unlimited budget
            return True
        
        # Calculate current month's usage
        now = timezone.now()
        monthly_usage = LLMUsageLog.objects.monthly_cost(
            self.tenant,
            now.year,
            now.month
        )
        
        # Check if exceeded
        if monthly_usage >= monthly_budget:
            logger.warning(
                f"Tenant {self.tenant.id} exceeded monthly LLM budget: "
                f"${monthly_usage} >= ${monthly_budget}"
            )
            
            # Check action to take
            action = self.config.llm_budget_exceeded_action
            if action == 'stop':
                return False
            elif action == 'throttle':
                # TODO: Implement throttling logic
                return False
            else:  # fallback
                return False
        
        return True
    
    def _log_usage(
        self,
        task_type: str,
        response: LLMResponse,
        prompt_template: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Log LLM usage for analytics and cost tracking.
        
        Args:
            task_type: Type of task
            response: LLM response
            prompt_template: Prompt template used
            metadata: Additional metadata
        """
        try:
            LLMUsageLog.objects.create(
                tenant=self.tenant,
                conversation=None,  # Will be set by caller if available
                model_name=response.model,
                task_type=task_type,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                estimated_cost_usd=response.estimated_cost,
                prompt_template=prompt_template,
                response_preview=response.content[:500],
                metadata=metadata
            )
            
            logger.info(
                f"Logged LLM usage: tenant={self.tenant.id}, "
                f"task={task_type}, model={response.model}, "
                f"tokens={response.total_tokens}, cost=${response.estimated_cost}"
            )
            
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {e}")
    
    def _get_agent_config(self) -> Optional[AgentConfiguration]:
        """Get agent configuration for tenant."""
        try:
            return AgentConfiguration.objects.get(tenant=self.tenant)
        except AgentConfiguration.DoesNotExist:
            return None
    
    def _build_intent_classification_prompt(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Build prompt for intent classification.
        
        Args:
            text: Message text
            context: Conversation context
            
        Returns:
            Formatted prompt
        """
        # Get valid intents
        valid_intents = [intent.value for intent in Intent]
        
        prompt = f"""Classify the following customer message into one of the predefined intents.

Customer message: "{text}"

Valid intents:
{', '.join(valid_intents)}

Context:
- Current flow: {context.get('current_flow', 'none')}
- Awaiting response: {context.get('awaiting_response', False)}

Respond with JSON in this exact format:
{{
    "intent": "INTENT_NAME",
    "confidence": 0.85,
    "slots": {{}},
    "reasoning": "brief explanation"
}}

Rules:
1. Intent MUST be one of the valid intents listed above
2. Confidence should be between 0.0 and 1.0
3. Extract any relevant slots (category, budget, quantity, date, time)
4. Keep reasoning brief (one sentence)
"""
        return prompt
    
    def _build_slot_extraction_prompt(
        self,
        text: str,
        intent: Intent,
        context: Dict[str, Any]
    ) -> str:
        """
        Build prompt for slot extraction.
        
        Args:
            text: Message text
            intent: Detected intent
            context: Conversation context
            
        Returns:
            Formatted prompt
        """
        prompt = f"""Extract structured information from the customer message.

Customer message: "{text}"
Detected intent: {intent.value}

Extract the following slots if present:
- category: product/service category (string)
- budget: maximum price (number)
- quantity: number of items (integer)
- date: date mentioned (ISO format or relative like "today", "tomorrow")
- time: time mentioned (24-hour format or relative like "morning", "afternoon")
- phone_number: phone number (E.164 format)

Respond with JSON in this exact format:
{{
    "category": "shoes",
    "budget": 5000,
    "quantity": 2
}}

Rules:
1. Only include slots that are explicitly mentioned
2. Convert numbers to appropriate types (int for quantity, float for budget)
3. Normalize phone numbers to E.164 format (+254...)
4. Return empty object {{}} if no slots found
"""
        return prompt
    
    def _build_rag_prompt(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        language: List[str]
    ) -> str:
        """
        Build prompt for RAG answer generation.
        
        Args:
            question: Customer's question
            chunks: Retrieved document chunks
            language: Detected language(s)
            
        Returns:
            Formatted prompt
        """
        # Format chunks
        context_text = "\n\n".join([
            f"[{i+1}] {chunk.get('text', '')}"
            for i, chunk in enumerate(chunks)
        ])
        
        # Determine response language
        lang_instruction = ""
        if 'sw' in language:
            lang_instruction = "Respond in Swahili."
        elif 'sheng' in language:
            lang_instruction = "Respond in Sheng (Kenyan slang)."
        else:
            lang_instruction = "Respond in English."
        
        prompt = f"""Answer the customer's question using ONLY the information provided below.

Context:
{context_text}

Question: {question}

Rules:
1. Answer ONLY from the context above
2. If the context doesn't contain the answer, say "I'm not sure about that. Let me connect you with someone from our team."
3. Keep your answer short and focused (2-3 sentences max)
4. {lang_instruction}
5. Never invent information
6. Cite the context number [1], [2], etc. if helpful

Answer:
"""
        return prompt


__all__ = ['LLMRouter']
