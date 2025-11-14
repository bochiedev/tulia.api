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
  
  - [ ] 3.3 Create REST API endpoints for knowledge base management
    - Create `KnowledgeEntrySerializer` with all fields
    - Create `KnowledgeEntryViewSet` with full CRUD operations
    - Add search endpoint with query parameter
    - Add bulk import endpoint for CSV/JSON
    - Add RBAC enforcement with required scope "integrations:manage"
    - _Requirements: 15.4, 15.5_

- [ ] 4. Build conversation memory and context system
  - [ ] 4.1 Create `ConversationContext` model for memory storage
    - Add fields for current_topic, pending_action, extracted_entities
    - Add foreign keys for last_product_viewed, last_service_viewed
    - Add fields for conversation_summary, key_facts, context_expires_at
    - Create database migration with indexes
    - _Requirements: 3.1, 3.2, 3.3, 20.1, 20.2, 22.1, 22.2_
  
  - [ ] 4.2 Implement `ContextBuilderService` for assembling agent context
    - Write `build_context()` method that orchestrates all context sources
    - Write `get_conversation_history()` method with intelligent truncation
    - Write `get_relevant_knowledge()` method using semantic search
    - Write `get_catalog_context()` method for products and services
    - Write `get_customer_history()` method for orders and appointments
    - Implement context window management with priority-based truncation
    - _Requirements: 3.1, 3.2, 3.5, 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [ ] 4.3 Add conversation summary generation for long histories
    - Write method to summarize old messages using LLM
    - Implement periodic background task to generate summaries
    - Store summaries in ConversationContext model
    - Use summaries when full history exceeds context window
    - _Requirements: 3.5, 8.5_

- [ ] 5. Implement core AI agent service
  - [ ] 5.1 Create `AIAgentService` class with main orchestration logic
    - Write `process_message()` method as main entry point
    - Write `generate_response()` method using LLM provider
    - Write `should_handoff()` method for handoff decisions
    - Write `select_model()` method based on task complexity
    - Add comprehensive error handling and logging
    - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.2, 7.1, 7.2_
  
  - [ ] 5.2 Build dynamic prompt engineering system
    - Write `build_system_prompt()` method with persona injection
    - Write `build_user_prompt()` method with context assembly
    - Implement prompt templates for different scenarios
    - Add knowledge base injection into prompts
    - Add catalog context injection into prompts
    - _Requirements: 2.5, 5.5, 8.1, 8.2, 8.3, 8.4_
  
  - [ ] 5.3 Implement intelligent handoff logic
    - Write confidence threshold checking
    - Write topic-based auto-handoff detection
    - Write consecutive low-confidence tracking
    - Write handoff reason categorization
    - Update conversation status on handoff
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6. Add fuzzy matching and spelling correction
  - [ ] 6.1 Implement `FuzzyMatcherService` for intelligent matching
    - Write `match_product()` method using Levenshtein distance and semantic similarity
    - Write `match_service()` method with same approach
    - Write `correct_spelling()` method using vocabulary-based correction
    - Add support for abbreviations and informal names
    - Return confidence scores with matches
    - _Requirements: 16.1, 16.2, 16.5, 21.1, 21.2, 21.3, 21.4, 21.5_
  
  - [ ] 6.2 Integrate fuzzy matching into agent workflow
    - Pre-process customer messages for spelling correction
    - Use fuzzy matching when exact catalog matches fail
    - Confirm corrections with customer when confidence is low
    - Track correction accuracy for improvement
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [ ] 7. Build multi-intent and message burst handling
  - [ ] 7.1 Create `MessageQueue` model for burst management
    - Add fields for conversation, message, status, queue_position
    - Add timestamps for queued_at and processed_at
    - Create database migration with indexes
    - _Requirements: 17.1, 17.4_
  
  - [ ] 7.2 Implement `MultiIntentProcessor` service
    - Write `detect_intents()` method using LLM to identify multiple intents
    - Write `process_message_burst()` method to handle queued messages
    - Write `prioritize_intents()` method based on urgency and logic
    - Write `generate_structured_response()` addressing all intents
    - _Requirements: 17.2, 17.3, 17.5_
  
  - [ ] 7.3 Add message queueing logic to Celery task
    - Detect rapid message sequences (within 5 seconds)
    - Queue messages instead of processing immediately
    - Batch process queued messages after delay
    - Prevent duplicate intent processing
    - _Requirements: 17.1, 17.4, 17.5_

