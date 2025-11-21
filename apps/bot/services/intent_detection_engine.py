"""
Intent Detection Engine for the sales orchestration refactor.

This service classifies customer messages into a constrained set of intents
using rule-based detection first, with LLM fallback only when needed.

Design principles:
- Rule-based classification for 60-80% of messages (fast, cheap)
- LLM fallback for ambiguous messages (20-40%)
- Context-aware intent adjustment
- Multi-language support (EN/SW/Sheng)
"""
import re
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from django.utils import timezone

from apps.messaging.models import Message, Conversation
from apps.bot.models import ConversationContext, AgentConfiguration
from apps.bot.models_sales_orchestration import IntentClassificationLog
from apps.tenants.models import Tenant


class Intent(str, Enum):
    """Constrained set of intents for the bot."""
    GREET = "GREET"
    BROWSE_PRODUCTS = "BROWSE_PRODUCTS"
    BROWSE_SERVICES = "BROWSE_SERVICES"
    PRODUCT_DETAILS = "PRODUCT_DETAILS"
    SERVICE_DETAILS = "SERVICE_DETAILS"
    PLACE_ORDER = "PLACE_ORDER"
    BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
    CHECK_ORDER_STATUS = "CHECK_ORDER_STATUS"
    CHECK_APPOINTMENT_STATUS = "CHECK_APPOINTMENT_STATUS"
    ASK_DELIVERY_FEES = "ASK_DELIVERY_FEES"
    ASK_RETURN_POLICY = "ASK_RETURN_POLICY"
    PAYMENT_HELP = "PAYMENT_HELP"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    GENERAL_FAQ = "GENERAL_FAQ"
    SMALL_TALK = "SMALL_TALK"
    UNKNOWN = "UNKNOWN"


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: Intent
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    language: List[str] = field(default_factory=list)  # ['en'], ['sw'], ['sheng'], ['en', 'sw']
    needs_clarification: bool = False
    resolved_from_context: bool = False  # True if resolved from menu/button
    method: str = "rule"  # "rule", "llm", "context"
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntentDetectionEngine:
    """
    Intent detection engine using rules first, LLM as fallback.
    
    Classification flow:
    1. Check if awaiting_response - use context to interpret
    2. Check for numeric reply - resolve from last_menu
    3. Check for WhatsApp button/list payload - direct mapping
    4. Try rule-based keyword matching
    5. Fall back to small LLM if needed
    """
    
    # Rule-based patterns for intent classification
    # Patterns support EN/SW/Sheng
    INTENT_PATTERNS = {
        Intent.GREET: [
            r'\b(hi|hello|hey|hola|sasa|mambo|vipi|habari|niaje)\b',
            r'\b(good morning|good afternoon|good evening)\b',
            r'\b(morning|afternoon|evening)\b',
        ],
        Intent.BROWSE_PRODUCTS: [
            r'\b(browse|view|see|show|display|list)\b.*\b(products?|items?|goods?|bidhaa|vitu)\b',
            r'\b(what do you (have|sell))\b',
            r'\b(what\'s available|whats available)\b',
            r'\b(naona nini|una nini|mna nini|kuna nini)\b',
            r'\b(nionyeshe|show me|let me see)\b.*\b(products?|bidhaa)\b',
            r'\b(nataka kuona|nataka kujua)\b.*\b(products?|bidhaa)\b',
        ],
        Intent.BROWSE_SERVICES: [
            r'\b(services?|salon|spa|clinic|therapy|massage)\b',
            r'\b(nataka service|services ziko|mna services gani)\b',
            r'\b(book|appointment|slot|booking)\b',
            r'\b(nataka kubook|nataka appointment)\b',
        ],
        Intent.PLACE_ORDER: [
            r'\b(order|buy|purchase|get|take|nunua|chukua)\b',
            r'\b(nataka kununua|nataka|nitanunua)\b',
            r'\b(add to cart|checkout|pay now)\b',
            r'\b(weka kwa cart|lipa sasa)\b',
            r'\b(i want|i need|i\'ll take)\b',
        ],
        Intent.PAYMENT_HELP: [
            r'\b(pay|payment|mpesa|lipa|malipo|pesa)\b',
            r'\b(paybill|till|card|visa|mastercard)\b',
            r'\b(how (do|can) i pay|payment method)\b',
            r'\b(nalipa aje|nilipe vipi|malipo)\b',
        ],
        Intent.CHECK_ORDER_STATUS: [
            r'\b(order status|my order|track order|order tracking)\b',
            r'\b(where is my order|order iko wapi)\b',
            r'\b(check order|order yangu)\b',
        ],
        Intent.CHECK_APPOINTMENT_STATUS: [
            r'\b(appointment status|my appointment|check appointment)\b',
            r'\b(appointment yangu|booking yangu)\b',
        ],
        Intent.ASK_DELIVERY_FEES: [
            r'\b(delivery fee|shipping cost|transport|delivery charge)\b',
            r'\b(bei ya delivery|gharama ya delivery)\b',
            r'\b(how much.*delivery|delivery.*cost)\b',
        ],
        Intent.ASK_RETURN_POLICY: [
            r'\b(return policy|refund|return|exchange)\b',
            r'\b(rudisha|refund|return)\b',
            r'\b(can i return|return policy)\b',
        ],
        Intent.REQUEST_HUMAN: [
            r'\b(human|person|agent|representative|mtu|binadamu)\b',
            r'\b(ongea na mtu|talk to someone|speak to agent)\b',
            r'\b(nataka kuongea na mtu)\b',
        ],
        Intent.SMALL_TALK: [
            r'\b(how are you|how\'s it going|what\'s up)\b',
            r'\b(habari yako|uko aje|mambo vipi)\b',
            r'\b(thank you|thanks|asante|shukran)\b',
            r'\b(you\'re welcome|karibu|no problem)\b',
        ],
    }
    
    # Slot extraction patterns
    SLOT_PATTERNS = {
        'category': r'\b(shoes?|shirts?|dresses?|jackets?|pants?|viatu|nguo)\b',
        'budget': r'\b(\d{1,3}(?:,\d{3})*|\d+)\s*(shillings?|bob|ksh|kes|/=)?\b',
        'quantity': r'\b(\d+)\s*(pieces?|items?|vitu)?\b',
        'date': r'\b(today|tomorrow|kesho|leo|next week|wiki ijayo)\b',
        'time': r'\b(\d{1,2})\s*(am|pm|asubuhi|jioni|usiku)?\b',
    }
    
    def __init__(self):
        """Initialize the intent detection engine."""
        pass
    
    def detect_intent(
        self,
        message: Message,
        context: ConversationContext,
        tenant: Tenant
    ) -> IntentResult:
        """
        Detect intent using rules first, LLM as fallback.
        
        Args:
            message: The message to classify
            context: Conversation context
            tenant: Tenant for configuration
        
        Returns:
            IntentResult with detected intent and metadata
        """
        start_time = time.time()
        text = message.body.strip().lower()
        
        # Step 1: Check if awaiting_response - use context to interpret
        if context.awaiting_response:
            result = self._resolve_from_awaiting_response(text, context)
            if result:
                result.resolved_from_context = True
                result.method = "context"
                self._log_classification(message, context, tenant, result, start_time)
                return result
        
        # Step 2: Check for numeric reply - resolve from last_menu
        if self._is_numeric_reply(text):
            result = self._resolve_from_menu(text, context)
            if result:
                result.resolved_from_context = True
                result.method = "context"
                self._log_classification(message, context, tenant, result, start_time)
                return result
        
        # Step 3: Check for WhatsApp button/list payload
        if message.metadata.get('interactive'):
            result = self._resolve_from_interactive(message, context)
            if result:
                result.resolved_from_context = True
                result.method = "context"
                self._log_classification(message, context, tenant, result, start_time)
                return result
        
        # Step 4: Try rule-based keyword matching
        result = self._rule_based_classification(text, context)
        if result and result.confidence >= 0.7:
            result.method = "rule"
            self._log_classification(message, context, tenant, result, start_time)
            return result
        
        # Step 5: Fall back to small LLM if needed
        config = self._get_agent_config(tenant)
        if config and config.enable_rule_based_intent:
            # LLM fallback
            result = self._llm_classification(text, context, tenant)
            result.method = "llm"
            self._log_classification(message, context, tenant, result, start_time)
            return result
        
        # Default to UNKNOWN if all else fails
        result = IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            language=self._detect_language(text),
            needs_clarification=True,
            method="rule"
        )
        self._log_classification(message, context, tenant, result, start_time)
        return result
    
    def _resolve_from_awaiting_response(
        self,
        text: str,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Resolve intent based on awaiting_response context."""
        if not context.awaiting_response or not context.current_flow:
            return None
        
        # Map flow states to expected intents
        flow_intent_map = {
            'browsing_products': Intent.PRODUCT_DETAILS,
            'product_details': Intent.PLACE_ORDER,
            'checkout': Intent.PAYMENT_HELP,
            'booking': Intent.BOOK_APPOINTMENT,
        }
        
        expected_intent = flow_intent_map.get(context.current_flow)
        if expected_intent:
            return IntentResult(
                intent=expected_intent,
                confidence=0.9,
                language=self._detect_language(text),
                slots=self._extract_slots(text, expected_intent, context)
            )
        
        return None
    
    def _is_numeric_reply(self, text: str) -> bool:
        """Check if text is a numeric reply (e.g., "1", "2", "first", "last")."""
        # Check for pure numbers
        if re.match(r'^\d+$', text):
            return True
        
        # Check for positional words
        positional_words = ['first', 'second', 'third', 'last', 'kwanza', 'ya pili', 'ya mwisho']
        return any(word in text for word in positional_words)
    
    def _resolve_from_menu(
        self,
        text: str,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Resolve intent from numeric menu selection."""
        if not context.last_menu or not context.last_menu.get('items'):
            return None
        
        # Check if menu is expired (5 minutes)
        if context.last_menu_timestamp:
            from datetime import timedelta
            if timezone.now() - context.last_menu_timestamp > timedelta(minutes=5):
                return None
        
        # Extract position
        position = self._extract_position(text, len(context.last_menu['items']))
        if position is None:
            return None
        
        # Determine intent based on menu type
        menu_type = context.last_menu.get('type', '')
        intent_map = {
            'products': Intent.PRODUCT_DETAILS,
            'services': Intent.SERVICE_DETAILS,
            'orders': Intent.CHECK_ORDER_STATUS,
            'appointments': Intent.CHECK_APPOINTMENT_STATUS,
        }
        
        intent = intent_map.get(menu_type, Intent.UNKNOWN)
        if intent == Intent.UNKNOWN:
            return None
        
        # Get selected item
        selected_item = context.last_menu['items'][position - 1]
        
        return IntentResult(
            intent=intent,
            confidence=1.0,
            language=self._detect_language(text),
            slots={'selected_item': selected_item, 'position': position}
        )
    
    def _extract_position(self, text: str, max_position: int) -> Optional[int]:
        """Extract position from text (1-indexed)."""
        # Try numeric
        match = re.match(r'^(\d+)$', text)
        if match:
            position = int(match.group(1))
            if 1 <= position <= max_position:
                return position
        
        # Try positional words
        if 'first' in text or 'kwanza' in text:
            return 1
        if 'last' in text or 'mwisho' in text:
            return max_position
        if 'second' in text or 'ya pili' in text:
            return 2 if max_position >= 2 else None
        if 'third' in text or 'ya tatu' in text:
            return 3 if max_position >= 3 else None
        
        return None
    
    def _resolve_from_interactive(
        self,
        message: Message,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Resolve intent from WhatsApp interactive message (button/list)."""
        interactive = message.metadata.get('interactive', {})
        
        # Button reply
        if interactive.get('type') == 'button_reply':
            button_id = interactive.get('button_reply', {}).get('id', '')
            return self._map_button_to_intent(button_id, context)
        
        # List reply
        if interactive.get('type') == 'list_reply':
            list_id = interactive.get('list_reply', {}).get('id', '')
            return self._map_list_to_intent(list_id, context)
        
        return None
    
    def _map_button_to_intent(
        self,
        button_id: str,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Map button ID to intent."""
        # Common button patterns
        button_intent_map = {
            'confirm_yes': Intent.PLACE_ORDER,
            'confirm_no': Intent.BROWSE_PRODUCTS,
            'pay_mpesa': Intent.PAYMENT_HELP,
            'pay_card': Intent.PAYMENT_HELP,
            'book_appointment': Intent.BOOK_APPOINTMENT,
            'request_human': Intent.REQUEST_HUMAN,
        }
        
        intent = button_intent_map.get(button_id, Intent.UNKNOWN)
        if intent == Intent.UNKNOWN:
            return None
        
        return IntentResult(
            intent=intent,
            confidence=1.0,
            language=['en'],  # Buttons are typically in English
            slots={'button_id': button_id}
        )
    
    def _map_list_to_intent(
        self,
        list_id: str,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Map list selection ID to intent."""
        # List IDs typically contain product/service IDs
        if list_id.startswith('product_'):
            return IntentResult(
                intent=Intent.PRODUCT_DETAILS,
                confidence=1.0,
                language=['en'],
                slots={'product_id': list_id.replace('product_', '')}
            )
        
        if list_id.startswith('service_'):
            return IntentResult(
                intent=Intent.SERVICE_DETAILS,
                confidence=1.0,
                language=['en'],
                slots={'service_id': list_id.replace('service_', '')}
            )
        
        return None
    
    def _rule_based_classification(
        self,
        text: str,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Use keyword patterns and regex for classification."""
        best_match = None
        best_confidence = 0.0
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # Calculate confidence based on pattern specificity
                    confidence = 0.8  # Base confidence for pattern match
                    
                    # Boost confidence if multiple patterns match
                    match_count = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
                    confidence += min(0.2, match_count * 0.05)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = intent
                        break
        
        if best_match:
            return IntentResult(
                intent=best_match,
                confidence=best_confidence,
                language=self._detect_language(text),
                slots=self._extract_slots(text, best_match, context),
                metadata={'matched_patterns': True}
            )
        
        return None
    
    def _llm_classification(
        self,
        text: str,
        context: ConversationContext,
        tenant: Tenant
    ) -> IntentResult:
        """
        Call small LLM with structured output for classification.
        
        Uses LLMRouter to select the cheapest viable model and track costs.
        """
        from apps.bot.services.llm_router import LLMRouter
        
        try:
            # Create LLM router for tenant
            router = LLMRouter(tenant)
            
            # Build context dict
            context_dict = {
                'current_flow': context.current_flow,
                'awaiting_response': context.awaiting_response,
                'last_question': context.last_question,
            }
            
            # Call LLM for classification
            result = router.classify_intent(text, context_dict)
            
            # Check if budget exceeded
            if result.get('budget_exceeded'):
                return IntentResult(
                    intent=Intent.UNKNOWN,
                    confidence=0.0,
                    language=self._detect_language(text),
                    needs_clarification=True,
                    metadata={'budget_exceeded': True}
                )
            
            # Parse result
            intent_value = result.get('intent', 'UNKNOWN')
            try:
                intent = Intent(intent_value)
            except ValueError:
                intent = Intent.UNKNOWN
            
            confidence = result.get('confidence', 0.5)
            slots = result.get('slots', {})
            
            return IntentResult(
                intent=intent,
                confidence=confidence,
                language=self._detect_language(text),
                slots=slots,
                needs_clarification=confidence < 0.65,
                metadata={
                    'llm_used': True,
                    'reasoning': result.get('reasoning', '')
                }
            )
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return IntentResult(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                language=self._detect_language(text),
                needs_clarification=True,
                metadata={'llm_error': str(e)}
            )
    
    def _extract_slots(
        self,
        text: str,
        intent: Intent,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Extract structured attributes using rules + LLM."""
        slots = {}
        
        # Extract using regex patterns
        for slot_name, pattern in self.SLOT_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                slots[slot_name] = match.group(1)
        
        # Clean up budget slot
        if 'budget' in slots:
            budget_str = slots['budget'].replace(',', '')
            try:
                slots['budget'] = int(budget_str)
            except ValueError:
                del slots['budget']
        
        # Clean up quantity slot
        if 'quantity' in slots:
            try:
                slots['quantity'] = int(slots['quantity'])
            except ValueError:
                del slots['quantity']
        
        return slots
    
    def _detect_language(self, text: str) -> List[str]:
        """Detect language from text (EN/SW/Sheng/mixed)."""
        languages = []
        
        # English indicators
        english_words = ['what', 'how', 'where', 'when', 'why', 'the', 'is', 'are', 'can', 'do']
        if any(word in text.lower() for word in english_words):
            languages.append('en')
        
        # Swahili indicators
        swahili_words = ['nini', 'vipi', 'wapi', 'lini', 'kwa', 'na', 'ya', 'wa', 'ni', 'una']
        if any(word in text.lower() for word in swahili_words):
            languages.append('sw')
        
        # Sheng indicators
        sheng_words = ['sasa', 'niaje', 'poa', 'fiti', 'doh', 'mboch', 'maze']
        if any(word in text.lower() for word in sheng_words):
            languages.append('sheng')
        
        # Default to English if no language detected
        if not languages:
            languages = ['en']
        
        return languages
    
    def _get_agent_config(self, tenant: Tenant) -> Optional[AgentConfiguration]:
        """Get agent configuration for tenant."""
        try:
            return AgentConfiguration.objects.get(tenant=tenant)
        except AgentConfiguration.DoesNotExist:
            return None
    
    def _log_classification(
        self,
        message: Message,
        context: ConversationContext,
        tenant: Tenant,
        result: IntentResult,
        start_time: float
    ) -> None:
        """Log classification for analytics and debugging."""
        classification_time_ms = int((time.time() - start_time) * 1000)
        
        IntentClassificationLog.objects.create(
            tenant=tenant,
            conversation=context.conversation,
            message=message,
            detected_intent=result.intent.value,
            confidence=result.confidence,
            method=result.method,
            extracted_slots=result.slots,
            detected_language=result.language,
            classification_time_ms=classification_time_ms,
            metadata=result.metadata
        )
