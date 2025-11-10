"""
BookingService for managing service availability and appointments.

Handles:
- Finding available time slots
- Checking capacity
- Creating appointments with validation
- Canceling appointments
- Proposing alternative slots
"""
from datetime import datetime, timedelta, time as dt_time
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.core.exceptions import ValidationError
import pytz

from apps.services.models import (
    Service,
    ServiceVariant,
    AvailabilityWindow,
    Appointment
)
from apps.tenants.models import Tenant, Customer


class BookingService:
    """
    Service for managing service bookings and availability.
    
    All methods are tenant-scoped to ensure multi-tenant isolation.
    """
    
    def __init__(self, tenant: Tenant):
        """
        Initialize booking service for a specific tenant.
        
        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant
    
    def find_availability(
        self,
        service_id: str,
        from_dt: datetime,
        to_dt: datetime,
        variant_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Find available time slots for a service within a date range.
        
        Args:
            service_id: Service UUID
            from_dt: Start of date range
            to_dt: End of date range
            variant_id: Optional service variant UUID
            
        Returns:
            List of available slots with format:
            [
                {
                    'start_dt': datetime,
                    'end_dt': datetime,
                    'capacity_left': int,
                    'window_id': UUID
                },
                ...
            ]
            
        Raises:
            Service.DoesNotExist: If service not found or doesn't belong to tenant
        """
        # Get service and validate tenant ownership
        service = Service.objects.get(id=service_id, tenant=self.tenant, is_active=True)
        
        # Get variant if specified
        variant = None
        if variant_id:
            variant = ServiceVariant.objects.get(id=variant_id, service=service)
        
        # Determine duration
        duration_minutes = variant.duration_minutes if variant else 60  # Default 60 min
        
        # Get availability windows for the date range
        available_slots = []
        current_date = from_dt.date()
        end_date = to_dt.date()
        
        while current_date <= end_date:
            # Get windows for this date
            windows = AvailabilityWindow.objects.for_date(service, current_date)
            
            for window in windows:
                # Generate slots for this window
                slots = self._generate_slots_for_window(
                    window,
                    current_date,
                    duration_minutes,
                    from_dt,
                    to_dt
                )
                available_slots.extend(slots)
            
            current_date += timedelta(days=1)
        
        # Sort by start time
        available_slots.sort(key=lambda x: x['start_dt'])
        
        return available_slots
    
    def _generate_slots_for_window(
        self,
        window: AvailabilityWindow,
        date: datetime.date,
        duration_minutes: int,
        from_dt: datetime,
        to_dt: datetime
    ) -> List[Dict]:
        """
        Generate available slots for a specific availability window.
        
        Args:
            window: AvailabilityWindow instance
            date: Date to generate slots for
            duration_minutes: Duration of each slot
            from_dt: Filter start datetime
            to_dt: Filter end datetime
            
        Returns:
            List of available slots
        """
        slots = []
        
        # Get timezone
        tz = pytz.timezone(window.timezone)
        
        # Create datetime objects for window start and end
        window_start = tz.localize(datetime.combine(date, window.start_time))
        window_end = tz.localize(datetime.combine(date, window.end_time))
        
        # Generate slots
        current_slot_start = window_start
        
        while current_slot_start + timedelta(minutes=duration_minutes) <= window_end:
            slot_end = current_slot_start + timedelta(minutes=duration_minutes)
            
            # Check if slot is within requested range
            if current_slot_start >= from_dt and slot_end <= to_dt:
                # Check capacity
                capacity_left = self.check_capacity(
                    window.service_id,
                    current_slot_start,
                    slot_end
                )
                
                if capacity_left > 0:
                    slots.append({
                        'start_dt': current_slot_start,
                        'end_dt': slot_end,
                        'capacity_left': capacity_left,
                        'window_id': window.id,
                        'window_capacity': window.capacity
                    })
            
            # Move to next slot (could add configurable slot interval)
            current_slot_start += timedelta(minutes=duration_minutes)
        
        return slots
    
    def check_capacity(
        self,
        service_id: str,
        start_dt: datetime,
        end_dt: datetime
    ) -> int:
        """
        Check available capacity for a time slot.
        
        Calculates: window.capacity - count(overlapping confirmed/pending appointments)
        
        Args:
            service_id: Service UUID
            start_dt: Slot start datetime
            end_dt: Slot end datetime
            
        Returns:
            Number of available slots (0 if fully booked)
        """
        # Get the service
        service = Service.objects.get(id=service_id, tenant=self.tenant)
        
        # Find the applicable availability window
        date = start_dt.date()
        windows = AvailabilityWindow.objects.for_date(service, date)
        
        # Find window that contains this time slot
        window_capacity = 1  # Default capacity
        for window in windows:
            tz = pytz.timezone(window.timezone)
            window_start = tz.localize(datetime.combine(date, window.start_time))
            window_end = tz.localize(datetime.combine(date, window.end_time))
            
            if window_start <= start_dt and end_dt <= window_end:
                window_capacity = window.capacity
                break
        
        # Count overlapping appointments
        overlapping_count = Appointment.objects.overlapping(
            service,
            start_dt,
            end_dt
        ).count()
        
        return max(0, window_capacity - overlapping_count)
    
    @transaction.atomic
    def create_appointment(
        self,
        customer_id: str,
        service_id: str,
        start_dt: datetime,
        end_dt: datetime,
        variant_id: Optional[str] = None,
        notes: Optional[str] = None,
        status: str = 'pending'
    ) -> Appointment:
        """
        Create a new appointment with capacity validation.
        
        Args:
            customer_id: Customer UUID
            service_id: Service UUID
            start_dt: Appointment start datetime
            end_dt: Appointment end datetime
            variant_id: Optional service variant UUID
            notes: Optional customer notes
            status: Initial status (default: 'pending')
            
        Returns:
            Created Appointment instance
            
        Raises:
            ValidationError: If slot is unavailable or validation fails
            Service.DoesNotExist: If service not found
            Customer.DoesNotExist: If customer not found
        """
        # Get and validate service
        service = Service.objects.get(id=service_id, tenant=self.tenant, is_active=True)
        
        # Get and validate customer
        customer = Customer.objects.get(id=customer_id, tenant=self.tenant)
        
        # Get and validate variant if specified
        variant = None
        if variant_id:
            variant = ServiceVariant.objects.get(id=variant_id, service=service)
        
        # Validate time slot is within an availability window
        if not self._is_within_availability_window(service, start_dt, end_dt):
            raise ValidationError(
                "Requested time slot is not within any availability window"
            )
        
        # Check capacity
        capacity_left = self.check_capacity(service_id, start_dt, end_dt)
        if capacity_left <= 0:
            raise ValidationError(
                "No capacity available for the requested time slot"
            )
        
        # Create appointment
        appointment = Appointment.objects.create(
            tenant=self.tenant,
            customer=customer,
            service=service,
            variant=variant,
            start_dt=start_dt,
            end_dt=end_dt,
            status=status,
            notes=notes
        )
        
        return appointment
    
    def _is_within_availability_window(
        self,
        service: Service,
        start_dt: datetime,
        end_dt: datetime
    ) -> bool:
        """
        Check if a time slot falls within an availability window.
        
        Args:
            service: Service instance
            start_dt: Slot start datetime
            end_dt: Slot end datetime
            
        Returns:
            True if slot is within a window, False otherwise
        """
        date = start_dt.date()
        windows = AvailabilityWindow.objects.for_date(service, date)
        
        for window in windows:
            tz = pytz.timezone(window.timezone)
            window_start = tz.localize(datetime.combine(date, window.start_time))
            window_end = tz.localize(datetime.combine(date, window.end_time))
            
            # Check if appointment fits within window
            if window_start <= start_dt and end_dt <= window_end:
                return True
        
        return False
    
    @transaction.atomic
    def cancel_appointment(self, appointment_id: str) -> Appointment:
        """
        Cancel an appointment.
        
        Args:
            appointment_id: Appointment UUID
            
        Returns:
            Updated Appointment instance
            
        Raises:
            Appointment.DoesNotExist: If appointment not found
            ValidationError: If appointment cannot be canceled
        """
        # Get appointment and validate tenant ownership
        appointment = Appointment.objects.get(id=appointment_id, tenant=self.tenant)
        
        # Check if appointment can be canceled
        if not appointment.can_cancel():
            raise ValidationError(
                f"Cannot cancel appointment with status '{appointment.status}' or past appointments"
            )
        
        # Update status
        appointment.status = 'canceled'
        appointment.save(update_fields=['status', 'updated_at'])
        
        return appointment
    
    def propose_alternatives(
        self,
        service_id: str,
        requested_dt: datetime,
        variant_id: Optional[str] = None,
        max_alternatives: int = 3
    ) -> List[Dict]:
        """
        Propose alternative time slots when requested slot is unavailable.
        
        Searches for available slots within ±3 days of requested time.
        
        Args:
            service_id: Service UUID
            requested_dt: Requested datetime
            variant_id: Optional service variant UUID
            max_alternatives: Maximum number of alternatives to return
            
        Returns:
            List of alternative slots (same format as find_availability)
        """
        # Get service and variant
        service = Service.objects.get(id=service_id, tenant=self.tenant, is_active=True)
        
        variant = None
        if variant_id:
            variant = ServiceVariant.objects.get(id=variant_id, service=service)
        
        duration_minutes = variant.duration_minutes if variant else 60
        
        # Search window: ±3 days
        search_start = requested_dt - timedelta(days=3)
        search_end = requested_dt + timedelta(days=3)
        
        # Find all available slots
        all_slots = self.find_availability(
            service_id,
            search_start,
            search_end,
            variant_id
        )
        
        if not all_slots:
            return []
        
        # Sort by proximity to requested time
        def time_distance(slot):
            return abs((slot['start_dt'] - requested_dt).total_seconds())
        
        all_slots.sort(key=time_distance)
        
        # Return top N alternatives
        return all_slots[:max_alternatives]
    
    def get_appointment(self, appointment_id: str) -> Appointment:
        """
        Get appointment by ID with tenant validation.
        
        Args:
            appointment_id: Appointment UUID
            
        Returns:
            Appointment instance
            
        Raises:
            Appointment.DoesNotExist: If appointment not found or doesn't belong to tenant
        """
        return Appointment.objects.get(id=appointment_id, tenant=self.tenant)
    
    def list_appointments(
        self,
        customer_id: Optional[str] = None,
        service_id: Optional[str] = None,
        status: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None
    ) -> List[Appointment]:
        """
        List appointments with optional filters.
        
        Args:
            customer_id: Filter by customer UUID
            service_id: Filter by service UUID
            status: Filter by status
            from_dt: Filter by start datetime >= from_dt
            to_dt: Filter by start datetime <= to_dt
            
        Returns:
            List of Appointment instances
        """
        queryset = Appointment.objects.for_tenant(self.tenant)
        
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        if service_id:
            queryset = queryset.filter(service_id=service_id)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if from_dt:
            queryset = queryset.filter(start_dt__gte=from_dt)
        
        if to_dt:
            queryset = queryset.filter(start_dt__lte=to_dt)
        
        return list(queryset.select_related('customer', 'service', 'variant'))
    
    def get_upcoming_appointments(
        self,
        customer_id: Optional[str] = None,
        days_ahead: int = 30
    ) -> List[Appointment]:
        """
        Get upcoming appointments for a customer or all customers.
        
        Args:
            customer_id: Optional customer UUID filter
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming Appointment instances
        """
        now = timezone.now()
        future = now + timedelta(days=days_ahead)
        
        queryset = Appointment.objects.for_tenant(self.tenant).filter(
            status__in=['pending', 'confirmed'],
            start_dt__gte=now,
            start_dt__lte=future
        )
        
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        return list(queryset.select_related('customer', 'service', 'variant').order_by('start_dt'))
