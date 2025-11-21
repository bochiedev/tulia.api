# Requirements Document

## Introduction

This specification defines a fundamental refactor of the Tulia AI (WabotIQ) conversational bot from a hallucination-prone, LLM-heavy system into a deterministic, sales-oriented agent. The current bot relies too heavily on LLMs for business logic, leading to hallucinated products, invented policies, high costs, and poor conversion rates. This refactor implements a hybrid architecture where deterministic business logic handles all critical decisions, and LLMs serve only as a thin NLU (Natural Language Understanding) and formatting layer. The goal is to create an autonomous agent that shortens the path from enquiry to sale/booking, maintains costs under $10/tenant/month, and never hallucinates business data.

## Glossary

- **Bot**: The AI-powered autonomous agent handling WhatsApp conversations for tenant businesses
- **Tenant**: The business owner whose products/services are sold through the Bot
- **Customer**: The end user interacting with the Bot via WhatsApp
- **Intent**: A classified user goal from a constrained set (e.g., BROWSE_PRODUCTS, BOOK_APPOINTMENT, PLACE_ORDER)
- **Slot**: A structured attribute extracted from user messages (e.g., category, date, time, quantity)
- **Business Logic Router**: The deterministic Python service that maps intents to actions without using LLMs
- **ConversationContext**: The state tracking current flow, last menu, awaiting response, and conversation summary
- **RAG**: Retrieval-Augmented Generation using Pinecone for grounded FAQ answers from tenant documents
- **Hallucination**: When the Bot generates incorrect information not grounded in actual database or document data
- **STK Push**: M-Pesa mobile money payment initiated via USSD prompt on customer's phone
- **Multi-Model Router**: The service that selects the cheapest viable LLM for each task

## Requirements

### Requirement 1

**User Story:** As a system architect, I want the Bot to use deterministic business logic for all critical decisions, so that products, prices, and policies are never hallucinated.

#### Acceptance Criteria

1. WHEN the Bot needs to display products THEN the system SHALL query the database and return only actual products with real prices
2. WHEN the Bot needs to check availability THEN the system SHALL query the database for actual stock or appointment slots
3. WHEN the Bot needs to create an order THEN the system SHALL use only database-validated product IDs and prices
4. WHEN the Bot needs to initiate payment THEN the system SHALL use only amounts calculated from database records
5. WHEN the Bot generates a response about policies THEN the system SHALL retrieve information only from RAG-indexed tenant documents or return uncertainty

### Requirement 2

**User Story:** As a system architect, I want intent classification to use rule-based detection first and LLMs only as fallback, so that LLM costs are minimized.

#### Acceptance Criteria

1. WHEN a Customer sends a message matching keyword patterns THEN the system SHALL classify intent using rules without calling an LLM
2. WHEN a Customer sends a numeric reply to a menu THEN the system SHALL resolve the selection deterministically without calling an LLM
3. WHEN a Customer interacts with WhatsApp buttons or lists THEN the system SHALL process the payload directly without calling an LLM
4. WHEN rule-based classification fails THEN the system SHALL call a small LLM model for intent detection
5. WHEN the LLM is called for intent detection THEN the system SHALL use GPT-4o-mini, Qwen 2.5 7B, or Gemini Flash exclusively

### Requirement 3

**User Story:** As a system architect, I want a constrained intent schema with clear slot extraction, so that the Bot handles only business-relevant conversations.

#### Acceptance Criteria

1. WHEN the system classifies intents THEN the system SHALL use only the predefined intent set: GREET, BROWSE_PRODUCTS, BROWSE_SERVICES, PRODUCT_DETAILS, SERVICE_DETAILS, PLACE_ORDER, BOOK_APPOINTMENT, CHECK_ORDER_STATUS, CHECK_APPOINTMENT_STATUS, ASK_DELIVERY_FEES, ASK_RETURN_POLICY, PAYMENT_HELP, REQUEST_HUMAN, GENERAL_FAQ, SMALL_TALK, UNKNOWN
2. WHEN the system extracts slots THEN the system SHALL use regex and rules for numbers, dates, times, and amounts before using LLMs
3. WHEN slot extraction requires an LLM THEN the system SHALL use a small model with structured JSON output
4. WHEN intent confidence is below threshold THEN the system SHALL ask clarifying questions or route to REQUEST_HUMAN
5. WHEN the system cannot classify an intent THEN the system SHALL return UNKNOWN and offer a main menu or human handoff

