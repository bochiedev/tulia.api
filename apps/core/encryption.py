"""
Encryption utilities for PII data.

Provides AES-256-GCM encryption for sensitive fields like phone numbers,
API keys, and credentials.
"""
import base64
import os
from typing import List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from django.conf import settings


def validate_encryption_key(key_b64: str) -> bytes:
    """
    Validate encryption key strength and return decoded key.
    
    Performs comprehensive validation to ensure the encryption key meets
    security requirements:
    - Must be valid base64
    - Must be exactly 32 bytes (256 bits) when decoded
    - Must have sufficient entropy (at least 16 unique bytes)
    - Must not be a weak key (all zeros, simple patterns)
    
    Args:
        key_b64: Base64-encoded encryption key string
        
    Returns:
        bytes: Decoded 32-byte encryption key
        
    Raises:
        ValueError: If key validation fails with specific reason
        
    Examples:
        >>> key = validate_encryption_key("base64_encoded_key_here")
        >>> len(key)
        32
    """
    if not key_b64:
        raise ValueError(
            "Encryption key is required. "
            "Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    
    # Decode base64
    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(
            f"Encryption key must be valid base64: {str(e)}. "
            f"Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    
    # Length check - must be exactly 32 bytes for AES-256
    if len(key) != 32:
        raise ValueError(
            f"Encryption key must be exactly 32 bytes (256 bits). "
            f"Current length: {len(key)} bytes. "
            f"Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    
    # Weak key check - all zeros (check before entropy for better error message)
    if key == b'\x00' * 32:
        raise ValueError(
            "Encryption key is all zeros (weak key). "
            "Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    
    # Weak key check - all same byte (check before entropy for better error message)
    if key == bytes([key[0]]) * 32:
        raise ValueError(
            f"Encryption key is repeating byte pattern (weak key). "
            f"Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    
    # Check for simple repeating patterns (e.g., "abababab...")
    # Check 2-byte, 4-byte, and 8-byte patterns (before entropy for better error messages)
    for pattern_len in [2, 4, 8]:
        pattern = key[:pattern_len]
        expected = pattern * (32 // pattern_len)
        if key == expected:
            raise ValueError(
                f"Encryption key is a simple {pattern_len}-byte repeating pattern (weak key). "
                f"Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
            )
    
    # Entropy check - must have at least 16 unique bytes (50% of key length)
    # This catches other weak keys that don't match the specific patterns above
    unique_bytes = len(set(key))
    if unique_bytes < 16:
        raise ValueError(
            f"Encryption key has insufficient entropy. "
            f"Found only {unique_bytes} unique bytes, need at least 16. "
            f"Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    
    return key


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.
    
    Supports key rotation by maintaining multiple keys:
    - Current key (ENCRYPTION_KEY): Used for all new encryptions
    - Old keys (ENCRYPTION_OLD_KEYS): Used for decryption only
    
    This allows seamless key rotation without data loss.
    """
    
    def __init__(self):
        """Initialize encryption service with key(s) from settings."""
        # Validate and load current encryption key
        encryption_key = settings.ENCRYPTION_KEY
        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY must be set in settings. "
                "Generate with: python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\""
            )
        
        # Validate current key
        self.key = validate_encryption_key(encryption_key)
        self.cipher = AESGCM(self.key)
        
        # Load old keys for rotation support (optional)
        self.old_keys: List[bytes] = []
        self.old_ciphers: List[AESGCM] = []
        
        old_keys_setting = getattr(settings, 'ENCRYPTION_OLD_KEYS', [])
        if old_keys_setting:
            for i, old_key_b64 in enumerate(old_keys_setting):
                try:
                    old_key = validate_encryption_key(old_key_b64)
                    self.old_keys.append(old_key)
                    self.old_ciphers.append(AESGCM(old_key))
                except ValueError as e:
                    # Log warning but don't fail - old keys are for decryption only
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Invalid old encryption key at index {i}: {e}")
    
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
        
        Supports key rotation by trying current key first, then old keys.
        This allows decryption of data encrypted with previous keys.
        
        Args:
            encrypted_data: Base64-encoded encrypted data with nonce
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If decryption fails with all available keys
        """
        if not encrypted_data:
            return encrypted_data
        
        try:
            # Decode base64
            data = base64.b64decode(encrypted_data)
            
            # Extract nonce (first 12 bytes) and ciphertext
            nonce = data[:12]
            ciphertext = data[12:]
            
            # Try current key first
            try:
                plaintext = self.cipher.decrypt(nonce, ciphertext, None)
                return plaintext.decode('utf-8')
            except Exception:
                # Current key failed, try old keys for rotation support
                for old_cipher in self.old_ciphers:
                    try:
                        plaintext = old_cipher.decrypt(nonce, ciphertext, None)
                        return plaintext.decode('utf-8')
                    except Exception:
                        continue
                
                # All keys failed
                raise ValueError("Decryption failed with all available keys")
                
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
