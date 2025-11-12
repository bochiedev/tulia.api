"""
Django admin configuration for orders app.
"""
from django.contrib import admin
from .models import Order, Cart

# Register models with default admin
admin.site.register(Order)
admin.site.register(Cart)
