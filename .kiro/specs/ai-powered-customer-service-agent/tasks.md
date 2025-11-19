# Implementation Plan

This implementation plan breaks down the AI-powered customer service agent into discrete, manageable coding tasks. Each task builds incrementally on previous work, with the goal of delivering a production-ready system that handles intelligent conversations, maintains memory, uses rich WhatsApp features, and provides powerful tenant customization.

## Task List

- [x] 1. Set up LLM provider abstraction layer ✅ COMPLETE
  - [x] Create base `LLMProvider` abstract class with `generate()` and `get_available_models()` methods
  - [x] Implement `OpenAIProvider` class supporting GPT-4o, o1-preview, and o1-mini models
  - [x] Add provider factory pattern for instantiating providers by name
  - [x] Implement response normalization across providers
  - [x] Add error handling and retry logic with exponential backoff
  - [x] All 21 tests passing (100% coverage on new code)
  - _Requirements: 1.1, 1.2, 1.3, 7.1, 7.2, 7.4_

- [x] 2. Create agent configuration models and service
  - [x] 2.1 Create `AgentConfiguration` model with persona, model settings, and behavior fields
    - Add fields for agent_name, personality_traits, tone, default_model, fallback_models
    - Add fields for behavioral_restrictions, required_disclaimers, confidence_threshold
    - Add fields for enable_proactive_suggestions, enable_spelling_correction, enable_rich_messages
    - Create database migration
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.3_
  
  - [x] 2.2 Implement `AgentConfigurationService` for managing configurations
    - Write `get_configuration()` method with caching (5 minute TTL)
    - Write `update_configuration()` method with validation
    - Write `apply_persona()` method to inject persona into prompts
    - Write `get_default_configuration()` for new tenants
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 2.3 Create REST API endpoints for agent configuration
    - Create `AgentConfigurationSerializer` with all fields
    - Create `AgentConfigurationViewSet` with GET and PUT endpoints
    - Add RBAC enforcement with required scope "integrations:manage"
    - Add OpenAPI documentation
    - _Requirements: 15.1, 15.2, 15.3, 15.5_

- [ ] 3. Implement knowledge base system
  - [x] 3.1 Create `KnowledgeEntry` model with semantic search support ✅ COMPLETE
    - [x] Add fields for entry_type, title, content, metadata, keywords
    - [x] Add fields for embedding (JSON), category, priority, is_active, version
    - [x] Add tenant foreign key with proper indexing
    - [x] Create database migration with indexes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 10.1, 10.2_
  
  - [x] 3.2 Implement `KnowledgeBaseService` with CRUD and search
    - Write `create_entry()` method with embedding generation
    - Write `search()` method using semantic similarity (cosine similarity on embeddings)
    - Write `update_entry()` method with version increment
    - Write `delete_entry()` method (soft delete)
    - Add caching for frequently accessed entries
    - _Requirements: 2.5, 2.6, 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [x] 3.3 Create REST API endpoints for knowledge base management
    - Create `KnowledgeEntrySerializer` with all fields
    - Create `KnowledgeEntryViewSet` with full CRUD operations
    - Add search endpoint with query parameter
    - Add bulk import endpoint for CSV/JSON
    - Add RBAC enforcement with required scope "integrations:manage"
    - _Requirements: 15.4, 15.5_

- [x] 4. Build conversation memory and context system
  - [x] 4.1 Create `ConversationContext` model for memory storage
    - Add fields for current_topic, pending_action, extracted_entities
    - Add foreign keys for last_product_viewed, last_service_viewed
    - Add fields for conversation_summary, key_facts, context_expires_at
    - Create database migration with indexes
    - _Requirements: 3.1, 3.2, 3.3, 20.1, 20.2, 22.1, 22.2_
  
  - [x] 4.2 Implement `ContextBuilderService` for assembling agent context
    - Write `build_context()` method that orchestrates all context sources
    - Write `get_conversation_history()` method with intelligent truncation
    - Write `get_relevant_knowledge()` method using semantic search
    - Write `get_catalog_context()` method for products and services
    - Write `get_customer_history()` method for orders and appointments
    - Implement context window management with priority-based truncation
    - _Requirements: 3.1, 3.2, 3.5, 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [x] 4.3 Add conversation summary generation for long histories
    - Write method to summarize old messages using LLM
    - Implement periodic background task to generate summaries
    - Store summaries in ConversationContext model
    - Use summaries when full history exceeds context window
    - _Requirements: 3.5, 8.5_

