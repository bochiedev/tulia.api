"""
Tests for Django admin authentication with custom User model.

Verifies that:
1. Custom User model works with Django admin
2. Email-based authentication works
3. Superusers can access admin
4. Non-superusers cannot access admin
5. Session authentication works correctly
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from apps.rbac.backends import EmailAuthBackend

User = get_user_model()


@pytest.mark.django_db
class TestDjangoAdminAuth:
    """Test Django admin authentication with custom User model."""
    
    def test_user_model_is_custom(self):
        """Test that AUTH_USER_MODEL is set to our custom User."""
        assert User.__module__ == 'apps.rbac.models'
        assert User.__name__ == 'User'
    
    def test_create_superuser(self):
        """Test creating a superuser using the manager."""
        user = User.objects.create_superuser(
            email='super@test.com',
            password='testpass123'
        )
        
        assert user.email == 'super@test.com'
        assert user.is_superuser is True
        assert user.is_active is True
        assert user.is_staff is True  # Should be True for superusers
        assert user.email_verified is True
        assert user.check_password('testpass123')
    
    def test_create_regular_user(self):
        """Test creating a regular user."""
        user = User.objects.create_user(
            email='user@test.com',
            password='testpass123'
        )
        
        assert user.email == 'user@test.com'
        assert user.is_superuser is False
        assert user.is_active is True
        assert user.is_staff is False  # Should be False for regular users
        assert user.check_password('testpass123')
    
    def test_email_auth_backend_success(self):
        """Test email authentication backend with valid credentials."""
        user = User.objects.create_user(
            email='auth@test.com',
            password='testpass123'
        )
        
        backend = EmailAuthBackend()
        authenticated_user = backend.authenticate(
            None,
            username='auth@test.com',  # Django admin passes email as 'username'
            password='testpass123'
        )
        
        assert authenticated_user is not None
        assert authenticated_user.email == 'auth@test.com'
    
    def test_email_auth_backend_wrong_password(self):
        """Test email authentication backend with wrong password."""
        User.objects.create_user(
            email='auth@test.com',
            password='testpass123'
        )
        
        backend = EmailAuthBackend()
        authenticated_user = backend.authenticate(
            None,
            username='auth@test.com',
            password='wrongpassword'
        )
        
        assert authenticated_user is None
    
    def test_email_auth_backend_nonexistent_user(self):
        """Test email authentication backend with non-existent user."""
        backend = EmailAuthBackend()
        authenticated_user = backend.authenticate(
            None,
            username='nonexistent@test.com',
            password='testpass123'
        )
        
        assert authenticated_user is None
    
    def test_email_auth_backend_inactive_user(self):
        """Test email authentication backend with inactive user."""
        user = User.objects.create_user(
            email='inactive@test.com',
            password='testpass123'
        )
        user.is_active = False
        user.save()
        
        backend = EmailAuthBackend()
        authenticated_user = backend.authenticate(
            None,
            username='inactive@test.com',
            password='testpass123'
        )
        
        assert authenticated_user is None
    
    def test_get_user_by_id(self):
        """Test getting user by ID (used by session authentication)."""
        user = User.objects.create_user(
            email='getuser@test.com',
            password='testpass123'
        )
        
        backend = EmailAuthBackend()
        retrieved_user = backend.get_user(user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.email == 'getuser@test.com'
    
    def test_superuser_has_all_permissions(self):
        """Test that superusers have all permissions."""
        user = User.objects.create_superuser(
            email='super@test.com',
            password='testpass123'
        )
        
        assert user.has_perm('any.permission') is True
        assert user.has_perms(['perm1', 'perm2']) is True
        assert user.has_module_perms('any_app') is True
    
    def test_regular_user_has_no_permissions(self):
        """Test that regular users have no Django admin permissions."""
        user = User.objects.create_user(
            email='user@test.com',
            password='testpass123'
        )
        
        assert user.has_perm('any.permission') is False
        assert user.has_perms(['perm1', 'perm2']) is False
        assert user.has_module_perms('any_app') is False
    
    def test_user_natural_key(self):
        """Test user natural key (email)."""
        user = User.objects.create_user(
            email='natural@test.com',
            password='testpass123'
        )
        
        assert user.natural_key() == ('natural@test.com',)
    
    def test_get_by_natural_key(self):
        """Test getting user by natural key."""
        user = User.objects.create_user(
            email='natural@test.com',
            password='testpass123'
        )
        
        retrieved_user = User.objects.get_by_natural_key('natural@test.com')
        assert retrieved_user.id == user.id
    
    def test_admin_login_page_accessible(self):
        """Test that admin login page is accessible without tenant headers."""
        client = Client()
        response = client.get('/admin/login/')
        
        # Should be accessible (200) or redirect to login (302)
        assert response.status_code in [200, 302]
    
    def test_superuser_can_access_admin(self):
        """Test that superuser can log in to Django admin."""
        user = User.objects.create_superuser(
            email='admin@test.com',
            password='testpass123'
        )
        
        client = Client()
        # Use force_login to simulate session authentication
        client.force_login(user)
        
        response = client.get('/admin/')
        
        # Should be accessible (200) or redirect to admin index (302)
        assert response.status_code in [200, 302]
        
        # If redirected, should not be to login page
        if response.status_code == 302:
            assert '/admin/login/' not in response.url
    
    def test_regular_user_cannot_access_admin(self):
        """Test that regular users cannot access Django admin."""
        user = User.objects.create_user(
            email='user@test.com',
            password='testpass123'
        )
        
        client = Client()
        client.force_login(user)
        
        response = client.get('/admin/')
        
        # Should redirect to login or show permission denied
        # Regular users don't have is_staff=True, so they can't access admin
        assert response.status_code in [302, 403]
    
    def test_password_property_alias(self):
        """Test that password property works as alias for password_hash."""
        user = User.objects.create_user(
            email='password@test.com',
            password='testpass123'
        )
        
        # password property should return password_hash
        assert user.password == user.password_hash
        
        # Setting password should update password_hash
        new_hash = 'pbkdf2_sha256$test'
        user.password = new_hash
        assert user.password_hash == new_hash
    
    def test_user_authentication_properties(self):
        """Test user authentication properties."""
        user = User.objects.create_user(
            email='props@test.com',
            password='testpass123'
        )
        
        assert user.is_authenticated is True
        assert user.is_anonymous is False
    
    def test_username_field_is_email(self):
        """Test that USERNAME_FIELD is set to email."""
        assert User.USERNAME_FIELD == 'email'
        assert User.REQUIRED_FIELDS == []


@pytest.mark.django_db
class TestAdminMiddlewareIntegration:
    """Test that admin paths work with TenantContextMiddleware."""
    
    def test_admin_bypasses_tenant_auth(self):
        """Test that /admin/ paths bypass tenant authentication."""
        client = Client()
        
        # Access admin without tenant headers
        response = client.get('/admin/login/')
        
        # Should not return 401 (tenant auth error)
        assert response.status_code != 401
        
        # Should be accessible or redirect
        assert response.status_code in [200, 302]
    
    def test_admin_preserves_request_user(self):
        """Test that admin paths preserve request.user for session auth."""
        user = User.objects.create_superuser(
            email='admin@test.com',
            password='testpass123'
        )
        
        client = Client()
        client.force_login(user)
        
        # Access admin - should work without tenant headers
        response = client.get('/admin/')
        
        # Should be accessible
        assert response.status_code in [200, 302]
        
        # If redirected, should not be to login
        if response.status_code == 302:
            assert '/admin/login/' not in response.url
    
    def test_api_still_requires_tenant_headers(self):
        """Test that API endpoints still require tenant authentication."""
        client = Client()
        
        # Try to access API without tenant headers
        response = client.get('/v1/catalog/')
        
        # Should return 401 (unauthorized)
        assert response.status_code == 401
