"""
Tests for CORS validation functionality.
"""
from django.test import TestCase, RequestFactory
from apps.core.cors import TenantCORSMiddleware
from apps.tenants.models import Tenant


class TenantCORSMiddlewareTestCase(TestCase):
    """Test tenant-specific CORS validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = TenantCORSMiddleware(lambda r: None)
        
        # Create test tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            status='active',
            allowed_origins=[
                'https://example.com',
                'https://*.subdomain.com',
            ]
        )
    
    def test_no_origin_header_bypasses_validation(self):
        """Test that requests without Origin header bypass CORS validation."""
        request = self.factory.get('/v1/products')
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        # Should return None (allow request)
        self.assertIsNone(response)
    
    def test_allowed_origin_exact_match(self):
        """Test that exact match origin is allowed."""
        request = self.factory.get(
            '/v1/products',
            HTTP_ORIGIN='https://example.com'
        )
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        # Should return None (allow request)
        self.assertIsNone(response)
    
    def test_allowed_origin_wildcard_match(self):
        """Test that wildcard subdomain pattern is allowed."""
        request = self.factory.get(
            '/v1/products',
            HTTP_ORIGIN='https://app.subdomain.com'
        )
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        # Should return None (allow request)
        self.assertIsNone(response)
    
    def test_disallowed_origin_blocked(self):
        """Test that disallowed origin is blocked."""
        request = self.factory.get(
            '/v1/products',
            HTTP_ORIGIN='https://malicious.com'
        )
        request.tenant = self.tenant
        request.request_id = 'test-123'
        
        response = self.middleware.process_request(request)
        
        # Should return 403 response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
    
    def test_wildcard_allows_all_origins(self):
        """Test that wildcard in allowed_origins allows all."""
        # Update tenant to allow all origins
        self.tenant.allowed_origins = ['*']
        self.tenant.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_ORIGIN='https://any-domain.com'
        )
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        # Should return None (allow request)
        self.assertIsNone(response)
    
    def test_no_allowed_origins_blocks_all(self):
        """Test that empty allowed_origins blocks all CORS requests."""
        # Update tenant to have no allowed origins
        self.tenant.allowed_origins = []
        self.tenant.save()
        
        request = self.factory.get(
            '/v1/products',
            HTTP_ORIGIN='https://example.com'
        )
        request.tenant = self.tenant
        request.request_id = 'test-123'
        
        response = self.middleware.process_request(request)
        
        # Should return 403 response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
    
    def test_webhook_path_bypasses_cors(self):
        """Test that webhook paths bypass CORS validation."""
        request = self.factory.post(
            '/v1/webhooks/twilio',
            HTTP_ORIGIN='https://malicious.com'
        )
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        # Should return None (bypass validation)
        self.assertIsNone(response)
