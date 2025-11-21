# 20 — LLM Minimization Strategy

Goal: keep per-tenant LLM cost under **$10/month** on Starter tier.

Techniques:

- **Rule-first NLU**:
  - Use dictionaries, regex, intent heuristics for 60–80% of messages.
- **Small models only**:
  - Use GPT-4o-mini / Qwen 7B for quick NLU.
- **Short prompts & responses**:
  - Always request concise JSON or very short answers.
- **Summaries, not full history**:
  - Keep a short `conversation_summary` and last 3–5 messages only.
- **Cache FAQ answers**:
  - Popular questions can be cached per tenant with TTL.
- **Hard caps**:
  - Per-tenant daily/monthly LLM budget; throttle or fall back to rules
    when exceeded.
