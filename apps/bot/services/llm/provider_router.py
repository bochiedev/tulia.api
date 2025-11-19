"""
Smart Provider Router for intelligent LLM model selection.

Routes queries to the most appropriate provider and model based on:
- Query complexity
- Context size
- Cost optimization
- Performance requirements
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    provider: str
    model: str
    reason: str
    estimated_cost_per_1k_tokens: float
    complexity_score: float


class ProviderRouter:
    """
    Intelligent router for selecting optimal LLM provider and model.
    
    Routing Strategy:
    - Simple queries (complexity < 0.3) -> Gemini Flash (cheapest)
    - Large context (>100K tokens) -> Gemini Pro (1M context window)
    - Complex reasoning (complexity > 0.7) -> OpenAI o1-preview
    - Default -> OpenAI GPT-4o (balanced performance)
    """
    
    # Complexity thresholds
    SIMPLE_THRESHOLD = 0.3
    COMPLEX_THRESHOLD = 0.7
    LARGE_CONTEXT_THRESHOLD = 100000  # tokens
    
    # Default routing configuration
    DEFAULT_ROUTING = {
        'simple_queries': {
            'provider': 'gemini',
            'model': 'gemini-1.5-flash',
            'reason': 'Simple query - using cost-effective Gemini Flash'
        },
        'large_context': {
            'provider': 'gemini',
            'model': 'gemini-1.5-pro',
            'reason': 'Large context - using Gemini Pro with 1M token window'
        },
        'complex_reasoning': {
            'provider': 'openai',
            'model': 'o1-preview',
            'reason': 'Complex reasoning - using OpenAI o1-preview'
        },
        'default': {
            'provider': 'openai',
            'model': 'gpt-4o',
            'reason': 'Balanced performance - using GPT-4o'
        }
    }
    
    def __init__(self, routing_config: Optional[Dict] = None):
        """
        Initialize provider router.
        
        Args:
            routing_config: Optional custom routing configuration
        """
        self.routing_config = routing_config or self.DEFAULT_ROUTING
    
    def route(
        self,
        messages: List[Dict[str, str]],
        context_size: Optional[int] = None,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None
    ) -> RoutingDecision:
        """
        Route query to optimal provider and model.
        
        Args:
            messages: List of message dicts
            context_size: Optional context size in tokens
            preferred_provider: Optional provider override
            preferred_model: Optional model override
            
        Returns:
            RoutingDecision with provider, model, and reasoning
        """
        # If specific model requested, use it
        if preferred_provider and preferred_model:
            logger.info(
                f"Using preferred provider/model: {preferred_provider}/{preferred_model}"
            )
            return RoutingDecision(
                provider=preferred_provider,
                model=preferred_model,
                reason='User-specified provider and model',
                estimated_cost_per_1k_tokens=0.0,  # Will be calculated by provider
                complexity_score=0.0
            )
        
        # Calculate complexity score
        complexity_score = self.calculate_complexity(messages)
        
        # Estimate context size if not provided
        if context_size is None:
            context_size = self._estimate_context_size(messages)
        
        logger.info(
            f"Routing decision: complexity={complexity_score:.2f}, "
            f"context_size={context_size}"
        )
        
        # Route based on context size first (highest priority)
        if context_size > self.LARGE_CONTEXT_THRESHOLD:
            config = self.routing_config['large_context']
            logger.info(f"Large context detected: {config['reason']}")
            return RoutingDecision(
                provider=config['provider'],
                model=config['model'],
                reason=config['reason'],
                estimated_cost_per_1k_tokens=self._get_cost_estimate(
                    config['provider'], config['model']
                ),
                complexity_score=complexity_score
            )
        
        # Route based on complexity
        if complexity_score < self.SIMPLE_THRESHOLD:
            config = self.routing_config['simple_queries']
            logger.info(f"Simple query detected: {config['reason']}")
            return RoutingDecision(
                provider=config['provider'],
                model=config['model'],
                reason=config['reason'],
                estimated_cost_per_1k_tokens=self._get_cost_estimate(
                    config['provider'], config['model']
                ),
                complexity_score=complexity_score
            )
        
        if complexity_score > self.COMPLEX_THRESHOLD:
            config = self.routing_config['complex_reasoning']
            logger.info(f"Complex reasoning detected: {config['reason']}")
            return RoutingDecision(
                provider=config['provider'],
                model=config['model'],
                reason=config['reason'],
                estimated_cost_per_1k_tokens=self._get_cost_estimate(
                    config['provider'], config['model']
                ),
                complexity_score=complexity_score
            )
        
        # Default routing
        config = self.routing_config['default']
        logger.info(f"Using default routing: {config['reason']}")
        return RoutingDecision(
            provider=config['provider'],
            model=config['model'],
            reason=config['reason'],
            estimated_cost_per_1k_tokens=self._get_cost_estimate(
                config['provider'], config['model']
            ),
            complexity_score=complexity_score
        )
    
    def calculate_complexity(self, messages: List[Dict[str, str]]) -> float:
        """
        Calculate complexity score for query (0.0 to 1.0).
        
        Factors:
        - Number of messages (conversation length)
        - Message length
        - Presence of complex keywords
        - Question complexity
        
        Args:
            messages: List of message dicts
            
        Returns:
            Complexity score between 0.0 and 1.0
        """
        if not messages:
            return 0.0
        
        score = 0.0
        
        # Factor 1: Conversation length (0.0 to 0.2)
        conversation_length = len(messages)
        if conversation_length > 10:
            score += 0.2
        elif conversation_length > 5:
            score += 0.1
        else:
            score += conversation_length * 0.02
        
        # Factor 2: Message length (0.0 to 0.2)
        total_length = sum(len(msg.get('content', '')) for msg in messages)
        if total_length > 5000:
            score += 0.2
        elif total_length > 2000:
            score += 0.15
        elif total_length > 1000:
            score += 0.1
        else:
            score += total_length / 10000
        
        # Factor 3: Complex keywords (0.0 to 0.3)
        complex_keywords = [
            'analyze', 'compare', 'evaluate', 'explain why', 'reasoning',
            'calculate', 'solve', 'optimize', 'recommend', 'strategy',
            'complex', 'detailed', 'comprehensive', 'in-depth', 'technical',
            'algorithm', 'logic', 'proof', 'derive', 'synthesize'
        ]
        
        last_user_message = None
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                last_user_message = msg.get('content', '').lower()
                break
        
        if last_user_message:
            keyword_count = sum(
                1 for keyword in complex_keywords
                if keyword in last_user_message
            )
            score += min(keyword_count * 0.1, 0.3)
        
        # Factor 4: Question complexity (0.0 to 0.3)
        if last_user_message:
            # Multiple questions
            question_marks = last_user_message.count('?')
            if question_marks > 2:
                score += 0.2
            elif question_marks > 1:
                score += 0.1
            
            # Long questions
            if len(last_user_message) > 500:
                score += 0.1
            elif len(last_user_message) > 200:
                score += 0.05
        
        # Normalize to 0.0-1.0 range
        return min(score, 1.0)
    
    def _estimate_context_size(self, messages: List[Dict[str, str]]) -> int:
        """
        Estimate context size in tokens.
        
        Args:
            messages: List of message dicts
            
        Returns:
            Estimated token count
        """
        # Rough estimate: 4 characters per token
        total_chars = sum(len(msg.get('content', '')) for msg in messages)
        return total_chars // 4
    
    def _get_cost_estimate(self, provider: str, model: str) -> float:
        """
        Get cost estimate per 1K tokens for provider/model.
        
        Args:
            provider: Provider name
            model: Model name
            
        Returns:
            Estimated cost per 1K tokens (average of input/output)
        """
        # Cost estimates (average of input and output costs)
        cost_map = {
            'openai': {
                'gpt-4o': 0.00625,  # ($0.0025 + $0.01) / 2
                'gpt-4o-mini': 0.000375,  # ($0.00015 + $0.0006) / 2
                'o1-preview': 0.0375,  # ($0.015 + $0.06) / 2
                'o1-mini': 0.0075,  # ($0.003 + $0.012) / 2
            },
            'gemini': {
                'gemini-1.5-pro': 0.003125,  # ($0.00125 + $0.005) / 2
                'gemini-1.5-flash': 0.0001875,  # ($0.000075 + $0.0003) / 2
                'gemini-1.5-pro-latest': 0.003125,
                'gemini-1.5-flash-latest': 0.0001875,
            },
            'together': {
                # Add Together AI costs if needed
            }
        }
        
        return cost_map.get(provider, {}).get(model, 0.0)
    
    @classmethod
    def from_agent_config(cls, agent_config) -> 'ProviderRouter':
        """
        Create router from agent configuration.
        
        Args:
            agent_config: AgentConfiguration instance
            
        Returns:
            Configured ProviderRouter
        """
        # Extract routing config from agent settings if available
        routing_config = None
        
        if hasattr(agent_config, 'routing_config') and agent_config.routing_config:
            routing_config = agent_config.routing_config
        
        return cls(routing_config=routing_config)
