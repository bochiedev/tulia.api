"""
Django admin configuration for catalog app.
"""
from django.contrib import admin
from .models import Product, ProductVariant

# Register models with default admin
admin.site.register(Product)
admin.site.register(ProductVariant)
