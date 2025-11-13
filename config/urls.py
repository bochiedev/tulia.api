"""
URL configuration for Tulia AI.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # API v1
    path('v1/', include('apps.core.urls')),
    
    # Authentication endpoints
    path('v1/auth/', include('apps.rbac.urls_auth')),  # Register, login, logout, verify-email, forgot-password, reset-password, refresh-token, me
    
    # Tenant management endpoints
    path('v1/', include('apps.tenants.urls_management')),  # Tenant CRUD and member management
    
    # Tenant settings endpoints
    path('v1/', include('apps.tenants.urls_settings')),  # Onboarding, integrations, payment methods, business settings, API keys
    
    # Tenant withdrawal endpoints (four-eyes approval)
    path('v1/', include('apps.tenants.urls_withdrawal')),  # Withdrawal management with four-eyes approval
    
    # Legacy tenant URLs (includes wallet and admin endpoints)
    path('v1/', include('apps.tenants.urls')),  # Wallet, admin, customers, payment features
    
    # RBAC endpoints
    path('v1/', include('apps.rbac.urls')),  # Memberships, roles, permissions, audit logs
    
    # Other API endpoints
    path('v1/messages/', include('apps.messaging.urls')),
    path('v1/products/', include('apps.catalog.urls')),
    path('v1/orders/', include('apps.orders.urls')),
    path('v1/services/', include('apps.services.urls')),
    path('v1/analytics/', include('apps.analytics.urls')),
    path('v1/webhooks/', include('apps.integrations.urls')),
]