### Requirement 4

**User Story:** As a system architect, I want a Business Logic Router that maps intents to deterministic actions, so that all business flows are predictable and testable.

#### Acceptance Criteria

1. WHEN an intent is classified THEN the Business Logic Router SHALL map it to a handler function without using LLMs
2. WHEN a handler executes THEN the handler SHALL return a structured BotAction with type, text, and rich payload
3. WHEN a handler needs data THEN the handler SHALL query the database directly using tenant-scoped queries
4. WHEN a handler updates state THEN the handler SHALL update ConversationContext with new flow state and metadata
5. WHEN a handler encounters an error THEN the handler SHALL log to Sentry and return a graceful fallback message

### Requirement 5

**User Story:** As a Customer, I want to browse products immediately when I ask what's available, so that I can make a purchase decision quickly.

#### Acceptance Criteria

1. WHEN a Customer sends a BROWSE_PRODUCTS intent THEN the system SHALL query products from the database filtered by tenant
2. WHEN products are found THEN the system SHALL display up to 10 products with names, prices, and availability
3. WHEN products are displayed THEN the system SHALL store the list in ConversationContext as last_menu for reference resolution
4. WHEN no products match the query THEN the system SHALL show all available products with an explanation
5. WHEN the tenant has no products THEN the system SHALL respond with a graceful message and offer human handoff

### Requirement 6

**User Story:** As a Customer, I want to select products by number or button, so that I can quickly add items to my order without typing complex commands.

#### Acceptance Criteria

1. WHEN a Customer replies with a number after seeing a product list THEN the system SHALL resolve the selection from last_menu deterministically
2. WHEN a Customer clicks a WhatsApp button THEN the system SHALL process the button payload directly without LLM classification
3. WHEN a Customer selects from a WhatsApp list THEN the system SHALL process the list_reply_id directly without LLM classification
4. WHEN a selection is resolved THEN the system SHALL transition to the appropriate next step (details, add to cart, or checkout)
5. WHEN a selection cannot be resolved THEN the system SHALL ask for clarification and re-display the menu

### Requirement 7

**User Story:** As a Customer, I want to complete a purchase from browsing to payment in a clear step-by-step flow, so that I can buy products without confusion.

#### Acceptance Criteria

1. WHEN a Customer selects a product THEN the system SHALL ask for quantity and variants if applicable
2. WHEN product details are confirmed THEN the system SHALL create an Order with status PENDING_PAYMENT
3. WHEN an order is created THEN the system SHALL ask for payment method selection (M-Pesa STK, M-Pesa manual, or card)
4. WHEN a payment method is selected THEN the system SHALL initiate the appropriate payment flow
5. WHEN payment is confirmed THEN the system SHALL update the Order status to PAID and send a confirmation message

### Requirement 8

**User Story:** As a Customer, I want to pay via M-Pesa STK push, so that I can complete my purchase quickly from my phone.

#### Acceptance Criteria

1. WHEN a Customer selects M-Pesa STK payment THEN the system SHALL ask for the phone number to use
2. WHEN a phone number is provided THEN the system SHALL initiate an STK push using the tenant's M-Pesa credentials
3. WHEN the STK push is initiated THEN the system SHALL create a PaymentRequest with status PENDING
4. WHEN the M-Pesa callback confirms success THEN the system SHALL update PaymentRequest to SUCCESS and Order to PAID
5. WHEN the M-Pesa callback indicates failure THEN the system SHALL update PaymentRequest to FAILED and offer retry or alternative payment

### Requirement 9

**User Story:** As a Customer, I want to pay via card payment link, so that I can use my credit or debit card for purchases.

#### Acceptance Criteria

