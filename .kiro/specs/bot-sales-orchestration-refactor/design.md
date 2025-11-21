# Design Document

## Overview

This design document specifies a fundamental architectural refactor of the Tulia AI conversational bot from an LLM-heavy, hallucination-prone system into a deterministic, sales-oriented agent. The new architecture implements a hybrid approach where:

1. **Deterministic business logic** handles all critical decisions (products, orders, payments, bookings)
2. **LLMs serve only as a thin layer** for NLU (intent classification, slot extraction) and natural language formatting
3. **Rule-based systems** handle the majority of interactions (menu selections, confirmations, structured flows)
4. **RAG (Retrieval-Augmented Generation)** provides grounded FAQ answers from tenant documents
5. **Cost optimization** keeps LLM usage under $10/tenant/month through smart routing and caching

### Key Design Principles

1. **LLM is not the source of truth** - Only database records, RAG documents, and payment callbacks are authoritative
2. **Never invent data** - Products, services, prices, policies must come from actual data sources
3. **Small models only** - Use GPT-4o-mini, Qwen 2.5 7B, or Gemini Flash; avoid large expensive models
4. **Intent-driven routing** - Use a constrained intent schema with deterministic handlers
5. **Short, focused responses** - Guide customers to the next action quickly
6. **Tenant isolation** - All queries are tenant-scoped; no cross-tenant data leakage

### Current Problems Being Solved

- **Hallucination**: Bot invents products, prices, and policies not in the database
- **High costs**: Excessive LLM usage for simple tasks that could be rule-based
- **Poor conversion**: Long, meandering conversations that don't lead to sales
- **Unpredictable behavior**: LLM-driven logic makes testing and debugging difficult
- **Context loss**: Bot forgets recent interactions and makes irrelevant suggestions

## Architecture

### High-Level System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     WhatsApp Customer                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Twilio Webhook Handler                              │
│  - Verify signature                                              │
│  - Resolve tenant                                                │
│  - Create Message record                                         │
│  - Enqueue Celery task                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Message Processing Task (Celery)                    │
│  - Load conversation context                                     │
│  - Normalize message                                             │
│  - Detect intent                                                 │
│  - Route to business logic                                       │
│  - Format response                                               │
│  - Send via Twilio                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Intent Detection Engine                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Rule-Based Classification (60-80% of messages)       │  │
│  │     - Keyword matching (EN/SW/Sheng)                     │  │
│  │     - Numeric menu replies                               │  │
│  │     - WhatsApp button/list payloads                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. LLM-Based Classification (20-40% of messages)        │  │
│  │     - Small model (GPT-4o-mini/Qwen/Gemini)             │  │
│  │     - Structured JSON output                             │  │
│  │     - Confidence scoring                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  3. Context-Aware Adjustment                             │  │
│  │     - Check current_flow                                 │  │
│  │     - Check awaiting_response                            │  │
│  │     - Resolve references to last_menu                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Business Logic Router                               │
│  - Maps intent → handler function                                │
│  - NO LLM calls inside handlers                                  │
│  - Pure Python business logic                                    │
│  - Database queries only                                         │
│  - Returns structured BotAction                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Intent Handlers (Deterministic)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  BROWSE_PRODUCTS → Query DB, return product list         │  │
│  │  PLACE_ORDER → Create Order, ask for payment             │  │
│  │  BOOK_APPOINTMENT → Check availability, create booking   │  │
│  │  PAYMENT_HELP → Initiate payment flow                    │  │
│  │  GENERAL_FAQ → Call RAG pipeline                         │  │
│  │  REQUEST_HUMAN → Tag conversation, stop bot              │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Response Formatter                                  │
│  - Format text in detected language                              │
│  - Build WhatsApp rich messages (lists, buttons, cards)          │
│  - Add payment links                                             │
│  - Store last_menu in context                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Twilio API → WhatsApp Customer                      │
└─────────────────────────────────────────────────────────────────┘
```

### Parallel Systems

```
┌─────────────────────────────────────────────────────────────────┐
│              RAG Pipeline (for FAQ/Policy questions)             │
│  - Pinecone vector search (tenant namespace)                     │
│  - Retrieve top 5-8 chunks                                       │
│  - Small LLM with strict grounding prompt                        │
│  - Return answer or "I'm not sure"                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Payment Orchestration                               │
│  - M-Pesa STK Push                                               │
│  - M-Pesa Manual (Paybill/Till)                                  │
│  - Card Payments (Paystack/Stripe/Pesapal)                       │
│  - Webhook callbacks                                             │
│  - Status updates                                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Multi-Model LLM Router                              │
│  - Select cheapest model for task                                │
│  - Track token usage per tenant                                  │
│  - Enforce budget caps                                           │
│  - Fallback to rules when budget exceeded                        │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Intent Detection Engine

**Purpose**: Classify customer messages into a constrained set of intents using rules first, LLMs as fallback

**Intent Schema**:
```python
class Intent(str, Enum):
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
```

