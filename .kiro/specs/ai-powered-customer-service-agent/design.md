# Design Document

## Overview

This design document outlines the architecture for upgrading the WabotIQ bot from a basic intent classification system to an advanced AI-powered customer service agent. The enhanced system will leverage state-of-the-art language models, maintain comprehensive conversation memory, integrate tenant-specific knowledge bases, and provide rich interactive experiences through WhatsApp's advanced messaging features.

The design follows a modular, service-oriented architecture that maintains strict multi-tenant isolation while enabling powerful AI capabilities including context-aware responses, intelligent error correction, multi-intent handling, and proactive recommendations.

## Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Inbound Flow"
        WA[WhatsApp Customer] -->|Message| TW[Twilio Webhook]
        TW -->|Create Message| MSG[Message Model]
        MSG -->|Trigger| CEL[Celery Task]
    end
    
    subgraph "AI Agent Core"
        CEL -->|Load Context| CTX[Context Builder]
        CTX -->|Retrieve| KB[Knowledge Base]
        CTX -->|Retrieve| MEM[Conversation Memory]
        CTX -->|Retrieve| CAT[Catalog Data]
        
        CTX -->|Build Prompt| AGT[AI Agent Service]
        AGT -->|API Call| LLM[LLM Provider]
        LLM -->|GPT-4o/o1| OPENAI[OpenAI]
        LLM -->|Multiple Models| TOGETHER[Together AI]
        
        AGT -->|Parse Response| RESP[Response Handler]
        RESP -->|Format| RICH[Rich Message Builder]
    end
    
    subgraph "Output Flow"
        RICH -->|Send| TWSVC[Twilio Service]
        TWSVC -->|WhatsApp| WA
        RESP -->|Track| ANALYTICS[Analytics]
    end
    
    subgraph "Configuration"
        TENANT[Tenant] -->|Configure| AGENTCFG[Agent Configuration]
        AGENTCFG -->|Persona| AGT
        AGENTCFG -->|Knowledge| KB
    end
```

### Component Architecture

The system is organized into the following major components:

1. **AI Agent Service** - Core orchestration and LLM interaction
2. **Context Builder** - Assembles conversation context from multiple sources
3. **Knowledge Base Service** - Manages and retrieves tenant-specific knowledge
4. **Conversation Memory Service** - Maintains and retrieves conversation history
5. **LLM Provider Abstraction** - Unified interface for multiple AI models
6. **Rich Message Builder** - Constructs WhatsApp interactive messages
7. **Agent Configuration Service** - Manages tenant-specific agent settings
8. **Multi-Intent Processor** - Handles messages with multiple intents
9. **Fuzzy Matcher** - Intelligent matching for products, services, and queries

## Components and Interfaces

### 1. AI Agent Service

**Purpose:** Orchestrates the entire AI agent workflow from message receipt to response generation.

**Key Responsibilities:**
- Coordinate context building from multiple sources
- Select appropriate LLM model based on task complexity
- Generate responses using configured persona and knowledge
- Handle multi-intent messages
- Manage handoff decisions
- Track analytics and performance metrics

**Interface:**
```python
class AIAgentService:
    def process_message(
        self,
        message: Message,
        conversation: Conversation,
        tenant: Tenant
    ) -> AgentResponse:
        """Process customer message and generate response."""
        
    def generate_response(
        self,
        context: AgentContext,
        agent_config: AgentConfiguration
    ) -> AgentResponse:
        """Generate AI response with full context."""
        
    def should_handoff(
        self,
        response: AgentResponse,
        conversation: Conversation
    ) -> Tuple[bool, str]:
        """Determine if handoff is needed."""
