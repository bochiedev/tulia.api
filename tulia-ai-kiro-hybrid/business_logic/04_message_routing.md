# 04 — Message Routing (Webhook to Response)

This document describes how incoming WhatsApp messages flow through the
backend:

1. **Webhook reception**
2. **Normalization & deduplication**
3. **Intent detection**
4. **Business logic routing**
5. **Response formatting**
6. **Sending via Twilio**

## 4.1 Twilio Webhook

Endpoint: `POST /v1/webhooks/twilio/inbound/{tenant_slug_or_id}`

Steps:
- Verify Twilio signature (if configured).
- Resolve tenant from path/phone mapping.
- Create `Message` DB record.
- Enqueue Celery task `process_inbound_message(message_id)`.

## 4.2 Processing Task

```python
def process_inbound_message(message_id: uuid.UUID):
    message = Message.objects.get(id=message_id)
    tenant = message.tenant
    customer = ensure_customer(tenant, message)
    context = load_conversation_context(tenant, customer, message)

    intent_result = detect_intent(message.text, context)
    action = route_business_logic(tenant, customer, context, intent_result)

    outbound_messages = format_for_whatsapp(action, context, tenant)
    send_via_twilio(tenant, customer, outbound_messages)

    save_conversation_context(context, action)
    log_agent_interaction(...)
```

## 4.3 Deduplication

Messages may arrive twice. Use:
- Twilio `MessageSid`
- Combination of `(from, to, body, timestamp)`

to detect duplicates and avoid double-processing.

## 4.4 Rate Limiting / Quiet Hours

- Respect `TenantSettings.quiet_hours_start/end`.
- If inside quiet hours:
  - Either:
    - Respond with a quiet-hours message
    - Queue messages for later (future extension)

## 4.5 Human Handoff

When router returns `HANDOFF`:
- Tag conversation as `needs_human = True`.
- Stop AI responses for this conversation until cleared.
- Optionally, send a final “human will reply” message.
