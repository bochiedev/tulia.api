# 06 — Multi-Model LLM Router & Cost Control

The LLM Router chooses **which model to call** and **when not to call any**.

## 6.1 When LLM Should Be Called

- Intent detection for long / messy / mixed-language messages where
  keywords and rules are insufficient.
- Slot extraction from natural phrases:
  - “Nataka jacket ya kublast baridi, around 5k”
  - “Nikuje saa ngapi kesho jioni?”
- RAG answer generation.

## 6.2 When LLM Must Not Be Called

- Numeric menu replies (“1”, “2”, “3”)
- Direct WhatsApp list/button responses
- Explicit order / booking confirmations (“yes”, “no”, “confirm”)
- Payment provider callbacks

## 6.3 Model Preference Order

1. **Small / cheap model** (GPT-4o-mini, Qwen 2.5 7B, Gemini Flash)
2. **Mid-tier model** (Qwen 14B, Llama 3 8B) – only when needed
3. **Premium model** (GPT-4o, Claude) – only for heavy tasks (optional)

The default for Tulia AI: **Tier 1 only**, unless explicitly overridden.

## 6.4 Central Router API

```python
class LLMRouter:
    def classify_intent(self, text: str, context: dict) -> dict: ...
    def extract_slots(self, text: str, schema: dict, context: dict) -> dict: ...
    def rag_answer(self, question: str, context_docs: list[dict]) -> str: ...
```

The router handles:
- Provider API keys from `TenantSettings`
- Timeouts
- Retries
- Logging token usage per tenant

## 6.5 Cost Tracking

- Every call logs:
  - `tenant_id`
  - `model_name`
  - `input_tokens`
  - `output_tokens`
  - `estimated_cost`
- Aggregate daily and expose to analytics.
