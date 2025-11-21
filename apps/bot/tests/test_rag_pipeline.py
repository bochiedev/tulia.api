"""
Tests for RAG Pipeline service.

Tests the RAGPipeline class for grounded FAQ answers.
"""
import pytest
from unittest.mock import Mock, patch

from apps.bot.services.rag_pipeline import RAGPipeline
from apps.bot.models import ConversationContext


@pytest.mark.django_db
class TestRAGPipeline:
    """Tests for RAGPipeline service."""
    
    def test_answer_question_no_chunks_returns_uncertainty(self, tenant, conversation):
        """Test that no chunks returns uncertainty response."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            detected_language=['en']
        )
        
        pipeline = RAGPipeline()
        
        with patch.object(pipeline, '_retrieve_chunks', return_value=[]):
            answer = pipeline.answer_question(
                question="What is your return policy?",
                tenant=tenant,
                context=context,
                top_k=5
            )
        
        assert "not sure" in answer.lower()
        assert "connect you" in answer.lower()
    
    def test_answer_question_low_similarity_returns_uncertainty(self, tenant, conversation):
        """Test that low similarity score returns uncertainty response."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            detected_language=['en']
        )
        
        pipeline = RAGPipeline()
        
        # Mock chunks with low similarity
        low_similarity_chunks = [
            {'id': 'chunk_1', 'score': 0.5, 'text': 'Some text'}
        ]
        
        with patch.object(pipeline, '_retrieve_chunks', return_value=low_similarity_chunks):
            answer = pipeline.answer_question(
                question="What is your return policy?",
                tenant=tenant,
                context=context,
                top_k=5
            )
        
        assert "not sure" in answer.lower()
    
    def test_answer_question_swahili_uncertainty_response(self, tenant, conversation):
        """Test that Swahili language gets Swahili uncertainty response."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            detected_language=['sw']
        )
        
        pipeline = RAGPipeline()
        
        with patch.object(pipeline, '_retrieve_chunks', return_value=[]):
            answer = pipeline.answer_question(
                question="Je, una sera gani ya kurudisha bidhaa?",
                tenant=tenant,
                context=context,
                top_k=5
            )
        
        # Should return Swahili uncertainty response
        assert "samahani" in answer.lower()
        assert "sina uhakika" in answer.lower()
    
    def test_answer_question_sheng_uncertainty_response(self, tenant, conversation):
        """Test that Sheng language gets Swahili uncertainty response."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            detected_language=['sheng']
        )
        
        pipeline = RAGPipeline()
        
        with patch.object(pipeline, '_retrieve_chunks', return_value=[]):
            answer = pipeline.answer_question(
                question="Niaje, una return policy gani?",
                tenant=tenant,
                context=context,
                top_k=5
            )
        
        # Should return Swahili uncertainty response for Sheng
        assert "samahani" in answer.lower()
    
    def test_retrieve_chunks_logs_query(self, tenant):
        """Test that _retrieve_chunks logs the query."""
        pipeline = RAGPipeline()
        
        with patch('apps.bot.services.rag_pipeline.logger') as mock_logger:
            chunks = pipeline._retrieve_chunks(
                query="test query",
                tenant=tenant,
                top_k=5
            )
        
        # Should log the query
        mock_logger.info.assert_called_once()
        assert "RAG retrieval" in str(mock_logger.info.call_args)
        assert str(tenant.id) in str(mock_logger.info.call_args)
        
        # Should return empty list (not yet implemented)
        assert chunks == []
    
    def test_generate_grounded_answer_returns_uncertainty(self, tenant):
        """Test that _generate_grounded_answer returns uncertainty (not yet implemented)."""
        pipeline = RAGPipeline()
        
        chunks = [
            {'id': 'chunk_1', 'score': 0.95, 'text': 'Our return policy is 30 days'}
        ]
        
        answer = pipeline._generate_grounded_answer(
            question="What is your return policy?",
            chunks=chunks,
            language=['en']
        )
        
        # Should return uncertainty (not yet implemented)
        assert "not sure" in answer.lower()
    
    def test_validate_grounding_returns_false(self):
        """Test that _validate_grounding returns False (not yet implemented)."""
        pipeline = RAGPipeline()
        
        answer = "Our return policy is 30 days"
        chunks = [
            {'id': 'chunk_1', 'text': 'Our return policy is 30 days'}
        ]
        
        result = pipeline._validate_grounding(answer, chunks)
        
        # Should return False (not yet implemented)
        assert result is False
    
    def test_uncertainty_response_english(self):
        """Test uncertainty response in English."""
        pipeline = RAGPipeline()
        
        response = pipeline._uncertainty_response(['en'])
        
        assert "not sure" in response.lower()
        assert "connect you" in response.lower()
    
    def test_uncertainty_response_swahili(self):
        """Test uncertainty response in Swahili."""
        pipeline = RAGPipeline()
        
        response = pipeline._uncertainty_response(['sw'])
        
        assert "samahani" in response.lower()
        assert "sina uhakika" in response.lower()
    
    def test_uncertainty_response_mixed_language(self):
        """Test uncertainty response with mixed language defaults to Swahili."""
        pipeline = RAGPipeline()
        
        response = pipeline._uncertainty_response(['en', 'sw'])
        
        # Should use Swahili if sw is in the list
        assert "samahani" in response.lower()


@pytest.mark.django_db
class TestRAGPipelineIntegration:
    """Integration tests for RAG Pipeline."""
    
    def test_full_pipeline_with_no_data(self, tenant, conversation):
        """Test full pipeline when no data is available."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            detected_language=['en']
        )
        
        pipeline = RAGPipeline()
        
        # Should handle gracefully with no Pinecone data
        answer = pipeline.answer_question(
            question="What is your return policy?",
            tenant=tenant,
            context=context,
            top_k=5
        )
        
        # Should return uncertainty response
        assert "not sure" in answer.lower()
        assert "connect you" in answer.lower()
    
    def test_pipeline_respects_top_k_parameter(self, tenant, conversation):
        """Test that pipeline respects top_k parameter."""
        context = ConversationContext.objects.create(
            conversation=conversation,
            detected_language=['en']
        )
        
        pipeline = RAGPipeline()
        
        with patch.object(pipeline, '_retrieve_chunks') as mock_retrieve:
            mock_retrieve.return_value = []
            
            pipeline.answer_question(
                question="test",
                tenant=tenant,
                context=context,
                top_k=3
            )
            
            # Should pass top_k to _retrieve_chunks
            mock_retrieve.assert_called_once_with("test", tenant, 3)