**Interface**:
```python
@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    slots: Dict[str, Any]
    language: List[str]  # ['en'], ['sw'], ['sheng'], ['en', 'sw']
    needs_clarification: bool
    resolved_from_context: bool  # True if resolved from menu/button

class IntentDetectionEngine:
    def detect_intent(
        self,
        message: Message,
        context: ConversationContext,
        tenant: Tenant
    ) -> IntentResult:
        """
        Detect intent using rules first, LLM as fallback.
        
        Steps:
        1. Check if awaiting_response - use context to interpret
        2. Check for numeric reply - resolve from last_menu
        3. Check for WhatsApp button/list payload - direct mapping
        4. Try rule-based keyword matching
        5. Fall back to small LLM if needed
        """
        
    def _rule_based_classification(
        self,
        text: str,
        context: ConversationContext
    ) -> Optional[IntentResult]:
        """Use keyword patterns and regex"""
        
    def _llm_classification(
        self,
        text: str,
        context: ConversationContext,
        tenant: Tenant
    ) -> IntentResult:
        """Call small LLM with structured output"""
        
    def _extract_slots(
        self,
        text: str,
        intent: Intent,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Extract structured attributes using rules + LLM"""
```

**Rule-Based Patterns**:
```python
INTENT_PATTERNS = {
    Intent.BROWSE_PRODUCTS: [
        r'\b(browse|view|see|show|what|nini|gani)\b.*\b(products|items|goods|bidhaa)\b',
        r'\b(what do you (have|sell))\b',
        r'\b(naona nini|una nini|mna nini)\b',
    ],
    Intent.BROWSE_SERVICES: [
        r'\b(services|service|salon|spa|clinic)\b',
        r'\b(nataka service|services ziko)\b',
        r'\b(book|appointment|slot)\b',
    ],
    Intent.PLACE_ORDER: [
        r'\b(order|buy|purchase|nunua|weka kwa cart)\b',
        r'\b(nataka kununua|nataka)\b',
        r'\b(add to cart|checkout)\b',
    ],
    Intent.PAYMENT_HELP: [
        r'\b(pay|payment|mpesa|lipa|malipo)\b',
        r'\b(paybill|till|card|visa|mastercard)\b',
        r'\b(how (do|can) i pay)\b',
    ],
    Intent.REQUEST_HUMAN: [
        r'\b(human|person|agent|representative|mtu)\b',
        r'\b(ongea na mtu|talk to someone)\b',
    ],
}
```

### 2. Business Logic Router

**Purpose**: Map intents to deterministic handler functions that execute business logic without LLMs

**Interface**:
```python
@dataclass
class BotAction:
    type: str  # "TEXT", "LIST", "BUTTONS", "PRODUCT_CARDS", "HANDOFF"
    text: Optional[str] = None
    rich_payload: Optional[Dict[str, Any]] = None
    new_context: Optional[Dict[str, Any]] = None
    side_effects: List[str] = field(default_factory=list)  # ["order_created", "payment_initiated"]

class BusinessLogicRouter:
    def route(
        self,
        intent_result: IntentResult,
        context: ConversationContext,
        tenant: Tenant,
        customer: Customer
    ) -> BotAction:
        """
        Route intent to appropriate handler.
        Returns structured action for response formatter.
        """
        handler = self.INTENT_HANDLERS.get(intent_result.intent)
        if not handler:
            return self._handle_unknown(intent_result, context)
        
        return handler(intent_result, context, tenant, customer)
    
    INTENT_HANDLERS = {
        Intent.GREET: handle_greet,
        Intent.BROWSE_PRODUCTS: handle_browse_products,
        Intent.BROWSE_SERVICES: handle_browse_services,
        Intent.PRODUCT_DETAILS: handle_product_details,
        Intent.SERVICE_DETAILS: handle_service_details,
        Intent.PLACE_ORDER: handle_place_order,
        Intent.BOOK_APPOINTMENT: handle_book_appointment,
        Intent.CHECK_ORDER_STATUS: handle_check_order_status,
        Intent.CHECK_APPOINTMENT_STATUS: handle_check_appointment_status,
        Intent.ASK_DELIVERY_FEES: handle_delivery_fees,
        Intent.ASK_RETURN_POLICY: handle_return_policy,
        Intent.PAYMENT_HELP: handle_payment_help,
        Intent.REQUEST_HUMAN: handle_request_human,
        Intent.GENERAL_FAQ: handle_general_faq,
        Intent.SMALL_TALK: handle_small_talk,
        Intent.UNKNOWN: handle_unknown,
    }
```

**Example Handler Implementation**:
```python
def handle_browse_products(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Show products from database.
    NO LLM calls.
    """
    # Extract filters from slots
    category = intent_result.slots.get('category')
    budget_max = intent_result.slots.get('budget_max')
    
    # Query database (tenant-scoped)
    products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        deleted_at__isnull=True
    )
    
    if category:
        products = products.filter(category__icontains=category)
    if budget_max:
        products = products.filter(price__lte=budget_max)
    
    products = products[:10]  # Limit to 10
    
    if not products.exists():
        # No products found - show all
        products = Product.objects.filter(
            tenant=tenant,
            is_active=True,
            deleted_at__isnull=True
        )[:10]
        
        return BotAction(
            type="PRODUCT_CARDS",
            text="Hatujapata hiyo category, lakini hizi ni bidhaa zetu:",
            rich_payload={
                "products": [serialize_product(p) for p in products]
            },
            new_context={
                "last_menu": {
                    "type": "products",
                    "items": [{"id": str(p.id), "position": i+1} for i, p in enumerate(products)]
                },
                "current_flow": "browsing_products"
            }
        )
    
    return BotAction(
        type="PRODUCT_CARDS",
        text="Hizi ni bidhaa zetu:",
        rich_payload={
            "products": [serialize_product(p) for p in products]
        },
        new_context={
            "last_menu": {
                "type": "products",
                "items": [{"id": str(p.id), "position": i+1} for i, p in enumerate(products)]
            },
            "current_flow": "browsing_products"
        }
    )
```

