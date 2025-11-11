"""
Messaging Service for outbound message sending with consent and rate limiting.

Handles:
- Sending messages with consent validation
- Rate limiting using Redis sliding window
- Template placeholder replacement
- Scheduling messages for future delivery
- Quiet hours enforcement with timezone handling
"""
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.messaging.models import (
    Message, MessageTemplate, ScheduledMessage,
    CustomerPreferences, Conversation
)
from apps.messaging.services.consent_service import ConsentService
from apps.integrations.services import create_twilio_service_for_tenant
from apps.tenants.models import Tenant, Customer

logger = logging.getLogger(__name__)


class MessagingServiceError(Exception):
    """Base exception for messaging service errors."""
    pass


class RateLimitExceeded(MessagingServiceError):
    """Raised when rate limit is exceeded."""
    pass


class ConsentRequired(MessagingServiceError):
    """Raised when customer consent is required but not granted."""
    pass


class MessagingService:
    """
    Service for sending outbound messages with consent and rate limiting.
    
    Implements:
    - Consent validation before sending
    - Rate limiting per tenant (24-hour rolling window)
    - Template placeholder replacement
    - Message scheduling
    - Quiet hours enforcement
    - Warning notifications at 80% rate limit
    """
    
    # Rate limit warning threshold (80%)
    RATE_LIMIT_WARNING_THRESHOLD = 0.8
    
    # Redis key prefixes
    RATE_LIMIT_KEY_PREFIX = 'rate_limit:tenant:'
    RATE_LIMIT_WARNING_KEY_PREFIX = 'rate_limit_warning:tenant:'
    
    # Rate limit window (24 hours in seconds)
    RATE_LIMIT_WINDOW = 86400
    
    @staticmethod
    def send_message(
        tenant: Tenant,
        customer: Customer,
        content: str,
        message_type: str = 'manual_outbound',
        template_id: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        conversation: Optional[Conversation] = None,
        media_url: Optional[str] = None,
        skip_consent_check: bool = False,
        skip_rate_limit_check: bool = False
    ) -> Message:
        """
        Send an outbound message with consent and rate limit validation.
        
        Args:
            tenant: Tenant sending the message
            customer: Customer receiving the message
            content: Message text content
            message_type: Type of message (for consent checking)
            template_id: Optional template ID if using template
            template_context: Optional context for template rendering
            conversation: Optional conversation to associate message with
            media_url: Optional media URL to attach
            skip_consent_check: Skip consent validation (for transactional messages)
            skip_rate_limit_check: Skip rate limit check (for critical messages)
            
        Returns:
            Message: Created message record
            
        Raises:
            ConsentRequired: If customer hasn't consented to message type
            RateLimitExceeded: If tenant has exceeded rate limit
            MessagingServiceError: If message sending fails
        """
        # Check consent unless skipped
        if not skip_consent_check:
            if not ConsentService.check_consent(tenant, customer, message_type):
                logger.warning(
                    f"Consent check failed for customer {customer.id} "
                    f"in tenant {tenant.slug} for message type {message_type}"
                )
                raise ConsentRequired(
                    f"Customer has not consented to {message_type} messages"
                )
        
        # Check rate limit unless skipped
        if not skip_rate_limit_check:
            if not MessagingService.check_rate_limit(tenant):
                logger.warning(
                    f"Rate limit exceeded for tenant {tenant.slug}"
                )
                raise RateLimitExceeded(
                    f"Daily message limit exceeded for tenant {tenant.slug}"
                )
        
        # Apply template if provided
        if template_id and template_context:
            try:
                template = MessageTemplate.objects.get(id=template_id, tenant=tenant)
                content = MessagingService.apply_template(template, template_context)
            except MessageTemplate.DoesNotExist:
                logger.error(f"Template {template_id} not found for tenant {tenant.slug}")
                raise MessagingServiceError(f"Template {template_id} not found")
        
        # Get or create conversation
        if not conversation:
            conversation, _ = Conversation.objects.get_or_create(
                tenant=tenant,
                customer=customer,
                defaults={'status': 'open', 'channel': 'whatsapp'}
            )
        
        # Create message record
        message = Message.objects.create(
            conversation=conversation,
            direction='out',
            message_type=message_type,
            text=content,
            payload={'media_url': media_url} if media_url else {},
            template_id=template_id
        )
        
        try:
            # Send via Twilio
            twilio_service = create_twilio_service_for_tenant(tenant)
            result = twilio_service.send_whatsapp(
                to=customer.phone_e164,
                body=content,
                media_url=media_url
            )
            
            # Mark as sent
            message.mark_sent(provider_msg_id=result['sid'])
            message.provider_status = result['status']
            message.save(update_fields=['provider_status'])
            
            # Increment rate limit counter
            if not skip_rate_limit_check:
                MessagingService._increment_rate_limit(tenant)
            
            # Check if warning threshold reached
            if not skip_rate_limit_check:
                MessagingService._check_rate_limit_warning(tenant)
            
            logger.info(
                f"Message sent successfully",
                extra={
                    'tenant': tenant.slug,
                    'customer': customer.id,
                    'message_id': message.id,
                    'provider_msg_id': result['sid'],
                    'message_type': message_type
                }
            )
            
            return message
            
        except Exception as e:
            # Mark as failed
            message.mark_failed(error_message=str(e))
            logger.error(
                f"Failed to send message",
                extra={
                    'tenant': tenant.slug,
                    'customer': customer.id,
                    'message_id': message.id,
                    'error': str(e)
                },
                exc_info=True
            )
            raise MessagingServiceError(f"Failed to send message: {str(e)}") from e
    
    @staticmethod
    def check_rate_limit(tenant: Tenant) -> bool:
        """
        Check if tenant is within rate limit using Redis sliding window.
        
        Args:
            tenant: Tenant to check
            
        Returns:
            bool: True if within limit, False if exceeded
        """
        # Get tier limit
        if not tenant.subscription_tier:
            # No tier = no limit (or use default)
            return True
        
        daily_limit = tenant.subscription_tier.max_daily_outbound
        if daily_limit is None:
            # Unlimited
            return True
        
        # Get current count from Redis
        current_count = MessagingService._get_rate_limit_count(tenant)
        
        return current_count < daily_limit
    
    @staticmethod
    def _get_rate_limit_count(tenant: Tenant) -> int:
        """
        Get current message count for tenant in 24-hour window.
        
        Uses Redis sorted set with timestamps as scores for sliding window.
        
        Args:
            tenant: Tenant to check
            
        Returns:
            int: Current message count
        """
        key = f"{MessagingService.RATE_LIMIT_KEY_PREFIX}{tenant.id}"
        
        try:
            # Get Redis connection
            from django.core.cache import cache
            redis_client = cache._cache.get_client()
            
            # Remove old entries (older than 24 hours)
            cutoff_time = timezone.now().timestamp() - MessagingService.RATE_LIMIT_WINDOW
            redis_client.zremrangebyscore(key, '-inf', cutoff_time)
            
            # Count remaining entries
            count = redis_client.zcard(key)
            
            return count
            
        except Exception as e:
            logger.error(
                f"Error getting rate limit count for tenant {tenant.slug}",
                exc_info=True
            )
            # On error, allow the message (fail open)
            return 0
    
    @staticmethod
    def _increment_rate_limit(tenant: Tenant):
        """
        Increment rate limit counter for tenant.
        
        Adds current timestamp to Redis sorted set.
        
        Args:
            tenant: Tenant to increment
        """
        key = f"{MessagingService.RATE_LIMIT_KEY_PREFIX}{tenant.id}"
        
        try:
            from django.core.cache import cache
            redis_client = cache._cache.get_client()
            
            # Add current timestamp
            current_time = timezone.now().timestamp()
            redis_client.zadd(key, {str(current_time): current_time})
            
            # Set expiry to 25 hours (slightly more than window)
            redis_client.expire(key, MessagingService.RATE_LIMIT_WINDOW + 3600)
            
        except Exception as e:
            logger.error(
                f"Error incrementing rate limit for tenant {tenant.slug}",
                exc_info=True
            )
    
    @staticmethod
    def _check_rate_limit_warning(tenant: Tenant):
        """
        Check if tenant has reached 80% of rate limit and send warning.
        
        Only sends warning once per day to avoid spam.
        
        Args:
            tenant: Tenant to check
        """
        if not tenant.subscription_tier:
            return
        
        daily_limit = tenant.subscription_tier.max_daily_outbound
        if daily_limit is None:
            return
        
        current_count = MessagingService._get_rate_limit_count(tenant)
        threshold = int(daily_limit * MessagingService.RATE_LIMIT_WARNING_THRESHOLD)
        
        if current_count >= threshold:
            # Check if we've already sent warning today
            warning_key = f"{MessagingService.RATE_LIMIT_WARNING_KEY_PREFIX}{tenant.id}"
            if cache.get(warning_key):
                return  # Already warned today
            
            # Send warning notification
            logger.warning(
                f"Tenant {tenant.slug} has reached {current_count}/{daily_limit} "
                f"messages ({current_count/daily_limit*100:.1f}% of daily limit)"
            )
            
            # TODO: Send email/SMS notification to tenant contact
            # For now, just log it
            
            # Set cache flag to prevent duplicate warnings (expires in 24 hours)
            cache.set(warning_key, True, MessagingService.RATE_LIMIT_WINDOW)
    
    @staticmethod
    def apply_template(
        template: MessageTemplate,
        context: Dict[str, Any]
    ) -> str:
        """
        Apply template with placeholder replacement.
        
        Supports {{placeholder}} syntax. Placeholders not in context
        are left as-is or replaced with empty string based on template config.
        
        Args:
            template: MessageTemplate instance
            context: Dictionary of placeholder values
            
        Returns:
            str: Rendered template content
            
        Example:
            >>> template = MessageTemplate(content="Hello {{customer_name}}!")
            >>> result = MessagingService.apply_template(template, {'customer_name': 'John'})
            >>> print(result)  # "Hello John!"
        """
        content = template.content
        
        # Find all placeholders
        placeholders = re.findall(r'\{\{(\w+)\}\}', content)
        
        # Replace each placeholder
        for placeholder in placeholders:
            value = context.get(placeholder, '')
            content = content.replace(f'{{{{{placeholder}}}}}', str(value))
        
        # Increment usage count
        template.increment_usage()
        
        return content
    
    @staticmethod
    @transaction.atomic
    def schedule_message(
        tenant: Tenant,
        scheduled_at: datetime,
        content: str,
        customer: Optional[Customer] = None,
        template_id: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        recipient_criteria: Optional[Dict[str, Any]] = None,
        message_type: str = 'scheduled_promotional',
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScheduledMessage:
        """
        Schedule a message for future delivery.
        
        Args:
            tenant: Tenant scheduling the message
            scheduled_at: When to send the message
            content: Message content
            customer: Optional specific customer (null for broadcast)
            template_id: Optional template ID
            template_context: Optional template context
            recipient_criteria: Optional criteria for broadcast targeting
            message_type: Type of message for consent checking
            metadata: Optional metadata (campaign_id, appointment_id, etc.)
            
        Returns:
            ScheduledMessage: Created scheduled message record
            
        Raises:
            ValueError: If scheduled_at is in the past
        """
        # Validate scheduled_at is in future
        if scheduled_at <= timezone.now():
            raise ValueError("scheduled_at must be in the future")
        
        # Adjust for quiet hours if applicable
        if customer:
            scheduled_at = MessagingService.respect_quiet_hours(
                tenant, customer, scheduled_at, message_type
            )
        
        # Create scheduled message
        scheduled_msg = ScheduledMessage.objects.create(
            tenant=tenant,
            customer=customer,
            content=content,
            template_id=template_id,
            template_context=template_context or {},
            scheduled_at=scheduled_at,
            recipient_criteria=recipient_criteria or {},
            message_type=message_type,
            metadata=metadata or {},
            status='pending'
        )
        
        logger.info(
            f"Message scheduled for {scheduled_at}",
            extra={
                'tenant': tenant.slug,
                'customer': customer.id if customer else None,
                'scheduled_message_id': scheduled_msg.id,
                'message_type': message_type
            }
        )
        
        return scheduled_msg
    
    @staticmethod
    def respect_quiet_hours(
        tenant: Tenant,
        customer: Customer,
        scheduled_at: datetime,
        message_type: str
    ) -> datetime:
        """
        Adjust scheduled time to respect quiet hours.
        
        If scheduled time falls within quiet hours, delays to end of quiet hours.
        Time-sensitive messages (transactional, reminders) override quiet hours.
        
        Args:
            tenant: Tenant with quiet hours configuration
            customer: Customer with timezone
            scheduled_at: Proposed send time
            message_type: Type of message
            
        Returns:
            datetime: Adjusted send time
        """
        # Time-sensitive messages override quiet hours
        if message_type in ['automated_transactional', 'automated_reminder']:
            return scheduled_at
        
        # Get customer timezone or fall back to tenant timezone
        tz_name = customer.timezone or tenant.timezone
        try:
            import pytz
            tz = pytz.timezone(tz_name)
        except Exception:
            # Invalid timezone, use UTC
            import pytz
            tz = pytz.UTC
        
        # Convert scheduled time to customer's timezone
        local_time = scheduled_at.astimezone(tz)
        
        # Check if in quiet hours
        quiet_start = tenant.quiet_hours_start
        quiet_end = tenant.quiet_hours_end
        
        # Handle quiet hours that span midnight
        if quiet_start > quiet_end:
            # e.g., 22:00 to 08:00
            in_quiet_hours = (
                local_time.time() >= quiet_start or
                local_time.time() < quiet_end
            )
        else:
            # e.g., 01:00 to 06:00
            in_quiet_hours = (
                quiet_start <= local_time.time() < quiet_end
            )
        
        if in_quiet_hours:
            # Delay to end of quiet hours
            adjusted_time = local_time.replace(
                hour=quiet_end.hour,
                minute=quiet_end.minute,
                second=0,
                microsecond=0
            )
            
            # If quiet hours end is earlier in the day, it's tomorrow
            if local_time.time() >= quiet_start and quiet_start > quiet_end:
                adjusted_time += timedelta(days=1)
            
            # Convert back to UTC
            adjusted_at = adjusted_time.astimezone(pytz.UTC)
            
            logger.info(
                f"Adjusted scheduled time from {scheduled_at} to {adjusted_at} "
                f"to respect quiet hours for customer {customer.id}"
            )
            
            return adjusted_at
        
        return scheduled_at
    
    @staticmethod
    def get_rate_limit_status(tenant: Tenant) -> Dict[str, Any]:
        """
        Get current rate limit status for tenant.
        
        Args:
            tenant: Tenant to check
            
        Returns:
            dict: Rate limit status with current count, limit, and percentage
        """
        if not tenant.subscription_tier:
            return {
                'current_count': 0,
                'daily_limit': None,
                'percentage_used': 0,
                'remaining': None,
                'is_unlimited': True
            }
        
        daily_limit = tenant.subscription_tier.max_daily_outbound
        if daily_limit is None:
            return {
                'current_count': 0,
                'daily_limit': None,
                'percentage_used': 0,
                'remaining': None,
                'is_unlimited': True
            }
        
        current_count = MessagingService._get_rate_limit_count(tenant)
        percentage_used = (current_count / daily_limit * 100) if daily_limit > 0 else 0
        remaining = max(0, daily_limit - current_count)
        
        return {
            'current_count': current_count,
            'daily_limit': daily_limit,
            'percentage_used': round(percentage_used, 2),
            'remaining': remaining,
            'is_unlimited': False,
            'warning_threshold_reached': percentage_used >= (MessagingService.RATE_LIMIT_WARNING_THRESHOLD * 100)
        }
    
    @staticmethod
    def queue_excess_messages(tenant: Tenant, messages: List[Dict[str, Any]]):
        """
        Queue messages that exceed daily limit for next day.
        
        Args:
            tenant: Tenant with exceeded limit
            messages: List of message data to queue
        """
        # Schedule for tomorrow at 8 AM tenant time
        import pytz
        try:
            tz = pytz.timezone(tenant.timezone)
        except Exception:
            tz = pytz.UTC
        
        tomorrow = timezone.now() + timedelta(days=1)
        tomorrow_8am = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
        tomorrow_8am = tz.localize(tomorrow_8am.replace(tzinfo=None))
        
        for msg_data in messages:
            MessagingService.schedule_message(
                tenant=tenant,
                scheduled_at=tomorrow_8am,
                content=msg_data.get('content', ''),
                customer=msg_data.get('customer'),
                template_id=msg_data.get('template_id'),
                template_context=msg_data.get('template_context'),
                message_type=msg_data.get('message_type', 'scheduled_promotional'),
                metadata={'queued_due_to_rate_limit': True}
            )
        
        logger.info(
            f"Queued {len(messages)} messages for tenant {tenant.slug} "
            f"due to rate limit, scheduled for {tomorrow_8am}"
        )
