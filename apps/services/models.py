"""
Service models for bookable services and appointments.

Implements service catalog, availability windows, and appointment booking
with capacity management and tenant isolation.
"""
from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel


class ServiceManager(models.Manager):
    """Manager for service queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get services for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def active(self):
        """Get only active services."""
        return self.filter(is_active=True)
    
    def for_tenant_active(self, tenant):
        """Get active services for a specific tenant."""
        return self.filter(tenant=tenant, is_active=True)


class Service(BaseModel):
    """
    Service model representing a bookable service offering.
    
    Services are tenant-scoped and can have multiple variants with
    different durations and pricing. Examples: haircut, consultation,
    massage, etc.
    
    Each service has:
    - Title and description
    - Base pricing (can be overridden by variants)
    - Images for display
    - Availability windows defining when it can be booked
    - Active status for catalog management
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='services',
        db_index=True,
        help_text="Tenant this service belongs to"
    )
    
    # Basic Information
    title = models.CharField(
        max_length=500,
        help_text="Service title"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Service description"
    )
    images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image URLs"
    )
    
    # Pricing
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base price (can be overridden by variants)"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code"
    )
    
    # Configuration
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether service is active and bookable"
    )
    requires_slot = models.BooleanField(
        default=True,
        help_text="Whether service requires time slot booking"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional service metadata"
    )
    
    # Custom manager
    objects = ServiceManager()
    
    class Meta:
        db_table = 'services'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'title']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.tenant.slug})"
    
    def get_price(self):
        """Get service price (base_price or from first variant)."""
        if self.base_price:
            return self.base_price
        
        # Try to get price from first variant
        first_variant = self.variants.first()
        if first_variant and first_variant.price:
            return first_variant.price
        
        return None


class ServiceVariantManager(models.Manager):
    """Manager for service variant queries."""
    
    def for_service(self, service):
        """Get variants for a specific service."""
        return self.filter(service=service)


class ServiceVariant(BaseModel):
    """
    Service variant representing a specific configuration of a service.
    
    Variants allow services to have different durations, pricing, or
    attributes. For example:
    - Haircut: Men's Cut (30 min, $25), Women's Cut (45 min, $40)
    - Massage: 30-minute ($50), 60-minute ($90), 90-minute ($120)
    
    Each variant has:
    - Title describing the variant
    - Duration in minutes
    - Optional price override
    - Custom attributes (JSON)
    """
    
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='variants',
        db_index=True,
        help_text="Service this variant belongs to"
    )
    
    # Basic Information
    title = models.CharField(
        max_length=255,
        help_text="Variant title (e.g., '30-minute session')"
    )
    duration_minutes = models.IntegerField(
        help_text="Duration in minutes"
    )
    
    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Variant price (overrides service base_price if set)"
    )
    
    # Attributes
    attrs = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom attributes (e.g., {'level': 'premium', 'therapist': 'senior'})"
    )
    
    # Custom manager
    objects = ServiceVariantManager()
    
    class Meta:
        db_table = 'service_variants'
        ordering = ['duration_minutes', 'price']
        indexes = [
            models.Index(fields=['service', 'duration_minutes']),
        ]
    
    def __str__(self):
        return f"{self.service.title} - {self.title}"
    
    def get_price(self):
        """Get variant price or fall back to service base price."""
        if self.price:
            return self.price
        return self.service.base_price
    
    def clean(self):
        """Validate variant data."""
        super().clean()
        
        if self.duration_minutes <= 0:
            raise ValidationError({
                'duration_minutes': 'Duration must be greater than 0'
            })


