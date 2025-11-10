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
    path('v1/', include('apps.tenants.urls')),  # Includes wallet and admin endpoints
    path('v1/', include('apps.rbac.urls')),  # RBAC endpoints (memberships, roles, permissions, audit logs)
    path('v1/messages/', include('apps.messaging.urls')),
    path('v1/products/', include('apps.catalog.urls')),
    path('v1/orders/', include('apps.orders.urls')),
    path('v1/services/', include('apps.services.urls')),
    path('v1/analytics/', include('apps.analytics.urls')),
    path('v1/webhooks/', include('apps.integrations.urls')),
]