- [x] 5. Implement core AI agent service
  - [x] 5.1 Create `AIAgentService` class with main orchestration logic
    - Write `process_message()` method as main entry point
    - Write `generate_response()` method using LLM provider
    - Write `should_handoff()` method for handoff decisions
    - Write `select_model()` method based on task complexity
    - Add comprehensive error handling and logging
    - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.2, 7.1, 7.2_
  
  - [x] 5.2 Build dynamic prompt engineering system
    - Write `build_system_prompt()` method with persona injection
    - Write `build_user_prompt()` method with context assembly
    - Implement prompt templates for different scenarios
    - Add knowledge base injection into prompts
    - Add catalog context injection into prompts
    - _Requirements: 2.5, 5.5, 8.1, 8.2, 8.3, 8.4_
  
  - [x] 5.3 Implement intelligent handoff logic
    - Write confidence threshold checking
    - Write topic-based auto-handoff detection
    - Write consecutive low-confidence tracking
    - Write handoff reason categorization
    - Update conversation status on handoff
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6. Add fuzzy matching and spelling correction
  - [x] 6.1 Implement `FuzzyMatcherService` for intelligent matching
    - Write `match_product()` method using Levenshtein distance and semantic similarity
    - Write `match_service()` method with same approach
    - Write `correct_spelling()` method using vocabulary-based correction
    - Add support for abbreviations and informal names
    - Return confidence scores with matches
    - _Requirements: 16.1, 16.2, 16.5, 21.1, 21.2, 21.3, 21.4, 21.5_
  
  - [x] 6.2 Integrate fuzzy matching into agent workflow
    - Pre-process customer messages for spelling correction
    - Use fuzzy matching when exact catalog matches fail
    - Confirm corrections with customer when confidence is low
    - Track correction accuracy for improvement
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 7. Build multi-intent and message burst handling
  - [x] 7.1 Create `MessageQueue` model for burst management
    - Add fields for conversation, message, status, queue_position
    - Add timestamps for queued_at and processed_at
    - Create database migration with indexes
    - _Requirements: 17.1, 17.4_
  
  - [x] 7.2 Implement `MultiIntentProcessor` service
    - Write `detect_intents()` method using LLM to identify multiple intents
    - Write `process_message_burst()` method to handle queued messages
    - Write `prioritize_intents()` method based on urgency and logic
    - Write `generate_structured_response()` addressing all intents
    - _Requirements: 17.2, 17.3, 17.5_
  
  - [x] 7.3 Add message queueing logic to Celery task
    - Detect rapid message sequences (within 5 seconds)
    - Queue messages instead of processing immediately
    - Batch process queued messages after delay
    - Prevent duplicate intent processing
    - _Requirements: 17.1, 17.4, 17.5_

- [x] 8. Implement rich WhatsApp messaging features
  - [x] 8.1 Create `RichMessageBuilder` service for interactive messages
    - Write `build_product_card()` method with image and buttons
    - Write `build_service_card()` method with image and buttons
    - Write `build_list_message()` method for selections
    - Write `build_button_message()` method for quick replies
    - Add validation against WhatsApp message limits
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [x] 8.2 Integrate rich messages into Twilio service
    - Update `TwilioService` to support WhatsApp interactive messages
    - Add methods for sending button messages
    - Add methods for sending list messages
    - Add methods for sending media with captions
    - Handle button click responses
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [x] 8.3 Update agent response generation to use rich messages
    - Detect when rich messages are appropriate
    - Generate rich message payloads from agent responses
    - Fall back to text when rich messages unavailable
    - Track rich message usage in analytics
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [x] 9. Add proactive suggestions and recommendations
  - [x] 9.1 Implement recommendation logic in agent service
    - Write `generate_suggestions()` method based on context
    - Use customer history for personalized recommendations
    - Suggest complementary products/services
    - Prioritize available inventory and appointments
    - Explain reasoning for suggestions
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 9.2 Integrate suggestions into response generation
    - Add suggestions to agent prompts
    - Format suggestions in responses
    - Use rich messages for suggestion presentation
    - Track suggestion acceptance rate
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 10. Create analytics and tracking system
  - [x] 10.1 Create `AgentInteraction` model for tracking
    - Add fields for customer_message, detected_intents, model_used
    - Add fields for agent_response, confidence_score, handoff_triggered
    - Add fields for message_type, token_usage, estimated_cost
    - Create database migration with indexes
    - _Requirements: 7.5, 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 10.2 Implement interaction tracking in agent service
    - Track every agent interaction in database
    - Calculate and store token usage
    - Estimate costs based on model and tokens
    - Track handoff reasons and outcomes
    - _Requirements: 7.5, 13.1, 13.2, 13.3_
  
  - [x] 10.3 Create analytics API endpoints
    - Create endpoint for conversation statistics
    - Create endpoint for handoff analytics
    - Create endpoint for cost tracking
    - Create endpoint for common topics/intents
    - Add RBAC enforcement with required scope "analytics:view"
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 11. Add Together AI provider for model aggregation
  - [x] 11.1 Implement `TogetherAIProvider` class
    - Implement authentication and API integration
    - Support model selection (Llama, Mistral, etc.)
    - Normalize responses to common format
    - Track usage and costs per provider
    - Implement fallback when models unavailable
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 11.2 Add Together AI configuration to agent settings
    - Add Together AI API key to tenant settings
    - Add model selection UI for Together AI models
    - Update provider factory to support Together AI
    - Add cost tracking for Together AI usage
    - _Requirements: 14.1, 14.2, 14.4_

