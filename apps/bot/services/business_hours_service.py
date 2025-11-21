"""
Business Hours and Quiet Hours Service for sales orchestration refactor.

This service manages business hours and quiet hours checking.

Design principles:
- Check if current time is within business hours
- Check if current time is within quiet hours
- Suggest alternative times within business hours
- Queue conversations during quiet hours
"""
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class BusinessHoursService:
    """
    Service for business hours and quiet hours management.
    
    Responsibilities:
    - Check if current time is within business hours
    - Check if current time is within quiet hours
    - Suggest alternative appointment times
    - Provide appropriate messages for out-of-hours
    """
    
    def is_within_business_hours(
        self,
        config,  # AgentConfiguration
        check_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if time is within business hours.
        
        Args:
            config: AgentConfiguration with business hours
            check_time: Time to check (defaults to now)
            
        Returns:
            True if within business hours
        """
        if not config:
            return True  # No config, allow all times
        
        if not config.business_hours_start or not config.business_hours_end:
            return True  # No hours configured, allow all times
        
        # Get current time in tenant timezone
        if check_time is None:
            check_time = timezone.now()
        
        current_time = check_time.time()
        
        # Check if within business hours
        start = config.business_hours_start
        end = config.business_hours_end
        
        if start <= end:
            # Normal case: 8:00 - 20:00
            return start <= current_time <= end
        else:
            # Overnight case: 20:00 - 8:00
            return current_time >= start or current_time <= end
    
    def is_within_quiet_hours(
        self,
        config,  # AgentConfiguration
        check_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if time is within quiet hours.
        
        Args:
            config: AgentConfiguration with quiet hours
            check_time: Time to check (defaults to now)
            
        Returns:
            True if within quiet hours
        """
        if not config:
            return False  # No config, no quiet hours
        
        if not config.quiet_hours_start or not config.quiet_hours_end:
            return False  # No quiet hours configured
        
        # Get current time
        if check_time is None:
            check_time = timezone.now()
        
        current_time = check_time.time()
        
        # Check if within quiet hours
        start = config.quiet_hours_start
        end = config.quiet_hours_end
        
        if start <= end:
            # Normal case: 22:00 - 08:00 (but this is unusual)
            return start <= current_time <= end
        else:
            # Overnight case: 22:00 - 08:00 (typical)
            return current_time >= start or current_time <= end
    
    def get_quiet_hours_message(
        self,
        config,  # AgentConfiguration
        language: List[str]
    ) -> str:
        """
        Get message to send during quiet hours.
        
        Args:
            config: AgentConfiguration
            language: Detected language(s)
            
        Returns:
            Appropriate message for quiet hours
        """
        messages = {
            'en': (
                "Thank you for your message! We're currently outside our operating hours. "
                "We'll respond to you as soon as we're back. "
                "Our hours are {start} to {end}."
            ),
            'sw': (
                "Asante kwa ujumbe wako! Kwa sasa tuko nje ya masaa yetu ya kazi. "
                "Tutakujibu mara tu tutakaporejea. "
                "Masaa yetu ni {start} hadi {end}."
            ),
            'sheng': (
                "Asante sa message! Saa hizi tuko out ya masaa za kazi. "
                "Tutakujibu vile tutarudi. "
                "Masaa zetu ni {start} mpaka {end}."
            )
        }
        
        # Determine language
        lang = 'en'
        if 'sw' in language:
            lang = 'sw'
        elif 'sheng' in language:
            lang = 'sheng'
        
        message = messages.get(lang, messages['en'])
        
        # Format with business hours
        if config and config.business_hours_start and config.business_hours_end:
            start = config.business_hours_start.strftime('%H:%M')
            end = config.business_hours_end.strftime('%H:%M')
            message = message.format(start=start, end=end)
        
        return message
    
    def suggest_alternative_times(
        self,
        config,  # AgentConfiguration
        requested_time: datetime,
        language: List[str]
    ) -> str:
        """
        Suggest alternative times within business hours.
        
        Args:
            config: AgentConfiguration
            requested_time: Time requested by customer
            language: Detected language(s)
            
        Returns:
            Message with alternative time suggestions
        """
        if not config or not config.business_hours_start:
            return ""
        
        # Find next available time
        next_time = self._find_next_business_hour(config, requested_time)
        
        # Format message
        messages = {
            'en': (
                "That time is outside our business hours. "
                "How about {time} instead? "
                "Our hours are {start} to {end}."
            ),
            'sw': (
                "Wakati huo uko nje ya masaa yetu ya kazi. "
                "Je, {time} inafaa? "
                "Masaa yetu ni {start} hadi {end}."
            ),
            'sheng': (
                "Time hiyo iko out ya masaa za kazi. "
                "Aje {time} instead? "
                "Masaa zetu ni {start} mpaka {end}."
            )
        }
        
        lang = 'en'
        if 'sw' in language:
            lang = 'sw'
        elif 'sheng' in language:
            lang = 'sheng'
        
        message = messages.get(lang, messages['en'])
        
        return message.format(
            time=next_time.strftime('%I:%M %p'),
            start=config.business_hours_start.strftime('%H:%M'),
            end=config.business_hours_end.strftime('%H:%M')
        )
    
    def _find_next_business_hour(
        self,
        config,  # AgentConfiguration
        from_time: datetime
    ) -> datetime:
        """
        Find next available time within business hours.
        
        Args:
            config: AgentConfiguration
            from_time: Starting time
            
        Returns:
            Next available datetime within business hours
        """
        if not config or not config.business_hours_start:
            return from_time
        
        # Start with the requested time
        check_time = from_time
        
        # Check up to 7 days ahead
        for _ in range(7):
            # If this time is within business hours, return it
            if self.is_within_business_hours(config, check_time):
                return check_time
            
            # Otherwise, move to start of next business day
            next_day = check_time.date() + timedelta(days=1)
            check_time = datetime.combine(
                next_day,
                config.business_hours_start
            )
            check_time = timezone.make_aware(check_time)
        
        # Fallback: return original time
        return from_time
    
    def should_queue_message(
        self,
        config,  # AgentConfiguration
    ) -> bool:
        """
        Determine if message should be queued instead of processed immediately.
        
        Args:
            config: AgentConfiguration
            
        Returns:
            True if message should be queued
        """
        # Queue if in quiet hours
        return self.is_within_quiet_hours(config)
    
    def get_next_processing_time(
        self,
        config,  # AgentConfiguration
    ) -> datetime:
        """
        Get next time when queued messages should be processed.
        
        Args:
            config: AgentConfiguration
            
        Returns:
            Datetime when processing should resume
        """
        if not config or not config.quiet_hours_end:
            return timezone.now()
        
        now = timezone.now()
        
        # If currently in quiet hours, return end of quiet hours
        if self.is_within_quiet_hours(config, now):
            # Combine today's date with quiet hours end time
            next_time = datetime.combine(
                now.date(),
                config.quiet_hours_end
            )
            next_time = timezone.make_aware(next_time)
            
            # If that's in the past, add a day
            if next_time <= now:
                next_time += timedelta(days=1)
            
            return next_time
        
        # Not in quiet hours, process now
        return now


__all__ = ['BusinessHoursService']
