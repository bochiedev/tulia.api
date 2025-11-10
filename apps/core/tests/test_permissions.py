"""
Tests for RBAC permission classes and decorators.
"""
import pytest
from unittest.mock import Mock, MagicMock
from django.test import RequestFactory
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.core.permissions import HasTenantScopes, requires_scopes


@pytest.fixture
def request_factory():
    """Provide Django request factory."""
    return RequestFactory()


@pytest.fixture
def mock_view():
    """Provide mock view instance."""
    view = Mock(spec=APIView)
    view.__class__.__name__ = 'MockView'
    return view


@pytest.fixture
def mock_request(request_factory):
    """Provide mock request with tenant and scopes."""
    request = request_factory.get('/test')
    request.tenant = Mock()
    request.tenant.id = 'tenant-123'
    request.tenant.slug = 'test-tenant'
    request.user = Mock()
    request.user.email = 'test@example.com'
    request.request_id = 'req-123'
    request.scopes = set()
    return request


class TestHasTenantScopes:
    """Test HasTenantScopes permission class."""
    
    def test_no_required_scopes_allows_access(self, mock_request, mock_view):
        """Test that views without required_scopes allow access."""
        permission = HasTenantScopes()
        
        # View has no required_scopes attribute
        assert not hasattr(mock_view, 'required_scopes')
        
        # Should allow access
        assert permission.has_permission(mock_request, mock_view) is True
    
    def test_empty_required_scopes_allows_access(self, mock_request, mock_view):
        """Test that views with empty required_scopes allow access."""
        permission = HasTenantScopes()
        mock_view.required_scopes = set()
        
        # Should allow access
        assert permission.has_permission(mock_request, mock_view) is True
    
    def test_user_has_all_required_scopes(self, mock_request, mock_view):
        """Test that user with all required scopes is granted access."""
        permission = HasTenantScopes()
        
        # Set required scopes on view
        mock_view.required_scopes = {'catalog:view', 'catalog:edit'}
        
        # Set user scopes on request
        mock_request.scopes = {'catalog:view', 'catalog:edit', 'orders:view'}
        
        # Should allow access
        assert permission.has_permission(mock_request, mock_view) is True
    
    def test_user_missing_one_scope(self, mock_request, mock_view):
        """Test that user missing one required scope is denied access."""
        permission = HasTenantScopes()
        
        # Set required scopes on view
        mock_view.required_scopes = {'catalog:view', 'catalog:edit'}
        
        # User only has one of the required scopes
        mock_request.scopes = {'catalog:view'}
        
        # Should deny access
        assert permission.has_permission(mock_request, mock_view) is False
    
    def test_user_missing_all_scopes(self, mock_request, mock_view):
        """Test that user with no required scopes is denied access."""
        permission = HasTenantScopes()
        
        # Set required scopes on view
        mock_view.required_scopes = {'catalog:view', 'catalog:edit'}
        
        # User has no scopes
        mock_request.scopes = set()
        
        # Should deny access
        assert permission.has_permission(mock_request, mock_view) is False
    
    def test_user_has_different_scopes(self, mock_request, mock_view):
        """Test that user with different scopes is denied access."""
        permission = HasTenantScopes()
        
        # Set required scopes on view
        mock_view.required_scopes = {'catalog:view', 'catalog:edit'}
        
        # User has different scopes
        mock_request.scopes = {'orders:view', 'analytics:view'}
        
        # Should deny access
        assert permission.has_permission(mock_request, mock_view) is False
    
    def test_required_scopes_as_string(self, mock_request, mock_view):
        """Test that required_scopes can be a single string."""
        permission = HasTenantScopes()
        
        # Set required scope as string
        mock_view.required_scopes = 'catalog:view'
        
        # User has the scope
        mock_request.scopes = {'catalog:view'}
        
        # Should allow access
        assert permission.has_permission(mock_request, mock_view) is True
    
    def test_required_scopes_as_list(self, mock_request, mock_view):
        """Test that required_scopes can be a list."""
        permission = HasTenantScopes()
        
        # Set required scopes as list
        mock_view.required_scopes = ['catalog:view', 'catalog:edit']
        
        # User has the scopes
        mock_request.scopes = {'catalog:view', 'catalog:edit'}
        
        # Should allow access
        assert permission.has_permission(mock_request, mock_view) is True
    
    def test_required_scopes_as_tuple(self, mock_request, mock_view):
        """Test that required_scopes can be a tuple."""
        permission = HasTenantScopes()
        
        # Set required scopes as tuple
        mock_view.required_scopes = ('catalog:view', 'catalog:edit')
        
        # User has the scopes
        mock_request.scopes = {'catalog:view', 'catalog:edit'}
        
        # Should allow access
        assert permission.has_permission(mock_request, mock_view) is True
    
    def test_request_without_scopes_attribute(self, request_factory, mock_view):
        """Test that request without scopes attribute is denied access."""
        permission = HasTenantScopes()
        
        # Create request without scopes attribute
        request = request_factory.get('/test')
        request.tenant = Mock()
        request.user = Mock()
        # No scopes attribute
        
        # Set required scopes on view
        mock_view.required_scopes = {'catalog:view'}
        
        # Should deny access (missing scopes treated as empty set)
        assert permission.has_permission(request, mock_view) is False


