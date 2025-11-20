# Conversational Commerce UX Enhancement - API Documentation

## Overview

This document describes the API endpoints and services added as part of the Conversational Commerce UX Enhancement feature. These enhancements transform the WabotIQ bot from a basic assistant into an intelligent sales guide that provides smooth inquiry-to-sale journeys.

## Core Services

### 1. Message Harmonization Service

**Purpose**: Combines rapid-fire messages into a single conversational turn to provide coherent responses.

**Location**: `apps/bot/services/message_harmonization_service.py`

**Key Methods**:

```python
MessageHarmonizationService.should_buffer_message(conversation, message) -> bool
MessageHarmonizationService.get_harmonized_messages(conversation, wait_seconds=3) -> List[Message]
MessageHarmonizationService.combine_messages(messages) -> str
```

**Configuration**:
- `AgentConfiguration.enable_message_harmonization` (default: True)
- `AgentConfiguration.harmonization_wait_seconds` (default: 3)

**Behavior**:
- Detects messages sent within 3 seconds of each other
- Buffers messages and shows typing indicator
- Processes all buffered messages together after silence period
- Generates one comprehensive response

### 2. Reference Context Manager

**Purpose**: Resolves customer references like "1", "first", "the blue one" to actual items from recent lists.

**Location**: `apps/bot/services/reference_context_manager.py`

**Key Methods**:

```python
ReferenceContextManager.store_list_context(conversation, list_type, items, ttl_minutes=5) -> str
ReferenceContextManager.resolve_reference(conversation, reference) -> Optional[Dict]
ReferenceContextManager.get_active_context(conversation) -> Optional[ReferenceContext]
```

**Supported References**:
- Positional: "1", "2", "3", etc.
- Ordinal: "first", "second", "last"
- Descriptive: "the blue one", "the cheapest"

**TTL**: 5 minutes (configurable)

### 3. Language Consistency Manager

**Purpose**: Maintains consistent language throughout conversations.

**Location**: `apps/bot/services/language_consistency_manager.py`

**Key Methods**:

```python
LanguageConsistencyManager.detect_language(text) -> str
LanguageConsistencyManager.get_conversation_language(conversation) -> str
LanguageConsistencyManager.set_conversation_language(conversation, language) -> None
```

**Supported Languages**:
- English (`en`)
- Swahili (`sw`)
- Mixed detection with fallback to tenant default

### 4. Smart Product Discovery Service

**Purpose**: Proactively suggests products without requiring category narrowing.

**Location**: `apps/bot/services/discovery_service.py`

**Key Methods**:

```python
SmartProductDiscoveryService.get_immediate_suggestions(tenant, query, context, limit=5) -> Dict
SmartProductDiscoveryService.get_contextual_recommendations(tenant, customer, context) -> List[Product]
```

**Features**:
- Immediate product display on vague queries
- Fuzzy matching for misspelled product names
- Context-aware recommendations
- Category-based filtering

**Configuration**:
- `AgentConfiguration.enable_immediate_product_display` (default: True)
- `AgentConfiguration.max_products_to_show` (default: 5)

### 5. Branded Persona Builder

**Purpose**: Creates tenant-specific bot personas with business branding.

**Location**: `apps/bot/services/branded_persona_builder.py`

**Key Methods**:

```python
BrandedPersonaBuilder.build_system_prompt(tenant, agent_config, language='en') -> str
```

**Includes**:
- Tenant business name
- Custom bot name (if configured)
- Agent capabilities (agent_can_do)
- Agent limitations (agent_cannot_do)
- Language preference

**Configuration**:
- `AgentConfiguration.use_business_name_as_identity` (default: True)
- `AgentConfiguration.custom_bot_greeting` (optional)

### 6. Grounded Response Validator

**Purpose**: Ensures bot responses only contain factual information from the knowledge base.

**Location**: `apps/bot/services/grounded_response_validator.py`

**Key Methods**:

```python
GroundedResponseValidator.validate_response(response, context) -> Tuple[bool, List[str]]
GroundedResponseValidator.extract_claims(response) -> List[str]
GroundedResponseValidator.verify_claim(claim, context) -> bool
```

**Features**:
- Extracts factual claims from responses
- Verifies claims against product catalog and knowledge base
- Flags unverifiable claims
- Prevents hallucination

