"""
Basic tests for analytics functionality.

Tests core analytics features including:
- AnalyticsDaily model creation
- AnalyticsService metric calculation
- Analytics rollup task
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from apps.analytics.models import AnalyticsDaily
from apps.analytics.services import AnalyticsService
from apps.analytics.tasks import rollup_daily_metrics, _aggregate_tenant_metrics
from apps.tenants.models import Tenant, SubscriptionTier


@pytest.mark.django_db
class TestAnalyticsDailyModel:
    """Test AnalyticsDaily model."""
    
    def test_create_analytics_daily(self):
        """Test creating an AnalyticsDaily record."""
        # Create tenant
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29,
            yearly_price=278
        )
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            subscription_tier=tier
        )
        
        # Create analytics record
        today = date.today()
        analytics = AnalyticsDaily.objects.create(
            tenant=tenant,
            date=today,
            msgs_in=100,
            msgs_out=80,
            conversations=20,
            orders=5,
            revenue=Decimal('500.00'),
            bookings=3
        )
        
        assert analytics.tenant == tenant
        assert analytics.date == today
        assert analytics.msgs_in == 100
        assert analytics.msgs_out == 80
        assert analytics.total_messages == 180
        assert analytics.avg_order_value == Decimal('100.00')
    
    def test_unique_constraint(self):
        """Test unique constraint on (tenant, date)."""
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29,
            yearly_price=278
        )
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            subscription_tier=tier
        )
        
        today = date.today()
        
        # Create first record
        AnalyticsDaily.objects.create(
            tenant=tenant,
            date=today,
            msgs_in=100
        )
        
        # Attempting to create duplicate should fail
        with pytest.raises(Exception):
            AnalyticsDaily.objects.create(
                tenant=tenant,
                date=today,
                msgs_in=200
            )


@pytest.mark.django_db
class TestAnalyticsService:
    """Test AnalyticsService."""
    
    def test_get_overview(self):
        """Test getting overview metrics."""
        # Create tenant
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29,
            yearly_price=278
        )
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            subscription_tier=tier
        )
        
        # Create analytics data for last 7 days
        today = date.today()
        for i in range(7):
            day = today - timedelta(days=i)
            AnalyticsDaily.objects.create(
                tenant=tenant,
                date=day,
                msgs_in=10 * (i + 1),
                msgs_out=8 * (i + 1),
                conversations=2 * (i + 1),
                orders=1,
                revenue=Decimal('100.00'),
                bookings=1
            )
        
        # Get overview
        service = AnalyticsService(tenant)
        overview = service.get_overview('7d')
        
        assert overview['msgs_in'] == sum(10 * (i + 1) for i in range(7))
        assert overview['msgs_out'] == sum(8 * (i + 1) for i in range(7))
        assert overview['orders'] == 7
        assert overview['revenue'] == 700.0
    
    def test_get_daily_metrics(self):
        """Test getting daily metrics for a specific date."""
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29,
            yearly_price=278
        )
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            subscription_tier=tier
        )
        
        today = date.today()
        analytics = AnalyticsDaily.objects.create(
            tenant=tenant,
            date=today,
            msgs_in=100,
            msgs_out=80
        )
        
        service = AnalyticsService(tenant)
        daily = service.get_daily_metrics(today)
        
        assert daily is not None
        assert daily.msgs_in == 100
        assert daily.msgs_out == 80


@pytest.mark.django_db
class TestAnalyticsRollupTask:
    """Test analytics rollup Celery task."""
    
    def test_aggregate_tenant_metrics(self):
        """Test aggregating metrics for a tenant."""
        # Create tenant
        tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29,
            yearly_price=278
        )
        tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            whatsapp_number='+1234567890',
            subscription_tier=tier,
            status='active'
        )
        
        # Aggregate metrics for today
        today = date.today()
        metrics = _aggregate_tenant_metrics(tenant, today)
        
        # Should return a dict with all metric fields
        assert 'msgs_in' in metrics
        assert 'msgs_out' in metrics
        assert 'conversations' in metrics
        assert 'orders' in metrics
        assert 'revenue' in metrics
        assert 'bookings' in metrics
        
        # All should be 0 or None since no data exists
        assert metrics['msgs_in'] == 0
        assert metrics['msgs_out'] == 0
        assert metrics['conversations'] == 0
