"""
Metrics collection for AI agent performance monitoring.

Tracks and aggregates metrics including:
- Response time percentiles (p50, p95, p99)
- Token usage per conversation
- Cost per conversation
- Handoff rate and reasons
- Knowledge base hit rate
- Model usage distribution
"""
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
import statistics


@dataclass
class ResponseTimeMetrics:
    """Container for response time metrics."""
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    mean: float = 0.0
    min: float = 0.0
    max: float = 0.0
    count: int = 0


@dataclass
class TokenUsageMetrics:
    """Container for token usage metrics."""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    avg_tokens_per_conversation: float = 0.0
    conversation_count: int = 0


@dataclass
class CostMetrics:
    """Container for cost metrics."""
    total_cost: Decimal = Decimal('0.0')
    avg_cost_per_conversation: Decimal = Decimal('0.0')
    avg_cost_per_token: Decimal = Decimal('0.0')
    conversation_count: int = 0
    by_model: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class HandoffMetrics:
    """Container for handoff metrics."""
    total_handoffs: int = 0
    handoff_rate: float = 0.0
    total_interactions: int = 0
    by_reason: Dict[str, int] = field(default_factory=dict)


@dataclass
class KnowledgeBaseMetrics:
    """Container for knowledge base metrics."""
    total_searches: int = 0
    searches_with_results: int = 0
    hit_rate: float = 0.0
    avg_results_per_search: float = 0.0
    avg_similarity_score: float = 0.0


