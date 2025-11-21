# Design Document

## Overview

This design addresses critical conversation flow failures that prevent the WabotIQ bot from completing sales. The current system suffers from: (1) echoing user messages, (2) not sending interactive WhatsApp elements, (3) poor context management, (4) endless conversations without closure, (5) confidence-undermining disclaimers, and (6) incomplete payment flows. This design provides concrete fixes to enable actual sales completion.

### Core Problems and Solutions

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| Bot echoes user messages | LLM prompt includes user message in response | Add post-processing filter to remove echoes |
| No interactive messages | Code exists but not being called | Fix message routing to use RichMessageBuilder |
| Poor context across days | Context loader limits to recent messages | Load full conversation history with session awareness |
| Never completes sales | No deterministic checkout flow | Implement state machine for checkout |
| "Needs verification" disclaimers | Overly cautious prompt engineering | Remove disclaimer phrases from prompts and responses |
| No payment initiation | Payment code not integrated with bot flow | Wire payment service directly into checkout flow |

## Architecture

### Message Processing Pipeline (Modified)

```
Customer Message
       ↓
[1. Message Harmonization] ← NEW: Buffer rapid messages
       ↓
[2. Context Loading] ← MODIFIED: Load full history + session detection
       ↓
[3. Echo Prevention] ← NEW: Store customer message for filtering
       ↓
[4. Intent Detection]
       ↓
[5. Reference Resolution] ← MODIFIED: Use last 5 lists, not just last 1
       ↓
[6. Business Logic Router]
       ↓
[7. Response Generation] ← MODIFIED: Remove disclaimers, enforce brevity
       ↓
[8. Echo Filtering] ← NEW: Remove customer message echoes
       ↓
[9. Rich Message Formatting] ← MODIFIED: Always use interactive elements
       ↓
[10. Response Validation] ← NEW: Check length, disclaimers, echoes
       ↓
WhatsApp Send
```

### Checkout State Machine (New)

```
BROWSING
   ↓ (customer selects product)
PRODUCT_SELECTED
   ↓ (ask quantity)
QUANTITY_CONFIRMED
   ↓ (create order, ask payment method)
PAYMENT_METHOD_SELECTED
   ↓ (initiate payment)
PAYMENT_INITIATED
   ↓ (wait for callback)
PAYMENT_CONFIRMED → ORDER_COMPLETE
```


## Components and Interfaces

### 1. Echo Prevention Filter (New)

**Purpose**: Remove customer message echoes from bot responses

**Interface**:
```python
class EchoPreventionFilter:
    def filter_response(
        self,
        response: str,
        customer_message: str,
        threshold: float = 0.8
    ) -> str:
        """
        Remove echoes of customer message from response.
        
        Steps:
        1. Check if customer message appears verbatim in response
        2. Check for partial matches (>80% similarity)
        3. Remove or rephrase echoed content
        4. Return cleaned response
        """
        
    def contains_echo(
        self,
        response: str,
        customer_message: str
    ) -> bool:
        """Check if response contains customer message echo"""
        
    def remove_quotes(
        self,
        response: str
    ) -> str:
        """Remove quoted customer text from response"""
```

**Implementation**:
- Use string matching to detect verbatim echoes
- Use fuzzy matching (difflib) for partial echoes
- Remove sentences containing echoes
- Log all echo removals for monitoring

### 2. Session-Aware Context Loader (Modified)

**Purpose**: Load conversation history with session awareness

**Interface**:
```python
class SessionAwareContextLoader:
    def load_context(
        self,
        conversation: Conversation,
        session_timeout_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Load context with session detection.
        
        Returns:
        {
            'current_session_messages': List[Message],  # Last 20 from current session
            'session_summary': str,  # Summary of current session
            'previous_sessions_summary': str,  # Summary of older sessions
            'reference_contexts': List[ReferenceContext],  # Last 5 lists
            'language_preference': str,
            'checkout_state': str
        }
        """
        
    def detect_session_boundary(
        self,
        conversation: Conversation
    ) -> Optional[datetime]:
        """Find start of current session (last 24hr gap)"""
        
    def summarize_session(
        self,
        messages: List[Message]
    ) -> str:
        """Generate summary of message sequence"""
```


### 3. Checkout State Machine (New)