1. WHEN a Customer selects card payment THEN the system SHALL generate a payment link using Paystack, Stripe, or Pesapal
2. WHEN a payment link is generated THEN the system SHALL create a PaymentRequest with status PENDING
3. WHEN a payment link is generated THEN the system SHALL send the link to the Customer via WhatsApp
4. WHEN the payment provider webhook confirms success THEN the system SHALL update PaymentRequest to SUCCESS and Order to PAID
5. WHEN the payment provider webhook indicates failure THEN the system SHALL update PaymentRequest to FAILED and notify the Customer

### Requirement 10

**User Story:** As a Customer, I want to book service appointments with date and time selection, so that I can schedule services at my convenience.

#### Acceptance Criteria

1. WHEN a Customer sends a BOOK_APPOINTMENT intent THEN the system SHALL identify the requested service from the message or ask for selection
2. WHEN a service is selected THEN the system SHALL ask for preferred date and time if not provided
3. WHEN date and time are provided THEN the system SHALL check availability against business hours and existing appointments
4. WHEN a slot is available THEN the system SHALL create an Appointment with status PENDING_CONFIRMATION and ask for confirmation
5. WHEN the Customer confirms THEN the system SHALL update Appointment to CONFIRMED and optionally initiate payment

### Requirement 11

**User Story:** As a Customer, I want to check my order or appointment status, so that I can track my purchases and bookings.

#### Acceptance Criteria

1. WHEN a Customer sends a CHECK_ORDER_STATUS intent THEN the system SHALL query orders for the Customer filtered by tenant
2. WHEN orders are found THEN the system SHALL display the most recent order with status, items, and tracking information
3. WHEN a Customer sends a CHECK_APPOINTMENT_STATUS intent THEN the system SHALL query appointments for the Customer filtered by tenant
4. WHEN appointments are found THEN the system SHALL display upcoming appointments with service, date, time, and status
5. WHEN no orders or appointments are found THEN the system SHALL respond with a helpful message and offer to create new ones

### Requirement 12

**User Story:** As a Customer, I want answers to FAQ questions grounded in the business's actual policies, so that I receive accurate information.

#### Acceptance Criteria

1. WHEN a Customer sends a GENERAL_FAQ, ASK_RETURN_POLICY, or ASK_DELIVERY_FEES intent THEN the system SHALL retrieve relevant chunks from Pinecone using the tenant namespace
2. WHEN relevant chunks are retrieved THEN the system SHALL pass them to a small LLM with a strict prompt to answer only from context
3. WHEN the LLM generates an answer THEN the answer SHALL be validated to contain only information from the retrieved chunks
4. WHEN no relevant chunks are found or similarity is below threshold THEN the system SHALL respond with uncertainty and offer human handoff
5. WHEN the LLM is used for FAQ THEN the system SHALL use GPT-4o-mini, Qwen 2.5 7B, or Gemini Flash exclusively

### Requirement 13

**User Story:** As a system architect, I want conversation context to track flow state and last interactions, so that multi-step flows work correctly.

#### Acceptance Criteria

1. WHEN a conversation starts THEN the system SHALL create or load a ConversationContext with current_flow, last_menu, and awaiting_response
2. WHEN the Bot displays a menu or list THEN the system SHALL store it in ConversationContext.last_menu with item IDs and positions
3. WHEN the Bot asks a question THEN the system SHALL set ConversationContext.awaiting_response and last_question
4. WHEN a Customer responds THEN the system SHALL check awaiting_response and route accordingly
5. WHEN a flow completes THEN the system SHALL clear current_flow and awaiting_response flags

### Requirement 14

**User Story:** As a system architect, I want LLM usage to be minimized and tracked, so that per-tenant costs stay under $10/month.

#### Acceptance Criteria

1. WHEN the system calls an LLM THEN the system SHALL log tenant_id, model_name, input_tokens, output_tokens, and estimated_cost
2. WHEN the system selects an LLM THEN the system SHALL prefer small models (GPT-4o-mini, Qwen 2.5 7B, Gemini Flash) over larger models
3. WHEN the system builds LLM context THEN the system SHALL use conversation summary and last 3-5 messages only, not full history
4. WHEN the system generates responses THEN the system SHALL request concise outputs with token limits
5. WHEN a tenant exceeds monthly LLM budget THEN the system SHALL throttle LLM usage and fall back to rule-based responses

