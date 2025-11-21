# Requirements Document

## Introduction

This specification addresses critical conversation flow failures in the WabotIQ bot that prevent sales completion. Real user conversations reveal that the bot: (1) echoes user messages verbatim, (2) never sends interactive WhatsApp elements despite having the code, (3) maintains poor context across conversation sessions, (4) talks endlessly without closing sales, (5) constantly disclaims "needs verification" undermining user confidence, and (6) never actually initiates payment flows. This spec focuses on fixing these immediate blockers to enable the bot to actually complete sales transactions.

## Glossary

- **Bot**: The AI-powered sales assistant handling WhatsApp conversations
- **Customer**: The end user purchasing products/services via WhatsApp
- **Tenant**: The business owner whose products are being sold
- **Interactive Message**: WhatsApp-native UI elements (buttons, lists, cards) that users can tap
- **STK Push**: M-Pesa mobile payment prompt sent directly to customer's phone
- **Conversation Session**: A continuous conversation that may span multiple days
- **Message Echo**: When the bot repeats the customer's exact words back to them
- **Sales Closure**: The complete flow from product selection to payment initiation
- **Context Window**: The recent conversation history used to generate responses

## Requirements

### Requirement 1

**User Story:** As a Customer, I want the bot to respond to my messages without repeating what I just said, so that the conversation feels natural and not robotic.

#### Acceptance Criteria

1. WHEN a Customer sends a message THEN the Bot SHALL NOT include the customer's exact message text in the response
2. WHEN the Bot needs to confirm understanding THEN the Bot SHALL paraphrase or reference the intent, not echo verbatim
3. WHEN a Customer selects an item by number THEN the Bot SHALL reference the item name, not repeat the number
4. WHEN the Bot generates a response THEN the response SHALL be validated to ensure it does not contain customer message echoes
5. WHEN the Bot confirms an action THEN the Bot SHALL use natural confirmation language without quoting the customer

### Requirement 2

**User Story:** As a Customer, I want to see products as tappable cards with buttons, so that I can easily select items without typing.

#### Acceptance Criteria

1. WHEN the Bot displays products THEN the Bot SHALL send WhatsApp interactive list messages or button messages
2. WHEN a product list is sent THEN each product SHALL have a unique selectable ID that the Bot can process
3. WHEN a Customer taps a product button THEN the Bot SHALL receive the selection payload and proceed to next step
4. WHEN the WhatsApp API is unavailable THEN the Bot SHALL fall back to numbered text lists
5. WHEN the Bot sends interactive messages THEN the messages SHALL be logged for debugging and analytics

### Requirement 3

**User Story:** As a Customer, I want the bot to remember our conversation even if I message again the next day, so that I don't have to start over.

#### Acceptance Criteria

1. WHEN a Customer sends a message THEN the Bot SHALL load the complete conversation history regardless of time gaps
2. WHEN a conversation spans multiple days THEN the Bot SHALL maintain context continuity
3. WHEN the Bot loads context THEN the Bot SHALL include the last 20 messages plus a summary of older messages
4. WHEN a Customer references something from a previous day THEN the Bot SHALL retrieve the relevant context
5. WHEN the Bot cannot find relevant context THEN the Bot SHALL ask for clarification without claiming "we haven't talked"

### Requirement 4

**User Story:** As a Customer, I want the bot to guide me quickly to checkout and payment, so that I can complete my purchase without endless back-and-forth.

#### Acceptance Criteria

1. WHEN a Customer expresses purchase intent THEN the Bot SHALL immediately ask for quantity and proceed to checkout
2. WHEN a Customer confirms a product THEN the Bot SHALL create an order and ask for payment method within 2 messages
3. WHEN a Customer is ready to pay THEN the Bot SHALL initiate payment within 1 message
4. WHEN the Bot guides to checkout THEN the Bot SHALL use a maximum of 3 messages from product selection to payment initiation
5. WHEN payment is initiated THEN the Bot SHALL send confirmation and stop further prompting

### Requirement 5

**User Story:** As a Customer, I want the bot to confidently provide product information without constant disclaimers, so that I trust the information I'm receiving.

#### Acceptance Criteria

1. WHEN the Bot displays product information from the database THEN the Bot SHALL present it as factual without disclaimers
2. WHEN the Bot is uncertain about information THEN the Bot SHALL offer to connect with a human instead of adding disclaimers
3. WHEN the Bot retrieves product details THEN the Bot SHALL validate data completeness before responding
4. WHEN product data is incomplete THEN the Bot SHALL omit the missing fields without mentioning verification
5. WHEN the Bot generates responses THEN responses SHALL NOT contain phrases like "needs verification", "may need confirmation", or "please verify"

### Requirement 6

**User Story:** As a Customer, I want to pay via M-Pesa STK push immediately after confirming my order, so that I can complete my purchase quickly.

#### Acceptance Criteria

1. WHEN a Customer confirms an order THEN the Bot SHALL ask for the M-Pesa phone number
2. WHEN a phone number is provided THEN the Bot SHALL initiate an STK push within 5 seconds
3. WHEN the STK push is initiated THEN the Bot SHALL send a message instructing the customer to check their phone
4. WHEN the M-Pesa callback confirms payment THEN the Bot SHALL send order confirmation
5. WHEN the M-Pesa callback indicates failure THEN the Bot SHALL offer to retry or provide alternative payment methods

### Requirement 7

**User Story:** As a Customer, I want the bot to stop talking and wait for my response after asking a question, so that I'm not overwhelmed with messages.

#### Acceptance Criteria

