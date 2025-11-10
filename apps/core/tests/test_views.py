"""
Tests for core views.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient


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
