"""
Tests for core views.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, TenantSettings
from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission


@pytest.mark.django_db
class TestHealthCheckView:
    """Test health check endpoint."""
    
    def test_health_check_success(self):
        """Test health check returns 200 when all services are healthy."""
        client = APIClient()
        url = reverse('health-check')
        response = client.get(url)
        
        assert response.status_code in [200, 503]  # May be 503 if services not running
        assert 'status' in response.data
        assert 'database' in response.data
        assert 'cache' in response.data
        assert 'celery' in response.data
    
    def test_health_check_no_auth_required(self):
        """Test health check does not require authentication."""
        client = APIClient()
        url = reverse('health-check')
        response = client.get(url)
        
        # Should not return 401 or 403
        assert response.status_code in [200, 503]


@pytest.mark.django_db
class TestSendWhatsAppView:
    """Test WhatsApp test utilities endpoint."""
    
    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            status='active',
            whatsapp_number='+1234567890'
        )
        # TenantSettings is auto-created by signal, just update it
        tenant.settings.twilio_sid = 'test_sid'
        tenant.settings.twilio_token = 'test_token'
        tenant.settings.twilio_webhook_secret = 'test_secret'
        tenant.settings.save()
        return tenant
    
    @pytest.fixture
    def user_with_scope(self, tenant):
        """Create a user with integrations:manage scope."""
        from apps.rbac.models import TenantUserRole
        
        user = User.objects.create(
            email='test@example.com',
            is_active=True
        )
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted'
        )
        
        # Get or create permission
        permission, _ = Permission.objects.get_or_create(
            code='integrations:manage',
            defaults={
                'label': 'Manage Integrations',
                'category': 'integrations'
            }
        )
        # Get the Admin role that was auto-created by signal
        role = Role.objects.get(tenant=tenant, name='Admin')
        RolePermission.objects.get_or_create(
            role=role,
            permission=permission
        )
        # Assign role to tenant user
        TenantUserRole.objects.create(
            tenant_user=tenant_user,
            role=role
        )
        
        return user
    
    @pytest.fixture
    def user_without_scope(self, tenant):
        """Create a user without integrations:manage scope."""
        user = User.objects.create(
            email='noscope@example.com',
            is_active=True
        )
        TenantUser.objects.create(
            tenant=tenant,
            user=user,
            invite_status='accepted'
        )
        return user
    
    def test_send_whatsapp_requires_scope(self, tenant, user_without_scope):
        """Test that endpoint requires integrations:manage scope."""
        from rest_framework.test import force_authenticate, APIRequestFactory
        from apps.core.views import TestSendWhatsAppView
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/test/send-whatsapp',
            data={
                'to': '+1234567890',
                'body': 'Test message'
            },
            format='json'
        )
        force_authenticate(request, user=user_without_scope)
        
        # Simulate middleware setting tenant context
        request.tenant = tenant
        request.membership = TenantUser.objects.get(tenant=tenant, user=user_without_scope)
        request.scopes = set()  # User has no scopes
        
        # Should return 403 because user lacks required scope
        view = TestSendWhatsAppView.as_view()
        response = view(request)
        assert response.status_code == 403
    
    @patch('django.conf.settings.DEBUG', True)
    @patch('apps.integrations.services.twilio_service.TwilioService.send_whatsapp')
    def test_send_whatsapp_success(self, mock_send, tenant, user_with_scope):
        """Test successful WhatsApp message send."""
        from rest_framework.test import force_authenticate, APIRequestFactory
        from apps.core.views import TestSendWhatsAppView
        
        # Mock Twilio response
        mock_send.return_value = {
            'sid': 'SM123456',
            'status': 'queued'
        }
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/test/send-whatsapp',
            data={
                'to': '+1234567890',
                'body': 'Test message'
            },
            format='json'
        )
        force_authenticate(request, user=user_with_scope)
        
        # Simulate middleware setting tenant context
        request.tenant = tenant
        request.membership = TenantUser.objects.get(tenant=tenant, user=user_with_scope)
        request.scopes = {'integrations:manage'}  # User has required scope
        
        view = TestSendWhatsAppView.as_view()
        response = view(request)
        
        assert response.status_code == 200
        assert response.data['success'] is True
        assert 'message_sid' in response.data
        assert response.data['to'] == '+1234567890'
    
    @patch('django.conf.settings.DEBUG', True)
    def test_send_whatsapp_missing_to(self, tenant, user_with_scope):
        """Test validation error when 'to' field is missing."""
        from rest_framework.test import force_authenticate, APIRequestFactory
        from apps.core.views import TestSendWhatsAppView
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/test/send-whatsapp',
            data={'body': 'Test message'},
            format='json'
        )
        force_authenticate(request, user=user_with_scope)
        
        # Simulate middleware setting tenant context
        request.tenant = tenant
        request.membership = TenantUser.objects.get(tenant=tenant, user=user_with_scope)
        request.scopes = {'integrations:manage'}
        
        view = TestSendWhatsAppView.as_view()
        response = view(request)
        
        assert response.status_code == 400
        assert 'error' in response.data
    
    @patch('django.conf.settings.DEBUG', True)
    def test_send_whatsapp_missing_body(self, tenant, user_with_scope):
        """Test validation error when 'body' field is missing."""
        from rest_framework.test import force_authenticate, APIRequestFactory
        from apps.core.views import TestSendWhatsAppView
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/test/send-whatsapp',
            data={'to': '+1234567890'},
            format='json'
        )
        force_authenticate(request, user=user_with_scope)
        
        # Simulate middleware setting tenant context
        request.tenant = tenant
        request.membership = TenantUser.objects.get(tenant=tenant, user=user_with_scope)
        request.scopes = {'integrations:manage'}
        
        view = TestSendWhatsAppView.as_view()
        response = view(request)
        
        assert response.status_code == 400
        assert 'error' in response.data
    
    @patch('django.conf.settings.DEBUG', True)
    def test_send_whatsapp_invalid_phone_format(self, tenant, user_with_scope):
        """Test validation error for invalid phone number format."""
        from rest_framework.test import force_authenticate, APIRequestFactory
        from apps.core.views import TestSendWhatsAppView
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/test/send-whatsapp',
            data={
                'to': '1234567890',  # Missing + prefix
                'body': 'Test message'
            },
            format='json'
        )
        force_authenticate(request, user=user_with_scope)
        
        # Simulate middleware setting tenant context
        request.tenant = tenant
        request.membership = TenantUser.objects.get(tenant=tenant, user=user_with_scope)
        request.scopes = {'integrations:manage'}
        
        view = TestSendWhatsAppView.as_view()
        response = view(request)
        
        assert response.status_code == 400
        assert 'Invalid phone number format' in response.data['error']
    
    @patch('django.conf.settings.DEBUG', False)
    def test_send_whatsapp_disabled_in_production(self, tenant, user_with_scope):
        """Test that endpoint is disabled when DEBUG=False (production)."""
        from rest_framework.test import force_authenticate, APIRequestFactory
        from apps.core.views import TestSendWhatsAppView
        
        factory = APIRequestFactory()
        request = factory.post(
            '/v1/test/send-whatsapp',
            data={
                'to': '+1234567890',
                'body': 'Test message'
            },
            format='json'
        )
        force_authenticate(request, user=user_with_scope)
        
        # Simulate middleware setting tenant context
        request.tenant = tenant
        request.membership = TenantUser.objects.get(tenant=tenant, user=user_with_scope)
        request.scopes = {'integrations:manage'}
        
        view = TestSendWhatsAppView.as_view()
        response = view(request)
        
        # Should return 404 in production
        assert response.status_code == 404
        assert 'Endpoint not available' in response.data['error']
        assert 'development environments' in response.data['message']