class AvailabilityWindowManager(models.Manager):
    """Manager for availability window queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get availability windows for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_service(self, service):
        """Get availability windows for a specific service."""
        return self.filter(service=service)
    
    def for_date(self, service, date):
        """Get availability windows for a specific date."""
        weekday = date.weekday()  # 0=Monday, 6=Sunday
        return self.filter(
            service=service
        ).filter(
            models.Q(date=date) | models.Q(weekday=weekday, date__isnull=True)
        )
    
    def recurring(self):
        """Get recurring availability windows (weekday-based)."""
        return self.filter(weekday__isnull=False, date__isnull=True)
    
    def specific_date(self):
        """Get specific date availability windows."""
        return self.filter(date__isnull=False)


class AvailabilityWindow(BaseModel):
    """
    Availability window defining when a service can be booked.
    
    Windows can be:
    - Recurring: Based on weekday (0=Monday, 6=Sunday)
    - Specific: For a particular date
    
    Each window has:
    - Time range (start_time to end_time)
    - Capacity (number of concurrent bookings allowed)
    - Timezone for proper time handling
    
    Examples:
    - Recurring: Every Monday 9:00-17:00, capacity 3
    - Specific: 2025-12-25 10:00-14:00, capacity 1 (holiday hours)
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='availability_windows',
        db_index=True,
        help_text="Tenant this availability window belongs to"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='availability_windows',
        db_index=True,
        help_text="Service this availability window applies to"
    )
    
    # Date/Time Configuration
    # Either weekday (recurring) OR date (specific) should be set, not both
    weekday = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of week (0=Monday, 6=Sunday) for recurring availability"
    )
    date = models.DateField(
        null=True,
        blank=True,
        help_text="Specific date for one-time availability"
    )
    
    start_time = models.TimeField(
        help_text="Start time of availability window"
    )
    end_time = models.TimeField(
        help_text="End time of availability window"
    )
    
    # Capacity
    capacity = models.IntegerField(
        default=1,
        help_text="Number of concurrent appointments allowed"
    )
    
    # Timezone
    timezone = models.CharField(
        max_length=50,
        help_text="Timezone for this availability window"
    )
    
    # Custom manager
    objects = AvailabilityWindowManager()
    
    class Meta:
        db_table = 'availability_windows'
        ordering = ['weekday', 'date', 'start_time']
        indexes = [
            models.Index(fields=['tenant', 'service', 'weekday']),
            models.Index(fields=['tenant', 'service', 'date']),
            models.Index(fields=['service', 'weekday']),
            models.Index(fields=['service', 'date']),
        ]
    
    def __str__(self):
        if self.weekday is not None:
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_name = days[self.weekday]
            return f"{self.service.title} - {day_name} {self.start_time}-{self.end_time}"
        return f"{self.service.title} - {self.date} {self.start_time}-{self.end_time}"
    
    def clean(self):
        """Validate availability window data."""
        super().clean()
        
        # Validate weekday range
        if self.weekday is not None and (self.weekday < 0 or self.weekday > 6):
            raise ValidationError({
                'weekday': 'Weekday must be between 0 (Monday) and 6 (Sunday)'
            })
        
        # Validate that either weekday or date is set, not both
        if self.weekday is not None and self.date is not None:
            raise ValidationError(
                'Cannot set both weekday and date. Use weekday for recurring or date for specific.'
            )
        
        if self.weekday is None and self.date is None:
            raise ValidationError(
                'Must set either weekday (for recurring) or date (for specific date)'
            )
        
        # Validate time range
        if self.end_time <= self.start_time:
            raise ValidationError({
                'end_time': 'End time must be after start time'
            })
        
        # Validate capacity
        if self.capacity < 1:
            raise ValidationError({
                'capacity': 'Capacity must be at least 1'
            })
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def is_recurring(self):
        """Check if this is a recurring availability window."""
        return self.weekday is not None
    
    def is_specific_date(self):
        """Check if this is a specific date availability window."""
        return self.date is not None


