"""
Catalog browser service for smart pagination and browsing.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from apps.bot.models import BrowseSession
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service

logger = logging.getLogger(__name__)


class CatalogBrowserService:
    """
    Service for managing catalog browsing with pagination.
    
    Handles large catalog navigation with state management,
    filtering, and WhatsApp-friendly pagination.
    """
    
    SESSION_EXPIRY_MINUTES = 10
    DEFAULT_ITEMS_PER_PAGE = 5
    
    @classmethod
    def start_browse_session(
        cls,
        tenant,
        conversation,
        catalog_type,
        search_query='',
        filters=None,
        items_per_page=None
    ):
        """
        Start a new browse session.
        
        Args:
            tenant: Tenant instance
            conversation: Conversation instance
            catalog_type: 'products' or 'services'
            search_query: Optional search query
            filters: Optional dict of filters
            items_per_page: Items per page (default 5)
        
        Returns:
            BrowseSession instance
        """
        # Deactivate any existing active sessions
        BrowseSession.objects.filter(
            tenant=tenant,
            conversation=conversation,
            is_active=True
        ).update(is_active=False)
        
        # Get total items count
        total_items = cls._get_total_items(
            tenant, catalog_type, search_query, filters
        )
        
        # Create new session
        session = BrowseSession.objects.create(
            tenant=tenant,
            conversation=conversation,
            catalog_type=catalog_type,
            current_page=1,
            items_per_page=items_per_page or cls.DEFAULT_ITEMS_PER_PAGE,
            total_items=total_items,
            filters=filters or {},
            search_query=search_query,
            is_active=True,
            expires_at=timezone.now() + timedelta(minutes=cls.SESSION_EXPIRY_MINUTES)
        )
        
        logger.info(
            f"Started browse session {session.id} for {catalog_type} "
            f"({total_items} items, {session.total_pages} pages)"
        )
        
        return session
    
    @classmethod
    def get_active_session(cls, tenant, conversation):
        """
        Get active browse session for conversation.
        
        Returns:
            BrowseSession instance or None
        """
        try:
            session = BrowseSession.objects.get(
                tenant=tenant,
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
        Get items for specific page.
        
        Args:
            session: BrowseSession instance
            page_number: Page number (defaults to current_page)
        
        Returns:
            dict with items, page info, and navigation
        """
        if page_number is not None:
            # Validate page number
            if page_number < 1 or page_number > session.total_pages:
                raise ValueError(f"Invalid page number: {page_number}")
            session.current_page = page_number
            session.save(update_fields=['current_page'])
        
        # Extend expiry
        session.expires_at = timezone.now() + timedelta(minutes=cls.SESSION_EXPIRY_MINUTES)
        session.save(update_fields=['expires_at'])
        
        # Get items for current page
        items = cls._get_items(
            session.tenant,
            session.catalog_type,
            session.search_query,
            session.filters,
            session.start_index,
            session.end_index
        )
        
        return {
            'items': items,
            'page': session.current_page,
            'total_pages': session.total_pages,
            'total_items': session.total_items,
            'start_index': session.start_index + 1,  # 1-indexed for display
            'end_index': session.end_index,
            'has_next': session.has_next_page,
            'has_previous': session.has_previous_page,
        }
    
    @classmethod
    def next_page(cls, session):
        """Navigate to next page."""
        if not session.has_next_page:
            raise ValueError("No next page available")
        return cls.get_page(session, session.current_page + 1)
    
    @classmethod
    def previous_page(cls, session):
        """Navigate to previous page."""
        if not session.has_previous_page:
            raise ValueError("No previous page available")
        return cls.get_page(session, session.current_page - 1)
    
    @classmethod
    def apply_filters(cls, session, filters):
        """
        Apply new filters to session.
        
        Args:
            session: BrowseSession instance
            filters: Dict of filters to apply
        
        Returns:
            Updated session
        """
        # Merge with existing filters
        session.filters.update(filters)
        
        # Recalculate total items
        session.total_items = cls._get_total_items(
            session.tenant,
            session.catalog_type,
            session.search_query,
            session.filters
        )
        
        # Reset to page 1
        session.current_page = 1
        session.expires_at = timezone.now() + timedelta(minutes=cls.SESSION_EXPIRY_MINUTES)
        session.save()
        
        logger.info(
            f"Applied filters to session {session.id}: {filters} "
            f"(now {session.total_items} items)"
        )
        
        return session
    
    @classmethod
    def _get_total_items(cls, tenant, catalog_type, search_query, filters):
        """Get total count of items matching criteria."""
        queryset = cls._build_queryset(tenant, catalog_type, search_query, filters)
        return queryset.count()
    
    @classmethod
    def _get_items(cls, tenant, catalog_type, search_query, filters, start, end):
        """Get items for specific range."""
        queryset = cls._build_queryset(tenant, catalog_type, search_query, filters)
        return list(queryset[start:end])
    
    @classmethod
    def _build_queryset(cls, tenant, catalog_type, search_query, filters):
        """Build queryset with filters and search."""
        if catalog_type == 'products':
            queryset = Product.objects.filter(
                tenant=tenant,
                is_active=True
            ).select_related('category')
            
            # Apply search
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(sku__icontains=search_query)
                )
            
            # Apply filters
            if filters:
                if 'category_id' in filters:
                    queryset = queryset.filter(category_id=filters['category_id'])
                if 'min_price' in filters:
                    queryset = queryset.filter(price__gte=filters['min_price'])
                if 'max_price' in filters:
                    queryset = queryset.filter(price__lte=filters['max_price'])
                if 'in_stock' in filters and filters['in_stock']:
                    queryset = queryset.filter(stock_quantity__gt=0)
        
        elif catalog_type == 'services':
            queryset = Service.objects.filter(
                tenant=tenant,
                is_active=True
            ).select_related('category')
            
            # Apply search
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query)
                )
            
            # Apply filters
            if filters:
                if 'category_id' in filters:
                    queryset = queryset.filter(category_id=filters['category_id'])
                if 'min_price' in filters:
                    queryset = queryset.filter(base_price__gte=filters['min_price'])
                if 'max_price' in filters:
                    queryset = queryset.filter(base_price__lte=filters['max_price'])
        
        else:
            raise ValueError(f"Invalid catalog type: {catalog_type}")
        
        return queryset.order_by('name')
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """Clean up expired browse sessions (background task)."""
        expired_count = BrowseSession.objects.filter(
            expires_at__lt=timezone.now()
        ).update(is_active=False)
        
        if expired_count > 0:
            logger.info(f"Deactivated {expired_count} expired browse sessions")
        
        return expired_count
