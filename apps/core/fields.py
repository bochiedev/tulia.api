"""
Custom Django model fields for encrypted data.
"""
from django.db import models
from django.db.models import Lookup
from .encryption import get_encryption_service


class EncryptedCharField(models.CharField):
    """
    CharField that automatically encrypts/decrypts data.
    
    Data is encrypted before saving to database and decrypted when
    retrieved. Supports transparent encryption/decryption at ORM level.
    
    Supports lookups by encrypting the lookup value:
    - exact: Customer.objects.filter(phone_e164='+1234567890')
    - iexact: Case-insensitive exact match
    - in: Customer.objects.filter(phone_e164__in=['+1234567890', '+0987654321'])
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
    
    def get_prep_lookup(self, lookup_type, value):
        """
        Encrypt value for lookups.
        
        Supports exact, iexact, and in lookups by encrypting the lookup value.
        """
        if lookup_type in ('exact', 'iexact'):
            if value is None or value == '':
                return value
            # Encrypt the lookup value
            return self.encryption_service.encrypt(value)
        elif lookup_type == 'in':
            # Encrypt each value in the list
            if value is None:
                return value
            return [self.encryption_service.encrypt(v) if v else v for v in value]
        else:
            # Other lookups not supported on encrypted fields
            raise ValueError(
                f"Lookup type '{lookup_type}' is not supported on encrypted fields. "
                f"Only 'exact', 'iexact', and 'in' are supported."
            )
    
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
    Supports exact and in lookups.
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
    
    def get_prep_lookup(self, lookup_type, value):
        """
        Encrypt value for lookups.
        
        Supports exact, iexact, and in lookups by encrypting the lookup value.
        """
        if lookup_type in ('exact', 'iexact'):
            if value is None or value == '':
                return value
            # Encrypt the lookup value
            return self.encryption_service.encrypt(value)
        elif lookup_type == 'in':
            # Encrypt each value in the list
            if value is None:
                return value
            return [self.encryption_service.encrypt(v) if v else v for v in value]
        else:
            # Other lookups not supported on encrypted fields
            raise ValueError(
                f"Lookup type '{lookup_type}' is not supported on encrypted fields. "
                f"Only 'exact', 'iexact', and 'in' are supported."
            )
    
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