**Purpose**: Deterministic checkout flow from selection to payment

**Interface**:
```python
class CheckoutStateMachine:
    def process_message(
        self,
        message: Message,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> CheckoutAction:
        """
        Process message based on current checkout state.
        
        Returns action to take (ask question, create order, initiate payment, etc.)
        """
        
    def transition_state(
        self,
        current_state: str,
        event: str,
        data: Dict[str, Any]
    ) -> Tuple[str, CheckoutAction]:
        """Execute state transition and return new state + action"""
        
    def create_order(
        self,
        product: Product,
        quantity: int,
        customer: Customer,
        tenant: Tenant
    ) -> Order:
        """Create order with PENDING_PAYMENT status"""
        
    def initiate_payment(
        self,
        order: Order,
        payment_method: str,
        phone_number: Optional[str] = None
    ) -> PaymentRequest:
        """Initiate payment and return request"""
```

**State Definitions**:
```python
class CheckoutState(str, Enum):
    BROWSING = "browsing"
    PRODUCT_SELECTED = "product_selected"
    QUANTITY_CONFIRMED = "quantity_confirmed"
    PAYMENT_METHOD_SELECTED = "payment_method_selected"
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_CONFIRMED = "payment_confirmed"
    ORDER_COMPLETE = "order_complete"
```

### 4. Interactive Message Router (Modified)

**Purpose**: Ensure all product/service displays use interactive elements

**Interface**:
```python
class InteractiveMessageRouter:
    def format_product_list(
        self,
        products: List[Product],
        context_id: str,
        language: str = 'en'
    ) -> WhatsAppInteractiveMessage:
        """
        Format products as WhatsApp list message.
        
        ALWAYS returns interactive format, never plain text.
        Falls back to buttons if list API fails.
        """
        
    def format_checkout_confirmation(
        self,
        order: Order,
        language: str = 'en'
    ) -> WhatsAppInteractiveMessage:
        """Format order confirmation with payment buttons"""
        
    def format_payment_methods(
        self,
        order: Order,
        available_methods: List[str],
        language: str = 'en'
    ) -> WhatsAppInteractiveMessage:
        """Format payment method selection as buttons"""
```

**WhatsApp Message Formats**:
```python
# List Message (for 3-10 products)
{
    "type": "list",
    "header": {"type": "text", "text": "Our Products"},
    "body": {"text": "Select a product:"},
    "action": {
        "button": "View Products",
        "sections": [{
            "rows": [
                {"id": "prod_123", "title": "Product Name", "description": "KES 5,000"}
            ]
        }]
    }
}

# Button Message (for 1-3 options)
{
    "type": "button",
    "body": {"text": "Would you like to proceed?"},
    "action": {
        "buttons": [
            {"type": "reply", "reply": {"id": "yes", "title": "Yes"}},
            {"type": "reply", "reply": {"id": "no", "title": "No"}}
        ]
    }
}
```


### 5. Disclaimer Remover (New)

**Purpose**: Remove confidence-undermining phrases from responses

**Interface**:
```python
class DisclaimerRemover:
    DISCLAIMER_PATTERNS = [
        r'needs? verification',
        r'may need confirmation',
        r'please verify',
        r'should be confirmed',
        r'might need to check',
        r'let me connect you.*for confirmation',
        r'some details may need',
    ]
    
    def remove_disclaimers(
        self,
        response: str
    ) -> str:
        """Remove disclaimer phrases from response"""
        
    def contains_disclaimers(
        self,
        response: str
    ) -> bool:
        """Check if response contains disclaimers"""
        
    def replace_with_confidence(
        self,
        response: str
    ) -> str:
        """Replace uncertain language with confident alternatives"""
```

**Replacement Rules**:
- "This needs verification" → Remove sentence
- "Please verify with our team" → "Contact us if you have questions"
- "May need confirmation" → Remove phrase
- "I'm not sure, but..." → "Let me connect you with our team"

### 6. Response Validator (New)

**Purpose**: Validate responses before sending

