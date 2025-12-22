"""
Tests for Support Journey subgraph implementation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.support_journey import (
    SupportRagAnswerNode,
    HandoffMessageNode,
    SupportJourneySubgraph,
    execute_support_journey_node
)
from apps.bot.tools.base import ToolResponse


@pytest.fixture
def sample_state():
    """Create a sample conversation state for testing."""
    return ConversationState(
        tenant_id="test-tenant-123",
        conversation_id="conv-456",
        request_id="req-789",
        customer_id="cust-101",
        phone_e164="+254712345678",
        tenant_name="Test Store",
        bot_name="Support Bot",
        incoming_message="How do I reset my password?",
        intent="support_question",
        intent_confidence=0.8,
        journey="support",
        turn_count=1
    )


class TestSupportRagAnswerNode:
    """Test support RAG answer node."""
    
    @pytest.mark.asyncio
    async def test_rag_answer_with_sufficient_knowledge(self, sample_state):
        """Test RAG answer generation with sufficient knowledge base information."""
        # Set up knowledge base snippets
        sample_state.kb_snippets = [
            {
                "content": "To reset your password, go to Settings > Account > Reset Password and follow the instructions.",
                "source": "user_guide.pdf",
                "score": 0.9
            },
            {
                "content": "Password reset emails are sent within 5 minutes. Check your spam folder if not received.",
                "source": "faq.pdf", 
                "score": 0.8
            }
        ]
        
        node = SupportRagAnswerNode()
        
        # Mock LLM call
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "answer": "To reset your password, go to Settings > Account > Reset Password and follow the instructions. The reset email will arrive within 5 minutes - check your spam folder if you don't see it.",
                "needs_escalation": False,
                "escalation_reason": None
            }
            
            result = await node.execute(sample_state)
            
            assert result.response_text is not None
            assert "reset your password" in result.response_text.lower()
            assert result.support_step == "answered"
            assert not result.escalation_required
    
    @pytest.mark.asyncio
    async def test_rag_answer_with_insufficient_knowledge(self, sample_state):
        """Test RAG answer when knowledge base has insufficient information."""
        # Set up empty or low-relevance knowledge base snippets
        sample_state.kb_snippets = [
            {
                "content": "General information about our products.",
                "source": "general.pdf",
                "score": 0.2
            }
        ]
        
        node = SupportRagAnswerNode()
        
        # Mock LLM call that indicates escalation needed
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "answer": "I don't have enough information about password resets. Let me connect you with our support team.",
                "needs_escalation": True,
                "escalation_reason": "Insufficient knowledge base information"
            }
            
            result = await node.execute(sample_state)
            
            assert result.response_text is not None
            assert "support team" in result.response_text.lower()
            assert result.support_step == "escalation_needed"
            assert result.escalation_required
    
    @pytest.mark.asyncio
    async def test_escalation_analysis(self, sample_state):
        """Test escalation need analysis."""
        node = SupportRagAnswerNode()
        
        # Test with empty knowledge base
        sample_state.kb_snippets = []
        needs_escalation = node._analyze_escalation_need("Some answer", sample_state)
        assert needs_escalation
        
        # Test with low relevance scores
        sample_state.kb_snippets = [{"score": 0.2}]
        needs_escalation = node._analyze_escalation_need("Some answer", sample_state)
        assert needs_escalation
        
        # Test with escalation phrases
        needs_escalation = node._analyze_escalation_need("I need to connect you with our support team", sample_state)
        assert needs_escalation
        
        # Test with very short answer
        needs_escalation = node._analyze_escalation_need("No.", sample_state)
        assert needs_escalation
        
        # Test with good knowledge and answer
        sample_state.kb_snippets = [{"score": 0.8}]
        needs_escalation = node._analyze_escalation_need("Here's a detailed answer with sufficient information to help you.", sample_state)
        assert not needs_escalation


class TestHandoffMessageNode:
    """Test handoff message node."""
    
    @pytest.mark.asyncio
    async def test_handoff_message_generation(self, sample_state):
        """Test handoff message generation."""
        sample_state.escalation_reason = "Password reset requires manual verification"
        
        node = HandoffMessageNode()
        
        # Mock LLM call
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.return_value = {
                "message": "Thanks for your question about password reset! I've connected you with our support team who will help you with the manual verification process. They'll be in touch within a few hours during business hours."
            }
            
            result = await node.execute(sample_state)
            
            assert result.response_text is not None
            assert "support team" in result.response_text.lower()
            assert result.support_step == "handoff_complete"
    
    @pytest.mark.asyncio
    async def test_handoff_message_fallback(self, sample_state):
        """Test handoff message fallback when LLM fails."""
        node = HandoffMessageNode()
        
        # Mock LLM call to raise exception
        with patch.object(node, '_call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            
            result = await node.execute(sample_state)
            
            assert result.response_text is not None
            assert "support team" in result.response_text.lower()
            assert result.support_step == "handoff_complete"


class TestSupportJourneySubgraph:
    """Test complete support journey subgraph."""
    
    @pytest.mark.asyncio
    async def test_journey_start_step(self, sample_state):
        """Test support journey starting step."""
        journey = SupportJourneySubgraph()
        
        # Mock the kb_retrieve tool
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResponse(
            success=True,
            data={
                "snippets": [
                    {
                        "content": "Password reset instructions here.",
                        "source": "user_guide.pdf",
                        "score": 0.9
                    }
                ]
            }
        )
        
        with patch('apps.bot.langgraph.support_journey.get_tool') as mock_get_tool:
            mock_get_tool.return_value = mock_tool
            
            # Mock the SupportRagAnswerNode to return a successful answer
            with patch('apps.bot.langgraph.support_journey.SupportRagAnswerNode') as mock_node_class:
                mock_node = MagicMock()
                mock_node_class.return_value = mock_node
                
                # Create a copy of the state with the expected updates
                updated_state = sample_state
                updated_state.kb_snippets = [
                    {
                        "content": "Password reset instructions here.",
                        "source": "user_guide.pdf", 
                        "score": 0.9
                    }
                ]
                updated_state.support_step = 'answered'
                updated_state.response_text = "Here's how to reset your password..."
                
                async def mock_execute(state):
                    return updated_state
                
                mock_node.execute = mock_execute
                
                result = await journey.execute_support_journey(sample_state)
                
                assert result.kb_snippets is not None
                assert len(result.kb_snippets) > 0
                assert result.support_step == 'answered'
    
    @pytest.mark.asyncio
    async def test_journey_with_escalation(self, sample_state):
        """Test support journey with escalation flow."""
        journey = SupportJourneySubgraph()
        
        # Mock kb_retrieve tool with empty results
        mock_kb_tool = MagicMock()
        mock_kb_tool.execute.return_value = ToolResponse(
            success=True,
            data={"snippets": []}
        )
        
        # Mock handoff_create_ticket tool
        mock_handoff_tool = MagicMock()
        mock_handoff_tool.execute.return_value = ToolResponse(
            success=True,
            data={"ticket_id": "TICKET-123"}
        )
        
        with patch('apps.bot.langgraph.support_journey.get_tool') as mock_get_tool:
            def tool_side_effect(tool_name):
                if tool_name == "kb_retrieve":
                    return mock_kb_tool
                elif tool_name == "handoff_create_ticket":
                    return mock_handoff_tool
                return None
            
            mock_get_tool.side_effect = tool_side_effect
            
            # Mock the SupportRagAnswerNode to trigger escalation
            with patch('apps.bot.langgraph.support_journey.SupportRagAnswerNode') as mock_rag_class:
                mock_rag_node = MagicMock()
                mock_rag_class.return_value = mock_rag_node
                
                # Create state that triggers escalation
                escalation_state = sample_state
                escalation_state.kb_snippets = []
                escalation_state.support_step = 'escalation_needed'
                escalation_state.set_escalation("Insufficient knowledge base information")
                
                async def mock_rag_execute(state):
                    return escalation_state
                
                mock_rag_node.execute = mock_rag_execute
                
                # Mock HandoffMessageNode
                with patch('apps.bot.langgraph.support_journey.HandoffMessageNode') as mock_handoff_class:
                    mock_handoff_node = MagicMock()
                    mock_handoff_class.return_value = mock_handoff_node
                    
                    # Create final state with handoff complete
                    final_state = escalation_state
                    final_state.handoff_ticket_id = "TICKET-123"
                    final_state.support_step = 'handoff_complete'
                    final_state.response_text = "I've connected you with our support team..."
                    
                    async def mock_handoff_execute(state):
                        return final_state
                    
                    mock_handoff_node.execute = mock_handoff_execute
                    
                    result = await journey.execute_support_journey(sample_state)
                    
                    assert result.handoff_ticket_id == "TICKET-123"
                    assert result.support_step == 'handoff_complete'
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_state):
        """Test error handling in support journey."""
        journey = SupportJourneySubgraph()
        
        # Mock an exception in knowledge retrieval
        with patch('apps.bot.langgraph.support_journey.get_tool') as mock_get_tool:
            mock_get_tool.side_effect = Exception("Tool registry error")
            
            result = await journey.execute_support_journey(sample_state)
            
            assert result.response_text is not None
            assert "support team" in result.response_text.lower()
            assert result.escalation_required


class TestSupportJourneyIntegration:
    """Test support journey integration with orchestrator."""
    
    @pytest.mark.asyncio
    async def test_execute_support_journey_node(self, sample_state):
        """Test the orchestrator entry point function."""
        state_dict = sample_state.to_dict()
        
        # Mock the support journey execution
        with patch('apps.bot.langgraph.support_journey.SupportJourneySubgraph') as mock_journey_class:
            mock_journey = MagicMock()
            mock_journey_class.return_value = mock_journey
            
            # Mock successful execution - return a coroutine
            updated_state = sample_state
            updated_state.response_text = "Here's the answer to your question..."
            updated_state.support_step = "answered"
            
            # Create an async mock
            async def mock_execute_support_journey(state):
                return updated_state
            
            mock_journey.execute_support_journey = mock_execute_support_journey
            
            result_dict = await execute_support_journey_node(state_dict)
            
            assert isinstance(result_dict, dict)
            assert result_dict["response_text"] == "Here's the answer to your question..."
            assert result_dict["support_step"] == "answered"


@pytest.mark.asyncio
async def test_support_journey_flow_complete():
    """Test complete support journey flow end-to-end."""
    # Create initial state
    state = ConversationState(
        tenant_id="test-tenant",
        conversation_id="conv-123",
        request_id="req-456",
        customer_id="cust-789",
        incoming_message="How do I cancel my subscription?",
        intent="support_question",
        journey="support"
    )
    
    # Mock all tools and LLM calls
    mock_kb_tool = MagicMock()
    mock_kb_tool.execute.return_value = ToolResponse(
        success=True,
        data={
            "snippets": [
                {
                    "content": "To cancel your subscription, go to Account Settings and click Cancel Subscription.",
                    "source": "cancellation_policy.pdf",
                    "score": 0.95
                }
            ]
        }
    )
    
    with patch('apps.bot.langgraph.support_journey.get_tool') as mock_get_tool:
        mock_get_tool.return_value = mock_kb_tool
        
        # Mock LLM calls for RAG answer
        with patch('apps.bot.langgraph.support_journey.SupportRagAnswerNode._call_llm') as mock_rag_llm:
            mock_rag_llm.return_value = {
                "answer": "To cancel your subscription, go to Account Settings and click Cancel Subscription. This will take effect at the end of your current billing period.",
                "needs_escalation": False,
                "escalation_reason": None
            }
            
            # Execute the journey
            journey = SupportJourneySubgraph()
            result = await journey.execute_support_journey(state)
            
            # Verify the result
            assert result.response_text is not None
            assert "cancel your subscription" in result.response_text.lower()
            assert result.support_step == "answered"
            assert not result.escalation_required
            assert len(result.kb_snippets) > 0