**Configuration**:
- `AgentConfiguration.enable_grounded_validation` (default: True)

### 7. Rich Message Builder

**Purpose**: Formats products and services as WhatsApp interactive messages.

**Location**: `apps/bot/services/rich_message_builder.py`

**Key Methods**:

```python
RichMessageBuilder.build_product_list(products, context_id, show_prices=True) -> WhatsAppMessage
RichMessageBuilder.build_product_card(product) -> WhatsAppMessage
RichMessageBuilder.build_service_card(service) -> WhatsAppMessage
RichMessageBuilder.build_checkout_message(order_summary, payment_link) -> WhatsAppMessage
```

**Message Types**:
- Product cards with images and buttons
- WhatsApp list messages (for 3+ items)
- Service cards with booking buttons
- Checkout messages with payment links

**Fallback**: Plain text with numbered lists if WhatsApp API fails

### 8. Conversation History Service

**Purpose**: Provides full conversation memory and summarization.

**Location**: `apps/bot/services/conversation_history_service.py`

**Key Methods**:

```python
ConversationHistoryService.get_full_history(conversation, include_system=False) -> List[Message]
ConversationHistoryService.summarize_history(conversation, max_tokens=500) -> str
ConversationHistoryService.get_conversation_topics(conversation) -> List[str]
```

**Features**:
- Loads complete conversation history
- Generates summaries for long conversations
- Extracts main topics discussed
- Supports "what have we talked about" queries

## Database Models

### ConversationContext (Enhanced)

**New Fields**:
```python
last_message_time = DateTimeField(null=True)
message_buffer = JSONField(default=list)
language_locked = BooleanField(default=False)
```

### AgentConfiguration (Enhanced)

**New Fields**:
```python
# Identity
use_business_name_as_identity = BooleanField(default=True)
custom_bot_greeting = TextField(blank=True)

# Message Harmonization
enable_message_harmonization = BooleanField(default=True)
harmonization_wait_seconds = IntegerField(default=3)

# Product Discovery
enable_immediate_product_display = BooleanField(default=True)
max_products_to_show = IntegerField(default=5)

# Validation
enable_grounded_validation = BooleanField(default=True)

# Reference Resolution
enable_reference_resolution = BooleanField(default=True)
```

### ReferenceContext (Existing)

```python
conversation = ForeignKey(Conversation)
context_id = CharField(max_length=50)
list_type = CharField(choices=['products', 'services', ...])
items = JSONField()
expires_at = DateTimeField()
```

### MessageHarmonizationLog (New)

```python
conversation = ForeignKey(Conversation)
message_ids = JSONField()
combined_text = TextField()
wait_time_ms = IntegerField()
response_generated = TextField()
created_at = DateTimeField(auto_now_add=True)
```

## Integration Points

### AIAgentService Integration

The main `AIAgentService.process_message()` method now integrates all enhancement services:

1. **Message Harmonization**: Buffers rapid messages before processing
2. **Context Building**: Loads full history and reference contexts
3. **Language Detection**: Maintains consistent language
4. **Branded Persona**: Uses tenant-specific system prompts
5. **Product Discovery**: Proactively suggests products
6. **Response Validation**: Verifies factual grounding
7. **Rich Formatting**: Formats responses as interactive messages
8. **Reference Storage**: Stores lists for future reference

### Context Builder Integration

The `ContextBuilderService` now:
- Loads ALL conversation messages (not just last 20)
- Includes conversation summaries for long histories
- Loads active reference contexts
- Detects and stores language preferences
- Includes tenant branding information

## Performance Considerations

### Caching Strategy

**Redis Caching**:
- Reference contexts: 5-minute TTL
- Product catalog: 15-minute TTL per tenant
- Conversation summaries: 30-minute TTL

**Database Indexes**:
```sql
CREATE INDEX idx_conversation_messages ON messaging_message(conversation_id, created_at);
CREATE INDEX idx_reference_context_expires ON bot_referencecontext(conversation_id, expires_at);
CREATE INDEX idx_harmonization_log ON bot_messageharmonizationlog(conversation_id, created_at);
```

### Query Optimization

- Use `select_related()` for product queries with variants
- Use `prefetch_related()` for conversation history with messages
- Paginate conversation history for very long conversations (>100 messages)
- Batch product lookups when displaying multiple items

## Error Handling

### Fallback Strategies