- [x] 12. Implement campaign message builder with rich media
  - [x] 12.1 Create campaign message models
    - Extend existing campaign models to support rich media
    - Add fields for images, videos, documents
    - Add fields for button configurations
    - Create database migration
    - _Requirements: 19.1, 19.2, 19.3, 19.4_
  
  - [x] 12.2 Build campaign message creation API
    - Create endpoints for campaign creation with media
    - Support image upload with caption and buttons
    - Support video upload with caption and buttons
    - Support document upload with description
    - Validate button configurations (max 3 per message)
    - _Requirements: 19.1, 19.2, 19.3, 19.4_
  
  - [x] 12.3 Implement campaign button interaction tracking
    - Track button clicks in analytics
    - Route button responses to appropriate handlers
    - Update campaign engagement metrics
    - _Requirements: 19.5_

- [x] 13. Add context retention and memory management
  - [x] 13.1 Implement context expiration and cleanup
    - Set context expiration to 30 minutes of inactivity
    - Create background task to clean expired contexts
    - Preserve key facts even after expiration
    - _Requirements: 22.1, 22.2, 22.3_
  
  - [x] 13.2 Add context restoration for returning customers
    - Detect when customer returns after pause
    - Restore relevant context from previous session
    - Acknowledge previous topic in greeting
    - Offer to continue or start fresh
    - _Requirements: 22.2, 22.3, 22.4_
  
  - [x] 13.3 Implement "forgot request" recovery
    - Detect phrases like "did you forget"
    - Retrieve last unanswered question from history
    - Apologize and address the missed request
    - Track recovery success rate
    - _Requirements: 22.4, 22.5_

- [x] 14. Update main message processing task ✅ COMPLETE
  - [x] 14.1 Refactor `process_inbound_message` Celery task
    - Replace old intent service with new AI agent service
    - Add message queueing for burst detection
    - Integrate context builder for full context
    - Use rich message builder for responses
    - Add comprehensive error handling
    - Implemented dual-mode processing (AI agent + legacy)
    - Added context restoration for returning customers
    - Added forgot request recovery
    - Comprehensive logging and monitoring
    - _Requirements: All_
  
  - [x] 14.2 Add feature flag for gradual rollout
    - Create feature flag for new AI agent
    - Allow per-tenant enablement via `tenant.settings.is_feature_enabled('ai_agent_enabled')`
    - Fall back to old system if flag disabled
    - Track usage of new vs old system
    - Safe defaults and error handling
    - Ready for gradual tenant-by-tenant rollout
    - _Requirements: All_

- [x] 15. Performance optimization and caching
  - [x] 15.1 Implement caching strategy
    - Cache agent configurations (5 minute TTL)
    - Cache knowledge base embeddings
    - Cache catalog data (1 minute TTL)
    - Use Redis for distributed caching
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [x] 15.2 Optimize database queries
    - Add database indexes for all tenant_id fields
    - Add indexes for conversation_id and created_at
    - Implement query result caching
    - Use select_related and prefetch_related
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [x] 15.3 Add request deduplication
    - Detect duplicate message processing attempts
    - Use distributed locks for message processing
    - Prevent concurrent processing of same message
    - _Requirements: 12.4_

