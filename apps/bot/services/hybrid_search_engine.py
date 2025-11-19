"""
Hybrid search engine combining semantic and keyword search.
"""
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Hybrid search engine that combines semantic and keyword search.
    """
    
    def __init__(
        self,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """
        Initialize hybrid search engine.
        
        Args:
            semantic_weight: Weight for semantic search results (0.0-1.0)
            keyword_weight: Weight for keyword search results (0.0-1.0)
        """
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        
        # Normalize weights
        total = semantic_weight + keyword_weight
        if total > 0:
            self.semantic_weight = semantic_weight / total
            self.keyword_weight = keyword_weight / total
    
    def search(
        self,
        query: str,
        semantic_search_fn: callable,
        keyword_search_fn: callable = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword results.
        
        Args:
            query: Search query
            semantic_search_fn: Function for semantic search
            keyword_search_fn: Optional function for keyword search
            top_k: Number of results to return
        
        Returns:
            List of search results with combined scores
        """
        start_time = time.time()
        
        # If no keyword search, just use semantic
        if not keyword_search_fn:
            results = semantic_search_fn(query, top_k=top_k)
            return self._format_results(results, 'semantic')
        
        # Execute searches in parallel
        semantic_results = []
        keyword_results = []
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(semantic_search_fn, query, top_k * 2): 'semantic',
                executor.submit(keyword_search_fn, query, top_k * 2): 'keyword'
            }
            
            for future in as_completed(futures):
                search_type = futures[future]
                try:
                    results = future.result(timeout=5.0)
                    if search_type == 'semantic':
                        semantic_results = results
                    else:
                        keyword_results = results
                except Exception as e:
                    logger.error(f"Error in {search_type} search: {e}")
        
        # Merge and rank results
        merged_results = self._merge_results(
            semantic_results,
            keyword_results,
            top_k
        )
        
        search_time = time.time() - start_time
        logger.info(
            f"Hybrid search completed in {search_time:.3f}s: "
            f"{len(semantic_results)} semantic + {len(keyword_results)} keyword "
            f"→ {len(merged_results)} merged"
        )
        
        return merged_results
    
    def _merge_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Merge semantic and keyword results with weighted scoring.
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            top_k: Number of results to return
        
        Returns:
            Merged and ranked results
        """
        # Normalize scores to 0-1 range
        semantic_results = self._normalize_scores(semantic_results)
        keyword_results = self._normalize_scores(keyword_results)
        
        # Create result map by ID
        result_map = {}
        
        # Add semantic results
        for result in semantic_results:
            result_id = result.get('id') or result.get('chunk_id')
            if result_id:
                result_map[result_id] = {
                    **result,
                    'semantic_score': result.get('score', 0),
                    'keyword_score': 0,
                    'combined_score': result.get('score', 0) * self.semantic_weight,
                    'sources': ['semantic']
                }
        
        # Add/merge keyword results
        for result in keyword_results:
            result_id = result.get('id') or result.get('chunk_id')
            if not result_id:
                continue
            
            if result_id in result_map:
                # Merge with existing result
                result_map[result_id]['keyword_score'] = result.get('score', 0)
                result_map[result_id]['combined_score'] += (
                    result.get('score', 0) * self.keyword_weight
                )
                result_map[result_id]['sources'].append('keyword')
            else:
                # Add new result
                result_map[result_id] = {
                    **result,
                    'semantic_score': 0,
                    'keyword_score': result.get('score', 0),
                    'combined_score': result.get('score', 0) * self.keyword_weight,
                    'sources': ['keyword']
                }
        
        # Sort by combined score and return top K
        merged = list(result_map.values())
        merged.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Deduplicate by content similarity
        deduplicated = self._deduplicate_results(merged)
        
        return deduplicated[:top_k]
    
    def _normalize_scores(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize scores to 0-1 range.
        
        Args:
            results: Search results with scores
        
        Returns:
            Results with normalized scores
        """
        if not results:
            return []
        
        scores = [r.get('score', 0) for r in results]
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 1
        score_range = max_score - min_score
        
        if score_range == 0:
            return results
        
        normalized = []
        for result in results:
            normalized_result = result.copy()
            normalized_result['score'] = (
                (result.get('score', 0) - min_score) / score_range
            )
            normalized.append(normalized_result)
        
        return normalized
    
    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate results based on content similarity.
        
        Args:
            results: Search results
        
        Returns:
            Deduplicated results
        """
        if not results:
            return []
        
        deduplicated = []
        seen_content = set()
        
        for result in results:
            content = result.get('content', '')
            
            # Simple deduplication by exact content match
            # Could be enhanced with fuzzy matching
            if content and content not in seen_content:
                deduplicated.append(result)
                seen_content.add(content)
        
        return deduplicated
    
    def _format_results(
        self,
        results: List[Dict[str, Any]],
        source: str
    ) -> List[Dict[str, Any]]:
        """Format results with source information."""
        formatted = []
        for result in results:
            formatted_result = result.copy()
            formatted_result['sources'] = [source]
            formatted_result['combined_score'] = result.get('score', 0)
            formatted.append(formatted_result)
        return formatted
