"""
Language Detection and Consistency Service for sales orchestration refactor.

This service ensures consistent language usage throughout conversations.

Design principles:
- Detect language from customer messages (EN/SW/Sheng/mixed)
- Store detected language in ConversationContext
- Ensure all responses use consistent language
- Fallback to tenant primary language when ambiguous
- Pass language to LLM prompts
"""
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class LanguageService:
    """
    Service for language detection and consistency.
    
    Responsibilities:
    - Detect language from text (EN/SW/Sheng/mixed)
    - Store language preference in ConversationContext
    - Provide language for response formatting
    - Fallback to tenant primary language
    """
    
    # Language indicators
    ENGLISH_WORDS = [
        'what', 'how', 'where', 'when', 'why', 'the', 'is', 'are', 'can', 'do',
        'have', 'want', 'need', 'get', 'buy', 'order', 'pay', 'help', 'please'
    ]
    
    SWAHILI_WORDS = [
        'nini', 'vipi', 'wapi', 'lini', 'kwa', 'na', 'ya', 'wa', 'ni', 'una',
        'nataka', 'ninahitaji', 'nunua', 'lipa', 'saidia', 'tafadhali', 'habari'
    ]
    
    SHENG_WORDS = [
        'sasa', 'niaje', 'poa', 'fiti', 'doh', 'mboch', 'maze', 'manze',
        'uko', 'niko', 'tuko', 'vitu', 'kitu', 'mse', 'msee'
    ]
    
    def detect_language(self, text: str) -> List[str]:
        """
        Detect language from text.
        
        Args:
            text: Message text to analyze
            
        Returns:
            List of detected languages ['en'], ['sw'], ['sheng'], or ['en', 'sw']
        """
        if not text:
            return ['en']  # Default
        
        text_lower = text.lower()
        languages = []
        
        # Check for English
        english_count = sum(1 for word in self.ENGLISH_WORDS if word in text_lower)
        if english_count > 0:
            languages.append('en')
        
        # Check for Swahili
        swahili_count = sum(1 for word in self.SWAHILI_WORDS if word in text_lower)
        if swahili_count > 0:
            languages.append('sw')
        
        # Check for Sheng
        sheng_count = sum(1 for word in self.SHENG_WORDS if word in text_lower)
        if sheng_count > 0:
            languages.append('sheng')
        
        # Default to English if no language detected
        if not languages:
            languages = ['en']
        
        return languages
    
    def get_conversation_language(
        self,
        context,  # ConversationContext
        tenant,  # Tenant
        current_message_language: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get language to use for conversation.
        
        Priority:
        1. Current message language (if provided)
        2. Stored language in context
        3. Tenant primary language
        4. Default to English
        
        Args:
            context: ConversationContext instance
            tenant: Tenant instance
            current_message_language: Language detected from current message
            
        Returns:
            List of languages to use
        """
        # Use current message language if provided
        if current_message_language:
            return current_message_language
        
        # Use stored language from context
        if context.detected_language:
            return context.detected_language
        
        # Fallback to tenant primary language
        if hasattr(tenant, 'primary_language') and tenant.primary_language:
            return [tenant.primary_language]
        
        # Default to English
        return ['en']
    
    def update_context_language(
        self,
        context,  # ConversationContext
        language: List[str]
    ) -> None:
        """
        Update conversation context with detected language.
        
        Args:
            context: ConversationContext instance
            language: Detected language(s)
        """
        context.detected_language = language
        context.save(update_fields=['detected_language'])
        
        logger.debug(
            f"Updated context language for conversation {context.conversation_id}: "
            f"{language}"
        )
    
    def should_update_language(
        self,
        current_language: List[str],
        new_language: List[str]
    ) -> bool:
        """
        Determine if language should be updated.
        
        Only update if:
        - Current language is empty/default
        - New language is more specific
        - New language is consistently different
        
        Args:
            current_language: Current stored language
            new_language: Newly detected language
            
        Returns:
            True if language should be updated
        """
        # Always update if no current language
        if not current_language or current_language == ['en']:
            return True
        
        # Don't update if languages are the same
        if set(current_language) == set(new_language):
            return False
        
        # Update if new language is more specific (single language vs mixed)
        if len(new_language) == 1 and len(current_language) > 1:
            return True
        
        return False
    
    def format_for_language(
        self,
        text_variants: dict,
        language: List[str]
    ) -> str:
        """
        Select appropriate text variant for language.
        
        Args:
            text_variants: Dict with language keys ('en', 'sw', 'sheng')
            language: Target language(s)
            
        Returns:
            Text in appropriate language
        """
        # Determine primary language
        primary_lang = 'en'  # Default
        if 'sw' in language:
            primary_lang = 'sw'
        elif 'sheng' in language:
            primary_lang = 'sheng'
        
        # Return variant or fallback to English
        return text_variants.get(primary_lang, text_variants.get('en', ''))


__all__ = ['LanguageService']
