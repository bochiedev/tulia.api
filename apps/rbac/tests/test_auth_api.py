"""
Tests for authentication API endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.rbac.models import User, PasswordResetToken
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestRegistrationEndpoint:
    """Test POST /v1/auth/register endpoint."""
    
    def test_register_user_success(self):
        """Test successful user registration."""
        client = APIClient()
        
        data = {
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'business_name': 'Acme Corp'
        }
        
        response = client.post('/v1/auth/register', data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'user' in response.data
        assert 'tenant' in response.data
        assert 'token' in response.data
        assert response.data['user']['email'] == 'newuser@example.com'
        assert response.data['tenant']['name'] == 'Acme Corp'
        
        # Verify user was created
        user = User.objects.get(email='newuser@example.com')
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'
        assert user.email_verified is False
        
        # Verify tenant was created
        tenant = Tenant.objects.get(slug='acme-corp')
        assert tenant.name == 'Acme Corp'
        assert tenant.status == 'trial'
    
    def test_register_duplicate_email(self):
        """Test registration with existing email fails."""
        # Create existing user
        User.objects.create_user(
            email='existing@example.com',
            password='testpass123'
        )
        
        client = APIClient()
        data = {
            'email': 'existing@example.com',
            'password': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'business_name': 'Test Corp'
        }
        
        response = client.post('/v1/auth/register', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    def test_register_weak_password(self):
        """Test registration with weak password fails."""
        client = APIClient()
        data = {
            'email': 'newuser@example.com',
            'password': '123',  # Too weak
            'first_name': 'John',
            'last_name': 'Doe',
            'business_name': 'Test Corp'
        }
        
        response = client.post('/v1/auth/register', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLoginEndpoint:
    """Test POST /v1/auth/login endpoint."""
    
    def test_login_success(self):
        """Test successful login."""
        # Create user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        client = APIClient()
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = client.post('/v1/auth/login', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'user' in response.data
        assert 'token' in response.data
        assert response.data['user']['email'] == 'test@example.com'
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        # Create user
        User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        client = APIClient()
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = client.post('/v1/auth/login', data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
    
    def test_login_nonexistent_user(self):
        """Test login with non-existent user."""
        client = APIClient()
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpass123'
        }
        
        response = client.post('/v1/auth/login', data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestEmailVerificationEndpoint:
    """Test POST /v1/auth/verify-email endpoint."""
    
    def test_verify_email_success(self):
        """Test successful email verification."""
        # Create user with verification token
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user.email_verification_token = 'test-token-123'
        user.email_verified = False
        user.save()
        
        client = APIClient()
        data = {
            'token': 'test-token-123'
        }
        
        response = client.post('/v1/auth/verify-email', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify user email is now verified
        user.refresh_from_db()
        assert user.email_verified is True
    
    def test_verify_email_invalid_token(self):
        """Test email verification with invalid token."""
        client = APIClient()
        data = {
            'token': 'invalid-token'
        }
        
        response = client.post('/v1/auth/verify-email', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPasswordResetEndpoints:
    """Test password reset endpoints."""
    
    def test_forgot_password_success(self):
        """Test requesting password reset."""
        # Create user
        User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        client = APIClient()
        data = {
            'email': 'test@example.com'
        }
        
        response = client.post('/v1/auth/forgot-password', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify token was created
        assert PasswordResetToken.objects.filter(user__email='test@example.com').exists()
    
    def test_forgot_password_nonexistent_user(self):
        """Test requesting password reset for non-existent user."""
        client = APIClient()
        data = {
            'email': 'nonexistent@example.com'
        }
        
        response = client.post('/v1/auth/forgot-password', data, format='json')
        
        # Should still return success to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK
    
    def test_reset_password_success(self):
        """Test resetting password with valid token."""
        # Create user and reset token
        user = User.objects.create_user(
            email='test@example.com',
            password='oldpass123'
        )
        reset_token = PasswordResetToken.create_token(user)
        
        client = APIClient()
        data = {
            'token': reset_token.token,
            'new_password': 'NewSecurePass123!'
        }
        
        response = client.post('/v1/auth/reset-password', data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify password was changed
        user.refresh_from_db()
        assert user.check_password('NewSecurePass123!')
        
        # Verify token was marked as used
        reset_token.refresh_from_db()
        assert reset_token.used is True
    
    def test_reset_password_invalid_token(self):
        """Test resetting password with invalid token."""
        client = APIClient()
        data = {
            'token': 'invalid-token',
            'new_password': 'NewSecurePass123!'
        }
        
        response = client.post('/v1/auth/reset-password', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserProfileEndpoints:
    """Test user profile endpoints."""
    
    def test_get_profile_authenticated(self):
        """Test getting user profile when authenticated."""
        from apps.rbac.services import AuthService
        
        # Create user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Generate JWT token
        token = AuthService.generate_jwt(user)
        
        client = APIClient()
        response = client.get(
            '/v1/auth/me',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == 'test@example.com'
        assert response.data['first_name'] == 'Test'
        assert response.data['last_name'] == 'User'
        assert response.data['full_name'] == 'Test User'
        assert 'tenants' in response.data
        assert 'total_tenants' in response.data
        assert 'pending_invites' in response.data
        assert isinstance(response.data['tenants'], list)
        assert isinstance(response.data['pending_invites'], list)
    
    def test_get_profile_with_tenants(self):
        """Test getting user profile with tenant memberships."""
        from apps.tenants.models import Tenant
        from apps.rbac.models import TenantUser, Role, TenantUserRole
        from apps.rbac.services import AuthService
        
        # Create user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create tenant
        tenant = Tenant.objects.create(
            name='Test Corp',
            slug='test-corp',
            status='active'
        )
        
        # Create membership
        membership = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            is_active=True,
            invite_status='accepted'
        )
        
        # Get existing Owner role (created by signal)
        role = Role.objects.get(tenant=tenant, name='Owner')
        
        # Assign role
        TenantUserRole.objects.create(
            tenant_user=membership,
            role=role,
            assigned_by=user
        )
        
        # Generate JWT token
        token = AuthService.generate_jwt(user)
        
        client = APIClient()
        response = client.get(
            '/v1/auth/me',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_tenants'] == 1
        assert len(response.data['tenants']) == 1
        
        tenant_data = response.data['tenants'][0]
        assert tenant_data['tenant']['id'] == str(tenant.id)
        assert tenant_data['tenant']['name'] == 'Test Corp'
        assert tenant_data['tenant']['slug'] == 'test-corp'
        assert tenant_data['tenant']['status'] == 'active'
        assert len(tenant_data['roles']) == 1
        assert tenant_data['roles'][0]['name'] == 'Owner'
        assert isinstance(tenant_data['scopes'], list)
        assert 'membership_id' in tenant_data
        assert 'joined_at' in tenant_data
    
    def test_get_profile_with_pending_invites(self):
        """Test getting user profile with pending invitations."""
        from apps.tenants.models import Tenant
        from apps.rbac.models import TenantUser
        from apps.rbac.services import AuthService
        
        # Create users
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        inviter = User.objects.create_user(
            email='inviter@example.com',
            password='testpass123',
            first_name='Inviter',
            last_name='User'
        )
        
        # Create tenant
        tenant = Tenant.objects.create(
            name='Test Corp',
            slug='test-corp',
            status='active'
        )
        
        # Create pending invitation
        TenantUser.objects.create(
            tenant=tenant,
            user=user,
            is_active=True,
            invite_status='pending',
            invited_by=inviter
        )
        
        # Generate JWT token
        token = AuthService.generate_jwt(user)
        
        client = APIClient()
        response = client.get(
            '/v1/auth/me',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_tenants'] == 0  # Pending invites don't count
        assert len(response.data['pending_invites']) == 1
        
        invite_data = response.data['pending_invites'][0]
        assert invite_data['tenant']['id'] == str(tenant.id)
        assert invite_data['tenant']['name'] == 'Test Corp'
        assert invite_data['invited_by']['email'] == 'inviter@example.com'
        assert invite_data['invited_by']['name'] == 'Inviter User'
    
    def test_get_profile_unauthenticated(self):
        """Test getting user profile when not authenticated."""
        client = APIClient()
        
        response = client.get('/v1/auth/me')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_profile_success(self):
        """Test updating user profile."""
        from apps.rbac.services import AuthService
        
        # Create user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Old',
            last_name='Name'
        )
        
        # Generate JWT token
        token = AuthService.generate_jwt(user)
        
        client = APIClient()
        data = {
            'first_name': 'New',
            'last_name': 'Name',
            'phone': '+1234567890'
        }
        
        response = client.put(
            '/v1/auth/me',
            data,
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'New'
        assert response.data['last_name'] == 'Name'
        
        # Verify changes were saved
        user.refresh_from_db()
        assert user.first_name == 'New'
        assert user.last_name == 'Name'
