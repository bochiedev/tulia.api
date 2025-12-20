"""
LLM-powered nodes for LangGraph orchestration.

This module implements the core LLM nodes for intent classification,
language policy, and conversation governance with exact JSON schemas
and confidence thresholds as specified in the design.
"""
import logging
from typing import Dict, Any, Optional
import json

from apps.bot.langgraph.nodes import LLMNode
from apps.bot.conversation_state import ConversationState, Intent, Journey, Lang, GovernorClass
from apps.bot.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class IntentClassificationNode(LLMNode):
    """
    Intent classification node with JSON output schema.
    
    Implements exact intent classification with confidence scoring:
    - confidence >= 0.70: route to suggested journey
    - 0.50 <= confidence < 0.70: ask ONE clarifying question then re-classify
    - confidence < 0.50: route to unknown handler
    """
    
    def __init__(self):
        """Initialize intent classification node."""
        system_prompt = """You are an intent classifier for a conversational commerce assistant.

Analyze the user's message and classify their intent with confidence scoring.

EXACT INTENTS (use only these):
- sales_discovery: Looking for products/services, browsing, "what do you have"
- product_question: Specific questions about products/services, features, availability
- support_question: Help with existing products, technical issues, how-to questions
- order_status: Checking order status, delivery, tracking
- discounts_offers: Asking about discounts, coupons, promotions, deals
- preferences_consent: Language preferences, marketing opt-in/out, notifications
- payment_help: Payment issues, methods, failed transactions
- human_request: Explicitly asking for human agent ("agent", "human", "call me")
- spam_casual: Off-topic, casual chat, spam, irrelevant messages
- unknown: Unclear intent, ambiguous messages

SUGGESTED JOURNEYS:
- sales_discovery/product_question → sales
- support_question/payment_help → support  
- order_status → orders
- discounts_offers → offers
- preferences_consent → prefs
- human_request → governance
- spam_casual → governance
- unknown → unknown

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "intent": "exact_intent_name",
    "confidence": 0.0-1.0,
    "notes": "short explanation",
    "suggested_journey": "sales|support|orders|offers|prefs|governance|unknown"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": [
                    "sales_discovery", "product_question", "support_question", "order_status",
                    "discounts_offers", "preferences_consent", "payment_help",
                    "human_request", "spam_casual", "unknown"
                ]},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "notes": {"type": "string", "maxLength": 100},
                "suggested_journey": {"type": "string", "enum": [
                    "sales", "support", "orders", "offers", "prefs", "governance", "unknown"
                ]}
            },
            "required": ["intent", "confidence", "notes", "suggested_journey"]
        }
        
        super().__init__("intent_classify", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for intent classification.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"User message: {state.incoming_message}",
            f"Conversation turn: {state.turn_count}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Tenant: {state.tenant_name or 'Commerce Bot'}"
        ]
        
        # Add conversation history context if available
        if state.turn_count > 1:
            context_parts.append(f"Previous intent: {state.intent}")
            if state.last_catalog_query:
                context_parts.append(f"Previous search: {state.last_catalog_query}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for intent classification with structured JSON output.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Intent classification result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                return {
                    "intent": "unknown",
                    "confidence": 0.0,
                    "notes": "Budget exceeded",
                    "suggested_journey": "unknown"
                }
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('intent_classification')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=150,
                temperature=0.1,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'intent_classification', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if not all(key in result for key in ["intent", "confidence", "notes", "suggested_journey"]):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate intent is in allowed list
                valid_intents = [
                    "sales_discovery", "product_question", "support_question", "order_status",
                    "discounts_offers", "preferences_consent", "payment_help",
                    "human_request", "spam_casual", "unknown"
                ]
                if result["intent"] not in valid_intents:
                    result["intent"] = "unknown"
                    result["confidence"] = 0.0
                    result["notes"] = "Invalid intent from LLM"
                
                # Validate confidence range
                if not (0.0 <= result["confidence"] <= 1.0):
                    result["confidence"] = max(0.0, min(1.0, result["confidence"]))
                
                # Ensure journey matches intent
                result["suggested_journey"] = self._intent_to_journey(result["intent"])
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to heuristic classification
                intent = self._classify_intent_heuristic(state.incoming_message or "")
                return {
                    "intent": intent,
                    "confidence": 0.6,
                    "notes": "Heuristic fallback",
                    "suggested_journey": self._intent_to_journey(intent)
                }
            
        except Exception as e:
            logger.error(
                f"Intent classification LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to heuristic classification
            intent = self._classify_intent_heuristic(state.incoming_message or "")
            return {
                "intent": intent,
                "confidence": 0.5,
                "notes": f"LLM error fallback: {str(e)[:50]}",
                "suggested_journey": self._intent_to_journey(intent)
            }
    
    def _classify_intent_heuristic(self, message: str) -> str:
        """
        Heuristic intent classification as fallback.
        
        Uses keyword matching to classify intents when LLM fails.
        
        Args:
            message: User message
            
        Returns:
            Classified intent
        """
        if not message:
            return "unknown"
        
        message_lower = message.lower().strip()
        
        # Human request keywords (highest priority)
        human_keywords = ['human', 'agent', 'person', 'call me', 'speak to someone', 'representative']
        if any(word in message_lower for word in human_keywords):
            return "human_request"
        
        # Order status keywords
        order_keywords = ['order', 'delivery', 'tracking', 'status', 'shipped', 'delivered', 'my order']
        if any(word in message_lower for word in order_keywords):
            return "order_status"
        
        # Payment help keywords
        payment_keywords = ['payment', 'pay', 'paid', 'transaction', 'refund', 'charge', 'billing']
        if any(word in message_lower for word in payment_keywords):
            return "payment_help"
        
        # Discounts/offers keywords
        discount_keywords = ['discount', 'coupon', 'offer', 'deal', 'promo', 'sale', 'cheap']
        if any(word in message_lower for word in discount_keywords):
            return "discounts_offers"
        
        # Preferences/consent keywords
        pref_keywords = ['language', 'unsubscribe', 'stop', 'opt out', 'preferences', 'settings']
        if any(word in message_lower for word in pref_keywords):
            return "preferences_consent"
        
        # Support question keywords
        support_keywords = ['help', 'support', 'problem', 'issue', 'broken', 'not working', 'error']
        if any(word in message_lower for word in support_keywords):
            return "support_question"
        
        # Product question keywords
        product_keywords = ['product', 'item', 'feature', 'specification', 'available', 'stock']
        if any(word in message_lower for word in product_keywords):
            return "product_question"
        
        # Sales discovery keywords
        sales_keywords = ['buy', 'purchase', 'shop', 'catalog', 'what do you have', 'show me', 'looking for']
        if any(word in message_lower for word in sales_keywords):
            return "sales_discovery"
        
        # Casual/greeting keywords
        casual_keywords = ['hello', 'hi', 'hey', 'how are you', 'good morning', 'good afternoon', 'thanks']
        if any(word in message_lower for word in casual_keywords):
            return "spam_casual"
        
        # Very short messages or unclear
        if len(message_lower) < 3:
            return "spam_casual"
        
        return "unknown"
    
    def _intent_to_journey(self, intent: str) -> str:
        """
        Map intent to journey according to exact specifications.
        
        Args:
            intent: Detected intent
            
        Returns:
            Corresponding journey
        """
        intent_journey_map = {
            "sales_discovery": "sales",
            "product_question": "sales",
            "support_question": "support",
            "order_status": "orders",
            "discounts_offers": "offers",
            "preferences_consent": "prefs",
            "payment_help": "support",
            "human_request": "governance",
            "spam_casual": "governance",
            "unknown": "unknown"
        }
        
        return intent_journey_map.get(intent, "unknown")
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from intent classification result with routing logic.
        
        Implements exact routing thresholds:
        - confidence >= 0.70: route to suggested journey
        - 0.50 <= confidence < 0.70: ask ONE clarifying question then re-classify
        - confidence < 0.50: route to unknown handler
        
        Args:
            state: Current conversation state
            result: LLM classification result
            
        Returns:
            Updated conversation state
        """
        intent = result["intent"]
        confidence = result["confidence"]
        suggested_journey = result["suggested_journey"]
        
        # Update intent and confidence
        state.update_intent(intent, confidence)
        
        # Apply routing thresholds
        if confidence >= 0.70:
            # High confidence - route to suggested journey
            state.journey = suggested_journey
            routing_decision = "route_to_journey"
        elif 0.50 <= confidence < 0.70:
            # Medium confidence - ask clarifying question
            state.journey = "unknown"  # Will trigger clarification
            routing_decision = "ask_clarification"
        else:
            # Low confidence - route to unknown handler
            state.journey = "unknown"
            routing_decision = "route_to_unknown"
        
        logger.info(
            f"Intent classified: {intent} (confidence: {confidence:.2f}) -> {routing_decision}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "intent": intent,
                "confidence": confidence,
                "suggested_journey": suggested_journey,
                "final_journey": state.journey,
                "routing_decision": routing_decision,
                "notes": result["notes"]
            }
        )
        
        return state