class TestHasTenantScopesObjectPermission:
    """Test HasTenantScopes object-level permission checking."""
    
    def test_object_belongs_to_request_tenant(self, mock_request, mock_view):
        """Test that object belonging to request tenant is allowed."""
        permission = HasTenantScopes()
        
        # Create mock object with tenant
        obj = Mock()
        obj.tenant = Mock()
        obj.tenant.id = 'tenant-123'
        obj.id = 'obj-123'
        obj.__class__.__name__ = 'Product'
        
        # Request tenant matches object tenant
        mock_request.tenant.id = 'tenant-123'
        
        # Should allow access
        assert permission.has_object_permission(mock_request, mock_view, obj) is True
    
    def test_object_belongs_to_different_tenant(self, mock_request, mock_view):
        """Test that object belonging to different tenant is denied."""
        permission = HasTenantScopes()
        
        # Create mock object with different tenant
        obj = Mock()
        obj.tenant = Mock()
        obj.tenant.id = 'tenant-456'
        obj.id = 'obj-123'
        obj.__class__.__name__ = 'Product'
        
        # Request tenant is different
        mock_request.tenant.id = 'tenant-123'
        
        # Should deny access
        assert permission.has_object_permission(mock_request, mock_view, obj) is False
    
    def test_object_without_tenant_attribute(self, mock_request, mock_view):
        """Test that object without tenant attribute is allowed (scope check passed)."""
        permission = HasTenantScopes()
        
        # Create mock object without tenant attribute
        obj = Mock(spec=['id', '__class__'])
        obj.id = 'obj-123'
        obj.__class__.__name__ = 'SomeModel'
        
        # Should allow access (can't verify tenant, but scope check already passed)
        assert permission.has_object_permission(mock_request, mock_view, obj) is True
    
    def test_request_without_tenant(self, request_factory, mock_view):
        """Test that request without tenant is denied object access."""
        permission = HasTenantScopes()
        
        # Create request without tenant
        request = request_factory.get('/test')
        # No tenant attribute
        
        # Create mock object
        obj = Mock()
        obj.tenant = Mock()
        obj.tenant.id = 'tenant-123'
        
        # Should deny access
        assert permission.has_object_permission(request, mock_view, obj) is False
    
    def test_object_tenant_as_id_string(self, mock_request, mock_view):
        """Test that object tenant can be an ID string instead of object."""
        permission = HasTenantScopes()
        
        # Create mock object with tenant as ID
        obj = Mock()
        obj.tenant = 'tenant-123'  # Direct ID instead of object
        obj.id = 'obj-123'
        obj.__class__.__name__ = 'Product'
        
        # Request tenant as object
        mock_request.tenant.id = 'tenant-123'
        
        # Should allow access
        assert permission.has_object_permission(mock_request, mock_view, obj) is True


