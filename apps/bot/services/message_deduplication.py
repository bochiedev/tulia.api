"""
Message Deduplication Service for AI Agent.

Provides request deduplication using distributed locks to prevent
concurrent processing of the same message across multiple workers.
"""
import logging
import hashlib
from typing import Optional, Callable, Any
from contextlib import contextmanager
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class MessageDeduplicationService:
    """
    Service for preventing duplicate message processing.
    
    Uses Redis distributed locks to ensure that only one worker
    processes a given message at a time. Implements:
    - Distributed locking with timeout
    - Message fingerprinting for duplicate detection
    - Processing state tracking
    - Automatic lock release on completion or timeout
    """
    
    # Lock TTL in seconds (5 minutes max processing time)
    LOCK_TTL = 300
    
    # Processing state TTL (10 minutes to detect recent duplicates)
    STATE_TTL = 600
    
    # Lock acquisition retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_MS = 100
    
    @classmethod
    def _get_message_fingerprint(
        cls,
        message_id: str,
        conversation_id: str,
        message_text: str
    ) -> str:
        """
        Generate unique fingerprint for a message.
        
        Uses message ID, conversation ID, and content hash to create
        a unique identifier for deduplication.
        
        Args:
            message_id: Message UUID
            conversation_id: Conversation UUID
            message_text: Message text content
            
        Returns:
            Fingerprint string
        """
        # Create hash of message content
        content_hash = hashlib.sha256(message_text.encode()).hexdigest()[:16]
        
        # Combine with IDs
        fingerprint = f"{conversation_id}:{message_id}:{content_hash}"
        
        return fingerprint
    
    @classmethod
    def _get_lock_key(cls, fingerprint: str) -> str:
        """Generate cache key for processing lock."""
        return f"message_lock:{fingerprint}"
    
    @classmethod
    def _get_state_key(cls, fingerprint: str) -> str:
        """Generate cache key for processing state."""
        return f"message_state:{fingerprint}"
    
    @classmethod
    def is_duplicate(
        cls,
        message_id: str,
        conversation_id: str,
        message_text: str
    ) -> bool:
        """
        Check if message is a duplicate that's already being processed.
        
        Args:
            message_id: Message UUID
            conversation_id: Conversation UUID
            message_text: Message text content
            
        Returns:
            True if message is a duplicate, False otherwise
        """
        fingerprint = cls._get_message_fingerprint(
            message_id,
            conversation_id,
            message_text
        )
        
        # Check if message is currently locked (being processed)
        lock_key = cls._get_lock_key(fingerprint)
        if cache.get(lock_key):
            logger.warning(
                f"Duplicate message detected (currently processing): "
                f"message_id={message_id}, conversation_id={conversation_id}"
            )
            return True
        
        # Check if message was recently processed
        state_key = cls._get_state_key(fingerprint)
        state = cache.get(state_key)
        if state and state.get('status') == 'completed':
            logger.warning(
                f"Duplicate message detected (recently completed): "
                f"message_id={message_id}, conversation_id={conversation_id}"
            )
            return True
        
        return False
    
    @classmethod
    @contextmanager
    def acquire_lock(
        cls,
        message_id: str,
        conversation_id: str,
        message_text: str,
        worker_id: Optional[str] = None
    ):
        """
        Acquire distributed lock for message processing.
        
        Context manager that acquires a lock before processing and
        releases it after completion or on error.
        
        Args:
            message_id: Message UUID
            conversation_id: Conversation UUID
            message_text: Message text content
            worker_id: Optional worker identifier
            
        Yields:
            True if lock acquired, raises exception otherwise
            
        Raises:
            MessageLockError: If lock cannot be acquired
            
        Example:
            with MessageDeduplicationService.acquire_lock(msg_id, conv_id, text):
                # Process message
                process_message()
        """
        fingerprint = cls._get_message_fingerprint(
            message_id,
            conversation_id,
            message_text
        )
        
        lock_key = cls._get_lock_key(fingerprint)
        state_key = cls._get_state_key(fingerprint)
        
        # Try to acquire lock
        lock_value = {
            'worker_id': worker_id or 'unknown',
            'acquired_at': timezone.now().isoformat(),
            'message_id': message_id,
            'conversation_id': conversation_id
        }
        
        # Use cache.add() which only sets if key doesn't exist (atomic operation)
        acquired = cache.add(lock_key, lock_value, cls.LOCK_TTL)
        
        if not acquired:
            # Lock already held by another worker
            existing_lock = cache.get(lock_key)
            logger.error(
                f"Failed to acquire lock for message {message_id}: "
                f"already held by {existing_lock.get('worker_id') if existing_lock else 'unknown'}"
            )
            raise MessageLockError(
                f"Message {message_id} is already being processed"
            )
        
        logger.info(
            f"Acquired lock for message {message_id} "
            f"(worker: {worker_id or 'unknown'})"
        )
        
        # Set processing state
        cache.set(state_key, {
            'status': 'processing',
            'started_at': timezone.now().isoformat(),
            'worker_id': worker_id or 'unknown'
        }, cls.STATE_TTL)
        
        try:
            yield True
            
            # Mark as completed
            cache.set(state_key, {
                'status': 'completed',
                'completed_at': timezone.now().isoformat(),
                'worker_id': worker_id or 'unknown'
            }, cls.STATE_TTL)
            
            logger.info(f"Message {message_id} processing completed")
            
        except Exception as e:
            # Mark as failed
            cache.set(state_key, {
                'status': 'failed',
                'failed_at': timezone.now().isoformat(),
                'error': str(e),
                'worker_id': worker_id or 'unknown'
            }, cls.STATE_TTL)
            
            logger.error(
                f"Message {message_id} processing failed: {e}",
                exc_info=True
            )
            raise
            
        finally:
            # Always release lock
            cache.delete(lock_key)
            logger.debug(f"Released lock for message {message_id}")
    
    @classmethod
    def get_processing_state(
        cls,
        message_id: str,
        conversation_id: str,
        message_text: str
    ) -> Optional[dict]:
        """
        Get current processing state for a message.
        
        Args:
            message_id: Message UUID
            conversation_id: Conversation UUID
            message_text: Message text content
            
        Returns:
            Dictionary with processing state or None if not found
        """
        fingerprint = cls._get_message_fingerprint(
            message_id,
            conversation_id,
            message_text
        )
        
        state_key = cls._get_state_key(fingerprint)
        state = cache.get(state_key)
        
        return state
    
    @classmethod
    def force_release_lock(
        cls,
        message_id: str,
        conversation_id: str,
        message_text: str
    ) -> bool:
        """
        Force release lock for a message.
        
        Use with caution - only for recovery from stuck locks.
        
        Args:
            message_id: Message UUID
            conversation_id: Conversation UUID
            message_text: Message text content
            
        Returns:
            True if lock was released, False if no lock existed
        """
        fingerprint = cls._get_message_fingerprint(
            message_id,
            conversation_id,
            message_text
        )
        
        lock_key = cls._get_lock_key(fingerprint)
        
        if cache.get(lock_key):
            cache.delete(lock_key)
            logger.warning(
                f"Force released lock for message {message_id}"
            )
            return True
        
        return False
    
    @classmethod
    def cleanup_expired_locks(cls) -> int:
        """
        Cleanup expired locks and states.
        
        This is handled automatically by Redis TTL, but this method
        can be used for manual cleanup or monitoring.
        
        Returns:
            Number of locks cleaned up
        """
        # Note: With Redis, expired keys are automatically removed
        # This method is here for compatibility and monitoring
        logger.info("Lock cleanup requested (handled automatically by Redis TTL)")
        return 0
    
    @classmethod
    def get_lock_statistics(cls) -> dict:
        """
        Get statistics about locks and processing states.
        
        Note: This is a simplified implementation. For production,
        consider using Redis SCAN to iterate through keys.
        
        Returns:
            Dictionary with lock statistics
        """
        # This is a placeholder - actual implementation would need
        # to scan Redis keys which can be expensive
        return {
            'note': 'Lock statistics require Redis SCAN implementation',
            'locks_are_managed_by': 'Redis TTL',
            'lock_ttl_seconds': cls.LOCK_TTL,
            'state_ttl_seconds': cls.STATE_TTL
        }


