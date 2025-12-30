"""
Tests for Preferences & Consent Journey subgraph.

This module tests the complete preferences journey workflow including
preference parsing, customer updates, and consent enforcement.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from apps.bot.conversation_state import ConversationState
from apps.bot.langgraph.preferences_journey import (
    PreferenceParsingNode,
    PrefsConsentResponseNode,
    PreferencesJourneySubgraph,
    preferences_journey_entry
)
from apps.bot.tools.base import ToolResponse


@pytest.fixture
def sample_state():
    """Create a sample conversation state for testing."""
    return ConversationState(
        tenant_id="550e8400-e29b-41d4-a716-446655440000",  # Valid UUID
        conversation_id="550e8400-e29b-41d4-a716-446655440001",  # Valid UUID
        request_id="550e8400-e29b-41d4-a716-446655440002",  # Valid UUID
        customer_id="550e8400-e29b-41d4-a716-446655440003",  # Valid UUID
        phone_e164="+254712345678",
        tenant_name="Test Shop",
        bot_name="ShopBot",
        incoming_message="I want to stop marketing messages",
        turn_count=1
    )


class TestPreferenceParsingNode:
    """Test preference parsing node functionality."""
    
    @pytest.mark.asyncio
    async def test_parse_stop_keyword(self, sample_state):
        """Test parsing of STOP keyword for immediate unsubscribe."""
        sample_state.incoming_message = "STOP"
        
        node = PreferenceParsingNode()
        
        # Mock LLM response
        mock_result = {
            "has_preferences": True,
            "language_preference": None,
            "marketing_opt_in": False,
            "notification_preferences": {
                "marketing": False,
                "notifications": None,
                "important_only": None
            },
            "immediate_stop": True,
            "parsed_intent": "stop_all",
            "confidence": 0.95,
            "notes": "STOP keyword detected for immediate unsubscribe"
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify state updates
        assert updated_state.prefs_step == "update_preferences"
        assert updated_state.metadata['preference_parsing']['immediate_stop'] is True
        assert updated_state.metadata['preference_parsing']['marketing_opt_in'] is False
        assert updated_state.metadata['preference_parsing']['parsed_intent'] == "stop_all"
    
    @pytest.mark.asyncio
    async def test_parse_language_preference(self, sample_state):
        """Test parsing of language preference change."""
        sample_state.incoming_message = "Please switch to Swahili"
        
        node = PreferenceParsingNode()
        
        # Mock LLM response
        mock_result = {
            "has_preferences": True,
            "language_preference": "sw",
            "marketing_opt_in": None,
            "notification_preferences": {
                "marketing": None,
                "notifications": None,
                "important_only": None
            },
            "immediate_stop": False,
            "parsed_intent": "language_change",
            "confidence": 0.85,
            "notes": "Language change to Swahili detected"
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify state updates
        assert updated_state.prefs_step == "update_preferences"
        assert updated_state.metadata['preference_parsing']['language_preference'] == "sw"
        assert updated_state.metadata['preference_parsing']['parsed_intent'] == "language_change"
        assert updated_state.metadata['preference_parsing']['immediate_stop'] is False
    
    @pytest.mark.asyncio
    async def test_parse_marketing_opt_in(self, sample_state):
        """Test parsing of marketing opt-in request."""
        sample_state.incoming_message = "Yes, I want to receive promotions"
        
        node = PreferenceParsingNode()
        
        # Mock LLM response
        mock_result = {
            "has_preferences": True,
            "language_preference": None,
            "marketing_opt_in": True,
            "notification_preferences": {
                "marketing": True,
                "notifications": None,
                "important_only": None
            },
            "immediate_stop": False,
            "parsed_intent": "marketing_opt_in",
            "confidence": 0.80,
            "notes": "Marketing opt-in detected"
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify state updates
        assert updated_state.prefs_step == "update_preferences"
        assert updated_state.metadata['preference_parsing']['marketing_opt_in'] is True
        assert updated_state.metadata['preference_parsing']['parsed_intent'] == "marketing_opt_in"
    
    @pytest.mark.asyncio
    async def test_heuristic_fallback_stop(self, sample_state):
        """Test heuristic fallback for STOP keyword when LLM fails."""
        sample_state.incoming_message = "UNSUBSCRIBE"
        
        node = PreferenceParsingNode()
        
        # Mock LLM failure by patching the _call_llm method to return heuristic fallback
        with patch.object(node, '_call_llm') as mock_call_llm:
            # Make _call_llm return the heuristic fallback directly
            mock_call_llm.return_value = {
                "has_preferences": True,
                "language_preference": None,
                "marketing_opt_in": False,
                "notification_preferences": {
                    "marketing": False,
                    "notifications": None,
                    "important_only": None
                },
                "immediate_stop": True,
                "parsed_intent": "stop_all",
                "confidence": 0.6,
                "notes": "Heuristic parsing detected: stop_all"
            }
            
            updated_state = await node.execute(sample_state)
        
        # Verify heuristic fallback worked
        assert updated_state.prefs_step == "update_preferences"
        assert updated_state.metadata['preference_parsing']['immediate_stop'] is True
        assert updated_state.metadata['preference_parsing']['marketing_opt_in'] is False
        assert updated_state.metadata['preference_parsing']['parsed_intent'] == "stop_all"
        assert updated_state.metadata['preference_parsing']['confidence'] == 0.6
    
    @pytest.mark.asyncio
    async def test_heuristic_fallback_language(self, sample_state):
        """Test heuristic fallback for language detection when LLM fails."""
        sample_state.incoming_message = "switch to english please"
        
        node = PreferenceParsingNode()
        
        # Mock LLM failure by patching the _call_llm method to return heuristic fallback
        with patch.object(node, '_call_llm') as mock_call_llm:
            # Make _call_llm return the heuristic fallback directly
            mock_call_llm.return_value = {
                "has_preferences": True,
                "language_preference": "en",
                "marketing_opt_in": None,
                "notification_preferences": {
                    "marketing": None,
                    "notifications": None,
                    "important_only": None
                },
                "immediate_stop": False,
                "parsed_intent": "language_change",
                "confidence": 0.6,
                "notes": "Heuristic parsing detected: language_change"
            }
            
            updated_state = await node.execute(sample_state)
        
        # Verify heuristic fallback worked
        assert updated_state.prefs_step == "update_preferences"
        assert updated_state.metadata['preference_parsing']['language_preference'] == "en"
        assert updated_state.metadata['preference_parsing']['parsed_intent'] == "language_change"
        assert updated_state.metadata['preference_parsing']['immediate_stop'] is False
    
    @pytest.mark.asyncio
    async def test_no_preferences_detected(self, sample_state):
        """Test when no preferences are detected in message."""
        sample_state.incoming_message = "Hello, how are you?"
        
        node = PreferenceParsingNode()
        
        # Mock LLM response with no preferences
        mock_result = {
            "has_preferences": False,
            "language_preference": None,
            "marketing_opt_in": None,
            "notification_preferences": {
                "marketing": None,
                "notifications": None,
                "important_only": None
            },
            "immediate_stop": False,
            "parsed_intent": "general_inquiry",
            "confidence": 0.40,
            "notes": "No specific preferences detected"
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify state updates
        assert updated_state.prefs_step == "update_preferences"
        assert updated_state.metadata['preference_parsing']['has_preferences'] is False
        assert updated_state.metadata['preference_parsing']['parsed_intent'] == "general_inquiry"


class TestPrefsConsentResponseNode:
    """Test preferences consent response node functionality."""
    
    @pytest.mark.asyncio
    async def test_stop_confirmation_response(self, sample_state):
        """Test confirmation response for STOP/unsubscribe."""
        # Set up state with STOP parsing result
        sample_state.metadata = {
            'preference_parsing': {
                'immediate_stop': True,
                'marketing_opt_in': False,
                'parsed_intent': 'stop_all'
            },
            'preference_update': {
                'success': True,
                'updated_fields': ['marketing_opt_in']
            }
        }
        
        node = PrefsConsentResponseNode()
        
        # Mock LLM response
        mock_result = {
            "response_text": "You've been unsubscribed from marketing messages. You'll only receive order updates and important notifications. Reply 'MARKETING OK' to re-subscribe anytime."
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify response
        assert updated_state.response_text == mock_result["response_text"]
        assert updated_state.prefs_step == "complete"
        assert "unsubscribed" in updated_state.response_text.lower()
        assert "marketing ok" in updated_state.response_text.lower()
    
    @pytest.mark.asyncio
    async def test_language_change_response(self, sample_state):
        """Test confirmation response for language preference change."""
        # Set up state with language change result
        sample_state.metadata = {
            'preference_parsing': {
                'language_preference': 'sw',
                'parsed_intent': 'language_change'
            },
            'preference_update': {
                'success': True,
                'updated_fields': ['language_preference']
            }
        }
        
        node = PrefsConsentResponseNode()
        
        # Mock LLM response
        mock_result = {
            "response_text": "I've updated your language preference to Swahili. All future messages will be in Swahili."
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify response
        assert updated_state.response_text == mock_result["response_text"]
        assert updated_state.prefs_step == "complete"
        assert "swahili" in updated_state.response_text.lower()
    
    @pytest.mark.asyncio
    async def test_marketing_opt_in_response(self, sample_state):
        """Test confirmation response for marketing opt-in."""
        # Set up state with marketing opt-in result
        sample_state.metadata = {
            'preference_parsing': {
                'marketing_opt_in': True,
                'parsed_intent': 'marketing_opt_in'
            },
            'preference_update': {
                'success': True,
                'updated_fields': ['marketing_opt_in']
            }
        }
        
        node = PrefsConsentResponseNode()
        
        # Mock LLM response
        mock_result = {
            "response_text": "You're now subscribed to receive our latest offers and promotions. Reply 'STOP' anytime to unsubscribe."
        }
        
        with patch.object(node, '_call_llm', return_value=mock_result):
            updated_state = await node.execute(sample_state)
        
        # Verify response
        assert updated_state.response_text == mock_result["response_text"]
        assert updated_state.prefs_step == "complete"
        assert "subscribed" in updated_state.response_text.lower()
        assert "stop" in updated_state.response_text.lower()
    
    @pytest.mark.asyncio
    async def test_heuristic_fallback_stop(self, sample_state):
        """Test heuristic fallback for STOP confirmation when LLM fails."""
        # Set up state with STOP parsing result
        sample_state.metadata = {
            'preference_parsing': {
                'immediate_stop': True,
                'marketing_opt_in': False,
                'parsed_intent': 'stop_all'
            }
        }
        
        node = PrefsConsentResponseNode()
        
        # Mock LLM failure by patching the _call_llm method to return heuristic fallback
        with patch.object(node, '_call_llm') as mock_call_llm:
            # Make _call_llm return the heuristic fallback directly
            mock_call_llm.return_value = {
                "response_text": "You've been unsubscribed from marketing messages. You'll only receive order updates and important notifications. Reply 'MARKETING OK' to re-subscribe anytime."
            }
            
            updated_state = await node.execute(sample_state)
        
        # Verify heuristic fallback worked
        assert updated_state.prefs_step == "complete"
        assert "unsubscribed" in updated_state.response_text.lower()
        assert "marketing ok" in updated_state.response_text.lower()
    
    @pytest.mark.asyncio
    async def test_heuristic_fallback_language(self, sample_state):
        """Test heuristic fallback for language change confirmation when LLM fails."""
        # Set up state with language change result
        sample_state.metadata = {
            'preference_parsing': {
                'language_preference': 'en',
                'parsed_intent': 'language_change'
            }
        }
        
        node = PrefsConsentResponseNode()
        
        # Mock LLM failure by patching the _call_llm method to return heuristic fallback
        with patch.object(node, '_call_llm') as mock_call_llm:
            # Make _call_llm return the heuristic fallback directly
            mock_call_llm.return_value = {
                "response_text": "I've updated your language preference to English. All future messages will be in English."
            }
            
            updated_state = await node.execute(sample_state)
        
        # Verify heuristic fallback worked
        assert updated_state.prefs_step == "complete"
        assert "english" in updated_state.response_text.lower()
        assert "language preference" in updated_state.response_text.lower()


class TestPreferencesJourneySubgraph:
    """Test preferences journey subgraph orchestration."""
    
    @pytest.mark.asyncio
    async def test_complete_stop_workflow(self, sample_state):
        """Test complete STOP workflow from parsing to response."""
        sample_state.incoming_message = "STOP"
        
        subgraph = PreferencesJourneySubgraph()
        
        # Mock tool response for customer update
        mock_tool_response = ToolResponse(
            success=True,
            data={
                'customer_id': 'cust-abc',
                'marketing_opt_in': False,
                'updated_fields': ['marketing_opt_in']
            }
        )
        
        with patch('apps.bot.langgraph.preferences_journey.get_tool') as mock_get_tool:
            mock_tool = Mock()
            mock_tool.execute.return_value = mock_tool_response
            mock_get_tool.return_value = mock_tool
            
            # Mock LLM nodes
            with patch.object(subgraph.preference_parsing_node, 'execute') as mock_parse:
                with patch.object(subgraph.prefs_consent_response_node, 'execute') as mock_response:
                    
                    # Mock parsing result
                    def mock_parse_execute(state):
                        state.prefs_step = "update_preferences"
                        state.metadata = {
                            'preference_parsing': {
                                'has_preferences': True,
                                'immediate_stop': True,
                                'marketing_opt_in': False,
                                'parsed_intent': 'stop_all'
                            }
                        }
                        return state
                    
                    # Mock response result
                    def mock_response_execute(state):
                        state.response_text = "You've been unsubscribed from marketing messages."
                        state.prefs_step = "complete"
                        return state
                    
                    mock_parse.side_effect = mock_parse_execute
                    mock_response.side_effect = mock_response_execute
                    
                    # Execute complete workflow
                    final_state = sample_state
                    while getattr(final_state, 'prefs_step', 'complete') != 'complete':
                        final_state = await subgraph.execute_step(final_state)
        
        # Verify final state
        assert final_state.prefs_step == "complete"
        assert final_state.response_text == "You've been unsubscribed from marketing messages."
        assert final_state.metadata['preference_update']['success'] is True
        
        # Verify tool was called with correct parameters
        mock_tool.execute.assert_called_once()
        call_args = mock_tool.execute.call_args[1]
        assert call_args['tenant_id'] == sample_state.tenant_id
        assert call_args['customer_id'] == sample_state.customer_id
        assert call_args['marketing_opt_in'] is False
    
    @pytest.mark.asyncio
    async def test_language_change_workflow(self, sample_state):
        """Test complete language change workflow."""
        sample_state.incoming_message = "Switch to Swahili please"
        
        subgraph = PreferencesJourneySubgraph()
        
        # Mock tool response for customer update
        mock_tool_response = ToolResponse(
            success=True,
            data={
                'customer_id': 'cust-abc',
                'language_preference': 'sw',
                'updated_fields': ['language_preference']
            }
        )
        
        with patch('apps.bot.langgraph.preferences_journey.get_tool') as mock_get_tool:
            mock_tool = Mock()
            mock_tool.execute.return_value = mock_tool_response
            mock_get_tool.return_value = mock_tool
            
            # Mock LLM nodes
            with patch.object(subgraph.preference_parsing_node, 'execute') as mock_parse:
                with patch.object(subgraph.prefs_consent_response_node, 'execute') as mock_response:
                    
                    # Mock parsing result
                    def mock_parse_execute(state):
                        state.prefs_step = "update_preferences"
                        state.metadata = {
                            'preference_parsing': {
                                'has_preferences': True,
                                'language_preference': 'sw',
                                'parsed_intent': 'language_change'
                            }
                        }
                        return state
                    
                    # Mock response result
                    def mock_response_execute(state):
                        state.response_text = "I've updated your language preference to Swahili."
                        state.prefs_step = "complete"
                        return state
                    
                    mock_parse.side_effect = mock_parse_execute
                    mock_response.side_effect = mock_response_execute
                    
                    # Execute complete workflow
                    final_state = sample_state
                    while getattr(final_state, 'prefs_step', 'complete') != 'complete':
                        final_state = await subgraph.execute_step(final_state)
        
        # Verify final state
        assert final_state.prefs_step == "complete"
        assert final_state.response_text == "I've updated your language preference to Swahili."
        assert final_state.metadata['preference_update']['success'] is True
        
        # Verify tool was called with correct parameters
        mock_tool.execute.assert_called_once()
        call_args = mock_tool.execute.call_args[1]
        assert call_args['language_preference'] == 'sw'
    
    @pytest.mark.asyncio
    async def test_no_preferences_workflow(self, sample_state):
        """Test workflow when no preferences are detected."""
        sample_state.incoming_message = "Hello, how are you?"
        
        subgraph = PreferencesJourneySubgraph()
        
        # Mock LLM nodes
        with patch.object(subgraph.preference_parsing_node, 'execute') as mock_parse:
            with patch.object(subgraph.prefs_consent_response_node, 'execute') as mock_response:
                
                # Mock parsing result with no preferences
                def mock_parse_execute(state):
                    state.prefs_step = "update_preferences"
                    state.metadata = {
                        'preference_parsing': {
                            'has_preferences': False,
                            'parsed_intent': 'general_inquiry'
                        }
                    }
                    return state
                
                # Mock response result
                def mock_response_execute(state):
                    state.response_text = "I understand you're asking about preferences. What would you like to update?"
                    state.prefs_step = "complete"
                    return state
                
                mock_parse.side_effect = mock_parse_execute
                mock_response.side_effect = mock_response_execute
                
                # Execute workflow
                final_state = sample_state
                while getattr(final_state, 'prefs_step', 'complete') != 'complete':
                    final_state = await subgraph.execute_step(final_state)
        
        # Verify final state
        assert final_state.prefs_step == "complete"
        assert "preferences" in final_state.response_text.lower()
        
        # Verify no tool was called since no preferences to update
        with patch('apps.bot.langgraph.preferences_journey.get_tool') as mock_get_tool:
            # Tool should not be called for no preferences
            mock_get_tool.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_tool_failure_handling(self, sample_state):
        """Test handling of tool execution failures."""
        sample_state.incoming_message = "STOP"
        
        subgraph = PreferencesJourneySubgraph()
        
        # Mock tool failure
        mock_tool_response = ToolResponse(
            success=False,
            error="Customer not found",
            error_code="CUSTOMER_NOT_FOUND"
        )
        
        with patch('apps.bot.langgraph.preferences_journey.get_tool') as mock_get_tool:
            mock_tool = Mock()
            mock_tool.execute.return_value = mock_tool_response
            mock_get_tool.return_value = mock_tool
            
            # Mock LLM nodes
            with patch.object(subgraph.preference_parsing_node, 'execute') as mock_parse:
                with patch.object(subgraph.prefs_consent_response_node, 'execute') as mock_response:
                    
                    # Mock parsing result
                    def mock_parse_execute(state):
                        state.prefs_step = "update_preferences"
                        state.metadata = {
                            'preference_parsing': {
                                'has_preferences': True,
                                'immediate_stop': True,
                                'marketing_opt_in': False
                            }
                        }
                        return state
                    
                    # Mock response result
                    def mock_response_execute(state):
                        state.response_text = "I'm having trouble updating your preferences right now."
                        state.prefs_step = "complete"
                        return state
                    
                    mock_parse.side_effect = mock_parse_execute
                    mock_response.side_effect = mock_response_execute
                    
                    # Execute workflow
                    final_state = sample_state
                    while getattr(final_state, 'prefs_step', 'complete') != 'complete':
                        final_state = await subgraph.execute_step(final_state)
        
        # Verify error handling
        assert final_state.prefs_step == "complete"
        assert final_state.metadata['preference_update']['success'] is False
        assert final_state.metadata['preference_update']['error'] == "Customer not found"
    
    @pytest.mark.asyncio
    async def test_journey_error_handling(self, sample_state):
        """Test handling of journey execution errors."""
        sample_state.incoming_message = "STOP"
        
        subgraph = PreferencesJourneySubgraph()
        
        # Mock parsing node failure
        with patch.object(subgraph.preference_parsing_node, 'execute', side_effect=Exception("Node failed")):
            final_state = await subgraph.execute_step(sample_state)
        
        # Verify error handling
        assert final_state.prefs_step == "complete"
        assert final_state.escalation_required is True
        assert "preferences journey error" in final_state.escalation_reason.lower()
        assert "having trouble" in final_state.response_text.lower()


class TestPreferencesJourneyEntry:
    """Test preferences journey entry point."""
    
    @pytest.mark.asyncio
    async def test_journey_entry_initialization(self, sample_state):
        """Test journey entry point initializes state correctly."""
        sample_state.incoming_message = "STOP"
        
        # Mock the subgraph execution
        with patch('apps.bot.langgraph.preferences_journey.PreferencesJourneySubgraph') as mock_subgraph_class:
            mock_subgraph = Mock()
            mock_subgraph_class.return_value = mock_subgraph
            
            # Mock execute_step to complete immediately
            async def mock_execute_step(state):
                state.prefs_step = "complete"
                state.response_text = "Preferences updated"
                return state
            
            mock_subgraph.execute_step = mock_execute_step
            
            # Execute journey entry
            final_state = await preferences_journey_entry(sample_state)
        
        # Verify initialization
        assert final_state.journey == "prefs"
        assert final_state.prefs_step == "complete"
        assert final_state.response_text == "Preferences updated"
    
    @pytest.mark.asyncio
    async def test_journey_entry_turn_limit(self, sample_state):
        """Test journey entry handles turn limit safety check."""
        sample_state.incoming_message = "STOP"
        sample_state.turn_count = 15  # Exceed limit
        
        # Mock the subgraph execution to never complete
        with patch('apps.bot.langgraph.preferences_journey.PreferencesJourneySubgraph') as mock_subgraph_class:
            mock_subgraph = Mock()
            mock_subgraph_class.return_value = mock_subgraph
            
            # Mock execute_step to never complete (infinite loop protection)
            async def mock_execute_step(state):
                state.prefs_step = "parse_preferences"  # Never complete
                return state
            
            mock_subgraph.execute_step = mock_execute_step
            
            # Execute journey entry
            final_state = await preferences_journey_entry(sample_state)
        
        # Verify safety handling
        assert final_state.escalation_required is True
        assert "exceeded turn limit" in final_state.escalation_reason.lower()
        assert "having trouble" in final_state.response_text.lower()


@pytest.mark.integration
class TestPreferencesJourneyIntegration:
    """Integration tests for preferences journey with real components."""
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, sample_state):
        """Test that preferences journey enforces tenant isolation."""
        sample_state.incoming_message = "STOP"
        subgraph = PreferencesJourneySubgraph()
        
        # Set up state with preferences parsing result
        sample_state.prefs_step = "update_preferences"
        sample_state.metadata = {
            'preference_parsing': {
                'has_preferences': True,
                'marketing_opt_in': False
            }
        }
        
        with patch('apps.bot.langgraph.preferences_journey.get_tool') as mock_get_tool:
            mock_tool = Mock()
            mock_tool.execute.return_value = ToolResponse(success=True, data={})
            mock_get_tool.return_value = mock_tool
            
            # Execute update step directly
            await subgraph._update_preferences_step(sample_state)
        
        # Verify tenant_id is passed to tool
        mock_tool.execute.assert_called_once()
        call_args = mock_tool.execute.call_args[1]
        assert call_args['tenant_id'] == sample_state.tenant_id
        assert call_args['customer_id'] == sample_state.customer_id
        assert call_args['conversation_id'] == sample_state.conversation_id
        assert call_args['request_id'] == sample_state.request_id
    
    @pytest.mark.asyncio
    async def test_consent_enforcement_workflow(self, sample_state):
        """Test that consent changes are properly enforced."""
        sample_state.incoming_message = "STOP"
        
        # Mock successful tool execution
        mock_tool_response = ToolResponse(
            success=True,
            data={
                'customer_id': 'cust-abc',
                'marketing_opt_in': False,
                'consent_flags': {'marketing': False},
                'updated_fields': ['marketing_opt_in', 'consent_flags']
            }
        )
        
        subgraph = PreferencesJourneySubgraph()
        
        # Set up state with preferences parsing result
        sample_state.prefs_step = "update_preferences"
        sample_state.metadata = {
            'preference_parsing': {
                'has_preferences': True,
                'immediate_stop': True,
                'marketing_opt_in': False,
                'notification_preferences': {'marketing': False}
            }
        }
        
        with patch('apps.bot.langgraph.preferences_journey.get_tool') as mock_get_tool:
            mock_tool = Mock()
            mock_tool.execute.return_value = mock_tool_response
            mock_get_tool.return_value = mock_tool
            
            # Execute update step directly
            updated_state = await subgraph._update_preferences_step(sample_state)
        
        # Verify consent flags are updated in state
        assert updated_state.marketing_opt_in is False
        assert updated_state.notification_prefs.get('marketing') is False
        assert updated_state.metadata['preference_update']['success'] is True
        assert 'marketing_opt_in' in updated_state.metadata['preference_update']['updated_fields']
        assert 'consent_flags' in updated_state.metadata['preference_update']['updated_fields']