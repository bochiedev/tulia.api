# Bot App - Intent Classification Service

This app implements the AI-powered intent classification and handling system for the Tulia WhatsApp commerce platform.

## Overview

The bot app provides natural language understanding capabilities to classify customer messages into actionable intents and route them to appropriate handlers. It uses OpenAI's GPT models for intent classification and entity extraction.

## Components

### Models

#### IntentEvent
Tracks all intent classifications for analytics and debugging.

**Fields:**
- `conversation`: Link to the conversation
- `intent_name`: Classified intent (e.g., BROWSE_PRODUCTS, BOOK_APPOINTMENT)
- `confidence_score`: Confidence from 0.0 to 1.0
- `slots`: Extracted entities/slots as JSON
- `model`: AI model used (e.g., gpt-4)
- `message_text`: Original customer message
- `processing_time_ms`: Classification time in milliseconds
- `metadata`: Additional data (token usage, etc.)

**Indexes:**
- `(conversation, created_at)` - For conversation history
- `(intent_name, created_at)` - For intent analytics
- `confidence_score` - For quality monitoring

### Services

#### IntentService
Core service for classifying customer intents using LLM.

**Key Methods:**
- `classify_intent(message_text, conversation_context)` - Classify message and extract slots
- `extract_slots(message_text, intent)` - Extract entities for specific intent
- `handle_low_confidence(conversation, message_text, confidence_score, attempt_count)` - Handle unclear intents
- `create_intent_event(conversation, message_text, classification_result)` - Create tracking record

**Supported Intents:**

*Product Intents:*
- `GREETING` - Customer greets or starts conversation
- `BROWSE_PRODUCTS` - Browse available products
- `PRODUCT_DETAILS` - View specific product details
- `PRICE_CHECK` - Check product pricing
- `STOCK_CHECK` - Check product availability
- `ADD_TO_CART` - Add product to cart
- `CHECKOUT_LINK` - Complete purchase

*Service Intents:*
- `BROWSE_SERVICES` - Browse available services
- `SERVICE_DETAILS` - View specific service details
- `CHECK_AVAILABILITY` - Check appointment availability
- `BOOK_APPOINTMENT` - Book an appointment
- `RESCHEDULE_APPOINTMENT` - Change appointment time
- `CANCEL_APPOINTMENT` - Cancel appointment

*Consent Intents:*
- `OPT_IN_PROMOTIONS` - Enable promotional messages
- `OPT_OUT_PROMOTIONS` - Disable promotional messages
- `STOP_ALL` - Stop all non-essential messages
- `START_ALL` - Resume all messages

*Support Intents:*
- `HUMAN_HANDOFF` - Request human assistance
- `OTHER` - Unclassified intent

**Configuration:**
- `CONFIDENCE_THRESHOLD`: 0.7 (minimum confidence to accept classification)
- `MAX_LOW_CONFIDENCE_ATTEMPTS`: 2 (auto-handoff after consecutive low confidence)

#### ProductIntentHandler
Handles product-related intents by querying catalog and managing cart.

**Key Methods:**
- `handle_greeting(slots)` - Welcome message
- `handle_browse_products(slots)` - List products with optional search
- `handle_product_details(slots)` - Show product details and variants
- `handle_price_check(slots)` - Display pricing information
- `handle_add_to_cart(slots)` - Add items to cart with stock validation
- `handle_checkout_link(slots)` - Create order and generate checkout link

**Features:**
- Tenant-scoped product queries
- Full-text search on title and description
- Stock availability checking
- Cart management with subtotal calculation
- Variant support

#### ServiceIntentHandler
Handles service-related intents by querying services and managing bookings.

**Key Methods:**
- `handle_browse_services(slots)` - List services with optional search
- `handle_service_details(slots)` - Show service details and variants
- `handle_check_availability(slots)` - Find available appointment slots
- `handle_book_appointment(slots)` - Create appointment with capacity validation
- `handle_cancel_appointment(slots)` - Cancel existing appointment

**Features:**
- Tenant-scoped service queries
- Availability window checking
- Capacity management
- Alternative slot proposals when unavailable
- Natural language date/time parsing

#### HandoffHandler
Handles human handoff requests and automatic escalation.

**Key Methods:**
- `handle_human_handoff(slots, reason)` - Mark conversation for human handling
- `handle_automatic_handoff(low_confidence_count)` - Auto-escalate after low confidence
- `is_handoff_active()` - Check if conversation is with human agent
- `prevent_bot_processing()` - Block bot when handoff active

**Handoff Reasons:**
- `customer_requested` - Customer explicitly asks for human
- `low_confidence` - Bot cannot understand after 2 attempts
- `error` - System error during processing

## Usage

### Basic Intent Classification

