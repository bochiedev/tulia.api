"""
Tests for four-eyes validation security fixes.
"""
from django.test import TestCase
from apps.rbac.models import User
from apps.rbac.services import RBACService


class FourEyesValidationTests(TestCase):
    """Tests for four-eyes validation."""
    
    def setUp(self):
        """Create test users."""
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='testpass123',
            is_active=True
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='testpass123',
            is_active=True
        )
        self.inactive_user = User.objects.create_user(
            email='inactive@example.com',
            password='testpass123',
            is_active=False
        )
    
    def test_validates_different_users(self):
        """Test that validation passes for different users."""
        result = RBACService.validate_four_eyes(
            initiator_user_id=self.user1.id,
            approver_user_id=self.user2.id
        )
        self.assertTrue(result)
    
    def test_rejects_same_user(self):
        """Test that validation fails when initiator and approver are same."""
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=self.user1.id,
                approver_user_id=self.user1.id
            )
        self.assertIn('different users', str(cm.exception))
    
    def test_rejects_none_initiator(self):
        """Test that validation fails when initiator is None."""
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=None,
                approver_user_id=self.user2.id
            )
        self.assertIn('initiator_user_id is required', str(cm.exception))
    
    def test_rejects_none_approver(self):
        """Test that validation fails when approver is None."""
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=self.user1.id,
                approver_user_id=None
            )
        self.assertIn('approver_user_id is required', str(cm.exception))
    
    def test_rejects_both_none(self):
        """Test that validation fails when both are None."""
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=None,
                approver_user_id=None
            )
        self.assertIn('initiator_user_id is required', str(cm.exception))
    
    def test_rejects_nonexistent_initiator(self):
        """Test that validation fails when initiator doesn't exist."""
        import uuid
        fake_id = uuid.uuid4()
        
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=fake_id,
                approver_user_id=self.user2.id
            )
        self.assertIn('initiator user does not exist', str(cm.exception))
    
    def test_rejects_nonexistent_approver(self):
        """Test that validation fails when approver doesn't exist."""
        import uuid
        fake_id = uuid.uuid4()
        
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=self.user1.id,
                approver_user_id=fake_id
            )
        self.assertIn('approver user does not exist', str(cm.exception))
    
    def test_rejects_inactive_initiator(self):
        """Test that validation fails when initiator is inactive."""
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=self.inactive_user.id,
                approver_user_id=self.user2.id
            )
        self.assertIn('initiator user is inactive', str(cm.exception))
    
    def test_rejects_inactive_approver(self):
        """Test that validation fails when approver is inactive."""
        with self.assertRaises(ValueError) as cm:
            RBACService.validate_four_eyes(
                initiator_user_id=self.user1.id,
                approver_user_id=self.inactive_user.id
            )
        self.assertIn('approver user is inactive', str(cm.exception))
