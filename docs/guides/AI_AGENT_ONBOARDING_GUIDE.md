# AI Agent Onboarding Guide

## Welcome to Your AI-Powered Customer Service Agent

This guide will help you set up and configure your AI agent to provide intelligent, personalized customer service through WhatsApp. By the end of this guide, your agent will be ready to handle customer inquiries, answer questions from your knowledge base, and seamlessly escalate to human agents when needed.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Agent Configuration](#agent-configuration)
4. [Knowledge Base Setup](#knowledge-base-setup)
5. [Model Selection and Costs](#model-selection-and-costs)
6. [Best Practices](#best-practices)
7. [Testing Your Agent](#testing-your-agent)
8. [Monitoring and Optimization](#monitoring-and-optimization)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before setting up your AI agent, ensure you have:

- ✅ Active WabotIQ tenant account
- ✅ WhatsApp Business API integration configured
- ✅ API credentials (Tenant ID and API Key)
- ✅ Required RBAC scope: `integrations:manage`
- ✅ OpenAI API key configured in tenant settings (or Together AI for alternative models)

---

## Quick Start

### Step 1: Enable the AI Agent

The AI agent is enabled by default for all tenants. To verify or toggle:

```bash
# Check if AI agent is enabled
python manage.py toggle_ai_agent --tenant-id=<your-tenant-id> --status
```

### Step 2: Configure Your Agent

Get your current agent configuration:

```bash
curl -X GET https://api.tulia.ai/v1/bot/agent-config \
  -H "X-TENANT-ID: <your-tenant-id>" \
  -H "X-TENANT-API-KEY: <your-api-key>"
```

Update basic settings:

```bash
curl -X PUT https://api.tulia.ai/v1/bot/agent-config \
  -H "X-TENANT-ID: <your-tenant-id>" \
  -H "X-TENANT-API-KEY: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "Sarah",
    "tone": "friendly",
    "default_model": "gpt-4o"
  }'
```

### Step 3: Add Knowledge Base Entries

Create your first FAQ entry:

```bash
curl -X POST https://api.tulia.ai/v1/bot/knowledge \
  -H "X-TENANT-ID: <your-tenant-id>" \
  -H "X-TENANT-API-KEY: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "entry_type": "faq",
    "title": "What are your business hours?",
    "content": "We are open Monday-Friday 9am-5pm EST, and Saturday 10am-2pm EST. We are closed on Sundays.",
    "keywords_list": ["hours", "schedule", "open", "closed", "time"],
    "priority": 90
  }'
```

### Step 4: Test Your Agent

Send a test message through WhatsApp to your business number and ask about business hours. The agent should respond using the knowledge you just added!

---

## Agent Configuration

### Persona Configuration

Define your agent's personality to match your brand:

```json
{
  "agent_name": "Sarah",
  "personality_traits": {
    "helpful": true,
    "empathetic": true,
    "professional": true,
    "patient": true
  },
  "tone": "friendly"
}
```

**Tone Options:**
- `professional` - Formal, business-like communication
- `friendly` - Warm, approachable, conversational
- `casual` - Relaxed, informal language
- `formal` - Very professional, structured responses

**Choosing the Right Tone:**
- **Retail/E-commerce**: `friendly` or `casual`
- **Healthcare**: `professional` with empathetic traits
- **Financial Services**: `formal` or `professional`
- **Hospitality**: `friendly` with helpful traits
- **B2B Services**: `professional`

### Model Configuration

Configure which AI models to use:

```json
{
  "default_model": "gpt-4o",
  "fallback_models": ["gpt-4o-mini"],
  "temperature": 0.7
}
```

**Model Options:**
- `gpt-4o` - Best balance of capability and cost (recommended)
- `gpt-4o-mini` - Fast and cost-effective for simple queries
- `o1-preview` - Advanced reasoning for complex questions
- `o1-mini` - Cost-effective reasoning model

**Temperature Settings:**
- `0.3-0.5` - Consistent, predictable responses (recommended for customer service)
- `0.6-0.8` - Balanced creativity and consistency
- `0.9-1.2` - More creative, varied responses

### Behavior Configuration

Control how your agent responds:

```json
{
  "max_response_length": 500,
  "behavioral_restrictions": [
    "Do not provide medical advice",
    "Do not provide legal advice",
    "Do not discuss competitor products"
  ],
  "required_disclaimers": [
    "I'm an AI assistant and my responses are for informational purposes only."
  ]
}
```

**Response Length Guidelines:**
- `200-300` - Short, concise responses (mobile-friendly)
- `400-500` - Standard responses with details
- `600-800` - Detailed explanations (use sparingly)

### Handoff Configuration

Configure when to escalate to human agents:

```json
{
  "confidence_threshold": 0.7,
  "auto_handoff_topics": [
    "refunds",
    "complaints",
    "account issues",
    "billing disputes"
  ],
  "max_low_confidence_attempts": 2
}
```

**Confidence Threshold Guidelines:**
- `0.8-0.9` - Conservative (more handoffs, higher quality)
- `0.7-0.8` - Balanced (recommended)
- `0.5-0.7` - Aggressive (fewer handoffs, may reduce quality)

**Auto-Handoff Topics:**
Add topics that always require human attention:
- Sensitive issues (complaints, disputes)
- Complex transactions (refunds, cancellations)
- Account security matters
- Regulatory compliance topics

### Feature Flags

Enable or disable specific features:

```json
{
  "enable_proactive_suggestions": true,
  "enable_spelling_correction": true,
  "enable_rich_messages": true
}
```

**Feature Descriptions:**
- `enable_proactive_suggestions` - Agent suggests relevant products/services
- `enable_spelling_correction` - Automatically corrects typos
- `enable_rich_messages` - Uses WhatsApp buttons, lists, and images

---

## Knowledge Base Setup

### Entry Types

The knowledge base supports six entry types:

1. **FAQ** - Frequently asked questions and answers
2. **Policy** - Business policies (returns, shipping, privacy)
3. **Product Info** - Detailed product information
4. **Service Info** - Service descriptions and details
5. **Procedure** - Step-by-step instructions
6. **General** - Other business information

### Creating Effective Knowledge Entries

#### FAQ Entries

```json
{
  "entry_type": "faq",
  "title": "What is your return policy?",
  "content": "We offer a 30-day return policy for all products. Items must be unused and in original packaging. To initiate a return, contact our support team with your order number. Refunds are processed within 5-7 business days after we receive the returned item.",
  "category": "returns",
  "keywords_list": ["return", "refund", "exchange", "money back", "send back"],
  "priority": 90
}
```

**FAQ Best Practices:**
- Write clear, complete answers
- Include all relevant details (timeframes, requirements, steps)
- Use customer language, not internal jargon
- Add common variations as keywords

#### Policy Entries

```json
{
  "entry_type": "policy",
  "title": "Shipping Policy",
  "content": "We offer free standard shipping on orders over $50. Standard shipping takes 5-7 business days. Express shipping (2-3 days) is available for $15. International shipping is available to select countries with delivery times of 10-15 business days. All orders are shipped from our warehouse in California.",
  "category": "shipping",
  "keywords_list": ["shipping", "delivery", "freight", "mail", "send"],
  "priority": 85
}
```

#### Product/Service Info

```json
{
  "entry_type": "product_info",
  "title": "Premium Subscription Features",
  "content": "Our Premium subscription includes: unlimited messaging, advanced analytics, custom branding, priority support, API access, and webhook integrations. The subscription is billed monthly at $99/month or annually at $999/year (save 16%). You can upgrade or downgrade at any time.",
  "category": "subscriptions",
  "keywords_list": ["premium", "subscription", "features", "upgrade", "plan"],
  "priority": 80,
  "metadata": {
    "product_id": "premium-sub",
    "price_monthly": 99,
    "price_annual": 999
  }
}
```

### Priority System

Priority determines which entries are shown first when multiple entries match:

- **90-100**: Critical information (hours, contact info, urgent policies)
- **70-89**: Important information (main products, key policies)
- **50-69**: Standard information (general FAQs)
- **0-49**: Supplementary information (nice-to-know details)

### Keywords Strategy

Add keywords that customers might use:

```json
{
  "keywords_list": [
    "hours",           // Exact term
    "schedule",        // Synonym
    "open",            // Related term
    "closed",          // Related term
    "time",            // Related term
    "when open",       // Phrase
    "operating hours", // Formal term
    "business hours"   // Formal term
  ]
}
```

**Keyword Tips:**
- Include common misspellings
- Add abbreviations (e.g., "hrs" for "hours")
- Include informal terms (e.g., "biz hours")
- Add question words (e.g., "when", "what time")

### Bulk Import

For initial setup, use bulk import:

**CSV Format:**
```csv
entry_type,title,content,category,keywords,priority,is_active
faq,"What are your hours?","We are open Mon-Fri 9am-5pm EST.",general,"hours,schedule,open",90,true
policy,"Return Policy","30-day returns on all items.",returns,"return,refund,exchange",85,true
```

**Import Command:**
```bash
curl -X POST https://api.tulia.ai/v1/bot/knowledge/bulk-import \
  -H "X-TENANT-ID: <your-tenant-id>" \
  -H "X-TENANT-API-KEY: <your-api-key>" \
  -H "Content-Type: text/csv" \
  --data-binary @knowledge_base.csv
```

### Knowledge Base Organization

**Recommended Categories:**
- `general` - Business hours, location, contact
- `products` - Product information
- `services` - Service descriptions
- `orders` - Order process, tracking
- `shipping` - Shipping and delivery
- `returns` - Returns and refunds
- `payments` - Payment methods, billing
- `account` - Account management
- `technical` - Technical support

---

## Model Selection and Costs

### Understanding AI Models

#### GPT-4o (Recommended)
- **Best for**: General customer service, balanced performance
- **Strengths**: Fast, accurate, cost-effective
- **Cost**: ~$0.015 per conversation
- **Use when**: 80% of queries

#### GPT-4o-mini
- **Best for**: Simple FAQs, quick responses
- **Strengths**: Very fast, lowest cost
- **Cost**: ~$0.001 per conversation
- **Use when**: Simple, straightforward questions

#### o1-preview
- **Best for**: Complex reasoning, multi-step problems
- **Strengths**: Advanced reasoning capabilities
- **Cost**: ~$0.045 per conversation
- **Use when**: Complex technical questions, troubleshooting

#### o1-mini
- **Best for**: Cost-effective reasoning
- **Strengths**: Good reasoning at lower cost
- **Cost**: ~$0.015 per conversation
- **Use when**: Moderate complexity questions

### Cost Optimization Strategies

1. **Use GPT-4o as default** - Best balance for most queries
2. **Set up fallbacks** - Use GPT-4o-mini as fallback for simple queries
3. **Optimize knowledge base** - Better knowledge = fewer complex queries
4. **Monitor analytics** - Track which models are used most
5. **Set cost alerts** - Monitor monthly spending

### Monthly Cost Estimates

**Small Business (100 conversations/month):**
- Mostly GPT-4o: $5-10/month
- Mixed models: $15-25/month

**Medium Business (1,000 conversations/month):**
- Mostly GPT-4o: $50-100/month
- Mixed models: $150-250/month

**Large Business (10,000 conversations/month):**
- Mostly GPT-4o: $500-1,000/month
- Mixed models: $1,500-2,500/month

### Cost Monitoring

Check your costs regularly:

```bash
curl -X GET "https://api.tulia.ai/v1/bot/analytics/costs?start_date=2024-01-01" \
  -H "X-TENANT-ID: <your-tenant-id>" \
  -H "X-TENANT-API-KEY: <your-api-key>"
```

---

## Best Practices

### 1. Start Simple

Begin with basic configuration:
- Use default model (GPT-4o)
- Start with friendly tone
- Add 10-20 essential knowledge entries
- Enable all features
- Test with real scenarios

### 2. Build Your Knowledge Base Gradually

**Week 1**: Core information
- Business hours
- Contact information
- Top 5 FAQs
- Main products/services
- Basic policies

**Week 2**: Expand coverage
- Additional FAQs from customer inquiries
- Detailed product information
- Shipping and returns
- Payment information

**Week 3**: Optimize
- Review analytics for common topics
- Add missing knowledge entries
- Refine existing entries
- Adjust priorities

### 3. Monitor and Iterate

**Daily** (first week):
- Check handoff rate
- Review low-confidence interactions
- Add missing knowledge

**Weekly**:
- Review analytics dashboard
- Check cost trends
- Update knowledge base
- Adjust configuration

**Monthly**:
- Comprehensive performance review
- Cost optimization
- Feature evaluation
- Strategy adjustment

### 4. Knowledge Base Maintenance

- **Review quarterly**: Update outdated information
- **Add seasonally**: Holiday hours, seasonal products
- **Remove obsolete**: Discontinued products, old policies
- **Refine continuously**: Improve based on customer feedback

### 5. Handoff Strategy

**Good handoff triggers:**
- Customer explicitly requests human
- Confidence below threshold after 2 attempts
- Sensitive topics (complaints, refunds)
- Complex technical issues

**Poor handoff triggers:**
- First low-confidence response
- Any mention of specific keywords
- Time-based (e.g., after 5 messages)

### 6. Response Quality

**Do:**
- Keep responses concise and clear
- Use bullet points for lists
- Include specific details (prices, timeframes)
- Provide next steps
- Offer to help further

**Don't:**
- Use overly technical language
- Provide incomplete information
- Make promises the agent can't keep
- Ignore customer sentiment
- Give generic responses

---

## Testing Your Agent

### Test Scenarios

#### Scenario 1: Simple FAQ
**Customer**: "What are your hours?"  
**Expected**: Agent responds with business hours from knowledge base  
**Check**: Response is accurate, complete, and friendly

#### Scenario 2: Product Inquiry
**Customer**: "Tell me about your premium plan"  
**Expected**: Agent provides features, pricing, and benefits  
**Check**: Information matches your product details

#### Scenario 3: Spelling Errors
**Customer**: "Wat r ur ours?"  
**Expected**: Agent understands and responds about hours  
**Check**: Spelling correction works

#### Scenario 4: Multi-Intent
**Customer**: "What are your hours and do you ship internationally?"  
**Expected**: Agent addresses both questions  
**Check**: Both intents are handled

#### Scenario 5: Low Confidence
**Customer**: "I have a problem with my account"  
**Expected**: Agent asks for clarification or offers handoff  
**Check**: Appropriate escalation

#### Scenario 6: Handoff Request
**Customer**: "I need to speak to a human"  
**Expected**: Agent immediately offers handoff  
**Check**: Handoff is triggered

### Testing Checklist

- [ ] Agent responds to basic FAQs
- [ ] Knowledge base search works
- [ ] Spelling correction functions
- [ ] Multi-intent handling works
- [ ] Handoff triggers appropriately
- [ ] Rich messages display correctly (if enabled)
- [ ] Response tone matches configuration
- [ ] Behavioral restrictions are enforced
- [ ] Required disclaimers are included
- [ ] Cost tracking is accurate

---

## Monitoring and Optimization

### Key Metrics to Track

1. **Conversation Statistics**
   - Total interactions
   - Average confidence score
   - Response time

2. **Handoff Analytics**
   - Handoff rate (target: <10%)
   - Handoff reasons
   - Attempts before handoff

3. **Cost Analytics**
   - Total cost
   - Cost per conversation
   - Cost by model

4. **Topic Analytics**
   - Common intents
   - Missing knowledge areas
   - Trending topics

### Optimization Workflow

**Step 1: Identify Issues**
```bash
# Check handoff analytics
curl -X GET "https://api.tulia.ai/v1/bot/analytics/handoffs" \
  -H "X-TENANT-ID: <your-tenant-id>" \
  -H "X-TENANT-API-KEY: <your-api-key>"
```

**Step 2: Analyze Root Causes**
- High handoff rate? → Add knowledge entries
- Low confidence? → Improve existing entries
- High costs? → Optimize model selection
- Common topics? → Prioritize those entries

**Step 3: Implement Changes**
- Add/update knowledge entries
- Adjust configuration
- Refine keywords
- Update priorities

**Step 4: Measure Impact**
- Wait 1-2 weeks
- Compare metrics
- Iterate as needed

### Performance Targets

**Good Performance:**
- Handoff rate: <10%
- Average confidence: >0.75
- Response time: <3 seconds
- Cost per conversation: <$0.02

**Excellent Performance:**
- Handoff rate: <5%
- Average confidence: >0.85
- Response time: <2 seconds
- Cost per conversation: <$0.015

---

## Troubleshooting

### Issue: High Handoff Rate

**Symptoms**: >15% of conversations escalate to humans

**Solutions**:
1. Check handoff analytics for common reasons
2. Add knowledge entries for missing topics
3. Increase confidence threshold slightly
4. Review and improve existing entries
5. Ensure keywords are comprehensive

### Issue: Low Confidence Scores

**Symptoms**: Average confidence <0.65

**Solutions**:
1. Improve knowledge entry content
2. Add more specific keywords
3. Increase entry priorities for important topics
4. Use more detailed, complete answers
5. Consider using a more capable model

### Issue: High Costs

**Symptoms**: Costs exceed budget

**Solutions**:
1. Switch default model to GPT-4o-mini
2. Optimize knowledge base to reduce complex queries
3. Set up model fallbacks
4. Review token usage per interaction
5. Implement cost alerts

### Issue: Irrelevant Responses

**Symptoms**: Agent provides wrong or off-topic answers

**Solutions**:
1. Review knowledge entry keywords
2. Ensure entry content is clear and specific
3. Check for conflicting entries
4. Adjust entry priorities
5. Add behavioral restrictions

### Issue: Slow Response Times

**Symptoms**: >5 seconds per response

**Solutions**:
1. Switch to faster model (GPT-4o-mini)
2. Reduce context size
3. Optimize knowledge base size
4. Check API latency
5. Review system performance

### Issue: Agent Ignores Configuration

**Symptoms**: Tone or behavior doesn't match settings

**Solutions**:
1. Clear configuration cache
2. Verify configuration was saved
3. Check for conflicting settings
4. Review behavioral restrictions
5. Test with simple queries first

---

## Next Steps

After completing this onboarding:

1. **Week 1**: Monitor daily, add missing knowledge
2. **Week 2**: Optimize based on analytics
3. **Week 3**: Fine-tune configuration
4. **Month 2**: Expand knowledge base
5. **Month 3**: Advanced features (rich messages, suggestions)

## Additional Resources

- **API Documentation**: `/docs/api/AI_AGENT_API_GUIDE.md`
- **Deployment Guide**: `/docs/AI_AGENT_DEPLOYMENT_CHECKLIST.md`
- **Support**: support@tulia.ai
- **Status Page**: https://status.tulia.ai

---

## Feedback

We're constantly improving the AI agent. Share your feedback:
- Feature requests
- Bug reports
- Documentation improvements
- Success stories

Contact: support@tulia.ai

---

**Congratulations!** Your AI agent is now configured and ready to provide intelligent customer service. Remember to monitor, iterate, and optimize based on your specific needs and customer feedback.
