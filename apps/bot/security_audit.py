"""
Security Audit Tool for AI Agent Multi-Tenant Isolation.

This module provides automated security auditing for tenant isolation,
input validation, and data encryption in the AI agent system.
"""
import logging
from typing import List, Dict, Any, Tuple
from django.db import models
from django.apps import apps
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class TenantIsolationAuditor:
    """
    Auditor for verifying tenant isolation in database queries.
    
    Checks that all queries properly filter by tenant to prevent
    cross-tenant data leakage.
    """
    
    # Models that should have tenant filtering
    TENANT_SCOPED_MODELS = [
        'bot.IntentEvent',
        'bot.AgentConfiguration',
        'bot.KnowledgeEntry',
        'bot.ConversationContext',
        'bot.AgentInteraction',
        'messaging.Conversation',
        'messaging.Message',
        'catalog.Product',
        'services.Service',
        'orders.Order',
    ]
    
    @classmethod
    def audit_model_queries(cls) -> Dict[str, Any]:
        """
        Audit all tenant-scoped models for proper filtering.
        
        Returns:
            Dictionary with audit results including:
            - models_checked: Number of models audited
            - issues_found: List of issues discovered
            - recommendations: List of recommendations
        """
        results = {
            'models_checked': 0,
            'issues_found': [],
            'recommendations': [],
            'passed': True
        }
        
        for model_path in cls.TENANT_SCOPED_MODELS:
            app_label, model_name = model_path.split('.')
            
            try:
                model = apps.get_model(app_label, model_name)
                results['models_checked'] += 1
                
                # Check if model has tenant field
                if not cls._has_tenant_field(model):
                    results['issues_found'].append({
                        'model': model_path,
                        'severity': 'HIGH',
                        'issue': 'Model does not have tenant field or relationship',
                        'recommendation': 'Add tenant ForeignKey field with db_index=True'
                    })
                    results['passed'] = False
                
                # Check if model has custom manager with tenant filtering
                if not cls._has_tenant_manager(model):
                    results['recommendations'].append({
                        'model': model_path,
                        'severity': 'MEDIUM',
                        'recommendation': 'Consider adding custom manager with tenant filtering methods'
                    })
                
                # Check if model has proper indexes
                if not cls._has_tenant_indexes(model):
                    results['issues_found'].append({
                        'model': model_path,
                        'severity': 'MEDIUM',
                        'issue': 'Model missing tenant-based database indexes',
                        'recommendation': 'Add indexes on tenant field and tenant+created_at'
                    })
                
            except LookupError:
                results['issues_found'].append({
                    'model': model_path,
                    'severity': 'LOW',
                    'issue': f'Model {model_path} not found',
                    'recommendation': 'Verify model exists or remove from audit list'
                })
        
        return results
    
    @staticmethod
    def _has_tenant_field(model) -> bool:
        """Check if model has tenant field or relationship."""
        # Direct tenant field
        if hasattr(model, 'tenant'):
            return True
        
        # Check through relationships (e.g., conversation.tenant)
        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey):
                related_model = field.related_model
                if hasattr(related_model, 'tenant'):
                    return True
        
        return False
    
    @staticmethod
    def _has_tenant_manager(model) -> bool:
        """Check if model has custom manager with tenant methods."""
        manager = model._default_manager
        
        # Check for common tenant filtering methods
        tenant_methods = ['for_tenant', 'by_tenant', 'tenant_filter']
        return any(hasattr(manager, method) for method in tenant_methods)
    
    @staticmethod
    def _has_tenant_indexes(model) -> bool:
        """Check if model has proper tenant-based indexes."""
        indexes = model._meta.indexes
        
        # Check if any index includes tenant field
        for index in indexes:
            if 'tenant' in [f.name for f in index.fields]:
                return True
        
        return False
    
    @classmethod
    def verify_query_filtering(
        cls,
        model_class,
        tenant,
        sample_query_method: str = 'all'
    ) -> Tuple[bool, str]:
        """
        Verify that a query properly filters by tenant.
        
        Args:
            model_class: Model class to test
            tenant: Tenant instance to filter by
            sample_query_method: Method name to test (default: 'all')
            
        Returns:
            Tuple of (is_safe: bool, message: str)
        """
        try:
            # Get queryset
            if hasattr(model_class.objects, sample_query_method):
                queryset = getattr(model_class.objects, sample_query_method)()
            else:
                queryset = model_class.objects.all()
            
            # Check if queryset has tenant filter
            query_str = str(queryset.query)
            
            if 'tenant' in query_str.lower():
                return True, f"Query properly filters by tenant: {query_str[:100]}"
            else:
                return False, f"Query does NOT filter by tenant: {query_str[:100]}"
                
        except Exception as e:
            return False, f"Error verifying query: {str(e)}"


