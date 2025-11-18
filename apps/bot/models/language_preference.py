"""
Language preference model for tracking customer language usage.
"""
from django.db import models
from apps.core.models import BaseModel


class LanguagePreference(BaseModel):
    """
    Tracks language preferences and usage patterns for customers.
    
    Supports multi-language conversations with code-switching
    between English, Swahili, and Sheng.
    """
    
    conversation = models.OneToOneField(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='language_preference'
    )
    primary_language = models.CharField(
        max_length=10,
        default='en',
        help_text="Primary language code (en, sw, mixed)"
    )
    language_usage = models.JSONField(
        default=dict,
        help_text="Usage statistics per language"
    )
    common_phrases = models.JSONField(
        default=list,
        help_text="Commonly used phrases by this customer"
    )
    
    class Meta:
        db_table = 'bot_language_preferences'
        indexes = [
            models.Index(fields=['conversation']),
        ]
    
    def __str__(self):
        return f"LanguagePreference({self.primary_language})"
    
    def record_language_usage(self, language_code):
        """Record usage of a language."""
        if language_code not in self.language_usage:
            self.language_usage[language_code] = 0
        self.language_usage[language_code] += 1
        self.save(update_fields=['language_usage'])
    
    def get_preferred_language(self):
        """Get most frequently used language."""
        if not self.language_usage:
            return self.primary_language
        
        return max(self.language_usage.items(), key=lambda x: x[1])[0]
