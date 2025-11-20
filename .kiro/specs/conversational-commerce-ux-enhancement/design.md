# Design Document

## Overview

This design addresses critical UX failures in the WabotIQ conversational commerce bot that prevent smooth inquiry-to-sale journeys. The current system suffers from context loss, poor product discovery, lack of rich media, inconsistent conversation flow, and memory failures. This design transforms the bot into an intelligent sales assistant that guides customers from inquiry to purchase efficiently.

### Core Problems Identified

1. **Context Loss**: Bot references old conversations instead of recent context (e.g., user says "1" after seeing products, bot references unrelated old message)
2. **Poor Discovery**: Users must play "twenty questions" before seeing actual products
3. **No Rich Media**: Products shown as plain text instead of WhatsApp cards with buttons
4. **Message Fragmentation**: Multiple rapid messages get separate responses instead of one coherent reply
5. **Memory Failure**: Bot claims "we haven't had a conversation yet" when clear history exists
6. **Language Inconsistency**: Random switching between English and Swahili mid-conversation
7. **Unclear Identity**: Bot introduces itself as generic "Assistant" instead of business name
8. **Hallucination**: Bot generates information not grounded in actual data
9. **Payment Dead End**: Bot can't help with payment and doesn't guide to checkout
10. **Legacy Code**: Unused code cluttering the system

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     WhatsApp Customer                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Message Harmonization Layer                     │
│  - Detects rapid message bursts (< 3 seconds)               │
│  - Buffers and combines messages                            │
│  - Shows typing indicator                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Enhanced Context Builder                        │
│  - Loads FULL conversation history                          │
│  - Maintains short-term reference memory (last 5 lists)     │
│  - Tracks language preference                               │
│  - Stores last viewed items                                 │
│  - Builds tenant-branded persona                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Intent & Reference Resolver                     │
│  - Resolves positional references ("1", "first", "last")   │
│  - Detects multiple intents                                 │
│  - Prioritizes intents                                      │
│  - Validates against actual data                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Smart Product Discovery                         │
│  - Proactive suggestions based on context                   │
│  - Immediate product display (no narrowing required)        │
│  - Fuzzy matching for queries                               │
│  - Category-aware recommendations                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Response Generator                          │
│  - Grounded in actual data only                             │
│  - Consistent language throughout                           │
│  - Branded persona                                          │
│  - Structured multi-intent responses                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Rich Message Formatter                          │
│  - Product cards with images and buttons                    │
│  - Service cards with booking buttons                       │
│  - WhatsApp lists for multiple items                        │
│  - Checkout links and payment guidance                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     WhatsApp Customer                        │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Message Harmonization Service

**Purpose**: Combine rapid-fire messages into single conversational turn

**Interface**:
```python
class MessageHarmonizationService:
    def should_buffer_message(
        self,
        conversation: Conversation,
        message: Message
    ) -> bool:
        """Check if message should be buffered for harmonization"""
        
    def get_harmonized_messages(
        self,
        conversation: Conversation,
        wait_seconds: int = 3
    ) -> List[Message]:
        """Get all messages in current burst"""
        
    def combine_messages(
        self,
        messages: List[Message]
    ) -> str:
        """Combine multiple messages into single text"""
```

**Implementation Strategy**:
- Use MessageQueue model (already exists) with status tracking
- Add `last_message_time` to ConversationContext
- If new message arrives within 3 seconds of last, mark for buffering
- Show typing indicator via WhatsApp API
- After 3 seconds of silence, process all buffered messages together

### 2. Reference Context Manager

**Purpose**: Resolve positional references like "1", "the first one", "last"

**Interface**:
```python
class ReferenceContextManager:
    def store_list_context(
        self,
        conversation: Conversation,
        list_type: str,  # 'products', 'services', 'appointments'
        items: List[Any],
        ttl_minutes: int = 5
    ) -> str:  # Returns context_id
        """Store a list for future reference"""
        
    def resolve_reference(
        self,
        conversation: Conversation,
        reference: str  # "1", "first", "last", "the blue one"
    ) -> Optional[Dict[str, Any]]:
        """Resolve a reference to actual item"""
        
    def get_active_context(
        self,
        conversation: Conversation
    ) -> Optional[ReferenceContext]:
        """Get most recent active context"""
```

**Data Model** (already exists as `ReferenceContext`):
```python
class ReferenceContext(BaseModel):
    conversation = ForeignKey(Conversation)
    context_id = CharField(max_length=50)
    list_type = CharField(choices=['products', 'services', ...])
    items = JSONField()  # [{'id': '...', 'title': '...', 'position': 1}, ...]
    expires_at = DateTimeField()
```

