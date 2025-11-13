"""
Custom authentication backend for WabotIQ.

Provides email-based authentication compatible with Django admin.
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailAuthBackend(BaseBackend):
    """
    Authenticate using email address instead of username.
    
    This backend is compatible with Django admin and session authentication.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user by email and password.
        
        Args:
            request: HTTP request object
            username: Email address (Django admin passes email as 'username')
            password: Plain text password
            
        Returns:
            User instance if authentication succeeds, None otherwise
        """
        # Django admin passes email as 'username' parameter
        email = username or kwargs.get('email')
        
        if not email or not password:
            return None
        
        try:
            # Find user by email
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing
            # difference between existing and non-existing users
            User().set_password(password)
            return None
        
        # Check password
        if user.check_password(password):
            # Check if user is active
            if user.is_active:
                return user
        
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID.
        
        Args:
            user_id: User primary key
            
        Returns:
            User instance if found, None otherwise
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
