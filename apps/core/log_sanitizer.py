"""
Log sanitization to prevent sensitive data leakage.

Automatically redacts sensitive information from logs including:
- API keys
- Tokens (JWT, OAuth, etc.)
- Passwords
- Credit card numbers
- Phone numbers
- Email addresses (optional)
"""
import re
import logging


class SanitizingFormatter(logging.Formatter):
    """
    Custom log formatter that sanitizes sensitive data.
    
    Automatically redacts:
    - API keys (various formats)
    - Bearer tokens
    - JWT tokens
    - OAuth tokens
    - Passwords
    - Credit card numbers
    - Phone numbers
    - Twilio credentials
    - Database URLs with passwords
    """
    
    # Regex patterns for sensitive data
    PATTERNS = [
        # API Keys (various formats)
        (re.compile(r'api[_-]?key["\s:=]+([a-zA-Z0-9_\-]{20,})', re.IGNORECASE), r'api_key=[REDACTED]'),
        (re.compile(r'apikey["\s:=]+([a-zA-Z0-9_\-]{20,})', re.IGNORECASE), r'apikey=[REDACTED]'),
        (re.compile(r'key["\s:=]+([a-zA-Z0-9_\-]{32,})', re.IGNORECASE), r'key=[REDACTED]'),
        
        # Bearer tokens
        (re.compile(r'Bearer\s+([a-zA-Z0-9_\-\.]{20,})', re.IGNORECASE), r'Bearer [REDACTED]'),
        (re.compile(r'bearer["\s:=]+([a-zA-Z0-9_\-\.]{20,})', re.IGNORECASE), r'bearer=[REDACTED]'),
        
        # JWT tokens (header.payload.signature format)
        (re.compile(r'eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+'), r'[REDACTED_JWT]'),
        
        # OAuth tokens
        (re.compile(r'access[_-]?token["\s:=]+([a-zA-Z0-9_\-\.]{20,})', re.IGNORECASE), r'access_token=[REDACTED]'),
        (re.compile(r'refresh[_-]?token["\s:=]+([a-zA-Z0-9_\-\.]{20,})', re.IGNORECASE), r'refresh_token=[REDACTED]'),
        (re.compile(r'oauth[_-]?token["\s:=]+([a-zA-Z0-9_\-\.]{20,})', re.IGNORECASE), r'oauth_token=[REDACTED]'),
        
        # Passwords
        (re.compile(r'password["\s:=]+([^\s,\]}"\']+)', re.IGNORECASE), r'password=[REDACTED]'),
        (re.compile(r'passwd["\s:=]+([^\s,\]}"\']+)', re.IGNORECASE), r'passwd=[REDACTED]'),
        (re.compile(r'pwd["\s:=]+([^\s,\]}"\']+)', re.IGNORECASE), r'pwd=[REDACTED]'),
        
        # Secrets
        (re.compile(r'secret["\s:=]+([a-zA-Z0-9_\-]{20,})', re.IGNORECASE), r'secret=[REDACTED]'),
        (re.compile(r'client[_-]?secret["\s:=]+([a-zA-Z0-9_\-]{20,})', re.IGNORECASE), r'client_secret=[REDACTED]'),
        
        # Twilio credentials
        (re.compile(r'AC[a-z0-9]{32}'), r'[REDACTED_TWILIO_SID]'),
        (re.compile(r'SK[a-z0-9]{32}'), r'[REDACTED_TWILIO_KEY]'),
        (re.compile(r'twilio[_-]?sid["\s:=]+([a-zA-Z0-9]{34})', re.IGNORECASE), r'twilio_sid=[REDACTED]'),
        (re.compile(r'twilio[_-]?token["\s:=]+([a-zA-Z0-9]{32})', re.IGNORECASE), r'twilio_token=[REDACTED]'),
        (re.compile(r'twilio[_-]?auth["\s:=]+([a-zA-Z0-9]{32})', re.IGNORECASE), r'twilio_auth=[REDACTED]'),
        
        # Stripe keys
        (re.compile(r'sk_live_[a-zA-Z0-9]{24,}'), r'[REDACTED_STRIPE_SECRET]'),
        (re.compile(r'sk_test_[a-zA-Z0-9]{24,}'), r'[REDACTED_STRIPE_TEST]'),
        (re.compile(r'pk_live_[a-zA-Z0-9]{24,}'), r'[REDACTED_STRIPE_PUBLIC]'),
        
        # AWS credentials
        (re.compile(r'AKIA[0-9A-Z]{16}'), r'[REDACTED_AWS_KEY]'),
        (re.compile(r'aws[_-]?secret["\s:=]+([a-zA-Z0-9/+=]{40})', re.IGNORECASE), r'aws_secret=[REDACTED]'),
        
        # Database URLs with passwords
        (re.compile(r'://([^:]+):([^@]+)@'), r'://\1:[REDACTED]@'),
        
        # Credit card numbers (basic pattern)
        (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), r'[REDACTED_CARD]'),
        
        # Phone numbers (E.164 format)
        (re.compile(r'\+\d{1,3}\d{6,14}'), r'[REDACTED_PHONE]'),
        
        # Generic tokens
        (re.compile(r'token["\s:=]+([a-zA-Z0-9_\-\.]{32,})', re.IGNORECASE), r'token=[REDACTED]'),
        
        # Authorization headers
        (re.compile(r'Authorization["\s:]+([^\s,\]}"\']+)', re.IGNORECASE), r'Authorization: [REDACTED]'),
        
        # X-API-Key headers
        (re.compile(r'X-API-Key["\s:]+([^\s,\]}"\']+)', re.IGNORECASE), r'X-API-Key: [REDACTED]'),
    ]
    
    def format(self, record):
        """
        Format log record and sanitize sensitive data.
        
        Args:
            record: LogRecord instance
            
        Returns:
            Sanitized log message
        """
        # Format the message first
        original_message = super().format(record)
        
        # Apply all sanitization patterns
        sanitized_message = original_message
        for pattern, replacement in self.PATTERNS:
            sanitized_message = pattern.sub(replacement, sanitized_message)
        
        return sanitized_message