### 3. Enhanced Context Builder

**Modifications to existing `ContextBuilderService`**:

```python
class ContextBuilderService:
    def build_context(
        self,
        conversation: Conversation,
        message: Message,
        tenant,
        max_tokens: Optional[int] = None
    ) -> AgentContext:
        # CHANGES:
        # 1. Load ALL conversation history (not just last 20)
        # 2. Include conversation summary if exists
        # 3. Load active reference contexts
        # 4. Detect and store language preference
        # 5. Include tenant branding info
        # 6. Add proactive suggestions
```

### 4. Conversation History Service

**Purpose**: Ensure full conversation memory is available

**Interface**:
```python
class ConversationHistoryService:
    def get_full_history(
        self,
        conversation: Conversation,
        include_system_messages: bool = False
    ) -> List[Message]:
        """Get complete conversation history"""
        
    def summarize_history(
        self,
        conversation: Conversation,
        max_tokens: int = 500
    ) -> str:
        """Generate summary of conversation for context"""
        
    def get_conversation_topics(
        self,
        conversation: Conversation
    ) -> List[str]:
        """Extract main topics discussed"""
```

### 5. Smart Product Discovery Service

**Purpose**: Proactively suggest products without requiring narrowing

**Interface**:
```python
class SmartProductDiscoveryService:
    def get_immediate_suggestions(
        self,
        tenant,
        query: Optional[str] = None,
        context: Optional[AgentContext] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Get products to show immediately"""
        # Returns: {
        #   'products': [Product, ...],
        #   'reasoning': 'Why these products',
        #   'priority': 'high|medium|low'
        # }
        
    def get_contextual_recommendations(
        self,
        tenant,
        customer,
        conversation_context: ConversationContext
    ) -> List[Product]:
        """Get recommendations based on conversation context"""
```

### 6. Language Consistency Manager

**Purpose**: Maintain consistent language throughout conversation

**Interface**:
```python
class LanguageConsistencyManager:
    def detect_language(
        self,
        text: str
    ) -> str:  # 'en', 'sw', 'mixed'
        """Detect language of message"""
        
    def get_conversation_language(
        self,
        conversation: Conversation
    ) -> str:
        """Get established language for conversation"""
        
    def set_conversation_language(
        self,
        conversation: Conversation,
        language: str
    ) -> None:
        """Set language preference"""
```

**Data Model** (already exists as `LanguagePreference`):
```python
class LanguagePreference(BaseModel):
    conversation = OneToOneField(Conversation)
    primary_language = CharField(default='en')
    language_usage = JSONField(default=dict)
```

### 7. Branded Persona Builder

**Purpose**: Build tenant-specific bot persona

**Interface**:
```python
class BrandedPersonaBuilder:
    def build_system_prompt(
        self,
        tenant,
        agent_config: AgentConfiguration,
        language: str = 'en'
    ) -> str:
        """Build system prompt with tenant branding"""
        # Includes:
        # - Business name
        # - Bot name (from agent_config or business name + "Assistant")
        # - What bot CAN do
        # - What bot CANNOT do
        # - Language to use
```

### 8. Grounded Response Validator

**Purpose**: Ensure responses only contain factual information

**Interface**:
```python
class GroundedResponseValidator:
    def validate_response(
        self,
        response: str,
        context: AgentContext
    ) -> Tuple[bool, List[str]]:
        """Validate response is grounded in context"""
        # Returns: (is_valid, list_of_issues)
        
    def extract_claims(
        self,
        response: str
    ) -> List[str]:
        """Extract factual claims from response"""
        
    def verify_claim(
        self,
        claim: str,
        context: AgentContext
    ) -> bool:
        """Verify a claim against context data"""
```

### 9. Enhanced Rich Message Builder

**Modifications to existing `RichMessageBuilder`**:

```python
class RichMessageBuilder:
    def build_product_list(
        self,
        products: List[Product],
        context_id: str,
        show_prices: bool = True,
        show_stock: bool = True
    ) -> WhatsAppMessage:
        """Build WhatsApp list message for products"""
        # Uses WhatsApp List Message format
        # Stores context for reference resolution
        
    def build_checkout_message(
        self,
        order_summary: Dict[str, Any],
        payment_link: str
    ) -> WhatsAppMessage:
        """Build message with checkout link and order summary"""
```

### 10. Code Cleanup Service

**Purpose**: Identify and remove unused code

**Interface**:
```python
class CodeCleanupAnalyzer:
    def find_unused_imports(
        self,
        directory: str
    ) -> List[str]:
        """Find unused imports across codebase"""
        
    def find_unused_functions(
        self,
        directory: str
    ) -> List[str]:
        """Find functions never called"""
        
    def find_duplicate_code(
        self,
        directory: str
    ) -> List[Tuple[str, str]]:
        """Find duplicate code blocks"""
```

