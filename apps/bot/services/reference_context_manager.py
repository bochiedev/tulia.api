"""
Reference context manager for positional resolution.
"""
import logging
import re
import uuid
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from apps.bot.models import ReferenceContext

logger = logging.getLogger(__name__)


class ReferenceContextManager:
    """
    Manages reference contexts for positional resolution.
    
    Allows customers to refer to items by position:
    - Numeric: "1", "2", "3"
    - Ordinal: "first", "second", "third", "last"
    - Relative: "the first one", "number 2"
    """
    
    CONTEXT_EXPIRY_MINUTES = 5
    CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL
    
    # Patterns for detecting positional references
    NUMERIC_PATTERN = re.compile(r'\b(\d+)\b')
    ORDINAL_PATTERNS = {
        'first': 1,
        '1st': 1,
        'second': 2,
        '2nd': 2,
        'third': 3,
        '3rd': 3,
        'fourth': 4,
        '4th': 4,
        'fifth': 5,
        '5th': 5,
        'last': -1,
    }
    
    @classmethod
    def store_list_context(cls, conversation, list_type, items):
        """
        Store a list context for future reference.
        
        Uses Redis caching for fast retrieval with database fallback.
        
        Args:
            conversation: Conversation instance
            list_type: Type of items ('products', 'services', etc.)
            items: List of dicts with 'id', 'name', and other display info
        
        Returns:
            context_id string
        """
        context_id = str(uuid.uuid4())[:8]
        
        # Store in database
        context = ReferenceContext.objects.create(
            conversation=conversation,
            context_id=context_id,
            list_type=list_type,
            items=items,
            expires_at=timezone.now() + timedelta(minutes=cls.CONTEXT_EXPIRY_MINUTES)
        )
        
        # Cache in Redis for fast retrieval
        cache_key = f"ref_context:{conversation.id}:current"
        cache.set(cache_key, {
            'context_id': context_id,
            'list_type': list_type,
            'items': items,
            'expires_at': context.expires_at.isoformat()
        }, cls.CACHE_TTL_SECONDS)
        
        logger.info(
            f"Stored reference context {context_id} for {list_type} "
            f"({len(items)} items) in DB and cache"
        )
        
        return context_id
    
    @classmethod
    def resolve_reference(cls, conversation, message_text):
        """
        Resolve a positional or descriptive reference to an actual item.
        
        Implements fallback handling for:
        - Missing reference context
        - Expired context
        - Ambiguous references
        - Out-of-range positions
        
        Args:
            conversation: Conversation instance
            message_text: Customer message text
        
        Returns:
            dict with 'item', 'list_type', 'position' or None if no match
        """
        try:
            # Get most recent active context
            context = cls._get_current_context(conversation)
            if not context:
                logger.info(
                    f"No active reference context found for conversation {conversation.id}"
                )
                return None
        except Exception as e:
            logger.error(
                f"Error retrieving reference context for conversation {conversation.id}: {e}",
                exc_info=True
            )
            return None
        
        try:
            # Try to extract position from message
            position = cls._extract_position(message_text, len(context.items))
            
            # If no positional reference found, try descriptive matching
            if position is None:
                matched_items = cls._match_descriptive_reference(message_text, context.items)
                if matched_items:
                    # Return first match with its position (handles ambiguous references)
                    item = matched_items[0]
                    display_position = context.items.index(item) + 1
                    
                    # Log if multiple matches (ambiguous reference)
                    if len(matched_items) > 1:
                        logger.warning(
                            f"Ambiguous reference '{message_text}' matched {len(matched_items)} items, "
                            f"returning first match at position {display_position}"
                        )
                    else:
                        logger.info(
                            f"Resolved descriptive reference '{message_text}' to position {display_position} "
                            f"in {context.list_type} list"
                        )
                    
                    return {
                        'item': item,
                        'list_type': context.list_type,
                        'position': display_position,
                        'context_id': context.context_id,
                        'match_type': 'descriptive',
                        'ambiguous': len(matched_items) > 1,
                        'match_count': len(matched_items)
                    }
                
                logger.info(
                    f"No descriptive match found for '{message_text}' in {context.list_type} list"
                )
                return None
        except Exception as e:
            logger.error(
                f"Error extracting position from message '{message_text}': {e}",
                exc_info=True
            )
            return None
        
        # Get item at position
        try:
            if position == -1:  # "last"
                item = context.get_last_item()
                display_position = len(context.items)
            else:
                item = context.get_item_by_position(position)
                display_position = position
            
            if item:
                logger.info(
                    f"Resolved positional reference '{message_text}' to position {display_position} "
                    f"in {context.list_type} list"
                )
                return {
                    'item': item,
                    'list_type': context.list_type,
                    'position': display_position,
                    'context_id': context.context_id,
                    'match_type': 'positional',
                }
            else:
                logger.warning(
                    f"Position {position} out of range for {context.list_type} list "
                    f"(size: {len(context.items)})"
                )
                return None
        except Exception as e:
            logger.error(
                f"Error retrieving item at position {position}: {e}",
                exc_info=True
            )
            return None
    
    @classmethod
    def get_current_list(cls, conversation):
        """
        Get the current active list context.
        
        Returns:
            ReferenceContext instance or None
        """
        return cls._get_current_context(conversation)
    
    @classmethod
    def is_positional_reference(cls, message_text):
        """
        Check if message appears to be a positional reference.
        
        Args:
            message_text: Customer message text
        
        Returns:
            bool
        """
        text_lower = message_text.lower().strip()
        
        # Check for standalone numbers (1-5)
        if text_lower.isdigit() and 1 <= int(text_lower) <= 5:
            return True
        
        # Check for ordinal words
        for ordinal in cls.ORDINAL_PATTERNS.keys():
            if ordinal in text_lower:
                return True
        
        # Check for patterns like "number 2", "the first one"
        if re.search(r'\b(number|the)\s+(\d+|first|second|third|last)', text_lower):
            return True
        
        return False
    
    @classmethod
    def _get_current_context(cls, conversation):
        """
        Get most recent non-expired context.
        
        Checks Redis cache first, falls back to database.
        """
        # Try cache first
        cache_key = f"ref_context:{conversation.id}:current"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            # Check if cached context is still valid
            from datetime import datetime
            expires_at = datetime.fromisoformat(cached_data['expires_at'])
            if expires_at > timezone.now():
                logger.debug(f"Cache hit for reference context {conversation.id}")
                # Return a mock object with the cached data
                class CachedContext:
                    def __init__(self, data):
                        self.context_id = data['context_id']
                        self.list_type = data['list_type']
                        self.items = data['items']
                        self.expires_at = datetime.fromisoformat(data['expires_at'])
                    
                    def get_item_by_position(self, position):
                        if 1 <= position <= len(self.items):
                            return self.items[position - 1]
                        return None
                    
                    def get_first_item(self):
                        return self.items[0] if self.items else None
                    
                    def get_last_item(self):
                        return self.items[-1] if self.items else None
                
                return CachedContext(cached_data)
        
        # Cache miss - query database
        logger.debug(f"Cache miss for reference context {conversation.id}, querying DB")
        try:
            context = ReferenceContext.objects.filter(
                conversation=conversation,
                expires_at__gt=timezone.now()
            ).order_by('-created_at').first()
            
            # Update cache if found
            if context:
                cache.set(cache_key, {
                    'context_id': context.context_id,
                    'list_type': context.list_type,
                    'items': context.items,
                    'expires_at': context.expires_at.isoformat()
                }, cls.CACHE_TTL_SECONDS)
            
            return context
        except ReferenceContext.DoesNotExist:
            return None
    
    @classmethod
    def _extract_position(cls, message_text, max_items):
        """
        Extract position number from message text.
        
        Returns:
            int position (1-indexed) or None
        """
        text_lower = message_text.lower().strip()
        
        # Check for standalone number
        if text_lower.isdigit():
            pos = int(text_lower)
            if 1 <= pos <= max_items:
                return pos
            return None
        
        # Check for ordinal words
        for ordinal, pos in cls.ORDINAL_PATTERNS.items():
            if ordinal in text_lower:
                if pos == -1:  # "last"
                    return -1
                if pos <= max_items:
                    return pos
                return None
        
        # Check for numeric patterns
        match = cls.NUMERIC_PATTERN.search(text_lower)
        if match:
            pos = int(match.group(1))
            if 1 <= pos <= max_items:
                return pos
        
        return None
    
    @classmethod
    def _match_descriptive_reference(cls, message_text, items):
        """
        Match descriptive references like "the blue one", "the cheap one".
        
        Args:
            message_text: Customer message text
            items: List of item dicts
        
        Returns:
            List of matching items (may be multiple matches)
        """
        text_lower = message_text.lower()
        matches = []
        
        # Extract descriptive words (adjectives, colors, etc.)
        # Common descriptive patterns
        descriptive_words = []
        
        # Extract words that might be descriptive
        words = text_lower.split()
        for word in words:
            # Skip common filler words
            if word in ['the', 'a', 'an', 'one', 'that', 'this', 'it']:
                continue
            descriptive_words.append(word)
        
        # Match against item properties
        for item in items:
            item_text = ""
            
            # Build searchable text from item properties
            if isinstance(item, dict):
                # Get common fields
                for field in ['title', 'name', 'description', 'color', 'size', 'category']:
                    if field in item and item[field]:
                        item_text += f" {str(item[field]).lower()}"
            
            # Check if any descriptive words match
            for word in descriptive_words:
                if word in item_text:
                    matches.append(item)
                    break
        
        return matches
    
    @classmethod
    def cleanup_expired_contexts(cls):
        """Clean up expired reference contexts (background task)."""
        deleted_count, _ = ReferenceContext.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} expired reference contexts")
        
        return deleted_count
