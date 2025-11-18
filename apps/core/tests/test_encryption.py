"""
Tests for encryption and PII masking functionality.
"""
import base64
import os
from unittest.mock import patch
from django.test import TestCase, override_settings
from apps.core.encryption import (
    EncryptionService,
    validate_encryption_key,
    mask_pii,
    mask_email,
    mask_phone,
    sanitize_for_export,
    sanitize_for_logging,
)


class KeyValidationTestCase(TestCase):
    """Test encryption key validation."""
    
    def test_validate_valid_key(self):
        """Test validation of a valid encryption key."""
        # Generate a valid 32-byte key
        key_bytes = os.urandom(32)
        key_b64 = base64.b64encode(key_bytes).decode('utf-8')
        
        # Should not raise
        validated_key = validate_encryption_key(key_b64)
        self.assertEqual(validated_key, key_bytes)
    
    def test_validate_empty_key(self):
        """Test validation rejects empty key."""
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key('')
        self.assertIn('required', str(cm.exception).lower())
    
    def test_validate_none_key(self):
        """Test validation rejects None key."""
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(None)
        self.assertIn('required', str(cm.exception).lower())
    
    def test_validate_invalid_base64(self):
        """Test validation rejects invalid base64."""
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key('not-valid-base64!!!')
        self.assertIn('base64', str(cm.exception).lower())
    
    def test_validate_wrong_length(self):
        """Test validation rejects keys that are not 32 bytes."""
        # 16 bytes (too short)
        short_key = base64.b64encode(os.urandom(16)).decode('utf-8')
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(short_key)
        self.assertIn('32 bytes', str(cm.exception))
        
        # 64 bytes (too long)
        long_key = base64.b64encode(os.urandom(64)).decode('utf-8')
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(long_key)
        self.assertIn('32 bytes', str(cm.exception))
    
    def test_validate_low_entropy(self):
        """Test validation rejects keys with low entropy."""
        # Key with only 10 unique bytes (insufficient)
        low_entropy_key = bytes([i % 10 for i in range(32)])
        key_b64 = base64.b64encode(low_entropy_key).decode('utf-8')
        
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(key_b64)
        self.assertIn('entropy', str(cm.exception).lower())
    
    def test_validate_all_zeros(self):
        """Test validation rejects all-zero key (weak key)."""
        zero_key = base64.b64encode(b'\x00' * 32).decode('utf-8')
        
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(zero_key)
        # Should explicitly detect all-zeros weak key
        self.assertIn('weak key', str(cm.exception).lower())
    
    def test_validate_repeating_byte(self):
        """Test validation rejects keys with repeating single byte (weak key)."""
        # Test with different repeating bytes
        for byte_val in [b'A', b'B', b'\xff', b'\x01']:
            repeating_key = base64.b64encode(byte_val * 32).decode('utf-8')
            
            with self.assertRaises(ValueError) as cm:
                validate_encryption_key(repeating_key)
            # Should explicitly detect repeating byte pattern
            self.assertIn('weak key', str(cm.exception).lower())
    
    def test_validate_simple_2byte_pattern(self):
        """Test validation rejects 2-byte repeating patterns (weak key)."""
        # 2-byte pattern: "ababab..."
        pattern_key = base64.b64encode(b'ab' * 16).decode('utf-8')
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(pattern_key)
        self.assertIn('weak key', str(cm.exception).lower())
        self.assertIn('2-byte', str(cm.exception))
    
    def test_validate_simple_4byte_pattern(self):
        """Test validation rejects 4-byte repeating patterns (weak key)."""
        # 4-byte pattern: "abcdabcd..."
        pattern_key = base64.b64encode(b'abcd' * 8).decode('utf-8')
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(pattern_key)
        self.assertIn('weak key', str(cm.exception).lower())
        self.assertIn('4-byte', str(cm.exception))
    
    def test_validate_simple_8byte_pattern(self):
        """Test validation rejects 8-byte repeating patterns (weak key)."""
        # 8-byte pattern: "abcdefgh..."
        pattern_key = base64.b64encode(b'abcdefgh' * 4).decode('utf-8')
        with self.assertRaises(ValueError) as cm:
            validate_encryption_key(pattern_key)
        self.assertIn('weak key', str(cm.exception).lower())
        self.assertIn('8-byte', str(cm.exception))
    
    def test_validate_complex_pattern_with_sufficient_entropy(self):
        """Test that keys with sufficient entropy but complex patterns are accepted."""
        # Create a key with 20 unique bytes (more than 16 required)
        # but not a simple repeating pattern
        key_bytes = bytes(range(20)) + bytes(range(12))  # 32 bytes total, 20 unique
        key_b64 = base64.b64encode(key_bytes).decode('utf-8')
        
        # Should be accepted (has sufficient entropy and not a simple pattern)
        validated_key = validate_encryption_key(key_b64)
        self.assertEqual(validated_key, key_bytes)


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