### 3. Conversation Context Manager

**Purpose**: Track conversation state, flow, and recent interactions

**Data Model**:
```python
class ConversationContext(BaseModel):
    """Extended from existing model"""
    conversation = OneToOneField(Conversation)
    
    # Flow state
    current_flow = CharField(max_length=50, blank=True)  # "browsing_products", "checkout", "booking"
    awaiting_response = BooleanField(default=False)
    last_question = TextField(blank=True)
    
    # Reference resolution
    last_menu = JSONField(default=dict)  # {"type": "products", "items": [{"id": "...", "position": 1}]}
    last_menu_timestamp = DateTimeField(null=True)
    
    # Language
    detected_language = JSONField(default=list)  # ["en"], ["sw"], ["sheng"]
    
    # Summary
    conversation_summary = TextField(blank=True)
    key_facts = JSONField(default=dict)  # {"product_interest": "jackets", "budget": 50000}
    
    # Metadata
    metadata = JSONField(default=dict)
```

**Interface**:
```python
class ConversationContextManager:
    def load_or_create(
        self,
        conversation: Conversation
    ) -> ConversationContext:
        """Load existing context or create new one"""
        
    def update_from_action(
        self,
        context: ConversationContext,
        action: BotAction
    ) -> ConversationContext:
        """Update context based on bot action"""
        
    def resolve_menu_reference(
        self,
        context: ConversationContext,
        reference: str  # "1", "2", "first", "last"
    ) -> Optional[Dict[str, Any]]:
        """Resolve numeric/positional reference to menu item"""
        
    def is_menu_expired(
        self,
        context: ConversationContext,
        ttl_minutes: int = 5
    ) -> bool:
        """Check if last_menu is still valid"""
```

### 4. RAG Pipeline

**Purpose**: Provide grounded FAQ answers from tenant documents

**Interface**:
```python
class RAGPipeline:
    def answer_question(
        self,
        question: str,
        tenant: Tenant,
        context: ConversationContext,
        top_k: int = 5
    ) -> str:
        """
        Answer question using RAG.
        
        Steps:
        1. Generate query embedding
        2. Search Pinecone (tenant namespace)
        3. Retrieve top_k chunks
        4. Call small LLM with strict grounding prompt
        5. Validate answer is grounded
        6. Return answer or "I'm not sure"
        """
        
    def _retrieve_chunks(
        self,
        query: str,
        tenant: Tenant,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Search Pinecone for relevant chunks"""
        
    def _generate_grounded_answer(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        language: List[str]
    ) -> str:
        """Call LLM with strict prompt to answer from chunks only"""
        
    def _validate_grounding(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """Verify answer contains only information from chunks"""
```

**Grounding Prompt Template**:
```
You are a helpful assistant for {business_name}.

Answer the customer's question using ONLY the information provided below.

Context:
{chunks}

Rules:
1. Answer ONLY from the context above
2. If the context doesn't contain the answer, say "I'm not sure about that. Let me connect you with someone from our team."
3. Keep your answer short and focused
4. Use {language} language
5. Never invent information

Question: {question}

Answer:
```

### 5. Payment Orchestration Service

**Purpose**: Handle all payment flows deterministically

**Interface**:
```python
class PaymentOrchestrationService:
    def initiate_mpesa_stk(
        self,
        order: Order,
        phone_number: str,
        tenant: Tenant
    ) -> PaymentRequest:
        """
        Initiate M-Pesa STK push.
        
        Steps:
        1. Validate phone number format
        2. Create PaymentRequest with PENDING status
        3. Call M-Pesa API with tenant credentials
        4. Return PaymentRequest
        """
        
    def initiate_card_payment(
        self,
        order: Order,
        provider: str,  # "paystack", "stripe", "pesapal"
        tenant: Tenant
    ) -> Tuple[PaymentRequest, str]:
        """
        Generate card payment link.
        
        Returns: (PaymentRequest, payment_link)
        """
        
    def handle_mpesa_callback(
        self,
        callback_data: Dict[str, Any],
        tenant: Tenant
    ) -> None:
        """
        Process M-Pesa callback.
        
        Steps:
        1. Find PaymentRequest by reference
        2. Update status based on result
        3. Update Order status if successful
        4. Send WhatsApp confirmation
        """
        
    def handle_card_callback(
        self,
        provider: str,
        callback_data: Dict[str, Any],
        tenant: Tenant
    ) -> None:
        """Process card payment webhook"""
```

### 6. Multi-Model LLM Router

**Purpose**: Select the cheapest viable model and track costs

