"""
Multi-language processor for handling English, Swahili, and Sheng.
"""
import logging
import re
from apps.bot.models import LanguagePreference

logger = logging.getLogger(__name__)


class MultiLanguageProcessor:
    """
    Service for processing multi-language messages.
    
    Supports:
    - English
    - Swahili
    - Sheng (Kenyan slang)
    - Code-switching (mixed languages)
    """
    
    # Swahili common phrases and their English translations
    SWAHILI_PHRASES = {
        # Greetings
        'habari': 'hello',
        'mambo': 'hello',
        'sasa': 'hello',
        'vipi': 'how are you',
        'poa': 'good',
        'safi': 'good',
        'salama': 'peace',
        
        # Requests
        'nataka': 'i want',
        'ninataka': 'i want',
        'nipe': 'give me',
        'naomba': 'i request',
        'ningependa': 'i would like',
        
        # Questions
        'bei gani': 'what price',
        'ngapi': 'how much',
        'iko': 'is it available',
        'kuna': 'is there',
        'wapi': 'where',
        'lini': 'when',
        'nini': 'what',
        
        # Responses
        'sawa': 'okay',
        'ndio': 'yes',
        'hapana': 'no',
        'asante': 'thank you',
        'karibu': 'welcome',
        
        # Common words
        'bidhaa': 'product',
        'huduma': 'service',
        'bei': 'price',
        'pesa': 'money',
        'malipo': 'payment',
        'oda': 'order',
        'kununua': 'to buy',
        'nunua': 'buy',
    }
    
    # Sheng phrases (Kenyan slang)
    SHENG_PHRASES = {
        'fiti': 'good',
        'poa': 'good',
        'sawa': 'okay',
        'doh': 'money',
        'mbao': 'money',
        'munde': 'person',
        'msee': 'person',
        'niaje': 'hello',
        'mambo vipi': 'how are you',
        'iko sawa': 'it is okay',
        'si mbaya': 'not bad',
        'cheki': 'check',
        'tuma': 'send',
        'pata': 'get',
        'kuja': 'come',
    }
    
    # Combined phrase dictionary
    PHRASE_DICT = {**SWAHILI_PHRASES, **SHENG_PHRASES}
    
    @classmethod
    def detect_languages(cls, message_text):
        """
        Detect languages present in message.
        
        Args:
            message_text: Customer message
        
        Returns:
            List of detected language codes
        """
        text_lower = message_text.lower()
        detected = set()
        
        # Check for Swahili/Sheng phrases
        for phrase in cls.PHRASE_DICT.keys():
            if phrase in text_lower:
                if phrase in cls.SWAHILI_PHRASES:
                    detected.add('sw')  # Swahili
                if phrase in cls.SHENG_PHRASES:
                    detected.add('sheng')
        
        # Check for English (if contains common English words)
        english_indicators = ['the', 'is', 'are', 'want', 'need', 'how', 'what', 'can', 'please']
        if any(word in text_lower.split() for word in english_indicators):
            detected.add('en')
        
        # Default to English if nothing detected
        if not detected:
            detected.add('en')
        
        return list(detected)
    
    @classmethod
    def normalize_message(cls, message_text):
        """
        Normalize mixed-language message to English.
        
        Args:
            message_text: Customer message (possibly mixed language)
        
        Returns:
            Normalized English message
        """
        normalized = message_text.lower()
        
        # Replace Swahili/Sheng phrases with English equivalents
        for phrase, translation in cls.PHRASE_DICT.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(phrase) + r'\b'
            normalized = re.sub(pattern, translation, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    @classmethod
    def translate_common_phrases(cls, phrase):
        """
        Translate common Swahili/Sheng phrase to English.
        
        Args:
            phrase: Swahili or Sheng phrase
        
        Returns:
            English translation or original phrase
        """
        phrase_lower = phrase.lower().strip()
        return cls.PHRASE_DICT.get(phrase_lower, phrase)
    
    @classmethod
    def get_customer_language_preference(cls, conversation):
        """
        Get customer's language preference.
        
        Args:
            conversation: Conversation instance
        
        Returns:
            LanguagePreference instance
        """
        try:
            return LanguagePreference.objects.get(conversation=conversation)
        except LanguagePreference.DoesNotExist:
            # Create default preference
            return LanguagePreference.objects.create(
                conversation=conversation,
                primary_language='en',
                language_usage={'en': 1},
            )
    
    @classmethod
    def format_response_in_language(cls, response_text, target_language):
        """
        Format response in customer's preferred language.
        
        Args:
            response_text: English response text
            target_language: Target language code
        
        Returns:
            Formatted response
        """
        # For now, we keep responses in English but add friendly Swahili greetings
        if target_language in ['sw', 'sheng', 'mixed']:
            # Add Swahili greeting if appropriate
            if any(greeting in response_text.lower() for greeting in ['hello', 'hi', 'hey']):
                response_text = response_text.replace('Hello', 'Habari', 1)
                response_text = response_text.replace('Hi', 'Mambo', 1)
            
            # Add Swahili closing if appropriate
            if 'thank you' in response_text.lower():
                response_text = response_text.replace('Thank you', 'Asante', 1)
        
        return response_text
    
    @classmethod
    def update_language_preference(cls, conversation, message_text):
        """
        Update language preference based on message.
        
        Args:
            conversation: Conversation instance
            message_text: Customer message
        """
        languages = cls.detect_languages(message_text)
        
        preference = cls.get_customer_language_preference(conversation)
        
        # Record usage
        for lang in languages:
            preference.record_language_usage(lang)
        
        # Update primary language if mixed usage
        if len(languages) > 1:
            preference.primary_language = 'mixed'
            preference.save(update_fields=['primary_language'])
        elif languages:
            preference.primary_language = languages[0]
            preference.save(update_fields=['primary_language'])
    
    @classmethod
    def is_swahili_or_sheng(cls, message_text):
        """
        Check if message contains Swahili or Sheng.
        
        Returns:
            bool
        """
        languages = cls.detect_languages(message_text)
        return 'sw' in languages or 'sheng' in languages
    
    @classmethod
    def extract_phrases(cls, message_text):
        """
        Extract Swahili/Sheng phrases from message.
        
        Returns:
            List of detected phrases with translations
        """
        text_lower = message_text.lower()
        found_phrases = []
        
        for phrase, translation in cls.PHRASE_DICT.items():
            if phrase in text_lower:
                found_phrases.append({
                    'original': phrase,
                    'translation': translation,
                    'language': 'sw' if phrase in cls.SWAHILI_PHRASES else 'sheng'
                })
        
        return found_phrases
