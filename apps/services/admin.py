"""
Django admin configuration for services app.
"""
from django.contrib import admin
from .models import Service, ServiceVariant, AvailabilityWindow, Appointment

# Register models with default admin
admin.site.register(Service)
admin.site.register(ServiceVariant)
admin.site.register(AvailabilityWindow)
admin.site.register(Appointment)
