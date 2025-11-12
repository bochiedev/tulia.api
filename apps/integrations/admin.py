"""
Django admin configuration for integrations app.
"""
from django.contrib import admin
from .models import WebhookLog

# Register model with default admin
admin.site.register(WebhookLog)
