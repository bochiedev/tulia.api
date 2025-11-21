"""
Conversation Context Manager for the sales orchestration refactor.

This service manages conversation state, flow tracking, and reference resolution.

Design principles:
- Track current flow state (browsing, checkout, booking)
- Store last displayed menus for reference resolution
- Manage awaiting_response state
- Handle language detection and persistence
- Generate conversation summaries for context window management
"""
from typing import Dict, Any, Optional
from datetime import timedelta
from django.utils import timezone

from apps.messaging.models import Conversation
from apps.bot.models import ConversationContext


class ConversationContextManager:
    """
    Manage conversation context for state tracking and memory.
    
    Responsibilities:
    - Load or create context for conversations
    - Update context based on bot actions
    - Resolve menu references (numeric, positional)
    - Check menu expiration
    - Detect and persist language preferences
    - Generate conversation summaries
    """
    
    def __init__(self):
        """Initialize the conversation context manager."""
        pass
    
    def load_or_create(self, conversation: Conversation) -> ConversationContext:
        """
        Load existing context or create new one.
        
        Args:
            conversation: The conversation to load context for
        
        Returns:
            ConversationContext instance
        """
        context, created = ConversationContext.objects.get_or_create(
            conversation=conversation,
            defaults={
                'current_flow': '',
                'awaiting_response': False,
                'last_question': '',
                'last_menu': {},
                'last_menu_timestamp': None,
                'detected_language': [],
                'conversation_summary': '',
                'key_facts': [],
                'extracted_entities': {},
            }
        )
        
        if created:
            # Set default expiration (30 minutes)
            context.context_expires_at = timezone.now() + timedelta(minutes=30)
            context.save(update_fields=['context_expires_at'])
        else:
            # Extend expiration on access
            context.extend_expiration(minutes=30)
        
        return context
    
    def update_from_action(
        self,
        context: ConversationContext,
        action: Dict[str, Any]
    ) -> ConversationContext:
        """
        Update context based on bot action.
        
        Args:
            context: The context to update
            action: BotAction dict with new_context field
        
        Returns:
            Updated ConversationContext
        """
        new_context = action.get('new_context', {})
        
        if not new_context:
            return context
        
        # Update flow state
        if 'current_flow' in new_context:
            context.current_flow = new_context['current_flow']
        
        if 'awaiting_response' in new_context:
            context.awaiting_response = new_context['awaiting_response']
        
        if 'last_question' in new_context:
            context.last_question = new_context['last_question']
        
        # Update menu reference
        if 'last_menu' in new_context:
            context.last_menu = new_context['last_menu']
            context.last_menu_timestamp = timezone.now()
        
        # Update language
        if 'detected_language' in new_context:
            context.detected_language = new_context['detected_language']
        
        # Update entities
        if 'entities' in new_context:
            context.extracted_entities.update(new_context['entities'])
        
        # Update key facts
        if 'key_facts' in new_context:
            for fact in new_context['key_facts']:
                if fact not in context.key_facts:
                    context.key_facts.append(fact)
        
        # Save changes
        context.save(update_fields=[
            'current_flow',
            'awaiting_response',
            'last_question',
            'last_menu',
            'last_menu_timestamp',
            'detected_language',
            'extracted_entities',
            'key_facts',
        ])
        
        return context
    
    def resolve_menu_reference(
        self,
        context: ConversationContext,
        reference: str  # "1", "2", "first", "last"
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve numeric/positional reference to menu item.
        
        Args:
            context: The context with last_menu
            reference: The reference string (e.g., "1", "first", "last")
        
        Returns:
            Menu item dict or None if not found/expired
        """
        # Check if menu exists
        if not context.last_menu or not context.last_menu.get('items'):
            return None
        
        # Check if menu is expired
        if self.is_menu_expired(context):
            return None
        
        # Extract position
        position = self._extract_position(reference, len(context.last_menu['items']))
        if position is None:
            return None
        
        # Return item (position is 1-indexed)
        return context.last_menu['items'][position - 1]
    
    def _extract_position(self, reference: str, max_position: int) -> Optional[int]:
        """
        Extract position from reference string (1-indexed).
        
        Args:
            reference: Reference string (e.g., "1", "first", "last")
            max_position: Maximum valid position
        
        Returns:
            Position (1-indexed) or None
        """
        reference = reference.strip().lower()
        
        # Try numeric
        if reference.isdigit():
            position = int(reference)
            if 1 <= position <= max_position:
                return position
            return None
        
        # Try positional words
        positional_map = {
            'first': 1,
            'kwanza': 1,
            'ya kwanza': 1,
            'second': 2,
            'ya pili': 2,
            'third': 3,
            'ya tatu': 3,
            'fourth': 4,
            'ya nne': 4,
            'fifth': 5,
            'ya tano': 5,
            'last': max_position,
            'mwisho': max_position,
            'ya mwisho': max_position,
        }
        
        position = positional_map.get(reference)
        if position and 1 <= position <= max_position:
            return position
        
        return None
    
    def is_menu_expired(
        self,
        context: ConversationContext,
        ttl_minutes: int = 5
    ) -> bool:
        """
        Check if last_menu is still valid.
        
        Args:
            context: The context to check
            ttl_minutes: Time-to-live in minutes (default: 5)
        
        Returns:
            True if expired, False otherwise
        """
        if not context.last_menu_timestamp:
            return True
        
        expiration_time = context.last_menu_timestamp + timedelta(minutes=ttl_minutes)
        return timezone.now() > expiration_time
    
    def detect_language(self, text: str) -> list:
        """
        Detect language from text (EN/SW/Sheng/mixed).
        
        Args:
           
    text: Text to analyze
        
        Returns:
            List of detected languages (e.g., ['en'], ['sw'], ['en', 'sw'])
        """
        languages = []
        text_lower = text.lower()
        
        # English indicators
        english_words = [
            'what', 'how', 'where', 'when', 'why', 'the', 'is', 'are', 'can', 'do',
            'have', 'want', 'need', 'get', 'show', 'tell', 'help', 'please', 'thank'
        ]
        if any(word in text_lower for word in english_words):
            languages.append('en')
        
        # Swahili indicators
        swahili_words = [
            'nini', 'vipi', 'wapi', 'lini', 'kwa', 'na', 'ya', 'wa', 'ni', 'una',
            'nataka', 'ninataka', 'tafadhali', 'asante', 'habari', 'mambo'
        ]
        if any(word in text_lower for word in swahili_words):
            languages.append('sw')
        
        # Sheng indicators
        sheng_words = [
            'sasa', 'niaje', 'poa', 'fiti', 'doh', 'mboch', 'maze', 'buda',
            'dem', 'manze', 'uko', 'niko', 'tuko'
        ]
        if any(word in text_lower for word in sheng_words):
            languages.append('sheng')
        
        # Default to English if no language detected
        if not languages:
            languages = ['en']
        
        return languages
    
    def persist_language(
        self,
        context: ConversationContext,
        language: list
    ) -> ConversationContext:
        """
        Persist detected language in context.
        
        Args:
            context: The context to update
            language: List of detected languages
        
        Returns:
            Updated ConversationContext
        """
        context.detected_language = language
        context.save(update_fields=['detected_language'])
        return context
    
    def generate_summary(
        self,
        context: ConversationContext,
        max_messages: int = 10
    ) -> str:
        """
        Generate conversation summary for context window management.
        
        This is a placeholder - will be enhanced with LLM in Task 13.
        For now, returns a simple summary based on key facts and entities.
        
        Args:
            context: The context to summarize
            max_messages: Maximum number of recent messages to consider
        
        Returns:
            Summary string
        """
        summary_parts = []
        
        # Add current flow
        if context.current_flow:
            summary_parts.append(f"Current flow: {context.current_flow}")
        
        # Add key facts
        if context.key_facts:
            summary_parts.append(f"Key facts: {', '.join(context.key_facts[:5])}")
        
        # Add extracted entities
        if context.extracted_entities:
            entities_str = ', '.join([
                f"{k}: {v}" for k, v in list(context.extracted_entities.items())[:5]
            ])
            summary_parts.append(f"Entities: {entities_str}")
        
        # Add last viewed items
        if context.last_product_viewed:
            summary_parts.append(f"Last product: {context.last_product_viewed.name}")
        
        if context.last_service_viewed:
            summary_parts.append(f"Last service: {context.last_service_viewed.name}")
        
        # Add language preference
        if context.detected_language:
            summary_parts.append(f"Language: {', '.join(context.detected_language)}")
        
        return '. '.join(summary_parts) if summary_parts else "New conversation"
    
    def clear_flow_state(self, context: ConversationContext) -> ConversationContext:
        """
        Clear flow state when flow completes.
        
        Args:
            context: The context to clear
        
        Returns:
            Updated ConversationContext
        """
        context.current_flow = ''
        context.awaiting_response = False
        context.last_question = ''
        context.save(update_fields=['current_flow', 'awaiting_response', 'last_question'])
        return context
    
    def clear_menu(self, context: ConversationContext) -> ConversationContext:
        """
        Clear last_menu when it's no longer needed.
        
        Args:
            context: The context to clear
        
        Returns:
            Updated ConversationContext
        """
        context.last_menu = {}
        context.last_menu_timestamp = None
        context.save(update_fields=['last_menu', 'last_menu_timestamp'])
        return context
    
    def add_key_fact(
        self,
        context: ConversationContext,
        fact: str
    ) -> ConversationContext:
        """
        Add a key fact to remember.
        
        Args:
            context: The context to update
            fact: The fact to add
        
        Returns:
            Updated ConversationContext
        """
        if fact not in context.key_facts:
            context.key_facts.append(fact)
            context.save(update_fields=['key_facts'])
        return context
    
    def set_entity(
        self,
        context: ConversationContext,
        entity_name: str,
        value: Any
    ) -> ConversationContext:
        """
        Set an extracted entity value.
        
        Args:
            context: The context to update
            entity_name: Name of the entity
            value: Value to set
        
        Returns:
            Updated ConversationContext
        """
        context.extracted_entities[entity_name] = value
        context.save(update_fields=['extracted_entities'])
        return context
    
    def get_entity(
        self,
        context: ConversationContext,
        entity_name: str,
        default: Any = None
    ) -> Any:
        """
        Get an extracted entity value.
        
        Args:
            context: The context to read from
            entity_name: Name of the entity
            default: Default value if not found
        
        Returns:
            Entity value or default
        """
        return context.extracted_entities.get(entity_name, default)