- [ ] 8. Implement rich WhatsApp messaging features
  - [ ] 8.1 Create `RichMessageBuilder` service for interactive messages
    - Write `build_product_card()` method with image and buttons
    - Write `build_service_card()` method with image and buttons
    - Write `build_list_message()` method for selections
    - Write `build_button_message()` method for quick replies
    - Add validation against WhatsApp message limits
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [ ] 8.2 Integrate rich messages into Twilio service
    - Update `TwilioService` to support WhatsApp interactive messages
    - Add methods for sending button messages
    - Add methods for sending list messages
    - Add methods for sending media with captions
    - Handle button click responses
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [ ] 8.3 Update agent response generation to use rich messages
    - Detect when rich messages are appropriate
    - Generate rich message payloads from agent responses
    - Fall back to text when rich messages unavailable
    - Track rich message usage in analytics
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [ ] 9. Add proactive suggestions and recommendations
  - [ ] 9.1 Implement recommendation logic in agent service
    - Write `generate_suggestions()` method based on context
    - Use customer history for personalized recommendations
    - Suggest complementary products/services
    - Prioritize available inventory and appointments
    - Explain reasoning for suggestions
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ] 9.2 Integrate suggestions into response generation
    - Add suggestions to agent prompts
    - Format suggestions in responses
    - Use rich messages for suggestion presentation
    - Track suggestion acceptance rate
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 10. Create analytics and tracking system
  - [ ] 10.1 Create `AgentInteraction` model for tracking
    - Add fields for customer_message, detected_intents, model_used
    - Add fields for agent_response, confidence_score, handoff_triggered
    - Add fields for message_type, token_usage, estimated_cost
    - Create database migration with indexes
    - _Requirements: 7.5, 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 10.2 Implement interaction tracking in agent service
    - Track every agent interaction in database
    - Calculate and store token usage
    - Estimate costs based on model and tokens
    - Track handoff reasons and outcomes
    - _Requirements: 7.5, 13.1, 13.2, 13.3_
  
  - [ ] 10.3 Create analytics API endpoints
    - Create endpoint for conversation statistics
    - Create endpoint for handoff analytics
    - Create endpoint for cost tracking
    - Create endpoint for common topics/intents
    - Add RBAC enforcement with required scope "analytics:view"
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 11. Add Together AI provider for model aggregation
  - [ ] 11.1 Implement `TogetherAIProvider` class
    - Implement authentication and API integration
    - Support model selection (Llama, Mistral, etc.)
    - Normalize responses to common format
    - Track usage and costs per provider
    - Implement fallback when models unavailable
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [ ] 11.2 Add Together AI configuration to agent settings
    - Add Together AI API key to tenant settings
    - Add model selection UI for Together AI models
    - Update provider factory to support Together AI
    - Add cost tracking for Together AI usage
    - _Requirements: 14.1, 14.2, 14.4_

- [ ] 12. Implement campaign message builder with rich media
  - [ ] 12.1 Create campaign message models
    - Extend existing campaign models to support rich media
    - Add fields for images, videos, documents
    - Add fields for button configurations
    - Create database migration
    - _Requirements: 19.1, 19.2, 19.3, 19.4_
  
  - [ ] 12.2 Build campaign message creation API
    - Create endpoints for campaign creation with media
    - Support image upload with caption and buttons
    - Support video upload with caption and buttons
    - Support document upload with description
    - Validate button configurations (max 3 per message)
    - _Requirements: 19.1, 19.2, 19.3, 19.4_
  
  - [ ] 12.3 Implement campaign button interaction tracking
    - Track button clicks in analytics
    - Route button responses to appropriate handlers
    - Update campaign engagement metrics
    - _Requirements: 19.5_

- [ ] 13. Add context retention and memory management
  - [ ] 13.1 Implement context expiration and cleanup
    - Set context expiration to 30 minutes of inactivity
    - Create background task to clean expired contexts
    - Preserve key facts even after expiration
    - _Requirements: 22.1, 22.2, 22.3_
  
  - [ ] 13.2 Add context restoration for returning customers
    - Detect when customer returns after pause
    - Restore relevant context from previous session
    - Acknowledge previous topic in greeting
    - Offer to continue or start fresh
    - _Requirements: 22.2, 22.3, 22.4_
  
  - [ ] 13.3 Implement "forgot request" recovery
    - Detect phrases like "did you forget"
    - Retrieve last unanswered question from history
    - Apologize and address the missed request
    - Track recovery success rate
    - _Requirements: 22.4, 22.5_

