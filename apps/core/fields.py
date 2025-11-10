"""
Custom Django model fields for encrypted data.
"""
from django.db import models
from .encryption import get_encryption_service


class EncryptedCharField(models.CharField):
    """
    CharField that automatically encrypts/decrypts data.
    
    Data is encrypted before saving to database and decrypted when
    retrieved. Supports transparent encryption/decryption at ORM level.
    """
    
    description = "Encrypted character field"
    
    def __init__(self, *args, **kwargs):
        """Initialize encrypted field."""
        super().__init__(*args, **kwargs)
        self.encryption_service = get_encryption_service()
    
    def get_prep_value(self, value):
        """Encrypt value before saving to database."""
        if value is None or value == '':
            return value
        
        # Encrypt the value
        encrypted = self.encryption_service.encrypt(value)
        return super().get_prep_value(encrypted)
    
    def from_db_value(self, value, expression, connection):
        """Decrypt value when loading from database."""
        if value is None or value == '':
            return value
        
        # Decrypt the value
        try:
            return self.encryption_service.decrypt(value)
        except Exception:
            # If decryption fails, return None to avoid exposing encrypted data
            return None
    
    def to_python(self, value):
        """Convert value to Python type."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)


class EncryptedTextField(models.TextField):
    """
    TextField that automatically encrypts/decrypts data.
    
    Similar to EncryptedCharField but for longer text content.
    """
    
    description = "Encrypted text field"
    
    def __init__(self, *args, **kwargs):
        """Initialize encrypted field."""
        super().__init__(*args, **kwargs)
        self.encryption_service = get_encryption_service()
    
    def get_prep_value(self, value):
        """Encrypt value before saving to database."""
        if value is None or value == '':
            return value
        
        # Encrypt the value
        encrypted = self.encryption_service.encrypt(value)
        return super().get_prep_value(encrypted)
    
    def from_db_value(self, value, expression, connection):
        """Decrypt value when loading from database."""
        if value is None or value == '':
            return value
        
        # Decrypt the value
        try:
            return self.encryption_service.decrypt(value)
        except Exception:
            # If decryption fails, return None to avoid exposing encrypted data
            return None
    
    def to_python(self, value):
        """Convert value to Python type."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)
