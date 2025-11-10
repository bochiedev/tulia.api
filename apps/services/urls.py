"""
URL configuration for services app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.services.views import ServiceViewSet, AppointmentViewSet

app_name = 'services'

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'appointments', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
]