**Interface**:
```python
class ResponseValidator:
    def validate(
        self,
        response: str,
        customer_message: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate response meets all criteria.
        
        Returns: (is_valid, list_of_issues)
        
        Checks:
        1. No customer message echoes
        2. No disclaimer phrases
        3. Maximum 3 sentences (for non-list responses)
        4. Contains actionable next step
        5. Consistent language
        """
        
    def count_sentences(
        self,
        text: str
    ) -> int:
        """Count sentences in text"""
        
    def has_call_to_action(
        self,
        text: str
    ) -> bool:
        """Check if text contains actionable next step"""
```

### 7. Payment Integration Service (Modified)

**Purpose**: Wire payment directly into bot flow

**Interface**:
```python
class BotPaymentService:
    def initiate_mpesa_stk(
        self,
        order: Order,
        phone_number: str,
        conversation: Conversation
    ) -> Tuple[PaymentRequest, str]:
        """
        Initiate M-Pesa STK push.
        
        Returns: (PaymentRequest, message_to_customer)
        """
        
    def handle_payment_callback(
        self,
        payment_request: PaymentRequest,
        callback_data: Dict[str, Any]
    ) -> None:
        """
        Process payment callback and send confirmation.
        
        Steps:
        1. Update PaymentRequest status
        2. Update Order status if successful
        3. Send WhatsApp confirmation to customer
        4. Log transaction
        """
        
    def generate_payment_message(
        self,
        order: Order,
        payment_method: str,
        language: str = 'en'
    ) -> str:
        """Generate payment instruction message"""
```


### 8. Reference Resolution Service (Modified)

**Purpose**: Resolve "this one", "1", "first" to actual products

**Interface**:
```python
class ReferenceResolutionService:
    def resolve_reference(
        self,
        reference_text: str,
        conversation: Conversation,
        max_age_minutes: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve reference to item from recent lists.
        
        Handles:
        - Numbers: "1", "2", "3"
        - Ordinals: "first", "second", "last"
        - Demonstratives: "this one", "that one"
        - Descriptive: "the blue one", "the cheap one"
        
        Returns: {
            'type': 'product' | 'service',
            'id': str,
            'name': str,
            'context_id': str
        }
        """
        
    def get_recent_lists(
        self,
        conversation: Conversation,
        max_age_minutes: int = 5
    ) -> List[ReferenceContext]:
        """Get recent reference contexts (last 5)"""
        
    def store_list_context(
        self,
        conversation: Conversation,
        list_type: str,
        items: List[Any]
    ) -> str:
        """Store list for future reference, return context_id"""
```

## Data Models

### Modified Models

#### ConversationContext
```python
class ConversationContext(BaseModel):
    # EXISTING FIELDS...
    
    # NEW: Checkout state
    checkout_state = CharField(
        max_length=50,
        default='browsing',
        choices=CheckoutState.choices
    )
    selected_product_id = UUIDField(null=True)
    selected_quantity = IntegerField(null=True)
    pending_order_id = UUIDField(null=True)
    
    # NEW: Session tracking
    current_session_start = DateTimeField(null=True)
    session_message_count = IntegerField(default=0)
    
    # MODIFIED: Ensure these exist
    last_bot_message = TextField(blank=True)
    last_customer_message = TextField(blank=True)
```

#### AgentConfiguration
```python
class AgentConfiguration(BaseModel):
    # EXISTING FIELDS...
    
    # NEW: Response controls
    enable_echo_prevention = BooleanField(default=True)
    enable_disclaimer_removal = BooleanField(default=True)
    max_response_sentences = IntegerField(default=3)
    
    # NEW: Checkout controls
    enable_quick_checkout = BooleanField(default=True)
    max_checkout_messages = IntegerField(default=3)
    
    # NEW: Interactive message controls
    force_interactive_messages = BooleanField(default=True)
    fallback_to_text_on_error = BooleanField(default=True)
```

### New Models

#### CheckoutSession
```python
class CheckoutSession(BaseModel):
    """Track checkout progress"""
    conversation = ForeignKey(Conversation)
    customer = ForeignKey(Customer)
    tenant = ForeignKey(Tenant)
    
    # State
    state = CharField(max_length=50, choices=CheckoutState.choices)
    
    # Data
    selected_product = ForeignKey(Product, null=True)
    quantity = IntegerField(null=True)
    order = ForeignKey(Order, null=True)
    payment_request = ForeignKey(PaymentRequest, null=True)
    
    # Metadata
    started_at = DateTimeField(auto_now_add=True)
    completed_at = DateTimeField(null=True)
    abandoned_at = DateTimeField(null=True)
    message_count = IntegerField(default=0)
```