class LanguagePolicyNode(LLMNode):
    """
    Language policy node with confidence-based switching.
    
    Implements language detection with exact thresholds:
    - confidence >= 0.75 AND language in allowed: switch language
    - confidence < 0.75: use tenant default language
    """
    
    def __init__(self):
        """Initialize language policy node."""
        system_prompt = """You are a language detection system for a multilingual commerce assistant.

Detect the user's preferred language and determine response language policy.

SUPPORTED LANGUAGES:
- en: English (default)
- sw: Swahili  
- sheng: Sheng (Kenyan slang mix)
- mixed: Code-switching between languages

DETECTION RULES:
- Analyze the user's message for language indicators
- Consider explicit language requests ("speak Swahili", "in English please")
- Detect code-switching patterns
- Account for customer language preference if set

LANGUAGE INDICATORS:
English: Standard English words, grammar patterns
Swahili: Words like "habari", "mambo", "asante", "karibu", "nina", "nataka", "sawa"
Sheng: Kenyan slang like "niaje", "sema", "poa", "fiti", "uko", "niko", "msee"
Mixed: Code-switching between languages in same message

EXPLICIT REQUESTS:
- "Speak Swahili" / "Ongea Kiswahili" -> sw with high confidence
- "In English please" / "Kwa Kiingereza" -> en with high confidence
- "Sheng" / "Mtaani" -> sheng with high confidence

POLICY RULES:
- If confidence >= 0.75 AND detected language is in tenant's allowed languages: switch
- If confidence < 0.75: use tenant default language
- Always respect explicit customer language preference overrides

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "response_language": "en|sw|sheng|mixed",
    "confidence": 0.0-1.0,
    "should_ask_language_question": true|false
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "response_language": {"type": "string", "enum": ["en", "sw", "sheng", "mixed"]},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "should_ask_language_question": {"type": "boolean"}
            },
            "required": ["response_language", "confidence", "should_ask_language_question"]
        }
        
        super().__init__("language_policy", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for language policy determination.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"User message: {state.incoming_message}",
            f"Tenant default language: {state.default_language}",
            f"Allowed languages: {', '.join(state.allowed_languages)}",
            f"Customer language preference: {state.customer_language_pref or 'Not set'}"
        ]
        
        # Add conversation history for language consistency
        if state.turn_count > 1:
            context_parts.append(f"Previous response language: {state.response_language}")
            context_parts.append(f"Language confidence history: {state.language_confidence}")
        
        # Add explicit language request detection hints
        message_lower = (state.incoming_message or "").lower()
        if any(phrase in message_lower for phrase in ["speak swahili", "ongea kiswahili", "in swahili"]):
            context_parts.append("EXPLICIT REQUEST: User explicitly requested Swahili")
        elif any(phrase in message_lower for phrase in ["in english", "speak english", "kwa kiingereza"]):
            context_parts.append("EXPLICIT REQUEST: User explicitly requested English")
        elif any(phrase in message_lower for phrase in ["sheng", "mtaani", "street language"]):
            context_parts.append("EXPLICIT REQUEST: User explicitly requested Sheng")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for language policy determination with structured JSON output.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Language policy result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to heuristic detection
                detected_language = self._detect_language_heuristic(state.incoming_message or "")
                return {
                    "response_language": detected_language,
                    "confidence": 0.6,
                    "should_ask_language_question": False
                }
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('language_detection')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=100,
                temperature=0.1,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'language_detection', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if not all(key in result for key in ["response_language", "confidence", "should_ask_language_question"]):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate language is in supported list
                valid_languages = ["en", "sw", "sheng", "mixed"]
                if result["response_language"] not in valid_languages:
                    result["response_language"] = state.default_language
                    result["confidence"] = 0.5
                
                # Validate confidence range
                if not (0.0 <= result["confidence"] <= 1.0):
                    result["confidence"] = max(0.0, min(1.0, result["confidence"]))
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse language policy LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to heuristic detection
                detected_language = self._detect_language_heuristic(state.incoming_message or "")
                return {
                    "response_language": detected_language,
                    "confidence": 0.6,
                    "should_ask_language_question": False
                }
            
        except Exception as e:
            logger.error(
                f"Language policy LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to heuristic detection
            detected_language = self._detect_language_heuristic(state.incoming_message or "")
            return {
                "response_language": detected_language,
                "confidence": 0.5,
                "should_ask_language_question": False
            }
    
    def _detect_language_heuristic(self, message: str) -> str:
        """
        Enhanced heuristic language detection as fallback.
        
        Uses keyword matching and pattern recognition to classify languages
        when LLM fails.
        
        Args:
            message: User message
            
        Returns:
            Detected language code
        """
        if not message:
            return "en"
        
        message_lower = message.lower().strip()
        
        # Check for explicit language requests first (highest priority)
        if any(phrase in message_lower for phrase in ["speak swahili", "ongea kiswahili", "in swahili", "kwa kiswahili"]):
            return "sw"
        elif any(phrase in message_lower for phrase in ["in english", "speak english", "kwa kiingereza", "english please"]):
            return "en"
        elif any(phrase in message_lower for phrase in ["sheng", "mtaani", "street language"]):
            return "sheng"
        
        # Count language indicators
        swahili_score = 0
        sheng_score = 0
        english_score = 0
        
        # Swahili keywords and patterns
        swahili_words = [
            'habari', 'mambo', 'poa', 'sawa', 'asante', 'karibu', 'nina', 'nataka', 
            'niko', 'uko', 'yuko', 'tuko', 'mko', 'wako', 'nini', 'gani', 'wapi',
            'lini', 'namna', 'jinsi', 'kwa', 'na', 'au', 'lakini', 'pia', 'tu',
            'kwanza', 'mwisho', 'sana', 'kidogo', 'kubwa', 'ndogo', 'nzuri', 'mbaya'
        ]
        
        for word in swahili_words:
            if word in message_lower:
                swahili_score += 1
        
        # Sheng keywords (Kenyan slang)
        sheng_words = [
            'niaje', 'sema', 'poa', 'fiti', 'uko', 'niko', 'msee', 'dame', 'jamaa',
            'keja', 'doh', 'mullah', 'ngwaci', 'mathree', 'gari', 'job', 'kazi',
            'shule', 'chuo', 'buda', 'manzi', 'dem', 'boy', 'kichwa', 'uso'
        ]
        
        for word in sheng_words:
            if word in message_lower:
                sheng_score += 1
        
        # English patterns (common English words not in Swahili/Sheng)
        english_words = [
            'hello', 'hi', 'hey', 'thanks', 'thank', 'please', 'sorry', 'excuse',
            'what', 'where', 'when', 'how', 'why', 'who', 'which', 'can', 'could',
            'would', 'should', 'will', 'shall', 'may', 'might', 'must', 'need',
            'want', 'like', 'love', 'hate', 'good', 'bad', 'nice', 'great'
        ]
        
        for word in english_words:
            if word in message_lower:
                english_score += 1
        
        # Check for mixed language patterns (code-switching)
        total_indicators = swahili_score + sheng_score + english_score
        if total_indicators >= 2 and swahili_score > 0 and english_score > 0:
            return "mixed"
        elif total_indicators >= 2 and sheng_score > 0 and (swahili_score > 0 or english_score > 0):
            return "mixed"
        
        # Determine primary language
        if sheng_score > swahili_score and sheng_score > english_score:
            return "sheng"
        elif swahili_score > english_score:
            return "sw"
        elif english_score > 0:
            return "en"
        
        # Default to English for unclear cases
        return "en"
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from language policy result with exact threshold logic.
        
        Implements exact language switching logic:
        - IF confidence >= 0.75 AND language in allowed_languages THEN switch
        - IF confidence < 0.75 THEN use tenant.default_language
        - Respect customer language preferences (override if explicitly set)
        
        Args:
            state: Current conversation state
            result: LLM language policy result
            
        Returns:
            Updated conversation state
        """
        detected_language = result["response_language"]
        confidence = result["confidence"]
        should_ask_question = result.get("should_ask_language_question", False)
        
        # Store original values for logging
        original_language = state.response_language
        
        # Apply exact language policy thresholds
        if confidence >= 0.75 and detected_language in state.allowed_languages:
            # High confidence and allowed language - switch
            final_language = detected_language
            language_switched = True
            switch_reason = "high_confidence_allowed"
        else:
            # Low confidence or not allowed - use tenant default
            final_language = state.default_language
            language_switched = False
            if confidence < 0.75:
                switch_reason = "low_confidence_fallback"
            else:
                switch_reason = "language_not_allowed"
        
        # Override with customer preference if explicitly set
        if state.customer_language_pref and state.customer_language_pref in state.allowed_languages:
            final_language = state.customer_language_pref
            language_switched = True
            switch_reason = "customer_preference_override"
        
        # Update state with final language decision
        state.update_language(final_language, confidence)
        
        # Log detailed language policy decision
        logger.info(
            f"Language policy applied: {original_language} -> {final_language}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "detected_language": detected_language,
                "detection_confidence": confidence,
                "original_language": original_language,
                "final_language": final_language,
                "language_switched": language_switched,
                "switch_reason": switch_reason,
                "customer_preference": state.customer_language_pref,
                "allowed_languages": state.allowed_languages,
                "tenant_default": state.default_language,
                "should_ask_question": should_ask_question,
                "threshold_met": confidence >= 0.75,
                "language_allowed": detected_language in state.allowed_languages
            }
        )
        
        return state


