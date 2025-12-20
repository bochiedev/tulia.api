"""
ConversationSession model for ConversationState persistence.

Implements the database model for storing and retrieving ConversationState
objects with proper tenant scoping and validation.
"""
from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from .conversation_state import ConversationState, ConversationStateManager


class ConversationSessionManager(models.Manager):
    """Manager for ConversationSession queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get conversation sessions for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_conversation(self, conversation):
        """Get session for a specific conversation."""
        return self.filter(conversation=conversation).first()
    
    def active(self, tenant=None):
        """Get active conversation sessions."""
        qs = self.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs
    
    def by_customer(self, tenant, customer):
        """Get sessions for a specific customer within a tenant."""
        return self.filter(tenant=tenant, customer=customer)
    
    def get_or_create_for_conversation(self, conversation, request_id, **state_kwargs):
        """
        Get or create ConversationSession for a conversation.
        
        Args:
            conversation: Conversation instance
            request_id: Current request ID
            **state_kwargs: Additional state fields
            
        Returns:
            Tuple of (ConversationSession, created)
        """
        # Create initial state for defaults
        initial_state = ConversationStateManager.create_initial_state(
            tenant_id=str(conversation.tenant.id),
            conversation_id=str(conversation.id),
            request_id=request_id,
            customer_id=str(conversation.customer.id) if conversation.customer else None,
            **state_kwargs
        )
        
        session, created = self.get_or_create(
            conversation=conversation,
            defaults={
                'tenant': conversation.tenant,
                'customer': conversation.customer,
                'is_active': True,
                'state_data': ConversationStateManager.serialize_for_storage(initial_state),
                'last_request_id': request_id,
            }
        )
        
        return session, created


class ConversationSession(BaseModel):
    """
    ConversationSession model for storing ConversationState objects.
    
    Each conversation has one session that maintains the LangGraph state
    throughout the conversation lifecycle. The state is serialized as JSON
    and stored in the state_data field.
    
    TENANT SCOPING: All queries MUST filter by tenant to prevent cross-tenant data leakage.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='conversation_sessions',
        db_index=True,
        help_text="Tenant this session belongs to"
    )
    
    conversation = models.OneToOneField(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='session',
        db_index=True,
        help_text="Conversation this session belongs to"
    )
    
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='conversation_sessions',
        db_index=True,
        help_text="Customer this session belongs to"
    )
    
    # State Storage
    state_data = models.JSONField(
        help_text="Serialized ConversationState as JSON"
    )
    
    # Session Management
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this session is currently active"
    )
    
    last_request_id = models.CharField(
        max_length=255,
        help_text="ID of the last processed request"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional session metadata"
    )
    
    # Custom manager
    objects = ConversationSessionManager()
    
    class Meta:
        db_table = 'conversation_sessions'
        verbose_name = 'Conversation Session'
        verbose_name_plural = 'Conversation Sessions'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'updated_at']),
            models.Index(fields=['tenant', 'customer', 'is_active']),
            models.Index(fields=['conversation', 'is_active']),
            models.Index(fields=['last_request_id']),
        ]
    
    def __str__(self):
        return f"ConversationSession {self.id} - {self.conversation} (active: {self.is_active})"
    
    def get_state(self) -> ConversationState:
        """
        Get ConversationState from stored data.
        
        Returns:
            ConversationState instance
            
        Raises:
            ValidationError: If state data is invalid
        """
        try:
            return ConversationStateManager.deserialize_from_storage(
                self.state_data if isinstance(self.state_data, str) else str(self.state_data)
            )
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid state data: {e}")
    
    def update_state(self, state: ConversationState) -> None:
        """
        Update stored ConversationState.
        
        Args:
            state: ConversationState to store
            
        Raises:
            ValidationError: If state is invalid
        """
        try:
            # Validate state before storing
            state.validate()
            
            # Ensure state matches session identifiers
            if state.tenant_id != str(self.tenant.id):
                raise ValidationError(
                    f"State tenant_id ({state.tenant_id}) must match session tenant ({self.tenant.id})"
                )
            if state.conversation_id != str(self.conversation.id):
                raise ValidationError(
                    f"State conversation_id ({state.conversation_id}) must match session conversation ({self.conversation.id})"
                )
            
            # Serialize and store
            self.state_data = ConversationStateManager.serialize_for_storage(state)
            self.last_request_id = state.request_id
            
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid state: {e}")
    
    def update_and_save_state(self, state: ConversationState) -> None:
        """
        Update state and save to database.
        
        Args:
            state: ConversationState to store
        """
        self.update_state(state)
        self.save(update_fields=['state_data', 'last_request_id', 'updated_at'])
    
    def deactivate(self) -> None:
        """Deactivate the session."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def reactivate(self) -> None:
        """Reactivate the session."""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
    
    def clean(self):
        """Validate model fields."""
        super().clean()
        
        # Validate tenant consistency
        if self.conversation_id and self.tenant_id:
            if self.conversation.tenant_id != self.tenant_id:
                raise ValidationError(
                    f"Session tenant ({self.tenant_id}) must match conversation tenant ({self.conversation.tenant_id})"
                )
        
        if self.customer_id and self.tenant_id:
            if self.customer.tenant_id != self.tenant_id:
                raise ValidationError(
                    f"Session tenant ({self.tenant_id}) must match customer tenant ({self.customer.tenant_id})"
                )
        
        # Validate state data if present
        if self.state_data:
            try:
                state = self.get_state()
                state.validate()
            except (ValidationError, ValueError) as e:
                raise ValidationError(f"Invalid state data: {e}")
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant consistency and validate state."""
        # Auto-populate tenant and customer from conversation if not set
        if self.conversation_id and not self.tenant_id:
            self.tenant = self.conversation.tenant
        if self.conversation_id and not self.customer_id:
            self.customer = self.conversation.customer
        
        # Validate before saving
        self.clean()
        
        super().save(*args, **kwargs)


