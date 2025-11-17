"""
Custom logging formatters for structured JSON logging.
"""
import json
import logging
import re
import traceback
from datetime import datetime
from django.utils import timezone
import sentry_sdk


class PIIMasker:
    """
    Utility class to mask sensitive PII data in logs.
    """
    
    # Patterns for sensitive data
    PHONE_PATTERN = re.compile(r'\+?\d{10,15}')
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    API_KEY_PATTERN = re.compile(r'(api[_-]?key|token|secret|password|auth)["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE)
    CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
    
    # Sensitive field names that should be masked
    SENSITIVE_FIELDS = {
        'phone', 'phone_e164', 'phone_number', 'mobile',
        'email', 'email_address',
        'password', 'password_hash', 'passwd',
        'api_key', 'api_token', 'access_token', 'refresh_token', 'bearer_token',
        'secret', 'secret_key', 'webhook_secret',
        'twilio_sid', 'twilio_token', 'twilio_auth_token',
        'credit_card', 'card_number', 'cvv', 'ssn',
        'woo_consumer_key', 'woo_consumer_secret',
        'shopify_access_token',
    }
    
    @classmethod
    def mask_phone(cls, text):
        """Mask phone numbers in text."""
        if not isinstance(text, str):
            return text
        return cls.PHONE_PATTERN.sub(lambda m: m.group(0)[:3] + '*' * (len(m.group(0)) - 3), text)
    
    @classmethod
    def mask_email(cls, text):
        """Mask email addresses in text."""
        if not isinstance(text, str):
            return text
        def mask_email_match(match):
            email = match.group(0)
            parts = email.split('@')
            if len(parts) == 2:
                username = parts[0]
                domain = parts[1]
                masked_username = username[0] + '*' * (len(username) - 1) if len(username) > 1 else username
                return f"{masked_username}@{domain}"
            return email
        return cls.EMAIL_PATTERN.sub(mask_email_match, text)
    
    @classmethod
    def mask_api_keys(cls, text):
        """Mask API keys, tokens, and secrets in text."""
        if not isinstance(text, str):
            return text
        return cls.API_KEY_PATTERN.sub(r'\1: ********', text)
    
    @classmethod
    def mask_credit_cards(cls, text):
        """Mask credit card numbers in text."""
        if not isinstance(text, str):
            return text
        return cls.CREDIT_CARD_PATTERN.sub(lambda m: '*' * (len(m.group(0)) - 4) + m.group(0)[-4:], text)
    
    @classmethod
    def mask_text(cls, text):
        """Apply all masking patterns to text."""
        if not isinstance(text, str):
            return text
        text = cls.mask_phone(text)
        text = cls.mask_email(text)
        text = cls.mask_api_keys(text)
        text = cls.mask_credit_cards(text)
        return text
    
    @classmethod
    def mask_dict(cls, data):
        """Recursively mask sensitive data in dictionaries."""
        if not isinstance(data, dict):
            return data
        
        masked = {}
        for key, value in data.items():
            # Check if field name is sensitive
            if any(sensitive in key.lower() for sensitive in cls.SENSITIVE_FIELDS):
                if value and not isinstance(value, (dict, list)):
                    masked[key] = '********'
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [cls.mask_dict(item) if isinstance(item, dict) else cls.mask_text(str(item)) if isinstance(item, str) else item for item in value]
            elif isinstance(value, str):
                masked[key] = cls.mask_text(value)
            else:
                masked[key] = value
        
        return masked


class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.
    Includes request_id and tenant_id from extra fields if available.
    Automatically masks sensitive PII data.
    """
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': PIIMasker.mask_text(record.getMessage()),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add request_id if available
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        # Add tenant_id if available
        if hasattr(record, 'tenant_id'):
            log_data['tenant_id'] = str(record.tenant_id)
        
        # Add task_id for Celery tasks
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        
        # Add task_name for Celery tasks
        if hasattr(record, 'task_name'):
            log_data['task_name'] = record.task_name
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': PIIMasker.mask_text(str(record.exc_info[1])),
                'traceback': [PIIMasker.mask_text(line) for line in traceback.format_exception(*record.exc_info)],
            }
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'lineno', 'module', 'msecs', 'message',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'request_id', 'tenant_id', 'task_id', 'task_name']:
                if not key.startswith('_'):
                    try:
                        # Mask sensitive data in extra fields
                        if isinstance(value, dict):
                            masked_value = PIIMasker.mask_dict(value)
                        elif isinstance(value, str):
                            masked_value = PIIMasker.mask_text(value)
                        else:
                            masked_value = value
                        
                        json.dumps(masked_value)  # Test if serializable
                        log_data[key] = masked_value
                    except (TypeError, ValueError):
                        log_data[key] = PIIMasker.mask_text(str(value))
        
        return json.dumps(log_data)



class SecurityLogger:
    """
    Centralized security event logging for critical security events.
    
    Logs security-related events with structured data and sends critical
    events to Sentry for alerting and monitoring.
    
    All security events are logged with:
    - Event type
    - Timestamp
    - IP address
    - User information (if available)
    - Tenant information (if available)
    - Additional context
    
    Critical events are also sent to Sentry for real-time alerting.
    """
    
    # Define which event types are critical and should alert via Sentry
    CRITICAL_EVENTS = {
        'invalid_webhook_signature',
        'four_eyes_violation',
        'suspicious_activity',
    }
    
    @staticmethod
    def log_event(event_type: str, level: str = 'warning', **context):
        """
        Log a security event with structured data.
        
        Args:
            event_type: Type of security event (e.g., 'failed_login', 'invalid_webhook_signature')
            level: Log level ('info', 'warning', 'error', 'critical')
            **context: Additional context data (ip_address, user_email, tenant_id, etc.)
            
        Example:
            >>> SecurityLogger.log_event(
            ...     'invalid_webhook_signature',
            ...     ip_address='192.168.1.1',
            ...     tenant_id='123',
            ...     provider='twilio'
            ... )
        """
        logger = logging.getLogger('security')
        
        # Build structured log data
        log_data = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
        }
        
        # Add all context data
        log_data.update(context)
        
        # Mask sensitive data
        log_data = PIIMasker.mask_dict(log_data)
        
        # Log at appropriate level
        log_method = getattr(logger, level, logger.warning)
        log_method(
            f"Security event: {event_type}",
            extra=log_data
        )
        
        # Send critical events to Sentry
        if event_type in SecurityLogger.CRITICAL_EVENTS:
            sentry_sdk.capture_message(
                f"Critical security event: {event_type}",
                level='error',
                extras=log_data
            )
    
    @staticmethod
    def log_failed_login(email: str, ip_address: str, user_agent: str = None, reason: str = None):
        """
        Log a failed login attempt.
        
        Args:
            email: Email address used in login attempt
            ip_address: IP address of the request
            user_agent: User agent string (optional)
            reason: Reason for failure (optional)
        """
        SecurityLogger.log_event(
            'failed_login',
            level='warning',
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason
        )
    
    @staticmethod
    def log_permission_denied(user, tenant, required_scopes: set, ip_address: str):
        """
        Log a permission denial.
        
        Args:
            user: User instance
            tenant: Tenant instance
            required_scopes: Set of required scopes that were missing
            ip_address: IP address of the request
        """
        SecurityLogger.log_event(
            'permission_denied',
            level='warning',
            user_email=user.email if user else None,
            user_id=str(user.id) if user else None,
            tenant_id=str(tenant.id) if tenant else None,
            tenant_slug=tenant.slug if tenant else None,
            required_scopes=list(required_scopes),
            ip_address=ip_address
        )
    
    @staticmethod
    def log_invalid_webhook_signature(
        provider: str,
        tenant_id: str = None,
        ip_address: str = None,
        url: str = None,
        user_agent: str = None
    ):
        """
        Log an invalid webhook signature attempt.
        
        This is a critical security event as it indicates either:
        - An attacker attempting to spoof webhooks
        - Misconfigured webhook credentials
        - Man-in-the-middle attack
        
        Args:
            provider: Webhook provider (e.g., 'twilio', 'woocommerce', 'shopify')
            tenant_id: Tenant ID (if resolved)
            ip_address: IP address of the request
            url: Webhook URL that was called
            user_agent: User agent string
        """
        SecurityLogger.log_event(
            'invalid_webhook_signature',
            level='error',
            provider=provider,
            tenant_id=tenant_id,
            ip_address=ip_address,
            url=url,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_rate_limit_exceeded(
        endpoint: str,
        ip_address: str,
        user_email: str = None,
        tenant_id: str = None,
        limit: str = None
    ):
        """
        Log a rate limit violation.
        
        Args:
            endpoint: API endpoint that was rate limited
            ip_address: IP address of the request
            user_email: Email of the user (if authenticated)
            tenant_id: Tenant ID (if applicable)
            limit: Rate limit that was exceeded (e.g., '5/min')
        """
        SecurityLogger.log_event(
            'rate_limit_exceeded',
            level='warning',
            endpoint=endpoint,
            ip_address=ip_address,
            user_email=user_email,
            tenant_id=tenant_id,
            limit=limit
        )
    
    @staticmethod
    def log_four_eyes_violation(
        initiator_user_id: str,
        approver_user_id: str,
        tenant_id: str,
        operation: str,
        ip_address: str = None
    ):
        """
        Log a four-eyes principle violation attempt.
        
        This occurs when the same user attempts to both initiate and approve
        a sensitive operation (e.g., withdrawal).
        
        Args:
            initiator_user_id: User ID of the initiator
            approver_user_id: User ID of the approver (same as initiator)
            tenant_id: Tenant ID
            operation: Operation being attempted (e.g., 'withdrawal_approval')
            ip_address: IP address of the request
        """
        SecurityLogger.log_event(
            'four_eyes_violation',
            level='error',
            initiator_user_id=initiator_user_id,
            approver_user_id=approver_user_id,
            tenant_id=tenant_id,
            operation=operation,
            ip_address=ip_address
        )
    
    @staticmethod
    def log_suspicious_activity(
        activity_type: str,
        description: str,
        ip_address: str = None,
        user_email: str = None,
        tenant_id: str = None,
        **additional_context
    ):
        """
        Log suspicious activity that doesn't fit other categories.
        
        Args:
            activity_type: Type of suspicious activity
            description: Human-readable description
            ip_address: IP address of the request
            user_email: Email of the user (if known)
            tenant_id: Tenant ID (if applicable)
            **additional_context: Any additional context data
        """
        SecurityLogger.log_event(
            'suspicious_activity',
            level='error',
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_email=user_email,
            tenant_id=tenant_id,
            **additional_context
        )
