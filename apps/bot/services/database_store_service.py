"""
Database store service for retrieving context from database.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class DatabaseStoreService:
    """
    Service for retrieving context from database (products, services, appointments).
    """
    
    def __init__(self, tenant):
        """
        Initialize database store service.
        
        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant
    
    def get_product_context(
        self,
        query: str = None,
        product_ids: List[str] = None,
        category: str = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get product context from database.
        
        Args:
            query: Search query for fuzzy matching
            product_ids: Specific product IDs to retrieve
            category: Filter by category
            max_results: Maximum number of results
        
        Returns:
            List of product context dicts
        """
        from apps.catalog.models import Product
        
        # Build query
        queryset = Product.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).select_related('category')
        
        # Filter by IDs
        if product_ids:
            queryset = queryset.filter(id__in=product_ids)
        
        # Filter by category
        if category:
            queryset = queryset.filter(
                Q(category__name__icontains=category) |
                Q(category__slug__icontains=category)
            )
        
        # Fuzzy search by query
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(sku__icontains=query)
            )
        
        # Limit results
        products = queryset[:max_results]
        
        # Format context
        context = []
        for product in products:
            context.append({
                'id': str(product.id),
                'type': 'product',
                'name': product.name,
                'description': product.description or '',
                'price': float(product.price) if product.price else None,
                'currency': product.currency,
                'sku': product.sku,
                'category': product.category.name if product.category else None,
                'in_stock': product.stock_quantity > 0 if product.stock_quantity is not None else True,
                'stock_quantity': product.stock_quantity,
                'needs_enrichment': self._needs_enrichment(product),
                'source': 'database'
            })
        
        logger.info(
            f"Retrieved {len(context)} products from database "
            f"(query: {query}, category: {category})"
        )
        
        return context
    
    def get_service_context(
        self,
        query: str = None,
        service_ids: List[str] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get service context from database.
        
        Args:
            query: Search query for fuzzy matching
            service_ids: Specific service IDs to retrieve
            max_results: Maximum number of results
        
        Returns:
            List of service context dicts
        """
        from apps.services.models import Service
        
        # Build query
        queryset = Service.objects.filter(
            tenant=self.tenant,
            is_active=True
        )
        
        # Filter by IDs
        if service_ids:
            queryset = queryset.filter(id__in=service_ids)
        
        # Fuzzy search by query
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Limit results
        services = queryset[:max_results]
        
        # Format context
        context = []
        for service in services:
            context.append({
                'id': str(service.id),
                'type': 'service',
                'name': service.name,
                'description': service.description or '',
                'duration_minutes': service.duration_minutes,
                'price': float(service.price) if service.price else None,
                'currency': service.currency,
                'source': 'database'
            })
        
        logger.info(
            f"Retrieved {len(context)} services from database "
            f"(query: {query})"
        )
        
        return context
    
    def get_appointment_availability(
        self,
        service_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get appointment availability from database.
        
        Args:
            service_id: Filter by service ID
            start_date: Start of date range
            end_date: End of date range
            max_results: Maximum number of slots
        
        Returns:
            List of available time slots
        """
        from apps.services.models import AvailabilityWindow, Appointment
        
        # Default date range (next 7 days)
        if not start_date:
            start_date = timezone.now()
        if not end_date:
            end_date = start_date + timedelta(days=7)
        
        # Get availability windows
        windows_query = AvailabilityWindow.objects.filter(
            tenant=self.tenant,
            is_active=True,
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        if service_id:
            windows_query = windows_query.filter(service_id=service_id)
        
        windows = windows_query.order_by('start_time')[:max_results]
        
        # Check for existing appointments
        appointment_times = set(
            Appointment.objects.filter(
                tenant=self.tenant,
                status__in=['confirmed', 'pending'],
                start_time__gte=start_date,
                start_time__lte=end_date
            ).values_list('start_time', flat=True)
        )
        
        # Format availability
        availability = []
        for window in windows:
            # Check if slot is booked
            is_available = window.start_time not in appointment_times
            
            if is_available:
                availability.append({
                    'id': str(window.id),
                    'type': 'availability',
                    'service_id': str(window.service_id) if window.service_id else None,
                    'service_name': window.service.name if window.service else None,
                    'start_time': window.start_time.isoformat(),
                    'end_time': window.end_time.isoformat(),
                    'capacity': window.capacity,
                    'available': is_available,
                    'source': 'database'
                })
        
        logger.info(
            f"Retrieved {len(availability)} available slots from database "
            f"(service: {service_id}, range: {start_date} to {end_date})"
        )
        
        return availability
    
    def needs_enrichment(self, product_id: str) -> bool:
        """
        Check if a product needs internet enrichment.
        
        Args:
            product_id: Product ID
        
        Returns:
            True if product needs enrichment
        """
        from apps.catalog.models import Product
        
        try:
            product = Product.objects.get(
                id=product_id,
                tenant=self.tenant
            )
            return self._needs_enrichment(product)
        except Product.DoesNotExist:
            return False
    
    def _needs_enrichment(self, product) -> bool:
        """
        Internal method to check if product needs enrichment.
        
        Args:
            product: Product instance
        
        Returns:
            True if product needs enrichment
        """
        # Check if description is minimal
        description = product.description or ''
        if len(description.strip()) < 50:
            return True
        
        # Check if product has brand/model indicators
        # (could be enhanced with brand database)
        name_lower = product.name.lower()
        brand_indicators = [
            'samsung', 'apple', 'nike', 'adidas', 'sony',
            'lg', 'hp', 'dell', 'lenovo', 'asus'
        ]
        
        has_brand = any(brand in name_lower for brand in brand_indicators)
        
        # Products with brands but minimal descriptions need enrichment
        if has_brand and len(description.strip()) < 100:
            return True
        
        return False
    
    @classmethod
    def create_for_tenant(cls, tenant) -> 'DatabaseStoreService':
        """
        Create database store service for a tenant.
        
        Args:
            tenant: Tenant instance
        
        Returns:
            DatabaseStoreService instance
        """
        return cls(tenant)
