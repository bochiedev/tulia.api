"""
Catalog browser service for smart pagination.

Implements Task 20.2 from AI agent spec: pagination logic for browsing
large catalogs with state management and filtering.
"""
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from apps.bot.models import BrowseSession
from apps.catalog.models import Product
from apps.services.models import Service
import logging

logger = logging.getLogger(__name__)


class CatalogBrowserService:
    """
    Service for managing catalog browsing sessions with pagination.
    
    Enables customers to browse large catalogs (100+ items) with:
    - Pagination (5 items per page by default)
    - State persistence across messages
    - Filter application (category, price range, etc.)
    - Search query support
    - Session expiration (10 minutes)
    
    TENANT SCOPING: All operations are tenant-scoped via conversation.
    """
    
    DEFAULT_ITEMS_PER_PAGE = 5
    SESSION_EXPIRATION_MINUTES = 10
    
    @classmethod
    def start_browse_session(
        cls,
        conversation,
        catalog_type,
        filters=None,
        search_query='',
        items_per_page=None
    ):
        """
        Start a new browse session for a conversation.
        
        Args:
            conversation: Conversation instance
            catalog_type: 'products' or 'services'
            filters: Dict of filters to apply (e.g., {'category': 'Electronics'})
            search_query: Search query string
            items_per_page: Number of items per page (default: 5)
        
        Returns:
            BrowseSession instance
        
        Raises:
            ValueError: If catalog_type is invalid
        """
        if catalog_type not in ['products', 'services']:
            raise ValueError(f"Invalid catalog_type: {catalog_type}")
        
        # Deactivate any existing active sessions for this conversation
        BrowseSession.objects.filter(
            conversation=conversation,
            is_active=True
        ).update(is_active=False)
        
        # Get total items count
        total_items = cls._count_items(
            tenant=conversation.tenant,
            catalog_type=catalog_type,
            filters=filters or {},
            search_query=search_query
        )
        
        # Create new session
        session = BrowseSession.objects.create(
            tenant=conversation.tenant,
            conversation=conversation,
            catalog_type=catalog_type,
            current_page=1,
            items_per_page=items_per_page or cls.DEFAULT_ITEMS_PER_PAGE,
            total_items=total_items,
            filters=filters or {},
            search_query=search_query,
            is_active=True,
            expires_at=timezone.now() + timedelta(minutes=cls.SESSION_EXPIRATION_MINUTES)
        )
        
        logger.info(
            f"Started browse session {session.id} for conversation {conversation.id}: "
            f"{catalog_type}, {total_items} items, {session.total_pages} pages"
        )
        
        return session
    
    @classmethod
    def get_active_session(cls, conversation):
        """
        Get the active browse session for a conversation.
        
        Args:
            conversation: Conversation instance
        
        Returns:
            BrowseSession instance or None if no active session
        """
        try:
            session = BrowseSession.objects.get(
                conversation=conversation,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            return session
        except BrowseSession.DoesNotExist:
            return None
    
    @classmethod
    def get_page(cls, session, page_number=None):
        """
        Get items for a specific page in the browse session.
        
        Args:
            session: BrowseSession instance
            page_number: Page number to retrieve (default: current_page)
        
        Returns:
            Dict with:
                - items: List of Product or Service instances
                - page: Current page number
                - total_pages: Total number of pages
                - has_next: Boolean
                - has_previous: Boolean
                - start_index: Start index (1-indexed for display)
                - end_index: End index (1-indexed for display)
        
        Raises:
            ValueError: If page_number is out of range
        """
        if page_number is None:
            page_number = session.current_page
        
        # Validate page number
        if page_number < 1 or page_number > session.total_pages:
            raise ValueError(
                f"Page {page_number} out of range (1-{session.total_pages})"
            )
        
        # Update current page
        if page_number != session.current_page:
            session.current_page = page_number
            session.save(update_fields=['current_page'])
        
        # Extend expiration
        session.expires_at = timezone.now() + timedelta(
            minutes=cls.SESSION_EXPIRATION_MINUTES
        )
        session.save(update_fields=['expires_at'])
        
        # Get items for this page
        items = cls._get_items(
            tenant=session.tenant,
            catalog_type=session.catalog_type,
            filters=session.filters,
            search_query=session.search_query,
            start_index=session.start_index,
            end_index=session.end_index
        )
        
        return {
            'items': items,
            'page': session.current_page,
            'total_pages': session.total_pages,
            'has_next': session.has_next_page,
            'has_previous': session.has_previous_page,
            'start_index': session.start_index + 1,  # 1-indexed for display
            'end_index': min(session.end_index, session.total_items),  # 1-indexed
            'total_items': session.total_items
        }
    
    @classmethod
    def next_page(cls, session):
        """
        Navigate to the next page.
        
        Args:
            session: BrowseSession instance
        
        Returns:
            Dict with page data (same as get_page)
        
        Raises:
            ValueError: If already on last page
        """
        if not session.has_next_page:
            raise ValueError("Already on last page")
        
        return cls.get_page(session, session.current_page + 1)
    
    @classmethod
    def previous_page(cls, session):
        """
        Navigate to the previous page.
        
        Args:
            session: BrowseSession instance
        
        Returns:
            Dict with page data (same as get_page)
        
        Raises:
            ValueError: If already on first page
        """
        if not session.has_previous_page:
            raise ValueError("Already on first page")
        
        return cls.get_page(session, session.current_page - 1)
    
    @classmethod
    def apply_filters(cls, session, filters):
        """
        Apply new filters to the browse session.
        
        This creates a new result set and resets to page 1.
        
        Args:
            session: BrowseSession instance
            filters: Dict of filters to apply
        
        Returns:
            Updated BrowseSession instance
        """
        # Update filters
        session.filters = filters
        
        # Recalculate total items
        session.total_items = cls._count_items(
            tenant=session.tenant,
            catalog_type=session.catalog_type,
            filters=filters,
            search_query=session.search_query
        )
        
        # Reset to page 1
        session.current_page = 1
        
        # Extend expiration
        session.expires_at = timezone.now() + timedelta(
            minutes=cls.SESSION_EXPIRATION_MINUTES
        )
        
        session.save(update_fields=['filters', 'total_items', 'current_page', 'expires_at'])
        
        logger.info(
            f"Applied filters to session {session.id}: {filters}, "
            f"now {session.total_items} items"
        )
        
        return session
    
    @classmethod
    def end_session(cls, session):
        """
        End a browse session.
        
        Args:
            session: BrowseSession instance
        """
        session.is_active = False
        session.save(update_fields=['is_active'])
        
        logger.info(f"Ended browse session {session.id}")
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """
        Clean up expired browse sessions.
        
        Should be called periodically (e.g., via Celery task).
        
        Returns:
            Number of sessions cleaned up
        """
        count = BrowseSession.objects.filter(
            is_active=True,
            expires_at__lte=timezone.now()
        ).update(is_active=False)
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired browse sessions")
        
        return count
    
    # Private helper methods
    
    @classmethod
    def _count_items(cls, tenant, catalog_type, filters, search_query):
        """Count total items matching filters and search."""
        queryset = cls._build_queryset(tenant, catalog_type, filters, search_query)
        return queryset.count()
    
    @classmethod
    def _get_items(cls, tenant, catalog_type, filters, search_query, start_index, end_index):
        """Get items for a specific page range."""
        queryset = cls._build_queryset(tenant, catalog_type, filters, search_query)
        return list(queryset[start_index:end_index])
    
    @classmethod
    def _build_queryset(cls, tenant, catalog_type, filters, search_query):
        """Build queryset with filters and search."""
        if catalog_type == 'products':
            queryset = Product.objects.filter(tenant=tenant, is_active=True)
            
            # Apply filters
            if filters.get('category'):
                queryset = queryset.filter(metadata__category__icontains=filters['category'])
            
            if filters.get('min_price'):
                queryset = queryset.filter(price__gte=filters['min_price'])
            
            if filters.get('max_price'):
                queryset = queryset.filter(price__lte=filters['max_price'])
            
            if filters.get('in_stock'):
                queryset = queryset.filter(stock__gt=0)
            
            # Apply search
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(sku__icontains=search_query)
                )
            
            queryset = queryset.order_by('title')
            
        elif catalog_type == 'services':
            queryset = Service.objects.filter(tenant=tenant, is_active=True)
            
            # Apply filters
            if filters.get('category'):
                queryset = queryset.filter(metadata__category__icontains=filters['category'])
            
            if filters.get('min_price'):
                queryset = queryset.filter(base_price__gte=filters['min_price'])
            
            if filters.get('max_price'):
                queryset = queryset.filter(base_price__lte=filters['max_price'])
            
            if filters.get('duration_minutes'):
                queryset = queryset.filter(metadata__duration_minutes=filters['duration_minutes'])
            
            # Apply search
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query)
                )
            
            queryset = queryset.order_by('title')
        
        else:
            raise ValueError(f"Invalid catalog_type: {catalog_type}")
        
        return queryset