**Missing Reference Context**:
```
"I'm not sure which item you're referring to. Let me show you our products again."
```

**Expired Context**:
- Treat as new inquiry
- Re-display products if needed

**WhatsApp API Failure**:
- Fall back to plain text with numbered lists
- Log error for monitoring

**Language Detection Error**:
- Default to tenant's primary language
- Log ambiguous cases

**Grounding Validation Failure**:
- Remove unverifiable claims
- Add disclaimer: "Please confirm with our team"
- Log for review

## Monitoring & Observability

### Key Metrics

**Message Harmonization**:
- `harmonization.buffer_size` - Number of messages combined
- `harmonization.wait_time_ms` - Time spent waiting
- `harmonization.success_rate` - Successful harmonizations

**Reference Resolution**:
- `reference.resolution_success` - Successful resolutions
- `reference.resolution_failure` - Failed resolutions
- `reference.context_expiry` - Expired contexts

**Language Consistency**:
- `language.detection_accuracy` - Detection success rate
- `language.switches` - Mid-conversation switches
- `language.consistency_score` - Overall consistency

**Product Discovery**:
- `discovery.immediate_display_rate` - Immediate product shows
- `discovery.fuzzy_match_success` - Fuzzy matching hits
- `discovery.empty_results` - No products found

**Grounding Validation**:
- `grounding.validation_failures` - Failed validations
- `grounding.claim_verification_rate` - Verified claims
- `grounding.hallucination_prevention` - Prevented hallucinations

**Rich Messages**:
- `rich_message.usage_rate` - Rich vs plain text
- `rich_message.fallback_rate` - API failures
- `rich_message.interaction_rate` - Button/list interactions

### Logging

All services log to structured logger with tenant context:

```python
logger.info(
    "Message harmonization completed",
    extra={
        "tenant_id": str(tenant.id),
        "conversation_id": str(conversation.id),
        "message_count": len(messages),
        "wait_time_ms": wait_time
    }
)
```

### Alerting

**Critical Alerts**:
- Grounding validation failure rate > 10%
- Message harmonization timeout rate > 5%
- Rich message fallback rate > 20%

**Warning Alerts**:
- Reference resolution failure rate > 15%
- Language detection ambiguity > 10%
- Product discovery empty results > 25%

## Security Considerations

### Tenant Isolation

All services enforce strict tenant isolation:
- Reference contexts scoped to conversation (which is tenant-scoped)
- Product queries filtered by tenant
- Message harmonization per-conversation
- No cross-tenant data leakage

### Rate Limiting

Enhanced endpoints maintain existing rate limits:
- Message processing: 60 requests/minute per tenant
- Product queries: 100 requests/minute per tenant
- Context resolution: 120 requests/minute per tenant

### Data Privacy

- Message buffers cleared after processing
- Reference contexts expire after 5 minutes
- Conversation summaries exclude PII
- Harmonization logs retain only metadata

## Testing

### Property-Based Tests

All correctness properties have corresponding property-based tests:

1. **Property 1**: Recent context priority
2. **Property 2**: Immediate product visibility
3. **Property 3**: Rich message formatting
4. **Property 4**: Message burst harmonization
5. **Property 5**: Checkout guidance completeness
6. **Property 6**: Language consistency
7. **Property 7**: Branded identity
8. **Property 8**: Factual grounding
9. **Property 9**: Conversation history recall
10. **Property 10**: Intent inference from context

### Integration Tests

End-to-end conversation flow tests cover:
- Complete inquiry-to-sale journey
- Multi-turn conversations with context
- Error recovery scenarios
- WhatsApp rich message rendering

## Migration Guide

### Enabling Features

All features are enabled by default. To disable:

```python
agent_config = AgentConfiguration.objects.get(tenant=tenant)
agent_config.enable_message_harmonization = False
agent_config.enable_immediate_product_display = False
agent_config.enable_grounded_validation = False
agent_config.save()
```

### Backward Compatibility

All enhancements are backward compatible:
- Graceful fallback if services fail
- Existing API contracts maintained
- No breaking changes to existing endpoints

### Database Migration

Run migrations to add new fields:

```bash
python manage.py migrate bot
python manage.py migrate tenants
```

## Support

For issues or questions:
- Check logs in CloudWatch/Sentry
- Review metrics in monitoring dashboard
- Contact engineering team via Slack #wabot-support
