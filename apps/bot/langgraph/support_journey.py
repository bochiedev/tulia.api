"""
Support Journey subgraph implementation for LangGraph orchestration.

This module implements the complete support journey workflow with RAG-based
answers from tenant knowledge base and escalation to human support when needed.
"""
import logging
from typing import Dict, Any, Optional, List
import json

from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.nodes import LLMNode
from apps.bot.services.llm_router import LLMRouter
from apps.bot.tools.registry import get_tool

logger = logging.getLogger(__name__)


class SupportRagAnswerNode(LLMNode):
    """
    Support RAG answer node with strict grounding.
    
    Provides answers using only retrieved knowledge base snippets with
    escalation logic when information is insufficient.
    """
    
    def __init__(self):
        """Initialize support RAG answer node."""
        system_prompt = """You are a customer support assistant that provides answers using ONLY the retrieved knowledge base information.

STRICT GROUNDING RULES:
- You MUST only use information from the provided knowledge base snippets
- You MUST NOT invent, assume, or hallucinate any information
- If the knowledge base doesn't contain sufficient information, you MUST indicate escalation is needed
- You MUST cite which knowledge base sections you're using
- You MUST be helpful but accurate

RESPONSE GUIDELINES:
- Provide clear, helpful answers when knowledge base has sufficient information
- Use natural, conversational language appropriate for WhatsApp
- Keep responses concise but complete
- Include relevant details from knowledge base snippets
- If multiple snippets are relevant, synthesize them coherently

ESCALATION TRIGGERS:
- Knowledge base doesn't contain answer to the specific question
- Information is incomplete or unclear
- Question requires real-time data not in knowledge base
- Technical issues beyond documented solutions
- Policy questions not covered in documentation

RESPONSE FORMAT:
- Direct answer when knowledge base is sufficient
- "I need to connect you with our support team for this specific question" when escalation needed
- Always be honest about limitations

You respond with natural language text only. No JSON or structured output."""
        
        super().__init__("support_rag_answer", system_prompt)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for support RAG answer generation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer question: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Support Assistant'}",
            f"Tenant: {state.tenant_name or 'Customer Support'}"
        ]
        
        # Add knowledge base snippets
        if state.kb_snippets:
            context_parts.append("\nKNOWLEDGE BASE INFORMATION:")
            for i, snippet in enumerate(state.kb_snippets, 1):
                source = snippet.get('source', 'Unknown')
                content = snippet.get('content', '')
                score = snippet.get('score', 0.0)
                
                context_parts.append(f"\nSnippet {i} (from {source}, relevance: {score:.2f}):")
                context_parts.append(content)
        else:
            context_parts.append("\nKNOWLEDGE BASE INFORMATION: No relevant information found")
        
        # Add conversation context if available
        if state.turn_count > 1:
            context_parts.append(f"\nConversation context: This is turn {state.turn_count}")
            if state.intent:
                context_parts.append(f"Customer intent: {state.intent}")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for support RAG answer generation.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Support answer result
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)

            await llm_router._ensure_config_loaded()

            await llm_router._ensure_config_loaded()
            
            # Check budget first
            if not llm_router._check_budget():
                return {
                    "answer": "I'm experiencing technical difficulties. Let me connect you with our support team who can help you directly.",
                    "needs_escalation": True,
                    "escalation_reason": "Budget exceeded"
                }
            
            # Get provider for text generation
            provider_name, model_name = llm_router._select_model('support_rag')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make LLM call for natural language response
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=300,
                temperature=0.2  # Low temperature for factual responses
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'support_rag', response.input_tokens)
            
            # Analyze response for escalation needs
            answer_text = response.content.strip()
            needs_escalation = self._analyze_escalation_need(answer_text, state)
            
            return {
                "answer": answer_text,
                "needs_escalation": needs_escalation,
                "escalation_reason": "Insufficient knowledge base information" if needs_escalation else None
            }
            
        except Exception as e:
            logger.error(
                f"Support RAG answer LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to escalation
            return {
                "answer": "I'm having trouble accessing our knowledge base right now. Let me connect you with our support team who can help you directly.",
                "needs_escalation": True,
                "escalation_reason": f"LLM error: {str(e)[:100]}"
            }
    
    def _analyze_escalation_need(self, answer_text: str, state: ConversationState) -> bool:
        """
        Analyze if the answer indicates escalation is needed.
        
        Args:
            answer_text: Generated answer text
            state: Current conversation state
            
        Returns:
            True if escalation is needed
        """
        # Check for explicit escalation phrases
        escalation_phrases = [
            "connect you with our support team",
            "need to escalate",
            "contact our support",
            "speak with someone",
            "I don't have enough information",
            "not in our knowledge base",
            "unable to find",
            "need more details",
            "requires human assistance"
        ]
        
        answer_lower = answer_text.lower()
        for phrase in escalation_phrases:
            if phrase in answer_lower:
                return True
        
        # Check if knowledge base was empty or insufficient
        if not state.kb_snippets:
            return True
        
        # Check if all snippets have low relevance scores
        if state.kb_snippets:
            max_score = max(snippet.get('score', 0.0) for snippet in state.kb_snippets)
            if max_score < 0.5:  # Low relevance threshold
                return True
        
        # Check for very short answers that might indicate insufficient info
        if len(answer_text.strip()) < 50:
            return True
        
        return False
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from support RAG answer result.
        
        Args:
            state: Current conversation state
            result: LLM result dictionary
            
        Returns:
            Updated conversation state
        """
        answer = result.get("answer", "")
        needs_escalation = result.get("needs_escalation", False)
        escalation_reason = result.get("escalation_reason")
        
        # Set response text
        state.response_text = answer
        
        # Set escalation if needed
        if needs_escalation:
            state.set_escalation(escalation_reason or "Support question requires human assistance")
            state.support_step = 'escalation_needed'
        else:
            state.support_step = 'answered'
        
        logger.info(
            f"Support RAG answer generated: escalation_needed={needs_escalation}",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "needs_escalation": needs_escalation,
                "escalation_reason": escalation_reason,
                "kb_snippets_count": len(state.kb_snippets) if state.kb_snippets else 0,
                "answer_length": len(answer),
                "support_step": state.support_step
            }
        )
        
        return state


class HandoffMessageNode(LLMNode):
    """
    Handoff message node for escalation communication.
    
    Creates appropriate messages when escalating to human support
    with expected timelines and context using the enhanced escalation service.
    """
    
    def __init__(self):
        """Initialize handoff message node."""
        system_prompt = """You are a customer service assistant creating handoff messages for human escalation.

Your role is to inform customers that their question is being escalated to human support with appropriate expectations and reassurance.

MESSAGE GUIDELINES:
- Be warm, professional, and reassuring
- Acknowledge their question/concern specifically
- Explain that a human agent will help them
- Provide realistic timeline expectations based on priority
- Include any relevant context about their inquiry
- Keep the tone consistent with the bot's personality
- Use language appropriate for WhatsApp messaging
- Include reference number for tracking

ESCALATION REASONS & MESSAGING:
- explicit_request: "I'm connecting you with one of our human agents right away."
- payment_dispute: "I understand your concern about this payment issue. Let me connect you with our billing specialist."
- sensitive_content: "I'm connecting you with a specialist who can better assist you with this matter."
- user_frustration: "I apologize for the difficulty you're experiencing. Let me connect you with someone who can provide more personalized assistance."
- repeated_failures: "I'm having trouble processing your request. Let me connect you with our technical support team."
- missing_information: "I need to get more specific information for you. Let me connect you with someone who has access to additional resources."

PRIORITY-BASED TIMELINES:
- urgent: "15 minutes"
- high: "1 hour" 
- medium: "4 hours"
- low: "24 hours"

TONE GUIDELINES:
- Professional but friendly
- Confident and reassuring
- Apologetic if there was a system issue
- Grateful for their patience
- Clear about next steps

AVOID:
- Overly technical explanations
- Exact time commitments beyond the standard timelines
- Apologizing excessively
- Making the customer feel like a burden
- Long explanations about why escalation is needed

You respond with natural language text only. No JSON or structured output."""
        
        super().__init__("handoff_message", system_prompt)
    
    def _prepare_llm_input(self, state: ConversationState) -> str:
        """
        Prepare input for handoff message generation with enhanced context.
        
        Args:
            state: Current conversation state
            
        Returns:
            Formatted input for LLM
        """
        context_parts = [
            f"Customer question: {state.incoming_message}",
            f"Bot name: {state.bot_name or 'Assistant'}",
            f"Escalation reason: {state.escalation_reason or 'Requires human assistance'}",
            f"Conversation turn: {state.turn_count}"
        ]
        
        # Add priority and category if available from escalation metadata
        if hasattr(state, 'escalation_priority'):
            context_parts.append(f"Priority: {state.escalation_priority}")
        
        if hasattr(state, 'escalation_category'):
            context_parts.append(f"Category: {state.escalation_category}")
        
        # Add context about the type of inquiry
        if state.intent:
            context_parts.append(f"Question type: {state.intent}")
        
        # Add any relevant conversation context
        if state.last_catalog_query:
            context_parts.append(f"They were asking about: {state.last_catalog_query}")
        
        if state.order_id:
            context_parts.append(f"Related to order: {state.order_id}")
        
        if state.payment_request_id:
            context_parts.append(f"Related to payment: {state.payment_request_id}")
        
        # Add ticket information if available
        if state.handoff_ticket_id:
            context_parts.append(f"Ticket ID: {state.handoff_ticket_id}")
        
        # Add urgency indicators
        urgency_keywords = ['urgent', 'emergency', 'asap', 'immediately', 'broken', 'not working', 'failed']
        message_lower = (state.incoming_message or "").lower()
        if any(keyword in message_lower for keyword in urgency_keywords):
            context_parts.append("URGENCY: Customer indicates this is urgent")
        
        # Add failure context if available
        if hasattr(state, 'consecutive_tool_errors') and state.consecutive_tool_errors > 0:
            context_parts.append(f"System had {state.consecutive_tool_errors} consecutive errors")
        
        return "\n".join(context_parts)
    
    async def _call_llm(self, input_text: str, state: ConversationState) -> Dict[str, Any]:
        """
        Call LLM for handoff message generation.
        
        Args:
            input_text: Formatted input text
            state: Current conversation state
            
        Returns:
            Handoff message result
        """
        try:
            # Get tenant for LLM router
            from apps.tenants.models import Tenant
            tenant = await Tenant.objects.aget(id=state.tenant_id)
            
            # Create LLM router for tenant
            llm_router = LLMRouter(tenant)

            await llm_router._ensure_config_loaded()

            await llm_router._ensure_config_loaded()
            
            # Check budget first
            if not llm_router._check_budget():
                # Fallback to template message
                return {
                    "message": f"Thanks for your question! I've connected you with our support team who will help you shortly. They'll have all the context from our conversation."
                }
            
            # Get provider for text generation
            provider_name, model_name = llm_router._select_model('handoff_message')
            provider = llm_router._get_provider(provider_name)
            
            # Prepare messages for LLM call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # Make LLM call for natural language response
            response = provider.generate(
                messages=messages,
                model=model_name,
                max_tokens=200,
                temperature=0.3  # Slightly creative for natural messaging
            )
            
            # Log usage
            llm_router._log_usage(provider_name, model_name, 'handoff_message', response.input_tokens)
            
            return {
                "message": response.content.strip()
            }
            
        except Exception as e:
            logger.error(
                f"Handoff message LLM call failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id
                },
                exc_info=True
            )
            
            # Fallback to template message
            bot_name = state.bot_name or "our team"
            return {
                "message": f"I've connected you with our support team who will help you with your question. They'll be in touch shortly with all the context from our conversation."
            }
    
    def _update_state_from_llm_result(self, state: ConversationState, result: Dict[str, Any]) -> ConversationState:
        """
        Update state from handoff message result.
        
        Args:
            state: Current conversation state
            result: LLM result dictionary
            
        Returns:
            Updated conversation state
        """
        message = result.get("message", "")
        
        # Set response text
        state.response_text = message
        state.support_step = 'handoff_complete'
        
        logger.info(
            f"Handoff message generated",
            extra={
                "tenant_id": state.tenant_id,
                "conversation_id": state.conversation_id,
                "request_id": state.request_id,
                "escalation_reason": state.escalation_reason,
                "handoff_ticket_id": state.handoff_ticket_id,
                "message_length": len(message)
            }
        )
        
        return state
    
    def _handle_error(self, state: ConversationState, error: Exception) -> ConversationState:
        """
        Handle handoff message node errors with fallback message.
        
        Args:
            state: Current conversation state
            error: Exception that occurred
            
        Returns:
            Updated state with fallback message
        """
        # Call parent error handling first
        state = super()._handle_error(state, error)
        
        # Provide fallback handoff message
        bot_name = state.bot_name or "our team"
        state.response_text = f"I've connected you with our support team who will help you with your question. They'll be in touch shortly with all the context from our conversation."
        state.support_step = 'handoff_complete'
        
        return state


class SupportJourneySubgraph:
    """
    Support Journey subgraph implementation.
    
    Orchestrates the complete support workflow with RAG-based answers
    and escalation to human support when needed.
    
    Flow:
    1. kb_retrieve tool - Get relevant knowledge base snippets
    2. support_rag_answer LLM - Generate grounded answer or determine escalation
    3. If escalation needed:
       a. handoff_create_ticket tool - Create support ticket
       b. handoff_message LLM - Generate escalation message
    4. Return response to customer
    """
    
    def __init__(self):
        """Initialize support journey subgraph."""
        self.logger = logging.getLogger(__name__)
    
    async def execute_support_journey(self, state: ConversationState) -> ConversationState:
        """
        Execute the complete support journey workflow.
        
        Implements the support journey flow:
        1. kb_retrieve tool integration with tenant-scoped vector search
        2. support_rag_answer LLM node with strict grounding
        3. Escalation logic when information is insufficient
        4. handoff_create_ticket tool for human escalation
        5. handoff_message LLM node for escalation communication
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated conversation state
        """
        try:
            # Determine current step in support journey
            current_step = getattr(state, 'support_step', 'start')
            
            self.logger.info(
                f"Executing support journey step: {current_step}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "support_step": current_step,
                    "turn_count": state.turn_count
                }
            )
            
            if current_step == 'start':
                return await self._step_retrieve_knowledge(state)
            elif current_step == 'knowledge_retrieved':
                return await self._step_generate_answer(state)
            elif current_step == 'escalation_needed':
                return await self._step_create_handoff_ticket(state)
            elif current_step == 'ticket_created':
                return await self._step_generate_handoff_message(state)
            elif current_step in ['answered', 'handoff_complete']:
                # Journey complete
                return state
            else:
                # Default to knowledge retrieval for unknown steps
                return await self._step_retrieve_knowledge(state)
                
        except Exception as e:
            self.logger.error(
                f"Support journey execution failed: {e}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "support_step": getattr(state, 'support_step', 'unknown')
                },
                exc_info=True
            )
            
            # Set error response and escalation
            state.response_text = "I'm having trouble accessing our support information. Let me connect you with our support team who can help you directly."
            state.set_escalation("Support journey execution error")
            return state
    
    async def _step_retrieve_knowledge(self, state: ConversationState) -> ConversationState:
        """Execute knowledge base retrieval step."""
        # Get kb_retrieve tool
        kb_retrieve_tool = get_tool("kb_retrieve")
        if not kb_retrieve_tool:
            # Tool not available - escalate immediately
            state.response_text = "I'm having trouble accessing our knowledge base. Let me connect you with our support team."
            state.set_escalation("kb_retrieve tool not available")
            state.support_step = 'escalation_needed'
            return await self._step_create_handoff_ticket(state)
        
        # Prepare retrieval parameters
        retrieval_params = {
            "tenant_id": state.tenant_id,
            "request_id": state.request_id,
            "conversation_id": state.conversation_id,
            "query": state.incoming_message or "support question",
            "limit": 8,  # Get top 8 most relevant snippets
            "min_score": 0.3  # Minimum relevance threshold
        }
        
        # Execute knowledge retrieval
        retrieval_result = kb_retrieve_tool.execute(**retrieval_params)
        
        if retrieval_result.success:
            # Update state with retrieved snippets
            data = retrieval_result.data
            state.kb_snippets = data.get("snippets", [])
            
            self.logger.info(
                f"Knowledge retrieved: {len(state.kb_snippets)} snippets",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "snippets_count": len(state.kb_snippets),
                    "query": retrieval_params["query"]
                }
            )
            
            # Proceed to answer generation
            state.support_step = 'knowledge_retrieved'
            return await self._step_generate_answer(state)
        else:
            # Retrieval failed - escalate
            self.logger.warning(
                f"Knowledge retrieval failed: {retrieval_result.error}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "error": retrieval_result.error
                }
            )
            
            state.response_text = "I'm having trouble accessing our knowledge base right now. Let me connect you with our support team."
            state.set_escalation(f"Knowledge retrieval failed: {retrieval_result.error}")
            state.support_step = 'escalation_needed'
            return await self._step_create_handoff_ticket(state)
    
    async def _step_generate_answer(self, state: ConversationState) -> ConversationState:
        """Execute support RAG answer generation step."""
        # Create and execute support RAG answer node
        rag_answer_node = SupportRagAnswerNode()
        updated_state = await rag_answer_node.execute(state)
        
        # Check if escalation is needed
        if getattr(updated_state, 'support_step', '') == 'escalation_needed':
            # Proceed to handoff ticket creation
            return await self._step_create_handoff_ticket(updated_state)
        else:
            # Answer provided - journey complete
            return updated_state
    
    async def _step_create_handoff_ticket(self, state: ConversationState) -> ConversationState:
        """Execute handoff ticket creation step."""
        # Get handoff_create_ticket tool
        handoff_tool = get_tool("handoff_create_ticket")
        if not handoff_tool:
            # Tool not available - provide fallback message
            state.response_text = "I've noted your question and our support team will be in touch with you shortly. Thank you for your patience."
            state.support_step = 'handoff_complete'
            return state
        
        # Prepare handoff parameters
        handoff_params = {
            "tenant_id": state.tenant_id,
            "request_id": state.request_id,
            "conversation_id": state.conversation_id,
            "customer_id": state.customer_id,
            "reason": state.escalation_reason or "Support question requires human assistance",
            "context": {
                "customer_question": state.incoming_message,
                "intent": state.intent,
                "journey": state.journey,
                "step": "support_rag_escalation",
                "kb_snippets_found": len(state.kb_snippets) if state.kb_snippets else 0,
                "turn_count": state.turn_count
            }
        }
        
        # Execute handoff ticket creation
        handoff_result = handoff_tool.execute(**handoff_params)
        
        if handoff_result.success:
            # Update state with ticket information
            data = handoff_result.data
            state.handoff_ticket_id = data.get("ticket_id")
            
            self.logger.info(
                f"Handoff ticket created: {state.handoff_ticket_id}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "ticket_id": state.handoff_ticket_id,
                    "escalation_reason": state.escalation_reason
                }
            )
            
            # Proceed to handoff message generation
            state.support_step = 'ticket_created'
            return await self._step_generate_handoff_message(state)
        else:
            # Ticket creation failed - provide fallback message
            self.logger.warning(
                f"Handoff ticket creation failed: {handoff_result.error}",
                extra={
                    "tenant_id": state.tenant_id,
                    "conversation_id": state.conversation_id,
                    "request_id": state.request_id,
                    "error": handoff_result.error
                }
            )
            
            state.response_text = "I've noted your question and our support team will be in touch with you shortly. Thank you for your patience."
            state.support_step = 'handoff_complete'
            return state
    
    async def _step_generate_handoff_message(self, state: ConversationState) -> ConversationState:
        """Execute handoff message generation step."""
        # Create and execute handoff message node
        handoff_message_node = HandoffMessageNode()
        updated_state = await handoff_message_node.execute(state)
        
        # Journey complete
        return updated_state


# Entry point function for orchestrator integration
async def execute_support_journey_node(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute support journey subgraph from orchestrator.
    
    This function serves as the entry point for the support journey
    from the main LangGraph orchestrator.
    
    Args:
        state_dict: State dictionary from orchestrator
        
    Returns:
        Updated state dictionary
    """
    # Convert dict to ConversationState
    conv_state = ConversationState.from_dict(state_dict)
    
    # Execute support journey
    support_journey = SupportJourneySubgraph()
    updated_state = await support_journey.execute_support_journey(conv_state)
    
    # Convert back to dict for orchestrator
    return updated_state.to_dict()