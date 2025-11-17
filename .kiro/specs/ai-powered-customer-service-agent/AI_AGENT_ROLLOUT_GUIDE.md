# AI Agent Rollout Guide

## Quick Start

### Prerequisites
1. Ensure OpenAI or Together AI credentials are configured for the tenant
2. Verify the AI agent service is deployed and working
3. Confirm the tenant has an active subscription

### Enable AI Agent for a Tenant

```bash
# Check current status
python manage.py toggle_ai_agent <tenant-slug> --status

# Enable AI agent
python manage.py toggle_ai_agent <tenant-slug> --enable

# Disable AI agent (rollback)
python manage.py toggle_ai_agent <tenant-slug> --disable
```

### Example

```bash
# Check status for demo tenant
python manage.py toggle_ai_agent demo-store --status

# Output:
# AI agent for tenant "Demo Store" (demo-store): DISABLED
#   LLM Provider: openai
#   OpenAI configured: Yes
#   Together AI configured: No

# Enable AI agent
python manage.py toggle_ai_agent demo-store --enable

# Output:
# ✓ AI agent ENABLED for tenant "Demo Store" (demo-store)
#   Using LLM provider: openai
```

## Rollout Strategy

### Phase 1: Internal Testing (Week 1)
- Enable for 1 internal test tenant
- Test all conversation flows
- Verify rich messages work correctly
- Monitor costs and performance
- Test handoff scenarios

### Phase 2: Pilot Tenants (Week 2-3)
- Select 3-5 pilot tenants with:
  - Active customer base
  - Diverse product/service catalogs
  - Willingness to provide feedback
- Enable AI agent
- Monitor daily for:
  - Response quality
  - Handoff rates
  - Customer satisfaction
  - Cost per conversation
- Gather feedback from tenant owners

### Phase 3: Gradual Rollout (Week 4-8)
- Week 4: 10% of tenants
- Week 5: 25% of tenants
- Week 6: 50% of tenants
- Week 7: 75% of tenants
- Week 8: 100% of tenants

### Phase 4: Legacy Deprecation (Week 12+)
- Monitor for any tenants still using legacy system
- Reach out to understand why
- Address concerns
- Eventually deprecate legacy system

## Monitoring Checklist

### Daily Checks (During Rollout)
- [ ] Check error rates in logs
- [ ] Review cost tracking dashboard
- [ ] Monitor handoff rates
- [ ] Check response times
- [ ] Review customer feedback

### Weekly Reviews
- [ ] Compare AI agent vs legacy metrics
- [ ] Analyze cost trends
- [ ] Review handoff reasons
- [ ] Identify improvement opportunities
- [ ] Update knowledge bases based on common questions

### Monthly Analysis
- [ ] Calculate ROI (cost vs. value)
- [ ] Measure customer satisfaction improvement
- [ ] Analyze conversation completion rates
- [ ] Review model performance
- [ ] Plan optimizations

## Troubleshooting

### AI Agent Not Working

**Symptom:** Messages still processed by legacy system

**Checks:**
1. Verify feature flag is enabled:
   ```bash
   python manage.py toggle_ai_agent <tenant-slug> --status
   ```

2. Check tenant settings in database:
   ```python
   from apps.tenants.models import Tenant
   tenant = Tenant.objects.get(slug='<tenant-slug>')
   print(tenant.settings.feature_flags)
   # Should show: {'ai_agent_enabled': True}
   ```

3. Check logs for feature flag checks:
   ```bash
   grep "AI agent feature flag" logs/tulia.log
   ```

**Solution:**
- Re-enable feature flag
- Restart Celery workers
- Check for any middleware issues

### High Costs

**Symptom:** Token usage higher than expected

**Checks:**
1. Review token usage per conversation:
   ```python
   from apps.bot.models import AgentInteraction
   interactions = AgentInteraction.objects.filter(
       conversation__tenant__slug='<tenant-slug>'
   ).order_by('-created_at')[:10]
   
   for i in interactions:
       print(f"Tokens: {i.token_usage}, Cost: ${i.estimated_cost}")
   ```

2. Check context size:
   ```python
   # Look for context_size_tokens in metadata
   for i in interactions:
       print(f"Context: {i.metadata.get('context_size_tokens', 0)} tokens")
   ```

**Solutions:**
- Reduce context window size
- Implement more aggressive context truncation
- Use cheaper models for simple queries
- Optimize knowledge base entries

### Low Confidence / High Handoff Rate

**Symptom:** Too many conversations handed off to humans

