"""
Integration tests for TenantSettings with other modules.

Tests the interaction between TenantSettings and:
- Twilio service (messaging)
- WooCommerce service (catalog sync)
- Shopify service (catalog sync)
- Webhook verification
- API authentication
"""
import pytest
from unittest.mock import patch, Mock
from decimal import Decimal

from apps.tenants.models import Tenant, TenantSettings, SubscriptionTier
from apps.catalog.models import Product


@pytest.fixture
def subscription_tier():
    """Create subscription tier."""
    return SubscriptionTier.objects.create(
        name='Growth',
        monthly_price=99.00,
        yearly_price=950.00,
        monthly_messages=10000,
        max_products=1000
    )


@pytest.fixture
def tenant_with_settings(subscription_tier):
    """Create tenant with configured settings."""
    tenant = Tenant.objects.create(
        name='Integration Test Store',
        slug='integration-test',
        whatsapp_number='+14155551234',
        twilio_sid='AC_old_sid',  # Old location (deprecated)
        twilio_token='old_token',
        webhook_secret='old_secret',
        subscription_tier=subscription_tier
    )
    
    # Configure settings (new location)
    settings = tenant.settings
    settings.twilio_sid = 'AC_new_sid'
    settings.twilio_token = 'new_token'
    settings.twilio_webhook_secret = 'new_secret'
    settings.woo_store_url = 'https://test-store.com'
    settings.woo_consumer_key = 'ck_test123'
    settings.woo_consumer_secret = 'cs_test456'
    settings.save()
    
    return tenant


@pytest.mark.django_db
class TestTwilioIntegration:
    """Test Twilio service integration with TenantSettings."""
    
    def test_twilio_service_uses_settings_credentials(self, tenant_with_settings):
        """Test that Twilio service uses TenantSettings credentials."""
        from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
        
        service = create_twilio_service_for_tenant(tenant_with_settings)
        
        # Should use NEW credentials from TenantSettings
        assert service.account_sid == 'AC_new_sid'
        assert service.auth_token == 'new_token'
        assert service.from_number == '+14155551234'
    
    def test_twilio_service_fallback_to_tenant(self, subscription_tier):
        """Test fallback to Tenant model when TenantSettings not configured."""
        tenant = Tenant.objects.create(
            name='Fallback Test',
            slug='fallback-test',
            whatsapp_number='+14155559999',
            twilio_sid='AC_fallback',
            twilio_token='fallback_token',
            webhook_secret='fallback_secret',
            subscription_tier=subscription_tier
        )
        
        # Clear TenantSettings credentials
        settings = tenant.settings
        settings.twilio_sid = None
        settings.twilio_token = None
        settings.save()
        
        from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
        
        service = create_twilio_service_for_tenant(tenant)
        
        # Should fallback to Tenant model
        assert service.account_sid == 'AC_fallback'
        assert service.auth_token == 'fallback_token'


@pytest.mark.django_db
class TestWooCommerceIntegration:
    """Test WooCommerce service integration with TenantSettings."""
    
    def test_woo_service_uses_settings_credentials(self, tenant_with_settings):
        """Test that WooCommerce service uses TenantSettings credentials."""
        from apps.integrations.services.woo_service import create_woo_service_for_tenant
        
        service = create_woo_service_for_tenant(tenant_with_settings)
        
        assert service.store_url == 'https://test-store.com'
        assert service.consumer_key == 'ck_test123'
        assert service.consumer_secret == 'cs_test456'
    
    def test_woo_sync_with_settings(self, tenant_with_settings):
        """Test product sync using TenantSettings credentials."""
        from apps.integrations.services.woo_service import create_woo_service_for_tenant
        
        service = create_woo_service_for_tenant(tenant_with_settings)
        
        # Mock API response
        mock_product = {
            'id': 123,
            'name': 'Test Product',
            'price': '29.99',
            'status': 'publish',
            'type': 'simple',
            'images': [],
            'categories': [],
            'tags': []
        }
        
        with patch.object(service.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = [mock_product]
            mock_get.return_value = mock_response
            
            result = service.sync_products(tenant_with_settings)
        
        assert result['synced_count'] == 1
        assert Product.objects.filter(tenant=tenant_with_settings).count() == 1


@pytest.mark.django_db
class TestCredentialMigration:
    """Test credential migration from Tenant to TenantSettings."""
    
    def test_migration_command_dry_run(self, subscription_tier):
        """Test migration command in dry-run mode."""
        from django.core.management import call_command
        from io import StringIO
        
        # Create tenant with old credentials
        tenant = Tenant.objects.create(
            name='Migration Test',
            slug='migration-test',
            whatsapp_number='+14155558888',
            twilio_sid='AC_migrate',
            twilio_token='migrate_token',
            webhook_secret='migrate_secret',
            subscription_tier=subscription_tier
        )
        
        # Clear settings
        settings = tenant.settings
        settings.twilio_sid = None
        settings.twilio_token = None
        settings.twilio_webhook_secret = None
        settings.save()
        
        # Run migration in dry-run mode
        out = StringIO()
        call_command('migrate_tenant_credentials', '--dry-run', stdout=out)
        
        # Verify nothing was migrated
        settings.refresh_from_db()
        assert settings.twilio_sid is None
        assert 'DRY RUN' in out.getvalue()
    
    def test_migration_command_actual(self, subscription_tier):
        """Test actual credential migration."""
        from django.core.management import call_command
        
        # Create tenant with old credentials
        tenant = Tenant.objects.create(
            name='Migration Test 2',
            slug='migration-test-2',
            whatsapp_number='+14155557777',
            twilio_sid='AC_migrate2',
            twilio_token='migrate_token2',
            webhook_secret='migrate_secret2',
            subscription_tier=subscription_tier
        )
        
        # Clear settings
        settings = tenant.settings
        settings.twilio_sid = None
        settings.twilio_token = None
        settings.twilio_webhook_secret = None
        settings.save()
        
        # Run actual migration
        call_command('migrate_tenant_credentials')
        
        # Verify credentials were migrated
        settings.refresh_from_db()
        assert settings.twilio_sid == 'AC_migrate2'
        assert settings.twilio_token == 'migrate_token2'
        assert settings.twilio_webhook_secret == 'migrate_secret2'


@pytest.mark.django_db
class TestFeatureFlagsIntegration:
    """Test feature flags integration across modules."""
    
    def test_feature_flag_controls_behavior(self, tenant_with_settings):
        """Test that feature flags control module behavior."""
        settings = tenant_with_settings.settings
        
        # Disable AI responses
        settings.feature_flags['ai_responses_enabled'] = False
        settings.save()
        
        assert not settings.is_feature_enabled('ai_responses_enabled')
        
        # Enable AI responses
        settings.feature_flags['ai_responses_enabled'] = True
        settings.save()
        
        assert settings.is_feature_enabled('ai_responses_enabled')


@pytest.mark.django_db
class TestNotificationSettings:
    """Test notification settings integration."""
    
    def test_notification_preferences(self, tenant_with_settings):
        """Test notification preferences control notifications."""
        settings = tenant_with_settings.settings
        
        # Configure notifications
        settings.notification_settings = {
            'email': {
                'order_received': True,
                'low_stock': False
            },
            'sms': {
                'critical_alerts': True
            }
        }
        settings.save()
        
        # Check preferences
        assert settings.is_notification_enabled('email', 'order_received')
        assert not settings.is_notification_enabled('email', 'low_stock')
        assert settings.is_notification_enabled('sms', 'critical_alerts')
        assert not settings.is_notification_enabled('sms', 'non_existent')
