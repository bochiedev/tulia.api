"""
Onboarding service for tracking tenant setup progress.

Handles:
- Onboarding status tracking
- Step completion marking
- Completion checking
- Reminder emails
"""
from typing import Dict, List
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from apps.tenants.models import Tenant, TenantSettings


class OnboardingService:
    """
    Service for managing tenant onboarding progress.
    
    Tracks completion of required and optional setup steps,
    calculates completion percentage, and sends reminder emails.
    """
    
    # Required steps that must be completed for onboarding
    REQUIRED_STEPS = [
        'twilio_configured',
        'payment_method_added',
        'business_settings_configured',
    ]
    
    # Optional steps that enhance functionality but aren't required
    OPTIONAL_STEPS = [
        'woocommerce_configured',
        'shopify_configured',
        'payout_method_configured',
    ]
    
    @classmethod
    def get_onboarding_status(cls, tenant: Tenant) -> Dict:
        """
        Get onboarding status with completion percentage.
        
        Returns detailed status including:
        - Overall completion status
        - Completion percentage (based on required steps only)
        - Status of each required step
        - Status of each optional step
        - List of pending required steps
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: {
                'completed': bool,
                'completion_percentage': int,
                'required_steps': {step_name: {completed: bool, completed_at: str}},
                'optional_steps': {step_name: {completed: bool, completed_at: str}},
                'pending_steps': [step_name, ...]
            }
        """
        settings_obj = TenantSettings.objects.get(tenant=tenant)
        
        # Initialize onboarding status if not set
        if not settings_obj.onboarding_status:
            settings_obj.initialize_onboarding_status()
            settings_obj.refresh_from_db()
        
        onboarding_status = settings_obj.onboarding_status
        
        # Separate required and optional steps
        required_steps = {}
        optional_steps = {}
        pending_steps = []
        
        for step_name in cls.REQUIRED_STEPS:
            step_data = onboarding_status.get(step_name, {'completed': False, 'completed_at': None})
            required_steps[step_name] = step_data
            if not step_data.get('completed'):
                pending_steps.append(step_name)
        
        for step_name in cls.OPTIONAL_STEPS:
            step_data = onboarding_status.get(step_name, {'completed': False, 'completed_at': None})
            optional_steps[step_name] = step_data
        
        # Calculate completion percentage based on required steps only
        total_required = len(cls.REQUIRED_STEPS)
        completed_required = sum(1 for step in required_steps.values() if step.get('completed'))
        completion_percentage = int((completed_required / total_required * 100)) if total_required > 0 else 0
        
        # Check if all required steps are completed
        completed = len(pending_steps) == 0
        
        return {
            'completed': completed,
            'completion_percentage': completion_percentage,
            'required_steps': required_steps,
            'optional_steps': optional_steps,
            'pending_steps': pending_steps,
        }
    
    @classmethod
    def mark_step_complete(cls, tenant: Tenant, step: str):
        """
        Mark an onboarding step as complete.
        
        Updates the step status with completion timestamp and checks
        if all required steps are now complete.
        
        Args:
            tenant: Tenant instance
            step: Step name to mark as complete
            
        Raises:
            ValueError: If step name is invalid
        """
        # Validate step name
        all_steps = cls.REQUIRED_STEPS + cls.OPTIONAL_STEPS
        if step not in all_steps:
            raise ValueError(f"Invalid step name: {step}. Must be one of {all_steps}")
        
        settings_obj = TenantSettings.objects.get(tenant=tenant)
        
        # Initialize onboarding status if not set
        if not settings_obj.onboarding_status:
            settings_obj.initialize_onboarding_status()
        
        # Mark step as complete
        if step not in settings_obj.onboarding_status:
            settings_obj.onboarding_status[step] = {}
        
        settings_obj.onboarding_status[step]['completed'] = True
        settings_obj.onboarding_status[step]['completed_at'] = timezone.now().isoformat()
        
        # Check if all required steps are now complete (check in-memory state)
        all_required_complete = all(
            settings_obj.onboarding_status.get(req_step, {}).get('completed', False)
            for req_step in cls.REQUIRED_STEPS
        )
        
        if all_required_complete:
            settings_obj.onboarding_completed = True
            settings_obj.onboarding_completed_at = timezone.now()
        
        settings_obj.save(update_fields=[
            'onboarding_status',
            'onboarding_completed',
            'onboarding_completed_at',
            'updated_at'
        ])
    
    @classmethod
    def check_completion(cls, tenant: Tenant) -> bool:
        """
        Check if all required onboarding steps are complete.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            bool: True if all required steps are complete
        """
        settings_obj = TenantSettings.objects.get(tenant=tenant)
        
        # Initialize onboarding status if not set
        if not settings_obj.onboarding_status:
            return False
        
        # Check all required steps
        for step_name in cls.REQUIRED_STEPS:
            step_data = settings_obj.onboarding_status.get(step_name, {})
            if not step_data.get('completed', False):
                return False
        
        return True
    
    @classmethod
    def send_reminder(cls, tenant: Tenant):
        """
        Send onboarding reminder email to tenant.
        
        Includes:
        - Completion percentage
        - List of pending steps
        - Links to complete each step
        
        Args:
            tenant: Tenant instance
        """
        # Get onboarding status
        status = cls.get_onboarding_status(tenant)
        
        # Don't send reminder if already completed
        if status['completed']:
            return
        
        # Get tenant contact email
        contact_email = tenant.contact_email
        if not contact_email:
            # Try to get owner's email
            from apps.rbac.models import TenantUser, Role
            owner_role = Role.objects.filter(tenant=tenant, name='Owner').first()
            if owner_role:
                owner_membership = TenantUser.objects.filter(
                    tenant=tenant,
                    user_roles__role=owner_role,
                    is_active=True
                ).first()
                if owner_membership:
                    contact_email = owner_membership.user.email
        
        if not contact_email:
            # No email to send to
            return
        
        # Build email content
        completion_percentage = status['completion_percentage']
        pending_steps = status['pending_steps']
        
        # Map step names to friendly names
        step_names = {
            'twilio_configured': 'Configure Twilio credentials',
            'payment_method_added': 'Add payment method',
            'business_settings_configured': 'Configure business settings',
            'woocommerce_configured': 'Connect WooCommerce store',
            'shopify_configured': 'Connect Shopify store',
            'payout_method_configured': 'Configure payout method',
        }
        
        pending_list = '\n'.join([f"- {step_names.get(step, step)}" for step in pending_steps])
        
        subject = f"Complete your {tenant.name} setup - {completion_percentage}% done"
        
        message = f"""
Hi there,

You're {completion_percentage}% done setting up your {tenant.name} account on Tulia AI!

To get the most out of your account, please complete these remaining steps:

{pending_list}

Complete your setup now: {getattr(settings, 'FRONTEND_URL', 'https://app.trytulia.com')}/onboarding

Need help? Reply to this email and we'll be happy to assist.

Best regards,
The Tulia AI Team
"""
        
        # Send email
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@trytulia.com'),
                recipient_list=[contact_email],
                fail_silently=False,
            )
        except Exception as e:
            # Log error but don't raise
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send onboarding reminder to {contact_email}: {str(e)}")
