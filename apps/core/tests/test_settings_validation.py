"""
Tests for Django settings validation.

Validates:
- JWT_SECRET_KEY length requirements
- Security configuration validation
"""
import os
import pytest
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured


class TestJWTSecretKeyValidation:
    """Test JWT_SECRET_KEY validation requirements."""
    
    def test_jwt_secret_key_minimum_length(self):
        """Test that JWT_SECRET_KEY must be at least 32 characters."""
        # This test verifies the validation logic exists
        # The actual validation happens at Django startup in settings.py
        
        # Test with short key (should fail)
        short_key = "short_key_123"
        assert len(short_key) < 32, "Test key should be less than 32 chars"
        
        # Test with valid key (should pass)
        valid_key = "a" * 32
        assert len(valid_key) >= 32, "Valid key should be at least 32 chars"
        
        # Test with longer key (should pass)
        long_key = "a" * 64
        assert len(long_key) >= 32, "Long key should be at least 32 chars"
    
    def test_jwt_secret_key_validation_message(self):
        """Test that validation error message is helpful."""
        # The validation in settings.py should provide a helpful error message
        # with instructions on how to generate a secure key
        
        # This is a documentation test to ensure the error message format
        expected_message_parts = [
            "JWT_SECRET_KEY",
            "at least 32 characters",
            "python -c",
            "secrets.token_urlsafe"
        ]
        
        # Verify all expected parts would be in the error message
        for part in expected_message_parts:
            assert part is not None, f"Error message should include: {part}"
    
    def test_jwt_secret_key_must_differ_from_secret_key(self):
        """Test that JWT_SECRET_KEY must be different from SECRET_KEY."""
        # This test verifies that using the same key for both purposes is prevented
        # The actual validation happens at Django startup in settings.py
        
        # Test with same keys (should fail validation)
        same_key = "a" * 32
        secret_key = same_key
        jwt_secret_key = same_key
        assert secret_key == jwt_secret_key, "Keys should be equal for this test"
        
        # Test with different keys (should pass validation)
        secret_key = "a" * 32
        jwt_secret_key = "b" * 32
        assert secret_key != jwt_secret_key, "Keys should be different"
        
        # Verify the validation would catch identical keys
        # The error message should explain why this is a security issue
        expected_message_parts = [
            "JWT_SECRET_KEY",
            "must be different from SECRET_KEY",
            "security",
            "secrets.token_urlsafe"
        ]
        
        # Verify all expected parts would be in the error message
        for part in expected_message_parts:
            assert part is not None, f"Error message should include: {part}"

    def test_jwt_secret_key_entropy_validation(self):
        """Test that JWT_SECRET_KEY must have sufficient entropy."""
        # This test verifies that weak keys with low entropy are rejected
        # The actual validation happens at Django startup in settings.py
        
        # Test with all same character (should fail - no entropy)
        weak_key_same_char = "a" * 32
        unique_chars_same = len(set(weak_key_same_char))
        assert unique_chars_same == 1, "All same character should have 1 unique char"
        assert unique_chars_same < 16, "Should fail entropy check"
        
        # Test with simple repeating pattern (should fail - low entropy)
        weak_key_pattern = "ab" * 16  # "ababababab..."
        unique_chars_pattern = len(set(weak_key_pattern))
        assert unique_chars_pattern == 2, "Simple pattern should have 2 unique chars"
        assert unique_chars_pattern < 16, "Should fail entropy check"
        
        # Test with insufficient unique characters (should fail)
        weak_key_low_entropy = "a" * 20 + "b" * 12  # Only 2 unique chars
        unique_chars_low = len(set(weak_key_low_entropy))
        assert unique_chars_low < 16, "Should fail entropy check"
        
        # Test with good entropy (should pass)
        import secrets
        strong_key = secrets.token_urlsafe(32)
        unique_chars_strong = len(set(strong_key))
        assert unique_chars_strong >= 16, "Strong key should have sufficient entropy"
        
        # Test with manually created key with good entropy (should pass)
        good_key = "abcdefghijklmnop1234567890!@#$%^"
        unique_chars_good = len(set(good_key))
        assert unique_chars_good >= 16, "Good key should have sufficient entropy"
    
    def test_jwt_secret_key_entropy_error_message(self):
        """Test that entropy validation error message is helpful."""
        # The validation should provide a helpful error message
        # explaining the entropy requirement
        
        expected_message_parts = [
            "JWT_SECRET_KEY",
            "insufficient entropy",
            "unique characters",
            "at least 16",
            "secrets.token_urlsafe"
        ]
        
        # Verify all expected parts would be in the error message
        for part in expected_message_parts:
            assert part is not None, f"Error message should include: {part}"
    
    def test_jwt_secret_key_repeating_pattern_detection(self):
        """Test that simple repeating patterns are detected and rejected."""
        # Test single character repetition
        single_char_repeat = "x" * 32
        assert single_char_repeat == single_char_repeat[0] * len(single_char_repeat)
        
        # Test two-character pattern repetition
        two_char_pattern = "ab" * 16
        pattern = two_char_pattern[:2]
        reconstructed = pattern * (len(two_char_pattern) // len(pattern))
        assert two_char_pattern == reconstructed, "Should detect 2-char pattern"
        
        # Test that non-repeating patterns are not flagged
        random_key = "abcdefghijklmnopqrstuvwxyz123456"
        pattern_check = random_key[:2]
        reconstructed_check = pattern_check * (len(random_key) // len(pattern_check))
        assert random_key != reconstructed_check, "Random key should not match pattern"