class TestRequiresScopesDecorator:
    """Test @requires_scopes decorator."""
    
    def test_decorator_on_class(self):
        """Test that decorator sets required_scopes on class."""
        @requires_scopes('catalog:view', 'catalog:edit')
        class TestView(APIView):
            pass
        
        # Should set required_scopes attribute
        assert hasattr(TestView, 'required_scopes')
        assert TestView.required_scopes == {'catalog:view', 'catalog:edit'}
    
    def test_decorator_on_method(self):
        """Test that decorator sets required_scopes on method."""
        class TestView(APIView):
            @requires_scopes('catalog:view')
            def get(self, request):
                return Response({'status': 'ok'})
        
        # Should set required_scopes on method
        assert hasattr(TestView.get, 'required_scopes')
        assert TestView.get.required_scopes == {'catalog:view'}
    
    def test_decorator_with_single_scope(self):
        """Test that decorator works with single scope."""
        @requires_scopes('catalog:view')
        class TestView(APIView):
            pass
        
        assert TestView.required_scopes == {'catalog:view'}
    
    def test_decorator_with_multiple_scopes(self):
        """Test that decorator works with multiple scopes."""
        @requires_scopes('catalog:view', 'catalog:edit', 'orders:view')
        class TestView(APIView):
            pass
        
        assert TestView.required_scopes == {'catalog:view', 'catalog:edit', 'orders:view'}
    
    def test_decorator_preserves_method_functionality(self):
        """Test that decorator preserves original method functionality."""
        class TestView(APIView):
            @requires_scopes('catalog:view')
            def get(self, request):
                return Response({'status': 'ok', 'data': 'test'})
        
        # Create instance and call method
        view = TestView()
        mock_request = Mock()
        response = view.get(mock_request)
        
        # Should return original response
        assert response.data == {'status': 'ok', 'data': 'test'}
    
    def test_decorator_on_method_sets_instance_attribute(self):
        """Test that method decorator sets required_scopes on view instance."""
        class TestView(APIView):
            @requires_scopes('catalog:view')
            def get(self, request):
                # Check that required_scopes is set on self
                return Response({'scopes': list(self.required_scopes)})
        
        # Create instance and call method
        view = TestView()
        mock_request = Mock()
        response = view.get(mock_request)
        
        # Should have set required_scopes on instance
        assert hasattr(view, 'required_scopes')
        assert view.required_scopes == {'catalog:view'}
        assert response.data == {'scopes': ['catalog:view']}
    
    def test_different_scopes_on_different_methods(self):
        """Test that different methods can have different scope requirements."""
        class TestView(APIView):
            @requires_scopes('catalog:view')
            def get(self, request):
                return Response({'method': 'get'})
            
            @requires_scopes('catalog:edit')
            def post(self, request):
                return Response({'method': 'post'})
        
        # Check that methods have different scopes
        assert TestView.get.required_scopes == {'catalog:view'}
        assert TestView.post.required_scopes == {'catalog:edit'}


class TestIntegration:
    """Integration tests for permission class and decorator together."""
    
    def test_decorator_and_permission_class_integration(self, mock_request):
        """Test that decorator and permission class work together."""
        @requires_scopes('catalog:view', 'catalog:edit')
        class TestView(APIView):
            permission_classes = [HasTenantScopes]
            
            def get(self, request):
                return Response({'status': 'ok'})
        
        # Create view instance
        view = TestView()
        
        # Create permission instance
        permission = HasTenantScopes()
        
        # User has required scopes
        mock_request.scopes = {'catalog:view', 'catalog:edit'}
        
        # Should allow access
        assert permission.has_permission(mock_request, view) is True
        
        # User missing one scope
        mock_request.scopes = {'catalog:view'}
        
        # Should deny access
        assert permission.has_permission(mock_request, view) is False
    
    def test_method_decorator_with_permission_class(self, mock_request):
        """Test that method-level decorator works with permission class."""
        class TestView(APIView):
            permission_classes = [HasTenantScopes]
            
            @requires_scopes('catalog:view')
            def get(self, request):
                return Response({'method': 'get'})
            
            @requires_scopes('catalog:edit')
            def post(self, request):
                return Response({'method': 'post'})
        
        # Create view instance
        view = TestView()
        permission = HasTenantScopes()
        
        # Simulate GET request
        mock_request.scopes = {'catalog:view'}
        view.get(mock_request)  # This sets required_scopes on view instance
        
        # Should allow GET with catalog:view
        assert permission.has_permission(mock_request, view) is True
        
        # Simulate POST request
        mock_request.scopes = {'catalog:view'}  # Missing catalog:edit
        view.post(mock_request)  # This updates required_scopes on view instance
        
        # Should deny POST without catalog:edit
        assert permission.has_permission(mock_request, view) is False
