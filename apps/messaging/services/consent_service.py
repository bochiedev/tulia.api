"""
Consent Service for managing customer communication preferences.

Handles:
- Getting and creating customer preferences
- Updating consent with audit logging
- Checking consent before sending messages
- Automatic preference creation on first interaction
"""
import logging
from django.db import transaction
from django.utils import timezone
from apps.messaging.models import CustomerPreferences, ConsentEvent

logger = logging.getLogger(__name__)


class ConsentService:
    """
    Service for managing customer consent preferences.
    
    Implements consent management with:
    - Automatic preference creation with defaults
    - Audit trail for all changes
    - Consent validation for message sending
    - Support for customer-initiated and tenant-initiated changes
    """
    
    @staticmethod
    def get_preferences(tenant, customer):
        """
        Get customer preferences, creating with defaults if not exists.
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            
        Returns:
            CustomerPreferences: Preferences record
        """
        prefs, created = CustomerPreferences.objects.get_or_create_for_customer(
            tenant=tenant,
            customer=customer
        )
        
        if created:
            logger.info(
                f"Created default preferences for customer {customer.id} "
                f"in tenant {tenant.slug}"
            )
            
            # Log initial consent events
            ConsentService._log_initial_consent_events(prefs)
        
        return prefs
    
    @staticmethod
    def _log_initial_consent_events(preferences):
        """
        Log initial consent events when preferences are created.
        
        Args:
            preferences: CustomerPreferences instance
        """
        consent_types = [
            ('transactional_messages', preferences.transactional_messages),
            ('reminder_messages', preferences.reminder_messages),
            ('promotional_messages', preferences.promotional_messages),
        ]
        
        events = []
        for consent_type, value in consent_types:
            events.append(ConsentEvent(
                tenant=preferences.tenant,
                customer=preferences.customer,
                preferences=preferences,
                consent_type=consent_type,
                previous_value=False,  # No previous value for initial creation
                new_value=value,
                source='system_default',
                reason='Initial preference creation with default values'
            ))
        
        ConsentEvent.objects.bulk_create(events)
    
    @staticmethod
    @transaction.atomic
    def update_consent(tenant, customer, consent_type, value, source='customer_initiated', 
                      reason='', changed_by=None):
        """
        Update a specific consent preference with audit logging.
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            consent_type: One of 'transactional_messages', 'reminder_messages', 'promotional_messages'
            value: Boolean consent value
            source: One of 'customer_initiated', 'tenant_updated', 'system_default'
            reason: Optional reason for the change
            changed_by: User instance if tenant_updated
            
        Returns:
            tuple: (CustomerPreferences, ConsentEvent)
            
        Raises:
            ValueError: If consent_type is invalid
        """
        valid_types = ['transactional_messages', 'reminder_messages', 'promotional_messages']
        if consent_type not in valid_types:
            raise ValueError(f"Invalid consent_type. Must be one of: {valid_types}")
        
        # Get or create preferences
        prefs = ConsentService.get_preferences(tenant, customer)
        
        # Get previous value
        previous_value = getattr(prefs, consent_type)
        
        # Only update if value changed
        if previous_value == value:
            logger.debug(
                f"Consent {consent_type} for customer {customer.id} "
                f"already set to {value}, skipping update"
            )
            return prefs, None
        
        # Update preference
        setattr(prefs, consent_type, value)
        prefs.last_updated_by = source
        if reason:
            prefs.notes = reason
        prefs.save()
        
        # Create audit event
        event = ConsentEvent.objects.create(
            tenant=tenant,
            customer=customer,
            preferences=prefs,
            consent_type=consent_type,
            previous_value=previous_value,
            new_value=value,
            source=source,
            reason=reason,
            changed_by=changed_by
        )
        
        logger.info(
            f"Updated consent {consent_type} for customer {customer.id} "
            f"in tenant {tenant.slug}: {previous_value} → {value} (source: {source})"
        )
        
        return prefs, event
    
    @staticmethod
    def check_consent(tenant, customer, message_type):
        """
        Check if customer has consented to receive a specific message type.
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            message_type: Message type to check (e.g., 'promotional', 'reminder', 'transactional')
            
        Returns:
            bool: True if customer has consented, False otherwise
        """
        prefs = ConsentService.get_preferences(tenant, customer)
        return prefs.has_consent_for(message_type)
    
    @staticmethod
    @transaction.atomic
    def opt_out_all(tenant, customer, source='customer_initiated', reason=''):
        """
        Opt customer out of all optional message types.
        
        Keeps transactional messages enabled as they are essential.
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            source: Source of the opt-out
            reason: Reason for opt-out
            
        Returns:
            CustomerPreferences: Updated preferences
        """
        prefs = ConsentService.get_preferences(tenant, customer)
        
        # Update reminder messages if currently enabled
        if prefs.reminder_messages:
            ConsentService.update_consent(
                tenant, customer, 'reminder_messages', False,
                source=source, reason=reason or 'Customer opted out of all messages'
            )
        
        # Update promotional messages if currently enabled
        if prefs.promotional_messages:
            ConsentService.update_consent(
                tenant, customer, 'promotional_messages', False,
                source=source, reason=reason or 'Customer opted out of all messages'
            )
        
        logger.info(
            f"Customer {customer.id} in tenant {tenant.slug} opted out of all optional messages"
        )
        
        # Refresh from DB to get latest values
        prefs.refresh_from_db()
        return prefs
    
    @staticmethod
    @transaction.atomic
    def opt_in_all(tenant, customer, source='customer_initiated', reason=''):
        """
        Opt customer in to all message types.
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            source: Source of the opt-in
            reason: Reason for opt-in
            
        Returns:
            CustomerPreferences: Updated preferences
        """
        prefs = ConsentService.get_preferences(tenant, customer)
        
        # Update reminder messages if currently disabled
        if not prefs.reminder_messages:
            ConsentService.update_consent(
                tenant, customer, 'reminder_messages', True,
                source=source, reason=reason or 'Customer opted in to all messages'
            )
        
        # Update promotional messages if currently disabled
        if not prefs.promotional_messages:
            ConsentService.update_consent(
                tenant, customer, 'promotional_messages', True,
                source=source, reason=reason or 'Customer opted in to all messages'
            )
        
        logger.info(
            f"Customer {customer.id} in tenant {tenant.slug} opted in to all messages"
        )
        
        # Refresh from DB to get latest values
        prefs.refresh_from_db()
        return prefs
    
    @staticmethod
    def get_consent_history(tenant, customer, consent_type=None):
        """
        Get consent change history for a customer.
        
        Args:
            tenant: Tenant instance
            customer: Customer instance
            consent_type: Optional specific consent type to filter by
            
        Returns:
            QuerySet: ConsentEvent queryset
        """
        if consent_type:
            return ConsentEvent.objects.by_consent_type(tenant, customer, consent_type)
        return ConsentEvent.objects.for_customer(tenant, customer)
    
    @staticmethod
    def get_customers_with_consent(tenant, message_type):
        """
        Get all customers in a tenant who have consented to a message type.
        
        Useful for campaign targeting and reach calculation.
        
        Args:
            tenant: Tenant instance
            message_type: Message type to check
            
        Returns:
            QuerySet: Customer queryset
        """
        from apps.tenants.models import Customer
        
        # Map message types to consent fields
        consent_field_map = {
            'transactional': 'transactional_messages',
            'reminder': 'reminder_messages',
            'promotional': 'promotional_messages',
            'automated_transactional': 'transactional_messages',
            'automated_reminder': 'reminder_messages',
            'automated_reengagement': 'promotional_messages',
            'scheduled_promotional': 'promotional_messages',
        }
        
        consent_field = consent_field_map.get(message_type)
        if not consent_field:
            logger.warning(f"Unknown message type: {message_type}, returning empty queryset")
            return Customer.objects.none()
        
        # Get customers with matching consent
        filter_kwargs = {
            f'preferences__{consent_field}': True
        }
        
        return Customer.objects.filter(
            tenant=tenant,
            **filter_kwargs
        ).distinct()
