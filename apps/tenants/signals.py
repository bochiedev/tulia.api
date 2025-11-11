"""
Signals for tenant lifecycle events.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenants.models import Tenant, TenantSettings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tenant)
def create_tenant_settings(sender, instance, created, **kwargs):
    """
    Auto-create TenantSettings when a new Tenant is created.
    
    Ensures every tenant has a settings record with default values.
    """
    if created:
        TenantSettings.objects.create(
            tenant=instance,
            notification_settings={
                'email': {
                    'order_received': True,
                    'low_stock': True,
                    'daily_summary': True,
                    'weekly_report': False
                },
                'sms': {
                    'critical_alerts': True,
                    'payment_failed': True
                },
                'in_app': {
                    'new_message': True,
                    'handoff_request': True
                },
                'quiet_hours': {
                    'enabled': True,
                    'start': '22:00',
                    'end': '08:00',
                    'timezone': instance.timezone
                }
            },
            feature_flags={
                'ai_responses_enabled': True,
                'auto_handoff_enabled': False,
                'product_recommendations': True,
                'appointment_reminders': True,
                'abandoned_cart_recovery': False,
                'multi_language_support': False
            },
            business_hours={
                'monday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'tuesday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'wednesday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'thursday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'friday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'saturday': {'open': '10:00', 'close': '14:00', 'closed': False},
                'sunday': {'closed': True}
            },
            integrations_status={},
            branding={
                'business_name': instance.name,
                'primary_color': '#007bff',
                'welcome_message': f'Hi! Welcome to {instance.name}. How can we help you today?'
            },
            compliance_settings={
                'gdpr_enabled': True,
                'data_retention_days': 365,
                'consent_required': True
            }
        )
        
        logger.info(
            f"Created TenantSettings for tenant",
            extra={
                'tenant_id': str(instance.id),
                'tenant_slug': instance.slug
            }
        )