- [ ] 14. Update main message processing task
  - [ ] 14.1 Refactor `process_inbound_message` Celery task
    - Replace old intent service with new AI agent service
    - Add message queueing for burst detection
    - Integrate context builder for full context
    - Use rich message builder for responses
    - Add comprehensive error handling
    - _Requirements: All_
  
  - [ ] 14.2 Add feature flag for gradual rollout
    - Create feature flag for new AI agent
    - Allow per-tenant enablement
    - Fall back to old system if flag disabled
    - Track usage of new vs old system
    - _Requirements: All_

- [ ] 15. Performance optimization and caching
  - [ ] 15.1 Implement caching strategy
    - Cache agent configurations (5 minute TTL)
    - Cache knowledge base embeddings
    - Cache catalog data (1 minute TTL)
    - Use Redis for distributed caching
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ] 15.2 Optimize database queries
    - Add database indexes for all tenant_id fields
    - Add indexes for conversation_id and created_at
    - Implement query result caching
    - Use select_related and prefetch_related
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [ ] 15.3 Add request deduplication
    - Detect duplicate message processing attempts
    - Use distributed locks for message processing
    - Prevent concurrent processing of same message
    - _Requirements: 12.4_

- [ ] 16. Security and multi-tenant isolation
  - [ ] 16.1 Audit all queries for tenant filtering
    - Verify all knowledge base queries filter by tenant
    - Verify all conversation queries filter by tenant
    - Verify all catalog queries filter by tenant
    - Add automated tests for tenant isolation
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 16.2 Implement input validation and sanitization
    - Sanitize all customer message inputs
    - Validate knowledge base content
    - Prevent prompt injection attacks
    - Add rate limiting to API endpoints
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 16.3 Add encryption for sensitive data
    - Encrypt customer messages at rest
    - Encrypt knowledge base content
    - Encrypt API keys in database
    - Implement secure key rotation
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 17. Monitoring and observability
  - [ ] 17.1 Add comprehensive logging
    - Log all agent interactions with structured data
    - Log LLM API calls and responses
    - Log context building steps
    - Log handoff decisions with reasons
    - Use JSON structured logging
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 17.2 Implement metrics collection
    - Track response time (p50, p95, p99)
    - Track token usage per conversation
    - Track cost per conversation
    - Track handoff rate and reasons
    - Track knowledge base hit rate
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 17.3 Set up alerting
    - Alert on high error rates
    - Alert on slow response times
    - Alert on high costs
    - Alert on frequent handoffs
    - Alert on API failures
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [ ]* 18. Testing and quality assurance
  - [ ]* 18.1 Write unit tests for all services
    - Test LLM provider abstraction and fallbacks
    - Test context builder with various scenarios
    - Test fuzzy matcher accuracy
    - Test multi-intent processor
    - Test rich message builder
    - _Requirements: All_
  
  - [ ]* 18.2 Write integration tests
    - Test end-to-end message flow
    - Test knowledge base search accuracy
    - Test conversation memory retention
    - Test multi-tenant isolation
    - Test rich message delivery
    - _Requirements: All_
  
  - [ ]* 18.3 Write performance tests
    - Test response time under load
    - Test concurrent tenant usage
    - Test context building speed
    - Test knowledge search speed
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [ ]* 18.4 Write AI quality tests
    - Test intent accuracy with sample messages
    - Test spelling correction accuracy
    - Test context retention across gaps
    - Test multi-intent handling
    - Test handoff appropriateness
    - _Requirements: All_

- [ ] 19. Documentation and deployment
  - [ ] 19.1 Update API documentation
    - Document all new endpoints in OpenAPI
    - Add example requests and responses
    - Document RBAC requirements
    - Add integration guides
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [ ] 19.2 Create tenant onboarding guide
    - Document agent configuration options
    - Provide knowledge base setup guide
    - Explain model selection and costs
    - Include best practices
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 5.3_
  
  - [ ] 19.3 Create deployment checklist
    - Environment variable configuration
    - Database migration steps
    - Cache setup verification
    - Monitoring setup
    - Rollback procedures
    - _Requirements: All_