class MetricsCollector:
    """
    Collects and aggregates metrics for AI agent performance monitoring.
    
    Maintains in-memory metrics with periodic cache updates for
    distributed access. Metrics are aggregated per tenant and globally.
    """
    
    # Cache TTL in seconds
    CACHE_TTL = 300  # 5 minutes
    
    # Maximum samples to keep in memory for percentile calculations
    MAX_SAMPLES = 1000
    
    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize metrics collector.
        
        Args:
            tenant_id: Optional tenant ID for tenant-specific metrics
        """
        self.tenant_id = tenant_id
        self.cache_key_prefix = f"agent_metrics:{tenant_id or 'global'}"
        
        # In-memory metrics storage
        self.response_times = deque(maxlen=self.MAX_SAMPLES)
        self.token_usage_data = []
        self.cost_data = []
        self.handoff_data = []
        self.knowledge_search_data = []
        
        # Counters
        self.interaction_count = 0
        self.handoff_count = 0
        self.knowledge_search_count = 0
        
        # Model usage tracking
        self.model_usage = defaultdict(int)
        self.model_costs = defaultdict(Decimal)
        
        # Handoff reasons tracking
        self.handoff_reasons = defaultdict(int)
    
    def record_interaction(
        self,
        response_time_ms: int,
        token_usage: Dict[str, int],
        estimated_cost: Decimal,
        model_used: str,
        handoff_triggered: bool = False,
        handoff_reason: str = '',
        confidence_score: float = 1.0,
        **kwargs
    ):
        """
        Record a complete agent interaction.
        
        Args:
            response_time_ms: Response time in milliseconds
            token_usage: Dict with prompt_tokens, completion_tokens, total_tokens
            estimated_cost: Estimated cost in USD
            model_used: Model identifier
            handoff_triggered: Whether handoff was triggered
            handoff_reason: Reason for handoff if triggered
            confidence_score: Response confidence score
            **kwargs: Additional metadata
        """
        # Record response time
        self.response_times.append(response_time_ms)
        
        # Record token usage
        self.token_usage_data.append(token_usage)
        
        # Record cost
        self.cost_data.append({
            'cost': estimated_cost,
            'model': model_used,
            'tokens': token_usage.get('total_tokens', 0)
        })
        
        # Track model usage
        self.model_usage[model_used] += 1
        self.model_costs[model_used] += estimated_cost
        
        # Record handoff
        if handoff_triggered:
            self.handoff_count += 1
            self.handoff_data.append({
                'reason': handoff_reason,
                'confidence_score': confidence_score
            })
            self.handoff_reasons[handoff_reason] += 1
        
        # Increment interaction count
        self.interaction_count += 1
        
        # Periodically update cache
        if self.interaction_count % 10 == 0:
            self._update_cache()
    
    def record_knowledge_search(
        self,
        results_count: int,
        top_similarity_score: Optional[float] = None,
        search_time_ms: int = 0,
        **kwargs
    ):
        """
        Record a knowledge base search operation.
        
        Args:
            results_count: Number of results returned
            top_similarity_score: Highest similarity score
            search_time_ms: Search time in milliseconds
            **kwargs: Additional metadata
        """
        self.knowledge_search_count += 1
        self.knowledge_search_data.append({
            'results_count': results_count,
            'top_similarity_score': top_similarity_score,
            'search_time_ms': search_time_ms
        })
        
        # Update cache periodically
        if self.knowledge_search_count % 10 == 0:
            self._update_cache()
    
    def get_response_time_metrics(self) -> ResponseTimeMetrics:
        """
        Calculate response time metrics including percentiles.
        
        Returns:
            ResponseTimeMetrics with p50, p95, p99, mean, min, max
        """
        if not self.response_times:
            return ResponseTimeMetrics()
        
        sorted_times = sorted(self.response_times)
        count = len(sorted_times)
        
        # Calculate percentiles
        p50_idx = int(count * 0.50)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        
        return ResponseTimeMetrics(
            p50=sorted_times[p50_idx] if p50_idx < count else 0.0,
            p95=sorted_times[p95_idx] if p95_idx < count else 0.0,
            p99=sorted_times[p99_idx] if p99_idx < count else 0.0,
            mean=statistics.mean(sorted_times),
            min=min(sorted_times),
            max=max(sorted_times),
            count=count
        )
    
    def get_token_usage_metrics(self) -> TokenUsageMetrics:
        """
        Calculate token usage metrics.
        
        Returns:
            TokenUsageMetrics with totals and averages
        """
        if not self.token_usage_data:
            return TokenUsageMetrics()
        
        total_tokens = sum(d.get('total_tokens', 0) for d in self.token_usage_data)
        prompt_tokens = sum(d.get('prompt_tokens', 0) for d in self.token_usage_data)
        completion_tokens = sum(d.get('completion_tokens', 0) for d in self.token_usage_data)
        count = len(self.token_usage_data)
        
        return TokenUsageMetrics(
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            avg_tokens_per_conversation=total_tokens / count if count > 0 else 0.0,
            conversation_count=count
        )
    
    def get_cost_metrics(self) -> CostMetrics:
        """
        Calculate cost metrics.
        
        Returns:
            CostMetrics with totals, averages, and breakdown by model
        """
        if not self.cost_data:
            return CostMetrics()
        
        total_cost = sum(d['cost'] for d in self.cost_data)
        total_tokens = sum(d['tokens'] for d in self.cost_data)
        count = len(self.cost_data)
        
        # Calculate cost by model
        by_model = {}
        for model, cost in self.model_costs.items():
            by_model[model] = cost
        
        return CostMetrics(
            total_cost=total_cost,
            avg_cost_per_conversation=total_cost / count if count > 0 else Decimal('0.0'),
            avg_cost_per_token=total_cost / total_tokens if total_tokens > 0 else Decimal('0.0'),
            conversation_count=count,
            by_model=by_model
        )
    
    def get_handoff_metrics(self) -> HandoffMetrics:
        """
        Calculate handoff metrics.
        
        Returns:
            HandoffMetrics with rate and breakdown by reason
        """
        return HandoffMetrics(
            total_handoffs=self.handoff_count,
            handoff_rate=self.handoff_count / self.interaction_count if self.interaction_count > 0 else 0.0,
            total_interactions=self.interaction_count,
            by_reason=dict(self.handoff_reasons)
        )
    
    def get_knowledge_base_metrics(self) -> KnowledgeBaseMetrics:
        """
        Calculate knowledge base metrics.
        
        Returns:
            KnowledgeBaseMetrics with hit rate and averages
        """
        if not self.knowledge_search_data:
            return KnowledgeBaseMetrics()
        
        searches_with_results = sum(
            1 for d in self.knowledge_search_data
            if d['results_count'] > 0
        )
        
        total_results = sum(d['results_count'] for d in self.knowledge_search_data)
        
        # Calculate average similarity score (only for searches with results)
        similarity_scores = [
            d['top_similarity_score']
            for d in self.knowledge_search_data
            if d['top_similarity_score'] is not None
        ]
        avg_similarity = statistics.mean(similarity_scores) if similarity_scores else 0.0
        
        count = len(self.knowledge_search_data)
        
        return KnowledgeBaseMetrics(
            total_searches=count,
            searches_with_results=searches_with_results,
            hit_rate=searches_with_results / count if count > 0 else 0.0,
            avg_results_per_search=total_results / count if count > 0 else 0.0,
            avg_similarity_score=avg_similarity
        )
    
    def get_model_usage_distribution(self) -> Dict[str, Dict[str, Any]]:
        """
        Get model usage distribution with counts and costs.
        
        Returns:
            Dict mapping model names to usage stats
        """
        distribution = {}
        
        for model, count in self.model_usage.items():
            distribution[model] = {
                'count': count,
                'percentage': (count / self.interaction_count * 100) if self.interaction_count > 0 else 0.0,
                'total_cost': float(self.model_costs[model]),
                'avg_cost': float(self.model_costs[model] / count) if count > 0 else 0.0
            }
        
        return distribution
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics as a dictionary.
        
        Returns:
            Dict with all metric categories
        """
        response_time = self.get_response_time_metrics()
        token_usage = self.get_token_usage_metrics()
        cost = self.get_cost_metrics()
        handoff = self.get_handoff_metrics()
        knowledge = self.get_knowledge_base_metrics()
        model_usage = self.get_model_usage_distribution()
        
        return {
            'response_time': {
                'p50_ms': response_time.p50,
                'p95_ms': response_time.p95,
                'p99_ms': response_time.p99,
                'mean_ms': response_time.mean,
                'min_ms': response_time.min,
                'max_ms': response_time.max,
                'sample_count': response_time.count
            },
            'token_usage': {
                'total_tokens': token_usage.total_tokens,
                'prompt_tokens': token_usage.prompt_tokens,
                'completion_tokens': token_usage.completion_tokens,
                'avg_per_conversation': token_usage.avg_tokens_per_conversation,
                'conversation_count': token_usage.conversation_count
            },
            'cost': {
                'total_usd': float(cost.total_cost),
                'avg_per_conversation_usd': float(cost.avg_cost_per_conversation),
                'avg_per_token_usd': float(cost.avg_cost_per_token),
                'conversation_count': cost.conversation_count,
                'by_model': {k: float(v) for k, v in cost.by_model.items()}
            },
            'handoff': {
                'total_handoffs': handoff.total_handoffs,
                'handoff_rate': handoff.handoff_rate,
                'total_interactions': handoff.total_interactions,
                'by_reason': handoff.by_reason
            },
            'knowledge_base': {
                'total_searches': knowledge.total_searches,
                'searches_with_results': knowledge.searches_with_results,
                'hit_rate': knowledge.hit_rate,
                'avg_results_per_search': knowledge.avg_results_per_search,
                'avg_similarity_score': knowledge.avg_similarity_score
            },
            'model_usage': model_usage,
            'timestamp': timezone.now().isoformat()
        }
    
    def _update_cache(self):
        """Update cached metrics for distributed access."""
        try:
            metrics = self.get_all_metrics()
            cache_key = f"{self.cache_key_prefix}:current"
            cache.set(cache_key, metrics, self.CACHE_TTL)
        except Exception as e:
            # Log error but don't fail
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to update metrics cache: {e}")
    
    def reset(self):
        """Reset all metrics."""
        self.response_times.clear()
        self.token_usage_data.clear()
        self.cost_data.clear()
        self.handoff_data.clear()
        self.knowledge_search_data.clear()
        self.interaction_count = 0
        self.handoff_count = 0
        self.knowledge_search_count = 0
        self.model_usage.clear()
        self.model_costs.clear()
        self.handoff_reasons.clear()
    
    @classmethod
    def get_cached_metrics(cls, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get cached metrics for a tenant or globally.
        
        Args:
            tenant_id: Optional tenant ID
            
        Returns:
            Cached metrics dict or None if not available
        """
        cache_key_prefix = f"agent_metrics:{tenant_id or 'global'}"
        cache_key = f"{cache_key_prefix}:current"
        return cache.get(cache_key)


# Global metrics collector instances
_global_collectors: Dict[str, MetricsCollector] = {}


def get_metrics_collector(tenant_id: Optional[str] = None) -> MetricsCollector:
    """
    Get metrics collector instance for tenant or global.
    
    Args:
        tenant_id: Optional tenant ID for tenant-specific metrics
        
    Returns:
        MetricsCollector instance
    """
    key = tenant_id or 'global'
    
    if key not in _global_collectors:
        _global_collectors[key] = MetricsCollector(tenant_id=tenant_id)
    
    return _global_collectors[key]
