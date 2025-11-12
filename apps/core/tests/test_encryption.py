"""
Tests for encryption and PII masking functionality.
"""
from django.test import TestCase
from apps.core.encryption import (
    EncryptionService,
    mask_pii,
    mask_email,
    mask_phone,
    sanitize_for_export,
    sanitize_for_logging,
)


class EncryptionServiceTestCase(TestCase):
    """Test encryption service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = EncryptionService()
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        plaintext = '+1234567890'
        
        # Encrypt
        encrypted = self.service.encrypt(plaintext)
        
        # Verify encrypted is different
        self.assertNotEqual(encrypted, plaintext)
        
        # Decrypt
        decrypted = self.service.decrypt(encrypted)
        
        # Verify decrypted matches original
        self.assertEqual(decrypted, plaintext)
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        encrypted = self.service.encrypt('')
        self.assertEqual(encrypted, '')
    
    def test_decrypt_empty_string(self):
        """Test decrypting empty string."""
        decrypted = self.service.decrypt('')
        self.assertEqual(decrypted, '')
    
    def test_encrypt_none(self):
        """Test encrypting None."""
        encrypted = self.service.encrypt(None)
        self.assertIsNone(encrypted)
    
    def test_decrypt_none(self):
        """Test decrypting None."""
        decrypted = self.service.decrypt(None)
        self.assertIsNone(decrypted)


class PIIMaskingTestCase(TestCase):
    """Test PII masking functions."""
    
    def test_mask_pii_default(self):
        """Test default PII masking."""
        result = mask_pii('+1234567890')
        self.assertEqual(result, '*******7890')
    
    def test_mask_pii_custom_visible_chars(self):
        """Test PII masking with custom visible chars."""
        result = mask_pii('+1234567890', visible_chars=2)
        self.assertEqual(result, '*********90')
    
    def test_mask_pii_short_value(self):
        """Test masking value shorter than visible chars."""
        result = mask_pii('123', visible_chars=4)
        self.assertEqual(result, '***')
    
    def test_mask_email(self):
        """Test email masking."""
        result = mask_email('user@example.com')
        self.assertEqual(result, 'u***@e******.com')
    
    def test_mask_email_short_username(self):
        """Test email masking with short username."""
        result = mask_email('a@example.com')
        self.assertEqual(result, 'a@e******.com')
    
    def test_mask_phone(self):
        """Test phone number masking."""
        result = mask_phone('+1234567890')
        self.assertEqual(result, '*******7890')
    
    def test_sanitize_for_export(self):
        """Test sanitizing data for export."""
        data = {
            'id': '123',
            'name': 'John Doe',
            'phone_e164': '+1234567890',
            'email': 'user@example.com',
            'api_key': 'secret-key-123',
        }
        
        sanitized = sanitize_for_export(data)
        
        # Non-PII fields unchanged
        self.assertEqual(sanitized['id'], '123')
        self.assertEqual(sanitized['name'], 'John Doe')
        
        # PII fields masked
        self.assertEqual(sanitized['phone_e164'], '*******7890')
        self.assertEqual(sanitized['email'], 'u***@e******.com')
        self.assertEqual(sanitized['api_key'], '**********-123')
    
    def test_sanitize_for_logging(self):
        """Test sanitizing data for logging."""
        data = {
            'id': '123',
            'phone_e164': '+1234567890',
            'email': 'user@example.com',
            'password': 'secret123',
            'api_key': 'secret-key-123',
        }
        
        sanitized = sanitize_for_logging(data)
        
        # Non-PII fields unchanged
        self.assertEqual(sanitized['id'], '123')
        
        # PII fields masked
        self.assertEqual(sanitized['phone_e164'], '*******7890')
        self.assertEqual(sanitized['email'], 'u***@e******.com')
        
        # Sensitive fields redacted
        self.assertEqual(sanitized['password'], '[REDACTED]')
        self.assertEqual(sanitized['api_key'], '[REDACTED]')
