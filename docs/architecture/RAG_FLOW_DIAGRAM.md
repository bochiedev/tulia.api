# RAG Integration Flow Diagram

## Complete Message Processing Flow with RAG

```
┌─────────────────────────────────────────────────────────────────┐
│                     Customer Sends Message                       │
│                    "What is your return policy?"                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AI Agent Service Receives                      │
│                    process_message() called                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Input Sanitization                            │
│              Sanitize customer message text                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Get Agent Configuration                         │
│         agent_config = get_or_create_configuration()             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Spelling Correction                            │
│              preprocess_message() (if enabled)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Build Conversation Context                      │
│         context = context_builder.build_context()                │
│   • Conversation history                                         │
│   • Customer history                                             │
│   • Catalog context                                              │
│   • Knowledge base                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────┴────────┐
                    │  RAG Enabled?   │
                    │ _should_use_rag │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                   Yes               No
                    │                 │
                    ▼                 │
    ┌───────────────────────────┐    │
    │   Retrieve RAG Context    │    │
    │ retrieve_rag_context()    │    │
    └───────────┬───────────────┘    │
                │                     │
                ▼                     │
    ┌───────────────────────────┐    │
    │  Initialize RAG Services  │    │
    │ • RAGRetrieverService     │    │
    │ • ContextSynthesizer      │    │
    │ • AttributionHandler      │    │
    └───────────┬───────────────┘    │
                │                     │
                ▼                     │
    ┌───────────────────────────┐    │
    │   Parallel Retrieval      │    │
    │ RAGRetrieverService.      │    │
    │      retrieve()           │    │
    └───────────┬───────────────┘    │
                │                     │
        ┌───────┴───────┐            │
        │               │            │
        ▼               ▼            │
┌──────────────┐ ┌──────────────┐   │
│  Documents   │ │   Database   │   │
│   Search     │ │    Query     │   │
│ (semantic +  │ │ (products,   │   │
│  keyword)    │ │  services)   │   │
└──────┬───────┘ └──────┬───────┘   │
       │                │            │
       │         ┌──────────────┐    │
       │         │   Internet   │    │
       │         │    Search    │    │
       │         │ (if enabled) │    │
       │         └──────┬───────┘    │
       │                │            │
       └────────┬───────┘            │
                │                     │
                ▼                     │
    ┌───────────────────────────┐    │
    │  Context Synthesis        │    │
    │ ContextSynthesizer.       │    │
    │    synthesize()           │    │
    │ • Merge results           │    │
    │ • Resolve conflicts       │    │
    │ • Prioritize sources      │    │
    └───────────┬───────────────┘    │
                │                     │
                ▼                     │
    ┌───────────────────────────┐    │
    │  Add to Context Metadata  │    │
    │ context.metadata[         │    │
    │   'rag_context'] = {...}  │    │
    └───────────┬───────────────┘    │
                │                     │
                └──────────┬──────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Generate Suggestions                            │
│         suggestions = generate_suggestions()                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Select Model                                  │
│              model = select_model()                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Build System Prompt                             │
│         _build_system_prompt(agent_config, context)              │
│   • Base capabilities (with RAG)                                 │
│   • RAG usage instructions ← NEW                                 │
│   • Scenario guidance                                            │
│   • Feature prompts                                              │
│   • Persona                                                      │
│   • agent_can_do ← NEW                                           │
│   • agent_cannot_do ← NEW                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Build User Prompt                              │
│           _build_user_prompt(context, suggestions)               │
│   • Retrieved Information ← NEW                                  │
│     - Synthesized context                                        │
│     - Document results                                           │
│     - Database results                                           │
│     - Internet results                                           │
│   • Current message                                              │
│   • Conversation history                                         │
│   • Suggestions                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Call LLM Provider                               │
│         response = generate_response()                           │
│   • Provider routing                                             │
│   • Failover handling                                            │
│   • Token tracking                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────┴────────┐
                    │  Attribution    │
                    │   Enabled?      │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                   Yes               No
                    │                 │
                    ▼                 │
    ┌───────────────────────────┐    │
    │  Add Source Attribution   │    │
    │ add_attribution_to_       │    │
    │      response()           │    │
    │ • Add citations           │    │
    │ • Track sources           │    │
    └───────────┬───────────────┘    │
                │                     │
                └──────────┬──────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                Calculate Processing Time                         │
│              processing_time_ms = ...                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Check Handoff Needed                            │
│         should_handoff, reason = should_handoff()                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Update Conversation Context                         │
│         _update_conversation_context()                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Enhance with Rich Message                           │
│         enhance_response_with_rich_message()                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Track Interaction                               │
│              track_interaction()                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Add Feedback Buttons                            │
│         add_feedback_buttons_to_response()                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Return Response                                │
│  "According to our FAQ, we offer a 30-day return policy..."     │
│  "[Source: FAQ.pdf]"                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Send to Customer                                │
└─────────────────────────────────────────────────────────────────┘
```