### Requirement 15

**User Story:** As a system architect, I want all database queries to be tenant-scoped, so that data isolation is guaranteed.

#### Acceptance Criteria

1. WHEN the system queries products THEN the query SHALL filter by tenant_id
2. WHEN the system queries services THEN the query SHALL filter by tenant_id
3. WHEN the system queries orders THEN the query SHALL filter by tenant_id
4. WHEN the system queries appointments THEN the query SHALL filter by tenant_id
5. WHEN the system queries RAG documents THEN the query SHALL use the tenant-specific Pinecone namespace

### Requirement 16

**User Story:** As a system architect, I want WhatsApp messages to use rich interactive elements, so that Customers have a better user experience.

#### Acceptance Criteria

1. WHEN the Bot displays 2-10 products THEN the system SHALL format them as WhatsApp list messages with selectable items
2. WHEN the Bot displays product details THEN the system SHALL include action buttons for "Add to Cart" or "Buy Now"
3. WHEN the Bot asks for confirmation THEN the system SHALL use WhatsApp button messages with "Yes" and "No" options
4. WHEN WhatsApp rich message API fails THEN the system SHALL fall back to plain text with numbered lists
5. WHEN the Bot sends a payment link THEN the system SHALL format it as a clickable URL in the message

### Requirement 17

**User Story:** As a system architect, I want the Bot to handle errors gracefully, so that Customers never see technical error messages.

#### Acceptance Criteria

1. WHEN a database query fails THEN the system SHALL log the error to Sentry and respond with a user-friendly apology message
2. WHEN an LLM call times out THEN the system SHALL fall back to rule-based responses or offer human handoff
3. WHEN a payment provider API fails THEN the system SHALL log the error and offer alternative payment methods
4. WHEN an unknown error occurs THEN the system SHALL offer human handoff and log full context for debugging
5. WHEN the system offers human handoff THEN the system SHALL tag the conversation as needs_human and stop automated responses

### Requirement 18

**User Story:** As a system architect, I want the Bot to respect tenant business hours and quiet hours, so that Customers are not disturbed at inappropriate times.

#### Acceptance Criteria

1. WHEN a message arrives during quiet hours THEN the system SHALL respond with a quiet hours message and queue the conversation for later
2. WHEN a Customer tries to book an appointment outside business hours THEN the system SHALL suggest alternative times within business hours
3. WHEN the system checks availability THEN the system SHALL respect TenantSettings.business_hours
4. WHEN the system sends proactive messages THEN the system SHALL check quiet hours before sending
5. WHEN quiet hours end THEN the system SHALL process queued conversations in order

### Requirement 19

**User Story:** As a system architect, I want the Bot to support English, Swahili, and Sheng, so that Customers can communicate in their preferred language.

#### Acceptance Criteria

1. WHEN the system detects language from a message THEN the system SHALL identify English, Swahili, Sheng, or mixed language
2. WHEN the system generates responses THEN the system SHALL use the detected language consistently
3. WHEN the system uses an LLM for formatting THEN the system SHALL instruct the LLM to use the detected language
4. WHEN language is ambiguous THEN the system SHALL default to the tenant's configured primary language
5. WHEN the system stores language preference THEN the system SHALL persist it in ConversationContext for future messages

### Requirement 20

**User Story:** As a system architect, I want comprehensive testing for all business logic handlers, so that the system is reliable and maintainable.

#### Acceptance Criteria

1. WHEN a business logic handler is implemented THEN the handler SHALL have unit tests covering success and error cases
2. WHEN intent classification is implemented THEN the system SHALL have tests for rule-based and LLM-based classification
3. WHEN payment flows are implemented THEN the system SHALL have tests for STK push, manual M-Pesa, and card payments
4. WHEN appointment booking is implemented THEN the system SHALL have tests for availability checking and slot conflicts
5. WHEN RAG retrieval is implemented THEN the system SHALL have tests for grounded answers and uncertainty handling
