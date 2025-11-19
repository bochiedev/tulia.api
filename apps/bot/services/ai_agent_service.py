"""
AI Agent Service for orchestrating intelligent customer service conversations.

This service is the core of the AI-powered customer service agent, coordinating
all aspects of message processing including context building, LLM interaction,
response generation, and handoff decisions.
"""
import logging
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from decimal import Decimal
from django.db import models
from django.utils import timezone

from apps.messaging.models import Message, Conversation
from apps.bot.models import AgentConfiguration, ConversationContext, AgentInteraction
from apps.bot.services.context_builder_service import (
    ContextBuilderService,
    AgentContext,
    create_context_builder_service
)
from apps.bot.services.agent_config_service import (
    AgentConfigurationService,
    create_agent_config_service
)
from apps.bot.services.llm.factory import LLMProviderFactory
from apps.bot.services.llm.base import LLMProvider, LLMResponse
from apps.bot.services.llm.provider_router import ProviderRouter
from apps.bot.services.llm.failover_manager import ProviderFailoverManager
from apps.bot.services.prompt_templates import PromptTemplateManager, PromptScenario
from apps.bot.services.fuzzy_matcher_service import FuzzyMatcherService
from apps.bot.services.rich_message_builder import (
    RichMessageBuilder,
    WhatsAppMessage,
    RichMessageValidationError
)
from apps.bot.services.feature_flags import FeatureFlagService
from apps.bot.services.rag_retriever_service import RAGRetrieverService
from apps.bot.services.context_synthesizer import ContextSynthesizer
from apps.bot.services.attribution_handler import AttributionHandler

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """
    Response from AI agent processing.
    
    Contains the generated response, metadata about processing,
    and handoff information if applicable.
    """
    # Response content
    content: str
    
    # Processing metadata
    model_used: str
    provider: str
    confidence_score: float
    processing_time_ms: int
    
    # Token usage and cost
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    
    # Handoff information
    should_handoff: bool = False
    handoff_reason: str = ''
    
    # Context information
    context_size_tokens: int = 0
    context_truncated: bool = False
    
    # Rich message support
    rich_message: Optional[WhatsAppMessage] = None
    use_rich_message: bool = False
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for serialization."""
        result = {
            'content': self.content,
            'model_used': self.model_used,
            'provider': self.provider,
            'confidence_score': self.confidence_score,
            'processing_time_ms': self.processing_time_ms,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'estimated_cost': str(self.estimated_cost),
            'should_handoff': self.should_handoff,
            'handoff_reason': self.handoff_reason,
            'context_size_tokens': self.context_size_tokens,
            'context_truncated': self.context_truncated,
            'use_rich_message': self.use_rich_message,
            'metadata': self.metadata,
        }
        
        if self.rich_message:
            result['rich_message'] = self.rich_message.to_dict()
        
        return result


class AIAgentService:
    """
    Core AI Agent Service for intelligent conversation handling.
    
    Orchestrates the entire AI agent workflow:
    1. Context building from multiple sources
    2. Model selection based on task complexity
    3. Prompt engineering with persona and context
    4. LLM interaction with retry logic
    5. Response generation and formatting
    6. Handoff decision making
    7. Analytics and tracking
    
    This service coordinates with:
    - ContextBuilderService: Assembles conversation context
    - AgentConfigurationService: Manages agent settings
    - LLMProviderFactory: Creates LLM provider instances
    - KnowledgeBaseService: Retrieves relevant knowledge
    """
    
    # Model selection thresholds
    SIMPLE_QUERY_MAX_TOKENS = 100  # Use mini model for short queries
    COMPLEX_REASONING_KEYWORDS = [
        'why', 'how', 'explain', 'compare', 'difference',
        'recommend', 'suggest', 'best', 'should i'
    ]
    
    def __init__(
        self,
        context_builder: Optional[ContextBuilderService] = None,
        config_service: Optional[AgentConfigurationService] = None,
        fuzzy_matcher: Optional[FuzzyMatcherService] = None,
        rich_message_builder: Optional[RichMessageBuilder] = None,
        provider_router: Optional[ProviderRouter] = None,
        failover_manager: Optional[ProviderFailoverManager] = None,
        rag_retriever: Optional[RAGRetrieverService] = None,
        context_synthesizer: Optional[ContextSynthesizer] = None,
        attribution_handler: Optional[AttributionHandler] = None
    ):
        """
        Initialize AI Agent Service.
        
        Args:
            context_builder: Optional ContextBuilderService instance
            config_service: Optional AgentConfigurationService instance
            fuzzy_matcher: Optional FuzzyMatcherService instance
            rich_message_builder: Optional RichMessageBuilder instance
            provider_router: Optional ProviderRouter instance
            failover_manager: Optional ProviderFailoverManager instance
            rag_retriever: Optional RAGRetrieverService instance
            context_synthesizer: Optional ContextSynthesizer instance
            attribution_handler: Optional AttributionHandler instance
        """
        self.context_builder = context_builder or create_context_builder_service()
        self.config_service = config_service or create_agent_config_service()
        self.fuzzy_matcher = fuzzy_matcher or FuzzyMatcherService()
        self.rich_message_builder = rich_message_builder or RichMessageBuilder()
        self.provider_router = provider_router or ProviderRouter()
        self.failover_manager = failover_manager or ProviderFailoverManager()
        
        # RAG components (initialized per-tenant in process_message)
        self.rag_retriever = rag_retriever
        self.context_synthesizer = context_synthesizer
        self.attribution_handler = attribution_handler
        
        # Track correction accuracy for improvement
        self.correction_stats = {
            'total_corrections': 0,
            'confirmed_corrections': 0,
            'rejected_corrections': 0
        }
        
        # Track rich message usage for analytics
        self.rich_message_stats = {
            'total_rich_messages': 0,
            'product_cards': 0,
            'service_cards': 0,
            'button_messages': 0,
            'list_messages': 0,
            'fallback_to_text': 0
        }
    
    def preprocess_message(
        self,
        message_text: str,
        tenant,
        agent_config: AgentConfiguration
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Pre-process customer message for spelling correction.
        
        Builds a vocabulary from catalog items and uses fuzzy matching
        to correct common spelling errors. Tracks corrections for
        improvement and confirmation.
        
        Args:
            message_text: Original customer message
            tenant: Tenant instance
            agent_config: AgentConfiguration for this tenant
            
        Returns:
            Tuple of (corrected_text, correction_metadata)
        """
        # Skip if spelling correction is disabled
        if not agent_config.enable_spelling_correction:
            return message_text, {}
        
        metadata = {
            'original_text': message_text,
            'corrections_made': [],
            'needs_confirmation': False
        }
        
        try:
            # Build vocabulary from catalog
            vocabulary = self._build_catalog_vocabulary(tenant)
            
            if not vocabulary:
                logger.debug("No vocabulary available for spelling correction")
                return message_text, metadata
            
            # Correct spelling
            corrected_text = self.fuzzy_matcher.correct_spelling(
                text=message_text,
                vocabulary=vocabulary,
                threshold=0.75
            )
            
            # Track corrections
            if corrected_text != message_text:
                # Find what was corrected
                original_words = set(message_text.lower().split())
                corrected_words = set(corrected_text.lower().split())
                
                changed_words = original_words.symmetric_difference(corrected_words)
                
                metadata['corrections_made'] = list(changed_words)
                metadata['corrected_text'] = corrected_text
                
                # Determine if confirmation is needed
                # (for now, always confirm corrections)
                metadata['needs_confirmation'] = True
                
                self.correction_stats['total_corrections'] += 1
                
                logger.info(
                    f"Spelling correction applied: '{message_text}' -> '{corrected_text}'"
                )
            
            return corrected_text, metadata
            
        except Exception as e:
            logger.error(f"Error in message preprocessing: {e}")
            return message_text, metadata
    
    def _build_catalog_vocabulary(self, tenant) -> List[str]:
        """
        Build vocabulary from catalog items for spelling correction.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            List of words from product and service titles
        """
        vocabulary = set()
        
        try:
            # Get product titles
            from apps.catalog.models import Product
            products = Product.objects.filter(
                tenant=tenant,
                is_active=True
            ).values_list('title', flat=True)
            
            for title in products:
                # Split title into words and add to vocabulary
                words = title.lower().split()
                vocabulary.update(words)
            
            # Get service titles
            from apps.services.models import Service
            services = Service.objects.filter(
                tenant=tenant,
                is_active=True
            ).values_list('title', flat=True)
            
            for title in services:
                # Split title into words and add to vocabulary
                words = title.lower().split()
                vocabulary.update(words)
            
            logger.debug(f"Built vocabulary with {len(vocabulary)} words")
            
        except Exception as e:
            logger.error(f"Error building vocabulary: {e}")
        
        return list(vocabulary)
    
    def process_message(
        self,
        message: Message,
        conversation: Conversation,
        tenant
    ) -> AgentResponse:
        """
        Process customer message and generate AI response.
        
        This is the main entry point for AI agent processing. It orchestrates
        all steps from context building to response generation.
        
        Args:
            message: Customer message to process
            conversation: Conversation instance
            tenant: Tenant instance
            
        Returns:
            AgentResponse with generated response and metadata
            
        Raises:
            Exception: On critical errors during processing
        """
        start_time = timezone.now()
        
        logger.info(
            f"Processing message {message.id} for conversation {conversation.id}, "
            f"tenant {tenant.id}"
        )
        
        try:
            # Sanitize customer message input
            from apps.bot.security_audit import InputSanitizer
            sanitized_text = InputSanitizer.sanitize_customer_message(message.text)
            
            # Update message text with sanitized version (in memory only, not saved)
            original_text = message.text
            message.text = sanitized_text
            
            # Get agent configuration
            agent_config = self.config_service.get_or_create_configuration(tenant)
            
            # Pre-process message for spelling correction
            processed_text, correction_metadata = self.preprocess_message(
                message_text=sanitized_text,
                tenant=tenant,
                agent_config=agent_config
            )
            
            # Create a temporary message object with corrected text for context building
            # (we don't modify the original message in the database)
            processed_message = message
            if correction_metadata.get('corrections_made'):
                # Store correction metadata for potential confirmation
                logger.info(
                    f"Message corrected: {len(correction_metadata['corrections_made'])} changes"
                )
            
            # Build comprehensive context
            context = self.context_builder.build_context(
                conversation=conversation,
                message=processed_message,
                tenant=tenant,
                max_tokens=100000  # GPT-4o context window
            )
            
            # Retrieve RAG context if enabled
            rag_context = None
            if self._should_use_rag(agent_config):
                rag_context = self.retrieve_rag_context(
                    query=processed_text,
                    conversation=conversation,
                    context=context,
                    agent_config=agent_config,
                    tenant=tenant
                )
                
                # Add RAG context to agent context
                if rag_context:
                    context.metadata['rag_context'] = rag_context
                    logger.info(
                        f"RAG retrieval completed: "
                        f"documents={len(rag_context.get('document_results', []))}, "
                        f"database={len(rag_context.get('database_results', []))}, "
                        f"internet={len(rag_context.get('internet_results', []))}"
                    )
            
            # Generate proactive suggestions
            suggestions = self.generate_suggestions(
                context=context,
                agent_config=agent_config,
                tenant=tenant
            )
            
            # Add suggestions to context metadata
            context.metadata['suggestions'] = suggestions
            
            # Select appropriate model
            model = self.select_model(message.text, agent_config)
            
            logger.info(f"Selected model: {model}")
            
            # Generate response using LLM (with suggestions in context)
            response = self.generate_response(
                context=context,
                agent_config=agent_config,
                model=model,
                tenant=tenant,
                suggestions=suggestions
            )
            
            # Add source attribution if RAG was used
            if rag_context and agent_config.enable_source_attribution:
                response = self.add_attribution_to_response(
                    response=response,
                    rag_context=rag_context,
                    agent_config=agent_config
                )
            
            # Calculate processing time
            end_time = timezone.now()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            response.processing_time_ms = processing_time_ms
            
            # Check if handoff is needed
            should_handoff, handoff_reason = self.should_handoff(
                response=response,
                conversation=conversation,
                agent_config=agent_config
            )
            
            response.should_handoff = should_handoff
            response.handoff_reason = handoff_reason
            
            # Update conversation status if handoff is needed
            if should_handoff:
                self._trigger_handoff(
                    conversation=conversation,
                    reason=handoff_reason
                )
            else:
                # Update low confidence tracking
                self._update_confidence_tracking(
                    conversation=conversation,
                    confidence_score=response.confidence_score,
                    threshold=agent_config.confidence_threshold
                )
            
            # Update conversation context
            self._update_conversation_context(
                context=context.context,
                message=message,
                response=response
            )
            
            # Add correction metadata to response
            if correction_metadata.get('corrections_made'):
                response.metadata['spelling_corrections'] = correction_metadata
            
            # Add suggestions metadata to response for tracking
            if suggestions and (suggestions.get('products') or suggestions.get('services')):
                response.metadata['suggestions'] = {
                    'product_count': len(suggestions.get('products', [])),
                    'service_count': len(suggestions.get('services', [])),
                    'reasoning': suggestions.get('reasoning', ''),
                    'priority': suggestions.get('priority', 'medium'),
                    'product_ids': [p.id for p in suggestions.get('products', [])],
                    'service_ids': [s.id for s in suggestions.get('services', [])]
                }
            
            # Enhance response with rich message if appropriate
            response = self.enhance_response_with_rich_message(
                response=response,
                context=context,
                agent_config=agent_config,
                tenant=tenant,
                suggestions=suggestions
            )
            
            logger.info(
                f"Message processed successfully: model={response.model_used}, "
                f"tokens={response.total_tokens}, cost=${response.estimated_cost}, "
                f"handoff={should_handoff}, rich_message={response.use_rich_message}, "
                f"suggestions={len(suggestions.get('products', [])) + len(suggestions.get('services', []))}"
            )
            
            # Track interaction for analytics
            interaction = self.track_interaction(
                conversation=conversation,
                message=message,
                response=response,
                detected_intents=response.metadata.get('detected_intents', [])
            )
            
            # Add feedback buttons if enabled and interaction was tracked
            if interaction and agent_config.enable_feedback_collection:
                response = self.add_feedback_buttons_to_response(
                    response=response,
                    interaction=interaction,
                    agent_config=agent_config
                )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error processing message {message.id}: {e}",
                exc_info=True
            )
            
            # Return fallback response
            fallback_response = self._create_fallback_response(
                error=str(e),
                processing_time_ms=int((timezone.now() - start_time).total_seconds() * 1000)
            )
            
            # Track fallback interaction
            self.track_interaction(
                conversation=conversation,
                message=message,
                response=fallback_response,
                detected_intents=[]
            )
            
            return fallback_response
    
    def generate_response(
        self,
        context: AgentContext,
        agent_config: AgentConfiguration,
        model: str,
        tenant,
        suggestions: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Generate AI response using LLM provider with smart routing and failover.
        
        Builds prompts with persona and context, uses provider router to select
        optimal provider/model, calls LLM with automatic failover, and processes
        the response into an AgentResponse object.
        
        Args:
            context: AgentContext with all context data
            agent_config: AgentConfiguration for this tenant
            model: Model identifier to use (can be overridden by router)
            tenant: Tenant instance
            suggestions: Optional suggestions to include in prompt
            
        Returns:
            AgentResponse with generated content and metadata
            
        Raises:
            Exception: On LLM API errors after all retries exhausted
        """
        logger.info(f"Generating response with model {model}")
        
        try:
            # Build prompts
            system_prompt = self._build_system_prompt(agent_config, context)
            user_prompt = self._build_user_prompt(context, suggestions)
            
            # Prepare messages for LLM
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
            
            # Check if multi-provider routing is enabled
            use_multi_provider = FeatureFlagService.is_enabled(
                'multi_provider_routing',
                tenant,
                default=True
            )
            
            if use_multi_provider:
                # Use provider router to select optimal provider/model
                routing_decision = self.provider_router.route(
                    messages=messages,
                    context_size=context.context_size_tokens,
                    preferred_provider=None,  # Let router decide
                    preferred_model=None  # Let router decide
                )
            else:
                # Fall back to default OpenAI model
                from apps.bot.services.llm.provider_router import RoutingDecision
                routing_decision = RoutingDecision(
                    provider='openai',
                    model=model,
                    reason='Multi-provider routing disabled',
                    estimated_cost_per_1k_tokens=0.00625,
                    complexity_score=0.5
                )
            
            logger.info(
                f"Router decision: {routing_decision.provider}/{routing_decision.model} "
                f"(complexity={routing_decision.complexity_score:.2f}, "
                f"reason={routing_decision.reason})"
            )
            
            # Call LLM with automatic failover
            llm_response, provider_used, model_used = self.failover_manager.execute_with_failover(
                provider_factory=LLMProviderFactory,
                tenant=tenant,
                messages=messages,
                primary_provider=routing_decision.provider,
                primary_model=routing_decision.model,
                temperature=agent_config.temperature,
                max_tokens=agent_config.max_response_length * 2  # Rough token estimate
            )
            
            # Calculate confidence score (simplified for now)
            confidence_score = self._calculate_confidence(
                llm_response=llm_response,
                context=context
            )
            
            # Create agent response
            response = AgentResponse(
                content=llm_response.content,
                model_used=model_used,
                provider=provider_used,
                confidence_score=confidence_score,
                processing_time_ms=0,  # Will be set by caller
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                total_tokens=llm_response.total_tokens,
                estimated_cost=llm_response.estimated_cost,
                context_size_tokens=context.context_size_tokens,
                context_truncated=context.truncated,
                metadata={
                    'finish_reason': llm_response.finish_reason,
                    'llm_metadata': llm_response.metadata,
                    'routing_decision': {
                        'provider': routing_decision.provider,
                        'model': routing_decision.model,
                        'reason': routing_decision.reason,
                        'complexity_score': routing_decision.complexity_score,
                        'estimated_cost_per_1k': routing_decision.estimated_cost_per_1k_tokens
                    },
                    'provider_used': provider_used,
                    'model_used': model_used,
                    # Store for provider tracking
                    '_llm_response': llm_response,
                    '_routing_decision': routing_decision
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            raise
    
    def detect_rich_message_opportunity(
        self,
        response: AgentResponse,
        context: AgentContext,
        agent_config: AgentConfiguration,
        suggestions: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Any]]:
        """
        Detect if the response would benefit from a rich message format.
        
        Analyzes the response content and context to determine if a rich
        message (product card, service card, list, buttons) would enhance
        the customer experience.
        
        Args:
            response: AgentResponse from LLM
            context: AgentContext with conversation data
            agent_config: AgentConfiguration for this tenant
            suggestions: Optional suggestions to present as rich messages
            
        Returns:
            Tuple of (should_use_rich: bool, message_type: str, data: Any)
            where message_type is 'product_card', 'service_card', 'list', 'button'
            and data is the relevant product/service/items
        """
        # Skip if rich messages are disabled
        if not agent_config.enable_rich_messages:
            return False, '', None
        
        response_lower = response.content.lower()
        
        # Check if response mentions suggestions and we have suggestions to show
        if suggestions and (suggestions.get('products') or suggestions.get('services')):
            suggestion_keywords = ['suggest', 'recommend', 'might like', 'consider', 'check out']
            if any(keyword in response_lower for keyword in suggestion_keywords):
                # Prioritize showing suggestions as rich messages
                if suggestions.get('products') and len(suggestions['products']) > 0:
                    if len(suggestions['products']) == 1:
                        logger.info("Detected suggestion product card opportunity")
                        return True, 'product_card', suggestions['products'][0]
                    else:
                        logger.info(f"Detected suggestion product list opportunity ({len(suggestions['products'])} items)")
                        return True, 'product_list', suggestions['products']
                
                if suggestions.get('services') and len(suggestions['services']) > 0:
                    if len(suggestions['services']) == 1:
                        logger.info("Detected suggestion service card opportunity")
                        return True, 'service_card', suggestions['services'][0]
                    else:
                        logger.info(f"Detected suggestion service list opportunity ({len(suggestions['services'])} items)")
                        return True, 'service_list', suggestions['services']
        
        # Check for product mentions
        if any(word in response_lower for word in ['product', 'item', 'buy', 'purchase', 'price']):
            # Check if context has a specific product
            if context.last_product_viewed:
                logger.info(f"Detected product card opportunity for product {context.last_product_viewed.id}")
                return True, 'product_card', context.last_product_viewed
            
            # Check if there are products in catalog context
            if context.catalog_context and context.catalog_context.get('products'):
                products = context.catalog_context['products']
                if len(products) == 1:
                    logger.info(f"Detected product card opportunity for single product")
                    return True, 'product_card', products[0]
                elif 2 <= len(products) <= 10:
                    logger.info(f"Detected product list opportunity for {len(products)} products")
                    return True, 'product_list', products
        
        # Check for service mentions
        if any(word in response_lower for word in ['service', 'appointment', 'book', 'schedule', 'available']):
            # Check if context has a specific service
            if context.last_service_viewed:
                logger.info(f"Detected service card opportunity for service {context.last_service_viewed.id}")
                return True, 'service_card', context.last_service_viewed
            
            # Check if there are services in catalog context
            if context.catalog_context and context.catalog_context.get('services'):
                services = context.catalog_context['services']
                if len(services) == 1:
                    logger.info(f"Detected service card opportunity for single service")
                    return True, 'service_card', services[0]
                elif 2 <= len(services) <= 10:
                    logger.info(f"Detected service list opportunity for {len(services)} services")
                    return True, 'service_list', services
        
        # Check for yes/no questions (button opportunity)
        if any(phrase in response_lower for phrase in [
            'would you like',
            'do you want',
            'shall i',
            'confirm',
            'proceed',
            'continue'
        ]):
            logger.info("Detected button message opportunity for yes/no question")
            return True, 'yes_no_buttons', None
        
        return False, '', None
    
    def generate_rich_message(
        self,
        message_type: str,
        data: Any,
        response_content: str,
        tenant
    ) -> Optional[WhatsAppMessage]:
        """
        Generate a rich WhatsApp message based on detected opportunity.
        
        Args:
            message_type: Type of rich message to generate
            data: Data for the message (product, service, items, etc.)
            response_content: Original text response content
            tenant: Tenant instance
            
        Returns:
            WhatsAppMessage instance or None if generation fails
        """
        try:
            if message_type == 'product_card':
                # Generate product card
                self.rich_message_stats['product_cards'] += 1
                return self.rich_message_builder.build_product_card(
                    product=data,
                    actions=['buy', 'details'],
                    include_stock=True
                )
            
            elif message_type == 'service_card':
                # Generate service card
                self.rich_message_stats['service_cards'] += 1
                return self.rich_message_builder.build_service_card(
                    service=data,
                    actions=['book', 'availability']
                )
            
            elif message_type == 'product_list':
                # Generate product list
                self.rich_message_stats['list_messages'] += 1
                items = [
                    {
                        'id': str(product.id),
                        'title': product.title,
                        'description': f"{self.rich_message_builder._format_price(product.price, product.currency)}"
                    }
                    for product in data[:10]  # Limit to 10 items
                ]
                return self.rich_message_builder.build_list_message(
                    title='Choose a product',
                    items=items,
                    button_text='Select',
                    body=response_content
                )
            
            elif message_type == 'service_list':
                # Generate service list
                self.rich_message_stats['list_messages'] += 1
                items = [
                    {
                        'id': str(service.id),
                        'title': service.title,
                        'description': f"{self.rich_message_builder._format_price(service.base_price, service.currency)}" if service.base_price else "Book now"
                    }
                    for service in data[:10]  # Limit to 10 items
                ]
                return self.rich_message_builder.build_list_message(
                    title='Choose a service',
                    items=items,
                    button_text='Select',
                    body=response_content
                )
            
            elif message_type == 'yes_no_buttons':
                # Generate yes/no buttons
                self.rich_message_stats['button_messages'] += 1
                buttons = [
                    {'id': 'yes', 'text': 'Yes'},
                    {'id': 'no', 'text': 'No'}
                ]
                return self.rich_message_builder.build_button_message(
                    text=response_content,
                    buttons=buttons
                )
            
            else:
                logger.warning(f"Unknown rich message type: {message_type}")
                return None
        
        except RichMessageValidationError as e:
            logger.warning(f"Rich message validation failed: {e}")
            self.rich_message_stats['fallback_to_text'] += 1
            return None
        
        except Exception as e:
            logger.error(f"Error generating rich message: {e}", exc_info=True)
            self.rich_message_stats['fallback_to_text'] += 1
            return None
    
    def enhance_response_with_rich_message(
        self,
        response: AgentResponse,
        context: AgentContext,
        agent_config: AgentConfiguration,
        tenant,
        suggestions: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Enhance agent response with rich message if appropriate.
        
        Detects opportunities for rich messages and generates them,
        falling back to text if rich messages are unavailable or fail.
        
        Args:
            response: AgentResponse from LLM
            context: AgentContext with conversation data
            agent_config: AgentConfiguration for this tenant
            tenant: Tenant instance
            suggestions: Optional suggestions to present as rich messages
            
        Returns:
            Enhanced AgentResponse with rich_message field populated
        """
        # Detect rich message opportunity
        should_use_rich, message_type, data = self.detect_rich_message_opportunity(
            response=response,
            context=context,
            agent_config=agent_config,
            suggestions=suggestions
        )
        
        if not should_use_rich:
            return response
        
        # Generate rich message
        rich_message = self.generate_rich_message(
            message_type=message_type,
            data=data,
            response_content=response.content,
            tenant=tenant
        )
        
        if rich_message:
            # Validate the rich message
            try:
                self.rich_message_builder.validate_message(rich_message)
                
                # Update response with rich message
                response.rich_message = rich_message
                response.use_rich_message = True
                response.metadata['rich_message_type'] = message_type
                
                self.rich_message_stats['total_rich_messages'] += 1
                
                logger.info(
                    f"Enhanced response with rich message",
                    extra={
                        'message_type': message_type,
                        'has_media': bool(rich_message.media_url),
                        'has_buttons': bool(rich_message.buttons),
                        'has_list': bool(rich_message.list_data)
                    }
                )
            
            except RichMessageValidationError as e:
                logger.warning(f"Rich message validation failed, falling back to text: {e}")
                response.metadata['rich_message_fallback_reason'] = str(e)
                self.rich_message_stats['fallback_to_text'] += 1
        else:
            logger.debug("Rich message generation returned None, using text response")
            response.metadata['rich_message_fallback_reason'] = 'generation_failed'
            self.rich_message_stats['fallback_to_text'] += 1
        
        return response
    
    def add_feedback_buttons_to_response(
        self,
        response: AgentResponse,
        interaction: AgentInteraction,
        agent_config: AgentConfiguration
    ) -> AgentResponse:
        """
        Add feedback buttons to agent response.
        
        Adds thumbs up/down buttons to collect user feedback on bot responses.
        Respects feedback frequency settings (always/sometimes/never).
        
        Args:
            response: AgentResponse to enhance
            interaction: AgentInteraction that was just created
            agent_config: AgentConfiguration for this tenant
            
        Returns:
            Enhanced AgentResponse with feedback buttons
        """
        # Check if we should add feedback buttons based on frequency
        should_add = self._should_add_feedback_buttons(
            interaction=interaction,
            frequency=agent_config.feedback_frequency
        )
        
        if not should_add:
            logger.debug("Skipping feedback buttons based on frequency setting")
            return response
        
        # If response already has rich message, don't override it
        # (feedback buttons are less important than product/service cards)
        if response.use_rich_message and response.rich_message:
            logger.debug("Response already has rich message, skipping feedback buttons")
            response.metadata['feedback_skipped'] = 'has_rich_message'
            return response
        
        try:
            # Create feedback button message
            feedback_message = self.rich_message_builder.add_feedback_buttons(
                message_body=response.content,
                interaction_id=interaction.id,
                include_comment=False  # Keep it simple with just thumbs up/down
            )
            
            # Update response with feedback buttons
            response.rich_message = feedback_message
            response.use_rich_message = True
            response.metadata['has_feedback_buttons'] = True
            
            logger.info(f"Added feedback buttons to response for interaction {interaction.id}")
            
        except Exception as e:
            logger.error(f"Error adding feedback buttons: {e}", exc_info=True)
            response.metadata['feedback_error'] = str(e)
        
        return response
    
    def _should_add_feedback_buttons(
        self,
        interaction: AgentInteraction,
        frequency: str
    ) -> bool:
        """
        Determine if feedback buttons should be added based on frequency setting.
        
        Args:
            interaction: Current AgentInteraction
            frequency: Feedback frequency setting ('always', 'sometimes', 'never')
            
        Returns:
            bool: True if feedback buttons should be added
        """
        if frequency == 'never':
            return False
        
        if frequency == 'always':
            return True
        
        if frequency == 'sometimes':
            # Show feedback every 3rd message
            # Count interactions for this conversation
            interaction_count = AgentInteraction.objects.filter(
                conversation=interaction.conversation,
                tenant=interaction.tenant,
                is_deleted=False
            ).count()
            
            return interaction_count % 3 == 0
        
        # Default to sometimes
        return True
    
    def should_handoff(
        self,
        response: AgentResponse,
        conversation: Conversation,
        agent_config: AgentConfiguration
    ) -> Tuple[bool, str]:
        """
        Determine if conversation should be handed off to human.
        
        Implements intelligent handoff logic checking multiple criteria:
        1. Confidence threshold - Low confidence in response
        2. Consecutive low-confidence tracking - Multiple failed attempts
        3. Explicit customer request - Customer asks for human
        4. Topic-based auto-handoff - Sensitive topics requiring human
        5. Agent suggestion - AI determines it cannot help
        
        Args:
            response: AgentResponse from LLM
            conversation: Conversation instance
            agent_config: AgentConfiguration for this tenant
            
        Returns:
            Tuple of (should_handoff: bool, reason: str)
        """
        # 1. Check confidence threshold
        if response.confidence_score < agent_config.confidence_threshold:
            logger.info(
                f"Low confidence detected: {response.confidence_score:.2f} < "
                f"{agent_config.confidence_threshold:.2f}"
            )
            
            # Check consecutive low confidence count
            if conversation.low_confidence_count >= agent_config.max_low_confidence_attempts - 1:
                logger.warning(
                    f"Triggering handoff due to {conversation.low_confidence_count + 1} "
                    f"consecutive low-confidence responses"
                )
                return True, 'consecutive_low_confidence'
            
            # Don't handoff yet, but this counts as a low-confidence attempt
            return False, ''
        
        # 2. Check for explicit customer request for human
        # Get the last customer message
        last_message = conversation.messages.filter(direction='in').last()
        if last_message:
            message_lower = last_message.text.lower()
            
            customer_request_phrases = [
                'speak to a human',
                'talk to a person',
                'human agent',
                'real person',
                'live agent',
                'customer service',
                'speak to someone',
                'talk to someone',
                'connect me to',
                'transfer me to'
            ]
            
            for phrase in customer_request_phrases:
                if phrase in message_lower:
                    logger.info(f"Customer explicitly requested human: '{phrase}'")
                    return True, 'customer_requested_human'
        
        # 3. Check for agent-suggested handoff in response
        handoff_phrases = [
            'connect you with',
            'transfer you to',
            'speak with a human',
            'human agent',
            'live agent',
            'escalate',
            'specialist can help'
        ]
        
        response_lower = response.content.lower()
        for phrase in handoff_phrases:
            if phrase in response_lower:
                logger.info(f"Agent suggested handoff: '{phrase}'")
                return True, 'agent_suggested_handoff'
        
        # 4. Check auto-handoff topics
        if last_message:
            message_lower = last_message.text.lower()
            for topic in agent_config.auto_handoff_topics:
                if topic.lower() in message_lower:
                    logger.info(f"Auto-handoff topic detected: {topic}")
                    return True, f'auto_handoff_topic:{topic}'
        
        # 5. Check for complex issues that typically require human intervention
        complex_issue_indicators = [
            'refund',
            'complaint',
            'legal',
            'lawsuit',
            'lawyer',
            'attorney',
            'sue',
            'fraud',
            'scam',
            'emergency',
            'urgent',
            'critical'
        ]
        
        if last_message:
            message_lower = last_message.text.lower()
            for indicator in complex_issue_indicators:
                if indicator in message_lower:
                    logger.info(f"Complex issue indicator detected: {indicator}")
                    return True, f'complex_issue:{indicator}'
        
        # No handoff needed
        return False, ''
    
    def select_model(
        self,
        message_text: str,
        agent_config: AgentConfiguration
    ) -> str:
        """
        Select appropriate model based on task complexity.
        
        Selection logic:
        1. Simple queries (< 100 chars, no complex keywords) -> gpt-4o-mini
        2. Complex reasoning (contains reasoning keywords) -> o1-preview
        3. Default -> configured default model
        
        Args:
            message_text: Customer message text
            agent_config: AgentConfiguration for this tenant
            
        Returns:
            Model identifier string
        """
        message_lower = message_text.lower()
        
        # Check for simple query
        if len(message_text) < self.SIMPLE_QUERY_MAX_TOKENS:
            # Check if it's truly simple (no complex keywords)
            has_complex_keywords = any(
                keyword in message_lower
                for keyword in self.COMPLEX_REASONING_KEYWORDS
            )
            
            if not has_complex_keywords:
                logger.debug("Selected gpt-4o-mini for simple query")
                return 'gpt-4o-mini'
        
        # Check for complex reasoning
        has_reasoning_keywords = any(
            keyword in message_lower
            for keyword in self.COMPLEX_REASONING_KEYWORDS
        )
        
        if has_reasoning_keywords and len(message_text) > 50:
            logger.debug("Selected o1-preview for complex reasoning")
            return 'o1-preview'
        
        # Use default model
        logger.debug(f"Selected default model: {agent_config.default_model}")
        return agent_config.default_model
    
    def _build_system_prompt(
        self,
        agent_config: AgentConfiguration,
        context: AgentContext
    ) -> str:
        """
        Build system prompt with persona and instructions.
        
        Detects conversation scenario and applies appropriate prompt template
        with persona customization.
        
        Args:
            agent_config: AgentConfiguration for this tenant
            context: AgentContext with conversation data
            
        Returns:
            Complete system prompt string
        """
        # Detect scenario from message and context
        scenario = PromptTemplateManager.detect_scenario(
            message_text=context.current_message.text,
            context=context
        )
        
        logger.debug(f"Detected scenario: {scenario}")
        
        # Get base prompt for scenario
        base_prompt = PromptTemplateManager.get_system_prompt(
            scenario=scenario,
            include_scenario_guidance=True
        )
        
        # Apply persona
        enhanced_prompt = self.config_service.apply_persona(
            base_prompt=base_prompt,
            config=agent_config
        )
        
        return enhanced_prompt
    
    def _build_user_prompt(
        self,
        context: AgentContext,
        suggestions: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build user prompt with context assembly.
        
        Uses PromptTemplateManager to assemble all context information
        into a structured prompt for the LLM, including new features like
        reference context, browse sessions, language preferences, etc.
        
        Args:
            context: AgentContext with all context data
            suggestions: Optional suggestions to include in prompt
            
        Returns:
            Complete user prompt string
        """
        # Extract context data
        conversation_summary = None
        key_facts = None
        reference_context = None
        browse_session = None
        language_preference = None
        product_analysis = None
        clarification_count = 0
        preferences = {}
        
        if context.context:
            conversation_summary = context.context.conversation_summary
            key_facts = context.context.key_facts
        
        # Get reference context if available
        try:
            from apps.bot.services.reference_context_manager import ReferenceContextManager
            ref_manager = ReferenceContextManager()
            reference_context = ref_manager.get_current_list(context.conversation)
        except Exception as e:
            logger.debug(f"No reference context available: {e}")
        
        # Get browse session if available
        try:
            from apps.bot.models import BrowseSession
            browse_session = BrowseSession.objects.filter(
                conversation=context.conversation,
                is_active=True
            ).first()
        except Exception as e:
            logger.debug(f"No browse session available: {e}")
        
        # Get language preference if available
        try:
            from apps.bot.models import LanguagePreference
            language_preference = LanguagePreference.objects.filter(
                conversation=context.conversation
            ).first()
        except Exception as e:
            logger.debug(f"No language preference available: {e}")
        
        # Get product analysis if viewing a specific product
        if context.last_product_viewed:
            try:
                from apps.bot.models import ProductAnalysis
                product_analysis = ProductAnalysis.objects.filter(
                    product=context.last_product_viewed
                ).first()
            except Exception as e:
                logger.debug(f"No product analysis available: {e}")
        
        # Get clarification context from conversation metadata
        if context.conversation.metadata:
            clarification_count = context.conversation.metadata.get('clarification_count', 0)
            preferences = context.conversation.metadata.get('extracted_preferences', {})
        
        # Build complete prompt using template manager
        base_prompt = PromptTemplateManager.build_complete_user_prompt(
            current_message=context.current_message.text,
            conversation_history=context.conversation_history,
            knowledge_entries=context.relevant_knowledge,
            products=context.catalog_context.products,
            services=context.catalog_context.services,
            customer_history=context.customer_history,
            conversation_summary=conversation_summary,
            key_facts=key_facts,
            reference_context=reference_context,
            browse_session=browse_session,
            language_preference=language_preference,
            product_analysis=product_analysis,
            clarification_count=clarification_count,
            preferences=preferences
        )
        
        # Add RAG context if available
        rag_context = context.metadata.get('rag_context')
        if rag_context:
            rag_section = self._build_rag_context_section(rag_context)
            base_prompt = base_prompt + "\n\n" + rag_section
        
        # Add suggestions if available and enabled
        if suggestions and (suggestions.get('products') or suggestions.get('services')):
            suggestions_section = self._build_suggestions_section(suggestions)
            base_prompt = base_prompt + "\n\n" + suggestions_section
        
        return base_prompt
    
    def _build_suggestions_section(self, suggestions: Dict[str, Any]) -> str:
        """
        Build suggestions section for prompt.
        
        Args:
            suggestions: Dictionary with products, services, reasoning, and priority
            
        Returns:
            Formatted suggestions section
        """
        sections = ["## Proactive Suggestions"]
        
        if suggestions.get('reasoning'):
            sections.append(f"\n{suggestions['reasoning']}")
        
        if suggestions.get('products'):
            sections.append("\n### Suggested Products:")
            for product in suggestions['products']:
                price_str = f"${product.price:.2f}" if product.price else "Price available"
                stock_str = "In stock" if product.is_in_stock else "Out of stock"
                sections.append(f"- **{product.title}**: {price_str} ({stock_str})")
        
        if suggestions.get('services'):
            sections.append("\n### Suggested Services:")
            for service in suggestions['services']:
                price_str = f"${service.base_price:.2f}" if service.base_price else "Price available"
                sections.append(f"- **{service.title}**: {price_str}")
        
        sections.append("\nYou may mention these suggestions naturally in your response if they're relevant to the customer's inquiry. Don't force suggestions if they don't fit the conversation context.")
        
        return "\n".join(sections)
    
    def _calculate_confidence(
        self,
        llm_response: LLMResponse,
        context: AgentContext
    ) -> float:
        """
        Calculate confidence score for response.
        
        This is a simplified confidence calculation. In production,
        this could be enhanced with:
        - Semantic similarity to knowledge base
        - Response coherence metrics
        - Uncertainty detection in response text
        - Model-specific confidence signals
        
        Args:
            llm_response: LLMResponse from LLM
            context: AgentContext used for generation
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.8  # Base confidence
        
        # Reduce confidence if no knowledge base entries were relevant
        if not context.relevant_knowledge:
            confidence -= 0.1
        
        # Reduce confidence if response contains uncertainty phrases
        uncertainty_phrases = [
            "i'm not sure",
            "i don't know",
            "i cannot",
            "i'm unable",
            "unclear",
            "uncertain"
        ]
        
        response_lower = llm_response.content.lower()
        for phrase in uncertainty_phrases:
            if phrase in response_lower:
                confidence -= 0.2
                break
        
        # Increase confidence if knowledge was used
        if context.relevant_knowledge and len(context.relevant_knowledge) > 0:
            avg_similarity = sum(score for _, score in context.relevant_knowledge) / len(context.relevant_knowledge)
            if avg_similarity > 0.8:
                confidence += 0.1
        
        # Ensure confidence is between 0 and 1
        confidence = max(0.0, min(1.0, confidence))
        
        return confidence
    
    def _trigger_handoff(
        self,
        conversation: Conversation,
        reason: str
    ) -> None:
        """
        Trigger handoff to human agent.
        
        Updates conversation status and logs the handoff reason.
        
        Args:
            conversation: Conversation to handoff
            reason: Reason for handoff
        """
        try:
            logger.info(
                f"Triggering handoff for conversation {conversation.id}: {reason}"
            )
            
            # Mark conversation for handoff
            conversation.mark_handoff()
            
            # Store handoff reason in metadata
            if not conversation.metadata:
                conversation.metadata = {}
            
            conversation.metadata['last_handoff_reason'] = reason
            conversation.metadata['last_handoff_at'] = timezone.now().isoformat()
            conversation.save(update_fields=['metadata'])
            
            logger.info(f"Handoff triggered successfully for conversation {conversation.id}")
            
        except Exception as e:
            logger.error(f"Error triggering handoff: {e}", exc_info=True)
    
    def _update_confidence_tracking(
        self,
        conversation: Conversation,
        confidence_score: float,
        threshold: float
    ) -> None:
        """
        Update consecutive low-confidence tracking.
        
        Increments counter if confidence is low, resets if high.
        
        Args:
            conversation: Conversation instance
            confidence_score: Current response confidence
            threshold: Confidence threshold
        """
        try:
            if confidence_score < threshold:
                # Increment low confidence counter
                conversation.increment_low_confidence()
                logger.debug(
                    f"Low confidence count incremented to {conversation.low_confidence_count} "
                    f"for conversation {conversation.id}"
                )
            else:
                # Reset counter on high confidence
                if conversation.low_confidence_count > 0:
                    conversation.reset_low_confidence()
                    logger.debug(
                        f"Low confidence count reset for conversation {conversation.id}"
                    )
        except Exception as e:
            logger.error(f"Error updating confidence tracking: {e}")
    
    def _update_conversation_context(
        self,
        context: Optional[ConversationContext],
        message: Message,
        response: AgentResponse
    ) -> None:
        """
        Update conversation context after processing.
        
        Args:
            context: ConversationContext to update
            message: Customer message
            response: AgentResponse generated
        """
        if not context:
            return
        
        try:
            # Extend expiration
            context.extend_expiration(minutes=30)
            
            # Update last interaction timestamp (auto-updated by model)
            context.save()
            
            logger.debug(f"Updated conversation context for conversation {context.conversation_id}")
            
        except Exception as e:
            logger.error(f"Error updating conversation context: {e}")
    
    def generate_suggestions(
        self,
        context: AgentContext,
        agent_config: AgentConfiguration,
        tenant
    ) -> Dict[str, Any]:
        """
        Generate proactive suggestions based on context and customer history.
        
        Analyzes conversation context, customer history, and catalog to provide
        personalized recommendations. Suggestions include:
        - Complementary products/services
        - Items based on customer preferences
        - Available appointments
        - Popular or featured items
        
        Args:
            context: AgentContext with conversation and customer data
            agent_config: AgentConfiguration for this tenant
            tenant: Tenant instance
            
        Returns:
            Dictionary with suggestions:
            {
                'products': [list of suggested products],
                'services': [list of suggested services],
                'reasoning': 'explanation for suggestions',
                'priority': 'high|medium|low'
            }
        """
        # Skip if proactive suggestions are disabled
        if not agent_config.enable_proactive_suggestions:
            return {
                'products': [],
                'services': [],
                'reasoning': '',
                'priority': 'low'
            }
        
        suggestions = {
            'products': [],
            'services': [],
            'reasoning': '',
            'priority': 'medium'
        }
        
        try:
            # Analyze current context for suggestion opportunities
            current_message = context.current_message.text.lower()
            
            # 1. Suggest complementary items if customer is viewing a product/service
            if context.last_product_viewed:
                complementary_products = self._get_complementary_products(
                    product=context.last_product_viewed,
                    tenant=tenant,
                    limit=3
                )
                suggestions['products'].extend(complementary_products)
                suggestions['reasoning'] = f"Based on your interest in {context.last_product_viewed.title}"
                suggestions['priority'] = 'high'
            
            if context.last_service_viewed:
                complementary_services = self._get_complementary_services(
                    service=context.last_service_viewed,
                    tenant=tenant,
                    limit=3
                )
                suggestions['services'].extend(complementary_services)
                suggestions['reasoning'] = f"Based on your interest in {context.last_service_viewed.title}"
                suggestions['priority'] = 'high'
            
            # 2. Use customer history for personalized recommendations
            if context.customer_history:
                history_based = self._get_history_based_suggestions(
                    customer_history=context.customer_history,
                    tenant=tenant,
                    limit=3
                )
                
                # Add products from history
                if history_based.get('products'):
                    suggestions['products'].extend(history_based['products'])
                    if not suggestions['reasoning']:
                        suggestions['reasoning'] = "Based on your previous purchases"
                        suggestions['priority'] = 'high'
                
                # Add services from history
                if history_based.get('services'):
                    suggestions['services'].extend(history_based['services'])
                    if not suggestions['reasoning']:
                        suggestions['reasoning'] = "Based on your previous bookings"
                        suggestions['priority'] = 'high'
            
            # 3. Suggest based on current conversation topic
            if not suggestions['products'] and not suggestions['services']:
                topic_based = self._get_topic_based_suggestions(
                    message_text=current_message,
                    context=context,
                    tenant=tenant,
                    limit=3
                )
                
                suggestions['products'].extend(topic_based.get('products', []))
                suggestions['services'].extend(topic_based.get('services', []))
                
                if suggestions['products'] or suggestions['services']:
                    suggestions['reasoning'] = "Based on what you're looking for"
                    suggestions['priority'] = 'medium'
            
            # 4. Prioritize available inventory and appointments
            suggestions['products'] = self._filter_available_products(
                products=suggestions['products'],
                limit=3
            )
            
            suggestions['services'] = self._filter_available_services(
                services=suggestions['services'],
                tenant=tenant,
                limit=3
            )
            
            # Remove duplicates
            suggestions['products'] = self._deduplicate_items(suggestions['products'])
            suggestions['services'] = self._deduplicate_items(suggestions['services'])
            
            logger.info(
                f"Generated {len(suggestions['products'])} product and "
                f"{len(suggestions['services'])} service suggestions"
            )
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}", exc_info=True)
        
        return suggestions
    
    def _get_complementary_products(
        self,
        product,
        tenant,
        limit: int = 3
    ) -> List:
        """
        Get complementary products based on a viewed product.
        
        Uses product metadata, category, and price range to find
        complementary items.
        
        Args:
            product: Product instance
            tenant: Tenant instance
            limit: Maximum number of suggestions
            
        Returns:
            List of Product instances
        """
        from apps.catalog.models import Product
        
        try:
            # Get products in similar price range (±30%)
            price_min = product.price * Decimal('0.7')
            price_max = product.price * Decimal('1.3')
            
            complementary = Product.objects.filter(
                tenant=tenant,
                is_active=True,
                price__gte=price_min,
                price__lte=price_max
            ).exclude(
                id=product.id
            ).order_by('-created_at')[:limit]
            
            return list(complementary)
            
        except Exception as e:
            logger.error(f"Error getting complementary products: {e}")
            return []
    
    def _get_complementary_services(
        self,
        service,
        tenant,
        limit: int = 3
    ) -> List:
        """
        Get complementary services based on a viewed service.
        
        Args:
            service: Service instance
            tenant: Tenant instance
            limit: Maximum number of suggestions
            
        Returns:
            List of Service instances
        """
        from apps.services.models import Service
        
        try:
            # Get other active services
            complementary = Service.objects.filter(
                tenant=tenant,
                is_active=True
            ).exclude(
                id=service.id
            ).order_by('-created_at')[:limit]
            
            result = list(complementary)
            logger.debug(f"Found {len(result)} complementary services for service {service.id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting complementary services: {e}", exc_info=True)
            return []
    
    def _get_history_based_suggestions(
        self,
        customer_history: Dict[str, Any],
        tenant,
        limit: int = 3
    ) -> Dict[str, List]:
        """
        Get suggestions based on customer purchase and booking history.
        
        Analyzes past orders and appointments to suggest:
        - Repurchase of previously bought items
        - Similar items to past purchases
        - Services previously booked
        
        Args:
            customer_history: Dictionary with orders and appointments
            tenant: Tenant instance
            limit: Maximum number of suggestions per category
            
        Returns:
            Dictionary with 'products' and 'services' lists
        """
        from apps.catalog.models import Product
        from apps.services.models import Service
        
        suggestions = {
            'products': [],
            'services': []
        }
        
        try:
            # Get products from past orders
            past_orders = customer_history.get('orders', [])
            if past_orders:
                # Extract product IDs from order items
                product_ids = set()
                for order in past_orders[:5]:  # Look at last 5 orders
                    items = order.get('items', [])
                    for item in items:
                        if 'product_id' in item:
                            product_ids.add(item['product_id'])
                
                # Get those products (for repurchase suggestions)
                if product_ids:
                    products = Product.objects.filter(
                        tenant=tenant,
                        id__in=list(product_ids),
                        is_active=True
                    )[:limit]
                    suggestions['products'].extend(list(products))
            
            # Get services from past appointments
            past_appointments = customer_history.get('appointments', [])
            if past_appointments:
                # Extract service IDs
                service_ids = set()
                for appointment in past_appointments[:5]:  # Look at last 5 appointments
                    if 'service_id' in appointment:
                        service_ids.add(appointment['service_id'])
                
                # Get those services (for rebooking suggestions)
                if service_ids:
                    services = Service.objects.filter(
                        tenant=tenant,
                        id__in=list(service_ids),
                        is_active=True
                    )[:limit]
                    suggestions['services'].extend(list(services))
            
        except Exception as e:
            logger.error(f"Error getting history-based suggestions: {e}")
        
        return suggestions
    
    def _get_topic_based_suggestions(
        self,
        message_text: str,
        context: AgentContext,
        tenant,
        limit: int = 3
    ) -> Dict[str, List]:
        """
        Get suggestions based on current conversation topic.
        
        Uses fuzzy matching to find products/services mentioned in
        the customer's message.
        
        Args:
            message_text: Customer message text
            context: AgentContext
            tenant: Tenant instance
            limit: Maximum number of suggestions per category
            
        Returns:
            Dictionary with 'products' and 'services' lists
        """
        suggestions = {
            'products': [],
            'services': []
        }
        
        try:
            # Try to match products mentioned in message
            product_matches = self.fuzzy_matcher.match_product(
                query=message_text,
                tenant=tenant,
                threshold=0.6
            )
            
            # Take top matches
            for product, score in product_matches[:limit]:
                if score > 0.6:  # Only include good matches
                    suggestions['products'].append(product)
            
            # Try to match services mentioned in message
            service_matches = self.fuzzy_matcher.match_service(
                query=message_text,
                tenant=tenant,
                threshold=0.6
            )
            
            # Take top matches
            for service, score in service_matches[:limit]:
                if score > 0.6:  # Only include good matches
                    suggestions['services'].append(service)
            
        except Exception as e:
            logger.error(f"Error getting topic-based suggestions: {e}")
        
        return suggestions
    
    def _filter_available_products(
        self,
        products: List,
        limit: int = 3
    ) -> List:
        """
        Filter products to only include those with available stock.
        
        Args:
            products: List of Product instances
            limit: Maximum number to return
            
        Returns:
            Filtered list of Product instances
        """
        available = []
        
        for product in products:
            # Check if product is in stock
            if product.is_in_stock:
                available.append(product)
                
                if len(available) >= limit:
                    break
        
        return available
    
    def _filter_available_services(
        self,
        services: List,
        tenant,
        limit: int = 3
    ) -> List:
        """
        Filter services to only include those with available appointments.
        
        Args:
            services: List of Service instances
            tenant: Tenant instance
            limit: Maximum number to return
            
        Returns:
            Filtered list of Service instances
        """
        from django.utils import timezone
        from datetime import timedelta
        
        available = []
        
        try:
            # Check next 7 days for availability
            start_date = timezone.now().date()
            end_date = start_date + timedelta(days=7)
            
            for service in services:
                # Check if service has availability windows
                has_availability = service.availability_windows.filter(
                    models.Q(date__gte=start_date, date__lte=end_date) |
                    models.Q(weekday__isnull=False, date__isnull=True)
                ).exists()
                
                if has_availability:
                    available.append(service)
                    
                    if len(available) >= limit:
                        break
            
        except Exception as e:
            logger.error(f"Error filtering available services: {e}")
            # Return all services if filtering fails
            return services[:limit]
        
        return available
    
    def _deduplicate_items(self, items: List) -> List:
        """
        Remove duplicate items from list based on ID.
        
        Args:
            items: List of model instances
            
        Returns:
            Deduplicated list
        """
        seen_ids = set()
        unique_items = []
        
        for item in items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)
        
        return unique_items
    
    def track_interaction(
        self,
        conversation: Conversation,
        message: Message,
        response: AgentResponse,
        detected_intents: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[AgentInteraction]:
        """
        Track agent interaction in database for analytics.
        
        Records every interaction between the AI agent and customers, including:
        - Customer message and detected intents
        - Model used and processing details
        - Agent response and confidence score
        - Handoff decisions and reasons
        - Token usage and estimated costs
        - Message type (text, button, list, media)
        
        Args:
            conversation: Conversation instance
            message: Customer message
            response: AgentResponse generated
            detected_intents: Optional list of detected intents
            
        Returns:
            AgentInteraction instance or None if tracking fails
        """
        try:
            # Determine message type
            message_type = 'text'
            if response.use_rich_message and response.rich_message:
                if response.rich_message.buttons:
                    message_type = 'button'
                elif response.rich_message.list_data:
                    message_type = 'list'
                elif response.rich_message.media_url:
                    message_type = 'media'
            
            # Build token usage dictionary
            token_usage = {
                'prompt_tokens': response.input_tokens,
                'completion_tokens': response.output_tokens,
                'total_tokens': response.total_tokens,
            }
            
            # Create interaction record
            interaction = AgentInteraction.objects.create(
                conversation=conversation,
                customer_message=message.text,
                detected_intents=detected_intents or [],
                model_used=response.model_used,
                context_size=response.context_size_tokens,
                processing_time_ms=response.processing_time_ms,
                agent_response=response.content,
                confidence_score=response.confidence_score,
                handoff_triggered=response.should_handoff,
                handoff_reason=response.handoff_reason,
                message_type=message_type,
                token_usage=token_usage,
                estimated_cost=response.estimated_cost
            )
            
            logger.info(
                f"Tracked agent interaction {interaction.id} for conversation {conversation.id}: "
                f"model={response.model_used}, tokens={response.total_tokens}, "
                f"cost=${response.estimated_cost}, confidence={response.confidence_score:.2f}"
            )
            
            # Track provider usage if we have the necessary metadata
            if '_llm_response' in response.metadata and '_routing_decision' in response.metadata:
                self._track_provider_usage(
                    tenant=conversation.tenant,
                    conversation=conversation,
                    llm_response=response.metadata['_llm_response'],
                    routing_decision=response.metadata['_routing_decision'],
                    provider_used=response.provider,
                    model_used=response.model_used,
                    agent_interaction=interaction
                )
            
            return interaction
            
        except Exception as e:
            logger.error(
                f"Error tracking agent interaction for conversation {conversation.id}: {e}",
                exc_info=True
            )
            return None
    
    def _track_provider_usage(
        self,
        tenant,
        conversation: Conversation,
        llm_response: LLMResponse,
        routing_decision,
        provider_used: str,
        model_used: str,
        agent_interaction: Optional[AgentInteraction] = None
    ):
        """
        Track provider usage for cost and performance monitoring.
        
        Records detailed metrics about LLM provider usage including:
        - Provider and model used
        - Token usage and costs
        - Latency and performance
        - Routing decisions and complexity scores
        - Failover information
        
        Args:
            tenant: Tenant instance
            conversation: Conversation instance
            llm_response: LLMResponse from provider
            routing_decision: RoutingDecision from router
            provider_used: Actual provider used (may differ from routing if failover)
            model_used: Actual model used (may differ from routing if failover)
            agent_interaction: Optional AgentInteraction to link to
        """
        try:
            from apps.bot.models_provider_tracking import ProviderUsage
            
            # Determine if this was a failover
            was_failover = (
                provider_used != routing_decision.provider or
                model_used != routing_decision.model
            )
            
            # Calculate latency (estimate from response metadata)
            latency_ms = llm_response.metadata.get('latency_ms', 0)
            if not latency_ms:
                # Estimate based on tokens (rough: 50 tokens/second)
                latency_ms = int((llm_response.total_tokens / 50) * 1000)
            
            # Create usage record
            usage = ProviderUsage.objects.create(
                tenant=tenant,
                conversation=conversation,
                agent_interaction=agent_interaction,
                provider=provider_used,
                model=model_used,
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                total_tokens=llm_response.total_tokens,
                estimated_cost=llm_response.estimated_cost,
                latency_ms=latency_ms,
                success=True,
                finish_reason=llm_response.finish_reason,
                was_failover=was_failover,
                routing_reason=routing_decision.reason,
                complexity_score=routing_decision.complexity_score,
                metadata={
                    'routing_provider': routing_decision.provider,
                    'routing_model': routing_decision.model,
                    'llm_metadata': llm_response.metadata
                }
            )
            
            logger.debug(
                f"Tracked provider usage: {provider_used}/{model_used}, "
                f"tokens={llm_response.total_tokens}, cost=${llm_response.estimated_cost}, "
                f"failover={was_failover}"
            )
            
        except Exception as e:
            logger.error(
                f"Error tracking provider usage: {e}",
                exc_info=True
            )
    
    def _should_use_rag(self, agent_config: AgentConfiguration) -> bool:
        """
        Determine if RAG should be used based on agent configuration.
        
        Args:
            agent_config: AgentConfiguration for this tenant
            
        Returns:
            True if any RAG source is enabled
        """
        return (
            agent_config.enable_document_retrieval or
            agent_config.enable_database_retrieval or
            agent_config.enable_internet_enrichment
        )
    
    def retrieve_rag_context(
        self,
        query: str,
        conversation: Conversation,
        context: AgentContext,
        agent_config: AgentConfiguration,
        tenant
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve context from RAG sources (documents, database, internet).
        
        Orchestrates retrieval from multiple sources based on agent configuration,
        synthesizes the results, and returns structured context for the LLM.
        
        Args:
            query: Customer query text
            conversation: Conversation instance
            context: AgentContext with conversation data
            agent_config: AgentConfiguration for this tenant
            tenant: Tenant instance
            
        Returns:
            Dictionary with synthesized RAG context or None if retrieval fails
        """
        try:
            # Initialize RAG services if not already done
            if not self.rag_retriever:
                self.rag_retriever = RAGRetrieverService.create_for_tenant(tenant)
            
            if not self.context_synthesizer:
                self.context_synthesizer = ContextSynthesizer()
            
            if not self.attribution_handler:
                self.attribution_handler = AttributionHandler(
                    enabled=agent_config.enable_source_attribution
                )
            
            # Retrieve from all enabled sources
            logger.info(f"Retrieving RAG context for query: {query[:100]}...")
            
            retrieval_results = self.rag_retriever.retrieve(
                query=query,
                conversation_context={
                    'conversation_id': str(conversation.id),
                    'customer_id': str(conversation.customer.id) if conversation.customer else None,
                    'conversation_history': context.conversation_history[:5],  # Last 5 messages
                    'current_topic': context.metadata.get('current_topic'),
                },
                max_document_results=agent_config.max_document_results,
                max_database_results=agent_config.max_database_results,
                max_internet_results=agent_config.max_internet_results,
                enable_documents=agent_config.enable_document_retrieval,
                enable_database=agent_config.enable_database_retrieval,
                enable_internet=agent_config.enable_internet_enrichment
            )
            
            # Synthesize results into coherent context
            synthesized_context = self.context_synthesizer.synthesize(
                retrieval_results=retrieval_results,
                query=query,
                conversation_context=context
            )
            
            # Return structured context
            return {
                'document_results': retrieval_results.get('document_results', []),
                'database_results': retrieval_results.get('database_results', []),
                'internet_results': retrieval_results.get('internet_results', []),
                'synthesized_text': synthesized_context.get('synthesized_text', ''),
                'sources': synthesized_context.get('sources', []),
                'confidence': synthesized_context.get('confidence', 0.0),
                'retrieval_time_ms': retrieval_results.get('retrieval_time_ms', 0)
            }
            
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {e}", exc_info=True)
            return None
    
    def _build_rag_context_section(self, rag_context: Dict[str, Any]) -> str:
        """
        Build RAG context section for prompt.
        
        Formats retrieved information from documents, database, and internet
        into a structured section for the LLM prompt.
        
        Args:
            rag_context: Dictionary with RAG retrieval results
            
        Returns:
            Formatted RAG context section
        """
        sections = ["## Retrieved Information"]
        
        # Add synthesized context if available
        if rag_context.get('synthesized_text'):
            sections.append("\n### Relevant Context:")
            sections.append(rag_context['synthesized_text'])
        
        # Add document results
        document_results = rag_context.get('document_results', [])
        if document_results:
            sections.append("\n### From Business Documents:")
            for i, result in enumerate(document_results[:3], 1):  # Limit to top 3
                sections.append(f"\n{i}. {result.get('content', '')}")
                if result.get('source'):
                    sections.append(f"   (Source: {result['source']})")
        
        # Add database results
        database_results = rag_context.get('database_results', [])
        if database_results:
            sections.append("\n### From Our Catalog:")
            for i, result in enumerate(database_results[:5], 1):  # Limit to top 5
                sections.append(f"\n{i}. {result.get('content', '')}")
        
        # Add internet results
        internet_results = rag_context.get('internet_results', [])
        if internet_results:
            sections.append("\n### Additional Information:")
            for i, result in enumerate(internet_results[:2], 1):  # Limit to top 2
                sections.append(f"\n{i}. {result.get('content', '')}")
                if result.get('source'):
                    sections.append(f"   (Source: {result['source']})")
        
        sections.append("\n**Instructions:** Use the above retrieved information to provide accurate, helpful responses. Prioritize information from business documents and our catalog over external sources.")
        
        return "\n".join(sections)
    
    def add_attribution_to_response(
        self,
        response: AgentResponse,
        rag_context: Optional[Dict[str, Any]],
        agent_config: AgentConfiguration
    ) -> AgentResponse:
        """
        Add source attribution to response if enabled.
        
        Uses AttributionHandler to add citations to the response content
        based on the sources used in RAG retrieval.
        
        Args:
            response: AgentResponse to add attribution to
            rag_context: RAG context with sources
            agent_config: AgentConfiguration for this tenant
            
        Returns:
            AgentResponse with attribution added
        """
        # Skip if attribution is disabled or no RAG context
        if not agent_config.enable_source_attribution or not rag_context:
            return response
        
        try:
            # Initialize attribution handler if needed
            if not self.attribution_handler:
                self.attribution_handler = AttributionHandler(
                    enabled=agent_config.enable_source_attribution
                )
            
            # Add attribution to response
            attributed_content = self.attribution_handler.add_attribution(
                response_text=response.content,
                sources=rag_context.get('sources', []),
                citation_style='inline'  # or 'endnote' based on preference
            )
            
            # Update response content
            response.content = attributed_content
            
            # Track attribution in metadata
            response.metadata['attribution_added'] = True
            response.metadata['source_count'] = len(rag_context.get('sources', []))
            
            logger.debug(f"Added attribution with {len(rag_context.get('sources', []))} sources")
            
        except Exception as e:
            logger.error(f"Error adding attribution: {e}", exc_info=True)
        
        return response
    
    def _create_fallback_response(
        self,
        error: str,
        processing_time_ms: int
    ) -> AgentResponse:
        """
        Create fallback response when processing fails.
        
        Args:
            error: Error message
            processing_time_ms: Processing time in milliseconds
            
        Returns:
            AgentResponse with fallback content
        """
        return AgentResponse(
            content="I apologize, but I'm having trouble processing your request right now. "
                   "Let me connect you with a human agent who can help you better.",
            model_used='fallback',
            provider='system',
            confidence_score=0.0,
            processing_time_ms=processing_time_ms,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal('0'),
            should_handoff=True,
            handoff_reason='processing_error',
            metadata={'error': error}
        )


def create_ai_agent_service(
    context_builder: Optional[ContextBuilderService] = None,
    config_service: Optional[AgentConfigurationService] = None,
    fuzzy_matcher: Optional[FuzzyMatcherService] = None,
    rich_message_builder: Optional[RichMessageBuilder] = None
) -> AIAgentService:
    """
    Factory function to create AIAgentService instance.
    
    Args:
        context_builder: Optional ContextBuilderService instance
        config_service: Optional AgentConfigurationService instance
        fuzzy_matcher: Optional FuzzyMatcherService instance
        rich_message_builder: Optional RichMessageBuilder instance
        
    Returns:
        AIAgentService instance
    """
    return AIAgentService(
        context_builder=context_builder,
        config_service=config_service,
        fuzzy_matcher=fuzzy_matcher,
        rich_message_builder=rich_message_builder
    )