```python
from apps.bot.services import create_intent_service

# Create service instance
intent_service = create_intent_service(model='gpt-4')

# Classify customer message
result = intent_service.classify_intent(
    message_text="I want to book a haircut for tomorrow at 2pm",
    conversation_context={
        'last_intent': 'BROWSE_SERVICES',
        'customer_name': 'John'
    }
)

print(result['intent_name'])  # 'BOOK_APPOINTMENT'
print(result['confidence_score'])  # 0.95
print(result['slots'])  # {'service_query': 'haircut', 'date': 'tomorrow', 'time': '2pm'}
```

### Product Intent Handling

```python
from apps.bot.services import create_product_handler
from apps.integrations.services.twilio_service import create_twilio_service_for_tenant

# Create handler
twilio_service = create_twilio_service_for_tenant(tenant)
handler = create_product_handler(tenant, conversation, twilio_service)

# Handle browse products intent
response = handler.handle_browse_products(slots={'product_query': 'shoes'})
handler.send_response(response)
```

### Service Intent Handling

```python
from apps.bot.services import create_service_handler

# Create handler
handler = create_service_handler(tenant, conversation, twilio_service)

# Handle check availability intent
response = handler.handle_check_availability(slots={
    'service_id': 'uuid-here',
    'date': 'tomorrow',
    'time_range': 'morning'
})
handler.send_response(response)
```

### Human Handoff

```python
from apps.bot.services import create_handoff_handler

# Create handler
handler = create_handoff_handler(tenant, conversation, twilio_service)

# Handle explicit handoff request
response = handler.handle_human_handoff(slots={}, reason='customer_requested')
handler.send_response(response)

# Check if handoff is active
if handler.is_handoff_active():
    response = handler.prevent_bot_processing()
    handler.send_response(response)
```

## Configuration

### Environment Variables

```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-...

# Model selection (optional, default: gpt-4)
OPENAI_MODEL=gpt-4
```

### Dependencies

The bot app requires the following Python packages:
- `openai` - OpenAI API client
- `dateparser` - Natural language date parsing

Install with:
```bash
pip install openai dateparser
```

## Database Schema

### IntentEvent Table

```sql
CREATE TABLE intent_events (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    intent_name VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    slots JSONB DEFAULT '{}',
    model VARCHAR(50) NOT NULL,
    message_text TEXT NOT NULL,
    processing_time_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_intent_events_conversation ON intent_events(conversation_id, created_at);
CREATE INDEX idx_intent_events_intent ON intent_events(intent_name, created_at);
CREATE INDEX idx_intent_events_confidence ON intent_events(confidence_score);
```

## Testing

### Unit Tests

```python
from apps.bot.services import IntentService

def test_intent_classification():
    service = IntentService()
    result = service.classify_intent("Show me your products")
    
    assert result['intent_name'] == 'BROWSE_PRODUCTS'
    assert result['confidence_score'] > 0.7
```

### Integration Tests

```python
def test_product_handler_browse():
    handler = create_product_handler(tenant, conversation, twilio_service)
    response = handler.handle_browse_products(slots={})
    
    assert 'message' in response
    assert response['action'] == 'send'
```

## Analytics

Intent events are tracked for:
- Intent distribution analysis
- Confidence score monitoring
- Low-confidence pattern detection
- Processing time optimization
- Model performance comparison

Query examples:

```python
# Get intent distribution
from apps.bot.models import IntentEvent
from django.db.models import Count

distribution = IntentEvent.objects.values('intent_name').annotate(
    count=Count('id')
).order_by('-count')

# Get low confidence intents
low_confidence = IntentEvent.objects.low_confidence(threshold=0.7)

# Get average processing time by intent
from django.db.models import Avg

avg_times = IntentEvent.objects.values('intent_name').annotate(
    avg_time=Avg('processing_time_ms')
)
```

## Error Handling

### IntentServiceError
Raised when intent classification fails due to:
- OpenAI API errors
- Invalid JSON response
- Network timeouts

### ProductHandlerError
Raised when product handling fails due to:
- Twilio send failures
- Database errors

### ServiceHandlerError
Raised when service handling fails due to:
- Booking validation errors
- Twilio send failures

### HandoffHandlerError
Raised when handoff handling fails due to:
- Twilio send failures

## Performance Considerations

### Caching
- Intent classification results are not cached (each message is unique)
- Product/service queries use Django ORM caching
- Conversation context is loaded once per request

### Rate Limiting
- OpenAI API has rate limits (check your plan)
- Implement exponential backoff for retries
- Consider queueing for high-volume scenarios

### Optimization Tips
1. Use lower temperature (0.3) for consistent classification
2. Limit context to recent messages only
3. Batch similar requests when possible
4. Monitor token usage to control costs

## Future Enhancements

- [ ] Support for Claude/Anthropic models
- [ ] Multi-language intent classification
- [ ] Intent confidence calibration
- [ ] Custom intent training
- [ ] Slot validation rules
- [ ] Intent routing optimization
- [ ] A/B testing for prompts
- [ ] Real-time intent analytics dashboard