**Interface**:
```python
class LLMRouter:
    def classify_intent(
        self,
        text: str,
        context: Dict[str, Any],
        tenant: Tenant
    ) -> Dict[str, Any]:
        """
        Classify intent using small model.
        Returns structured JSON.
        """
        model = self._select_model(task="intent_classification", tenant=tenant)
        result = self._call_model(model, prompt, tenant)
        self._log_usage(tenant, model, result)
        return result
        
    def extract_slots(
        self,
        text: str,
        intent: Intent,
        context: Dict[str, Any],
        tenant: Tenant
    ) -> Dict[str, Any]:
        """Extract structured slots using small model"""
        
    def generate_rag_answer(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        language: List[str],
        tenant: Tenant
    ) -> str:
        """Generate grounded answer from chunks"""
        
    def _select_model(
        self,
        task: str,
        tenant: Tenant
    ) -> str:
        """
        Select model based on:
        1. Task requirements
        2. Tenant budget remaining
        3. Model availability
        
        Preference order:
        1. GPT-4o-mini (cheapest, good quality)
        2. Qwen 2.5 7B (open source, self-hosted option)
        3. Gemini Flash (Google, competitive pricing)
        """
        
    def _log_usage(
        self,
        tenant: Tenant,
        model: str,
        result: Dict[str, Any]
    ) -> None:
        """
        Log token usage and cost.
        
        Creates LLMUsageLog record with:
        - tenant_id
        - model_name
        - task_type
        - input_tokens
        - output_tokens
        - estimated_cost
        - timestamp
        """
```

### 7. WhatsApp Message Formatter

**Purpose**: Build rich WhatsApp messages from BotAction

**Interface**:
```python
class WhatsAppMessageFormatter:
    def format_action(
        self,
        action: BotAction,
        language: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Convert BotAction to Twilio-compatible messages.
        
        Returns list of message payloads to send.
        """
        
    def build_product_list(
        self,
        products: List[Dict[str, Any]],
        language: List[str]
    ) -> Dict[str, Any]:
        """
        Build WhatsApp list message for products.
        
        Format:
        {
            "type": "list",
            "header": {"type": "text", "text": "Our Products"},
            "body": {"text": "Select a product to view details"},
            "action": {
                "button": "View Products",
                "sections": [
                    {
                        "title": "Category Name",
                        "rows": [
                            {"id": "product_123", "title": "Product Name", "description": "KES 5,000"}
                        ]
                    }
                ]
            }
        }
        """
        
    def build_button_message(
        self,
        text: str,
        buttons: List[Dict[str, str]],
        language: List[str]
    ) -> Dict[str, Any]:
        """
        Build WhatsApp button message.
        
        buttons: [{"id": "confirm_yes", "title": "Yes"}, {"id": "confirm_no", "title": "No"}]
        """
        
    def build_payment_message(
        self,
        order_summary: Dict[str, Any],
        payment_link: Optional[str],
        language: List[str]
    ) -> Dict[str, Any]:
        """Build message with order summary and payment link"""
```

## Data Models

### New Models

#### IntentClassificationLog
```python
class IntentClassificationLog(BaseModel):
    """Track intent classification for analytics and debugging"""
    tenant = ForeignKey(Tenant)
    conversation = ForeignKey(Conversation)
    message = ForeignKey(Message)
    
    # Classification
    detected_intent = CharField(max_length=50)
    confidence = FloatField()
    method = CharField(max_length=20)  # "rule", "llm", "context"
    
    # Slots
    extracted_slots = JSONField(default=dict)
    
    # Language
    detected_language = JSONField(default=list)
    
    # Timing
    classification_time_ms = IntegerField()
```

#### LLMUsageLog
```python
class LLMUsageLog(BaseModel):
    """Track LLM usage and costs per tenant"""
    tenant = ForeignKey(Tenant)
    conversation = ForeignKey(Conversation, null=True)
    
    # Model
    model_name = CharField(max_length=100)
    task_type = CharField(max_length=50)  # "intent_classification", "slot_extraction", "rag_answer"
    
    # Usage
    input_tokens = IntegerField()
    output_tokens = IntegerField()
    total_tokens = IntegerField()
    
    # Cost
    estimated_cost_usd = DecimalField(max_digits=10, decimal_places=6)
    
    # Metadata
    prompt_template = TextField(blank=True)
    response_preview = TextField(blank=True)
```

#### PaymentRequest
```python
class PaymentRequest(BaseModel):
    """Track payment attempts"""
    tenant = ForeignKey(Tenant)
    customer = ForeignKey(Customer)
    order = ForeignKey(Order, null=True)
    appointment = ForeignKey(Appointment, null=True)
    
    # Payment details
    amount = DecimalField(max_digits=10, decimal_places=2)
    currency = CharField(max_length=3, default="KES")
    payment_method = CharField(max_length=50)  # "mpesa_stk", "mpesa_manual", "paystack", "stripe", "pesapal"
    
    # Status
    status = CharField(max_length=20)  # "PENDING", "SUCCESS", "FAILED", "CANCELLED"
    
    # Provider details
    provider_reference = CharField(max_length=255, blank=True)
    provider_response = JSONField(default=dict)
    
    # Callback
    callback_received_at = DateTimeField(null=True)
    callback_data = JSONField(default=dict)
```

### Modified Models

#### ConversationContext (Extended)
```python
class ConversationContext(BaseModel):
    # Existing fields...
    
    # NEW: Flow state
    current_flow = CharField(max_length=50, blank=True)
    awaiting_response = BooleanField(default=False)
    last_question = TextField(blank=True)
    
    # NEW: Reference resolution
    last_menu = JSONField(default=dict)
    last_menu_timestamp = DateTimeField(null=True)
    
    # NEW: Language
    detected_language = JSONField(default=list)
    
    # MODIFIED: Ensure these exist
    conversation_summary = TextField(blank=True)
    key_facts = JSONField(default=dict)
```

