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
        assert service.from_number == 'whatsapp:+14155551234'  # Service adds whatsapp: prefix
    
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



@pytest.mark.django_db
class TestBusinessSettingsAPI:
    """Test business settings API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create API client."""
        from rest_framework.test import APIClient
        return APIClient()
    
    def _get_jwt_token(self, user):
        """Helper to generate JWT token for user."""
        from apps.rbac.services import AuthService
        return AuthService.generate_jwt(user)
    
    def test_get_business_settings(self, tenant_with_settings, client):
        """Test GET /v1/settings/business returns current settings."""
        from apps.rbac.models import User, TenantUser, Role
        
        # Create user with access
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            email_verified=True
        )
        
        # Get or create Owner role (may already exist from signal)
        owner_role, _ = Role.objects.get_or_create(
            tenant=tenant_with_settings,
            name='Owner',
            defaults={'is_system': True}
        )
        
        # Create tenant user
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=owner_role)
        
        # Set up business settings
        tenant_with_settings.timezone = 'America/New_York'
        tenant_with_settings.quiet_hours_start = '22:00'
        tenant_with_settings.quiet_hours_end = '08:00'
        tenant_with_settings.save()
        
        settings = tenant_with_settings.settings
        settings.business_hours = {
            'monday': {'open': '09:00', 'close': '17:00', 'closed': False},
            'tuesday': {'open': '09:00', 'close': '17:00', 'closed': False}
        }
        settings.notification_settings = {
            'email': {'order_received': True}
        }
        settings.save()
        
        # Make request with JWT token
        token = self._get_jwt_token(user)
        response = client.get(
            '/v1/settings/business',
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['timezone'] == 'America/New_York'
        assert data['quiet_hours']['enabled'] is True
        assert data['quiet_hours']['start'] == '22:00:00'
        assert data['quiet_hours']['end'] == '08:00:00'
        assert 'monday' in data['business_hours']
        assert data['business_hours']['monday']['open'] == '09:00'
        assert 'email' in data['notification_preferences']
    
    def test_update_business_settings_with_users_manage_scope(self, tenant_with_settings, client):
        """Test PUT /v1/settings/business with users:manage scope."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Create user with users:manage scope
        user = User.objects.create(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        
        # Create role with users:manage permission
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Admin',
            is_system=True
        )
        
        permission = Permission.objects.get_or_create(
            code='users:manage',
            defaults={'name': 'Manage Users', 'description': 'Manage users and settings'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Update business settings
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'timezone': 'Europe/London',
                'business_hours': {
                    'monday': {'open': '08:00', 'close': '18:00', 'closed': False},
                    'sunday': {'closed': True}
                },
                'quiet_hours': {
                    'enabled': True,
                    'start': '23:00',
                    'end': '07:00'
                },
                'notification_preferences': {
                    'email': {
                        'order_received': True,
                        'low_stock': True
                    },
                    'sms': {
                        'critical_alerts': True
                    }
                }
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['message'] == 'Business settings updated successfully'
        assert data['settings']['timezone'] == 'Europe/London'
        assert data['settings']['business_hours']['monday']['open'] == '08:00'
        assert data['settings']['quiet_hours']['start'] == '23:00:00'
        
        # Verify database was updated
        tenant_with_settings.refresh_from_db()
        assert tenant_with_settings.timezone == 'Europe/London'
        assert str(tenant_with_settings.quiet_hours_start) == '23:00:00'
        assert str(tenant_with_settings.quiet_hours_end) == '07:00:00'
        
        settings = tenant_with_settings.settings
        settings.refresh_from_db()
        assert settings.business_hours['monday']['open'] == '08:00'
        assert settings.notification_settings['email']['low_stock'] is True
    
    def test_update_business_settings_with_integrations_manage_scope(self, tenant_with_settings, api_client):
        """Test PUT /v1/settings/business with integrations:manage scope."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Create user with integrations:manage scope
        user = User.objects.create(
            email='integration@example.com',
            first_name='Integration',
            last_name='Manager'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Integration Manager',
            is_system=False
        )
        
        permission = Permission.objects.get_or_create(
            code='integrations:manage',
            defaults={'name': 'Manage Integrations', 'description': 'Manage integration settings'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Update business settings
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'timezone': 'Asia/Tokyo',
                'business_hours': {
                    'monday': {'open': '10:00', 'close': '19:00', 'closed': False}
                }
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 200
        
        # Verify update
        tenant_with_settings.refresh_from_db()
        assert tenant_with_settings.timezone == 'Asia/Tokyo'
    
    def test_update_business_settings_without_required_scope(self, tenant_with_settings, api_client):
        """Test PUT /v1/settings/business without required scope returns 403."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Create user without required scopes
        user = User.objects.create(
            email='viewer@example.com',
            first_name='Viewer',
            last_name='User'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Viewer',
            is_system=False
        )
        
        # Give only catalog:view permission
        permission = Permission.objects.get_or_create(
            code='catalog:view',
            defaults={'name': 'View Catalog', 'description': 'View catalog items'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Attempt to update business settings
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'timezone': 'America/Los_Angeles'
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 403
        assert 'users:manage OR integrations:manage' in response.json()['detail']
    
    def test_update_business_settings_invalid_timezone(self, tenant_with_settings, api_client):
        """Test PUT /v1/settings/business with invalid timezone returns 400."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Create user with required scope
        user = User.objects.create(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Admin',
            is_system=True
        )
        
        permission = Permission.objects.get_or_create(
            code='users:manage',
            defaults={'name': 'Manage Users', 'description': 'Manage users'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Attempt to update with invalid timezone
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'timezone': 'Invalid/Timezone'
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 400
        assert 'timezone' in response.json()
    
    def test_update_business_settings_invalid_business_hours(self, tenant_with_settings, api_client):
        """Test PUT /v1/settings/business with invalid business hours format."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Create user with required scope
        user = User.objects.create(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Admin',
            is_system=True
        )
        
        permission = Permission.objects.get_or_create(
            code='users:manage',
            defaults={'name': 'Manage Users', 'description': 'Manage users'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Attempt to update with invalid time format
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'business_hours': {
                    'monday': {'open': '25:00', 'close': '17:00', 'closed': False}
                }
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 400
        assert 'business_hours' in response.json()
    
    def test_update_business_settings_invalid_quiet_hours(self, tenant_with_settings, api_client):
        """Test PUT /v1/settings/business with invalid quiet hours format."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Create user with required scope
        user = User.objects.create(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Admin',
            is_system=True
        )
        
        permission = Permission.objects.get_or_create(
            code='users:manage',
            defaults={'name': 'Manage Users', 'description': 'Manage users'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Attempt to update with invalid quiet hours
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'quiet_hours': {
                    'enabled': True,
                    'start': 'invalid',
                    'end': '08:00'
                }
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 400
        assert 'quiet_hours' in response.json()
    
    def test_disable_quiet_hours(self, tenant_with_settings, api_client):
        """Test disabling quiet hours."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Set up initial quiet hours
        tenant_with_settings.quiet_hours_start = '22:00'
        tenant_with_settings.quiet_hours_end = '08:00'
        tenant_with_settings.save()
        
        # Create user with required scope
        user = User.objects.create(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Admin',
            is_system=True
        )
        
        permission = Permission.objects.get_or_create(
            code='users:manage',
            defaults={'name': 'Manage Users', 'description': 'Manage users'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Disable quiet hours
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'quiet_hours': {
                    'enabled': False
                }
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 200
        
        # Verify quiet hours are disabled
        tenant_with_settings.refresh_from_db()
        assert tenant_with_settings.quiet_hours_start is None
        assert tenant_with_settings.quiet_hours_end is None
        
        # Verify response shows disabled
        data = response.json()
        assert data['settings']['quiet_hours']['enabled'] is False
    
    def test_onboarding_status_updated_on_business_settings_save(self, tenant_with_settings, api_client):
        """Test that onboarding status is updated when business settings are saved."""
        from apps.rbac.models import User, TenantUser, Role, Permission, RolePermission
        
        # Initialize onboarding status
        settings = tenant_with_settings.settings
        settings.initialize_onboarding_status()
        
        # Create user with required scope
        user = User.objects.create(
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        
        role = Role.objects.create(
            tenant=tenant_with_settings,
            name='Admin',
            is_system=True
        )
        
        permission = Permission.objects.get_or_create(
            code='users:manage',
            defaults={'name': 'Manage Users', 'description': 'Manage users'}
        )[0]
        
        RolePermission.objects.create(role=role, permission=permission, allow=True)
        
        tenant_user = TenantUser.objects.create(
            tenant=tenant_with_settings,
            user=user,
            is_active=True
        )
        tenant_user.user_roles.create(role=role)
        
        # Update business settings
        api_client.force_authenticate(user=user)
        response = api_client.put(
            '/v1/settings/business',
            {
                'timezone': 'America/New_York',
                'business_hours': {
                    'monday': {'open': '09:00', 'close': '17:00', 'closed': False}
                }
            },
            format='json',
            HTTP_X_TENANT_ID=str(tenant_with_settings.id)
        )
        
        assert response.status_code == 200
        
        # Verify onboarding status was updated
        settings.refresh_from_db()
        assert settings.onboarding_status['business_settings_configured']['completed'] is True
        assert settings.onboarding_status['business_settings_configured']['completed_at'] is not None
