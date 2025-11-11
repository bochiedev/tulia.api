"""
Analytics API URL configuration.

Provides endpoints for:
- Overview metrics
- Daily metrics
- Messaging analytics
- Conversion funnel
- Platform revenue (admin only)
"""
from django.urls import path
from apps.analytics import views

app_name = 'analytics'

urlpatterns = [
    # Tenant-scoped analytics endpoints
    path('overview', views.analytics_overview, name='overview'),
    path('daily', views.analytics_daily, name='daily'),
    path('messaging', views.analytics_messaging, name='messaging'),
    path('funnel', views.analytics_funnel, name='funnel'),
    
    # Admin-only platform analytics
    path('admin/revenue', views.admin_analytics_revenue, name='admin-revenue'),
]
