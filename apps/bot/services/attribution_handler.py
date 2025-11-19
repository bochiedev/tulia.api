"""
Attribution handler for adding source citations to responses.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AttributionHandler:
    """
    Handles source attribution and citation formatting.
    """
    
    def __init__(self, config=None):
        """
        Initialize attribution handler.
        
        Args:
            config: AgentConfiguration instance (optional)
        """
        self.config = config
        self.enabled = config.enable_source_attribution if config else True
    
    def add_attribution(
        self,
        response: str,
        sources: List[Dict[str, Any]],
        style: str = 'endnote'
    ) -> str:
        """
        Add source attribution to response.
        
        Args:
            response: Agent response text
            sources: List of source dicts
            style: Citation style ('inline' or 'endnote')
        
        Returns:
            Response with attribution
        """
        if not self.enabled or not sources:
            return response
        
        if not self.should_attribute(sources):
            return response
        
        if style == 'inline':
            return self._add_inline_attribution(response, sources)
        else:
            return self._add_endnote_attribution(response, sources)
    
    def should_attribute(self, sources: List[Dict[str, Any]]) -> bool:
        """
        Determine if attribution should be added.
        
        Args:
            sources: List of sources
        
        Returns:
            True if attribution should be added
        """
        if not self.enabled:
            return False
        
        # Always attribute if we have sources
        return len(sources) > 0
    
    def format_citation(
        self,
        source: Dict[str, Any],
        index: int = None
    ) -> str:
        """
        Format a single citation.
        
        Args:
            source: Source dict
            index: Citation index (for numbered citations)
        
        Returns:
            Formatted citation string
        """
        source_type = source.get('type', 'unknown')
        
        if source_type == 'document':
            return self._format_document_citation(source, index)
        elif source_type == 'database':
            return self._format_database_citation(source, index)
        elif source_type == 'internet':
            return self._format_internet_citation(source, index)
        else:
            return f"[{index}] Unknown source" if index else "Unknown source"
    
    def _format_document_citation(
        self,
        source: Dict[str, Any],
        index: int = None
    ) -> str:
        """Format document citation."""
        name = source.get('name', 'Document')
        
        if index:
            return f"[{index}] {name}"
        else:
            return name
    
    def _format_database_citation(
        self,
        source: Dict[str, Any],
        index: int = None
    ) -> str:
        """Format database citation."""
        if index:
            return f"[{index}] Our Catalog"
        else:
            return "our catalog"
    
    def _format_internet_citation(
        self,
        source: Dict[str, Any],
        index: int = None
    ) -> str:
        """Format internet citation."""
        name = source.get('name', 'External Source')
        url = source.get('url', '')
        
        if index:
            if url:
                return f"[{index}] {name} ({url})"
            else:
                return f"[{index}] {name}"
        else:
            return name
    
    def _add_inline_attribution(
        self,
        response: str,
        sources: List[Dict[str, Any]]
    ) -> str:
        """
        Add inline citations to response.
        
        Args:
            response: Response text
            sources: List of sources
        
        Returns:
            Response with inline citations
        """
        # For inline, we add a brief mention at the end
        if not sources:
            return response
        
        source_types = set(s.get('type') for s in sources)
        
        attribution_parts = []
        if 'document' in source_types:
            attribution_parts.append("our documentation")
        if 'database' in source_types:
            attribution_parts.append("our catalog")
        if 'internet' in source_types:
            attribution_parts.append("external sources")
        
        if attribution_parts:
            attribution = f" (based on {', '.join(attribution_parts)})"
            return response + attribution
        
        return response
    
    def _add_endnote_attribution(
        self,
        response: str,
        sources: List[Dict[str, Any]]
    ) -> str:
        """
        Add endnote citations to response.
        
        Args:
            response: Response text
            sources: List of sources
        
        Returns:
            Response with endnote citations
        """
        if not sources:
            return response
        
        # Deduplicate sources
        unique_sources = self._deduplicate_sources(sources)
        
        if not unique_sources:
            return response
        
        # Build citations section
        citations = ["\n\n---\nSources:"]
        
        for i, source in enumerate(unique_sources, start=1):
            citation = self.format_citation(source, index=i)
            citations.append(citation)
        
        return response + '\n'.join(citations)
    
    def _deduplicate_sources(
        self,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate sources.
        
        Args:
            sources: List of sources
        
        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []
        
        for source in sources:
            # Create unique key based on type and identifier
            source_type = source.get('type')
            source_id = source.get('id') or source.get('url') or source.get('name')
            key = f"{source_type}:{source_id}"
            
            if key not in seen:
                seen.add(key)
                unique.append(source)
        
        return unique
    
    @classmethod
    def create_for_config(cls, config) -> 'AttributionHandler':
        """
        Create attribution handler for agent configuration.
        
        Args:
            config: AgentConfiguration instance
        
        Returns:
            AttributionHandler instance
        """
        return cls(config)
