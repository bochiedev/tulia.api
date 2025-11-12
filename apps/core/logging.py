"""
Custom logging formatters for structured JSON logging.
"""
import json
import logging
import re
import traceback
from datetime import datetime


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
