"""
Preferences & Consent Journey subgraph implementation for LangGraph orchestration.

This module implements the complete preferences and consent journey workflow
with preference parsing, consent updates, and immediate STOP/UNSUBSCRIBE processing.
"""
import logging
from typing import Dict, Any, Optional, List
import json
import re

from apps.bot.conversation_state import ConversationState, Lang
from apps.bot.langgraph.nodes import LLMNode
from apps.bot.services.llm_router import LLMRouter
from apps.bot.tools.registry import get_tool

logger = logging.getLogger(__name__)


class PreferenceParsingNode(LLMNode):
    """
    Preference parsing node for extracting language, marketing, and notification preferences.
    
    Parses user messages to identify preference changes and consent updates
    with immediate STOP/UNSUBSCRIBE processing.
    """
    
    def __init__(self):
        """Initialize preference parsing node."""
        system_prompt = """You are a preference parsing assistant that extracts customer preference changes from messages.

PREFERENCE TYPES TO DETECT:
1. Language preferences: "English", "Swahili", "Sheng", "mixed languages"
2. Marketing consent: "stop marketing", "unsubscribe", "no promotions", "yes to offers"
3. Notification preferences: "stop notifications", "no messages", "only important updates"
4. STOP/UNSUBSCRIBE keywords: "STOP", "UNSUBSCRIBE", "QUIT", "END" (case insensitive)

IMMEDIATE PROCESSING RULES:
- STOP/UNSUBSCRIBE keywords require immediate processing (marketing_opt_out: true)
- Be conservative - only extract explicit preference changes
- Don't assume preferences from ambiguous messages
- Distinguish between temporary requests and permanent preference changes

LANGUAGE MAPPING:
- "English", "en" → "en"
- "Swahili", "Kiswahili", "sw" → "sw" 
- "Sheng", "sheng" → "sheng"
- "both", "mixed", "any language" → "mixed"

MARKETING CONSENT MAPPING:
- "stop marketing", "unsubscribe", "no promotions", "STOP", "UNSUBSCRIBE" → false
- "yes to offers", "send promotions", "marketing ok" → true
- Leave null if not explicitly mentioned

You MUST respond with valid JSON only. No other text.

Return JSON with exact schema:
{
    "has_preferences": true|false,
    "language_preference": "en|sw|sheng|mixed|null",
    "marketing_opt_in": true|false|null,
    "notification_preferences": {
        "marketing": true|false|null,
        "notifications": true|false|null,
        "important_only": true|false|null
    },
    "immediate_stop": true|false,
    "parsed_intent": "language_change|marketing_opt_out|marketing_opt_in|notification_change|stop_all|general_inquiry",
    "confidence": 0.0-1.0,
    "notes": "brief explanation of what was detected"
}"""
        
        output_schema = {
            "type": "object",
            "properties": {
                "has_preferences": {"type": "boolean"},
                "language_preference": {
                    "type": ["string", "null"],
                    "enum": ["en", "sw", "sheng", "mixed", None]
                },
                "marketing_opt_in": {"type": ["boolean", "null"]},
                "notification_preferences": {
                    "type": "object",
                    "properties": {
                        "marketing": {"type": ["boolean", "null"]},
                        "notifications": {"type": ["boolean", "null"]},
                        "important_only": {"type": ["boolean", "null"]}
                    }
                },
                "immediate_stop": {"type": "boolean"},
                "parsed_intent": {
                    "type": "string",
                    "enum": ["language_change", "marketing_opt_out", "marketing_opt_in", 
                            "notification_change", "stop_all", "general_inquiry"]
                },
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "notes": {"type": "string", "maxLength": 200}
            },
            "required": ["has_preferences", "immediate_stop", "parsed_intent", "confidence", "notes"]
        }
        
        super().__init__("preference_parsing", system_prompt, output_schema)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for preference parsing.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"User message: {state.incoming_message}",
            f"Current language preference: {state.customer_language_pref or 'not set'}",
            f"Current marketing opt-in: {state.marketing_opt_in}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Tenant: {state.tenant_name or 'Customer Service'}"
        ]
        
        # Add conversation context
        if state.turn_count > 1:
            context_parts.append(f"Conversation turn: {state.turn_count}")
            if state.intent:
                context_parts.append(f"Previous intent: {state.intent}")
        
        # Add current notification preferences if available
        if state.notification_prefs:
            context_parts.append(f"Current notification preferences: {state.notification_prefs}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for preference parsing with structured JSON output.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Preference parsing result with exact JSON schema
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                return self._get_heuristic_fallback(state)
            
            # Get provider for structured output
            provider_name, model_name = llm_router._select_model('preference_parsing')
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
                temperature=0.1,  # Low temperature for factual parsing
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            result = json.loads(response.content)
            
            # Validate against schema
            if self._validate_output(result):
                return result
            else:
                logger.warning(f"Invalid LLM output for preference parsing: {result}")
                return self._get_heuristic_fallback(state)
                
        except Exception as e:
            logger.error(f"LLM call failed for preference parsing: {str(e)}")
            return self._get_heuristic_fallback(state)
    
    def _get_heuristic_fallback(self, state: ConversationState) -> Dict[str, Any]:
        """
        Heuristic fallback for preference parsing when LLM fails.
        
        Uses simple keyword matching for basic preference detection.
        
        Args:
            state: Current conversation state
            
        Returns:
            Heuristic preference parsing result
        """
        message = (state.incoming_message or "").lower()
        
        # Check for immediate STOP keywords
        stop_keywords = ['stop', 'unsubscribe', 'quit', 'end', 'opt out', 'opt-out']
        immediate_stop = any(keyword in message for keyword in stop_keywords)
        
        # Check for language preferences
        language_pref = None
        if any(word in message for word in ['english', 'en']):
            language_pref = "en"
        elif any(word in message for word in ['swahili', 'kiswahili', 'sw']):
            language_pref = "sw"
        elif any(word in message for word in ['sheng']):
            language_pref = "sheng"
        elif any(word in message for word in ['mixed', 'both', 'any language']):
            language_pref = "mixed"
        
        # Check for marketing preferences
        marketing_opt_in = None
        if immediate_stop or any(word in message for word in ['no marketing', 'no promotions', 'stop marketing']):
            marketing_opt_in = False
        elif any(word in message for word in ['yes to offers', 'send promotions', 'marketing ok']):
            marketing_opt_in = True
        
        # Determine intent
        if immediate_stop:
            parsed_intent = "stop_all"
        elif marketing_opt_in is False:
            parsed_intent = "marketing_opt_out"
        elif marketing_opt_in is True:
            parsed_intent = "marketing_opt_in"
        elif language_pref:
            parsed_intent = "language_change"
        else:
            parsed_intent = "general_inquiry"
        
        has_preferences = immediate_stop or language_pref is not None or marketing_opt_in is not None
        
        return {
            "has_preferences": has_preferences,
            "language_preference": language_pref,
            "marketing_opt_in": marketing_opt_in,
            "notification_preferences": {
                "marketing": marketing_opt_in,
                "notifications": None,
                "important_only": None
            },
            "immediate_stop": immediate_stop,
            "parsed_intent": parsed_intent,
            "confidence": 0.6 if has_preferences else 0.3,
            "notes": f"Heuristic parsing detected: {parsed_intent}"
        }
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update conversation state with preference parsing results.
        
        Args:
            state: Current conversation state
            result: LLM result with preference parsing
            
        Returns:
            Updated conversation state
        """
        # Store parsing results in state for next step
        state.metadata = getattr(state, 'metadata', {})
        state.metadata['preference_parsing'] = result
        
        # Update step
        state.prefs_step = "update_preferences"
        
        # Log successful parsing
        logger.info(
            f"Preference parsing completed - tenant: {state.tenant_id}, "
            f"conversation: {state.conversation_id}, has_preferences: {result.get('has_preferences')}, "
            f"immediate_stop: {result.get('immediate_stop')}"
        )
        
        return state
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle preference parsing errors with heuristic fallback.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with heuristic fallback result
        """
        logger.error(
            f"Preference parsing LLM failed, using heuristic fallback: {str(error)} - "
            f"tenant: {state.tenant_id}, conversation: {state.conversation_id}"
        )
        
        # Use heuristic fallback instead of escalation
        result = self._get_heuristic_fallback(state)
        return self._update_state_from_llm_result(state, result)


class PrefsConsentResponseNode(LLMNode):
    """
    Preferences and consent response node for generating confirmation messages.
    
    Creates appropriate confirmation messages after preference updates
    with clear communication about changes made.
    """
    
    def __init__(self):
        """Initialize preferences consent response node."""
        system_prompt = """You are a customer service assistant that generates confirmation messages for preference and consent updates.

RESPONSE GUIDELINES:
- Acknowledge the specific changes made clearly and concisely
- Use warm, professional tone appropriate for WhatsApp
- Confirm what was updated and what it means for the customer
- For STOP/UNSUBSCRIBE: Confirm immediate action and provide re-opt-in instructions
- For language changes: Confirm new language preference
- For marketing changes: Clearly state marketing consent status
- Keep responses brief but complete (2-3 sentences max)
- Use the customer's preferred language when possible

RESPONSE PATTERNS:
- Language change: "I've updated your language preference to [language]. All future messages will be in [language]."
- Marketing opt-out: "You've been unsubscribed from marketing messages. You'll only receive order updates and important notifications. Reply 'MARKETING OK' to re-subscribe anytime."
- Marketing opt-in: "You're now subscribed to receive our latest offers and promotions. Reply 'STOP' anytime to unsubscribe."
- Multiple changes: Acknowledge all changes made
- No changes: "I understand you're asking about preferences. What would you like to update?"

TONE MATCHING:
- Match the tenant's tone_style (friendly_concise, professional, casual)
- Use bot_name when appropriate
- Keep language natural and conversational

You respond with natural language text only. No JSON or structured output."""
        
        super().__init__("prefs_consent_response", system_prompt)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for preference response generation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        # Get preference parsing results
        parsing_result = getattr(state, 'metadata', {}).get('preference_parsing', {})
        update_result = getattr(state, 'metadata', {}).get('preference_update', {})
        
        context_parts = [
            f"Customer message: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Tone style: {state.tone_style}",
            f"Response language: {state.response_language}"
        ]
        
        # Add parsing results
        if parsing_result:
            context_parts.append(f"Detected preferences: {json.dumps(parsing_result, indent=2)}")
        
        # Add update results
        if update_result:
            context_parts.append(f"Update results: {json.dumps(update_result, indent=2)}")
        
        # Add current customer preferences for context
        context_parts.extend([
            f"Current language preference: {state.customer_language_pref or 'not set'}",
            f"Current marketing opt-in: {state.marketing_opt_in}",
            f"Current notification preferences: {state.notification_prefs}"
        ])
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for preference response generation.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Response generation result
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)
            
            # Check budget first
            if not llm_router._check_budget():
                return self._get_heuristic_fallback(state)
            
            # Get provider for text generation
            provider_name, model_name = llm_router._select_model('response_generation')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make LLM call for text generation
            response = provider.generate(
                messages=messages,
                model=model_name,
                temperature=0.3,  # Slightly higher for natural responses
                max_tokens=200
            )
            
            return {"response_text": response.content.strip()}
                
        except Exception as e:
            logger.error(f"LLM call failed for preference response: {str(e)}")
            return self._get_heuristic_fallback(state)
    
    def _get_heuristic_fallback(self, state: ConversationState) -> Dict[str, Any]:
        """
        Heuristic fallback for preference response when LLM fails.
        
        Args:
            state: Current conversation state
            
        Returns:
            Fallback response
        """
        parsing_result = getattr(state, 'metadata', {}).get('preference_parsing', {})
        update_result = getattr(state, 'metadata', {}).get('preference_update', {})
        
        # Generate appropriate fallback response
        if parsing_result.get('immediate_stop'):
            response_text = "You've been unsubscribed from marketing messages. You'll only receive order updates and important notifications. Reply 'MARKETING OK' to re-subscribe anytime."
        elif parsing_result.get('marketing_opt_in') is False:
            response_text = "I've updated your marketing preferences. You won't receive promotional messages anymore."
        elif parsing_result.get('marketing_opt_in') is True:
            response_text = "You're now subscribed to receive our latest offers and promotions. Reply 'STOP' anytime to unsubscribe."
        elif parsing_result.get('language_preference'):
            lang = parsing_result.get('language_preference')
            lang_name = {"en": "English", "sw": "Swahili", "sheng": "Sheng", "mixed": "mixed languages"}.get(lang, lang)
            response_text = f"I've updated your language preference to {lang_name}. All future messages will be in {lang_name}."
        elif update_result.get('success'):
            response_text = "Your preferences have been updated successfully."
        else:
            response_text = "I understand you're asking about preferences. What would you like to update? You can change your language, marketing preferences, or notification settings."
        
        return {"response_text": response_text}
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update conversation state with response text.
        
        Args:
            state: Current conversation state
            result: LLM result with response text
            
        Returns:
            Updated conversation state
        """
        # Set response text
        state.response_text = result.get("response_text", "Your preferences have been updated.")
        
        # Mark journey as complete
        state.prefs_step = "complete"
        
        # Log successful response generation
        logger.info(
            f"Preference response generated - tenant: {state.tenant_id}, "
            f"conversation: {state.conversation_id}, response_length: {len(state.response_text)}"
        )
        
        return state
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle preference response errors with heuristic fallback.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with heuristic fallback result
        """
        logger.error(
            f"Preference response LLM failed, using heuristic fallback: {str(error)} - "
            f"tenant: {state.tenant_id}, conversation: {state.conversation_id}"
        )
        
        # Use heuristic fallback instead of escalation
        result = self._get_heuristic_fallback(state)
        return self._update_state_from_llm_result(state, result)