class KeyRotationTestCase(TestCase):
    """Test encryption key rotation functionality."""
    
    def test_decrypt_with_old_key(self):
        """Test that data encrypted with old key can still be decrypted."""
        # Generate two different keys
        old_key_bytes = os.urandom(32)
        old_key_b64 = base64.b64encode(old_key_bytes).decode('utf-8')
        
        new_key_bytes = os.urandom(32)
        new_key_b64 = base64.b64encode(new_key_bytes).decode('utf-8')
        
        # Encrypt with old key
        with override_settings(
            ENCRYPTION_KEY=old_key_b64,
            ENCRYPTION_OLD_KEYS=[]
        ):
            old_service = EncryptionService()
            plaintext = '+1234567890'
            encrypted = old_service.encrypt(plaintext)
        
        # Decrypt with new key (old key in rotation list)
        with override_settings(
            ENCRYPTION_KEY=new_key_b64,
            ENCRYPTION_OLD_KEYS=[old_key_b64]
        ):
            new_service = EncryptionService()
            decrypted = new_service.decrypt(encrypted)
            self.assertEqual(decrypted, plaintext)
    
    def test_encrypt_uses_current_key(self):
        """Test that encryption always uses current key, not old keys."""
        # Generate two different keys
        old_key_bytes = os.urandom(32)
        old_key_b64 = base64.b64encode(old_key_bytes).decode('utf-8')
        
        new_key_bytes = os.urandom(32)
        new_key_b64 = base64.b64encode(new_key_bytes).decode('utf-8')
        
        # Encrypt with new key (old key in rotation list)
        with override_settings(
            ENCRYPTION_KEY=new_key_b64,
            ENCRYPTION_OLD_KEYS=[old_key_b64]
        ):
            service = EncryptionService()
            plaintext = '+1234567890'
            encrypted = service.encrypt(plaintext)
            
            # Should be able to decrypt with current key
            decrypted = service.decrypt(encrypted)
            self.assertEqual(decrypted, plaintext)
        
        # Should NOT be decryptable with only old key
        with override_settings(
            ENCRYPTION_KEY=old_key_b64,
            ENCRYPTION_OLD_KEYS=[]
        ):
            old_service = EncryptionService()
            with self.assertRaises(ValueError):
                old_service.decrypt(encrypted)
    
    def test_multiple_old_keys(self):
        """Test decryption with multiple old keys."""
        # Generate three different keys
        oldest_key_bytes = os.urandom(32)
        oldest_key_b64 = base64.b64encode(oldest_key_bytes).decode('utf-8')
        
        old_key_bytes = os.urandom(32)
        old_key_b64 = base64.b64encode(old_key_bytes).decode('utf-8')
        
        new_key_bytes = os.urandom(32)
        new_key_b64 = base64.b64encode(new_key_bytes).decode('utf-8')
        
        # Encrypt with oldest key
        with override_settings(
            ENCRYPTION_KEY=oldest_key_b64,
            ENCRYPTION_OLD_KEYS=[]
        ):
            oldest_service = EncryptionService()
            plaintext = '+1234567890'
            encrypted = oldest_service.encrypt(plaintext)
        
        # Decrypt with new key (both old keys in rotation list)
        with override_settings(
            ENCRYPTION_KEY=new_key_b64,
            ENCRYPTION_OLD_KEYS=[old_key_b64, oldest_key_b64]
        ):
            new_service = EncryptionService()
            decrypted = new_service.decrypt(encrypted)
            self.assertEqual(decrypted, plaintext)
    
    def test_invalid_old_key_logged_but_not_fatal(self):
        """Test that invalid old keys are logged but don't prevent service initialization."""
        # Generate valid current key
        current_key_bytes = os.urandom(32)
        current_key_b64 = base64.b64encode(current_key_bytes).decode('utf-8')
        
        # Invalid old key (too short)
        invalid_old_key = base64.b64encode(b'short').decode('utf-8')
        
        # Should initialize successfully despite invalid old key
        with override_settings(
            ENCRYPTION_KEY=current_key_b64,
            ENCRYPTION_OLD_KEYS=[invalid_old_key]
        ):
            service = EncryptionService()
            
            # Should still be able to encrypt/decrypt with current key
            plaintext = '+1234567890'
            encrypted = service.encrypt(plaintext)
            decrypted = service.decrypt(encrypted)
            self.assertEqual(decrypted, plaintext)


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
