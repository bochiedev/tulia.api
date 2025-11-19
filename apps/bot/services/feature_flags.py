"""
Feature flag service for gradual rollout of new features.

Enables safe, controlled rollout of new features to subsets of tenants.
"""

import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """
    Service for managing feature flags and gradual rollouts.
    
    Features:
    - Per-tenant feature enablement
    - Percentage-based rollouts
    - A/B testing support
    - Feature flag caching
    """
    
    # Cache TTL for feature flags (5 minutes)
    CACHE_TTL = 300
    
    # Default feature flags
    DEFAULT_FLAGS = {
        'multi_provider_routing': {
            'enabled': True,
            'rollout_percentage': 100,
            'description': 'Smart multi-provider LLM routing'
        },
        'feedback_collection': {
            'enabled': True,
            'rollout_percentage': 100,
            'description': 'Feedback collection buttons'
        },
        'gemini_provider': {
            'enabled': True,
            'rollout_percentage': 100,
            'description': 'Gemini AI provider support'
        },
        'rag_retrieval': {
            'enabled': False,
            'rollout_percentage': 0,
            'description': 'RAG document retrieval'
        },
        'continuous_learning': {
            'enabled': False,
            'rollout_percentage': 0,
            'description': 'Continuous learning pipeline'
        }
    }
    
    @classmethod
    def is_enabled(
        cls,
        feature_name: str,
        tenant,
        default: bool = False
    ) -> bool:
        """
        Check if a feature is enabled for a tenant.
        
        Args:
            feature_name: Name of the feature flag
            tenant: Tenant instance
            default: Default value if flag not found
            
        Returns:
            bool: True if feature is enabled for this tenant
        """
        # Check cache first
        cache_key = f'feature_flag:{tenant.id}:{feature_name}'
        cached_value = cache.get(cache_key)
        
        if cached_value is not None:
            return cached_value
        
        # Get feature flag configuration
        flag_config = cls._get_flag_config(feature_name, tenant)
        
        if not flag_config:
            return default
        
        # Check if globally enabled
        if not flag_config.get('enabled', False):
            cache.set(cache_key, False, cls.CACHE_TTL)
            return False
        
        # Check rollout percentage
        rollout_percentage = flag_config.get('rollout_percentage', 0)
        
        if rollout_percentage >= 100:
            # Fully rolled out
            cache.set(cache_key, True, cls.CACHE_TTL)
            return True
        
        if rollout_percentage <= 0:
            # Not rolled out
            cache.set(cache_key, False, cls.CACHE_TTL)
            return False
        
        # Partial rollout - use consistent hashing
        is_enabled = cls._is_in_rollout(tenant.id, rollout_percentage)
        cache.set(cache_key, is_enabled, cls.CACHE_TTL)
        
        return is_enabled
    
    @classmethod
    def _get_flag_config(cls, feature_name: str, tenant) -> Optional[Dict[str, Any]]:
        """
        Get feature flag configuration.
        
        Args:
            feature_name: Name of the feature flag
            tenant: Tenant instance
            
        Returns:
            Dict with flag configuration or None
        """
        # Check if tenant has custom flag configuration
        if hasattr(tenant, 'settings'):
            custom_flags = getattr(tenant.settings, 'feature_flags', {})
            if feature_name in custom_flags:
                return custom_flags[feature_name]
        
        # Fall back to default flags
        return cls.DEFAULT_FLAGS.get(feature_name)
    
    @classmethod
    def _is_in_rollout(cls, tenant_id, rollout_percentage: int) -> bool:
        """
        Determine if tenant is in rollout based on consistent hashing.
        
        Uses tenant ID to consistently assign tenants to rollout groups.
        
        Args:
            tenant_id: Tenant UUID
            rollout_percentage: Percentage of tenants to include (0-100)
            
        Returns:
            bool: True if tenant is in rollout
        """
        # Convert tenant ID to integer hash
        tenant_hash = hash(str(tenant_id))
        
        # Use modulo to get consistent bucket (0-99)
        bucket = abs(tenant_hash) % 100
        
        # Include if bucket is within rollout percentage
        return bucket < rollout_percentage
    
    @classmethod
    def set_flag(
        cls,
        feature_name: str,
        tenant,
        enabled: bool,
        rollout_percentage: Optional[int] = None
    ):
        """
        Set feature flag for a tenant.
        
        Args:
            feature_name: Name of the feature flag
            tenant: Tenant instance
            enabled: Whether feature is enabled
            rollout_percentage: Optional rollout percentage (0-100)
        """
        if not hasattr(tenant, 'settings'):
            logger.warning(f"Tenant {tenant.id} has no settings, cannot set feature flag")
            return
        
        # Get or create feature flags dict
        feature_flags = getattr(tenant.settings, 'feature_flags', {})
        if not isinstance(feature_flags, dict):
            feature_flags = {}
        
        # Update flag
        flag_config = feature_flags.get(feature_name, {})
        flag_config['enabled'] = enabled
        
        if rollout_percentage is not None:
            flag_config['rollout_percentage'] = max(0, min(100, rollout_percentage))
        
        flag_config['updated_at'] = timezone.now().isoformat()
        
        feature_flags[feature_name] = flag_config
        
        # Save to tenant settings
        tenant.settings.feature_flags = feature_flags
        tenant.settings.save(update_fields=['feature_flags'])
        
        # Clear cache
        cache_key = f'feature_flag:{tenant.id}:{feature_name}'
        cache.delete(cache_key)
        
        logger.info(
            f"Feature flag updated: {feature_name} for tenant {tenant.id}: "
            f"enabled={enabled}, rollout={rollout_percentage}%"
        )
    
    @classmethod
    def get_all_flags(cls, tenant) -> Dict[str, Dict[str, Any]]:
        """
        Get all feature flags for a tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Dict of feature flags with their configurations
        """
        flags = {}
        
        # Start with defaults
        for feature_name, config in cls.DEFAULT_FLAGS.items():
            flags[feature_name] = {
                **config,
                'is_enabled': cls.is_enabled(feature_name, tenant)
            }
        
        # Override with custom flags
        if hasattr(tenant, 'settings'):
            custom_flags = getattr(tenant.settings, 'feature_flags', {})
            for feature_name, config in custom_flags.items():
                flags[feature_name] = {
                    **config,
                    'is_enabled': cls.is_enabled(feature_name, tenant)
                }
        
        return flags
    
    @classmethod
    def clear_cache(cls, tenant, feature_name: Optional[str] = None):
        """
        Clear feature flag cache.
        
        Args:
            tenant: Tenant instance
            feature_name: Optional specific feature to clear, or None for all
        """
        if feature_name:
            cache_key = f'feature_flag:{tenant.id}:{feature_name}'
            cache.delete(cache_key)
        else:
            # Clear all feature flags for tenant
            for feature in cls.DEFAULT_FLAGS.keys():
                cache_key = f'feature_flag:{tenant.id}:{feature}'
                cache.delete(cache_key)