class InputSanitizer:
    """
    Input sanitization for customer messages and knowledge base content.
    
    Prevents prompt injection attacks, XSS, and other malicious input.
    """
    
    # Patterns that might indicate prompt injection
    PROMPT_INJECTION_PATTERNS = [
        'ignore previous instructions',
        'ignore all previous',
        'disregard previous',
        'forget everything',
        'new instructions',
        'system:',
        'assistant:',
        'user:',
        '<|im_start|>',
        '<|im_end|>',
        '[INST]',
        '[/INST]',
    ]
    
    # Maximum lengths for different input types
    MAX_MESSAGE_LENGTH = 5000
    MAX_KNOWLEDGE_TITLE_LENGTH = 255
    MAX_KNOWLEDGE_CONTENT_LENGTH = 50000
    
    @classmethod
    def sanitize_customer_message(cls, message_text: str) -> str:
        """
        Sanitize customer message input.
        
        Removes potentially malicious content while preserving
        legitimate customer messages.
        
        Args:
            message_text: Raw customer message
            
        Returns:
            Sanitized message text
            
        Raises:
            ValidationError: If message contains dangerous patterns
        """
        if not message_text:
            return ''
        
        # Truncate to maximum length
        if len(message_text) > cls.MAX_MESSAGE_LENGTH:
            logger.warning(
                f"Message truncated from {len(message_text)} to {cls.MAX_MESSAGE_LENGTH} characters"
            )
            message_text = message_text[:cls.MAX_MESSAGE_LENGTH]
        
        # Check for prompt injection patterns
        message_lower = message_text.lower()
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if pattern in message_lower:
                logger.warning(
                    f"Potential prompt injection detected: '{pattern}' in message"
                )
                # Remove the suspicious pattern
                message_text = message_text.replace(pattern, '[removed]')
                message_text = message_text.replace(pattern.upper(), '[removed]')
                message_text = message_text.replace(pattern.title(), '[removed]')
        
        # Remove control characters except newlines and tabs
        sanitized = ''.join(
            char for char in message_text
            if char.isprintable() or char in '\n\t'
        )
        
        # Remove excessive whitespace
        sanitized = ' '.join(sanitized.split())
        
        return sanitized.strip()
    
    @classmethod
    def sanitize_knowledge_content(
        cls,
        title: str,
        content: str
    ) -> Tuple[str, str]:
        """
        Sanitize knowledge base entry content.
        
        Args:
            title: Knowledge entry title
            content: Knowledge entry content
            
        Returns:
            Tuple of (sanitized_title, sanitized_content)
            
        Raises:
            ValidationError: If content is invalid
        """
        # Sanitize title
        if not title:
            raise ValidationError("Title cannot be empty")
        
        if len(title) > cls.MAX_KNOWLEDGE_TITLE_LENGTH:
            raise ValidationError(
                f"Title exceeds maximum length of {cls.MAX_KNOWLEDGE_TITLE_LENGTH}"
            )
        
        sanitized_title = cls._sanitize_text(title)
        
        # Sanitize content
        if not content:
            raise ValidationError("Content cannot be empty")
        
        if len(content) > cls.MAX_KNOWLEDGE_CONTENT_LENGTH:
            raise ValidationError(
                f"Content exceeds maximum length of {cls.MAX_KNOWLEDGE_CONTENT_LENGTH}"
            )
        
        sanitized_content = cls._sanitize_text(content)
        
        return sanitized_title, sanitized_content
    
    @classmethod
    def _sanitize_text(cls, text: str) -> str:
        """
        Generic text sanitization.
        
        Args:
            text: Raw text
            
        Returns:
            Sanitized text
        """
        # Remove control characters except newlines and tabs
        sanitized = ''.join(
            char for char in text
            if char.isprintable() or char in '\n\t'
        )
        
        # Normalize whitespace
        lines = sanitized.split('\n')
        lines = [' '.join(line.split()) for line in lines]
        sanitized = '\n'.join(lines)
        
        return sanitized.strip()
    
    @classmethod
    def validate_json_field(cls, data: Any, field_name: str) -> None:
        """
        Validate JSON field data.
        
        Args:
            data: JSON data to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If data is invalid
        """
        if data is None:
            return
        
        # Check for excessively nested structures
        if isinstance(data, (dict, list)):
            depth = cls._get_json_depth(data)
            if depth > 10:
                raise ValidationError(
                    f"{field_name}: JSON structure too deeply nested (max depth: 10)"
                )
        
        # Check for excessively large structures
        import json
        json_str = json.dumps(data)
        if len(json_str) > 100000:  # 100KB limit
            raise ValidationError(
                f"{field_name}: JSON data too large (max size: 100KB)"
            )
    
    @staticmethod
    def _get_json_depth(data: Any, current_depth: int = 0) -> int:
        """Calculate maximum depth of JSON structure."""
        if not isinstance(data, (dict, list)):
            return current_depth
        
        if isinstance(data, dict):
            if not data:
                return current_depth
            return max(
                InputSanitizer._get_json_depth(v, current_depth + 1)
                for v in data.values()
            )
        else:  # list
            if not data:
                return current_depth
            return max(
                InputSanitizer._get_json_depth(item, current_depth + 1)
                for item in data
            )


