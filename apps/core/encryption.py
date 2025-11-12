"""
Encryption utilities for PII data.

Provides AES-256-GCM encryption for sensitive fields like phone numbers,
API keys, and credentials.
"""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from django.conf import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self):
        """Initialize encryption service with key from settings."""
        encryption_key = settings.ENCRYPTION_KEY
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY must be set in settings")
        
        # Decode base64 key
        try:
            self.key = base64.b64decode(encryption_key)
        except Exception:
            raise ValueError("ENCRYPTION_KEY must be a valid base64-encoded 32-byte key")
        
        if len(self.key) != 32:
            raise ValueError("ENCRYPTION_KEY must be 32 bytes (256 bits)")
        
        self.cipher = AESGCM(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted data with nonce prepended
        """
        if not plaintext:
            return plaintext
        
        # Generate random nonce (12 bytes for GCM)
        nonce = os.urandom(12)
        
        # Encrypt
        ciphertext = self.cipher.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Prepend nonce to ciphertext and encode as base64
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted string.
        
        Args:
            encrypted_data: Base64-encoded encrypted data with nonce
            
        Returns:
            Decrypted plaintext string
        """
        if not encrypted_data:
            return encrypted_data
        
        try:
            # Decode base64
            data = base64.b64decode(encrypted_data)
            
            # Extract nonce (first 12 bytes) and ciphertext
            nonce = data[:12]
            ciphertext = data[12:]
            
            # Decrypt
            plaintext = self.cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


# Global instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get or create global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def mask_pii(value: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """
    Mask PII data for display in logs and exports.
    
    Shows only the last N characters, masking the rest.
    Useful for phone numbers, emails, etc.
    
    Args:
        value: Value to mask
        mask_char: Character to use for masking (default: *)
        visible_chars: Number of characters to show at end (default: 4)
        
    Returns:
        Masked string
        
    Examples:
        mask_pii('+1234567890') -> '******7890'
        mask_pii('user@example.com') -> '************.com'
    """
    if not value or len(value) <= visible_chars:
        return mask_char * len(value) if value else ''
    
    masked_length = len(value) - visible_chars
    return (mask_char * masked_length) + value[-visible_chars:]


def mask_email(email: str) -> str:
    """
    Mask email address for display.
    
    Shows first character of username and domain.
    
    Args:
        email: Email address to mask
        
    Returns:
        Masked email
        
    Example:
        mask_email('user@example.com') -> 'u***@e******.com'
    """
    if not email or '@' not in email:
        return mask_pii(email)
    
    username, domain = email.split('@', 1)
    
    # Mask username (show first char)
    if len(username) > 1:
        masked_username = username[0] + ('*' * (len(username) - 1))
    else:
        masked_username = username
    
    # Mask domain (show first char and TLD)
    if '.' in domain:
        domain_parts = domain.rsplit('.', 1)
        domain_name = domain_parts[0]
        tld = domain_parts[1]
        
        if len(domain_name) > 1:
            masked_domain = domain_name[0] + ('*' * (len(domain_name) - 1)) + '.' + tld
        else:
            masked_domain = domain_name + '.' + tld
    else:
        masked_domain = domain[0] + ('*' * (len(domain) - 1)) if len(domain) > 1 else domain
    
    return f"{masked_username}@{masked_domain}"


def mask_phone(phone: str) -> str:
    """
    Mask phone number for display.
    
    Shows only last 4 digits.
    
    Args:
        phone: Phone number to mask
        
    Returns:
        Masked phone number
        
    Example:
        mask_phone('+1234567890') -> '******7890'
    """
    return mask_pii(phone, visible_chars=4)


def sanitize_for_export(data: dict, pii_fields: list = None) -> dict:
    """
    Sanitize dictionary for export by masking PII fields.
    
    Args:
        data: Dictionary to sanitize
        pii_fields: List of field names to mask (default: common PII fields)
        
    Returns:
        Sanitized dictionary with PII fields masked
    """
    if pii_fields is None:
        pii_fields = [
            'phone', 'phone_e164', 'phone_number',
            'email', 'email_address',
            'ssn', 'social_security_number',
            'credit_card', 'card_number',
            'password', 'password_hash',
            'api_key', 'secret', 'token',
            'twilio_sid', 'twilio_token', 'webhook_secret',
        ]
    
    sanitized = data.copy()
    
    for field in pii_fields:
        if field in sanitized and sanitized[field]:
            value = sanitized[field]
            
            # Determine masking strategy based on field name
            if 'email' in field.lower():
                sanitized[field] = mask_email(str(value))
            elif 'phone' in field.lower():
                sanitized[field] = mask_phone(str(value))
            else:
                sanitized[field] = mask_pii(str(value))
    
    return sanitized


def sanitize_for_logging(data: dict) -> dict:
    """
    Sanitize dictionary for logging by removing/masking sensitive fields.
    
    More aggressive than export sanitization - completely removes
    some fields that should never appear in logs.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary safe for logging
    """
    # Fields to completely remove from logs
    remove_fields = [
        'password', 'password_hash',
        'api_key', 'secret', 'token', 'access_token', 'refresh_token',
        'twilio_token', 'webhook_secret',
        'credit_card', 'card_number', 'cvv',
        'ssn', 'social_security_number',
    ]
    
    # Fields to mask in logs
    mask_fields = [
        'phone', 'phone_e164', 'phone_number',
        'email', 'email_address',
        'twilio_sid',
    ]
    
    sanitized = data.copy()
    
    # Remove sensitive fields
    for field in remove_fields:
        if field in sanitized:
            sanitized[field] = '[REDACTED]'
    
    # Mask PII fields
    for field in mask_fields:
        if field in sanitized and sanitized[field]:
            value = sanitized[field]
            
            if 'email' in field.lower():
                sanitized[field] = mask_email(str(value))
            elif 'phone' in field.lower():
                sanitized[field] = mask_phone(str(value))
            else:
                sanitized[field] = mask_pii(str(value))
    
    return sanitized