#### ResponseValidationLog
```python
class ResponseValidationLog(BaseModel):
    """Track response validation for monitoring"""
    conversation = ForeignKey(Conversation)
    message = ForeignKey(Message, null=True)
    
    # Validation results
    had_echo = BooleanField(default=False)
    had_disclaimer = BooleanField(default=False)
    exceeded_length = BooleanField(default=False)
    missing_cta = BooleanField(default=False)
    
    # Original vs cleaned
    original_response = TextField()
    cleaned_response = TextField()
    
    # Metadata
    validation_time_ms = IntegerField()
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: No message echoes
*For any* customer message and bot response pair, the bot response should not contain the customer's exact message text as a substring
**Validates: Requirements 1.1, 1.4**

### Property 2: Natural confirmations
*For any* confirmation response, the response should not contain verbatim quotes from the customer message
**Validates: Requirements 1.2, 1.5**

### Property 3: Reference resolution with names
*For any* numeric or demonstrative reference ("1", "this one"), the bot response should contain the actual item name, not just the reference
**Validates: Requirements 1.3, 11.3**

### Property 4: Interactive message format
*For any* response containing 2 or more products, the message format should be WhatsApp interactive (list or buttons), not plain text
**Validates: Requirements 2.1, 2.2**

### Property 5: Unique product IDs
*For any* product list sent, all products should have unique selectable IDs
**Validates: Requirements 2.2**

### Property 6: Full history loading
*For any* conversation, when loading context, all messages should be retrieved regardless of time gaps
**Validates: Requirements 3.1, 3.2**

### Property 7: Context window structure
*For any* loaded context, it should contain the last 20 messages from current session plus a summary of older messages
**Validates: Requirements 3.3**

### Property 8: No false "haven't talked" claims
*For any* conversation with at least one prior message, responses should not contain phrases like "we haven't talked" or "we haven't had a conversation"
**Validates: Requirements 3.5**

### Property 9: Quick checkout flow
*For any* purchase intent to payment initiation, the message count should not exceed 3 messages
**Validates: Requirements 4.2, 4.4**

### Property 10: Payment initiation speed
*For any* confirmed order, payment should be initiated within 1 message
**Validates: Requirements 4.3**

### Property 11: No unsolicited messages after payment
*For any* payment initiation, no additional bot messages should be sent until payment callback or customer response
**Validates: Requirements 4.5, 7.5**

### Property 12: No disclaimer phrases
*For any* bot response, it should not contain phrases like "needs verification", "may need confirmation", or "please verify"
**Validates: Requirements 5.1, 5.4, 5.5**

### Property 13: Human handoff for uncertainty
*For any* response expressing uncertainty, it should offer human connection instead of adding disclaimers
**Validates: Requirements 5.2**

### Property 14: Payment flow completeness
*For any* order confirmation, the next message should ask for M-Pesa phone number
**Validates: Requirements 6.1**

### Property 15: STK push confirmation message
*For any* STK push initiation, the bot should send a message instructing customer to check their phone
**Validates: Requirements 6.3**

### Property 16: Payment callback handling
*For any* successful payment callback, the bot should send order confirmation
**Validates: Requirements 6.4**

### Property 17: Payment failure alternatives
*For any* failed payment callback, the bot should offer retry or alternative payment methods
**Validates: Requirements 6.5**

### Property 18: Session boundary detection
*For any* conversation idle for more than 24 hours, the next message should trigger new session detection
**Validates: Requirements 8.2**

### Property 19: Session-scoped context
*For any* new session, loaded context should include session summary, not full old message history
**Validates: Requirements 8.3, 8.4**

### Property 20: Current session references
*For any* bot response referencing past interactions, references should be to current session only
**Validates: Requirements 8.5**

### Property 21: Product images included
*For any* product display where image URL exists, the message should include the image in the media payload
**Validates: Requirements 9.1, 9.4**

### Property 22: Primary image selection
*For any* product with multiple images, the message should use the primary image
**Validates: Requirements 9.2**

### Property 23: No image placeholders
*For any* product without an image, the message should not include image placeholders
**Validates: Requirements 9.3**

### Property 24: Order creation on confirmation
*For any* product confirmation, an Order record with status PENDING_PAYMENT should be created
**Validates: Requirements 10.1**

### Property 25: Accurate order totals
*For any* created order, the total should exactly match the sum of database product prices × quantities
**Validates: Requirements 10.2**

### Property 26: Payment amount accuracy
*For any* payment initiation, the PaymentRequest amount should exactly match the Order total
**Validates: Requirements 10.3**

### Property 27: Correct payment credentials
*For any* payment processing, only the tenant's actual credentials from TenantSettings should be used
**Validates: Requirements 10.4**

### Property 28: Order status update on payment
*For any* successful payment, the Order status should be updated to PAID
**Validates: Requirements 10.5**

### Property 29: Reference resolution accuracy
*For any* reference phrase ("this one", "1", "first"), it should resolve to the correct item from the most recent list
**Validates: Requirements 11.1, 11.2**

### Property 30: Clarification for ambiguity
*For any* ambiguous reference, the bot should ask for clarification with specific options
**Validates: Requirements 11.4**

### Property 31: Specification request for missing context
*For any* reference when no recent list exists, the bot should ask customer to specify which product
**Validates: Requirements 11.5**

### Property 32: Response brevity
*For any* non-list bot response, it should contain a maximum of 3 sentences
**Validates: Requirements 12.1, 12.4**

### Property 33: Product list size limit
*For any* product display, a maximum of 5 products should be shown at once
**Validates: Requirements 12.2**

### Property 34: Business name in introduction
*For any* bot introduction, the tenant's business name should be present in the message
**Validates: Requirements 13.1**

### Property 35: Business name in confirmations
*For any* order confirmation, the tenant's business name should be referenced
**Validates: Requirements 13.3**

### Property 36: AI assistant identification
*For any* human handoff, the bot should identify itself as the business's AI assistant
**Validates: Requirements 13.4**

### Property 37: Custom greeting usage
*For any* first message when custom greeting is configured, the custom greeting should be used
**Validates: Requirements 13.5**

### Property 38: Payment request logging
*For any* payment initiation, a PaymentRequest record with status PENDING should be created
**Validates: Requirements 14.1**

### Property 39: Callback data storage
*For any* payment callback, the PaymentRequest should be updated with callback data
**Validates: Requirements 14.2**

### Property 40: Failure logging
*For any* payment failure, the failure reason and error details should be logged
**Validates: Requirements 14.3**

### Property 41: Success transaction logging
*For any* payment success, the transaction reference and amount should be logged
**Validates: Requirements 14.4**

### Property 42: Error logging to Sentry
*For any* payment error, a Sentry log with full context should be created
**Validates: Requirements 14.5**

### Property 43: Language matching
*For any* customer message in a specific language (English/Swahili), the bot response should be in the same language
**Validates: Requirements 15.1, 15.2**

### Property 44: Dominant language for mixed input
*For any* customer message mixing languages, the bot should respond in the dominant language
**Validates: Requirements 15.3**

### Property 45: Language preference storage
*For any* language detection, the preference should be stored in ConversationContext
**Validates: Requirements 15.4**

### Property 46: Immediate language adaptation
*For any* language switch by customer, the bot should adapt to the new language in the next response
**Validates: Requirements 15.5**


## Error Handling

### Echo Detection Failures
- **False Positive**: If echo filter removes valid content, log and allow through
- **Missed Echo**: If echo slips through, log for pattern improvement
- **Performance**: If filtering takes >100ms, skip and log

### Interactive Message Failures
- **WhatsApp API Error**: Fall back to numbered text list
- **Invalid Payload**: Log error, send plain text version
- **Button Limit Exceeded**: Convert to list message format

### Context Loading Failures
- **Database Timeout**: Load last 10 messages only, log error
- **Missing Conversation**: Create new context, log warning
- **Corrupt Context Data**: Reset context, log error

### Checkout State Errors
- **Invalid State Transition**: Reset to BROWSING, log error
- **Missing Product**: Ask customer to select again
- **Order Creation Failure**: Log to Sentry, offer human handoff

### Payment Errors
- **STK Push Failure**: Offer manual M-Pesa or card payment
- **Invalid Phone Number**: Ask customer to provide valid number
- **Callback Timeout**: After 2 minutes, ask customer to confirm payment status
- **Duplicate Payment**: Check order status, don't charge twice

### Reference Resolution Errors
- **Expired Context**: Ask customer to specify which product
- **Ambiguous Reference**: Show all matches, ask customer to choose
- **No Recent Lists**: Prompt customer to browse products first

## Testing Strategy

### Unit Testing

**Echo Prevention Tests**:
- Test verbatim echo detection and removal
- Test partial echo detection (>80% similarity)
- Test quote removal
- Test false positive handling

**Disclaimer Removal Tests**:
- Test each disclaimer pattern removal
- Test replacement with confident alternatives
- Test preservation of valid uncertainty expressions

**Response Validation Tests**:
- Test sentence counting
- Test call-to-action detection
- Test length validation
- Test combined validation

**Checkout State Machine Tests**:
- Test each state transition
- Test invalid transitions
- Test order creation
- Test payment initiation

**Reference Resolution Tests**:
- Test numeric references ("1", "2")
- Test ordinal references ("first", "last")
- Test demonstrative references ("this one")
- Test expired context handling

### Property-Based Testing

We'll use **Hypothesis** (Python) for property-based testing.

**Property Test 1: No Message Echoes**
```python
@given(
    customer_message=st.text(min_size=10, max_size=200),
    bot_response=st.text(min_size=20, max_size=500)
)
def test_no_message_echoes(customer_message, bot_response):
    """Property: Bot responses never contain customer message verbatim"""
    # Assume: bot_response generated from customer_message
    # Action: Apply echo filter
    # Assert: Filtered response doesn't contain customer_message
