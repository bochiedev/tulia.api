"""
URL configuration for monitoring and observability endpoints.
"""
from django.urls import path
from apps.bot.views.monitoring_views import (
    SystemHealthView,
    JourneyMetricsView,
    PaymentMetricsView,
    EscalationMetricsView,
    PerformanceMetricsView,
)

urlpatterns = [
    # System health and overview
    path('health/', SystemHealthView.as_view(), name='system-health'),
    
    # Journey metrics
    path('journeys/', JourneyMetricsView.as_view(), name='journey-metrics'),
    
    # Payment metrics
    path('payments/', PaymentMetricsView.as_view(), name='payment-metrics'),
    
    # Escalation metrics
    path('escalations/', EscalationMetricsView.as_view(), name='escalation-metrics'),
    
    # Performance metrics
    path('performance/', PerformanceMetricsView.as_view(), name='performance-metrics'),
]