"""
Provider Failover Manager for handling LLM provider failures.

Implements automatic failover to backup providers when primary provider fails.
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ProviderFailoverManager:
    """
    Manages automatic failover between LLM providers.
    
    Features:
    - Automatic failover on provider errors
    - Provider health tracking
    - Configurable fallback order
    - Timeout limits per provider
    """
    
    # Default timeout per provider (seconds)
    DEFAULT_TIMEOUT = 30
    
    # Provider health tracking window (minutes)
    HEALTH_WINDOW = 60
    
    # Failure threshold for marking provider unhealthy
    FAILURE_THRESHOLD = 0.5  # 50% failure rate
    
    def __init__(
        self,
        fallback_order: Optional[List[Tuple[str, str]]] = None,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize failover manager.
        
        Args:
            fallback_order: List of (provider, model) tuples in fallback order
            timeout: Timeout in seconds for each provider attempt
        """
        self.fallback_order = fallback_order or self._get_default_fallback_order()
        self.timeout = timeout
        
        # Track provider health
        self.provider_stats = {}  # provider -> {'success': int, 'failure': int, 'last_check': datetime}
    
    def _get_default_fallback_order(self) -> List[Tuple[str, str]]:
        """
        Get default fallback order with Together AI as final fallback.
        
        Returns:
            List of (provider, model) tuples
        """
        return [
            ('openai', 'gpt-4o'),
            ('gemini', 'gemini-1.5-pro'),
            ('together', 'Qwen/Qwen2.5-72B-Instruct-Turbo'),  # Excellent multilingual support
            ('openai', 'gpt-4o-mini'),
            ('gemini', 'gemini-1.5-flash'),
            ('together', 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo'),  # Strong general model
            ('together', 'Qwen/Qwen2.5-7B-Instruct-Turbo'),  # Cost-effective fallback
        ]
    
    def execute_with_failover(
        self,
        provider_factory,
        tenant,
        messages: List[Dict[str, str]],
        primary_provider: str,
        primary_model: str,
        **kwargs
    ) -> Tuple[any, str, str]:
        """
        Execute LLM call with automatic failover.
        
        Args:
            provider_factory: LLMProviderFactory instance
            tenant: Tenant instance
            messages: List of message dicts
            primary_provider: Primary provider name
            primary_model: Primary model name
            **kwargs: Additional parameters for generate()
            
        Returns:
            Tuple of (LLMResponse, provider_used, model_used)
            
        Raises:
            Exception: If all providers fail
        """
        # Build attempt list: primary first, then fallbacks
        attempts = [(primary_provider, primary_model)]
        
        # Add fallbacks (skip if same as primary)
        for provider, model in self.fallback_order:
            if (provider, model) != (primary_provider, primary_model):
                attempts.append((provider, model))
        
        last_exception = None
        
        for attempt_num, (provider_name, model_name) in enumerate(attempts, 1):
            try:
                logger.info(
                    f"Attempt {attempt_num}/{len(attempts)}: "
                    f"provider={provider_name}, model={model_name}"
                )
                
                # Check if provider is healthy
                if not self._is_provider_healthy(provider_name):
                    logger.warning(
                        f"Provider {provider_name} marked unhealthy, skipping"
                    )
                    continue
                
                # Create provider instance
                provider = provider_factory.create_from_tenant_settings(
                    tenant,
                    provider_name=provider_name
                )
                
                # Set timeout
                if hasattr(provider, 'timeout'):
                    provider.timeout = self.timeout
                
                # Make API call
                response = provider.generate(
                    messages=messages,
                    model=model_name,
                    **kwargs
                )
                
                # Record success
                self._record_success(provider_name)
                
                logger.info(
                    f"Successfully generated response using "
                    f"{provider_name}/{model_name}"
                )
                
                # Log failover event if not primary
                if attempt_num > 1:
                    logger.warning(
                        f"Failover successful: used {provider_name}/{model_name} "
                        f"after {attempt_num - 1} failed attempts"
                    )
                
                return response, provider_name, model_name
                
            except Exception as e:
                last_exception = e
                
                # Record failure
                self._record_failure(provider_name)
                
                logger.error(
                    f"Provider {provider_name}/{model_name} failed: {e}"
                )
                
                # Continue to next provider
                if attempt_num < len(attempts):
                    logger.info(f"Trying next provider in fallback order...")
                    continue
        
        # All providers failed
        logger.error(
            f"All providers failed after {len(attempts)} attempts. "
            f"Last error: {last_exception}"
        )
        
        raise Exception(
            f"All LLM providers failed. Last error: {last_exception}"
        )
    
    def _is_provider_healthy(self, provider: str) -> bool:
        """
        Check if provider is healthy based on recent stats.
        
        Args:
            provider: Provider name
            
        Returns:
            True if provider is healthy, False otherwise
        """
        if provider not in self.provider_stats:
            # No stats yet, assume healthy
            return True
        
        stats = self.provider_stats[provider]
        
        # Check if stats are recent (within health window)
        if 'last_check' in stats:
            age = datetime.now() - stats['last_check']
            if age > timedelta(minutes=self.HEALTH_WINDOW):
                # Stats too old, reset and assume healthy
                self.provider_stats[provider] = {
                    'success': 0,
                    'failure': 0,
                    'last_check': datetime.now()
                }
                return True
        
        # Calculate failure rate
        total = stats.get('success', 0) + stats.get('failure', 0)
        if total == 0:
            return True
        
        failure_rate = stats.get('failure', 0) / total
        
        is_healthy = failure_rate < self.FAILURE_THRESHOLD
        
        if not is_healthy:
            logger.warning(
                f"Provider {provider} marked unhealthy: "
                f"failure_rate={failure_rate:.2%} "
                f"(threshold={self.FAILURE_THRESHOLD:.2%})"
            )
        
        return is_healthy
    
    def _record_success(self, provider: str):
        """
        Record successful provider call.
        
        Args:
            provider: Provider name
        """
        if provider not in self.provider_stats:
            self.provider_stats[provider] = {
                'success': 0,
                'failure': 0,
                'last_check': datetime.now()
            }
        
        self.provider_stats[provider]['success'] += 1
        self.provider_stats[provider]['last_check'] = datetime.now()
    
    def _record_failure(self, provider: str):
        """
        Record failed provider call.
        
        Args:
            provider: Provider name
        """
        if provider not in self.provider_stats:
            self.provider_stats[provider] = {
                'success': 0,
                'failure': 0,
                'last_check': datetime.now()
            }
        
        self.provider_stats[provider]['failure'] += 1
        self.provider_stats[provider]['last_check'] = datetime.now()
    
    def get_provider_health(self) -> Dict[str, Dict]:
        """
        Get health stats for all providers.
        
        Returns:
            Dict mapping provider name to health stats
        """
        health = {}
        
        for provider, stats in self.provider_stats.items():
            total = stats.get('success', 0) + stats.get('failure', 0)
            if total > 0:
                success_rate = stats.get('success', 0) / total
                failure_rate = stats.get('failure', 0) / total
            else:
                success_rate = 0.0
                failure_rate = 0.0
            
            health[provider] = {
                'success_count': stats.get('success', 0),
                'failure_count': stats.get('failure', 0),
                'total_calls': total,
                'success_rate': success_rate,
                'failure_rate': failure_rate,
                'is_healthy': self._is_provider_healthy(provider),
                'last_check': stats.get('last_check')
            }
        
        return health
    
    def reset_provider_stats(self, provider: Optional[str] = None):
        """
        Reset provider statistics.
        
        Args:
            provider: Optional provider name to reset, or None to reset all
        """
        if provider:
            if provider in self.provider_stats:
                self.provider_stats[provider] = {
                    'success': 0,
                    'failure': 0,
                    'last_check': datetime.now()
                }
                logger.info(f"Reset stats for provider: {provider}")
        else:
            self.provider_stats = {}
            logger.info("Reset stats for all providers")