## Data Models

### Modifications to Existing Models

#### ConversationContext
```python
class ConversationContext(BaseModel):
    # ADD:
    last_message_time = DateTimeField(null=True)
    message_buffer = JSONField(default=list)  # For harmonization
    language_locked = BooleanField(default=False)
    
    # MODIFY:
    conversation_summary = TextField()  # Ensure this is populated
```

#### AgentConfiguration
```python
class AgentConfiguration(BaseModel):
    # ADD:
    use_business_name_as_identity = BooleanField(default=True)
    custom_bot_greeting = TextField(blank=True)
    enable_message_harmonization = BooleanField(default=True)
    harmonization_wait_seconds = IntegerField(default=3)
    enable_immediate_product_display = BooleanField(default=True)
    max_products_to_show = IntegerField(default=5)
```

### New Models

#### MessageHarmonizationLog
```python
class MessageHarmonizationLog(BaseModel):
    """Track message harmonization for analytics"""
    conversation = ForeignKey(Conversation)
    message_ids = JSONField()  # List of message IDs combined
    combined_text = TextField()
    wait_time_ms = IntegerField()
    response_generated = TextField()
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Recent context priority
*For any* conversation and customer reference (like "1", "first", "the blue one"), the system should resolve the reference using the most recent list context (within last 5 minutes) before considering older contexts
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Immediate product visibility
*For any* product inquiry or general "what do you have" question, the system should display at least one actual product in the response without requiring category narrowing
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 3: Rich message for product lists
*For any* response containing 2 or more products, the system should format them as WhatsApp interactive messages (list or cards) with action buttons
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

### Property 4: Message burst harmonization
*For any* sequence of messages from the same customer within 3 seconds, the system should process them as a single conversational turn and generate one comprehensive response
**Validates: Requirements 4.1, 4.2, 4.3**

### Property 5: Checkout guidance completeness
*For any* customer expressing purchase intent, the system should provide a complete path to checkout including product selection, quantity confirmation, and payment link or instructions
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

### Property 6: Language consistency
*For any* conversation, once a language is detected from customer messages, all subsequent bot responses should use that same language until the customer explicitly switches
**Validates: Requirements 6.1, 6.2, 6.3, 6.5**

### Property 7: Branded identity
*For any* bot introduction or identity question, the response should include the tenant's business name and never use generic terms like "Assistant" alone
**Validates: Requirements 7.1, 7.2, 7.3**

### Property 8: Factual grounding
*For any* bot response containing product information (price, availability, features), all stated facts should be verifiable against the actual product data in the database
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

### Property 9: Conversation history recall
*For any* conversation with at least one prior message, when asked "what have we talked about", the system should retrieve and summarize actual topics from the conversation history
**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

### Property 10: Intent inference from context
*For any* vague customer message, the system should use the last 3 messages of conversation context to infer intent before asking clarifying questions
**Validates: Requirements 10.1, 10.4, 10.5**

## Error Handling

### Context Resolution Errors
- **Missing Reference Context**: If customer says "1" but no recent list exists, respond with "I'm not sure which item you're referring to. Let me show you our products again."
- **Expired Context**: If reference context expired (>5 minutes), treat as new inquiry
- **Ambiguous Reference**: If "the blue one" matches multiple items, show all matches as list

### Message Harmonization Errors
- **Buffer Overflow**: If >10 messages in 3 seconds, process immediately to prevent delays
- **Timeout**: If waiting >5 seconds total, process what's buffered
- **Processing Failure**: Fall back to processing messages individually

### Product Discovery Errors
- **No Products Found**: Show all available products with message "I couldn't find that specific item, but here's what we have"
- **Empty Catalog**: Respond with "We're currently updating our catalog. Please check back soon or speak with a human agent."

### Language Detection Errors
- **Ambiguous Language**: Default to tenant's primary language setting
- **Mixed Language**: Use the language of the most recent customer message

### Rich Message Errors
- **WhatsApp API Failure**: Fall back to plain text with numbered list
- **Image Load Failure**: Send message without image, include text description
- **Button Limit Exceeded**: Convert to list message

### Grounding Validation Errors
- **Unverifiable Claim**: Remove claim from response or add "Please confirm with our team"
- **Contradictory Data**: Use most recent data, log inconsistency
- **Missing Data**: Explicitly state "I don't have that information" instead of guessing

## Testing Strategy

### Unit Testing

**Context Resolution Tests**:
- Test resolving "1", "2", "first", "last" with various list sizes
- Test expired context handling
- Test multiple active contexts (prioritize most recent)
- Test ambiguous references

**Message Harmonization Tests**:
- Test buffering logic with various timing scenarios
- Test combining messages with different content types
- Test buffer overflow handling
- Test timeout scenarios

**Language Detection Tests**:
- Test English, Swahili, mixed language detection
- Test language persistence across conversation
- Test language switching mid-conversation

**Product Discovery Tests**:
- Test immediate product display for vague queries
- Test fuzzy matching for misspelled product names
- Test empty catalog handling
- Test category-based filtering

**Grounding Validation Tests**:
- Test claim extraction from responses
- Test verification against product data
- Test handling of unverifiable claims

### Property-Based Testing

We'll use **Hypothesis** (Python property-based testing library) for universal property validation.

**Property Test 1: Recent Context Priority**
```python
@given(
    conversation=conversations(),
    reference_contexts=st.lists(reference_contexts(), min_size=2, max_size=5),
    reference=st.sampled_from(["1", "2", "first", "last"])
)
def test_recent_context_priority(conversation, reference_contexts, reference):
    """Property: Most recent context is always used for resolution"""
    # Setup: Create contexts with different timestamps
    # Action: Resolve reference
    # Assert: Resolved item comes from most recent context