#### AgentConfiguration (Extended)
```python
class AgentConfiguration(BaseModel):
    # Existing fields...
    
    # NEW: Intent detection
    enable_rule_based_intent = BooleanField(default=True)
    intent_confidence_threshold = FloatField(default=0.65)
    
    # NEW: LLM budget
    monthly_llm_budget_usd = DecimalField(max_digits=10, decimal_places=2, default=10.00)
    llm_budget_exceeded_action = CharField(max_length=20, default="fallback")  # "fallback", "throttle", "stop"
    
    # NEW: Payment
    enable_mpesa_stk = BooleanField(default=True)
    enable_card_payments = BooleanField(default=True)
    
    # NEW: Business hours
    business_hours_start = TimeField(default=time(8, 0))
    business_hours_end = TimeField(default=time(20, 0))
    quiet_hours_start = TimeField(null=True)
    quiet_hours_end = TimeField(null=True)
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Database-grounded product display
*For any* product query, all displayed products should exist in the database with matching prices and availability
**Validates: Requirements 1.1, 5.1, 5.2**

### Property 2: Database-grounded availability checks
*For any* availability query for products or appointments, the returned availability should match the current database state
**Validates: Requirements 1.2, 10.3**

### Property 3: Order integrity
*For any* order creation, all product IDs and prices should be validated against current database records
**Validates: Requirements 1.3, 7.2**

### Property 4: Payment amount integrity
*For any* payment initiation, the payment amount should exactly match the order total calculated from database records
**Validates: Requirements 1.4, 8.2, 9.1**

### Property 5: RAG grounding
*For any* FAQ or policy question, the answer should contain only information present in the retrieved document chunks or express uncertainty
**Validates: Requirements 1.5, 12.2, 12.3, 12.4**

### Property 6: Rule-based intent classification efficiency
*For any* message matching keyword patterns, intent classification should complete without calling an LLM
**Validates: Requirements 2.1**

### Property 7: Numeric selection efficiency
*For any* numeric reply following a menu display, selection resolution should complete without calling an LLM
**Validates: Requirements 2.2, 6.1**

### Property 8: Interactive message efficiency
*For any* WhatsApp button click or list selection, processing should complete without calling an LLM
**Validates: Requirements 2.3, 6.2, 6.3**

### Property 9: LLM fallback behavior
*For any* message that fails rule-based classification, the system should call a small LLM model
**Validates: Requirements 2.4**

### Property 10: Small model constraint
*For any* LLM call for intent detection or FAQ, the system should use only GPT-4o-mini, Qwen 2.5 7B, or Gemini Flash
**Validates: Requirements 2.5, 12.5**

### Property 11: Intent schema constraint
*For any* intent classification result, the intent should be from the predefined set of allowed intents
**Validates: Requirements 3.1**

### Property 12: Slot extraction efficiency
*For any* message containing structured data (numbers, dates, times), slot extraction should use regex/rules before LLMs
**Validates: Requirements 3.2**

### Property 13: Low confidence handling
*For any* intent classification with confidence below threshold, the system should ask clarifying questions or route to REQUEST_HUMAN
**Validates: Requirements 3.4**

### Property 14: Unknown intent handling
*For any* unclassifiable message, the system should return UNKNOWN intent and offer menu or human handoff
**Validates: Requirements 3.5**

### Property 15: Deterministic routing
*For any* classified intent, the Business Logic Router should map to a handler without calling LLMs
**Validates: Requirements 4.1**

### Property 16: Handler output structure
*For any* handler execution, the output should be a structured BotAction with required fields
**Validates: Requirements 4.2**

### Property 17: Tenant-scoped queries
*For any* database query in a handler, the query should include tenant_id filter
**Validates: Requirements 4.3, 15.1, 15.2, 15.3, 15.4**

### Property 18: Context state updates
*For any* handler execution that changes flow, the ConversationContext should be updated with new state
**Validates: Requirements 4.4, 13.2, 13.3**

### Property 19: Graceful error handling
*For any* handler error, the system should log to Sentry and return a user-friendly message
**Validates: Requirements 4.5, 17.1, 17.4**

### Property 20: Product display limits
*For any* product browsing response, the system should display at most 10 products
**Validates: Requirements 5.2**

### Property 21: Menu storage
*For any* menu or list display, the system should store item IDs and positions in ConversationContext.last_menu
**Validates: Requirements 5.3, 13.2**

### Property 22: Empty catalog handling
*For any* tenant with zero products, product browsing should return a graceful message and offer human handoff
**Validates: Requirements 5.5**

### Property 23: Selection resolution
*For any* valid numeric or positional reference, the system should resolve to the correct item from last_menu
**Validates: Requirements 6.1, 6.4**

### Property 24: Invalid selection handling
*For any* invalid selection reference, the system should ask for clarification and re-display the menu
**Validates: Requirements 6.5**

### Property 25: Order creation flow
*For any* product selection confirmation, the system should create an Order with status PENDING_PAYMENT
**Validates: Requirements 7.2**

### Property 26: Payment method routing
*For any* payment method selection, the system should initiate the corresponding payment flow
**Validates: Requirements 7.4**

### Property 27: Payment confirmation
*For any* successful payment callback, the system should update Order status to PAID and send confirmation
**Validates: Requirements 7.5, 8.4, 9.4**

### Property 28: STK push initiation
*For any* M-Pesa STK selection with valid phone number, the system should create PaymentRequest with PENDING status
**Validates: Requirements 8.3**

### Property 29: Payment failure handling
*For any* failed payment callback, the system should update PaymentRequest to FAILED and offer retry or alternatives
**Validates: Requirements 8.5, 9.5**

### Property 30: Card payment link generation
*For any* card payment selection, the system should generate a payment link and send it via WhatsApp
**Validates: Requirements 9.1, 9.3**

### Property 31: Appointment availability checking
*For any* appointment booking request, the system should check availability against business hours and existing appointments
**Validates: Requirements 10.3**

### Property 32: Appointment confirmation
*For any* appointment confirmation, the system should update Appointment status to CONFIRMED
**Validates: Requirements 10.5**

### Property 33: Order status display
*For any* order status check, the system should display the most recent order with complete information
**Validates: Requirements 11.2**

### Property 34: Appointment status display
*For any* appointment status check, the system should display upcoming appointments with complete information
**Validates: Requirements 11.4**

### Property 35: Empty status handling
*For any* status check with no orders or appointments, the system should offer to create new ones
**Validates: Requirements 11.5**

### Property 36: RAG retrieval
*For any* FAQ intent, the system should retrieve chunks from Pinecone using the tenant-specific namespace
**Validates: Requirements 12.1, 15.5**

### Property 37: RAG uncertainty handling
*For any* FAQ query with no relevant chunks or low similarity, the system should express uncertainty and offer human handoff
**Validates: Requirements 12.4**

### Property 38: Context initialization
*For any* new conversation, the system should create ConversationContext with required fields
**Validates: Requirements 13.1**

### Property 39: Awaiting response routing
*For any* customer response when awaiting_response is true, the system should route based on the pending question
**Validates: Requirements 13.4**

### Property 40: Flow completion cleanup
*For any* completed flow, the system should clear current_flow and awaiting_response flags
**Validates: Requirements 13.5**

### Property 41: LLM usage logging
*For any* LLM call, the system should create an LLMUsageLog record with tenant, model, tokens, and cost
**Validates: Requirements 14.1**

### Property 42: Small model preference
*For any* LLM task, the system should select small models (GPT-4o-mini, Qwen, Gemini Flash) over larger models
**Validates: Requirements 14.2**

### Property 43: Context window optimization
*For any* LLM context building, the system should use conversation summary and last 3-5 messages only
**Validates: Requirements 14.3**

### Property 44: Budget enforcement
*For any* tenant exceeding monthly LLM budget, the system should throttle LLM usage and fall back to rules
**Validates: Requirements 14.5**

### Property 45: Rich message formatting
*For any* response with 2-10 products, the system should format as WhatsApp list message
**Validates: Requirements 16.1**

### Property 46: Confirmation button formatting
*For any* confirmation request, the system should use WhatsApp button message with Yes/No options
**Validates: Requirements 16.3**

### Property 47: Rich message fallback
*For any* WhatsApp API failure, the system should fall back to plain text with numbered lists
**Validates: Requirements 16.4**

### Property 48: LLM timeout fallback
*For any* LLM call timeout, the system should fall back to rule-based responses or offer human handoff
**Validates: Requirements 17.2**

### Property 49: Payment API error handling
*For any* payment provider API failure, the system should log error and offer alternative payment methods
**Validates: Requirements 17.3**

### Property 50: Human handoff tagging
*For any* human handoff trigger, the system should tag conversation as needs_human and stop automated responses
**Validates: Requirements 17.5**

### Property 51: Quiet hours handling
*For any* message during quiet hours, the system should respond with quiet hours message and queue conversation
**Validates: Requirements 18.1**

### Property 52: Business hours enforcement
*For any* appointment booking outside business hours, the system should suggest alternative times within business hours
**Validates: Requirements 18.2, 18.3**

### Property 53: Language detection
*For any* customer message, the system should detect language as English, Swahili, Sheng, or mixed
**Validates: Requirements 19.1**

### Property 54: Language consistency
*For any* bot response, the system should use the detected language from the conversation
**Validates: Requirements 19.2**

### Property 55: Language fallback
*For any* ambiguous language detection, the system should default to tenant's configured primary language
**Validates: Requirements 19.4**

### Property 56: Language persistence
*For any* language detection, the system should persist the preference in ConversationContext
**Validates: Requirements 19.5**

## Error Handling

### Intent Classification Errors
- **Low confidence (<0.65)**: Ask clarifying question with specific options or route to REQUEST_HUMAN
- **Ambiguous slots**: Ask for specific information needed (e.g., "Which date did you want?")
- **LLM timeout**: Fall back to showing main menu with product/service categories
- **LLM error**: Log to Sentry, fall back to rule-based classification or show menu

### Business Logic Handler Errors
- **Database query failure**: Log to Sentry, respond with "Sorry, we're experiencing technical issues. Let me connect you with our team."
- **Product not found**: Show alternative products or full catalog
- **Service not found**: Show all available services
- **No availability**: Suggest alternative times or dates
- **Invalid quantity**: Ask for valid quantity (1-100)
- **Invalid phone number**: Ask for correct format (+254...)

### Payment Errors
- **M-Pesa API failure**: Offer manual paybill/till instructions or card payment
- **STK timeout**: Offer to retry or use manual payment
- **Card payment link generation failure**: Offer M-Pesa or manual payment
- **Callback processing error**: Log to Sentry, mark payment as PENDING_REVIEW, notify tenant
- **Amount mismatch**: Log critical error, halt payment, request human review

### RAG Errors
- **Pinecone connection failure**: Respond with "I'm not sure about that. Let me connect you with our team."
- **No chunks found**: Express uncertainty and offer human handoff
- **LLM grounding failure**: Fall back to "I don't have that information. Would you like to speak with someone?"
- **Embedding generation failure**: Log error, offer human handoff

### WhatsApp API Errors
- **Message send failure**: Retry up to 3 times with exponential backoff
- **Rich message not supported**: Fall back to plain text with numbered lists
- **Media upload failure**: Send text-only message
- **Rate limit exceeded**: Queue messages and send when limit resets

### Context Management Errors
- **Context load failure**: Create new context, log warning
- **Menu expiration**: Ask customer to select again, re-display menu
- **Invalid reference**: Ask for clarification, re-display menu
- **State corruption**: Reset to clean state, log error to Sentry

## Testing Strategy

### Unit Testing

**Intent Detection Tests**:
- Test rule-based classification for all keyword patterns
- Test numeric reply resolution
- Test WhatsApp button/list payload processing
- Test LLM fallback for ambiguous messages
- Test slot extraction with regex patterns
- Test language detection for EN/SW/Sheng

**Business Logic Handler Tests**:
- Test each handler with valid inputs
- Test each handler with missing data
- Test each handler with invalid data
- Test tenant scoping in all queries
- Test context updates after each handler
- Test error handling and fallbacks

**Payment Flow Tests**:
- Test M-Pesa STK initiation
- Test M-Pesa callback processing (success/failure)
- Test card payment link generation
- Test card payment webhook processing
- Test payment amount validation
- Test payment retry logic

**RAG Pipeline Tests**:
- Test chunk retrieval from Pinecone
- Test grounding validation
- Test uncertainty responses
- Test tenant namespace isolation
- Test similarity threshold handling

**Context Management Tests**:
- Test context creation and loading
- Test menu storage and resolution
- Test flow state transitions
- Test awaiting_response handling
- Test context expiration

### Property-Based Testing

We'll use **Hypothesis** (Python property-based testing library) for universal property validation.

**Property Test 1: Database-grounded product display**
```python
@given(
    tenant=tenants(),
    query=st.text(min_size=1, max_size=100)
)
def test_product_display_grounding(tenant, query):
    """Property: All displayed products exist in database"""
    # Assume: Tenant has at least one product
    # Action: Browse products
    # Assert: All returned products exist in DB with matching prices
