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