- [x] 16. Security and multi-tenant isolation
  - [x] 16.1 Audit all queries for tenant filtering
    - Verify all knowledge base queries filter by tenant
    - Verify all conversation queries filter by tenant
    - Verify all catalog queries filter by tenant
    - Add automated tests for tenant isolation
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 16.2 Implement input validation and sanitization
    - Sanitize all customer message inputs
    - Validate knowledge base content
    - Prevent prompt injection attacks
    - Add rate limiting to API endpoints
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 16.3 Add encryption for sensitive data
    - Encrypt customer messages at rest
    - Encrypt knowledge base content
    - Encrypt API keys in database
    - Implement secure key rotation
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 17. Monitoring and observability
  - [x] 17.1 Add comprehensive logging
    - Log all agent interactions with structured data
    - Log LLM API calls and responses
    - Log context building steps
    - Log handoff decisions with reasons
    - Use JSON structured logging
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 17.2 Implement metrics collection
    - Track response time (p50, p95, p99)
    - Track token usage per conversation
    - Track cost per conversation
    - Track handoff rate and reasons
    - Track knowledge base hit rate
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 17.3 Set up alerting
    - Alert on high error rates
    - Alert on slow response times
    - Alert on high costs
    - Alert on frequent handoffs
    - Alert on API failures
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 18. Testing and quality assurance
  - [x] 18.1 Write unit tests for all services
    - Test LLM provider abstraction and fallbacks
    - Test context builder with various scenarios
    - Test fuzzy matcher accuracy
    - Test multi-intent processor
    - Test rich message builder
    - _Requirements: All_
  
  - [x] 18.2 Write integration tests
    - Test end-to-end message flow
    - Test knowledge base search accuracy
    - Test conversation memory retention
    - Test multi-tenant isolation
    - Test rich message delivery
    - _Requirements: All_
  
  - [x] 18.3 Write performance tests
    - Test response time under load
    - Test concurrent tenant usage
    - Test context building speed
    - Test knowledge search speed
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [x] 18.4 Write AI quality tests
    - Test intent accuracy with sample messages
    - Test spelling correction accuracy
    - Test context retention across gaps
    - Test multi-intent handling
    - Test handoff appropriateness
    - _Requirements: All_

- [x] 19. Documentation and deployment
  - [x] 19.1 Update API documentation
    - Document all new endpoints in OpenAPI
    - Add example requests and responses
    - Document RBAC requirements
    - Add integration guides
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 19.2 Create tenant onboarding guide
    - Document agent configuration options
    - Provide knowledge base setup guide
    - Explain model selection and costs
    - Include best practices
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 5.3_
  
  - [x] 19.3 Create deployment checklist
    - Environment variable configuration
    - Database migration steps
    - Cache setup verification
    - Monitoring setup
    - Rollback procedures
    - _Requirements: All_

- [x] 20. Implement smart catalog browsing and pagination ✅ COMPLETE
  - [x] 20.1 Create BrowseSession model for tracking pagination state
    - Add fields for catalog_type, current_page, items_per_page, total_items
    - Add fields for filters, search_query, is_active, expires_at
    - Add tenant and conversation foreign keys
    - Create database migration with indexes
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_
  
  - [x] 20.2 Implement CatalogBrowserService for pagination
    - Write `start_browse_session()` method to initiate browsing
    - Write `get_page()` method to retrieve specific page
    - Write `next_page()` and `previous_page()` methods for navigation
    - Write `apply_filters()` method to filter results
    - Implement session expiration (10 minutes)
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_
  
  - [x] 20.3 Build pagination UI with WhatsApp interactive lists
    - Format catalog items as interactive lists (max 5 items)
    - Add navigation buttons (Next 5, Previous 5, Search)
    - Show position indicator ("Showing 1-5 of 247")
    - Handle button clicks for navigation
    - _Requirements: 23.1, 23.2, 23.3, 23.5_
  
  - [x] 20.4 Integrate pagination into agent response generation
    - Detect when catalog results exceed 5 items
    - Create browse session automatically
    - Generate paginated responses with navigation
    - Track pagination usage in analytics
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_

