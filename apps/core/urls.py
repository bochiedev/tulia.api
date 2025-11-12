"""
Core API URLs.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.HealthCheckView.as_view(), name='health-check'),
    path('test/send-whatsapp/', views.TestSendWhatsAppView.as_view(), name='test-send-whatsapp'),
]
