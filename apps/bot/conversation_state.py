"""
ConversationState schema and management for LangGraph orchestration.

Implements the canonical ConversationState dataclass with exact fields from design
and provides serialization/deserialization for persistence.
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Literal
import json
from datetime import datetime
from django.utils import timezone


# Literal types as specified in design
Intent = Literal[
    "sales_discovery", "product_question", "support_question", "order_status",
    "discounts_offers", "preferences_consent", "payment_help",
    "human_request", "spam_casual", "unknown"
]

Journey = Literal["sales", "support", "orders", "offers", "prefs", "governance", "unknown"]
Lang = Literal["en", "sw", "sheng", "mixed"]
GovernorClass = Literal["business", "casual", "spam", "abuse"]


@dataclass
class ConversationState:
    """
    Canonical ConversationState dataclass with exact fields from design.
    
    This is the explicit shared state object that tracks all conversation context
    and progress through the LangGraph orchestration system.
    
    All fields are exactly as specified in the design document to ensure
    compatibility with the LangGraph state machine.
    """
    
    # Identity & scoping
    tenant_id: str
    conversation_id: str
    request_id: str
    customer_id: Optional[str] = None
    phone_e164: Optional[str] = None  # only when needed for STK

    # Tenant context
    tenant_name: Optional[str] = None
    bot_name: Optional[str] = None
    bot_intro: Optional[str] = None
    tone_style: str = "friendly_concise"
    default_language: Lang = "en"
    allowed_languages: List[str] = field(default_factory=lambda: ["en", "sw", "sheng"])
    max_chattiness_level: int = 2  # 0..3 recommended
    catalog_link_base: Optional[str] = None
    payments_enabled: Dict[str, bool] = field(default_factory=dict)
    compliance: Dict[str, Any] = field(default_factory=dict)
    handoff: Dict[str, Any] = field(default_factory=dict)

    # Customer preferences / consent
    customer_language_pref: Optional[Lang] = None
    marketing_opt_in: Optional[bool] = None
    notification_prefs: Dict[str, bool] = field(default_factory=dict)

    # Classifiers
    intent: Intent = "unknown"
    intent_confidence: float = 0.0
    journey: Journey = "unknown"

    response_language: Lang = "en"
    language_confidence: float = 0.0

    governor_classification: GovernorClass = "business"
    governor_confidence: float = 0.0

    # Catalog selection & ordering
    last_catalog_query: Optional[str] = None
    last_catalog_filters: Dict[str, Any] = field(default_factory=dict)
    last_catalog_results: List[Dict[str, Any]] = field(default_factory=list)
    catalog_total_matches_estimate: Optional[int] = None
    selected_item_ids: List[str] = field(default_factory=list)

    cart: List[Dict[str, Any]] = field(default_factory=list)  # [{item_id, qty, variant_selection}]
    order_id: Optional[str] = None
    order_totals: Dict[str, Any] = field(default_factory=dict)
    payment_request_id: Optional[str] = None
    payment_status: Optional[str] = None  # pending/paid/failed/unknown

    # Retrieval context (RAG)
    kb_snippets: List[Dict[str, Any]] = field(default_factory=list)

    # Safety / escalation
    escalation_required: bool = False
    escalation_reason: Optional[str] = None
    handoff_ticket_id: Optional[str] = None

    # Conversation controls
    turn_count: int = 0
    casual_turns: int = 0
    spam_turns: int = 0

    # Input/Output
    incoming_message: Optional[str] = None  # Current incoming message text
    response_text: Optional[str] = None
    
    # Sales journey specific fields
    sales_step: Optional[str] = None  # Current step in sales journey
    presented_products: List[Dict[str, Any]] = field(default_factory=list)  # Products presented to user
    selected_product_details: Optional[Dict[str, Any]] = None  # Details of selected product
    available_offers: List[Dict[str, Any]] = field(default_factory=list)  # Available offers for order
    available_payment_methods: List[Dict[str, Any]] = field(default_factory=list)  # Available payment methods
    shortlist_rejections: int = 0  # Count of shortlist rejections for catalog link logic

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ConversationState to dictionary for serialization.
        
        Returns:
            Dict representation suitable for JSON serialization
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationState':
        """
        Create ConversationState from dictionary.
        
        Args:
            data: Dictionary representation of state
            
        Returns:
            ConversationState instance
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        required_fields = ['tenant_id', 'conversation_id', 'request_id']
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Required field '{field_name}' missing from state data")
        
        # Filter out fields that are not part of ConversationState schema
        # These are LangGraph orchestration fields that shouldn't be in the state object
        orchestration_fields = {
            'needs_clarification', 'clarification_reason', 'clarification_metadata',
            'escalation_metadata', 'routing_metadata', 'routing_decision', 
            'routing_confidence', 'journey_transition_reason', 'journey_transition_confidence',
            'journey_transition_metadata', 'previous_journey'
        }
        
        # Create filtered data with only ConversationState fields
        filtered_data = {k: v for k, v in data.items() if k not in orchestration_fields}
        
        # Create instance with filtered data
        return cls(**filtered_data)
    
    def to_json(self) -> str:
        """
        Serialize ConversationState to JSON string.
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ConversationState':
        """
        Deserialize ConversationState from JSON string.
        
        Args:
            json_str: JSON string representation
            
        Returns:
            ConversationState instance
            
        Raises:
            ValueError: If JSON is invalid or required fields missing
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in state data: {e}")
    
    def validate(self) -> None:
        """
        Validate state to ensure required fields are present and valid.
        
        Raises:
            ValueError: If state is invalid
        """
        # Validate required fields
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.conversation_id:
            raise ValueError("conversation_id is required")
        if not self.request_id:
            raise ValueError("request_id is required")
        
        # Validate literal types
        valid_intents = [
            "sales_discovery", "product_question", "support_question", "order_status",
            "discounts_offers", "preferences_consent", "payment_help",
            "human_request", "spam_casual", "unknown"
        ]
        if self.intent not in valid_intents:
            raise ValueError(f"Invalid intent: {self.intent}")
        
        valid_journeys = ["sales", "support", "orders", "offers", "prefs", "governance", "unknown"]
        if self.journey not in valid_journeys:
            raise ValueError(f"Invalid journey: {self.journey}")
        
        valid_languages = ["en", "sw", "sheng", "mixed"]
        if self.response_language not in valid_languages:
            raise ValueError(f"Invalid response_language: {self.response_language}")
        if self.default_language not in valid_languages:
            raise ValueError(f"Invalid default_language: {self.default_language}")
        if self.customer_language_pref and self.customer_language_pref not in valid_languages:
            raise ValueError(f"Invalid customer_language_pref: {self.customer_language_pref}")
        
        valid_governor_classes = ["business", "casual", "spam", "abuse"]
        if self.governor_classification not in valid_governor_classes:
            raise ValueError(f"Invalid governor_classification: {self.governor_classification}")
        
        # Validate confidence scores
        if not (0.0 <= self.intent_confidence <= 1.0):
            raise ValueError(f"intent_confidence must be between 0.0 and 1.0: {self.intent_confidence}")
        if not (0.0 <= self.language_confidence <= 1.0):
            raise ValueError(f"language_confidence must be between 0.0 and 1.0: {self.language_confidence}")
        if not (0.0 <= self.governor_confidence <= 1.0):
            raise ValueError(f"governor_confidence must be between 0.0 and 1.0: {self.governor_confidence}")
        
        # Validate chattiness level
        if not (0 <= self.max_chattiness_level <= 3):
            raise ValueError(f"max_chattiness_level must be between 0 and 3: {self.max_chattiness_level}")
        
        # Validate turn counts
        if self.turn_count < 0:
            raise ValueError(f"turn_count cannot be negative: {self.turn_count}")
        if self.casual_turns < 0:
            raise ValueError(f"casual_turns cannot be negative: {self.casual_turns}")
        if self.spam_turns < 0:
            raise ValueError(f"spam_turns cannot be negative: {self.spam_turns}")
    
    def update_intent(self, intent: Intent, confidence: float) -> None:
        """
        Update intent classification with validation.
        
        Args:
            intent: Detected intent
            confidence: Confidence score (0.0-1.0)
        """
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0: {confidence}")
        
        self.intent = intent
        self.intent_confidence = confidence
    
    def update_language(self, language: Lang, confidence: float) -> None:
        """
        Update language detection with validation.
        
        Args:
            language: Detected language
            confidence: Confidence score (0.0-1.0)
        """
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0: {confidence}")
        
        self.response_language = language
        self.language_confidence = confidence
    
    def update_governor(self, classification: GovernorClass, confidence: float) -> None:
        """
        Update conversation governor classification with validation.
        
        Args:
            classification: Governor classification
            confidence: Confidence score (0.0-1.0)
        """
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0: {confidence}")
        
        self.governor_classification = classification
        self.governor_confidence = confidence
    
    def increment_turn(self) -> None:
        """Increment turn count."""
        self.turn_count += 1
    
    def increment_casual_turns(self) -> None:
        """Increment casual turn count."""
        self.casual_turns += 1
    
    def increment_spam_turns(self) -> None:
        """Increment spam turn count."""
        self.spam_turns += 1
    
    def add_to_cart(self, item_id: str, quantity: int = 1, variant_selection: Optional[Dict[str, Any]] = None) -> None:
        """
        Add item to cart.
        
        Args:
            item_id: Product or service ID
            quantity: Quantity to add
            variant_selection: Selected variants (size, color, etc.)
        """
        cart_item = {
            "item_id": item_id,
            "qty": quantity,
            "variant_selection": variant_selection or {}
        }
        self.cart.append(cart_item)
    
    def clear_cart(self) -> None:
        """Clear shopping cart."""
        self.cart = []
    
    def set_escalation(self, reason: str, ticket_id: Optional[str] = None) -> None:
        """
        Set escalation flag with reason.
        
        Args:
            reason: Reason for escalation
            ticket_id: Optional handoff ticket ID
        """
        self.escalation_required = True
        self.escalation_reason = reason
        if ticket_id:
            self.handoff_ticket_id = ticket_id
    
    def clear_escalation(self) -> None:
        """Clear escalation flag."""
        self.escalation_required = False
        self.escalation_reason = None
        self.handoff_ticket_id = None


