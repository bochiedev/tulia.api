"""
Django admin configuration for messaging app.
"""
from django.contrib import admin
from .models import (
    CustomerPreferences, ConsentEvent,
    Conversation, Message, MessageTemplate, 
    ScheduledMessage, MessageCampaign
)

# Register models with default admin
admin.site.register(CustomerPreferences)
admin.site.register(ConsentEvent)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(MessageTemplate)
admin.site.register(ScheduledMessage)
admin.site.register(MessageCampaign)