```

### 2. Context Builder Service

**Purpose:** Assembles comprehensive context from conversation history, knowledge base, catalog, and customer data.

**Key Responsibilities:**
- Retrieve and prioritize conversation history
- Fetch relevant knowledge base entries
- Load product and service catalog data
- Include customer preferences and history
- Manage context window limits with intelligent truncation
- Cache frequently accessed context data

**Interface:**
```python
class ContextBuilderService:
    def build_context(
        self,
        conversation: Conversation,
        message: Message,
        tenant: Tenant
    ) -> AgentContext:
        """Build comprehensive context for AI agent."""
        
    def get_conversation_history(
        self,
        conversation: Conversation,
        max_messages: int = 20
    ) -> List[Message]:
        """Retrieve relevant conversation history."""
        
    def get_relevant_knowledge(
        self,
        query: str,
        tenant: Tenant,
        limit: int = 5
    ) -> List[KnowledgeEntry]:
        """Retrieve relevant knowledge base entries."""
        
    def get_catalog_context(
        self,
        tenant: Tenant,
        query: Optional[str] = None
    ) -> CatalogContext:
        """Get product and service catalog context."""
```

### 3. Knowledge Base Service

**Purpose:** Manages tenant-specific knowledge including FAQs, policies, and custom instructions.

**Key Responsibilities:**
- Store and index knowledge base entries
- Perform semantic search for relevant entries
- Support multiple entry types (FAQ, policy, instruction)
- Handle knowledge base updates and versioning
- Provide conflict detection and resolution

**Interface:**
```python
class KnowledgeBaseService:
    def create_entry(
        self,
        tenant: Tenant,
        entry_type: str,
        content: Dict[str, Any]
    ) -> KnowledgeEntry:
        """Create new knowledge base entry."""
        
    def search(
        self,
        tenant: Tenant,
        query: str,
        entry_types: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[KnowledgeEntry]:
        """Search knowledge base using semantic similarity."""
        
    def update_entry(
        self,
        entry_id: UUID,
        content: Dict[str, Any]
    ) -> KnowledgeEntry:
        """Update existing knowledge entry."""
```


### 4. LLM Provider Abstraction

**Purpose:** Provides unified interface for multiple AI model providers (OpenAI, Together AI, future providers).

**Key Responsibilities:**
- Abstract provider-specific API differences
- Handle authentication and rate limiting
- Implement fallback strategies
- Track token usage and costs
- Support streaming responses
- Normalize responses across providers

**Interface:**
```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate completion from LLM."""
        
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models."""

class OpenAIProvider(LLMProvider):
    """OpenAI implementation supporting GPT-4o, o1-preview, o1-mini."""
    
class TogetherAIProvider(LLMProvider):
    """Together AI implementation for multiple model access."""

class LLMProviderFactory:
    def get_provider(self, provider_name: str) -> LLMProvider:
        """Get provider instance by name."""
```

### 5. Rich Message Builder

**Purpose:** Constructs WhatsApp interactive messages with buttons, lists, images, and media.

**Key Responsibilities:**
- Build interactive button messages
- Create list messages for selections
- Format product/service cards with images
- Handle media attachments (images, videos, documents)
- Validate message structure against WhatsApp limits
- Generate fallback text for unsupported clients

**Interface:**
```python
class RichMessageBuilder:
    def build_product_card(
        self,
        product: Product,
        actions: List[str] = ['buy', 'details']
    ) -> WhatsAppMessage:
        """Build product card with image and action buttons."""
        
    def build_service_card(
        self,
        service: Service,
        actions: List[str] = ['book', 'availability']
    ) -> WhatsAppMessage:
        """Build service card with image and action buttons."""
        
    def build_list_message(
        self,
        title: str,
        items: List[Dict[str, Any]],
        button_text: str = "Select"
    ) -> WhatsAppMessage:
        """Build interactive list message."""
        
    def build_button_message(
        self,
        text: str,
        buttons: List[Dict[str, str]]
    ) -> WhatsAppMessage:
        """Build message with quick reply buttons."""
```

### 6. Agent Configuration Service

**Purpose:** Manages tenant-specific agent configuration including persona, behavior, and model selection.

**Key Responsibilities:**
- Store and retrieve agent configuration
- Validate configuration settings
- Apply persona to prompts
- Manage behavioral restrictions
- Handle configuration versioning

**Interface:**
```python
class AgentConfigurationService:
    def get_configuration(self, tenant: Tenant) -> AgentConfiguration:
        """Get agent configuration for tenant."""
        
    def update_configuration(
        self,
        tenant: Tenant,
        config: Dict[str, Any]
    ) -> AgentConfiguration:
        """Update agent configuration."""
        
    def apply_persona(
        self,
        base_prompt: str,
        config: AgentConfiguration
    ) -> str:
        """Apply persona settings to prompt."""
```

### 7. Multi-Intent Processor

**Purpose:** Identifies and handles messages containing multiple intents or rapid message bursts.

**Key Responsibilities:**
- Detect multiple intents in single message
- Queue and process rapid message sequences
- Maintain context across message bursts
- Prioritize intents based on urgency
- Generate structured responses addressing all intents

**Interface:**
```python
class MultiIntentProcessor:
    def detect_intents(
        self,
        message: str,
        context: AgentContext
    ) -> List[Intent]:
        """Detect all intents in message."""
        
    def process_message_burst(
        self,
        messages: List[Message],
        conversation: Conversation
    ) -> AgentResponse:
        """Process multiple messages as single context."""
        
    def prioritize_intents(
        self,
        intents: List[Intent]
    ) -> List[Intent]:
        """Order intents by priority and logical flow."""
```

### 8. Fuzzy Matcher Service

**Purpose:** Provides intelligent matching for products, services, and queries with spelling correction.

**Key Responsibilities:**
- Perform fuzzy string matching
- Correct common spelling errors
- Use semantic similarity for matching
- Handle abbreviations and informal names
- Suggest alternatives when no exact match

**Interface:**
```python
class FuzzyMatcherService:
    def match_product(
        self,
        query: str,
        tenant: Tenant,
        threshold: float = 0.7
    ) -> List[Tuple[Product, float]]:
        """Match query to products with confidence scores."""
        
    def match_service(
        self,
        query: str,
        tenant: Tenant,
        threshold: float = 0.7
    ) -> List[Tuple[Service, float]]:
        """Match query to services with confidence scores."""
        
    def correct_spelling(
        self,
        text: str,
        vocabulary: List[str]
    ) -> str:
        """Correct spelling using vocabulary."""
```

## Data Models

### AgentConfiguration Model

```python
class AgentConfiguration(BaseModel):
    """Tenant-specific agent configuration."""
    
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='agent_configuration'
    )
    
    # Persona
    agent_name = models.CharField(max_length=100, default="Assistant")
    personality_traits = models.JSONField(default=dict)
    tone = models.CharField(
        max_length=20,
        choices=[
            ('professional', 'Professional'),
            ('friendly', 'Friendly'),
            ('casual', 'Casual'),
            ('formal', 'Formal')
        ],
        default='friendly'
    )
    
    # Model Configuration
    default_model = models.CharField(max_length=50, default='gpt-4o')
    fallback_models = models.JSONField(default=list)
    temperature = models.FloatField(default=0.7)
    
    # Behavior
    max_response_length = models.IntegerField(default=500)
    behavioral_restrictions = models.JSONField(default=list)
    required_disclaimers = models.JSONField(default=list)
    
    # Handoff Configuration
    confidence_threshold = models.FloatField(default=0.7)
    auto_handoff_topics = models.JSONField(default=list)
    max_low_confidence_attempts = models.IntegerField(default=2)
    
    # Features
    enable_proactive_suggestions = models.BooleanField(default=True)
    enable_spelling_correction = models.BooleanField(default=True)
    enable_rich_messages = models.BooleanField(default=True)