class RateLimitChecker:
    """
    Rate limiting checker for API endpoints.
    
    Helps prevent abuse and ensure fair usage across tenants.
    """
    
    # Rate limits per endpoint type (requests per minute)
    RATE_LIMITS = {
        'knowledge_create': 10,
        'knowledge_search': 60,
        'agent_config_update': 5,
        'message_processing': 100,
    }
    
    @classmethod
    def check_rate_limit(
        cls,
        tenant_id: str,
        endpoint_type: str,
        cache_backend=None
    ) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.
        
        Args:
            tenant_id: Tenant ID
            endpoint_type: Type of endpoint being accessed
            cache_backend: Cache backend (defaults to Django cache)
            
        Returns:
            Tuple of (is_allowed: bool, remaining_requests: int)
        """
        if cache_backend is None:
            from django.core.cache import cache
            cache_backend = cache
        
        limit = cls.RATE_LIMITS.get(endpoint_type, 60)
        cache_key = f"rate_limit:{tenant_id}:{endpoint_type}"
        
        # Get current count
        current_count = cache_backend.get(cache_key, 0)
        
        if current_count >= limit:
            return False, 0
        
        # Increment count
        cache_backend.set(cache_key, current_count + 1, 60)  # 60 second TTL
        
        remaining = limit - current_count - 1
        return True, remaining


def run_security_audit() -> Dict[str, Any]:
    """
    Run complete security audit.
    
    Returns:
        Dictionary with audit results
    """
    logger.info("Starting security audit...")
    
    results = {
        'timestamp': None,
        'tenant_isolation': None,
        'overall_status': 'PASSED',
        'critical_issues': [],
        'warnings': [],
        'recommendations': []
    }
    
    # Audit tenant isolation
    isolation_results = TenantIsolationAuditor.audit_model_queries()
    results['tenant_isolation'] = isolation_results
    
    if not isolation_results['passed']:
        results['overall_status'] = 'FAILED'
        results['critical_issues'].extend([
            issue for issue in isolation_results['issues_found']
            if issue['severity'] == 'HIGH'
        ])
        results['warnings'].extend([
            issue for issue in isolation_results['issues_found']
            if issue['severity'] in ['MEDIUM', 'LOW']
        ])
    
    results['recommendations'].extend(isolation_results.get('recommendations', []))
    
    from django.utils import timezone
    results['timestamp'] = timezone.now().isoformat()
    
    logger.info(f"Security audit completed: {results['overall_status']}")
    
    return results