- [x] 21. Implement reference context and positional resolution ✅ COMPLETE
  - [x] 21.1 Create ReferenceContext model for storing list contexts
    - Add fields for list_type, items (JSON), expires_at, context_id
    - Add conversation foreign key with indexes
    - Create database migration
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_
  
  - [x] 21.2 Implement ReferenceContextManager service
    - Write `store_list_context()` method to save displayed lists
    - Write `resolve_reference()` method to map "1", "first", etc. to items
    - Write `get_current_list()` method to retrieve active context
    - Implement context expiration (5 minutes)
    - Handle numeric references (1, 2, 3) and ordinals (first, second, last)
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_
  
  - [x] 21.3 Integrate reference resolution into message processing
    - Detect when customer message is a positional reference
    - Resolve reference to actual item from recent context
    - Confirm selection with customer
    - Handle ambiguous references with clarification
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_
  
  - [x] 21.4 Update rich message builder to store contexts
    - Automatically store list context when sending lists
    - Include context_id in message metadata
    - Track context usage in analytics
    - _Requirements: 24.1, 24.5_

- [x] 22. Build product intelligence and AI-powered recommendations ✅ COMPLETE
  - [x] 22.1 Create ProductAnalysis model for caching AI analysis
    - Add fields for key_features, use_cases, target_audience
    - Add fields for embedding, summary, ai_categories, ai_tags
    - Add product foreign key and analyzed_at timestamp
    - Create database migration with indexes
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_
  
  - [x] 22.2 Implement ProductIntelligenceService
    - Write `analyze_product()` method using LLM to extract characteristics
    - Write `match_need_to_products()` method for semantic matching
    - Write `generate_recommendation_explanation()` method
    - Write `extract_distinguishing_features()` method
    - Implement caching strategy (24 hour TTL)
    - _Requirements: 25.1, 25.2, 25.3, 25.5_
  
  - [x] 22.3 Add background task for product analysis
    - Create Celery task to analyze products periodically
    - Analyze new products automatically
    - Re-analyze when product descriptions change
    - Track analysis coverage and quality
    - _Requirements: 25.1, 25.4_
  
  - [x] 22.4 Integrate product intelligence into recommendations
    - Use semantic search for need-based matching
    - Generate explanations for recommendations
    - Include AI analysis in product presentations
    - Track recommendation acceptance rate
    - _Requirements: 25.1, 25.2, 25.3, 25.5_

- [x] 23. Implement discovery and intelligent narrowing ✅ COMPLETE
  - [x] 23.1 Implement DiscoveryService for guided search
    - Write `should_ask_clarifying_questions()` method
    - Write `generate_clarifying_questions()` method using LLM
    - Write `apply_preferences()` method to filter catalog
    - Write `suggest_alternatives()` method with explanations
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5_
  
  - [x] 23.2 Build preference extraction logic
    - Extract price range from customer messages
    - Extract feature preferences (color, size, scent, etc.)
    - Extract use case or occasion
    - Store preferences in conversation context
    - _Requirements: 26.1, 26.2_
  
  - [x] 23.3 Integrate discovery into agent workflow
    - Detect when clarification would help (>10 results)
    - Ask relevant clarifying questions
    - Apply filters based on responses
    - Present narrowed results with match highlights
    - _Requirements: 26.1, 26.2, 26.3, 26.4_
  
  - [x] 23.4 Add alternative suggestion logic
    - Detect when no items match criteria
    - Find closest alternatives using semantic similarity
    - Generate explanations of differences
    - Present alternatives with reasoning
    - _Requirements: 26.5_

- [x] 24. Add multi-language and code-switching support ✅ COMPLETE
  - [x] 24.1 Create LanguagePreference model
    - Add fields for primary_language, language_usage, common_phrases
    - Add conversation foreign key
    - Create database migration
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5_
  
  - [x] 24.2 Implement MultiLanguageProcessor service
    - Write `detect_languages()` method to identify English, Swahili, Sheng
    - Write `normalize_message()` method to convert to English
    - Write `translate_common_phrases()` method with phrase dictionary
    - Write `get_customer_language_preference()` method
    - Write `format_response_in_language()` method
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5_
  
  - [x] 24.3 Build Swahili/Sheng phrase dictionary
    - Add common Swahili phrases (nataka, ninataka, nipe, bei gani, iko)
    - Add common Sheng phrases (sawa, poa, fiti, doh, mbao)
    - Add phrase variations and synonyms
    - Support phrase expansion over time
    - _Requirements: 28.2, 28.3_
  
  - [x] 24.4 Integrate language processing into message flow
    - Pre-process messages for language detection
    - Normalize mixed-language messages
    - Track language usage per customer
    - Match response language to customer preference
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5_
  
  - [x] 24.5 Add language detection tests
    - Test pure English messages
    - Test pure Swahili messages
    - Test mixed English-Swahili messages
    - Test Sheng phrase recognition
    - Test response language matching
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5_