```


### KnowledgeEntry Model

```python
class KnowledgeEntry(BaseModel):
    """Tenant-specific knowledge base entry."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='knowledge_entries'
    )
    
    entry_type = models.CharField(
        max_length=20,
        choices=[
            ('faq', 'FAQ'),
            ('policy', 'Policy'),
            ('instruction', 'Instruction'),
            ('location', 'Location'),
            ('hours', 'Operating Hours')
        ]
    )
    
    # Content
    title = models.CharField(max_length=200)
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    
    # Search
    embedding = models.JSONField(null=True, blank=True)
    keywords = models.JSONField(default=list)
    
    # Organization
    category = models.CharField(max_length=100, blank=True)
    priority = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'entry_type', 'is_active']),
            models.Index(fields=['tenant', 'category']),
        ]
```

### ConversationContext Model

```python
class ConversationContext(BaseModel):
    """Stores conversation context for memory."""
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='contexts'
    )
    
    # Context Data
    current_topic = models.CharField(max_length=100, blank=True)
    pending_action = models.CharField(max_length=100, blank=True)
    extracted_entities = models.JSONField(default=dict)
    
    # State
    last_product_viewed = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    last_service_viewed = models.ForeignKey(
        'services.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Memory
    conversation_summary = models.TextField(blank=True)
    key_facts = models.JSONField(default=list)
    
    # Timing
    last_interaction = models.DateTimeField(auto_now=True)
    context_expires_at = models.DateTimeField(null=True, blank=True)
```

### AgentInteraction Model

```python
class AgentInteraction(BaseModel):
    """Tracks AI agent interactions for analytics."""
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='agent_interactions'
    )
    
    # Input
    customer_message = models.TextField()
    detected_intents = models.JSONField(default=list)
    
    # Processing
    model_used = models.CharField(max_length=50)
    context_size = models.IntegerField()
    processing_time_ms = models.IntegerField()
    
    # Output
    agent_response = models.TextField()
    confidence_score = models.FloatField()
    handoff_triggered = models.BooleanField(default=False)
    handoff_reason = models.CharField(max_length=100, blank=True)
    
    # Rich Message
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Text'),
            ('button', 'Button'),
            ('list', 'List'),
            ('media', 'Media')
        ],
        default='text'
    )
    
    # Metrics
    token_usage = models.JSONField(default=dict)
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['model_used', 'created_at']),
            models.Index(fields=['confidence_score']),
        ]
```

### MessageQueue Model

```python
class MessageQueue(BaseModel):
    """Queues messages for burst handling."""
    
    conversation = models.ForeignKey(
        'messaging.Conversation',
        on_delete=models.CASCADE,
        related_name='message_queue'
    )
    
    message = models.ForeignKey(
        'messaging.Message',
        on_delete=models.CASCADE
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('processing', 'Processing'),
            ('processed', 'Processed'),
            ('failed', 'Failed')
        ],
        default='queued'
    )
    
    queue_position = models.IntegerField()
    queued_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['conversation', 'status', 'queue_position']),
        ]
```

## Prompt Engineering Strategy

### System Prompt Structure

The system prompt will be dynamically constructed with the following sections:

1. **Agent Identity** - Name, role, and tenant business context
2. **Persona Instructions** - Tone, style, and personality traits
3. **Capabilities** - What the agent can and cannot do
4. **Knowledge Access** - How to use provided knowledge base
5. **Behavioral Rules** - Restrictions and required disclaimers
6. **Response Format** - Structure for responses including rich messages
7. **Handoff Criteria** - When to escalate to humans

### Context Assembly

Context will be assembled in priority order:

1. **Current Message** - The customer's latest message(s)
2. **Immediate Context** - Last 3-5 messages for continuity
3. **Relevant Knowledge** - Top 3-5 knowledge base entries
4. **Catalog Context** - Relevant products/services
5. **Customer History** - Previous orders, appointments, preferences
6. **Conversation Summary** - Condensed history for older conversations

### Token Management

To manage context window limits:

- **GPT-4o**: 128K tokens - Use full context
- **o1-preview**: 128K tokens - Use for complex reasoning
- **o1-mini**: 128K tokens - Use for cost-effective reasoning
- **Fallback**: Intelligent truncation prioritizing recent and relevant

## Error Handling

### Spelling Correction Strategy

1. **Pre-processing** - Correct obvious typos before LLM call
2. **Fuzzy Matching** - Use Levenshtein distance for catalog items
3. **LLM Assistance** - Let LLM infer meaning from context
4. **Confirmation** - Confirm corrections with customer when critical

### Multi-Intent Handling Strategy

1. **Detection** - Use LLM to identify multiple intents
2. **Prioritization** - Order by urgency and logical flow
3. **Structured Response** - Address each intent in sections
4. **Context Preservation** - Maintain state for follow-ups

### Message Burst Handling

1. **Queueing** - Queue messages received within 5 seconds
2. **Batching** - Process queued messages as single context
3. **Deduplication** - Prevent duplicate intent processing
4. **Response Timing** - Send single comprehensive response

### Handoff Scenarios

1. **Low Confidence** - After 2 consecutive low-confidence responses
2. **Explicit Request** - Customer asks for human
3. **Complex Issue** - Agent determines it cannot help
4. **Restricted Topic** - Topic in auto-handoff list
5. **Error Recovery** - After repeated failures

## Testing Strategy

### Unit Tests

1. **Context Builder** - Test context assembly and prioritization
2. **Fuzzy Matcher** - Test spelling correction and matching
3. **Multi-Intent Processor** - Test intent detection and prioritization
4. **Rich Message Builder** - Test message formatting
5. **LLM Provider** - Test provider abstraction and fallbacks

### Integration Tests

1. **End-to-End Flow** - Message receipt to response delivery
2. **Knowledge Base Search** - Semantic search accuracy
3. **Conversation Memory** - Context retention across messages
4. **Multi-Tenant Isolation** - Verify data separation
5. **Rich Message Delivery** - WhatsApp interactive messages

### Performance Tests

1. **Response Time** - 95th percentile under 5 seconds
2. **Concurrent Load** - Multiple tenants simultaneously
3. **Context Building** - Sub-second context assembly
4. **Knowledge Search** - Sub-500ms semantic search
5. **Token Usage** - Cost optimization validation


### AI Quality Tests

1. **Intent Accuracy** - Measure correct intent classification rate
2. **Spelling Correction** - Validate correction accuracy
3. **Context Retention** - Test memory across conversation gaps
4. **Multi-Intent Handling** - Verify all intents addressed
5. **Handoff Appropriateness** - Validate handoff decisions

## Implementation Phases

### Phase 1: Foundation (Core AI Agent)

- Implement LLM provider abstraction
- Create AI Agent Service with basic orchestration
- Build Context Builder Service
- Implement Agent Configuration model and service
- Add support for GPT-4o, o1-preview, o1-mini
- Create basic prompt engineering framework

### Phase 2: Knowledge and Memory

- Implement Knowledge Base Service
- Create KnowledgeEntry model and CRUD APIs
- Add semantic search capability
- Implement Conversation Context model
- Build conversation memory retrieval
- Add context window management

### Phase 3: Intelligence Features

- Implement Fuzzy Matcher Service
- Add spelling correction
- Build Multi-Intent Processor
- Implement message burst handling
- Add proactive suggestions logic
- Enhance handoff decision making

### Phase 4: Rich Messaging

- Implement Rich Message Builder
- Add WhatsApp button message support
- Add WhatsApp list message support
- Implement product/service cards with images
- Add media attachment handling
- Create campaign message builder

### Phase 5: Analytics and Optimization

- Implement AgentInteraction tracking
- Build analytics dashboard
- Add cost tracking and optimization
- Implement A/B testing framework
- Add performance monitoring
- Create tenant insights reports

## Security Considerations

### Multi-Tenant Isolation

- All database queries MUST filter by tenant_id
- Knowledge base entries scoped to tenant
- Conversation context isolated per tenant
- Agent configurations separate per tenant
- No cross-tenant data leakage in prompts

### API Key Management

- LLM API keys stored encrypted in settings
- Tenant-specific API keys supported for Together AI
- Rate limiting per tenant
- Cost tracking and limits per tenant
- Secure key rotation procedures

### Data Privacy

- Customer messages encrypted at rest
- PII handling in compliance with regulations
- Conversation data retention policies
- Knowledge base content encryption
- Audit logging for all agent interactions

### Input Validation

- Sanitize all customer inputs
- Validate knowledge base content
- Prevent prompt injection attacks
- Limit context size to prevent abuse
- Rate limit API endpoints

## Performance Optimization

### Caching Strategy

- Cache agent configurations (5 minute TTL)
- Cache knowledge base embeddings
- Cache catalog data (1 minute TTL)
- Cache conversation summaries
- Use Redis for distributed caching

### Database Optimization

- Index all tenant_id fields
- Index conversation_id for history queries
- Index created_at for time-based queries
- Use database connection pooling
- Implement read replicas for heavy queries

### LLM Call Optimization

- Batch similar requests when possible
- Use streaming for long responses
- Implement request deduplication
- Cache common responses (FAQs)
- Use cheaper models for simple tasks

### Async Processing

- Process messages asynchronously via Celery
- Queue message bursts for batch processing
- Background knowledge base indexing
- Async analytics aggregation
- Non-blocking response delivery

## Monitoring and Observability

### Metrics to Track

- Response time (p50, p95, p99)
- Token usage per conversation
- Cost per conversation
- Handoff rate and reasons
- Intent classification accuracy
- Knowledge base hit rate
- Customer satisfaction scores
- Error rates by type

### Logging Strategy

- Log all agent interactions
- Log LLM API calls and responses
- Log context building steps
- Log handoff decisions
- Log errors with full context
- Use structured logging (JSON)

### Alerting

- Alert on high error rates
- Alert on slow response times
- Alert on high costs
- Alert on frequent handoffs
- Alert on API failures
- Alert on low confidence trends

## Migration Strategy

### Backward Compatibility

- Maintain existing intent classification system
- Gradual rollout per tenant
- Feature flags for new capabilities
- Fallback to old system on errors
- Data migration scripts for existing conversations

### Rollout Plan

1. **Alpha** - Internal testing with demo tenant
2. **Beta** - 5-10 selected tenants
3. **Gradual Rollout** - 10% → 50% → 100%
4. **Monitoring** - Track metrics at each stage
5. **Rollback Plan** - Quick revert if issues

## Future Enhancements

### Advanced Features

- Voice message transcription and processing
- Image recognition for product identification
- Multi-language support with translation
- Sentiment analysis for customer satisfaction
- Predictive analytics for proactive outreach
- Integration with CRM systems
- Custom model fine-tuning per tenant

### Model Improvements

- Support for Claude (Anthropic)
- Support for Gemini (Google)
- Support for Llama models via Together AI
- Custom model training on tenant data
- Ensemble models for improved accuracy
- Specialized models for specific domains

### User Experience

- Customer feedback collection
- Agent personality customization UI
- Visual knowledge base builder
- Conversation analytics dashboard
- A/B testing for prompts
- Real-time agent performance monitoring

## Cost Estimation

### Per Conversation Estimates

**Simple Query (GPT-4o-mini):**
- Input: ~2K tokens (context + message)
- Output: ~200 tokens
- Cost: ~$0.001 per conversation

**Complex Query (GPT-4o):**
- Input: ~5K tokens (full context)
- Output: ~500 tokens
- Cost: ~$0.015 per conversation

**Reasoning Task (o1-preview):**
- Input: ~3K tokens
- Output: ~1K tokens
- Cost: ~$0.045 per conversation

### Monthly Cost Projections

**Small Tenant (100 conversations/month):**
- Mostly simple queries: ~$5-10/month
- Mixed complexity: ~$15-25/month

**Medium Tenant (1,000 conversations/month):**
- Mostly simple queries: ~$50-100/month
- Mixed complexity: ~$150-250/month

**Large Tenant (10,000 conversations/month):**
- Mostly simple queries: ~$500-1,000/month
- Mixed complexity: ~$1,500-2,500/month

### Cost Optimization Strategies

- Use GPT-4o-mini for 80% of queries
- Reserve o1 models for complex reasoning
- Implement response caching for FAQs
- Optimize context size
- Batch similar requests
- Use tenant-specific cost limits