class ConversationStateManager:
    """
    Manager for ConversationState persistence and retrieval.
    
    Handles serialization/deserialization and database operations
    for ConversationState objects.
    """
    
    @staticmethod
    def create_initial_state(
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        customer_id: Optional[str] = None,
        **kwargs
    ) -> ConversationState:
        """
        Create initial ConversationState with required fields.
        
        Args:
            tenant_id: Tenant identifier
            conversation_id: Conversation identifier
            request_id: Request identifier
            customer_id: Optional customer identifier
            **kwargs: Additional state fields
            
        Returns:
            ConversationState instance
        """
        state = ConversationState(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=request_id,
            customer_id=customer_id,
            **kwargs
        )
        state.validate()
        return state
    
    @staticmethod
    def serialize_for_storage(state: ConversationState) -> str:
        """
        Serialize ConversationState for database storage.
        
        Args:
            state: ConversationState to serialize
            
        Returns:
            JSON string for storage
        """
        state.validate()
        return state.to_json()
    
    @staticmethod
    def deserialize_from_storage(json_str: str) -> ConversationState:
        """
        Deserialize ConversationState from database storage.
        
        Args:
            json_str: JSON string from storage
            
        Returns:
            ConversationState instance
        """
        state = ConversationState.from_json(json_str)
        state.validate()
        return state