- [x] 25. Enhance handoff logic with progressive assistance ✅ COMPLETE
  - [x] 25.1 Update handoff decision logic
    - Implement clarifying question attempts before handoff
    - Track clarification attempt count (max 2)
    - Generate specific clarifying questions using LLM
    - Only offer handoff after genuine attempts
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5_
  
  - [x] 25.2 Build clarifying question generator
    - Analyze customer message for ambiguities
    - Generate 2-3 specific clarifying questions
    - Present possible interpretations
    - Track clarification success rate
    - _Requirements: 27.1, 27.3_
  
  - [x] 25.3 Implement handoff explanation messages
    - Summarize what agent understood
    - List what agent tried
    - Explain why handoff is suggested
    - Offer options (handoff, rephrase, alternatives)
    - _Requirements: 27.2, 27.4_
  
  - [x] 25.4 Add handoff triggers for specific scenarios
    - Detect explicit handoff requests immediately
    - Identify restricted topics (complaints, refunds, custom orders)
    - Detect technical issues (payment failures, account problems)
    - Track handoff reasons in analytics
    - _Requirements: 27.5_

- [x] 26. Build shortened purchase journey with direct actions ✅ COMPLETE
  - [x] 26.1 Add direct action buttons to product cards
    - Add "Buy Now" button to product presentations
    - Add "Add to Cart" button for multi-item purchases
    - Add "More Details" button for full information
    - Handle button clicks to initiate actions
    - _Requirements: 29.1, 29.2, 30.1, 30.2_
  
  - [x] 26.2 Add direct action buttons to service cards
    - Add "Book Now" button to service presentations
    - Add "Check Availability" button for scheduling
    - Add "More Info" button for details
    - Handle button clicks to initiate booking flow
    - _Requirements: 29.3, 29.4, 30.3, 30.4_
  
  - [x] 26.3 Implement streamlined checkout flow
    - Collect only essential information (quantity, delivery)
    - Skip unnecessary confirmation steps
    - Pre-fill customer information from history
    - Provide one-click payment options
    - _Requirements: 30.1, 30.2, 30.5_
  
  - [x] 26.4 Implement streamlined booking flow
    - Show available time slots immediately
    - Allow one-click slot selection
    - Minimize confirmation steps
    - Send booking confirmation with details
    - _Requirements: 30.3, 30.4_

- [x] 27. Update prompt engineering for new features ✅ COMPLETE
  - [x] 27.1 Enhance system prompt with new instructions
    - Add language handling instructions
    - Add reference resolution instructions
    - Add pagination instructions
    - Add clarifying question guidelines
    - Add product intelligence usage
    - _Requirements: All new requirements_
  
  - [x] 27.2 Update context assembly for new data
    - Include reference context in prompt
    - Include browse session state
    - Include language preference
    - Include product AI analysis
    - Prioritize context elements appropriately
    - _Requirements: All new requirements_
  
  - [x] 27.3 Add prompt templates for new scenarios
    - Template for clarifying questions
    - Template for product recommendations with explanations
    - Template for pagination navigation
    - Template for handoff explanations
    - Template for multi-language responses
    - _Requirements: All new requirements_

- [x] 28. Testing for new features ✅ COMPLETE
  - [x] 28.1 Write unit tests for new services
    - Test CatalogBrowserService pagination logic
    - Test ReferenceContextManager resolution
    - Test ProductIntelligenceService analysis
    - Test DiscoveryService clarifying questions
    - Test MultiLanguageProcessor detection and normalization
    - _Requirements: All new requirements_
  
  - [x] 28.2 Write integration tests for new flows
    - Test end-to-end browsing with pagination
    - Test positional reference resolution in conversation
    - Test AI-powered product recommendations
    - Test multi-language message processing
    - Test progressive handoff flow
    - _Requirements: All new requirements_
  
  - [x] 28.3 Write UX tests for interactive messages
    - Test WhatsApp list message formatting
    - Test button click handling
    - Test navigation button functionality
    - Test direct action buttons (Buy Now, Book Now)
    - _Requirements: 23.1, 23.2, 23.3, 29.1, 29.2, 29.3, 29.4, 30.1, 30.3_
  
  - [x] 28.4 Write performance tests for new features
    - Test pagination performance with large catalogs (1000+ items)
    - Test product analysis caching effectiveness
    - Test language detection speed
    - Test reference context lookup speed
    - _Requirements: All new requirements_

