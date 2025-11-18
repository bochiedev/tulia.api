"""
Embedding service for generating semantic embeddings.
"""
import logging
import math
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating and comparing semantic embeddings.
    
    Uses OpenAI's embedding API for generating embeddings
    and provides cosine similarity for comparison.
    """
    
    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Text to embed
        
        Returns:
            List of floats representing the embedding vector
        """
        try:
            import openai
            from django.conf import settings
            
            # Use OpenAI's embedding model
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = client.embeddings.create(
                model="text-embedding-3-small",  # Cheaper, faster model
                input=text
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 1536  # text-embedding-3-small dimension
    
    @classmethod
    def cosine_similarity(cls, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        
        Returns:
            Similarity score between 0 and 1
        """
        try:
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            
            # Calculate magnitudes
            magnitude1 = math.sqrt(sum(a * a for a in embedding1))
            magnitude2 = math.sqrt(sum(b * b for b in embedding2))
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = dot_product / (magnitude1 * magnitude2)
            
            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, float(similarity)))
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    @classmethod
    def batch_generate_embeddings(cls, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        try:
            import openai
            from django.conf import settings
            
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            # Return zero vectors as fallback
            return [[0.0] * 1536 for _ in texts]
