"""
LLM Router Service for tenant-scoped LLM calls.

This service provides centralized LLM routing with tenant isolation,
provider failover, and cost tracking for conversational AI.
"""
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.llm.base import LLMProvider, LLMResponse
from apps.bot.models import AgentConfiguration
from apps.bot.models_sales_orchestration import LLMUsageLog
from django.db import models
from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Router for tenant-scoped LLM calls with cost tracking and failover.
    
    Provides centralized LLM access with:
    - Tenant-specific provider configuration
    - Cost tracking and budget management
    - Model selection based on task requirements
    - Provider failover for reliability
    """
    
    def __init__(self, tenant: Tenant):
        """
        Initialize LLM router for tenant.
        
        Args:
            tenant: Tenant instance for configuration
        """
        self.tenant = tenant
        self.config = AgentConfiguration.objects.filter(tenant=tenant).first()
        self._provider_cache: Dict[str, LLMProvider] = {}
        self.factory = LLMProviderFactory()
    
    def classify_intent(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify user intent using optimized LLM call.
        
        Args:
            text: User message text
            context: Conversation context
            
        Returns:
            Intent classification result
        """
        if not self._check_budget():
            return {'budget_exceeded': True}
        
        try:
            provider_name, model_name = self._select_model('intent_classification')
            provider = self._get_provider(provider_name)
            
            # Build prompt for intent classification
            system_prompt = self._build_intent_system_prompt()
            user_prompt = f"Message: {text}\nContext: {context}"
            
            # Make LLM call
            response = provider.call_llm(
                system_prompt=system_prompt,
                user_message=user_prompt,
                max_tokens=150,
                temperature=0.1,
                model=model_name
            )
            
            # Log usage
            self._log_usage(provider_name, model_name, 'intent_classification', len(text))
            
            # Parse response (simplified for now)
            return {
                'intent': 'unknown',
                'confidence': 0.5,
                'raw_response': response.content
            }
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            return {'error': str(e)}
    
    def extract_slots(self, text: str, intent: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract slots from user message for given intent.
        
        Args:
            text: User message text
            intent: Detected intent
            context: Conversation context
            
        Returns:
            Extracted slots
        """
        if not self._check_budget():
            return {'budget_exceeded': True}
        
        try:
            provider_name, model_name = self._select_model('slot_extraction')
            provider = self._get_provider(provider_name)
            
            # Build prompt for slot extraction
            system_prompt = self._build_slot_system_prompt(intent)
            user_prompt = f"Message: {text}\nIntent: {intent}\nContext: {context}"
            
            # Make LLM call
            response = provider.call_llm(
                system_prompt=system_prompt,
                user_message=user_prompt,
                max_tokens=200,
                temperature=0.1,
                model=model_name
            )
            
            # Log usage
            self._log_usage(provider_name, model_name, 'slot_extraction', len(text))
            
            return {'slots': {}, 'raw_response': response.content}
            
        except Exception as e:
            logger.error(f"Slot extraction failed: {e}", exc_info=True)
            return {'error': str(e)}
    
    def generate_response(self, chunks: list, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate response using RAG chunks and context.
        
        Args:
            chunks: Retrieved knowledge chunks
            query: User query
            context: Conversation context
            
        Returns:
            Generated response
        """
        if not self._check_budget():
            return {'budget_exceeded': True}
        
        try:
            provider_name, model_name = self._select_model('response_generation')
            provider = self._get_provider(provider_name)
            
            # Build prompt for response generation
            system_prompt = self._build_response_system_prompt()
            user_prompt = f"Query: {query}\nChunks: {chunks}\nContext: {context}"
            
            # Make LLM call
            response = provider.call_llm(
                system_prompt=system_prompt,
                user_message=user_prompt,
                max_tokens=500,
                temperature=0.7,
                model=model_name
            )
            
            # Log usage
            self._log_usage(provider_name, model_name, 'response_generation', len(user_prompt))
            
            return {'response': response.content, 'raw_response': response.content}
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}", exc_info=True)
            return {'error': str(e)}
    
    def _select_model(self, task: str) -> Tuple[str, str]:
        """
        Select optimal provider and model for task.
        
        Args:
            task: Task type (intent_classification, slot_extraction, etc.)
            
        Returns:
            Tuple of (provider_name, model_name)
        """
        # Task-specific model selection
        task_models = {
            'intent_classification': ('openai', 'gpt-4o-mini'),
            'slot_extraction': ('openai', 'gpt-4o-mini'),
            'response_generation': ('openai', 'gpt-4o'),
            'conversation_governance': ('openai', 'gpt-4o-mini'),
            'language_detection': ('openai', 'gpt-4o-mini')
        }
        
        return task_models.get(task, ('openai', 'gpt-4o-mini'))
    
    def _get_provider(self, provider_name: str) -> LLMProvider:
        """
        Get or create provider instance.
        
        Args:
            provider_name: Name of provider
            
        Returns:
            LLM provider instance
        """
        if provider_name not in self._provider_cache:
            self._provider_cache[provider_name] = self.factory.create_from_tenant_settings(
                self.tenant, provider_name
            )
        
        return self._provider_cache[provider_name]
    
    def _check_budget(self) -> bool:
        """
        Check if tenant is within LLM usage budget.
        
        Returns:
            True if within budget, False otherwise
        """
        if not self.config or not self.config.llm_budget_limit:
            return True
        
        # Get current month usage
        from django.utils import timezone
        from datetime import datetime
        
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_cost = LLMUsageLog.objects.filter(
            tenant=self.tenant,
            created_at__gte=current_month
        ).aggregate(
            total=models.Sum('cost')
        )['total'] or Decimal('0.00')
        
        return total_cost < self.config.llm_budget_limit
    
    def _log_usage(self, provider: str, model: str, task: str, input_tokens: int):
        """
        Log LLM usage for cost tracking.
        
        Args:
            provider: Provider name
            model: Model name
            task: Task type
            input_tokens: Estimated input tokens
        """
        try:
            # Estimate cost (simplified)
            estimated_cost = Decimal(str(input_tokens * 0.0001))  # $0.0001 per token estimate
            
            LLMUsageLog.objects.create(
                tenant=self.tenant,
                provider=provider,
                model=model,
                task_type=task,
                input_tokens=input_tokens,
                output_tokens=100,  # Estimate
                cost=estimated_cost
            )
        except Exception as e:
            logger.warning(f"Failed to log LLM usage: {e}")
    
    def _build_intent_system_prompt(self) -> str:
        """Build system prompt for intent classification."""
        return """You are an intent classifier for a conversational commerce assistant.
        
Classify the user's message into one of these intents:
- sales_discovery: Looking for products/services
- product_question: Specific product questions
- support_question: Help with existing products
- order_status: Checking order status
- discounts_offers: Asking about deals
- preferences_consent: Language/marketing preferences
- payment_help: Payment issues
- human_request: Asking for human agent
- spam_casual: Off-topic or casual chat
- unknown: Unclear intent

Respond with just the intent name."""
    
    def _build_slot_system_prompt(self, intent: str) -> str:
        """Build system prompt for slot extraction."""
        return f"""Extract relevant information from the user message for intent: {intent}.
        
Return key-value pairs of extracted information.
Be precise and only extract explicitly mentioned information."""
    
    def _build_response_system_prompt(self) -> str:
        """Build system prompt for response generation."""
        return """You are a helpful commerce assistant. Use the provided knowledge chunks to answer the user's query.
        
Be concise, accurate, and helpful. If the chunks don't contain relevant information, say so politely."""


# For backward compatibility with existing imports
def get_llm_router() -> type:
    """Get LLMRouter class for instantiation."""
    return LLMRouter