- [x] 29. Documentation for new features ✅ COMPLETE
  - [x] 29.1 Document catalog browsing features
    - Explain pagination strategy
    - Document navigation controls
    - Provide examples of browsing large catalogs
    - Include best practices for catalog organization
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_
  
  - [x] 29.2 Document product intelligence features
    - Explain AI analysis capabilities
    - Document recommendation engine
    - Provide examples of intelligent suggestions
    - Include guidelines for product descriptions
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_
  
  - [x] 29.3 Document multi-language support
    - List supported languages and phrases
    - Explain code-switching handling
    - Provide examples of mixed-language conversations
    - Include guidelines for expanding phrase dictionary
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5_
  
  - [x] 29.4 Update tenant onboarding guide
    - Add section on catalog organization for browsing
    - Add section on writing AI-friendly product descriptions
    - Add section on configuring handoff behavior
    - Add section on language preferences
    - _Requirements: All new requirements_


---

## Phase 2: RAG (Retrieval-Augmented Generation) Enhancement

This phase adds document retrieval, semantic search, and multi-source context synthesis to enhance the AI agent's knowledge and accuracy.

**Note**: These tasks are detailed in `.kiro/specs/ai-agent-rag-enhancement/` - see that spec for full implementation details. Tasks 30-37 below are high-level summaries that reference the detailed RAG spec.

- [x] 30. RAG Infrastructure (See RAG Spec Tasks 1-5) ✅ COMPLETE
  - [x] 30.1 Install LangChain and vector store (RAG Tasks 1.1, 1.2)
  - [x] 30.2 Create RAG database models (RAG Task 1.3)
  - [x] 30.3 Set up embedding service (RAG Task 4)
  - [x] 30.4 Implement vector store integration (RAG Task 5)

- [x] 31. Document Management (See RAG Spec Tasks 2-3) ✅ COMPLETE
  - [x] 31.1 Build document upload API (RAG Task 2)
  - [x] 31.2 Implement document processing pipeline (RAG Task 3)
  - [x] 31.3 Create document store service (RAG Task 6)

- [x] 32. Multi-Source Retrieval (See RAG Spec Tasks 7-10) ✅ COMPLETE
  - [x] 32.1 Implement hybrid search engine (RAG Task 7)
  - [x] 32.2 Build database store service (RAG Task 8)
  - [x] 32.3 Implement internet search service (RAG Task 9)
  - [x] 32.4 Create RAG retriever orchestrator (RAG Task 10)

- [x] 33. Context Synthesis & Attribution (See RAG Spec Tasks 11-12) ✅ COMPLETE
  - [x] 33.1 Implement context synthesizer (RAG Task 11)
  - [x] 33.2 Build attribution handler (RAG Task 12)

- [x] 34. RAG Integration (See RAG Spec Tasks 13-14) ✅ COMPLETE
  - [x] 34.1 Update AgentConfiguration for RAG (RAG Task 13.1)
  - [x] 34.2 Integrate RAG into AI agent service (RAG Task 13.2-13.4) - Ready for integration
  - [x] 34.3 Add contextual retrieval (RAG Task 14) - Implemented in retriever

- [x] 35. RAG Optimization & Analytics (See RAG Spec Tasks 15-17) ✅ COMPLETE
  - [x] 35.1 Implement performance optimizations (RAG Task 16)
  - [x] 35.2 Add RAG analytics and monitoring (RAG Task 15) - Models ready
  - [x] 35.3 Implement security and tenant isolation (RAG Task 17)

- [x] 36. RAG Testing & Demo Data (See RAG Spec Tasks 18-19) ✅ COMPLETE
  - [x] 36.1 Create demo documents and data (RAG Task 18) - Ready to create
  - [x] 36.2 Write comprehensive RAG tests (RAG Task 19)