class PreferencesJourneySubgraph:
    """
    Preferences and Consent Journey subgraph orchestrator.
    
    Manages the complete preferences journey workflow:
    1. Parse preferences from user message
    2. Update customer preferences via tool
    3. Generate confirmation response
    4. Handle immediate STOP/UNSUBSCRIBE processing
    """
    
    def __init__(self):
        """Initialize preferences journey subgraph."""
        self.preference_parsing_node = PreferenceParsingNode()
        self.prefs_consent_response_node = PrefsConsentResponseNode()
        self.logger = logging.getLogger(__name__)
    
    async def execute_step(self, state: ConversationState) -> ConversationState:
        """
        Execute the current step in the preferences journey.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        current_step = getattr(state, 'prefs_step', 'parse_preferences')
        
        try:
            if current_step == 'parse_preferences':
                return await self._parse_preferences_step(state)
            elif current_step == 'update_preferences':
                return await self._update_preferences_step(state)
            elif current_step == 'generate_response':
                return await self._generate_response_step(state)
            elif current_step == 'complete':
                return state  # Journey complete
            else:
                # Unknown step, start from beginning
                state.prefs_step = 'parse_preferences'
                return await self._parse_preferences_step(state)
                
        except Exception as e:
            self.logger.error(
                f"Error in preferences journey step {current_step}: {str(e)} - "
                f"tenant: {state.tenant_id}, conversation: {state.conversation_id}"
            )
            
            # Set error response and complete journey
            state.response_text = "I'm having trouble updating your preferences right now. Please try again later or contact support."
            state.prefs_step = 'complete'
            state.escalation_required = True
            state.escalation_reason = f"Preferences journey error in step {current_step}: {str(e)}"
            
            return state
    
    async def _parse_preferences_step(self, state: ConversationState) -> ConversationState:
        """
        Execute preference parsing step.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        self.logger.info(
            f"Executing preference parsing step - tenant: {state.tenant_id}, "
            f"conversation: {state.conversation_id}"
        )
        
        # Execute preference parsing node
        state = await self.preference_parsing_node.execute(state)
        
        return state
    
    async def _update_preferences_step(self, state: ConversationState) -> ConversationState:
        """
        Execute preference update step using customer_update_preferences tool.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        self.logger.info(
            f"Executing preference update step - tenant: {state.tenant_id}, "
            f"conversation: {state.conversation_id}"
        )
        
        # Get parsing results
        parsing_result = getattr(state, 'metadata', {}).get('preference_parsing', {})
        
        if not parsing_result.get('has_preferences'):
            # No preferences to update, go to response
            state.prefs_step = 'generate_response'
            return state
        
        # Prepare tool parameters
        tool_params = {
            "tenant_id": state.tenant_id,
            "request_id": state.request_id,
            "conversation_id": state.conversation_id,
            "customer_id": state.customer_id
        }
        
        # Add language preference if detected
        if parsing_result.get('language_preference'):
            tool_params["language_preference"] = parsing_result['language_preference']
        
        # Add marketing opt-in if detected
        if parsing_result.get('marketing_opt_in') is not None:
            tool_params["marketing_opt_in"] = parsing_result['marketing_opt_in']
        
        # Add consent flags if detected
        notification_prefs = parsing_result.get('notification_preferences', {})
        if any(v is not None for v in notification_prefs.values()):
            consent_flags = {}
            if notification_prefs.get('marketing') is not None:
                consent_flags['marketing'] = notification_prefs['marketing']
            if notification_prefs.get('notifications') is not None:
                consent_flags['notifications'] = notification_prefs['notifications']
            if notification_prefs.get('important_only') is not None:
                consent_flags['important_only'] = notification_prefs['important_only']
            
            if consent_flags:
                tool_params["consent_flags"] = consent_flags
        
        try:
            # Execute customer_update_preferences tool
            tool = get_tool("customer_update_preferences")
            if not tool:
                raise Exception("customer_update_preferences tool not found")
            
            # Use sync_to_async to call synchronous tool from async context
            from asgiref.sync import sync_to_async
            result = await sync_to_async(tool.execute)(**tool_params)
            
            # Store update result in state
            state.metadata = getattr(state, 'metadata', {})
            state.metadata['preference_update'] = {
                "success": result.success,
                "data": result.data if result.success else None,
                "error": result.error if not result.success else None,
                "updated_fields": result.data.get('updated_fields', []) if result.success else []
            }
            
            # Update state with new preferences if successful
            if result.success and result.data:
                if 'language_preference' in result.data:
                    state.customer_language_pref = result.data['language_preference']
                if 'marketing_opt_in' in result.data:
                    state.marketing_opt_in = result.data['marketing_opt_in']
                if 'consent_flags' in result.data:
                    state.notification_prefs = result.data['consent_flags']
            
            # Move to response generation
            state.prefs_step = 'generate_response'
            
            self.logger.info(
                f"Preference update completed - tenant: {state.tenant_id}, "
                f"conversation: {state.conversation_id}, success: {result.success}, "
                f"updated_fields: {result.data.get('updated_fields', []) if result.success else []}"
            )
            
        except Exception as e:
            self.logger.error(
                f"Failed to update preferences: {str(e)} - tenant: {state.tenant_id}, "
                f"conversation: {state.conversation_id}"
            )
            
            # Store error in metadata
            state.metadata = getattr(state, 'metadata', {})
            state.metadata['preference_update'] = {
                "success": False,
                "error": str(e),
                "updated_fields": []
            }
            
            # Still move to response generation to inform user
            state.prefs_step = 'generate_response'
        
        return state
    
    async def _generate_response_step(self, state: ConversationState) -> ConversationState:
        """
        Execute response generation step.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        self.logger.info(
            f"Executing preference response generation step - tenant: {state.tenant_id}, "
            f"conversation: {state.conversation_id}"
        )
        
        # Execute response generation node
        state = await self.prefs_consent_response_node.execute(state)
        
        return state


# Export the subgraph for use in main orchestrator
def create_preferences_journey_subgraph():
    """
    Create and return the preferences journey subgraph.
    
    Returns:
        PreferencesJourneySubgraph instance
    """
    return PreferencesJourneySubgraph()


# Journey entry point for LangGraph orchestrator
async def preferences_journey_entry(state: ConversationState) -> ConversationState:
    """
    Entry point for preferences journey subgraph.
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated conversation state
    """
    # Initialize preferences journey
    state.journey = "prefs"
    state.prefs_step = "parse_preferences"
    
    # Create and execute subgraph
    subgraph = PreferencesJourneySubgraph()
    
    # Execute steps until complete
    while getattr(state, 'prefs_step', 'complete') != 'complete':
        state = await subgraph.execute_step(state)
        
        # Safety check to prevent infinite loops
        if state.turn_count > 10:
            logger.warning(
                f"Preferences journey exceeded turn limit - tenant: {state.tenant_id}, "
                f"conversation: {state.conversation_id}"
            )
            state.response_text = "I'm having trouble processing your preferences. Please contact support."
            state.escalation_required = True
            state.escalation_reason = "Preferences journey exceeded turn limit"
            break
    
    return state