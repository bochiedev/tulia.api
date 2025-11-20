# Conversational Commerce UX Enhancement - Admin Configuration Guide

## Overview

This guide explains how to configure and manage the Conversational Commerce UX Enhancement features for your WabotIQ tenant. These features transform your bot into an intelligent sales assistant that provides smooth inquiry-to-sale journeys.

## Table of Contents

1. [Feature Overview](#feature-overview)
2. [Configuration Settings](#configuration-settings)
3. [Django Admin Interface](#django-admin-interface)
4. [Feature Flags](#feature-flags)
5. [Monitoring & Analytics](#monitoring--analytics)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

## Feature Overview

### Core Features

| Feature | Description | Default |
|---------|-------------|---------|
| Message Harmonization | Combines rapid messages into one response | Enabled |
| Reference Resolution | Resolves "1", "first", etc. to actual items | Enabled |
| Immediate Product Display | Shows products without category narrowing | Enabled |
| Language Consistency | Maintains consistent language throughout | Enabled |
| Branded Identity | Uses business name in bot introduction | Enabled |
| Grounded Validation | Verifies all facts against catalog | Enabled |
| Rich Messages | WhatsApp cards and interactive buttons | Enabled |
| Full History Recall | Remembers entire conversation | Enabled |
| Smart Intent Detection | Infers intent from context | Enabled |
| Checkout Guidance | Step-by-step purchase flow | Enabled |

## Configuration Settings

### Accessing Configuration

**Via Django Admin**:
1. Log in to Django Admin: `/admin/`
2. Navigate to: `Bot > Agent Configurations`
3. Select your tenant's configuration
4. Scroll to "UX Enhancement Settings"

**Via API** (for programmatic access):
```python
from apps.bot.models import AgentConfiguration

# Get configuration
config = AgentConfiguration.objects.get(tenant=tenant)

# Update settings
config.enable_message_harmonization = True
config.harmonization_wait_seconds = 3
config.save()
```

### Configuration Fields

#### 1. Business Identity Settings

**`use_business_name_as_identity`** (Boolean, default: `True`)
- When enabled, bot introduces itself with your business name
- Example: "I'm the AI assistant for Acme Fashion Store"
- When disabled, uses generic introduction

**`custom_bot_greeting`** (Text, optional)
- Custom greeting message for first interaction
- Example: "Welcome to Acme Fashion! I'm here to help you find the perfect outfit."
- Leave blank to use default greeting

**Configuration Example**:
```python
config.use_business_name_as_identity = True
config.custom_bot_greeting = "Welcome to Acme Fashion! I'm here to help you find the perfect outfit."
config.save()
```

#### 2. Message Harmonization Settings

**`enable_message_harmonization`** (Boolean, default: `True`)
- Combines rapid-fire messages into single response
- Prevents fragmented conversations

**`harmonization_wait_seconds`** (Integer, default: `3`)
- How long to wait for additional messages
- Range: 1-10 seconds
- Recommended: 3 seconds

**Configuration Example**:
```python
config.enable_message_harmonization = True
config.harmonization_wait_seconds = 3
config.save()
```

**When to Adjust**:
- Increase to 5 seconds if customers frequently send many messages
- Decrease to 2 seconds for faster-paced conversations
- Disable if you prefer immediate responses to each message

#### 3. Product Discovery Settings

**`enable_immediate_product_display`** (Boolean, default: `True`)
- Shows products immediately without category narrowing
- Improves discovery experience

**`max_products_to_show`** (Integer, default: `5`)
- Maximum products to display in initial response
- Range: 3-10 products
- Recommended: 5 products

**Configuration Example**:
```python
config.enable_immediate_product_display = True
config.max_products_to_show = 5
config.save()
```

**When to Adjust**:
- Increase to 8-10 if you have diverse catalog
- Decrease to 3 if you have few products
- Disable if you prefer category-first approach

#### 4. Validation Settings

**`enable_grounded_validation`** (Boolean, default: `True`)
- Verifies all bot responses against actual data
- Prevents hallucination and incorrect information

**`enable_reference_resolution`** (Boolean, default: `True`)
- Allows customers to say "1", "first", etc.
- Resolves references to items from recent lists

**Configuration Example**:
```python
config.enable_grounded_validation = True
config.enable_reference_resolution = True
config.save()
```

**When to Disable**:
- Grounded validation: Never recommended (security risk)
- Reference resolution: If causing confusion (rare)

#### 5. Language Settings

**`primary_language`** (String, default: `'en'`)
- Default language for bot responses
- Options: `'en'` (English), `'sw'` (Swahili)
- Bot adapts to customer's language automatically

**Configuration Example**:
```python
from apps.tenants.models import TenantSettings

settings = tenant.settings
settings.primary_language = 'sw'  # Swahili
settings.save()
```

## Django Admin Interface

### Agent Configuration Admin

**Location**: `/admin/bot/agentconfiguration/`

**Sections**:

1. **Basic Information**
   - Tenant
   - Created/Updated timestamps

2. **Identity & Branding**
   - Use business name as identity
   - Custom bot greeting
   - Agent capabilities (agent_can_do)
   - Agent limitations (agent_cannot_do)

3. **UX Enhancement Features**
   - Message harmonization settings
   - Product discovery settings
   - Validation settings
   - Reference resolution settings

4. **Advanced Settings**
   - LLM provider configuration
   - RAG settings
   - Intent detection settings

### Inline Editing

You can edit multiple configurations at once:
1. Go to Agent Configurations list
2. Select configurations to edit
3. Choose "Edit selected configurations" action
4. Update fields in bulk

### Filtering & Search

**Available Filters**:
- By tenant
- By feature enabled/disabled
- By creation date

**Search Fields**:
- Tenant name
- Tenant ID
- Custom greeting text

## Feature Flags

### Enabling/Disabling Features

**Via Django Admin**:
1. Navigate to Agent Configuration
2. Scroll to feature section
3. Check/uncheck feature checkbox
4. Click "Save"

**Via Management Command**:
```bash
# Enable message harmonization for all tenants
python manage.py configure_ux_features --enable-harmonization

# Disable immediate product display for specific tenant
python manage.py configure_ux_features --tenant-id=<uuid> --disable-immediate-display

# Reset to defaults
python manage.py configure_ux_features --reset-defaults
```

**Via API**:
```python
from apps.bot.models import AgentConfiguration

# Bulk enable for all tenants
AgentConfiguration.objects.all().update(
    enable_message_harmonization=True,
    enable_immediate_product_display=True,
    enable_grounded_validation=True
)

# Enable for specific tenant
config = AgentConfiguration.objects.get(tenant=tenant)
config.enable_message_harmonization = True
config.save()
```

### Feature Dependencies

Some features depend on others:

| Feature | Requires |
|---------|----------|
| Reference Resolution | Message Harmonization (recommended) |
| Checkout Guidance | Rich Messages, Product Discovery |
| Smart Intent Detection | Full History Recall |

**Note**: Disabling a parent feature may reduce effectiveness of dependent features.

## Monitoring & Analytics

### Key Metrics Dashboard

**Location**: `/admin/analytics/dashboard/`

**Metrics to Monitor**:

1. **Message Harmonization**
   - Average messages per burst
   - Average wait time
   - Harmonization success rate
   - Target: >95% success rate

2. **Reference Resolution**
   - Resolution success rate
   - Context expiry rate
   - Ambiguous reference rate
   - Target: >90% success rate

3. **Product Discovery**
   - Immediate display rate
   - Empty result rate
   - Fuzzy match success rate
   - Target: <10% empty results

4. **Language Consistency**
   - Language detection accuracy
   - Mid-conversation switches
   - Consistency score
   - Target: >95% consistency

5. **Grounding Validation**
   - Validation failure rate
   - Hallucination prevention count
   - Claim verification rate
   - Target: <5% failures

6. **Rich Messages**
   - Rich message usage rate
   - Fallback rate (API failures)
   - Button interaction rate
   - Target: >80% usage, <10% fallback

7. **Conversation Completion**
   - Inquiry-to-sale conversion rate
   - Average conversation length
   - Handoff rate
   - Target: >30% conversion

### Viewing Logs

**Harmonization Logs**:
```python
from apps.bot.models import MessageHarmonizationLog

# Recent harmonizations
logs = MessageHarmonizationLog.objects.filter(
    conversation__tenant=tenant
).order_by('-created_at')[:100]

for log in logs:
    print(f"Combined {len(log.message_ids)} messages")
    print(f"Wait time: {log.wait_time_ms}ms")
```

**Reference Context Logs**:
```python
from apps.bot.models import ReferenceContext

# Active contexts
contexts = ReferenceContext.objects.filter(
    conversation__tenant=tenant,
    expires_at__gt=timezone.now()
)

for ctx in contexts:
    print(f"Context: {ctx.list_type}")
    print(f"Items: {len(ctx.items)}")
    print(f"Expires: {ctx.expires_at}")
```

### CloudWatch/Sentry Integration

**Structured Logging**:
All services log with tenant context:
```json
{
  "level": "info",
  "message": "Message harmonization completed",
  "tenant_id": "uuid",
  "conversation_id": "uuid",
  "message_count": 3,
  "wait_time_ms": 2500
}
```

**Alerts**:
- Critical: Grounding validation failure rate > 10%
- Warning: Reference resolution failure rate > 15%
- Info: New feature usage milestones

## Troubleshooting

### Common Issues

#### Issue 1: Bot Not Showing Products Immediately

**Symptoms**:
- Bot asks for category before showing products
- Customers complain about too many questions

**Diagnosis**:
```python
config = AgentConfiguration.objects.get(tenant=tenant)
print(config.enable_immediate_product_display)  # Should be True
print(config.max_products_to_show)  # Should be 3-10
```

**Solutions**:
1. Enable immediate product display
2. Verify products exist in catalog
3. Check product visibility settings
4. Review product query filters

#### Issue 2: References Not Resolving

**Symptoms**:
- Customer says "1" but bot doesn't understand
- Bot asks "what do you mean by 1?"

**Diagnosis**:
```python
# Check if reference resolution is enabled
config = AgentConfiguration.objects.get(tenant=tenant)
print(config.enable_reference_resolution)  # Should be True

# Check for active contexts
from apps.bot.models import ReferenceContext
contexts = ReferenceContext.objects.filter(
    conversation=conversation,
    expires_at__gt=timezone.now()
)
print(f"Active contexts: {contexts.count()}")  # Should be > 0
```

**Solutions**:
1. Enable reference resolution
2. Check context expiry time (default 5 minutes)
3. Verify lists are being stored correctly
4. Review conversation flow

#### Issue 3: Language Switching Unexpectedly

**Symptoms**:
- Bot switches between English and Swahili
- Inconsistent language in responses

**Diagnosis**:
```python
from apps.bot.models import LanguagePreference

pref = LanguagePreference.objects.get(conversation=conversation)
print(pref.primary_language)  # Should match expected
print(pref.language_usage)  # Check detection history
```

**Solutions**:
1. Set primary language in tenant settings
2. Review language detection logs
3. Check for mixed-language customer messages
4. Verify language consistency manager is active

#### Issue 4: Message Harmonization Not Working

**Symptoms**:
- Multiple rapid messages get separate responses
- Fragmented conversation flow

**Diagnosis**:
```python
config = AgentConfiguration.objects.get(tenant=tenant)
print(config.enable_message_harmonization)  # Should be True
print(config.harmonization_wait_seconds)  # Should be 2-5

# Check harmonization logs
from apps.bot.models import MessageHarmonizationLog
recent = MessageHarmonizationLog.objects.filter(
    conversation__tenant=tenant
).order_by('-created_at').first()
print(f"Last harmonization: {recent.created_at if recent else 'None'}")
```

**Solutions**:
1. Enable message harmonization
2. Adjust wait time (try 3-5 seconds)
3. Check for message queue issues
4. Review Celery worker status

#### Issue 5: Rich Messages Not Appearing

**Symptoms**:
- Products shown as plain text instead of cards
- No interactive buttons

**Diagnosis**:
```python
# Check WhatsApp integration
from apps.integrations.services.twilio_service import TwilioService

service = TwilioService(tenant)
print(service.supports_rich_media())  # Should be True

# Check fallback rate
from apps.bot.models import MessageLog
fallbacks = MessageLog.objects.filter(
    tenant=tenant,
    message_type='fallback'
).count()
print(f"Fallback rate: {fallbacks}")
```

**Solutions**:
1. Verify WhatsApp Business API is active
2. Check Twilio credentials
3. Review WhatsApp API limits
4. Test with different phone numbers

### Debug Mode

Enable debug logging for troubleshooting:

```python
# In settings.py or via environment variable
LOGGING = {
    'loggers': {
        'apps.bot.services': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}
```

### Support Escalation

If issues persist:
1. Collect logs from last 24 hours
2. Export configuration settings
3. Document reproduction steps
4. Contact engineering: support@wabotiq.com

## Best Practices

### 1. Configuration Management

**Do**:
- Test configuration changes in staging first
- Document why you changed settings
- Monitor metrics after changes
- Keep settings consistent across similar tenants

**Don't**:
- Disable grounded validation (security risk)
- Set harmonization wait time > 10 seconds
- Show more than 10 products initially
- Change multiple settings at once without testing

### 2. Product Catalog Management

**Do**:
- Keep product data accurate and up-to-date
- Use high-quality product images
- Write clear product descriptions
- Set accurate stock levels
- Update prices regularly

**Don't**:
- Leave products with missing data
- Use placeholder images in production
- Forget to mark out-of-stock items
- Have duplicate product entries

### 3. Monitoring & Maintenance

**Daily**:
- Check conversation completion rate
- Review error logs
- Monitor response times

**Weekly**:
- Analyze conversation patterns
- Review customer feedback
- Check feature usage metrics
- Update product catalog

**Monthly**:
- Review configuration effectiveness
- Analyze conversion rates
- Plan feature optimizations
- Update documentation

### 4. Customer Experience

**Do**:
- Test the bot regularly as a customer
- Review actual customer conversations
- Gather feedback from customers
- Train staff on bot capabilities

**Don't**:
- Assume the bot works perfectly
- Ignore customer complaints
- Forget to update bot knowledge
- Neglect human handoff procedures

### 5. Performance Optimization

**Do**:
- Monitor response times
- Use caching effectively
- Optimize product queries
- Keep conversation history manageable

**Don't**:
- Load entire catalog on every query
- Store unlimited conversation history
- Ignore slow query warnings
- Disable caching without reason

## Advanced Configuration

### Custom Persona Building

Create a custom bot persona:

```python
config = AgentConfiguration.objects.get(tenant=tenant)

config.agent_can_do = """
- Browse our complete product catalog
- Provide detailed product information
- Help with size and fit questions
- Process orders and payments
- Track order status
- Handle returns and exchanges
"""

config.agent_cannot_do = """
- Provide medical advice
- Make custom orders
- Modify existing orders after payment
- Provide refunds (connect with team)
"""

config.custom_bot_greeting = """
Welcome to Acme Fashion! 👋

I'm your personal shopping assistant. I can help you:
• Find the perfect outfit
• Check sizes and availability
• Place orders securely
• Track your delivery

What are you looking for today?
"""

config.save()
```

### Multi-Language Support

Configure language preferences:

```python
from apps.tenants.models import TenantSettings

settings = tenant.settings

# Set primary language
settings.primary_language = 'sw'  # Swahili

# Configure language detection
settings.metadata = {
    'language_config': {
        'auto_detect': True,
        'fallback_language': 'en',
        'supported_languages': ['en', 'sw']
    }
}

settings.save()
```

### Custom Validation Rules

Add custom grounding validation rules:

```python
from apps.bot.services.grounded_response_validator import GroundedResponseValidator

# Extend validator with custom rules
class CustomValidator(GroundedResponseValidator):
    def verify_claim(self, claim, context):
        # Add custom verification logic
        if 'price' in claim.lower():
            # Verify price claims extra carefully
            return self.verify_price_claim(claim, context)
        return super().verify_claim(claim, context)
```

## Migration & Rollback

### Enabling Features Gradually

Roll out features incrementally:

```python
# Phase 1: Enable for test tenant
test_config = AgentConfiguration.objects.get(tenant=test_tenant)
test_config.enable_message_harmonization = True
test_config.save()

# Monitor for 1 week

# Phase 2: Enable for 10% of tenants
configs = AgentConfiguration.objects.all()[:int(configs.count() * 0.1)]
configs.update(enable_message_harmonization=True)

# Monitor for 1 week

# Phase 3: Enable for all tenants
AgentConfiguration.objects.all().update(enable_message_harmonization=True)
```

### Rollback Procedure

If issues occur, rollback quickly:

```bash
# Disable specific feature for all tenants
python manage.py configure_ux_features --disable-harmonization

# Rollback to previous configuration
python manage.py restore_config --backup-id=<backup_id>

# Emergency: Disable all new features
python manage.py configure_ux_features --disable-all-enhancements
```

## Appendix

### Configuration Checklist

Before going live:
- [ ] Business identity configured
- [ ] Custom greeting set (optional)
- [ ] Message harmonization enabled
- [ ] Product display settings optimized
- [ ] Language preference set
- [ ] Grounded validation enabled
- [ ] Rich messages tested
- [ ] Checkout flow verified
- [ ] Monitoring alerts configured
- [ ] Staff trained on features

### Quick Reference

**Enable All Features**:
```python
config.enable_message_harmonization = True
config.enable_immediate_product_display = True
config.enable_grounded_validation = True
config.enable_reference_resolution = True
config.use_business_name_as_identity = True
config.save()
```

**Recommended Settings**:
```python
config.harmonization_wait_seconds = 3
config.max_products_to_show = 5
```

**Check Feature Status**:
```python
config = AgentConfiguration.objects.get(tenant=tenant)
print(f"Harmonization: {config.enable_message_harmonization}")
print(f"Product Display: {config.enable_immediate_product_display}")
print(f"Validation: {config.enable_grounded_validation}")
```

## Support & Resources

- **Documentation**: https://docs.wabotiq.com
- **Support Email**: support@wabotiq.com
- **Slack Channel**: #wabot-support
- **Status Page**: https://status.wabotiq.com