class AppointmentManager(models.Manager):
    """Manager for appointment queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get appointments for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_customer(self, customer):
        """Get appointments for a specific customer."""
        return self.filter(customer=customer)
    
    def for_service(self, service):
        """Get appointments for a specific service."""
        return self.filter(service=service)
    
    def by_status(self, status):
        """Get appointments with a specific status."""
        return self.filter(status=status)
    
    def upcoming(self):
        """Get upcoming appointments (pending or confirmed)."""
        from django.utils import timezone
        return self.filter(
            status__in=['pending', 'confirmed'],
            start_dt__gte=timezone.now()
        )
    
    def in_date_range(self, start_dt, end_dt):
        """Get appointments in a date range."""
        return self.filter(start_dt__lt=end_dt, end_dt__gt=start_dt)
    
    def overlapping(self, service, start_dt, end_dt):
        """Get appointments that overlap with a time range for a service."""
        return self.filter(
            service=service,
            status__in=['pending', 'confirmed'],
            start_dt__lt=end_dt,
            end_dt__gt=start_dt
        )


class Appointment(BaseModel):
    """
    Appointment model representing a booked service slot.
    
    Appointments are created when customers book services through
    WhatsApp or API. Each appointment:
    - Is scoped to a tenant and customer
    - References a service and optional variant
    - Has a specific time slot (start_dt to end_dt)
    - Tracks status through lifecycle
    - Can include customer notes
    
    Status lifecycle:
    - pending: Initial booking, awaiting confirmation
    - confirmed: Confirmed by business
    - done: Service completed
    - canceled: Canceled by customer or business
    - no_show: Customer didn't show up
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
        ('no_show', 'No Show'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='appointments',
        db_index=True,
        help_text="Tenant this appointment belongs to"
    )
    customer = models.ForeignKey(
        'tenants.Customer',
        on_delete=models.CASCADE,
        related_name='appointments',
        db_index=True,
        help_text="Customer who booked the appointment"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='appointments',
        db_index=True,
        help_text="Service being booked"
    )
    variant = models.ForeignKey(
        ServiceVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text="Specific service variant (optional)"
    )
    
    # Time Slot
    start_dt = models.DateTimeField(
        db_index=True,
        help_text="Appointment start date and time"
    )
    end_dt = models.DateTimeField(
        db_index=True,
        help_text="Appointment end date and time"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current appointment status"
    )
    
    # Additional Information
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Customer notes or special requests"
    )
    provider_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="External calendar or booking system reference"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional appointment metadata"
    )
    
    # Custom manager
    objects = AppointmentManager()
    
    class Meta:
        db_table = 'appointments'
        ordering = ['start_dt']
        indexes = [
            models.Index(fields=['tenant', 'customer', 'status']),
            models.Index(fields=['tenant', 'service', 'start_dt']),
            models.Index(fields=['tenant', 'start_dt', 'status']),
            models.Index(fields=['service', 'start_dt', 'status']),
            models.Index(fields=['customer', 'start_dt']),
            models.Index(fields=['status', 'start_dt']),
        ]
    
    def __str__(self):
        return f"{self.customer} - {self.service.title} at {self.start_dt}"
    
    def duration_minutes(self):
        """Calculate appointment duration in minutes."""
        delta = self.end_dt - self.start_dt
        return int(delta.total_seconds() / 60)
    
    def is_upcoming(self):
        """Check if appointment is in the future."""
        from django.utils import timezone
        return self.start_dt > timezone.now()
    
    def is_past(self):
        """Check if appointment is in the past."""
        from django.utils import timezone
        return self.end_dt < timezone.now()
    
    def can_cancel(self):
        """Check if appointment can be canceled."""
        return self.status in ['pending', 'confirmed'] and self.is_upcoming()
    
    def clean(self):
        """Validate appointment data."""
        super().clean()
        
        # Validate time range
        if self.end_dt <= self.start_dt:
            raise ValidationError({
                'end_dt': 'End time must be after start time'
            })
        
        # Validate tenant consistency
        if self.customer.tenant_id != self.tenant_id:
            raise ValidationError({
                'customer': 'Customer must belong to the same tenant'
            })
        
        if self.service.tenant_id != self.tenant_id:
            raise ValidationError({
                'service': 'Service must belong to the same tenant'
            })
        
        # Validate variant belongs to service
        if self.variant and self.variant.service_id != self.service_id:
            raise ValidationError({
                'variant': 'Variant must belong to the selected service'
            })
