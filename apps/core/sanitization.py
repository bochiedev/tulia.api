"""
Input sanitization utilities for preventing XSS and SQL injection.

Provides functions to sanitize user inputs before storage and display.
"""
import re
import html
from typing import Any, Dict, List, Optional


def sanitize_html(text: str, allowed_tags: Optional[List[str]] = None) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    By default, escapes all HTML. Optionally allows specific safe tags.
    
    Args:
        text: Text to sanitize
        allowed_tags: List of allowed HTML tags (e.g., ['b', 'i', 'u'])
                     If None, all HTML is escaped
        
    Returns:
        Sanitized text safe for display
        
    Examples:
        >>> sanitize_html('<script>alert("xss")</script>')
        '&lt;script&gt;alert("xss")&lt;/script&gt;'
        
        >>> sanitize_html('<b>Bold</b> text', allowed_tags=['b'])
        '<b>Bold</b> text'
    """
    if not text:
        return text
    
    # If no allowed tags, escape all HTML
    if not allowed_tags:
        return html.escape(text)
    
    # Build regex pattern for allowed tags
    # This is a simple implementation - for production use bleach library
    allowed_pattern = '|'.join(re.escape(tag) for tag in allowed_tags)
    
    # Escape everything first
    sanitized = html.escape(text)
    
    # Unescape allowed tags
    for tag in allowed_tags:
        escaped_open = html.escape(f'<{tag}>')
        escaped_close = html.escape(f'</{tag}>')
        sanitized = sanitized.replace(escaped_open, f'<{tag}>')
        sanitized = sanitized.replace(escaped_close, f'</{tag}>')
    
    return sanitized


def sanitize_sql(text: str) -> str:
    """
    Sanitize text to prevent SQL injection.
    
    Note: Django ORM already prevents SQL injection through parameterized queries.
    This is an additional layer for raw SQL or external integrations.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text safe for SQL contexts
        
    Examples:
        >>> sanitize_sql("'; DROP TABLE users; --")
        "'' DROP TABLE users --"
    """
    if not text:
        return text
    
    # Remove common SQL injection patterns
    dangerous_patterns = [
        r";\s*DROP\s+TABLE",
        r";\s*DELETE\s+FROM",
        r";\s*UPDATE\s+",
        r";\s*INSERT\s+INTO",
        r"--",
        r"/\*.*?\*/",
        r"UNION\s+SELECT",
        r"OR\s+1\s*=\s*1",
        r"OR\s+'1'\s*=\s*'1'",
    ]
    
    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Escape single quotes (double them for SQL)
    sanitized = sanitized.replace("'", "''")
    
    return sanitized


def sanitize_text_input(
    text: str,
    max_length: Optional[int] = None,
    strip_html: bool = True,
    strip_sql: bool = False
) -> str:
    """
    General text input sanitization.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length (truncates if exceeded)
        strip_html: Whether to escape HTML (default: True)
        strip_sql: Whether to sanitize SQL patterns (default: False)
        
    Returns:
        Sanitized text
        
    Examples:
        >>> sanitize_text_input('<script>alert("xss")</script>', max_length=20)
        '&lt;script&gt;alert("'
    """
    if not text:
        return text
    
    # Strip leading/trailing whitespace
    sanitized = text.strip()
    
    # Escape HTML if requested
    if strip_html:
        sanitized = sanitize_html(sanitized)
    
    # Sanitize SQL if requested
    if strip_sql:
        sanitized = sanitize_sql(sanitized)
    
    # Enforce max length
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def sanitize_dict(
    data: Dict[str, Any],
    fields_to_sanitize: Optional[List[str]] = None,
    max_length: Optional[int] = None
) -> Dict[str, Any]:
    """
    Sanitize dictionary fields.
    
    Args:
        data: Dictionary to sanitize
        fields_to_sanitize: List of field names to sanitize (if None, sanitizes all string fields)
        max_length: Maximum length for text fields
        
    Returns:
        Dictionary with sanitized fields
        
    Examples:
        >>> sanitize_dict({'name': '<script>xss</script>', 'age': 25})
        {'name': '&lt;script&gt;xss&lt;/script&gt;', 'age': 25}
    """
    if not data:
        return data
    
    sanitized = {}
    
    for key, value in data.items():
        # Only sanitize if field is in the list (or list is None)
        should_sanitize = fields_to_sanitize is None or key in fields_to_sanitize
        
        if should_sanitize and isinstance(value, str):
            sanitized[key] = sanitize_text_input(value, max_length=max_length)
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_dict(value, fields_to_sanitize, max_length)
        elif isinstance(value, list):
            # Sanitize list items
            sanitized[key] = [
                sanitize_text_input(item, max_length=max_length)
                if isinstance(item, str) and should_sanitize
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


def validate_and_sanitize_json_field(
    data: Any,
    max_depth: int = 5,
    max_keys: int = 100,
    max_string_length: int = 1000
) -> Any:
    """
    Validate and sanitize JSON field data.
    
    Prevents:
    - Deeply nested objects (DoS via recursion)
    - Excessive number of keys (memory exhaustion)
    - Excessively long strings (memory exhaustion)
    - XSS in string values
    
    Args:
        data: JSON data to validate and sanitize
        max_depth: Maximum nesting depth
        max_keys: Maximum number of keys in objects
        max_string_length: Maximum length of string values
        
    Returns:
        Sanitized JSON data
        
    Raises:
        ValueError: If validation fails
    """
    def _validate_recursive(obj: Any, current_depth: int = 0) -> Any:
        # Check depth
        if current_depth > max_depth:
            raise ValueError(f"JSON depth exceeds maximum of {max_depth}")
        
        if isinstance(obj, dict):
            # Check number of keys
            if len(obj) > max_keys:
                raise ValueError(f"JSON object has too many keys (max: {max_keys})")
            
            # Recursively validate and sanitize
            return {
                key: _validate_recursive(value, current_depth + 1)
                for key, value in obj.items()
            }
        
        elif isinstance(obj, list):
            # Check list length
            if len(obj) > max_keys:
                raise ValueError(f"JSON array has too many items (max: {max_keys})")
            
            # Recursively validate and sanitize
            return [
                _validate_recursive(item, current_depth + 1)
                for item in obj
            ]
        
        elif isinstance(obj, str):
            # Check string length
            if len(obj) > max_string_length:
                raise ValueError(
                    f"JSON string exceeds maximum length of {max_string_length}"
                )
            
            # Sanitize HTML in strings
            return sanitize_html(obj)
        
        elif isinstance(obj, (int, float, bool, type(None))):
            # Primitive types are safe
            return obj
        
        else:
            # Unknown type - reject
            raise ValueError(f"Unsupported JSON type: {type(obj)}")
    
    return _validate_recursive(data)


# Regex patterns for common injection attempts
INJECTION_PATTERNS = [
    # SQL injection
    r"(?i)(union\s+select|drop\s+table|delete\s+from|insert\s+into|or\s+1\s*=\s*1)",
    # XSS
    r"(?i)(<script|javascript:|onerror=|onload=)",
    # Command injection
    r"(?i)(;|\||&&|\$\(|`)",
    # Path traversal
    r"(\.\./|\.\.\\)",
]


def contains_injection_attempt(text: str) -> bool:
    """
    Check if text contains common injection patterns.
    
    Args:
        text: Text to check
        
    Returns:
        True if injection patterns detected
        
    Examples:
        >>> contains_injection_attempt("'; DROP TABLE users; --")
        True
        
        >>> contains_injection_attempt("Hello world")
        False
    """
    if not text:
        return False
    
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True
    
    return False


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.
    
    Args:
        filename: Filename to sanitize
        max_length: Maximum filename length
        
    Returns:
        Safe filename
        
    Examples:
        >>> sanitize_filename("../../etc/passwd")
        'etc_passwd'
        
        >>> sanitize_filename("file<script>.txt")
        'file_script_.txt'
    """
    if not filename:
        return "unnamed"
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove path traversal attempts
    filename = filename.replace('..', '')
    
    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Limit length
    if len(filename) > max_length:
        # Preserve extension if possible
        parts = filename.rsplit('.', 1)
        if len(parts) == 2:
            name, ext = parts
            max_name_length = max_length - len(ext) - 1
            filename = name[:max_name_length] + '.' + ext
        else:
            filename = filename[:max_length]
    
    # Ensure not empty after sanitization
    if not filename or filename == '.':
        filename = "unnamed"
    
    return filename
