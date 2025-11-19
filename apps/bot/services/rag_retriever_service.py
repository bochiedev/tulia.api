"""
RAG retriever service that orchestrates multi-source retrieval.
"""
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from apps.bot.services.document_store_service import DocumentStoreService
from apps.bot.services.database_store_service import DatabaseStoreService
from apps.bot.services.internet_search_service import InternetSearchService

logger = logging.getLogger(__name__)


class RAGRetrieverService:
    """
    Service that orchestrates retrieval from multiple sources:
    - Documents (uploaded PDFs/TXT)
    - Database (products, services, appointments)
    - Internet (product enrichment)
    """
    
    def __init__(self, tenant, config=None):
        """
        Initialize RAG retriever service.
        
        Args:
            tenant: Tenant instance
            config: AgentConfiguration instance (optional)
        """
        self.tenant = tenant
        self.config = config or tenant.agent_configuration
        
        # Initialize source services
        self.document_store = DocumentStoreService.create_for_tenant(tenant)
        self.database_store = DatabaseStoreService.create_for_tenant(tenant)
        self.internet_search = InternetSearchService.create_for_tenant(tenant)
    
    def retrieve(
        self,
        query: str,
        query_type: str = 'general',
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Retrieve relevant information from all enabled sources.
        
        Args:
            query: Search query
            query_type: Type of query (product, service, general)
            context: Additional context (conversation history, etc.)
        
        Returns:
            Dict with results from all sources
        """
        start_time = time.time()
        
        # Analyze query to determine relevant sources
        sources_to_query = self._analyze_query(query, query_type)
        
        logger.info(
            f"RAG retrieval for query: '{query[:50]}...' "
            f"(type: {query_type}, sources: {sources_to_query})"
        )
        
        # Retrieve from sources in parallel
        results = self._parallel_retrieve(query, sources_to_query, context)
        
        # Rank and combine results
        ranked_results = self._rank_results(results, query_type)
        
        retrieval_time = time.time() - start_time
        
        logger.info(
            f"RAG retrieval complete in {retrieval_time:.3f}s: "
            f"{len(ranked_results.get('documents', []))} docs, "
            f"{len(ranked_results.get('database', []))} db, "
            f"{len(ranked_results.get('internet', []))} internet"
        )
        
        return {
            **ranked_results,
            'retrieval_time': retrieval_time,
            'query': query,
            'query_type': query_type
        }
    
    def _analyze_query(
        self,
        query: str,
        query_type: str
    ) -> List[str]:
        """
        Analyze query to determine which sources to query.
        
        Args:
            query: Search query
            query_type: Type of query
        
        Returns:
            List of source names to query
        """
        sources = []
        
        # Check configuration
        if self.config.enable_document_retrieval:
            sources.append('documents')
        
        if self.config.enable_database_retrieval:
            sources.append('database')
        
        # Only use internet for product queries if enabled
        if self.config.enable_internet_enrichment and query_type == 'product':
            sources.append('internet')
        
        return sources
    
    def _parallel_retrieve(
        self,
        query: str,
        sources: List[str],
        context: Dict[str, Any] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve from multiple sources in parallel.
        
        Args:
            query: Search query
            sources: List of sources to query
            context: Additional context
        
        Returns:
            Dict mapping source names to results
        """
        results = {
            'documents': [],
            'database': [],
            'internet': []
        }
        
        # Create retrieval tasks
        tasks = {}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            if 'documents' in sources:
                tasks[executor.submit(
                    self._retrieve_from_documents,
                    query
                )] = 'documents'
            
            if 'database' in sources:
                tasks[executor.submit(
                    self._retrieve_from_database,
                    query,
                    context
                )] = 'database'
            
            if 'internet' in sources:
                tasks[executor.submit(
                    self._retrieve_from_internet,
                    query,
                    context
                )] = 'internet'
            
            # Collect results with timeout
            for future in as_completed(tasks, timeout=5.0):
                source = tasks[future]
                try:
                    source_results = future.result(timeout=1.0)
                    results[source] = source_results
                except Exception as e:
                    logger.error(f"Error retrieving from {source}: {e}")
                    results[source] = []
        
        return results
    
    def _retrieve_from_documents(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve from uploaded documents."""
        try:
            max_results = self.config.max_document_results
            return self.document_store.search_documents(
                query=query,
                top_k=max_results
            )
        except Exception as e:
            logger.error(f"Document retrieval error: {e}")
            return []
    
    def _retrieve_from_database(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve from database (products, services)."""
        try:
            max_results = self.config.max_database_results
            results = []
            
            # Get products
            products = self.database_store.get_product_context(
                query=query,
                max_results=max_results // 2
            )
            results.extend(products)
            
            # Get services
            services = self.database_store.get_service_context(
                query=query,
                max_results=max_results // 2
            )
            results.extend(services)
            
            return results
        except Exception as e:
            logger.error(f"Database retrieval error: {e}")
            return []
    
    def _retrieve_from_internet(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve from internet search."""
        try:
            max_results = self.config.max_internet_results
            
            # Extract product name from context if available
            product_name = query
            category = None
            
            if context and 'product' in context:
                product_name = context['product'].get('name', query)
                category = context['product'].get('category')
            
            return self.internet_search.search_product_info(
                product_name=product_name,
                category=category,
                max_results=max_results
            )
        except Exception as e:
            logger.error(f"Internet retrieval error: {e}")
            return []
    
    def _rank_results(
        self,
        results: Dict[str, List[Dict[str, Any]]],
        query_type: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Rank and filter results by relevance.
        
        Args:
            results: Results from all sources
            query_type: Type of query
        
        Returns:
            Ranked results
        """
        # For now, just return results as-is
        # Could implement more sophisticated ranking based on:
        # - Source reliability
        # - Recency
        # - Relevance scores
        # - Query type
        
        return results
    
    @classmethod
    def create_for_tenant(cls, tenant) -> 'RAGRetrieverService':
        """
        Create RAG retriever service for a tenant.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            RAGRetrieverService instance
        """
        return cls(tenant)