class ConversationGovernorNode(LLMNode):
    """
    Conversation governor node for spam/casual detection and cost control.
    
    Implements business vs casual/spam classification with exact routing:
    - business: proceed to journey routing
    - casual: check chattiness limits, redirect if exceeded
    - spam: increment spam turns, disengage after 2 turns
    - abuse: stop immediately
    
    Chattiness levels (EXACT):
    - Level 0: Strictly business only (no small talk)
    - Level 1: 1 short greeting allowed
    - Level 2: Max 2 casual turns before redirect (DEFAULT)
    - Level 3: Max 4 casual turns before redirect
    
    Routing logic (EXACT):
    - IF classification == "business" THEN proceed
    - IF "casual" THEN increment casual_turns, allow max per level before redirect
    - IF "spam" THEN increment spam_turns, after 2 turns disengage
    - IF "abuse" THEN stop immediately
    """
    
    def __init__(self):
        """Initialize conversation governor node."""
        system_prompt = """You are a conversation governor for a commerce assistant.

Your role is to classify user messages to maintain business focus, prevent spam/abuse, and control conversation costs.

CLASSIFICATIONS (use only these):
- business: Commerce-related messages including product inquiries, orders, support, payments, preferences, legitimate business requests
- casual: Friendly chat, greetings, small talk, off-topic but harmless conversations, social pleasantries
- spam: Repetitive messages, nonsense, testing messages, irrelevant content, very short meaningless messages
- abuse: Offensive language, harassment, inappropriate content, threats, explicit content

CLASSIFICATION GUIDELINES:

BUSINESS indicators:
- Product/service inquiries ("what products", "show me", "I want to buy")
- Order-related ("my order", "delivery status", "tracking")
- Support requests ("help with", "problem", "not working")
- Payment discussions ("how to pay", "payment failed", "refund")
- Preference management ("change language", "unsubscribe", "opt out")
- Legitimate questions about business operations

CASUAL indicators:
- Greetings only ("hello", "hi", "hey", "good morning")
- Social pleasantries ("how are you", "what's up", "nice to meet you")
- Off-topic chat ("weather", "sports", "news")
- Personal questions not related to commerce
- Friendly banter without business intent

SPAM indicators:
- Very short messages (< 3 characters) without clear meaning
- Repetitive patterns ("test test test", "123 123")
- Nonsense strings ("asdf", "qwerty", "random")
- Multiple identical messages in sequence
- Messages clearly testing the system

ABUSE indicators:
- Profanity and offensive language
- Harassment or threatening language
- Sexually explicit content
- Hate speech or discriminatory language
- Attempts to manipulate or break the system

CONTEXT CONSIDERATIONS:
- First message greetings are often casual but acceptable
- Business messages may include casual elements (friendly tone)
- Repeated casual messages after redirects indicate spam
- Consider conversation history and patterns

RECOMMENDED ACTIONS:
- business → proceed (continue with commerce conversation)
- casual → redirect (friendly redirect to business topics)
- spam → limit (warn and limit responses)
- abuse → stop (immediately stop conversation)
- handoff → escalate to human (for edge cases)

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "classification": "business|casual|spam|abuse",
    "confidence": 0.0-1.0,
    "recommended_action": "proceed|redirect|limit|stop|handoff"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "classification": {"type": "string", "enum": ["business", "casual", "spam", "abuse"]},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "recommended_action": {"type": "string", "enum": ["proceed", "redirect", "limit", "stop", "handoff"]}
            },
            "required": ["classification", "confidence", "recommended_action"]
        }
        
        super().__init__("governor_spam_casual", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for conversation governance.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"User message: {state.incoming_message}",
            f"Turn count: {state.turn_count}",
            f"Casual turns so far: {state.casual_turns}",
            f"Spam turns so far: {state.spam_turns}",
            f"Max chattiness level: {state.max_chattiness_level}",
            f"Current intent: {state.intent}",
            f"Intent confidence: {state.intent_confidence}"
        ]
        
        # Add conversation pattern context
        if state.turn_count > 1:
            context_parts.append(f"Previous governor classification: {state.governor_classification}")
            context_parts.append(f"Previous journey: {state.journey}")
        
        # Add chattiness level context
        max_casual_turns = self._get_max_casual_turns(state.max_chattiness_level)
        context_parts.append(f"Max casual turns allowed: {max_casual_turns}")
        
        # Add warning if approaching limits
        if state.casual_turns >= max_casual_turns - 1:
            context_parts.append("WARNING: Approaching casual turn limit")
        if state.spam_turns >= 1:
            context_parts.append("WARNING: Spam detected in conversation")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for conversation governance with structured JSON output.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Governance classification result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to heuristic classification
                classification = self._classify_governance_heuristic(state.incoming_message or "", state)
                return {
                    "classification": classification,
                    "confidence": 0.6,
                    "recommended_action": self._get_recommended_action(classification, state)
                }
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('governance')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make structured LLM call with JSON schema
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=100,
                temperature=0.1,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'governance', response.input_tokens)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                if not all(key in result for key in ["classification", "confidence", "recommended_action"]):
                    raise ValueError("Missing required fields in LLM response")
                
                # Validate classification is in allowed list
                valid_classifications = ["business", "casual", "spam", "abuse"]
                if result["classification"] not in valid_classifications:
                    result["classification"] = "business"
                    result["confidence"] = 0.5
                
                # Validate confidence range
                if not (0.0 <= result["confidence"] <= 1.0):
                    result["confidence"] = max(0.0, min(1.0, result["confidence"]))
                
                # Validate recommended action
                valid_actions = ["proceed", "redirect", "limit", "stop", "handoff"]
                if result["recommended_action"] not in valid_actions:
                    result["recommended_action"] = self._get_recommended_action(result["classification"], state)
                
                return result
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Failed to parse governance LLM JSON response: {e}. Response: {response.content}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "request_id": state.request_id
                    }
                )
                
                # Fallback to heuristic classification
                classification = self._classify_governance_heuristic(state.incoming_message or "", state)
                return {
                    "classification": classification,
                    "confidence": 0.6,
                    "recommended_action": self._get_recommended_action(classification, state)
                }
            
        except Exception as e:
            logger.error(
                f"Conversation governor LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to heuristic classification
            classification = self._classify_governance_heuristic(state.incoming_message or "", state)
            return {
                "classification": classification,
                "confidence": 0.5,
                "recommended_action": self._get_recommended_action(classification, state)
            }
    
    def _classify_governance_heuristic(self, message: str, state: ConversationState) -> str:
        """
        Enhanced heuristic governance classification as fallback.
        
        Uses keyword matching and pattern recognition to classify messages
        when LLM fails.
        
        Args:
            message: User message
            state: Current conversation state
            
        Returns:
            Governance classification
        """
        if not message:
            return "spam"
        
        message_lower = message.lower().strip()
        
        # Check for abuse keywords (highest priority) - use word boundaries
        abuse_words = [
            'fuck', 'shit', 'damn', 'bitch', 'ass', 'hell', 'bastard',
            'stupid', 'idiot', 'moron', 'dumb', 'hate', 'kill', 'die'
        ]
        # Use word boundaries to avoid false positives (e.g., "hello" containing "hell")
        import re
        for word in abuse_words:
            if re.search(r'\b' + re.escape(word) + r'\b', message_lower):
                return "abuse"
        
        # Check for spam patterns
        # Very short messages
        if len(message.strip()) < 3:
            return "spam"
        
        # Repetitive characters
        if len(set(message.strip())) <= 2 and len(message.strip()) > 3:
            return "spam"
        
        # Common spam/test keywords
        spam_words = ['test', 'testing', '123', 'asdf', 'qwerty', 'random', 'zzz']
        if any(word in message_lower for word in spam_words):
            return "spam"
        
        # Check if message is mostly numbers or special characters
        alphanumeric_count = sum(c.isalnum() for c in message)
        if alphanumeric_count < len(message) * 0.5 and len(message) > 2:  # Changed from > 5 to > 2
            return "spam"
        
        # Check for business intent keywords (high priority)
        business_keywords = [
            # Product/shopping
            'buy', 'purchase', 'shop', 'product', 'item', 'catalog', 'price', 'cost',
            'available', 'stock', 'show me', 'looking for', 'want', 'need',
            # Orders
            'order', 'delivery', 'tracking', 'status', 'shipped', 'delivered',
            # Support
            'help', 'support', 'problem', 'issue', 'broken', 'not working', 'error',
            'question', 'how to', 'can you', 'unable',
            # Payment
            'payment', 'pay', 'paid', 'transaction', 'refund', 'charge', 'billing',
            'mpesa', 'card', 'checkout',
            # Offers
            'discount', 'coupon', 'offer', 'deal', 'promo', 'sale', 'cheap',
            # Preferences
            'language', 'unsubscribe', 'stop', 'opt out', 'preferences', 'settings'
        ]
        
        if any(keyword in message_lower for keyword in business_keywords):
            return "business"
        
        # Check if intent is business-related
        business_intents = [
            "sales_discovery", "product_question", "support_question", "order_status",
            "discounts_offers", "preferences_consent", "payment_help"
        ]
        if state.intent in business_intents and state.intent_confidence >= 0.5:
            return "business"
        
        # Check for casual/greeting keywords
        casual_keywords = [
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'how are you', 'what\'s up', 'whats up', 'wassup', 'sup',
            'thanks', 'thank you', 'bye', 'goodbye', 'see you',
            'nice', 'cool', 'great', 'awesome', 'lol', 'haha'
        ]
        
        if any(keyword in message_lower for keyword in casual_keywords):
            # First turn greetings are acceptable casual
            if state.turn_count <= 1:
                return "casual"
            # Subsequent casual messages
            return "casual"
        
        # Check for questions without business context
        question_words = ['what', 'where', 'when', 'how', 'why', 'who', 'which']
        has_question = any(word in message_lower for word in question_words) or '?' in message
        
        if has_question and len(message_lower.split()) <= 5:
            # Short questions without business keywords are likely casual
            return "casual"
        
        # Default to business for unclear cases (benefit of the doubt)
        return "business"
    
    def _get_max_casual_turns(self, chattiness_level: int) -> int:
        """
        Get maximum casual turns allowed for chattiness level.
        
        EXACT levels as specified:
        - Level 0: 0 casual turns (strictly business)
        - Level 1: 1 casual turn (1 short greeting)
        - Level 2: 2 casual turns (DEFAULT)
        - Level 3: 4 casual turns
        
        Args:
            chattiness_level: Tenant's max chattiness level (0-3)
            
        Returns:
            Maximum casual turns allowed
        """
        level_map = {
            0: 0,  # Strictly business
            1: 1,  # 1 short greeting
            2: 2,  # Max 2 casual turns (DEFAULT)
            3: 4   # Max 4 casual turns
        }
        return level_map.get(chattiness_level, 2)  # Default to level 2
    
    def _get_recommended_action(self, classification: str, state: ConversationState) -> str:
        """
        Get recommended action for governance classification with state-aware logic.
        
        Implements EXACT routing logic:
        - business: proceed
        - casual: check limits, redirect if exceeded
        - spam: check limits, disengage after 2 turns
        - abuse: stop immediately
        
        Args:
            classification: Governance classification
            state: Current conversation state
            
        Returns:
            Recommended action
        """
        if classification == "business":
            return "proceed"
        
        elif classification == "casual":
            max_casual_turns = self._get_max_casual_turns(state.max_chattiness_level)
            
            # Level 0: No casual allowed
            if max_casual_turns == 0:
                return "redirect"
            
            # Check if we've exceeded casual turn limit
            if state.casual_turns >= max_casual_turns:
                return "redirect"
            
            # Still within limits
            return "proceed"
        
        elif classification == "spam":
            # After 2 spam turns, disengage
            if state.spam_turns >= 2:
                return "stop"
            else:
                return "limit"
        
        elif classification == "abuse":
            # Abuse: stop immediately
            return "stop"
        
        # Default fallback
        return "proceed"
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from governance classification result with EXACT routing logic and rate limiting.
        
        Implements:
        - IF classification == "business" THEN proceed
        - IF "casual" THEN increment casual_turns, allow max per level before redirect
        - IF "spam" THEN increment spam_turns, after 2 turns disengage
        - IF "abuse" THEN stop immediately
        - Rate limiting per customer per tenant
        
        Args:
            state: Current conversation state
            result: LLM governance result
            
        Returns:
            Updated conversation state
        """
        from apps.bot.services.rate_limiter import get_rate_limiter
        
        classification = result["classification"]
        confidence = result["confidence"]
        recommended_action = result["recommended_action"]
        
        # Store original values for logging
        original_casual_turns = state.casual_turns
        original_spam_turns = state.spam_turns
        
        # Update governor classification
        state.update_governor(classification, confidence)
        
        # Check rate limits first
        rate_limiter = get_rate_limiter()
        
        # Increment message count for rate limiting
        if state.customer_id:
            rate_limiter.increment_message_count(state.tenant_id, state.customer_id)
            
            # Check if customer is rate limited
            rate_limit_status = rate_limiter.check_rate_limit(state.tenant_id, state.customer_id)
            
            if not rate_limit_status['allowed']:
                # Rate limited - set appropriate response and stop
                if rate_limit_status['reason'] == 'spam_cooldown':
                    state.response_text = "Please wait before sending more messages. I'll be here when you're ready to discuss our products or services."
                elif rate_limit_status['reason'] == 'abuse_cooldown':
                    state.response_text = "This conversation has been temporarily restricted. Please contact our support team if you need assistance."
                else:
                    state.response_text = "You're sending messages too quickly. Please wait a moment before continuing."
                
                state.journey = "governance"
                state.set_escalation(f"Rate limited: {rate_limit_status['reason']}")
                
                logger.warning(
                    f"Customer rate limited: {rate_limit_status['reason']}",
                    extra={
                        "tenant_id": state.tenant_id,
                        "conversation_id": state.conversation_id,
                        "customer_id": state.customer_id,
                        "rate_limit_reason": rate_limit_status['reason'],
                        "retry_after_seconds": rate_limit_status['retry_after_seconds'],
                        "current_counts": rate_limit_status['current_counts']
                    }
                )
                
                return state
        
        # Apply EXACT routing logic and update turn counters
        if classification == "business":
            # Business: proceed normally, no turn increments
            routing_decision = "proceed_to_journey"
            
        elif classification == "casual":
            # Casual: increment casual_turns
            state.increment_casual_turns()
            
            # Check casual turn limits
            casual_limit_status = rate_limiter.check_casual_turn_limit(
                state.casual_turns, 
                state.max_chattiness_level
            )
            
            if casual_limit_status['should_redirect']:
                # Exceeded limit: redirect to business
                routing_decision = "redirect_to_business"
                state.journey = "governance"  # Route to governance response
            else:
                # Within limit: allow casual interaction
                routing_decision = "allow_casual"
                # Don't change journey, let it proceed
        
        elif classification == "spam":
            # Spam: increment spam_turns
            state.increment_spam_turns()
            
            if state.spam_turns >= 2:
                # After 2 spam turns: disengage and apply cooldown
                routing_decision = "disengage"
                state.journey = "governance"  # Route to governance response
                state.response_text = "I'm here to help with your shopping needs. Please let me know if you have any questions about our products or services."
                
                # Apply spam cooldown
                if state.customer_id:
                    rate_limiter.apply_spam_cooldown(state.tenant_id, state.customer_id)
            else:
                # First spam turn: warn and limit
                routing_decision = "warn_spam"
                state.journey = "governance"  # Route to governance response
        
        elif classification == "abuse":
            # Abuse: stop immediately and apply cooldown
            routing_decision = "stop_immediately"
            state.journey = "governance"  # Route to governance response
            state.set_escalation("Abusive content detected")
            state.response_text = "I'm unable to continue this conversation. If you need assistance, please contact our support team."
            
            # Apply abuse cooldown
            if state.customer_id:
                rate_limiter.apply_abuse_cooldown(state.tenant_id, state.customer_id)
        
        else:
            # Unknown classification: default to business
            routing_decision = "default_proceed"
        
        # Log detailed governance decision
        logger.info(
            f"Conversation governed: {classification} -> {routing_decision}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "classification": classification,
                "confidence": confidence,
                "recommended_action": recommended_action,
                "routing_decision": routing_decision,
                "casual_turns": state.casual_turns,
                "spam_turns": state.spam_turns,
                "max_chattiness_level": state.max_chattiness_level,
                "max_casual_turns_allowed": self._get_max_casual_turns(state.max_chattiness_level),
                "casual_turns_incremented": state.casual_turns > original_casual_turns,
                "spam_turns_incremented": state.spam_turns > original_spam_turns,
                "journey": state.journey,
                "escalation_required": state.escalation_required,
                "rate_limited": not rate_limit_status.get('allowed', True) if state.customer_id else False
            }
        )
        
        return state