```

**Property Test 2: Rule-based classification efficiency**
```python
@given(
    message=st.sampled_from([
        "what do you sell",
        "nataka kununua",
        "book appointment",
        "mpesa details"
    ])
)
def test_rule_based_no_llm(message):
    """Property: Keyword messages don't call LLM"""
    # Action: Classify intent
    # Assert: No LLM calls made
```

**Property Test 3: Tenant isolation**
```python
@given(
    tenant1=tenants(),
    tenant2=tenants(),
    query=st.text()
)
def test_tenant_isolation(tenant1, tenant2, query):
    """Property: Queries never return cross-tenant data"""
    # Assume: tenant1 != tenant2
    # Action: Query products for tenant1
    # Assert: No products from tenant2 in results
```

**Property Test 4: Payment amount integrity**
```python
@given(
    order=orders(),
    payment_method=st.sampled_from(["mpesa_stk", "card"])
)
def test_payment_amount_integrity(order, payment_method):
    """Property: Payment amount matches order total"""
    # Action: Initiate payment
    # Assert: PaymentRequest.amount == Order.total
```

**Property Test 5: RAG grounding**
```python
@given(
    question=st.text(min_size=10, max_size=200),
    chunks=st.lists(st.dictionaries(
        keys=st.just("text"),
        values=st.text(min_size=50, max_size=500)
    ), min_size=1, max_size=5)
)
def test_rag_grounding(question, chunks):
    """Property: RAG answers contain only chunk information"""
    # Action: Generate answer from chunks
    # Assert: All facts in answer are present in chunks