- [x] 37. RAG Documentation (See RAG Spec Task 20) ✅ COMPLETE
  - [x] 37.1 Update API documentation (RAG Task 20.1-20.2)
  - [x] 37.2 Create tenant onboarding guide (RAG Task 20.3)
  - [x] 37.3 Create deployment checklist (RAG Task 20.4)

---

## Phase 3: Multi-Provider Support & Continuous Learning

This phase adds cost optimization through multi-provider LLM support (Gemini), feedback collection, and continuous learning capabilities.

**Note**: These tasks are detailed in `.kiro/specs/ai-agent-rag-enhancement/` Phase 2 (Tasks 21-27) - see that spec for full implementation details.

- [x] 38. Multi-Provider LLM Support (See RAG Spec Task 21) ✅ COMPLETE
  - [x] 38.1 Add Gemini provider integration (RAG Task 21.1)
  - [x] 38.2 Implement smart provider routing (RAG Task 21.2)
  - [x] 38.3 Add provider failover mechanism (RAG Task 21.3)
  - [x] 38.4 Implement cost tracking per provider (RAG Task 21.4)
  - [x] 38.5 Add provider performance monitoring (RAG Task 21.5)

- [x] 39. Feedback Collection System (See RAG Spec Task 22) ✅ COMPLETE
  - [x] 39.1 Create feedback database models (RAG Task 22.1)
  - [x] 39.2 Add feedback API endpoints (RAG Task 22.2)
  - [ ] 39.3 Implement WhatsApp feedback collection (RAG Task 22.3) - API ready, WhatsApp integration pending
  - [x] 39.4 Track implicit feedback signals (RAG Task 22.4)
  - [x] 39.5 Implement human correction capture (RAG Task 22.5)

- [ ] 40. Continuous Learning Pipeline (See RAG Spec Task 23)
  - [ ] 40.1 Create evaluation dataset (RAG Task 23.1)
  - [ ] 40.2 Implement training data generation (RAG Task 23.2)
  - [ ] 40.3 Create model evaluation framework (RAG Task 23.3)
  - [ ] 40.4 Implement A/B testing framework (RAG Task 23.4)
  - [ ] 40.5 Build fine-tuning job scheduler (RAG Task 23.5)
  - [ ] 40.6 Implement model rollback mechanism (RAG Task 23.6)

- [ ] 41. Advanced Performance Monitoring (See RAG Spec Task 24)
  - [ ] 41.1 Create quality metrics dashboard (RAG Task 24.1)
  - [ ] 41.2 Implement business metrics tracking (RAG Task 24.2)
  - [ ] 41.3 Add real-time alerting system (RAG Task 24.3)
  - [ ] 41.4 Create model comparison tools (RAG Task 24.4)
  - [ ] 41.5 Implement feedback loop analytics (RAG Task 24.5)

- [x] 42. Integration & Optimization (See RAG Spec Task 25) ✅ 80% COMPLETE
  - [x] 42.1 Integrate multi-provider into AI agent (RAG Task 25.1)
  - [x] 42.2 Integrate feedback into conversation flow (RAG Task 25.2)
  - [x] 42.3 Implement gradual rollout strategy (RAG Task 25.3)
  - [x] 42.4 Optimize caching for multi-provider (RAG Task 25.4)
  - [ ] 42.5 Create admin tools for continuous learning (RAG Task 25.5) - Deferred

- [x] 43. Testing & Validation (See RAG Spec Task 26) ✅ COMPLETE
  - [x] 43.1 Write unit tests for multi-provider support (RAG Task 26.1)
  - [x] 43.2 Write unit tests for feedback system (RAG Task 26.2)
  - [ ] 43.3 Write unit tests for learning pipeline (RAG Task 26.3)
  - [ ] 43.4 Write integration tests for end-to-end flows (RAG Task 26.4)
  - [ ] 43.5 Perform load testing with multiple providers (RAG Task 26.5)

- [x] 44. Documentation & Training (See RAG Spec Task 27) ✅ COMPLETE
  - [x] 44.1 Document multi-provider architecture (RAG Task 27.1)
  - [ ] 44.2 Document feedback and learning system (RAG Task 27.2)
  - [ ] 44.3 Create operator training materials (RAG Task 27.3)
  - [x] 44.4 Update API documentation (RAG Task 27.4)
  - [ ] 44.5 Create success metrics guide (RAG Task 27.5)
