# AI Agent New Features Guide

This guide documents the new features added to the AI-powered customer service agent (Tasks 20-26).

## Table of Contents

1. [Catalog Browsing and Pagination](#catalog-browsing-and-pagination)
2. [Product Intelligence and AI Recommendations](#product-intelligence-and-ai-recommendations)
3. [Multi-Language Support](#multi-language-support)
4. [Reference Context and Positional Resolution](#reference-context-and-positional-resolution)
5. [Discovery and Intelligent Narrowing](#discovery-and-intelligent-narrowing)
6. [Progressive Handoff](#progressive-handoff)
7. [Shortened Purchase Journey](#shortened-purchase-journey)

---

## Catalog Browsing and Pagination

### Overview

The catalog browsing feature allows customers to navigate large product or service catalogs efficiently using pagination. Instead of overwhelming customers with hundreds of items, the system shows 5 items at a time with easy navigation.

### How It Works

1. **Automatic Pagination**: When a search returns more than 5 items, the system automatically creates a browse session
2. **Navigation Controls**: Customers can use "Next 5", "Previous 5", or "Search" buttons
3. **Position Indicator**: Shows "Showing 1-5 of 247" so customers know where they are
4. **Session Management**: Browse sessions expire after 10 minutes of inactivity

### Example Conversation

```
Customer: Show me all face creams
Agent: I found 47 face creams for you! Here are the first 5:

1. Organic Face Cream - $25.00
2. Anti-Aging Serum - $35.00
3. Moisturizing Lotion - $20.00
4. Night Repair Cream - $40.00
5. Daily Hydrator - $18.00

Showing 1-5 of 47
[Next 5] [Search]

Customer: Next 5
Agent: Here are items 6-10:
...
```

### Best Practices for Catalog Organization

1. **Clear Product Titles**: Use descriptive, searchable titles
2. **Consistent Pricing**: Ensure prices are up-to-date
3. **Good Descriptions**: Write clear, concise product descriptions
4. **Categories**: Use categories to help customers filter
5. **Stock Status**: Keep inventory status current

### API Usage

```python
from apps.bot.services.catalog_browser_service import CatalogBrowserService

browser = CatalogBrowserService()

# Start a browse session
session = browser.start_browse_session(
    conversation=conversation,
    catalog_type='products',
    queryset=Product.objects.filter(tenant=tenant, is_active=True),
    items_per_page=5
)

# Get current page
items, has_next, has_prev = browser.get_page(session, page=1)

# Navigate
items, has_next, has_prev = browser.next_page(session)
```

---

## Product Intelligence and AI Recommendations

### Overview

The product intelligence feature uses AI to analyze products and match them to customer needs semantically. Instead of simple keyword matching, the system understands what customers are looking for and recommends products that truly fit their needs.

### How It Works

1. **Product Analysis**: AI analyzes each product to extract:
   - Key features
   - Use cases
   - Target audience
   - Distinguishing characteristics

2. **Semantic Matching**: When customers describe what they need, the system:
   - Understands the intent (not just keywords)
   - Matches needs to product characteristics
   - Ranks products by relevance

3. **Explanations**: Recommendations include explanations:
   - "I recommend [Product] because it has [feature] which is perfect for [use case]"

### Example Conversation

```
Customer: I need something for dry sensitive skin
Agent: Based on your needs, I recommend:

1. **Gentle Hydrating Cream** - $28.00
   Perfect for sensitive skin with natural ingredients like aloe vera and chamomile. 
   Provides deep hydration without irritation.

2. **Sensitive Skin Moisturizer** - $32.00
   Hypoallergenic formula specifically designed for sensitive skin types.
   Fragrance-free and dermatologist-tested.

Would you like more details about either of these?
```

### Guidelines for Product Descriptions

To get the best AI recommendations, write product descriptions that include:

1. **Key Features**: What makes this product special?
2. **Use Cases**: What problems does it solve?
3. **Target Audience**: Who is this for?
4. **Ingredients/Materials**: What's it made of?
5. **Benefits**: What will customers gain?

**Good Example**:
```
Organic Face Cream - Natural moisturizing cream with aloe vera and vitamin E. 
Perfect for sensitive skin. Provides 24-hour hydration without clogging pores. 
Ideal for daily use, especially for those with dry or combination skin types.
```

**Poor Example**:
```
Face Cream - Good cream for face
```

### API Usage

```python
from apps.bot.services.product_intelligence import ProductIntelligenceService

service = ProductIntelligenceService()

# Analyze a product
analysis = service.analyze_product(product)

# Match customer need to products
matches = service.match_need_to_products(
    tenant=tenant,
    customer_need="I need something for dry skin",
    limit=5
)

# Generate recommendation explanation
explanation = service.generate_recommendation_explanation(
    product=product,
    customer_need="dry skin care"
)
```

---

## Multi-Language Support

### Overview

The AI agent supports multi-language conversations in English, Swahili, and Sheng (Kenyan slang). Customers can mix languages naturally, and the agent will respond in their preferred language.

### Supported Languages

1. **English**: Full support
2. **Swahili**: Common phrases and vocabulary
3. **Sheng**: Popular slang terms
4. **Code-Switching**: Mixed language conversations

### Common Phrases

**Swahili**:
- `nataka` / `ninataka` = I want
- `nipe` = give me
- `bei gani` = what price
- `iko` = is it available
- `ngapi` = how much
- `tafadhali` = please

**Sheng**:
- `sawa` = okay
- `poa` = cool/good
- `fiti` = good/fine
- `doh` / `mbao` = money
- `maze` = friend/bro

### Example Conversations

**Pure Swahili**:
```
Customer: Nataka kununua cream ya uso
Agent: Nimepata cream 5 za uso. Hizi ni za kwanza:
1. Organic Face Cream - $25.00
...
```

**Mixed Language**:
```
Customer: Nataka to buy hiyo face cream
Agent: Sawa! The Organic Face Cream costs $25.00. Would you like to proceed with the purchase?
```

**Sheng**:
```
Customer: Maze, nipe hiyo product ya kwanza. Bei gani?
Agent: Sawa bro! That product costs $25.00. Poa?
```

### Expanding the Phrase Dictionary

To add new phrases, update `apps/bot/services/multi_language_processor.py`:

```python
SWAHILI_PHRASES = {
    'nataka': 'I want',
    'nipe': 'give me',
    # Add new phrases here
}

SHENG_PHRASES = {
    'sawa': 'okay',
    'poa': 'cool',
    # Add new phrases here
}
```

---

## Reference Context and Positional Resolution

### Overview

Customers can refer to items by position ("the first one", "number 2") instead of repeating full product names. The system remembers recently shown lists and resolves these references automatically.

### How It Works

1. **Context Storage**: When showing a list, the system stores it for 5 minutes
2. **Reference Detection**: Detects when customer uses positional references
3. **Resolution**: Maps references to actual items
4. **Confirmation**: Always confirms what item they mean

### Supported References

**Numeric**:
- "1", "2", "3", etc.
- "number 1", "number 2"

**Ordinal**:
- "first", "first one", "the first"
- "second", "second one", "the second"
- "last", "last one", "the last"

### Example Conversation

```
Customer: Show me face creams
Agent: Here are 5 face creams:
1. Organic Face Cream - $25.00
2. Anti-Aging Serum - $35.00
3. Moisturizing Lotion - $20.00
4. Night Repair Cream - $40.00
5. Daily Hydrator - $18.00

Customer: I want the first one
Agent: You mean the Organic Face Cream ($25.00)? Great choice! 
Would you like to proceed with the purchase?

Customer: Yes
Agent: Perfect! How many would you like to order?
```

### API Usage

```python
from apps.bot.services.reference_context_manager import ReferenceContextManager

manager = ReferenceContextManager()

# Store list context
context = manager.store_list_context(
    conversation=conversation,
    list_type='products',
    items=[
        {'id': '1', 'title': 'Product A', 'type': 'product'},
        {'id': '2', 'title': 'Product B', 'type': 'product'}
    ]
)

# Resolve reference
resolved = manager.resolve_reference(conversation, "the first one")
# Returns: {'id': '1', 'title': 'Product A', 'type': 'product'}
```

---

## Discovery and Intelligent Narrowing

### Overview

When customers have many options (>10 results), the agent asks clarifying questions to narrow down choices instead of overwhelming them with a long list.

### How It Works

1. **Detection**: System detects when there are too many results
2. **Question Generation**: AI generates 2-3 specific clarifying questions
3. **Filtering**: Uses customer responses to filter results
4. **Presentation**: Shows narrowed results with match highlights

### Example Conversation

```
Customer: I need a face cream
Agent: I found 47 face creams! To help you find the perfect one, 
I have a few questions:

1. What's your budget range? (Under $20, $20-$40, Over $40)
2. What's your skin type? (Dry, Oily, Combination, Sensitive)
3. Any specific concerns? (Anti-aging, Acne, Hydration, Brightening)

Customer: Under $20 and for dry skin
Agent: Perfect! Based on your preferences, here are the top 3 matches:

1. **Daily Hydrator** - $18.00
   ✓ Under $20
   ✓ Specifically formulated for dry skin
   ✓ Provides 24-hour moisture

2. **Gentle Moisturizer** - $16.00
   ✓ Budget-friendly
   ✓ Great for dry, sensitive skin
   ✓ Fragrance-free

Would you like more details about either of these?
```

### Clarifying Question Types

1. **Price Range**: Budget constraints
2. **Features**: Specific characteristics (color, size, scent)
3. **Use Case**: What they'll use it for
4. **Preferences**: Personal preferences (brand, ingredients)

### API Usage

```python
from apps.bot.services.discovery_service import DiscoveryService

service = DiscoveryService()

# Check if clarification is needed
should_ask = service.should_ask_clarifying_questions(
    result_count=47,
    has_filters=False
)

# Generate questions
questions = service.generate_clarifying_questions(
    customer_message="I need a face cream",
    result_count=47,
    tenant=tenant
)

# Apply preferences to filter
filtered_results = service.apply_preferences(
    queryset=products,
    preferences={'price_max': 20, 'skin_type': 'dry'}
)
```

---

## Progressive Handoff

### Overview

Instead of immediately offering human handoff when uncertain, the agent makes genuine attempts to help with clarifying questions. Handoff is only suggested after real attempts to assist.

### How It Works

1. **Clarification First**: Agent asks 2 clarifying questions before suggesting handoff
2. **Specific Questions**: Questions are specific to the customer's situation
3. **Handoff Explanation**: When suggesting handoff, agent explains:
   - What it understood
   - What it tried
   - Why human assistance would be better
4. **Options**: Offers multiple options (handoff, rephrase, alternatives)

### Immediate Handoff Triggers

These situations trigger immediate handoff without clarification:

1. **Explicit Request**: "I want to talk to a human"
2. **Complaints**: Refunds, complaints, legal matters
3. **Technical Issues**: Payment failures, account problems
4. **Custom Orders**: Special requests beyond standard catalog

### Example Conversation

**With Clarification**:
```
Customer: I need something
Agent: I'd be happy to help! Could you tell me more about what you're looking for?
- Are you interested in products or services?
- What's the main purpose or use case?

Customer: Something for my face
Agent: Great! Are you looking for:
- Skincare (creams, serums, cleansers)?
- Makeup (foundation, concealer)?
- Treatment (acne, anti-aging)?

Customer: I don't know, just something good
Agent: I understand you're looking for facial care but need help deciding. 
Here's what I've tried:
- Asked about product category
- Asked about specific needs

A human agent can have a detailed conversation to understand your needs better 
and recommend the perfect products. Would you like me to connect you with someone?

Options:
1. Connect with human agent
2. Let me try showing you our most popular facial products
3. Tell me more about your skin concerns
```

**Immediate Handoff**:
```
Customer: I want to speak to a human
Agent: Of course! I'll connect you with a human agent right away.
```

### API Usage

```python
from apps.bot.services.progressive_handoff import ProgressiveHandoffService

service = ProgressiveHandoffService()

# Evaluate if handoff is needed
should_handoff, action = service.evaluate_handoff_need(
    conversation=conversation,
    confidence_score=0.5,
    clarification_count=1,
    max_clarifications=2
)

# Detect explicit handoff request
is_explicit = service.detect_explicit_handoff_request(
    "I want to talk to a person"
)
```

---

## Shortened Purchase Journey

### Overview

Direct action buttons ("Buy Now", "Book Now") allow customers to complete purchases or bookings with minimal steps, reducing friction in the customer journey.

### Features

1. **Product Cards**: Show product with "Buy Now" and "More Details" buttons
2. **Service Cards**: Show service with "Book Now" and "Check Availability" buttons
3. **Streamlined Checkout**: Collect only essential information
4. **Pre-filled Data**: Use customer history to pre-fill forms
5. **One-Click Actions**: Minimize confirmation steps

### Example Conversations

**Product Purchase**:
```
Customer: Show me the Organic Face Cream
Agent: [Product Card]
Organic Face Cream
$25.00
Natural moisturizing cream with aloe vera

[Buy Now] [More Details]

Customer: [Clicks Buy Now]
Agent: Great choice! How many would you like?

Customer: 2
Agent: Perfect! 2 x Organic Face Cream = $50.00

Delivery to: [Your saved address]
Payment: [Your saved method]

[Confirm Order] [Change Details]
```

**Service Booking**:
```
Customer: I want to book a massage
Agent: [Service Card]
Relaxing Massage
$50.00 | 60 minutes
Professional massage therapy

[Book Now] [Check Availability]

Customer: [Clicks Book Now]
Agent: Available time slots today:
- 2:00 PM
- 4:00 PM
- 6:00 PM

Which time works for you?

Customer: 4 PM
Agent: Booked! Relaxing Massage at 4:00 PM today.
Confirmation sent to your phone.
```

### Configuration

Enable direct actions in agent configuration:

```python
agent_config = AgentConfiguration.objects.get(tenant=tenant)
agent_config.enable_rich_messages = True
agent_config.save()
```

### API Usage

```python
from apps.bot.services.direct_action_handler import DirectActionHandler

handler = DirectActionHandler()

# Handle product action
result = handler.handle_product_action(
    action='buy_now',
    product=product,
    customer=customer,
    conversation=conversation
)

# Handle service action
result = handler.handle_service_action(
    action='book_now',
    service=service,
    customer=customer,
    conversation=conversation
)
```

---

## Configuration

### Agent Configuration

All new features can be enabled/disabled per tenant:

```python
from apps.bot.models import AgentConfiguration

config = AgentConfiguration.objects.get(tenant=tenant)

# Enable/disable features
config.enable_rich_messages = True  # For pagination, cards, buttons
config.enable_proactive_suggestions = True  # For AI recommendations
config.enable_spelling_correction = True  # For multi-language support

config.save()
```

### Feature Flags

Use tenant settings for gradual rollout:

```python
# Enable for specific tenant
tenant.settings.set_feature('ai_agent_pagination', True)
tenant.settings.set_feature('ai_agent_multi_language', True)
tenant.settings.set_feature('ai_agent_product_intelligence', True)
```

---

## Monitoring and Analytics

### Key Metrics

Track these metrics to measure feature effectiveness:

1. **Pagination Usage**:
   - Browse sessions created
   - Average pages viewed
   - Completion rate

2. **Product Intelligence**:
   - Recommendation acceptance rate
   - Match quality scores
   - Customer satisfaction

3. **Multi-Language**:
   - Language distribution
   - Code-switching frequency
   - Translation accuracy

4. **Reference Resolution**:
   - Reference usage rate
   - Resolution accuracy
   - Confirmation rate

5. **Discovery**:
   - Clarification success rate
   - Filter effectiveness
   - Result narrowing impact

6. **Progressive Handoff**:
   - Clarification attempts before handoff
   - Handoff rate reduction
   - Customer satisfaction

7. **Direct Actions**:
   - Button click rate
   - Conversion rate
   - Average time to purchase

### Analytics API

```python
from apps.bot.views_agent_interactions import AgentAnalyticsView

# Get analytics for new features
analytics = AgentAnalyticsView.get_feature_analytics(
    tenant=tenant,
    start_date=start_date,
    end_date=end_date
)
```

---

## Troubleshooting

### Common Issues

1. **Pagination not working**:
   - Check that `enable_rich_messages` is True
   - Verify browse session hasn't expired
   - Check that result count > 5

2. **References not resolving**:
   - Verify reference context hasn't expired (5 min)
   - Check that list was stored correctly
   - Ensure reference format is supported

3. **Multi-language not detecting**:
   - Update phrase dictionary
   - Check language detection thresholds
   - Verify message preprocessing

4. **Product intelligence not matching**:
   - Ensure products have good descriptions
   - Run product analysis task
   - Check embedding generation

5. **Clarifying questions not asked**:
   - Verify result count > 10
   - Check discovery service configuration
   - Ensure LLM is accessible

---

## Best Practices

1. **Catalog Organization**:
   - Use clear, descriptive titles
   - Write detailed product descriptions
   - Keep inventory up-to-date
   - Use consistent categorization

2. **Product Descriptions**:
   - Include key features
   - Describe use cases
   - Specify target audience
   - List benefits clearly

3. **Multi-Language**:
   - Expand phrase dictionary regularly
   - Monitor language usage patterns
   - Test with native speakers
   - Handle mixed languages gracefully

4. **Customer Experience**:
   - Keep pagination to 5 items
   - Always confirm references
   - Ask specific clarifying questions
   - Minimize steps in purchase journey

5. **Monitoring**:
   - Track feature usage metrics
   - Monitor customer satisfaction
   - Analyze handoff rates
   - Review conversation logs

---

## Future Enhancements

Planned improvements for these features:

1. **Pagination**:
   - Visual product cards in lists
   - Filter controls in pagination
   - Search within results

2. **Product Intelligence**:
   - Image-based recommendations
   - Collaborative filtering
   - Trend analysis

3. **Multi-Language**:
   - More languages (French, Arabic)
   - Voice message support
   - Dialect variations

4. **Discovery**:
   - Visual preference selection
   - Comparison tools
   - Saved searches

5. **Direct Actions**:
   - One-click reorder
   - Subscription options
   - Gift purchases

---

## Support

For questions or issues with these features:

1. Check this documentation
2. Review conversation logs
3. Check analytics dashboard
4. Contact development team

---

**Last Updated**: November 2025
**Version**: 1.0
