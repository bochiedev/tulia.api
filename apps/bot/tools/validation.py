"""
Input validation utilities for tool contracts.
"""

import re
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal, InvalidOperation


def validate_phone_e164(phone: str) -> Optional[str]:
    """
    Validate phone number in E164 format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(phone, str):
        return "Phone number must be a string"
    
    # E164 format: +[country code][number] (1-15 digits total after +)
    pattern = r'^\+[1-9]\d{1,14}$'
    if not re.match(pattern, phone):
        return "Phone number must be in E164 format (e.g., +254712345678)"
    
    return None


def validate_kenya_phone(phone: str) -> Optional[str]:
    """
    Validate Kenyan phone number in E164 format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(phone, str):
        return "Phone number must be a string"
    
    # Kenya format: +254[7/1][8 digits]
    pattern = r'^\+254[71]\d{8}$'
    if not re.match(pattern, phone):
        return "Phone number must be a valid Kenyan number (e.g., +254712345678)"
    
    return None


def validate_email(email: str) -> Optional[str]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(email, str):
        return "Email must be a string"
    
    # Basic email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return "Invalid email address format"
    
    return None


def validate_currency_code(currency: str) -> Optional[str]:
    """
    Validate currency code (ISO 4217).
    
    Args:
        currency: Currency code to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(currency, str):
        return "Currency code must be a string"
    
    # Common currency codes
    valid_currencies = ['KES', 'USD', 'EUR', 'GBP', 'UGX', 'TZS']
    if currency.upper() not in valid_currencies:
        return f"Currency code must be one of: {', '.join(valid_currencies)}"
    
    return None


def validate_amount(amount: Union[int, float, str, Decimal], min_value: float = 0.0) -> Optional[str]:
    """
    Validate monetary amount.
    
    Args:
        amount: Amount to validate
        min_value: Minimum allowed value
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return "Amount must be a valid number"
    
    if decimal_amount < Decimal(str(min_value)):
        return f"Amount must be at least {min_value}"
    
    # Check for reasonable maximum (1 billion)
    if decimal_amount > Decimal('1000000000'):
        return "Amount is too large"
    
    # Check decimal places (max 2 for currency)
    if decimal_amount.as_tuple().exponent < -2:
        return "Amount cannot have more than 2 decimal places"
    
    return None


def validate_language_code(language: str) -> Optional[str]:
    """
    Validate language code.
    
    Args:
        language: Language code to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(language, str):
        return "Language code must be a string"
    
    valid_languages = ['en', 'sw', 'sheng', 'mixed']
    if language.lower() not in valid_languages:
        return f"Language code must be one of: {', '.join(valid_languages)}"
    
    return None


def validate_priority(priority: str) -> Optional[str]:
    """
    Validate priority level.
    
    Args:
        priority: Priority to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(priority, str):
        return "Priority must be a string"
    
    valid_priorities = ['low', 'medium', 'high', 'urgent']
    if priority.lower() not in valid_priorities:
        return f"Priority must be one of: {', '.join(valid_priorities)}"
    
    return None


def validate_document_type(doc_type: str) -> Optional[str]:
    """
    Validate document type.
    
    Args:
        doc_type: Document type to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(doc_type, str):
        return "Document type must be a string"
    
    valid_types = ['faq', 'policy', 'doc', 'sop', 'manual']
    if doc_type.lower() not in valid_types:
        return f"Document type must be one of: {', '.join(valid_types)}"
    
    return None


def validate_confidence_score(score: Union[int, float]) -> Optional[str]:
    """
    Validate confidence score (0.0 to 1.0).
    
    Args:
        score: Confidence score to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    try:
        float_score = float(score)
    except (ValueError, TypeError):
        return "Confidence score must be a number"
    
    if not (0.0 <= float_score <= 1.0):
        return "Confidence score must be between 0.0 and 1.0"
    
    return None


def validate_quantity(quantity: Union[int, str]) -> Optional[str]:
    """
    Validate quantity (positive integer).
    
    Args:
        quantity: Quantity to validate
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    try:
        int_quantity = int(quantity)
    except (ValueError, TypeError):
        return "Quantity must be an integer"
    
    if int_quantity < 1:
        return "Quantity must be at least 1"
    
    if int_quantity > 1000:
        return "Quantity cannot exceed 1000"
    
    return None


def validate_limit(limit: Union[int, str], max_limit: int = 100) -> Optional[str]:
    """
    Validate result limit.
    
    Args:
        limit: Limit to validate
        max_limit: Maximum allowed limit
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    try:
        int_limit = int(limit)
    except (ValueError, TypeError):
        return "Limit must be an integer"
    
    if int_limit < 1:
        return "Limit must be at least 1"
    
    if int_limit > max_limit:
        return f"Limit cannot exceed {max_limit}"
    
    return None


def validate_string_length(value: str, field_name: str, min_length: int = 1, max_length: int = 1000) -> Optional[str]:
    """
    Validate string length.
    
    Args:
        value: String to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(value, str):
        return f"{field_name} must be a string"
    
    if len(value) < min_length:
        return f"{field_name} must be at least {min_length} characters long"
    
    if len(value) > max_length:
        return f"{field_name} cannot exceed {max_length} characters"
    
    return None


def sanitize_search_query(query: str) -> str:
    """
    Sanitize search query to prevent injection attacks.
    
    Args:
        query: Search query to sanitize
        
    Returns:
        str: Sanitized query
    """
    if not isinstance(query, str):
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\';\\]', '', query)
    
    # Limit length
    sanitized = sanitized[:500]
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    return sanitized


def validate_json_object(obj: Any, field_name: str) -> Optional[str]:
    """
    Validate that an object is a valid JSON-serializable dict.
    
    Args:
        obj: Object to validate
        field_name: Name of the field for error messages
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(obj, dict):
        return f"{field_name} must be a JSON object"
    
    try:
        import json
        json.dumps(obj)
    except (TypeError, ValueError):
        return f"{field_name} must be JSON-serializable"
    
    return None


def validate_array(arr: Any, field_name: str, max_items: int = 100) -> Optional[str]:
    """
    Validate that an object is a valid array.
    
    Args:
        arr: Array to validate
        field_name: Name of the field for error messages
        max_items: Maximum number of items allowed
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
    """
    if not isinstance(arr, list):
        return f"{field_name} must be an array"
    
    if len(arr) > max_items:
        return f"{field_name} cannot have more than {max_items} items"
    
    return None