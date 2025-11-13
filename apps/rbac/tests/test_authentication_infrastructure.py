"""
Tests for authentication infrastructure (User email verification and PasswordResetToken).
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from apps.rbac.models import User, PasswordResetToken


@pytest.mark.django_db
class TestUserEmailVerification:
    """Test User model email verification fields."""
    
    def test_user_created_with_unverified_email(self):
        """Test that new users have email_verified=False by default."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        assert user.email_verified is False
        assert user.email_verification_token is None
        assert user.email_verification_sent_at is None
    
    def test_user_email_verification_fields(self):
        """Test that email verification fields can be set."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Set verification token
        user.email_verification_token = 'test-token-123'
        user.email_verification_sent_at = timezone.now()
        user.save()
        
        # Reload from database
        user.refresh_from_db()
        
        assert user.email_verification_token == 'test-token-123'
        assert user.email_verification_sent_at is not None
        assert user.email_verified is False
        
        # Mark as verified
        user.email_verified = True
        user.save()
        
        user.refresh_from_db()
        assert user.email_verified is True


@pytest.mark.django_db
class TestPasswordResetToken:
    """Test PasswordResetToken model."""
    
    def test_create_token(self):
        """Test creating a password reset token."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token = PasswordResetToken.create_token(user)
        
        assert token.user == user
        assert token.token is not None
        assert len(token.token) > 0
        assert token.expires_at > timezone.now()
        assert token.used is False
        assert token.used_at is None
    
    def test_token_expires_in_24_hours(self):
        """Test that token expires in 24 hours."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token = PasswordResetToken.create_token(user)
        
        # Token should expire approximately 24 hours from now
        expected_expiry = timezone.now() + timedelta(hours=24)
        time_diff = abs((token.expires_at - expected_expiry).total_seconds())
        
        # Allow 1 second difference for test execution time
        assert time_diff < 1
    
    def test_is_valid(self):
        """Test token validity check."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token = PasswordResetToken.create_token(user)
        
        # Fresh token should be valid
        assert token.is_valid() is True
        
        # Mark as used
        token.mark_as_used()
        
        # Used token should be invalid
        assert token.is_valid() is False
    
    def test_mark_as_used(self):
        """Test marking token as used."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token = PasswordResetToken.create_token(user)
        
        assert token.used is False
        assert token.used_at is None
        
        token.mark_as_used()
        
        assert token.used is True
        assert token.used_at is not None
    
    def test_get_valid_token(self):
        """Test retrieving a valid token."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token = PasswordResetToken.create_token(user)
        
        # Should be able to retrieve valid token
        retrieved = PasswordResetToken.objects.get_valid_token(token.token)
        assert retrieved is not None
        assert retrieved.id == token.id
        
        # Mark as used
        token.mark_as_used()
        
        # Should not retrieve used token
        retrieved = PasswordResetToken.objects.get_valid_token(token.token)
        assert retrieved is None
    
    def test_expired_token_is_invalid(self):
        """Test that expired tokens are invalid."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token = PasswordResetToken.create_token(user)
        
        # Manually set expiry to past
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save()
        
        # Token should be invalid
        assert token.is_valid() is False
        
        # Should not be retrievable as valid token
        retrieved = PasswordResetToken.objects.get_valid_token(token.token)
        assert retrieved is None
    
    def test_multiple_tokens_per_user(self):
        """Test that a user can have multiple tokens."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        token1 = PasswordResetToken.create_token(user)
        token2 = PasswordResetToken.create_token(user)
        
        assert token1.id != token2.id
        assert token1.token != token2.token
        
        # Both should be valid
        assert token1.is_valid() is True
        assert token2.is_valid() is True
        
        # User should have 2 tokens
        assert user.password_reset_tokens.count() == 2
    
    def test_token_manager_for_user(self):
        """Test getting tokens for a specific user."""
        user1 = User.objects.create_user(
            email='user1@example.com',
            password='testpass123'
        )
        user2 = User.objects.create_user(
            email='user2@example.com',
            password='testpass123'
        )
        
        token1 = PasswordResetToken.create_token(user1)
        token2 = PasswordResetToken.create_token(user2)
        
        # Each user should only see their own tokens
        user1_tokens = PasswordResetToken.objects.for_user(user1)
        assert user1_tokens.count() == 1
        assert user1_tokens.first().id == token1.id
        
        user2_tokens = PasswordResetToken.objects.for_user(user2)
        assert user2_tokens.count() == 1
        assert user2_tokens.first().id == token2.id
    
    def test_valid_tokens_manager(self):
        """Test getting only valid tokens."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create valid token
        valid_token = PasswordResetToken.create_token(user)
        
        # Create used token
        used_token = PasswordResetToken.create_token(user)
        used_token.mark_as_used()
        
        # Create expired token
        expired_token = PasswordResetToken.create_token(user)
        expired_token.expires_at = timezone.now() - timedelta(hours=1)
        expired_token.save()
        
        # Only valid token should be returned
        valid_tokens = PasswordResetToken.objects.valid_tokens()
        assert valid_tokens.count() == 1
        assert valid_tokens.first().id == valid_token.id
