"""
Tests for onboarding reminder Celery tasks.
"""
import pytest
from datetime import timedelta, date
from django.utils import timezone
from unittest.mock import patch, MagicMock

from apps.tenants.models import Tenant, TenantSettings
from apps.tenants.tasks import send_onboarding_reminders
from apps.tenants.services.onboarding_service import OnboardingService


@pytest.mark.django_db
class TestOnboardingReminderTask:
    """Test onboarding reminder Celery task."""
    
    def test_send_reminders_to_3_day_old_incomplete_tenants(self):
        """Test that reminders are sent to tenants created 3 days ago with incomplete onboarding."""
        # Create tenant from 3 days ago with incomplete onboarding
        # Use date.today() - timedelta to match the task's date filtering
        three_days_ago_date = date.today() - timedelta(days=3)
        three_days_ago = timezone.make_aware(
            timezone.datetime.combine(three_days_ago_date, timezone.datetime.min.time())
        )
        tenant = Tenant.objects.create(
            name="Test Tenant 3D",
            slug="test-tenant-3d",
            whatsapp_number="+1234567890",
            contact_email="test@example.com",
            status="trial",
            created_at=three_days_ago
        )
        
        # Get auto-created settings and initialize onboarding status
        settings = TenantSettings.objects.get(tenant=tenant)
        settings.initialize_onboarding_status()
        
        # Mock the send_reminder method
        with patch.object(OnboardingService, 'send_reminder') as mock_send:
            result = send_onboarding_reminders()
            
            # Verify reminder was sent
            assert mock_send.call_count == 1
            assert mock_send.call_args[0][0].id == tenant.id
            
            # Verify result
            assert result['reminders_3d'] == 1
            assert result['reminders_7d'] == 0
            assert result['total'] == 1
    
    def test_send_reminders_to_7_day_old_incomplete_tenants(self):
        """Test that reminders are sent to tenants created 7 days ago with incomplete onboarding."""
        # Create tenant from 7 days ago with incomplete onboarding
        # Use date.today() - timedelta to match the task's date filtering
        seven_days_ago_date = date.today() - timedelta(days=7)
        seven_days_ago = timezone.make_aware(
            timezone.datetime.combine(seven_days_ago_date, timezone.datetime.min.time())
        )
        tenant = Tenant.objects.create(
            name="Test Tenant 7D",
            slug="test-tenant-7d",
            whatsapp_number="+1234567891",
            contact_email="test7@example.com",
            status="trial",
            created_at=seven_days_ago
        )
        
        # Get auto-created settings and initialize onboarding status
        settings = TenantSettings.objects.get(tenant=tenant)
        settings.initialize_onboarding_status()
        
        # Mock the send_reminder method
        with patch.object(OnboardingService, 'send_reminder') as mock_send:
            result = send_onboarding_reminders()
            
            # Verify reminder was sent
            assert mock_send.call_count == 1
            assert mock_send.call_args[0][0].id == tenant.id
            
            # Verify result
            assert result['reminders_3d'] == 0
            assert result['reminders_7d'] == 1
            assert result['total'] == 1
    
    def test_no_reminders_for_completed_onboarding(self):
        """Test that no reminders are sent to tenants with completed onboarding."""
        # Create tenant from 3 days ago
        three_days_ago = timezone.now() - timedelta(days=3)
        tenant = Tenant.objects.create(
            name="Test Tenant Complete",
            slug="test-tenant-complete",
            whatsapp_number="+1234567892",
            contact_email="complete@example.com",
            status="trial",
            created_at=three_days_ago
        )
        
        # Get auto-created settings and initialize onboarding status
        settings = TenantSettings.objects.get(tenant=tenant)
        settings.initialize_onboarding_status()
        
        for step in OnboardingService.REQUIRED_STEPS:
            OnboardingService.mark_step_complete(tenant, step)
        
        # Mock the send_reminder method
        with patch.object(OnboardingService, 'send_reminder') as mock_send:
            result = send_onboarding_reminders()
            
            # Verify no reminder was sent
            assert mock_send.call_count == 0
            
            # Verify result
            assert result['reminders_3d'] == 0
            assert result['reminders_7d'] == 0
            assert result['total'] == 0
    
    def test_no_reminders_for_deleted_tenants(self):
        """Test that no reminders are sent to soft-deleted tenants."""
        # Create deleted tenant from 3 days ago
        three_days_ago = timezone.now() - timedelta(days=3)
        tenant = Tenant.objects.create(
            name="Test Tenant Deleted",
            slug="test-tenant-deleted",
            whatsapp_number="+1234567893",
            contact_email="deleted@example.com",
            status="trial",
            created_at=three_days_ago,
            deleted_at=timezone.now()
        )
        
        # Get auto-created settings and initialize onboarding status
        settings = TenantSettings.objects.get(tenant=tenant)
        settings.initialize_onboarding_status()
        
        # Mock the send_reminder method
        with patch.object(OnboardingService, 'send_reminder') as mock_send:
            result = send_onboarding_reminders()
            
            # Verify no reminder was sent
            assert mock_send.call_count == 0
            
            # Verify result
            assert result['total'] == 0
    
    def test_handles_multiple_tenants(self):
        """Test that task handles multiple tenants correctly."""
        # Create multiple tenants at different ages
        # Use date.today() - timedelta to match the task's date filtering
        three_days_ago_date = date.today() - timedelta(days=3)
        three_days_ago = timezone.make_aware(
            timezone.datetime.combine(three_days_ago_date, timezone.datetime.min.time())
        )
        seven_days_ago_date = date.today() - timedelta(days=7)
        seven_days_ago = timezone.make_aware(
            timezone.datetime.combine(seven_days_ago_date, timezone.datetime.min.time())
        )
        
        # 3-day old tenant (incomplete)
        tenant_3d = Tenant.objects.create(
            name="Tenant 3D",
            slug="tenant-3d",
            whatsapp_number="+1234567894",
            contact_email="3d@example.com",
            status="trial",
            created_at=three_days_ago
        )
        settings_3d = TenantSettings.objects.get(tenant=tenant_3d)
        settings_3d.initialize_onboarding_status()
        
        # 7-day old tenant (incomplete)
        tenant_7d = Tenant.objects.create(
            name="Tenant 7D",
            slug="tenant-7d",
            whatsapp_number="+1234567895",
            contact_email="7d@example.com",
            status="trial",
            created_at=seven_days_ago
        )
        settings_7d = TenantSettings.objects.get(tenant=tenant_7d)
        settings_7d.initialize_onboarding_status()
        
        # Mock the send_reminder method
        with patch.object(OnboardingService, 'send_reminder') as mock_send:
            result = send_onboarding_reminders()
            
            # Verify reminders were sent to both
            assert mock_send.call_count == 2
            
            # Verify result
            assert result['reminders_3d'] == 1
            assert result['reminders_7d'] == 1
            assert result['total'] == 2
    
    def test_continues_on_email_failure(self):
        """Test that task continues processing even if one email fails."""
        # Create two tenants from 3 days ago
        # Use date.today() - timedelta to match the task's date filtering
        three_days_ago_date = date.today() - timedelta(days=3)
        three_days_ago = timezone.make_aware(
            timezone.datetime.combine(three_days_ago_date, timezone.datetime.min.time())
        )
        
        tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            whatsapp_number="+1234567896",
            contact_email="tenant1@example.com",
            status="trial",
            created_at=three_days_ago
        )
        settings1 = TenantSettings.objects.get(tenant=tenant1)
        settings1.initialize_onboarding_status()
        
        tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            whatsapp_number="+1234567897",
            contact_email="tenant2@example.com",
            status="trial",
            created_at=three_days_ago
        )
        settings2 = TenantSettings.objects.get(tenant=tenant2)
        settings2.initialize_onboarding_status()
        
        # Mock send_reminder to fail for first tenant but succeed for second
        with patch.object(OnboardingService, 'send_reminder') as mock_send:
            mock_send.side_effect = [Exception("Email failed"), None]
            
            result = send_onboarding_reminders()
            
            # Verify both were attempted
            assert mock_send.call_count == 2
            
            # Only one succeeded
            assert result['reminders_3d'] == 1
            assert result['total'] == 1
