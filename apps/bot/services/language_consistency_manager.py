"""
Language Consistency Manager for maintaining consistent language throughout conversations.

This service ensures that once a language is detected in a conversation,
all subsequent bot responses maintain that language until the customer
explicitly switches.

Supports: English (en), Swahili (sw), and mixed language detection.
"""
import logging
import re
from typing import Optional, Dict, List
from django.core.cache import cache

from apps.bot.models import LanguagePreference
from apps.messaging.models import Conversation

logger = logging.getLogger(__name__)


class LanguageConsistencyManager:
    """
    Service for maintaining language consistency in conversations.
    
    Ensures that bot responses maintain the same language as the customer
    throughout the conversation, supporting requirements 6.1-6.5.
    """
    
    # Language detection patterns
    ENGLISH_INDICATORS = [
        'the', 'is', 'are', 'was', 'were', 'want', 'need', 'how', 'what',
        'can', 'please', 'thank', 'you', 'hello', 'hi', 'help', 'buy',
        'price', 'cost', 'available', 'order', 'payment'
    ]
    
    SWAHILI_INDICATORS = [
        'habari', 'mambo', 'sasa', 'vipi', 'poa', 'safi', 'nataka',
        'ninataka', 'nipe', 'naomba', 'ningependa', 'bei', 'ngapi',
        'iko', 'kuna', 'wapi', 'lini', 'nini', 'sawa', 'ndio',
        'hapana', 'asante', 'karibu', 'bidhaa', 'huduma', 'pesa',
        'malipo', 'oda', 'nunua'
    ]
    
    SHENG_INDICATORS = [
        'fiti', 'doh', 'mbao', 'munde', 'msee', 'niaje', 'cheki',
        'tuma', 'pata', 'kuja'
    ]
    
    # Cache TTL for language detection results
    CACHE_TTL = 300  # 5 minutes
    
    @classmethod
    def detect_language(cls, text: str) -> str:
        """
        Detect the primary language of a message.
        
        Analyzes the text for language indicators and returns the
        detected language code.
        
        Implements fallback handling for:
        - Empty or whitespace-only text
        - Text with no language indicators
        - Mixed language text
        
        Args:
            text: Message text to analyze
            
        Returns:
            Language code: 'en' (English), 'sw' (Swahili), or 'mixed'
            Defaults to 'en' for empty/ambiguous text
        """
        if not text or not text.strip():
            logger.debug("Empty text provided for language detection, defaulting to 'en'")
            return 'en'  # Default to English for empty messages
        
        text_lower = text.lower()
        words = text_lower.split()
        
        # Count language indicators
        english_count = sum(1 for word in words if word in cls.ENGLISH_INDICATORS)
        swahili_count = sum(1 for word in words if word in cls.SWAHILI_INDICATORS)
        sheng_count = sum(1 for word in words if word in cls.SHENG_INDICATORS)
        
        # Combine Swahili and Sheng counts (both are Swahili-based)
        swahili_total = swahili_count + sheng_count
        
        logger.debug(
            f"Language detection: EN={english_count}, SW={swahili_total} "
            f"for text: '{text[:50]}...'"
        )
        
        # Determine language based on indicator counts
        if english_count == 0 and swahili_total == 0:
            # No clear indicators - default to English
            return 'en'
        
        if english_count > 0 and swahili_total > 0:
            # Both languages present - mixed
            return 'mixed'
        
        if swahili_total > english_count:
            return 'sw'
        
        return 'en'
    
    @classmethod
    def get_conversation_language(cls, conversation: Conversation) -> str:
        """
        Get the established language for a conversation.
        
        Retrieves the language preference from the database or cache.
        If no preference exists, returns the default language.
        
        Implements fallback handling for:
        - Cache failures
        - Database errors
        - Missing preferences
        
        Args:
            conversation: Conversation instance
            
        Returns:
            Language code: 'en', 'sw', or 'mixed' (defaults to 'en' on error)
        """
        # Try cache first
        try:
            cache_key = f"conversation_language:{conversation.id}"
            cached_language = cache.get(cache_key)
            if cached_language:
                logger.debug(
                    f"Retrieved cached language '{cached_language}' "
                    f"for conversation {conversation.id}"
                )
                return cached_language
        except Exception as e:
            logger.warning(
                f"Cache error retrieving language for conversation {conversation.id}: {e}"
            )
            # Continue to database fallback
        
        # Get from database
        try:
            preference = LanguagePreference.objects.get(conversation=conversation)
            language = preference.primary_language
            
            # Validate language code
            if language not in ['en', 'sw', 'mixed']:
                logger.warning(
                    f"Invalid language code '{language}' in database, defaulting to 'en'"
                )
                language = 'en'
            
            # Cache the result
            try:
                cache.set(cache_key, language, cls.CACHE_TTL)
            except Exception as cache_error:
                logger.warning(f"Failed to cache language preference: {cache_error}")
            
            logger.debug(
                f"Retrieved language '{language}' from database "
                f"for conversation {conversation.id}"
            )
            
            return language
            
        except LanguagePreference.DoesNotExist:
            # No preference exists - return default
            logger.debug(
                f"No language preference found for conversation {conversation.id}, "
                "defaulting to 'en'"
            )
            return 'en'
        except Exception as e:
            # Database error - return default
            logger.error(
                f"Database error retrieving language for conversation {conversation.id}: {e}",
                exc_info=True
            )
            return 'en'
    
    @classmethod
    def set_conversation_language(
        cls,
        conversation: Conversation,
        language: str,
        update_usage: bool = True
    ) -> None:
        """
        Set the language preference for a conversation.
        
        Creates or updates the LanguagePreference record and updates
        the cache.
        
        Args:
            conversation: Conversation instance
            language: Language code to set ('en', 'sw', or 'mixed')
            update_usage: Whether to update usage statistics
        """
        if language not in ['en', 'sw', 'mixed']:
            logger.warning(
                f"Invalid language code '{language}', defaulting to 'en'"
            )
            language = 'en'
        
        try:
            # Get or create preference
            preference, created = LanguagePreference.objects.get_or_create(
                conversation=conversation,
                defaults={
                    'primary_language': language,
                    'language_usage': {language: 1}
                }
            )
            
            if not created:
                # Update existing preference
                preference.primary_language = language
                
                if update_usage:
                    # Update usage statistics
                    if language not in preference.language_usage:
                        preference.language_usage[language] = 0
                    preference.language_usage[language] += 1
                
                preference.save(update_fields=['primary_language', 'language_usage'])
                
                logger.info(
                    f"Updated language preference to '{language}' "
                    f"for conversation {conversation.id}"
                )
            else:
                logger.info(
                    f"Created language preference '{language}' "
                    f"for conversation {conversation.id}"
                )
            
            # Update cache
            cache_key = f"conversation_language:{conversation.id}"
            cache.set(cache_key, language, cls.CACHE_TTL)
            
        except Exception as e:
            logger.error(
                f"Failed to set language preference for conversation "
                f"{conversation.id}: {e}"
            )
    
    @classmethod
    def detect_and_update_language(
        cls,
        conversation: Conversation,
        message_text: str
    ) -> str:
        """
        Detect language from message and update conversation preference.
        
        This is a convenience method that combines detection and updating.
        It detects the language of the message and updates the conversation
        preference if needed.
        
        Args:
            conversation: Conversation instance
            message_text: Customer message text
            
        Returns:
            Detected language code
        """
        # Detect language from message
        detected_language = cls.detect_language(message_text)
        
        # Get current conversation language
        current_language = cls.get_conversation_language(conversation)
        
        # Check if language has changed
        if detected_language != current_language:
            logger.info(
                f"Language switch detected in conversation {conversation.id}: "
                f"{current_language} -> {detected_language}"
            )
            
            # Update to new language
            cls.set_conversation_language(
                conversation,
                detected_language,
                update_usage=True
            )
            
            return detected_language
        
        # Language unchanged - just update usage statistics
        cls.set_conversation_language(
            conversation,
            current_language,
            update_usage=True
        )
        
        return current_language
    
    @classmethod
    def should_maintain_language(
        cls,
        conversation: Conversation,
        new_message_text: str
    ) -> bool:
        """
        Check if the bot should maintain the current conversation language.
        
        Returns True if the new message is in the same language as the
        established conversation language, or if it's ambiguous.
        
        Args:
            conversation: Conversation instance
            new_message_text: New customer message
            
        Returns:
            True if language should be maintained, False if switched
        """
        current_language = cls.get_conversation_language(conversation)
        detected_language = cls.detect_language(new_message_text)
        
        # If detected language is the same, maintain it
        if detected_language == current_language:
            return True
        
        # If detected language is mixed, maintain current language
        # (mixed messages don't indicate a clear switch)
        if detected_language == 'mixed':
            return True
        
        # If current is mixed and detected is clear, switch to detected
        if current_language == 'mixed' and detected_language in ['en', 'sw']:
            return False
        
        # Otherwise, language has switched
        return False
    
    @classmethod
    def get_language_statistics(
        cls,
        conversation: Conversation
    ) -> Dict[str, int]:
        """
        Get language usage statistics for a conversation.
        
        Returns a dictionary with language codes as keys and usage
        counts as values.
        
        Args:
            conversation: Conversation instance
            
        Returns:
            Dictionary of language usage statistics
        """
        try:
            preference = LanguagePreference.objects.get(conversation=conversation)
            return preference.language_usage
        except LanguagePreference.DoesNotExist:
            return {}
    
    @classmethod
    def clear_language_cache(cls, conversation: Conversation) -> None:
        """
        Clear the language cache for a conversation.
        
        Useful when language preference is updated externally.
        
        Args:
            conversation: Conversation instance
        """
        cache_key = f"conversation_language:{conversation.id}"
        cache.delete(cache_key)
        logger.debug(f"Cleared language cache for conversation {conversation.id}")
    
    @classmethod
    def get_tenant_default_language(cls, tenant) -> str:
        """
        Get the default language for a tenant.
        
        Falls back to 'en' if not configured.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            Language code
        """
        # Check if tenant has a default language setting
        try:
            if hasattr(tenant, 'settings') and tenant.settings:
                default_lang = getattr(tenant.settings, 'default_language', 'en')
                return default_lang if default_lang in ['en', 'sw'] else 'en'
        except Exception as e:
            logger.debug(f"Could not get tenant default language: {e}")
        
        return 'en'
    
    @classmethod
    def initialize_conversation_language(
        cls,
        conversation: Conversation,
        tenant,
        first_message_text: Optional[str] = None
    ) -> str:
        """
        Initialize language preference for a new conversation.
        
        Uses the first message to detect language, or falls back to
        tenant default.
        
        Args:
            conversation: Conversation instance
            tenant: Tenant instance
            first_message_text: Optional first message text
            
        Returns:
            Initialized language code
        """
        if first_message_text:
            # Detect from first message
            language = cls.detect_language(first_message_text)
        else:
            # Use tenant default
            language = cls.get_tenant_default_language(tenant)
        
        # Set the language
        cls.set_conversation_language(conversation, language, update_usage=True)
        
        logger.info(
            f"Initialized conversation {conversation.id} with language '{language}'"
        )
        
        return language