1. WHEN the Bot asks a question THEN the Bot SHALL wait for customer response before sending additional messages
2. WHEN the Bot sends a product list THEN the Bot SHALL not send follow-up prompts until customer responds
3. WHEN the Bot initiates payment THEN the Bot SHALL wait for payment confirmation before sending more messages
4. WHEN a Customer is viewing options THEN the Bot SHALL not send unsolicited suggestions
5. WHEN the Bot completes an action THEN the Bot SHALL send one confirmation message and stop

### Requirement 8

**User Story:** As a system architect, I want the bot to use conversation context from the current session only, so that old unrelated conversations don't pollute responses.

#### Acceptance Criteria

1. WHEN the Bot loads context THEN the Bot SHALL prioritize messages from the current conversation session
2. WHEN a conversation has been idle for more than 24 hours THEN the Bot SHALL treat the next message as a new session
3. WHEN the Bot detects a new session THEN the Bot SHALL load a summary of previous sessions, not full message history
4. WHEN the Bot generates responses THEN the Bot SHALL use only the last 20 messages plus session summary
5. WHEN the Bot references past interactions THEN the Bot SHALL only reference the current session unless explicitly asked

### Requirement 9

**User Story:** As a Customer, I want to see product images in the bot's messages, so that I can make informed purchase decisions.

#### Acceptance Criteria

1. WHEN the Bot displays a product THEN the Bot SHALL include the product image URL if available
2. WHEN a product has multiple images THEN the Bot SHALL use the primary image
3. WHEN a product has no image THEN the Bot SHALL send the message without an image placeholder
4. WHEN the Bot sends interactive messages THEN images SHALL be included in the WhatsApp media payload
5. WHEN an image URL is invalid THEN the Bot SHALL send the message without the image and log the error

### Requirement 10

**User Story:** As a system architect, I want the bot to use deterministic business logic for order creation and payment, so that no steps are skipped or hallucinated.

#### Acceptance Criteria

1. WHEN a Customer confirms a product THEN the Bot SHALL create an Order record with status PENDING_PAYMENT
2. WHEN an Order is created THEN the Bot SHALL calculate the total from database product prices
3. WHEN payment is initiated THEN the Bot SHALL create a PaymentRequest record with the exact order total
4. WHEN the Bot processes payment THEN the Bot SHALL use only the tenant's actual payment credentials from TenantSettings
5. WHEN payment succeeds THEN the Bot SHALL update Order status to PAID and send confirmation

### Requirement 11

**User Story:** As a Customer, I want the bot to understand when I say "I want this one" after seeing products, so that I don't have to type the full product name.

#### Acceptance Criteria

1. WHEN a Customer says "this one", "that one", or "the first one" THEN the Bot SHALL resolve the reference to the most recent product list
2. WHEN a Customer uses a number like "1" or "2" THEN the Bot SHALL map it to the corresponding product from the last list
3. WHEN the Bot resolves a reference THEN the Bot SHALL confirm the product name before proceeding
4. WHEN a reference is ambiguous THEN the Bot SHALL ask for clarification with specific options
5. WHEN no recent product list exists THEN the Bot SHALL ask the customer to specify which product they mean

### Requirement 12

**User Story:** As a system architect, I want all bot responses to be concise and action-oriented, so that customers can complete purchases quickly.

#### Acceptance Criteria

1. WHEN the Bot generates a response THEN the response SHALL be a maximum of 3 sentences
2. WHEN the Bot displays products THEN the Bot SHALL show a maximum of 5 products at a time
3. WHEN the Bot asks a question THEN the question SHALL be direct and require a simple answer
4. WHEN the Bot confirms an action THEN the confirmation SHALL be one sentence
5. WHEN the Bot provides information THEN the Bot SHALL focus on the next action the customer should take

### Requirement 13

**User Story:** As a Tenant, I want the bot to use my business name and branding in conversations, so that customers know they're talking to my business.

#### Acceptance Criteria

1. WHEN the Bot introduces itself THEN the Bot SHALL use the tenant's business name
2. WHEN the Bot sends messages THEN the Bot SHALL maintain the tenant's brand voice from AgentConfiguration
3. WHEN the Bot confirms orders THEN the Bot SHALL reference the business name in confirmations
4. WHEN the Bot hands off to human THEN the Bot SHALL identify itself as the business's AI assistant
5. WHEN the tenant has configured a custom greeting THEN the Bot SHALL use it for first messages

### Requirement 14

**User Story:** As a system architect, I want the bot to log all payment attempts and outcomes, so that we can debug payment failures and track conversions.

#### Acceptance Criteria

1. WHEN the Bot initiates payment THEN the Bot SHALL create a PaymentRequest record with status PENDING
2. WHEN a payment callback is received THEN the Bot SHALL update the PaymentRequest with the callback data
3. WHEN payment fails THEN the Bot SHALL log the failure reason and error details
4. WHEN payment succeeds THEN the Bot SHALL log the transaction reference and amount
5. WHEN the Bot encounters payment errors THEN the Bot SHALL log to Sentry with full context

### Requirement 15

**User Story:** As a Customer, I want the bot to handle my messages in the language I'm using, so that I can communicate naturally.

#### Acceptance Criteria

1. WHEN a Customer sends a message in Swahili THEN the Bot SHALL respond in Swahili
2. WHEN a Customer sends a message in English THEN the Bot SHALL respond in English
3. WHEN a Customer mixes languages THEN the Bot SHALL use the dominant language in the response
4. WHEN the Bot detects language THEN the Bot SHALL store the preference in ConversationContext
5. WHEN a Customer switches languages THEN the Bot SHALL adapt to the new language immediately