```

**Property Test 6: Context state consistency**
```python
@given(
    conversation=conversations(),
    actions=st.lists(bot_actions(), min_size=1, max_size=10)
)
def test_context_state_consistency(conversation, actions):
    """Property: Context updates are consistent with actions"""
    # Action: Apply sequence of actions
    # Assert: Final context state matches expected state from actions
```

**Property Test 7: Language consistency**
```python
@given(
    language=st.sampled_from(["en", "sw", "sheng"]),
    message_count=st.integers(min_value=2, max_value=10)
)
def test_language_consistency(language, message_count):
    """Property: Bot maintains language throughout conversation"""
    # Setup: Set initial language
    # Action: Generate multiple responses
    # Assert: All responses in same language
```

**Property Test 8: Menu reference resolution**
```python
@given(
    menu_items=st.lists(st.uuids(), min_size=1, max_size=10),
    reference=st.integers(min_value=1, max_value=10)
)
def test_menu_reference_resolution(menu_items, reference):
    """Property: Numeric references resolve to correct menu items"""
    # Setup: Store menu in context
    # Action: Resolve reference
    # Assert: Resolved item matches menu_items[reference-1]
```

### Integration Testing

**End-to-End Flow Tests**:
1. **Product Purchase Flow**:
   - Customer: "What do you sell?"
   - Bot: Shows product list
   - Customer: "1"
   - Bot: Shows product details, asks quantity
   - Customer: "2"
   - Bot: Creates order, asks payment method
   - Customer: "M-Pesa"
   - Bot: Asks phone number
   - Customer: "+254712345678"
   - Bot: Initiates STK, confirms
   - System: Processes callback, updates order
   - Bot: Sends confirmation

2. **Appointment Booking Flow**:
   - Customer: "Nataka pedicure kesho saa kumi"
   - Bot: Checks availability, asks confirmation
   - Customer: "Yes"
   - Bot: Creates appointment, asks payment
   - Customer: "Card"
   - Bot: Generates link, sends
   - System: Processes webhook, updates appointment
   - Bot: Sends confirmation

3. **FAQ Flow**:
   - Customer: "What's your return policy?"
   - Bot: Retrieves from RAG, answers
   - Customer: "How long do I have?"
   - Bot: Answers from same context

4. **Error Recovery Flow**:
   - Customer: "I want to buy"
   - Bot: Shows products
   - Customer: "xyz" (invalid)
   - Bot: Asks for clarification, re-shows menu
   - Customer: "2"
   - Bot: Proceeds with selection

**Multi-Tenant Tests**:
- Test tenant isolation in all queries
- Test tenant-specific branding
- Test tenant-specific payment credentials
- Test tenant-specific RAG namespaces
- Test tenant-specific business hours

**Performance Tests**:
- Test response time <1.5s for rule-based flows
- Test response time <3s for LLM-based flows
- Test concurrent message processing
- Test database query performance with indexes
- Test Pinecone query performance

**Cost Tests**:
- Test LLM usage stays under budget
- Test token counting accuracy
- Test cost estimation accuracy
- Test budget enforcement and throttling

## Implementation Notes

### Phase 1: Foundation (Weeks 1-2)
1. Intent Detection Engine with rule-based classification
2. Business Logic Router with handler framework
3. Conversation Context Manager
4. Database models (IntentClassificationLog, LLMUsageLog, PaymentRequest)
5. Basic unit tests

### Phase 2: Core Flows (Weeks 3-4)
1. Product browsing handler
2. Order creation handler
3. Payment orchestration (M-Pesa STK, card)
4. Appointment booking handler
5. Status checking handlers
6. Integration tests for core flows

### Phase 3: Intelligence Layer (Weeks 5-6)
1. LLM Router with model selection
2. RAG Pipeline with grounding validation
3. Slot extraction with rules + LLM fallback
4. Language detection and consistency
5. Property-based tests

### Phase 4: Polish & Optimization (Weeks 7-8)
1. WhatsApp rich message formatting
2. Error handling and fallbacks
3. Business hours and quiet hours
4. Cost tracking and budget enforcement
5. Performance optimization
6. Comprehensive testing
7. Documentation

### Performance Considerations
- **Cache frequently accessed data**: Product catalogs, service lists, tenant settings
- **Use database indexes**: On tenant_id, customer_id, created_at, status fields
- **Batch Pinecone queries**: When possible, retrieve multiple chunks in one call
- **Optimize LLM prompts**: Keep prompts short, use structured outputs
- **Use Redis for**: Menu storage (5-minute TTL), conversation summaries, rate limiting
- **Async processing**: Use Celery for all message processing, payment callbacks, RAG queries

### Backward Compatibility
- All new features behind feature flags in AgentConfiguration
- Graceful fallback to existing behavior if new services fail
- Maintain existing API contracts for webhooks
- Gradual migration path for existing conversations

### Monitoring & Observability
- **Sentry**: All errors with full context
- **Structured logging**: JSON logs with tenant_id, conversation_id, intent, handler
- **Metrics to track**:
  - Intent classification method distribution (rule vs LLM)
  - LLM usage per tenant (calls, tokens, cost)
  - Conversion rates (enquiry → order → payment)
  - Payment success/failure rates
  - Response times by handler
  - Error rates by type
  - RAG retrieval quality (similarity scores)
- **Alerts**:
  - Payment processing failures
  - LLM budget exceeded
  - High error rates
  - Slow response times
  - Database connection issues

### Security Considerations
- **Tenant isolation**: All queries filtered by tenant_id
- **Encrypted credentials**: All API keys encrypted at rest
- **Webhook verification**: Verify Twilio, M-Pesa, payment provider signatures
- **Rate limiting**: Per tenant and per customer
- **Input validation**: Sanitize all user inputs
- **Audit logging**: Log all payment events, order creations, appointment bookings
- **PII protection**: Encrypt phone numbers, payment details
- **Access control**: RBAC for admin/tenant dashboards

### Deployment Strategy
- **Blue-green deployment**: Zero-downtime updates
- **Feature flags**: Gradual rollout of new features
- **Canary testing**: Test with small percentage of tenants first
- **Rollback plan**: Quick rollback if issues detected
- **Database migrations**: Run migrations before code deployment
- **Cache warming**: Pre-populate caches after deployment
- **Health checks**: Verify all services before routing traffic