## RAG Retrieval Detail

```
┌─────────────────────────────────────────────────────────────────┐
│              RAGRetrieverService.retrieve()                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │  Parallel       │
                    │  Execution      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Document    │    │  Database    │    │  Internet    │
│  Retrieval   │    │  Retrieval   │    │  Retrieval   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ • Generate   │    │ • Query      │    │ • Check      │
│   embedding  │    │   products   │    │   cache      │
│ • Search     │    │ • Query      │    │ • Google     │
│   vector     │    │   services   │    │   Search     │
│   store      │    │ • Query      │    │ • Extract    │
│ • Retrieve   │    │   orders     │    │   content    │
│   chunks     │    │ • Format     │    │ • Cache      │
│ • Score      │    │   results    │    │   results    │
│   results    │    │              │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       └────────────────────┼────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  Collect All Results  │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  ContextSynthesizer   │
                │    .synthesize()      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  • Merge results      │
                │  • Remove duplicates  │
                │  • Resolve conflicts  │
                │  • Prioritize:        │
                │    1. Documents       │
                │    2. Database        │
                │    3. Internet        │
                │  • Create summary     │
                │  • Track sources      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  Return Synthesized   │
                │       Context         │
                └───────────────────────┘
```

## Source Prioritization

```
┌─────────────────────────────────────────────────────────────────┐
│                    Information Conflict                          │
│  Document says: "30-day return policy"                           │
│  Database says: "14-day return policy"                           │
│  Internet says: "Industry standard is 30 days"                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Prioritize    │
                    │    Sources     │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  1. Document   │ ← Highest Priority
                    │  (Tenant's     │   (Business-specific)
                    │   official     │
                    │   policy)      │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  2. Database   │ ← Medium Priority
                    │  (Real-time    │   (Current data)
                    │   catalog)     │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  3. Internet   │ ← Lowest Priority
                    │  (General      │   (Enrichment only)
                    │   info)        │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Resolution:   │
                    │  Use Document  │
                    │  "30-day       │
                    │   return       │
                    │   policy"      │
                    └────────────────┘
```

## Attribution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Generated Response                        │
│  "We offer a 30-day return policy on all items."                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Attribution   │
                    │   Enabled?     │
                    └────────┬───────┘
                             │
                            Yes
                             │
                             ▼
                ┌────────────────────────┐
                │  AttributionHandler    │
                │  .add_attribution()    │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Analyze Response      │
                │  • Find claims         │
                │  • Match to sources    │
                │  • Determine style     │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Add Citations         │
                │  • Inline: [Source]    │
                │  • Endnote: [1]        │
                └────────────┬───────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Attributed Response                            │
│  "We offer a 30-day return policy on all items. [Source:        │
│   FAQ.pdf]"                                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Integration Points

1. **RAG Check** - After context building, before suggestions
2. **RAG Retrieval** - Parallel execution from all sources
3. **Context Synthesis** - Merge and prioritize information
4. **Prompt Building** - Include RAG context in user prompt
5. **LLM Generation** - Use retrieved information
6. **Attribution** - Add source citations to response

## Performance Targets

- Document Search: ~100-150ms
- Database Query: ~50-100ms
- Internet Search: ~200-300ms
- **Total (parallel): ~300ms** ✅

## NEW Components Added

✅ `_should_use_rag()` - Check if RAG enabled
✅ `retrieve_rag_context()` - Orchestrate RAG retrieval
✅ `_build_rag_context_section()` - Format for prompt
✅ `add_attribution_to_response()` - Add citations
✅ RAG usage prompt - Instructions for LLM
✅ agent_can_do/cannot_do - Capability guidance