```

**Property Test 2: Interactive Message Format**
```python
@given(
    products=st.lists(products(), min_size=2, max_size=10)
)
def test_interactive_message_format(products):
    """Property: Multiple products always formatted as interactive"""
    # Action: Format products
    # Assert: Message type is 'list' or 'button', not plain text
```

**Property Test 3: Quick Checkout**
```python
@given(
    product=products(),
    quantity=st.integers(min_value=1, max_value=10)
)
def test_quick_checkout(product, quantity):
    """Property: Checkout completes in ≤3 messages"""
    # Setup: Customer selects product
    # Action: Run through checkout flow
    # Assert: Message count from selection to payment ≤ 3
```

**Property Test 4: No Disclaimers**
```python
@given(
    response=st.text(min_size=20, max_size=500)
)
def test_no_disclaimers(response):
    """Property: Responses don't contain disclaimer phrases"""
    # Action: Apply disclaimer remover
    # Assert: No disclaimer patterns in cleaned response
```

**Property Test 5: Accurate Order Totals**
```python
@given(
    product=products(),
    quantity=st.integers(min_value=1, max_value=100)
)
def test_accurate_order_totals(product, quantity):
    """Property: Order total = product price × quantity"""
    # Action: Create order
    # Assert: order.total == product.price * quantity