class MessageLockError(Exception):
    """Exception raised when message lock cannot be acquired."""
    pass


def create_message_deduplication_service() -> MessageDeduplicationService:
    """
    Factory function to create MessageDeduplicationService instance.
    
    Returns:
        MessageDeduplicationService instance
    """
    return MessageDeduplicationService()


# Decorator for automatic deduplication
def deduplicate_message(func: Callable) -> Callable:
    """
    Decorator to automatically deduplicate message processing.
    
    Wraps a function that processes messages and ensures it only
    runs once per unique message.
    
    Args:
        func: Function to wrap (must accept message, conversation, tenant)
        
    Returns:
        Wrapped function with deduplication
        
    Example:
        @deduplicate_message
        def process_message(message, conversation, tenant):
            # Process message
            pass
    """
    def wrapper(message, conversation, tenant, *args, **kwargs):
        # Check for duplicate
        if MessageDeduplicationService.is_duplicate(
            message_id=str(message.id),
            conversation_id=str(conversation.id),
            message_text=message.text
        ):
            logger.warning(
                f"Skipping duplicate message {message.id} "
                f"in conversation {conversation.id}"
            )
            return None
        
        # Acquire lock and process
        try:
            with MessageDeduplicationService.acquire_lock(
                message_id=str(message.id),
                conversation_id=str(conversation.id),
                message_text=message.text,
                worker_id=kwargs.get('worker_id')
            ):
                return func(message, conversation, tenant, *args, **kwargs)
        
        except MessageLockError as e:
            logger.error(f"Lock acquisition failed: {e}")
            return None
    
    return wrapper