class SanitizingFilter(logging.Filter):
    """
    Logging filter that sanitizes sensitive data in log records.
    
    Can be used in addition to or instead of SanitizingFormatter.
    Sanitizes the message before formatting.
    """
    
    def filter(self, record):
        """
        Sanitize log record message.
        
        Args:
            record: LogRecord instance
            
        Returns:
            True (always allows the record through)
        """
        # Sanitize the message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacement in SanitizingFormatter.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        
        # Sanitize args if present
        if hasattr(record, 'args') and record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_arg = arg
                    for pattern, replacement in SanitizingFormatter.PATTERNS:
                        sanitized_arg = pattern.sub(replacement, sanitized_arg)
                    sanitized_args.append(sanitized_arg)
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)
        
        return True


def sanitize_dict_for_logging(data: dict) -> dict:
    """
    Sanitize dictionary for safe logging.
    
    Removes or redacts sensitive fields.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary
    """
    if not isinstance(data, dict):
        return data
    
    # Fields to completely remove
    remove_fields = {
        'password', 'passwd', 'pwd',
        'secret', 'client_secret', 'api_secret',
        'token', 'access_token', 'refresh_token', 'auth_token',
        'api_key', 'apikey',
        'twilio_token', 'twilio_auth_token',
        'stripe_secret_key', 'stripe_key',
        'aws_secret_access_key',
        'private_key', 'ssh_key',
        'credit_card', 'card_number', 'cvv', 'cvc',
    }
    
    # Fields to mask (show last 4 chars)
    mask_fields = {
        'phone', 'phone_number', 'phone_e164',
        'email', 'email_address',
        'twilio_sid', 'account_sid',
    }
    
    sanitized = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        
        # Remove sensitive fields
        if any(field in key_lower for field in remove_fields):
            sanitized[key] = '[REDACTED]'
        # Mask PII fields
        elif any(field in key_lower for field in mask_fields):
            if isinstance(value, str) and len(value) > 4:
                sanitized[key] = '****' + value[-4:]
            else:
                sanitized[key] = '****'
        # Recursively sanitize nested dicts
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict_for_logging(value)
        # Sanitize lists
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict_for_logging(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_url(url: str) -> str:
    """
    Sanitize URL by removing password from connection strings.
    
    Args:
        url: URL to sanitize
        
    Returns:
        Sanitized URL
        
    Examples:
        >>> sanitize_url('postgresql://user:pass@localhost/db')
        'postgresql://user:[REDACTED]@localhost/db'
    """
    if not url:
        return url
    
    # Pattern for URLs with passwords
    pattern = re.compile(r'://([^:]+):([^@]+)@')
    return pattern.sub(r'://\1:[REDACTED]@', url)


# Convenience function for quick sanitization
def sanitize_for_logging(obj):
    """
    Sanitize any object for safe logging.
    
    Args:
        obj: Object to sanitize (str, dict, list, etc.)
        
    Returns:
        Sanitized object
    """
    if isinstance(obj, dict):
        return sanitize_dict_for_logging(obj)
    elif isinstance(obj, str):
        sanitized = obj
        for pattern, replacement in SanitizingFormatter.PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_for_logging(item) for item in obj]
    else:
        return obj
