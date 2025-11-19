"""
Context synthesizer for merging multi-source retrieval results.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ContextSynthesizer:
    """
    Synthesizes context from multiple sources into coherent LLM input.
    """
    
    def __init__(self, config=None):
        """
        Initialize context synthesizer.
        
        Args:
            config: AgentConfiguration instance (optional)
        """
        self.config = config
    
    def synthesize(
        self,
        retrieval_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesize context from retrieval results.
        
        Args:
            retrieval_results: Results from RAGRetrieverService
        
        Returns:
            Dict with synthesized context and metadata
        """
        documents = retrieval_results.get('documents', [])
        database = retrieval_results.get('database', [])
        internet = retrieval_results.get('internet', [])
        
        # Resolve conflicts between sources
        resolved_data = self.resolve_conflicts(documents, database, internet)
        
        # Format for LLM
        formatted_context = self.format_for_llm(resolved_data)
        
        return {
            'context': formatted_context,
            'sources': self._extract_sources(documents, database, internet),
            'metadata': {
                'document_count': len(documents),
                'database_count': len(database),
                'internet_count': len(internet),
                'total_count': len(documents) + len(database) + len(internet)
            }
        }
    
    def resolve_conflicts(
        self,
        documents: List[Dict[str, Any]],
        database: List[Dict[str, Any]],
        internet: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Resolve conflicts between different sources.
        
        Priority order:
        1. Database (most authoritative for real-time data)
        2. Documents (tenant-provided knowledge)
        3. Internet (external enrichment)
        
        Args:
            documents: Document results
            database: Database results
            internet: Internet results
        
        Returns:
            Resolved data with conflict notes
        """
        resolved = {
            'primary_data': [],
            'supplementary_data': [],
            'conflicts': []
        }
        
        # Database results are primary (most authoritative)
        resolved['primary_data'].extend(database)
        
        # Documents are supplementary
        resolved['supplementary_data'].extend(documents)
        
        # Internet results are supplementary (lowest priority)
        resolved['supplementary_data'].extend(internet)
        
        # Detect conflicts (e.g., different prices for same product)
        # This is a simplified implementation
        conflicts = self._detect_conflicts(database, internet)
        resolved['conflicts'] = conflicts
        
        return resolved
    
    def _detect_conflicts(
        self,
        database: List[Dict[str, Any]],
        internet: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts between database and internet data.
        
        Args:
            database: Database results
            internet: Internet results
        
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Check for price conflicts
        db_products = {
            item.get('name'): item
            for item in database
            if item.get('type') == 'product'
        }
        
        for internet_item in internet:
            name = internet_item.get('title', '')
            for db_name, db_item in db_products.items():
                if db_name.lower() in name.lower():
                    # Found potential match
                    db_price = db_item.get('price')
                    internet_price = internet_item.get('price')
                    
                    if db_price and internet_price and abs(db_price - internet_price) > 0.01:
                        conflicts.append({
                            'type': 'price_mismatch',
                            'product': db_name,
                            'database_price': db_price,
                            'internet_price': internet_price,
                            'resolution': 'using_database_price'
                        })
        
        return conflicts
    
    def format_for_llm(
        self,
        resolved_data: Dict[str, Any]
    ) -> str:
        """
        Format synthesized context for LLM consumption.
        
        Args:
            resolved_data: Resolved data from multiple sources
        
        Returns:
            Formatted context string
        """
        sections = []
        
        # Primary data (database)
        primary = resolved_data.get('primary_data', [])
        if primary:
            sections.append("## Available Products and Services")
            for item in primary:
                if item.get('type') == 'product':
                    sections.append(self._format_product(item))
                elif item.get('type') == 'service':
                    sections.append(self._format_service(item))
                elif item.get('type') == 'availability':
                    sections.append(self._format_availability(item))
        
        # Supplementary data (documents + internet)
        supplementary = resolved_data.get('supplementary_data', [])
        if supplementary:
            sections.append("\n## Additional Information")
            for item in supplementary:
                if 'content' in item:  # Document chunk
                    sections.append(f"- {item['content'][:200]}...")
                elif 'snippet' in item:  # Internet result
                    sections.append(f"- {item['snippet']}")
        
        # Conflicts (if any)
        conflicts = resolved_data.get('conflicts', [])
        if conflicts:
            sections.append("\n## Note")
            sections.append(
                "Some information from external sources differs from our records. "
                "Using our authoritative data."
            )
        
        return '\n'.join(sections)
    
    def _format_product(self, product: Dict[str, Any]) -> str:
        """Format product for LLM."""
        parts = [f"**{product['name']}**"]
        
        if product.get('description'):
            parts.append(f"  Description: {product['description']}")
        
        if product.get('price'):
            parts.append(f"  Price: {product['currency']} {product['price']}")
        
        if product.get('in_stock') is not None:
            stock_status = "In stock" if product['in_stock'] else "Out of stock"
            parts.append(f"  Status: {stock_status}")
        
        return '\n'.join(parts)
    
    def _format_service(self, service: Dict[str, Any]) -> str:
        """Format service for LLM."""
        parts = [f"**{service['name']}**"]
        
        if service.get('description'):
            parts.append(f"  Description: {service['description']}")
        
        if service.get('duration_minutes'):
            parts.append(f"  Duration: {service['duration_minutes']} minutes")
        
        if service.get('price'):
            parts.append(f"  Price: {service['currency']} {service['price']}")
        
        return '\n'.join(parts)
    
    def _format_availability(self, slot: Dict[str, Any]) -> str:
        """Format availability slot for LLM."""
        return (
            f"Available: {slot.get('start_time')} - {slot.get('end_time')} "
            f"({slot.get('service_name', 'General')})"
        )
    
    def _extract_sources(
        self,
        documents: List[Dict[str, Any]],
        database: List[Dict[str, Any]],
        internet: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Extract source information for attribution."""
        sources = []
        
        # Document sources
        for doc in documents:
            sources.append({
                'type': 'document',
                'name': doc.get('document_name', 'Unknown'),
                'id': doc.get('document_id')
            })
        
        # Database sources
        if database:
            sources.append({
                'type': 'database',
                'name': 'Our Catalog',
                'id': None
            })
        
        # Internet sources
        for result in internet:
            if 'link' in result:
                sources.append({
                    'type': 'internet',
                    'name': result.get('title', 'External Source'),
                    'url': result['link']
                })
        
        return sources
