"""
Enhanced multi-language processor for handling English, Swahili, and Sheng.

This processor enables the bot to understand and respond naturally in:
- English (formal and casual)
- Swahili (standard Kenyan Swahili)
- Sheng (Kenyan street slang)
- Code-switching (mixed languages - very common in Kenya)

The bot can detect language patterns, understand mixed messages, and respond
in a fun, engaging way that matches the customer's vibe.
"""
import logging
import re
from typing import Dict, List, Tuple, Optional
from apps.bot.models import LanguagePreference

logger = logging.getLogger(__name__)


class MultiLanguageProcessor:
    """
    Enhanced service for processing multi-language messages with personality.
    
    Supports:
    - English (formal and casual)
    - Swahili (standard Kenyan Swahili)
    - Sheng (Kenyan street slang)
    - Code-switching (mixed languages)
    - Fun, engaging responses that match customer's energy
    """
    
    # Expanded Swahili phrases with context
    SWAHILI_PHRASES = {
        # Greetings (expanded)
        'habari': 'hello',
        'habari yako': 'how are you',
        'habari za asubuhi': 'good morning',
        'habari za jioni': 'good evening',
        'mambo': 'hello',
        'sasa': 'hello',
        'vipi': 'how are you',
        'poa': 'good',
        'safi': 'good',
        'salama': 'peace',
        'shikamoo': 'respectful greeting',
        'hujambo': 'how are you',
        'sijambo': 'i am fine',
        
        # Requests (expanded)
        'nataka': 'i want',
        'ninataka': 'i want',
        'nipe': 'give me',
        'naomba': 'i request',
        'ningependa': 'i would like',
        'naweza kupata': 'can i get',
        'nitapata': 'will i get',
        'unaweza kunipa': 'can you give me',
        'tafadhali': 'please',
        
        # Questions (expanded)
        'bei gani': 'what price',
        'ngapi': 'how much',
        'ni bei gani': 'what is the price',
        'iko': 'is it available',
        'kuna': 'is there',
        'iko wapi': 'where is it',
        'wapi': 'where',
        'lini': 'when',
        'nini': 'what',
        'kwa nini': 'why',
        'vipi': 'how',
        'je': 'question marker',
        'ama': 'or',
        
        # Responses (expanded)
        'sawa': 'okay',
        'sawa sawa': 'very okay',
        'ndio': 'yes',
        'ndiyo': 'yes',
        'hapana': 'no',
        'asante': 'thank you',
        'asante sana': 'thank you very much',
        'karibu': 'welcome',
        'karibu sana': 'very welcome',
        'pole': 'sorry',
        'pole sana': 'very sorry',
        
        # Common words (expanded)
        'bidhaa': 'product',
        'huduma': 'service',
        'bei': 'price',
        'pesa': 'money',
        'malipo': 'payment',
        'oda': 'order',
        'kununua': 'to buy',
        'nunua': 'buy',
        'uza': 'sell',
        'tuma': 'send',
        'peleka': 'deliver',
        'lete': 'bring',
        'chukua': 'take',
        'angalia': 'look',
        'tafuta': 'search',
        'pata': 'get',
        'kuja': 'come',
        'nenda': 'go',
        'rudi': 'return',
        'fanya': 'do',
        'sema': 'say',
        'jibu': 'answer',
        'uliza': 'ask',
        'jua': 'know',
        'elewa': 'understand',
        'sikia': 'hear',
        'ona': 'see',
        'soma': 'read',
        'andika': 'write',
    }
    
    # Expanded Sheng phrases (Kenyan street slang)
    SHENG_PHRASES = {
        # Greetings
        'niaje': 'hello',
        'niaje buda': 'hello friend',
        'mambo vipi': 'how are you',
        'uko poa': 'are you good',
        'sasa': 'hello',
        'sasa buda': 'hello friend',
        'vipi': 'how are you',
        
        # Status/Feelings
        'fiti': 'good',
        'poa': 'good',
        'sawa': 'okay',
        'freshi': 'fresh/good',
        'bomba': 'excellent',
        'kali': 'cool',
        'noma': 'awesome',
        'iko sawa': 'it is okay',
        'si mbaya': 'not bad',
        'poa kabisa': 'very good',
        'fiti kabisa': 'very good',
        
        # Money
        'doh': 'money',
        'mbao': 'money',
        'ganji': 'money',
        'munde': 'money',
        'ngwara': 'money',
        'chapaa': 'money',
        
        # People
        'msee': 'person',
        'mse': 'person',
        'buda': 'friend',
        'bro': 'brother',
        'siz': 'sister',
        'manze': 'friend',
        'kijanaa': 'young person',
        
        # Actions
        'cheki': 'check',
        'tuma': 'send',
        'pata': 'get',
        'kuja': 'come',
        'enda': 'go',
        'leta': 'bring',
        'chukua': 'take',
        'angalia': 'look',
        'tafuta': 'search',
        'nunua': 'buy',
        'uza': 'sell',
        
        # Expressions
        'maze': 'friend',
        'wacha': 'stop',
        'wacha mchezo': 'stop joking',
        'kwani': 'why',
        'alafu': 'then',
        'lakini': 'but',
        'sasa hivi': 'right now',
        'haraka': 'quickly',
        'pole pole': 'slowly',
        'tu': 'just',
        'pia': 'also',
        'tena': 'again',
        
        # Questions
        'ni ngapi': 'how much',
        'iko': 'is it there',
        'kuna': 'is there',
        'iko wapi': 'where is it',
        'ni nini': 'what is it',
        'ni lini': 'when is it',
    }
    
    # Fun response templates for different languages
    RESPONSE_TEMPLATES = {
        'en': {
            'greeting': ['Hey there!', 'Hello!', 'Hi!', 'Hey!'],
            'thanks': ['You\'re welcome!', 'Happy to help!', 'Anytime!', 'My pleasure!'],
            'confirmation': ['Got it!', 'Understood!', 'Perfect!', 'Awesome!'],
        },
        'sw': {
            'greeting': ['Habari!', 'Mambo!', 'Karibu!'],
            'thanks': ['Karibu sana!', 'Asante!', 'Hakuna matata!'],
            'confirmation': ['Sawa!', 'Nzuri!', 'Poa!'],
        },
        'sheng': {
            'greeting': ['Niaje!', 'Mambo vipi!', 'Sasa!', 'Vipi!'],
            'thanks': ['Poa buda!', 'Sawa msee!', 'Fiti!'],
            'confirmation': ['Sawa sawa!', 'Poa kabisa!', 'Fiti!', 'Bomba!'],
        },
        'mixed': {
            'greeting': ['Niaje! How can I help?', 'Mambo! What do you need?', 'Sasa! Vipi?'],
            'thanks': ['Asante! Happy to help!', 'Karibu sana!', 'Poa! Anytime!'],
            'confirmation': ['Sawa sawa! Got it!', 'Poa! Perfect!', 'Fiti kabisa!'],
        }
    }
    
    # Combined phrase dictionary
    PHRASE_DICT = {**SWAHILI_PHRASES, **SHENG_PHRASES}
    
    @classmethod
    def detect_languages(cls, message_text: str) -> List[str]:
        """
        Detect languages present in message with improved accuracy.
        
        Args:
            message_text: Customer message
        
        Returns:
            List of detected language codes (e.g., ['en', 'sw', 'sheng'])
        """
        text_lower = message_text.lower()
        detected = set()
        
        # Count phrase matches for each language
        swahili_count = 0
        sheng_count = 0
        
        # Check for Swahili/Sheng phrases
        for phrase in cls.PHRASE_DICT.keys():
            if phrase in text_lower:
                if phrase in cls.SWAHILI_PHRASES:
                    detected.add('sw')
                    swahili_count += 1
                if phrase in cls.SHENG_PHRASES:
                    detected.add('sheng')
                    sheng_count += 1
        
        # Check for English (if contains common English words)
        english_indicators = [
            'the', 'is', 'are', 'want', 'need', 'how', 'what', 'can', 'please',
            'would', 'like', 'get', 'buy', 'price', 'cost', 'available', 'have',
            'do', 'does', 'will', 'when', 'where', 'which', 'who', 'why'
        ]
        english_count = sum(1 for word in english_indicators if word in text_lower.split())
        if english_count > 0:
            detected.add('en')
        
        # Default to English if nothing detected
        if not detected:
            detected.add('en')
        
        # Determine primary language based on counts
        language_scores = {
            'en': english_count,
            'sw': swahili_count,
            'sheng': sheng_count
        }
        
        # Sort by score and return
        sorted_languages = sorted(
            [lang for lang in detected],
            key=lambda x: language_scores.get(x, 0),
            reverse=True
        )
        
        return sorted_languages
    
    @classmethod
    def get_language_mix_type(cls, languages: List[str]) -> str:
        """
        Determine the type of language mix.
        
        Args:
            languages: List of detected languages
            
        Returns:
            Language mix type: 'en', 'sw', 'sheng', or 'mixed'
        """
        if len(languages) == 1:
            return languages[0]
        elif 'sheng' in languages:
            return 'mixed'  # Sheng is always mixed
        elif 'sw' in languages and 'en' in languages:
            return 'mixed'
        else:
            return languages[0] if languages else 'en'
    
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
    def format_response_in_language(cls, response_text: str, target_language: str, add_personality: bool = True) -> str:
        """
        Format response in customer's preferred language with personality.
        
        This makes the bot more engaging by matching the customer's language style
        and adding fun, natural expressions.
        
        Args:
            response_text: English response text
            target_language: Target language code ('en', 'sw', 'sheng', 'mixed')
            add_personality: Whether to add personality touches
        
        Returns:
            Formatted response with appropriate language mix
        """
        if not add_personality:
            return response_text
        
        # Add language-appropriate greetings and expressions
        if target_language in ['sw', 'sheng', 'mixed']:
            # Replace formal greetings with more natural ones
            greetings_map = {
                'Hello': 'Habari' if target_language == 'sw' else 'Niaje',
                'Hi': 'Mambo' if target_language == 'sw' else 'Sasa',
                'Hey': 'Vipi' if target_language == 'sw' else 'Niaje',
                'Good morning': 'Habari za asubuhi',
                'Good evening': 'Habari za jioni',
            }
            
            for eng, local in greetings_map.items():
                if eng in response_text:
                    response_text = response_text.replace(eng, local, 1)
                    break
            
            # Replace thank you expressions
            if 'Thank you' in response_text or 'Thanks' in response_text:
                replacement = 'Asante sana' if target_language == 'sw' else 'Asante buda'
                response_text = response_text.replace('Thank you', replacement, 1)
                response_text = response_text.replace('Thanks', replacement, 1)
            
            # Replace you're welcome
            if "You're welcome" in response_text or 'Welcome' in response_text:
                replacement = 'Karibu sana' if target_language == 'sw' else 'Poa msee'
                response_text = response_text.replace("You're welcome", replacement, 1)
            
            # Add confirmations
            if response_text.startswith('Okay') or response_text.startswith('OK'):
                replacement = 'Sawa' if target_language == 'sw' else 'Poa'
                response_text = response_text.replace('Okay', replacement, 1)
                response_text = response_text.replace('OK', replacement, 1)
            
            # Add personality for Sheng/mixed
            if target_language in ['sheng', 'mixed']:
                # Add casual expressions
                if 'Great!' in response_text:
                    response_text = response_text.replace('Great!', 'Fiti kabisa!', 1)
                if 'Perfect!' in response_text:
                    response_text = response_text.replace('Perfect!', 'Bomba!', 1)
                if 'Awesome!' in response_text:
                    response_text = response_text.replace('Awesome!', 'Noma sana!', 1)
        
        return response_text
    
    @classmethod
    def add_personality_to_response(cls, response_text: str, language_mix: str, customer_energy: str = 'neutral') -> str:
        """
        Add personality and fun to bot responses based on customer's energy.
        
        Args:
            response_text: Base response text
            language_mix: Detected language mix type
            customer_energy: Customer's energy level ('casual', 'formal', 'excited', 'neutral')
            
        Returns:
            Response with added personality
        """
        import random
        
        # Don't add personality to formal customers
        if customer_energy == 'formal':
            return response_text
        
        # Add fun expressions based on language mix
        if language_mix == 'sheng' or (language_mix == 'mixed' and customer_energy == 'casual'):
            # Add casual Sheng expressions
            casual_additions = [
                ' Poa!',
                ' Fiti!',
                ' Sawa sawa!',
                ' Bomba!',
            ]
            if random.random() > 0.7:  # 30% chance
                response_text += random.choice(casual_additions)
        
        elif language_mix == 'sw':
            # Add Swahili expressions
            swahili_additions = [
                ' Asante!',
                ' Karibu!',
                ' Sawa!',
            ]
            if random.random() > 0.7:
                response_text += random.choice(swahili_additions)
        
        return response_text
    
    @classmethod
    def detect_customer_energy(cls, message_text: str) -> str:
        """
        Detect customer's energy/tone from their message.
        
        Args:
            message_text: Customer message
            
        Returns:
            Energy level: 'casual', 'formal', 'excited', 'neutral'
        """
        text_lower = message_text.lower()
        
        # Check for excited indicators
        excited_indicators = ['!', '!!', '!!!', '😊', '😃', '🔥', '💯']
        if any(indicator in message_text for indicator in excited_indicators):
            return 'excited'
        
        # Check for casual/Sheng indicators
        casual_indicators = ['niaje', 'vipi', 'msee', 'buda', 'poa', 'fiti']
        if any(indicator in text_lower for indicator in casual_indicators):
            return 'casual'
        
        # Check for formal indicators
        formal_indicators = ['please', 'kindly', 'would like', 'could you', 'may i']
        if any(indicator in text_lower for indicator in formal_indicators):
            return 'formal'
        
        return 'neutral'
    
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