class ConversationStateService:
    """
    Service class for ConversationState operations.
    
    Provides high-level operations for managing conversation state
    throughout the LangGraph orchestration process.
    """
    
    @staticmethod
    def get_or_create_session(conversation, request_id, **state_kwargs):
        """
        Get or create ConversationSession for a conversation.
        
        Args:
            conversation: Conversation instance
            request_id: Current request ID
            **state_kwargs: Additional state fields for initial state
            
        Returns:
            ConversationSession instance
        """
        session, created = ConversationSession.objects.get_or_create_for_conversation(
            conversation=conversation,
            request_id=request_id,
            **state_kwargs
        )
        return session
    
    @staticmethod
    def get_state(conversation):
        """
        Get ConversationState for a conversation.
        
        Args:
            conversation: Conversation instance
            
        Returns:
            ConversationState instance or None if no session exists
        """
        session = ConversationSession.objects.for_conversation(conversation)
        if session:
            return session.get_state()
        return None
    
    @staticmethod
    def update_state(conversation, state):
        """
        Update ConversationState for a conversation.
        
        Args:
            conversation: Conversation instance
            state: ConversationState to store
        """
        session = ConversationSession.objects.for_conversation(conversation)
        if session:
            session.update_and_save_state(state)
        else:
            raise ValueError(f"No session found for conversation {conversation.id}")
    
    @staticmethod
    def create_initial_state_for_conversation(conversation, request_id, **kwargs):
        """
        Create initial ConversationState for a new conversation.
        
        Args:
            conversation: Conversation instance
            request_id: Initial request ID
            **kwargs: Additional state fields
            
        Returns:
            ConversationState instance
        """
        return ConversationStateManager.create_initial_state(
            tenant_id=str(conversation.tenant.id),
            conversation_id=str(conversation.id),
            request_id=request_id,
            customer_id=str(conversation.customer.id) if conversation.customer else None,
            **kwargs
        )
    
    @staticmethod
    def deactivate_session(conversation):
        """
        Deactivate ConversationSession for a conversation.
        
        Args:
            conversation: Conversation instance
        """
        session = ConversationSession.objects.for_conversation(conversation)
        if session:
            session.deactivate()
    
    @staticmethod
    def cleanup_inactive_sessions(tenant, days=7):
        """
        Clean up inactive sessions older than specified days.
        
        Args:
            tenant: Tenant instance
            days: Number of days to keep inactive sessions
            
        Returns:
            Number of sessions cleaned up
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find inactive sessions older than cutoff
        old_sessions = ConversationSession.objects.filter(
            tenant=tenant,
            is_active=False,
            updated_at__lt=cutoff_date
        )
        
        count = old_sessions.count()
        old_sessions.delete()
        
        return count