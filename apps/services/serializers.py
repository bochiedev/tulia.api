"""
Serializers for services and appointments.
"""
from rest_framework import serializers
from apps.services.models import (
    Service,
    ServiceVariant,
    AvailabilityWindow,
    Appointment
)


class ServiceVariantSerializer(serializers.ModelSerializer):
    """Serializer for service variants."""
    
    price_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceVariant
        fields = [
            'id',
            'title',
            'duration_minutes',
            'price',
            'price_display',
            'attrs',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_price_display(self, obj):
        """Get formatted price."""
        price = obj.get_price()
        if price:
            currency = obj.service.currency
            return f"{currency} {price}"
        return None


class ServiceListSerializer(serializers.ModelSerializer):
    """Serializer for service list view."""
    
    price_display = serializers.SerializerMethodField()
    variant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id',
            'title',
            'description',
            'images',
            'base_price',
            'price_display',
            'currency',
            'is_active',
            'requires_slot',
            'variant_count',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_price_display(self, obj):
        """Get formatted price."""
        price = obj.get_price()
        if price:
            return f"{obj.currency} {price}"
        return None
    
    def get_variant_count(self, obj):
        """Get number of variants."""
        return obj.variants.count()


class ServiceDetailSerializer(serializers.ModelSerializer):
    """Serializer for service detail view with variants."""
    
    variants = ServiceVariantSerializer(many=True, read_only=True)
    price_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = [
            'id',
            'title',
            'description',
            'images',
            'base_price',
            'price_display',
            'currency',
            'is_active',
            'requires_slot',
            'variants',
            'metadata',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_price_display(self, obj):
        """Get formatted price."""
        price = obj.get_price()
        if price:
            return f"{obj.currency} {price}"
        return None


class ServiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating services."""
    
    variants = ServiceVariantSerializer(many=True, required=False)
    
    class Meta:
        model = Service
        fields = [
            'title',
            'description',
            'images',
            'base_price',
            'currency',
            'is_active',
            'requires_slot',
            'metadata',
            'variants'
        ]
    
    def create(self, validated_data):
        """Create service with variants."""
        variants_data = validated_data.pop('variants', [])
        
        # Create service
        service = Service.objects.create(**validated_data)
        
        # Create variants
        for variant_data in variants_data:
            ServiceVariant.objects.create(service=service, **variant_data)
        
        return service


class AvailabilityWindowSerializer(serializers.ModelSerializer):
    """Serializer for availability windows."""
    
    class Meta:
        model = AvailabilityWindow
        fields = [
            'id',
            'weekday',
            'date',
            'start_time',
            'end_time',
            'capacity',
            'timezone',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate availability window data."""
        # Check that either weekday or date is set, not both
        weekday = data.get('weekday')
        date = data.get('date')
        
        if weekday is not None and date is not None:
            raise serializers.ValidationError(
                "Cannot set both weekday and date. Use weekday for recurring or date for specific."
            )
        
        if weekday is None and date is None:
            raise serializers.ValidationError(
                "Must set either weekday (for recurring) or date (for specific date)"
            )
        
        # Validate weekday range
        if weekday is not None and (weekday < 0 or weekday > 6):
            raise serializers.ValidationError({
                'weekday': 'Weekday must be between 0 (Monday) and 6 (Sunday)'
            })
        
        # Validate time range
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time'
            })
        
        return data


class AvailabilitySlotSerializer(serializers.Serializer):
    """Serializer for available time slots."""
    
    start_dt = serializers.DateTimeField()
    end_dt = serializers.DateTimeField()
    capacity_left = serializers.IntegerField()
    window_id = serializers.UUIDField()
    window_capacity = serializers.IntegerField()


class AppointmentListSerializer(serializers.ModelSerializer):
    """Serializer for appointment list view."""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    service_title = serializers.CharField(source='service.title', read_only=True)
    variant_title = serializers.CharField(source='variant.title', read_only=True, allow_null=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'customer_name',
            'service_title',
            'variant_title',
            'start_dt',
            'end_dt',
            'duration_minutes',
            'status',
            'notes',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_duration_minutes(self, obj):
        """Get appointment duration in minutes."""
        return obj.duration_minutes()


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Serializer for appointment detail view."""
    
    customer = serializers.SerializerMethodField()
    service = ServiceListSerializer(read_only=True)
    variant = ServiceVariantSerializer(read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'customer',
            'service',
            'variant',
            'start_dt',
            'end_dt',
            'duration_minutes',
            'status',
            'notes',
            'provider_ref',
            'metadata',
            'can_cancel',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_customer(self, obj):
        """Get customer info (without exposing PII)."""
        return {
            'id': str(obj.customer.id),
            'name': obj.customer.name
        }
    
    def get_duration_minutes(self, obj):
        """Get appointment duration in minutes."""
        return obj.duration_minutes()
    
    def get_can_cancel(self, obj):
        """Check if appointment can be canceled."""
        return obj.can_cancel()


class AppointmentCreateSerializer(serializers.Serializer):
    """Serializer for creating appointments."""
    
    customer_id = serializers.UUIDField(required=True)
    service_id = serializers.UUIDField(required=True)
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    start_dt = serializers.DateTimeField(required=True)
    end_dt = serializers.DateTimeField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.ChoiceField(
        choices=['pending', 'confirmed'],
        default='pending',
        required=False
    )
    
    def validate(self, data):
        """Validate appointment data."""
        start_dt = data.get('start_dt')
        end_dt = data.get('end_dt')
        
        if end_dt <= start_dt:
            raise serializers.ValidationError({
                'end_dt': 'End time must be after start time'
            })
        
        return data


class AppointmentCancelSerializer(serializers.Serializer):
    """Serializer for canceling appointments."""
    
    reason = serializers.CharField(required=False, allow_blank=True)