**Checks:**
1. Review handoff reasons:
   ```python
   from apps.bot.models import AgentInteraction
   handoffs = AgentInteraction.objects.filter(
       conversation__tenant__slug='<tenant-slug>',
       handoff_triggered=True
   )
   
   for h in handoffs:
       print(f"Reason: {h.handoff_reason}, Confidence: {h.confidence_score}")
   ```

2. Check confidence threshold:
   ```python
   from apps.bot.models import AgentConfiguration
   config = AgentConfiguration.objects.get(tenant__slug='<tenant-slug>')
   print(f"Threshold: {config.confidence_threshold}")
   ```

**Solutions:**
- Lower confidence threshold (e.g., from 0.7 to 0.6)
- Add more knowledge base entries
- Improve agent persona instructions
- Train on common customer questions

### Rich Messages Not Sending

**Symptom:** All messages sent as plain text

**Checks:**
1. Check if rich messages are enabled:
   ```python
   from apps.bot.models import AgentConfiguration
   config = AgentConfiguration.objects.get(tenant__slug='<tenant-slug>')
   print(f"Rich messages enabled: {config.enable_rich_messages}")
   ```

2. Check logs for fallback events:
   ```bash
   grep "falling back to text" logs/tulia.log
   ```

**Solutions:**
- Verify Twilio service has rich message support
- Check WhatsApp Business API configuration
- Review rich message validation errors
- Test with simple button messages first

## Rollback Procedure

### Immediate Rollback (Emergency)

If critical issues are discovered:

```bash
# Disable AI agent for affected tenant
python manage.py toggle_ai_agent <tenant-slug> --disable

# Or disable for all tenants
python manage.py shell
>>> from apps.tenants.models import TenantSettings
>>> TenantSettings.objects.all().update(
...     feature_flags={'ai_agent_enabled': False}
... )
```

### Gradual Rollback

If issues are less severe:

1. Stop enabling new tenants
2. Monitor existing AI agent tenants
3. Disable for tenants with issues
4. Fix issues
5. Re-enable gradually

## Success Metrics

### Key Performance Indicators

1. **Response Quality**
   - Customer satisfaction score
   - Conversation completion rate
   - Handoff rate (target: <20%)

2. **Efficiency**
   - Average response time (target: <5s)
   - Token usage per conversation
   - Cost per conversation (target: <$0.05)

3. **Business Impact**
   - Conversations handled by bot (target: >80%)
   - Customer engagement rate
   - Conversion rate improvement

### Comparison: AI Agent vs Legacy

| Metric | Legacy | AI Agent | Target |
|--------|--------|----------|--------|
| Handoff Rate | 30% | 15% | <20% |
| Avg Response Time | 3s | 4s | <5s |
| Customer Satisfaction | 3.5/5 | 4.2/5 | >4.0/5 |
| Cost per Conversation | $0.01 | $0.03 | <$0.05 |
| Conversations Completed | 60% | 85% | >80% |

## Best Practices

### For Platform Operators

1. **Start Small**
   - Begin with 1-2 pilot tenants
   - Monitor closely for first week
   - Gather feedback before expanding

2. **Monitor Costs**
   - Set up cost alerts
   - Track token usage trends
   - Optimize prompts regularly

3. **Maintain Knowledge Bases**
   - Review common questions weekly
   - Add new entries proactively
   - Update outdated information

4. **Tune Configurations**
   - Adjust confidence thresholds based on data
   - Optimize context window sizes
   - Test different models for different use cases

### For Tenants

1. **Prepare Knowledge Base**
   - Add comprehensive FAQs
   - Document business policies
   - Include product/service details

2. **Configure Agent Persona**
   - Define brand voice and tone
   - Set behavioral restrictions
   - Add required disclaimers

3. **Monitor Performance**
   - Review conversation logs
   - Check handoff reasons
   - Gather customer feedback

4. **Iterate and Improve**
   - Add knowledge entries for common questions
   - Refine agent instructions
   - Test different configurations

## Support and Escalation

### Level 1: Self-Service
- Check this guide
- Review logs
- Use management commands

### Level 2: Platform Support
- Contact platform support team
- Provide tenant slug and issue description
- Include relevant log excerpts

### Level 3: Engineering Escalation
- Critical issues affecting multiple tenants
- System-wide performance problems
- Security concerns

## Additional Resources

- [AI Agent Design Document](./design.md)
- [Requirements Document](./requirements.md)
- [Task Implementation Summary](./TASK_14_IMPLEMENTATION_SUMMARY.md)
- [API Documentation](../../docs/api/)
- [Monitoring Setup](../../docs/MONITORING_SETUP.md)