```

**Property Test 2: Immediate Product Visibility**
```python
@given(
    tenant=tenants(),
    query=st.one_of(st.none(), st.text(min_size=1, max_size=100))
)
def test_immediate_product_visibility(tenant, query):
    """Property: Product queries always show at least one product"""
    # Assume: Tenant has at least one active product
    # Action: Get product suggestions
    # Assert: At least one product returned
```

**Property Test 3: Message Harmonization**
```python
@given(
    conversation=conversations(),
    messages=st.lists(st.text(min_size=1, max_size=200), min_size=2, max_size=5),
    time_gaps=st.lists(st.floats(min_value=0.1, max_value=2.9), min_size=1)
)
def test_message_harmonization(conversation, messages, time_gaps):
    """Property: Rapid messages get one response"""
    # Setup: Create messages with small time gaps
    # Action: Process messages
    # Assert: Only one response generated
```

**Property Test 4: Language Consistency**
```python
@given(
    conversation=conversations(),
    initial_language=st.sampled_from(['en', 'sw']),
    message_count=st.integers(min_value=2, max_value=10)
)
def test_language_consistency(conversation, initial_language, message_count):
    """Property: Bot maintains language throughout conversation"""
    # Setup: Set initial language
    # Action: Generate multiple responses
    # Assert: All responses in same language
```

**Property Test 5: Factual Grounding**
```python
@given(
    product=products(),
    response_template=st.text()
)
def test_factual_grounding(product, response_template):
    """Property: Product info in responses matches database"""
    # Setup: Generate response mentioning product
    # Action: Extract claims about product
    # Assert: All claims verifiable against product data
```

### Integration Testing

**End-to-End Conversation Tests**:
1. Customer asks "what do you have" → Bot shows products immediately
2. Customer says "1" → Bot resolves to correct product from list
3. Customer sends "I want this" then "size large" → Bot harmonizes and responds once
4. Customer asks "what have we talked about" → Bot summarizes conversation
5. Customer switches from English to Swahili → Bot adapts language

**WhatsApp Integration Tests**:
- Test rich message rendering in WhatsApp
- Test button interactions
- Test list message interactions
- Test fallback to plain text

**Multi-Tenant Tests**:
- Test tenant isolation in context resolution
- Test tenant-specific branding
- Test tenant-specific product catalogs

## Implementation Notes

### Phase 1: Foundation (Critical Path)
1. Message harmonization service
2. Reference context manager
3. Enhanced conversation history loading
4. Language consistency manager

### Phase 2: Discovery & UX
1. Smart product discovery
2. Enhanced rich message builder
3. Branded persona builder
4. Checkout guidance

### Phase 3: Quality & Cleanup
1. Grounded response validator
2. Code cleanup
3. Comprehensive testing
4. Performance optimization

### Performance Considerations
- Cache reference contexts in Redis (5-minute TTL)
- Use database indexes on conversation_id + created_at for history queries
- Batch product queries with select_related/prefetch_related
- Limit conversation history to last 50 messages for context (use summary for older)

### Backward Compatibility
- All new features behind feature flags in AgentConfiguration
- Graceful fallback to existing behavior if new services fail
- Maintain existing API contracts

### Monitoring & Observability
- Log all reference resolutions with success/failure
- Track message harmonization metrics (buffer size, wait time)
- Monitor language detection accuracy
- Track rich message usage vs. fallback rates
- Alert on high grounding validation failure rates
