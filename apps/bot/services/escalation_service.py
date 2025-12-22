"""
Escalation Service for Human Handoff Management.

Implements EXACT escalation triggers and context preservation as specified
in the design document for Tulia AI V2.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from django.utils import timezone

from apps.bot.conversation_state import ConversationState
from apps.bot.tools.registry import get_tool

logger = logging.getLogger(__name__)


@dataclass
class EscalationContext:
    """
    Context information for escalation decisions.
    
    Tracks conversation history, failures, and context needed for
    human handoff with complete information preservation.
    """
    # Failure tracking
    consecutive_tool_errors: int = 0
    clarification_loops: int = 0
    failed_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    # Context preservation
    conversation_summary: str = ""
    current_journey: str = "unknown"
    current_step: str = "unknown"
    related_order_id: Optional[str] = None
    related_product_ids: List[str] = field(default_factory=list)
    
    # Escalation metadata
    escalation_triggers: List[str] = field(default_factory=list)
    escalation_priority: str = "medium"
    escalation_category: str = "general_inquiry"
    
    # Timing information
    conversation_start_time: Optional[datetime] = None
    last_successful_action: Optional[datetime] = None


class EscalationService:
    """
    Service for managing escalation rules and human handoff.
    
    Implements EXACT escalation triggers as specified in the design:
    - User explicitly asks for human ("agent", "human", "call me")
    - Payment disputes ("I paid but..."), chargebacks, refunds, delivery complaints
    - Missing authoritative info after RAG/tool attempts
    - Repeated failures (2 consecutive tool errors OR 3 clarification loops)
    - Sensitive/legal/medical content (tenant policy)
    - User frustration detected + failure to resolve in 2 turns
    """
    
    def __init__(self):
        """Initialize escalation service."""
        self.logger = logging.getLogger(__name__)
    
    def check_escalation_triggers(
        self, 
        state: ConversationState, 
        escalation_context: Optional[EscalationContext] = None
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Check for EXACT escalation triggers that require immediate human handoff.
        
        Returns tuple of (should_escalate, reason, priority, category).
        
        Escalate immediately if ANY is true:
        - User explicitly asks for human ("agent", "human", "call me")
        - Payment disputes ("I paid but..."), chargebacks, refunds, delivery complaints beyond policy
        - Missing authoritative info after RAG/tool attempts (unclear order lookup)
        - Repeated failures (2 consecutive tool errors OR 3 clarification loops)
        - Sensitive/legal/medical content (tenant policy)
        - User frustration detected + failure to resolve in 2 turns
        
        Args:
            state: Current conversation state
            escalation_context: Optional escalation context for failure tracking
            
        Returns:
            Tuple of (should_escalate, reason, priority, category)
        """
        message = (state.incoming_message or "").lower()
        
        # 1. Explicit human request (HIGHEST PRIORITY)
        if self._check_explicit_human_request(message):
            return (
                True, 
                "explicit_request", 
                "high", 
                "general_inquiry"
            )
        
        # 2. Payment disputes and complaints (HIGH PRIORITY)
        if self._check_payment_disputes(message):
            return (
                True, 
                "payment_dispute", 
                "high", 
                "payment_issue"
            )
        
        # 3. Check if escalation is already flagged in state
        if state.escalation_required:
            return (
                True, 
                state.escalation_reason or "escalation_required", 
                "medium", 
                "technical_support"
            )
        
        # 4. Repeated failures (2 consecutive tool errors OR 3 clarification loops)
        if escalation_context:
            if self._check_repeated_failures(escalation_context):
                return (
                    True, 
                    "repeated_failures", 
                    "medium", 
                    "technical_support"
                )
        
        # 5. Sensitive/legal/medical content
        if self._check_sensitive_content(message):
            return (
                True, 
                "sensitive_content", 
                "high", 
                "complaint"
            )
        
        # 6. User frustration with multiple turns
        if self._check_user_frustration(message, state):
            return (
                True, 
                "user_frustration", 
                "medium", 
                "complaint"
            )
        
        # 7. Missing authoritative information after attempts
        if self._check_missing_information(state, escalation_context):
            return (
                True, 
                "missing_information", 
                "medium", 
                "technical_support"
            )
        
        # No escalation triggers found
        return (False, None, None, None)
    
    def _check_explicit_human_request(self, message: str) -> bool:
        """Check for explicit human request keywords."""
        human_keywords = [
            'agent', 'human', 'person', 'call me', 'speak to someone', 
            'representative', 'manager', 'supervisor', 'talk to human',
            'real person', 'customer service', 'support agent', 'live chat',
            'connect me', 'transfer me', 'escalate', 'human help'
        ]
        return any(keyword in message for keyword in human_keywords)
    
    def _check_payment_disputes(self, message: str) -> bool:
        """Check for payment dispute and complaint keywords."""
        payment_dispute_keywords = [
            'i paid but', 'already paid', 'charged twice', 'wrong amount', 'refund',
            'chargeback', 'dispute', 'fraud', 'unauthorized', 'delivery problem',
            'never received', 'damaged', 'broken on arrival', 'wrong item',
            'defective', 'not working', 'poor quality', 'missing parts',
            'late delivery', 'delayed shipment', 'lost package', 'stolen package',
            'return policy', 'warranty claim', 'money back', 'cancel order'
        ]
        return any(keyword in message for keyword in payment_dispute_keywords)
    
    def _check_sensitive_content(self, message: str) -> bool:
        """Check for sensitive/legal/medical content."""
        sensitive_keywords = [
            'legal', 'lawyer', 'attorney', 'court', 'sue', 'lawsuit',
            'medical', 'doctor', 'hospital', 'emergency', 'urgent',
            'death', 'died', 'suicide', 'depression', 'mental health',
            'harassment', 'discrimination', 'abuse', 'threat', 'violence',
            'privacy violation', 'data breach', 'gdpr', 'compliance',
            'regulatory', 'investigation', 'audit', 'subpoena'
        ]
        return any(keyword in message for keyword in sensitive_keywords)
    
    def _check_user_frustration(self, message: str, state: ConversationState) -> bool:
        """Check for user frustration indicators with turn count."""
        frustration_keywords = [
            'frustrated', 'angry', 'upset', 'terrible', 'awful', 'horrible',
            'useless', 'stupid', 'waste of time', 'not helping', 'doesnt work',
            'fed up', 'sick of', 'enough', 'ridiculous', 'pathetic',
            'incompetent', 'worst', 'hate this', 'give up', 'cancel everything'
        ]
        
        has_frustration = any(keyword in message for keyword in frustration_keywords)
        
        # Require multiple turns (2+) with frustration for escalation
        return has_frustration and state.turn_count >= 2
    
    def _check_repeated_failures(self, escalation_context: EscalationContext) -> bool:
        """Check for repeated failures (2 consecutive tool errors OR 3 clarification loops)."""
        return (
            escalation_context.consecutive_tool_errors >= 2 or 
            escalation_context.clarification_loops >= 3
        )
    
    def _check_missing_information(
        self, 
        state: ConversationState, 
        escalation_context: Optional[EscalationContext]
    ) -> bool:
        """Check for missing authoritative information after RAG/tool attempts."""
        # Check if we've attempted RAG but have insufficient information
        if state.kb_snippets and len(state.kb_snippets) == 0:
            return True
        
        # Check if order lookup failed
        if state.journey == "orders" and not state.order_id and state.turn_count >= 2:
            return True
        
        # Check if catalog search returned no results after multiple attempts
        if (state.journey == "sales" and 
            state.last_catalog_results and 
            len(state.last_catalog_results) == 0 and 
            state.turn_count >= 2):
            return True
        
        return False
    
    async def create_handoff_ticket(
        self, 
        state: ConversationState, 
        escalation_context: Optional[EscalationContext] = None
    ) -> Dict[str, Any]:
        """
        Create handoff ticket with comprehensive context preservation.
        
        Args:
            state: Current conversation state
            escalation_context: Optional escalation context
            
        Returns:
            Dictionary with ticket creation result
        """
        try:
            # Get handoff_create_ticket tool
            handoff_tool = get_tool("handoff_create_ticket")
            if not handoff_tool:
                self.logger.error("handoff_create_ticket tool not available")
                return {
                    "success": False,
                    "error": "Handoff tool not available",
                    "fallback_message": "I'm having trouble connecting you with support. Please contact us directly."
                }
            
            # Determine escalation reason, priority, and category
            should_escalate, reason, priority, category = self.check_escalation_triggers(
                state, escalation_context
            )
            
            if not should_escalate:
                reason = "manual_escalation"
                priority = "medium"
                category = "general_inquiry"
            
            # Build comprehensive context
            context = self._build_escalation_context(state, escalation_context)
            
            # Execute handoff tool
            result = handoff_tool.execute(
                tenant_id=state.tenant_id,
                request_id=state.request_id,
                conversation_id=state.conversation_id,
                customer_id=state.customer_id,
                reason=reason,
                priority=priority,
                category=category,
                context=context
            )
            
            if result.success:
                # Update conversation state with ticket information
                state.handoff_ticket_id = result.data.get("ticket_id")
                state.escalation_required = True
                state.escalation_reason = reason
                
                self.logger.info(
                    f"Handoff ticket created successfully: {result.data.get('ticket_number')} "
                    f"for tenant {state.tenant_id}, customer {state.customer_id}"
                )
                
                return {
                    "success": True,
                    "ticket_data": result.data,
                    "escalation_reason": reason,
                    "priority": priority,
                    "category": category
                }
            else:
                self.logger.error(f"Failed to create handoff ticket: {result.error}")
                return {
                    "success": False,
                    "error": result.error,
                    "fallback_message": "I'm having trouble creating your support request. Please contact us directly."
                }
                
        except Exception as e:
            self.logger.error(f"Error creating handoff ticket: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "fallback_message": "I'm experiencing technical difficulties. Please contact our support team directly."
            }
    
    def _build_escalation_context(
        self, 
        state: ConversationState, 
        escalation_context: Optional[EscalationContext]
    ) -> Dict[str, Any]:
        """
        Build comprehensive escalation context for handoff ticket.
        
        Args:
            state: Current conversation state
            escalation_context: Optional escalation context
            
        Returns:
            Dictionary with complete context information
        """
        context = {
            "summary": self._generate_context_summary(state, escalation_context),
            "conversation_history": self._extract_conversation_history(state),
            "current_journey": state.journey,
            "current_step": getattr(state, f"{state.journey}_step", "unknown"),
        }
        
        # Add order information if available
        if state.order_id:
            context["order_id"] = state.order_id
        
        # Add product information if available
        if state.selected_item_ids:
            context["product_ids"] = state.selected_item_ids
        
        # Add cart information if available
        if state.cart:
            context["cart_items"] = [
                {
                    "item_id": item.get("item_id"),
                    "quantity": item.get("qty", 1),
                    "variant": item.get("variant_selection", {})
                }
                for item in state.cart
            ]
        
        # Add payment information if available
        if state.payment_request_id or state.payment_status:
            context["payment_info"] = {
                "payment_request_id": state.payment_request_id,
                "payment_status": state.payment_status
            }
        
        # Add escalation context if available
        if escalation_context:
            context["error_details"] = {
                "consecutive_tool_errors": escalation_context.consecutive_tool_errors,
                "clarification_loops": escalation_context.clarification_loops,
                "failed_tool_calls": escalation_context.failed_tool_calls[-5:],  # Last 5 failures
                "escalation_triggers": escalation_context.escalation_triggers
            }
        
        # Add conversation metrics
        context["conversation_metrics"] = {
            "turn_count": state.turn_count,
            "casual_turns": state.casual_turns,
            "spam_turns": state.spam_turns,
            "intent_confidence": state.intent_confidence,
            "language_confidence": state.language_confidence
        }
        
        return context
    
    def _generate_context_summary(
        self, 
        state: ConversationState, 
        escalation_context: Optional[EscalationContext]
    ) -> str:
        """Generate a brief summary of the escalation context."""
        summary_parts = []
        
        # Add journey context
        if state.journey != "unknown":
            summary_parts.append(f"Customer was in {state.journey} journey")
        
        # Add intent context
        if state.intent != "unknown":
            summary_parts.append(f"with {state.intent} intent (confidence: {state.intent_confidence:.2f})")
        
        # Add escalation reason
        if state.escalation_reason:
            summary_parts.append(f"Escalated due to: {state.escalation_reason}")
        
        # Add failure context
        if escalation_context:
            if escalation_context.consecutive_tool_errors > 0:
                summary_parts.append(f"{escalation_context.consecutive_tool_errors} consecutive tool errors")
            if escalation_context.clarification_loops > 0:
                summary_parts.append(f"{escalation_context.clarification_loops} clarification loops")
        
        # Add order/product context
        if state.order_id:
            summary_parts.append(f"Related to order: {state.order_id}")
        elif state.selected_item_ids:
            summary_parts.append(f"Related to products: {', '.join(state.selected_item_ids[:3])}")
        
        return ". ".join(summary_parts) if summary_parts else "Customer requested human assistance"
    
    def _extract_conversation_history(self, state: ConversationState) -> List[Dict[str, Any]]:
        """Extract recent conversation history for context."""
        # This is a simplified implementation
        # In a full implementation, this would extract actual message history
        history = []
        
        if hasattr(state, 'incoming_message') and state.incoming_message:
            history.append({
                "timestamp": timezone.now().isoformat(),
                "role": "user",
                "message": state.incoming_message
            })
        
        if state.response_text:
            history.append({
                "timestamp": timezone.now().isoformat(),
                "role": "assistant", 
                "message": state.response_text
            })
        
        return history
    
    def generate_handoff_message(
        self, 
        ticket_data: Dict[str, Any], 
        escalation_reason: str,
        priority: str
    ) -> str:
        """
        Generate handoff message with expected timelines.
        
        Args:
            ticket_data: Ticket creation result data
            escalation_reason: Reason for escalation
            priority: Ticket priority
            
        Returns:
            Formatted handoff message with timeline expectations
        """
        # Get expected response time based on priority
        response_times = {
            "urgent": "15 minutes",
            "high": "1 hour",
            "medium": "4 hours", 
            "low": "24 hours"
        }
        
        expected_time = response_times.get(priority, "4 hours")
        ticket_number = ticket_data.get("ticket_number", "N/A")
        
        # Generate message based on escalation reason
        if escalation_reason == "explicit_request":
            message = "I'm connecting you with one of our human agents right away."
        elif escalation_reason == "payment_dispute":
            message = "I understand your concern about this payment issue. Let me connect you with our billing specialist who can help resolve this."
        elif escalation_reason == "sensitive_content":
            message = "I'm connecting you with a specialist who can better assist you with this matter."
        elif escalation_reason == "user_frustration":
            message = "I apologize for the difficulty you're experiencing. Let me connect you with someone who can provide more personalized assistance."
        elif escalation_reason == "repeated_failures":
            message = "I'm having trouble processing your request. Let me connect you with our technical support team."
        elif escalation_reason == "missing_information":
            message = "I need to get more specific information for you. Let me connect you with someone who has access to additional resources."
        else:
            message = "Let me connect you with one of our support specialists who can better assist you."
        
        # Build complete message with timeline and reference
        full_message = f"{message}\n\n"
        full_message += f"📋 Reference: {ticket_number}\n"
        full_message += f"⏱️ Expected response: {expected_time}\n"
        full_message += f"📱 You'll be notified here when an agent responds\n\n"
        
        if priority in ["urgent", "high"]:
            full_message += "This has been marked as high priority and will be addressed quickly."
        else:
            full_message += "Thank you for your patience while we connect you with the right person to help."
        
        return full_message
    
    def track_tool_failure(
        self, 
        escalation_context: EscalationContext, 
        tool_name: str, 
        error_message: str
    ) -> EscalationContext:
        """
        Track tool failure for escalation decision making.
        
        Args:
            escalation_context: Current escalation context
            tool_name: Name of the failed tool
            error_message: Error message from tool failure
            
        Returns:
            Updated escalation context
        """
        # Record the failure
        failure_record = {
            "tool_name": tool_name,
            "error_message": error_message,
            "timestamp": timezone.now().isoformat()
        }
        
        escalation_context.failed_tool_calls.append(failure_record)
        escalation_context.consecutive_tool_errors += 1
        
        # Reset consecutive errors if we have a successful action
        # (This would be called from a separate method when tools succeed)
        
        return escalation_context
    
    def track_clarification_loop(self, escalation_context: EscalationContext) -> EscalationContext:
        """
        Track clarification loop for escalation decision making.
        
        Args:
            escalation_context: Current escalation context
            
        Returns:
            Updated escalation context
        """
        escalation_context.clarification_loops += 1
        return escalation_context
    
    def reset_failure_counters(self, escalation_context: EscalationContext) -> EscalationContext:
        """
        Reset failure counters after successful action.
        
        Args:
            escalation_context: Current escalation context
            
        Returns:
            Updated escalation context
        """
        escalation_context.consecutive_tool_errors = 0
        escalation_context.last_successful_action = timezone.now()
        return escalation_context