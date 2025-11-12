"""
Django admin configuration for bot app.
"""
from django.contrib import admin


# Note: This app doesn't have models, only services for intent classification
# and bot handlers. If you add models for intent logs or bot analytics,
# register them here

# Example placeholder for future bot models:
# @admin.register(IntentLog)
# class IntentLogAdmin(admin.ModelAdmin):
#     list_display = ['tenant', 'customer', 'intent', 'confidence', 'created_at']
#     list_filter = ['intent', 'created_at']
#     search_fields = ['customer__phone_e164', 'message_text']