```

**Property Test 6: Reference Resolution**
```python
@given(
    products=st.lists(products(), min_size=1, max_size=10),
    reference=st.sampled_from(["1", "2", "first", "last", "this one"])
)
def test_reference_resolution(products, reference):
    """Property: References resolve to correct product"""
    # Setup: Store product list context
    # Action: Resolve reference
    # Assert: Resolved product is correct from list
```

**Property Test 7: Language Matching**
```python
@given(
    message_language=st.sampled_from(['en', 'sw']),
    message_text=st.text(min_size=10, max_size=100)
)
def test_language_matching(message_language, message_text):
    """Property: Bot responds in same language as customer"""
    # Setup: Customer message in specific language
    # Action: Generate response
    # Assert: Response language matches customer language
```

### Integration Testing

**End-to-End Checkout Flow**:
1. Customer: "Mko na perfume?"
2. Bot: [Interactive list with 5 perfumes]
3. Customer: "1" (selects first)
4. Bot: "How many would you like?" [Buttons: 1, 2, 3]
5. Customer: "1"
6. Bot: "Your order: Perfume x1 = KES 79.99. Pay via?" [Buttons: M-Pesa, Card]
7. Customer: "M-Pesa"
8. Bot: "Enter your M-Pesa number:"
9. Customer: "0712345678"
10. Bot: "STK push sent! Check your phone to complete payment."
11. [Payment callback received]
12. Bot: "Payment confirmed! Order #123 complete. Thank you!"

**Assertions**:
- Total messages from step 1 to step 10: ≤ 10
- All product displays use interactive format
- No message echoes customer text
- No disclaimer phrases
- Order total matches product price
- PaymentRequest created with correct amount
- Order status updated to PAID after callback

**Multi-Day Conversation**:
1. Day 1: Customer browses, doesn't buy
2. Day 2: Customer returns, says "I want that perfume"
3. Bot: Resolves reference to Day 1 product OR asks for clarification
4. Verify: No "we haven't talked" message

**Language Switching**:
1. Customer: "Hello" (English)
2. Bot: Responds in English
3. Customer: "Nataka perfume" (Swahili)
4. Bot: Responds in Swahili
5. Verify: Language switches immediately


## Implementation Notes

### Critical Path (Must Fix First)

1. **Echo Prevention** - Immediate impact on conversation quality
2. **Interactive Message Routing** - Code exists, just needs to be called
3. **Disclaimer Removal** - Quick win for confidence
4. **Checkout State Machine** - Core sales completion blocker

### Phase 1: Foundation (Week 1)
- Implement EchoPreventionFilter
- Implement DisclaimerRemover
- Implement ResponseValidator
- Wire into existing message processing pipeline
- Add feature flags to AgentConfiguration

### Phase 2: Interactive Messages (Week 1)
- Fix InteractiveMessageRouter to always use rich format
- Add fallback handling for API failures
- Test with real WhatsApp API
- Add logging for debugging

### Phase 3: Context & Sessions (Week 2)
- Implement SessionAwareContextLoader
- Add session boundary detection
- Modify context building to use full history
- Add session summaries

### Phase 4: Checkout Flow (Week 2)
- Implement CheckoutStateMachine
- Wire into message processing
- Integrate with payment service
- Add CheckoutSession model

### Phase 5: Reference Resolution (Week 3)
- Enhance ReferenceResolutionService
- Support multiple reference types
- Add context expiration
- Test with real conversations

### Phase 6: Testing & Polish (Week 3)
- Write property-based tests
- Run integration tests
- Fix bugs
- Performance optimization
- Documentation

### Performance Considerations

**Echo Detection**:
- Use simple string matching first (O(n))
- Only use fuzzy matching if needed (O(n²))
- Cache customer message for comparison
- Timeout after 100ms

**Context Loading**:
- Index on (conversation_id, created_at)
- Use select_related for related objects
- Cache session summaries in Redis (1 hour TTL)
- Limit to 50 messages max for context

**Interactive Messages**:
- Pre-build message templates
- Cache product images
- Batch product queries
- Use connection pooling for WhatsApp API

**Checkout State**:
- Store state in ConversationContext (no extra query)
- Use database transactions for order creation
- Cache payment credentials in Redis

### Backward Compatibility

- All new features behind feature flags
- Graceful fallback to existing behavior
- No breaking changes to existing APIs
- Maintain existing message format support

### Monitoring & Alerts

**Metrics to Track**:
- Echo detection rate (should be <5%)
- Disclaimer removal rate (should decrease over time)
- Interactive message success rate (target >95%)
- Checkout completion rate (target >60%)
- Average messages to payment (target <5)
- Payment success rate (target >80%)

**Alerts**:
- Echo detection rate >10%
- Interactive message failure rate >10%
- Checkout abandonment rate >50%
- Payment failure rate >30%
- Response validation failure rate >5%

### Security Considerations

- Validate all customer input before processing
- Sanitize phone numbers before STK push
- Never log payment credentials
- Rate limit payment attempts (3 per 10 minutes)
- Verify payment callbacks with signatures

### Rollout Strategy

1. **Canary**: Enable for 1 test tenant
2. **Beta**: Enable for 10 willing tenants
3. **Gradual**: Enable for 25% of tenants
4. **Full**: Enable for all tenants
5. **Monitor**: Track metrics at each stage
6. **Rollback**: Feature flags allow instant disable

