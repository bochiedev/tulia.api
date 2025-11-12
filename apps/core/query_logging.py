"""
Database query logging middleware for development.

Logs slow queries and N+1 query patterns to help identify performance issues.
"""
import logging
import time
from django.conf import settings
from django.db import connection, reset_queries

logger = logging.getLogger(__name__)


class QueryLoggingMiddleware:
    """
    Middleware to log database queries in development.
    
    Features:
    - Logs total query count per request
    - Logs slow queries (> 100ms)
    - Detects potential N+1 query patterns
    - Only active when DEBUG=True
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = settings.DEBUG
    
    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)
        
        # Reset queries before request
        reset_queries()
        
        # Track request start time
        start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate request duration
        duration = time.time() - start_time
        
        # Get query information
        queries = connection.queries
        query_count = len(queries)
        
        # Calculate total query time
        query_time = sum(float(q['time']) for q in queries)
        
        # Log summary
        logger.info(
            f"[Query Stats] {request.method} {request.path} | "
            f"Queries: {query_count} | "
            f"Query Time: {query_time:.3f}s | "
            f"Total Time: {duration:.3f}s"
        )
        
        # Log slow queries (> 100ms)
        slow_queries = [q for q in queries if float(q['time']) > 0.1]
        if slow_queries:
            logger.warning(
                f"[Slow Queries] {len(slow_queries)} slow queries detected "
                f"for {request.method} {request.path}"
            )
            for i, query in enumerate(slow_queries, 1):
                logger.warning(
                    f"  Slow Query #{i} ({query['time']}s): "
                    f"{query['sql'][:200]}..."
                )
        
        # Detect potential N+1 patterns (many similar queries)
        if query_count > 20:
            # Group queries by SQL pattern (simplified)
            query_patterns = {}
            for q in queries:
                # Extract table name from SQL
                sql = q['sql'].lower()
                if 'from' in sql:
                    table_part = sql.split('from')[1].split('where')[0].strip()
                    table_name = table_part.split()[0].strip('`"')
                    query_patterns[table_name] = query_patterns.get(table_name, 0) + 1
            
            # Find tables with many queries
            repeated_queries = {
                table: count for table, count in query_patterns.items()
                if count > 10
            }
            
            if repeated_queries:
                logger.warning(
                    f"[N+1 Pattern] Potential N+1 query pattern detected "
                    f"for {request.method} {request.path}: {repeated_queries}"
                )
        
        # Add query count to response headers in development
        response['X-Query-Count'] = str(query_count)
        response['X-Query-Time'] = f"{query_time:.3f}"
        
        return response


class QueryCountContext:
    """
    Context manager to track queries in a specific code block.
    
    Usage:
        with QueryCountContext("Loading products"):
            products = Product.objects.all()[:10]
    """
    
    def __init__(self, label="Code block"):
        self.label = label
        self.initial_count = 0
        self.initial_queries = []
    
    def __enter__(self):
        reset_queries()
        self.initial_count = len(connection.queries)
        self.initial_queries = list(connection.queries)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        final_count = len(connection.queries)
        query_count = final_count - self.initial_count
        
        new_queries = connection.queries[self.initial_count:]
        query_time = sum(float(q['time']) for q in new_queries)
        
        logger.debug(
            f"[Query Context] {self.label} | "
            f"Queries: {query_count} | "
            f"Time: {query_time:.3f}s"
        )
        
        # Log individual queries if there are many
        if query_count > 5:
            for i, query in enumerate(new_queries, 1):
                logger.debug(
                    f"  Query #{i} ({query['time']}s): "
                    f"{query['sql'][:150]}..."
                )
