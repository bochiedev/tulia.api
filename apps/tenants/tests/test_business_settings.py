"""
Tests for business settings serializers and validation.

Focuses on testing the validation logic for:
- Timezone validation
- Business hours format validation
- Quiet hours format validation
- Notification preferences validation
"""
import pytest
from rest_framework.exceptions import ValidationError

from apps.tenants.serializers_settings import BusinessSettingsSerializer


class TestBusinessSettingsSerializer:
    """Test BusinessSettingsSerializer validation."""
    
    def test_valid_timezone(self):
        """Test that valid IANA timezones are accepted."""
        serializer = BusinessSettingsSerializer(data={
            'timezone': 'America/New_York'
        })
        assert serializer.is_valid()
        assert serializer.validated_data['timezone'] == 'America/New_York'
        
        serializer = BusinessSettingsSerializer(data={
            'timezone': 'Europe/London'
        })
        assert serializer.is_valid()
        
        serializer = BusinessSettingsSerializer(data={
            'timezone': 'Asia/Tokyo'
        })
        assert serializer.is_valid()
    
    def test_invalid_timezone(self):
        """Test that invalid timezones are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'timezone': 'Invalid/Timezone'
        })
        assert not serializer.is_valid()
        assert 'timezone' in serializer.errors
    
    def test_valid_business_hours(self):
        """Test that valid business hours format is accepted."""
        serializer = BusinessSettingsSerializer(data={
            'business_hours': {
                'monday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'tuesday': {'open': '08:30', 'close': '18:30', 'closed': False},
                'sunday': {'closed': True}
            }
        })
        assert serializer.is_valid()
    
    def test_invalid_business_hours_day(self):
        """Test that invalid day names are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'business_hours': {
                'invalidday': {'open': '09:00', 'close': '17:00', 'closed': False}
            }
        })
        assert not serializer.is_valid()
        assert 'business_hours' in serializer.errors
    
    def test_invalid_business_hours_time_format(self):
        """Test that invalid time formats are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'business_hours': {
                'monday': {'open': '25:00', 'close': '17:00', 'closed': False}
            }
        })
        assert not serializer.is_valid()
        assert 'business_hours' in serializer.errors
        
        serializer = BusinessSettingsSerializer(data={
            'business_hours': {
                'monday': {'open': '09:00', 'close': '17:70', 'closed': False}
            }
        })
        assert not serializer.is_valid()
        assert 'business_hours' in serializer.errors
    
    def test_business_hours_missing_time(self):
        """Test that missing open/close times are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'business_hours': {
                'monday': {'open': '09:00', 'closed': False}
            }
        })
        assert not serializer.is_valid()
        assert 'business_hours' in serializer.errors
    
    def test_business_hours_closed_day_no_times_required(self):
        """Test that closed days don't require open/close times."""
        serializer = BusinessSettingsSerializer(data={
            'business_hours': {
                'sunday': {'closed': True}
            }
        })
        assert serializer.is_valid()
    
    def test_valid_quiet_hours(self):
        """Test that valid quiet hours format is accepted."""
        serializer = BusinessSettingsSerializer(data={
            'quiet_hours': {
                'enabled': True,
                'start': '22:00',
                'end': '08:00'
            }
        })
        assert serializer.is_valid()
    
    def test_quiet_hours_disabled_no_times_required(self):
        """Test that disabled quiet hours don't require times."""
        serializer = BusinessSettingsSerializer(data={
            'quiet_hours': {
                'enabled': False
            }
        })
        assert serializer.is_valid()
    
    def test_invalid_quiet_hours_time_format(self):
        """Test that invalid quiet hours time formats are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'quiet_hours': {
                'enabled': True,
                'start': 'invalid',
                'end': '08:00'
            }
        })
        assert not serializer.is_valid()
        assert 'quiet_hours' in serializer.errors
    
    def test_quiet_hours_missing_times(self):
        """Test that enabled quiet hours require start and end times."""
        serializer = BusinessSettingsSerializer(data={
            'quiet_hours': {
                'enabled': True,
                'start': '22:00'
            }
        })
        assert not serializer.is_valid()
        assert 'quiet_hours' in serializer.errors
    
    def test_quiet_hours_overnight_range_allowed(self):
        """Test that overnight ranges (e.g., 22:00 to 08:00) are allowed."""
        serializer = BusinessSettingsSerializer(data={
            'quiet_hours': {
                'enabled': True,
                'start': '22:00',
                'end': '08:00'
            }
        })
        assert serializer.is_valid()
        # Note: The application logic should handle overnight ranges correctly
    
    def test_valid_notification_preferences(self):
        """Test that valid notification preferences are accepted."""
        serializer = BusinessSettingsSerializer(data={
            'notification_preferences': {
                'email': {
                    'order_received': True,
                    'low_stock': False,
                    'appointment_booked': True
                },
                'sms': {
                    'critical_alerts': True
                },
                'in_app': {
                    'order_received': True
                }
            }
        })
        assert serializer.is_valid()
    
    def test_invalid_notification_channel(self):
        """Test that invalid notification channels are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'notification_preferences': {
                'invalid_channel': {
                    'order_received': True
                }
            }
        })
        assert not serializer.is_valid()
        assert 'notification_preferences' in serializer.errors
    
    def test_invalid_notification_value_type(self):
        """Test that non-boolean notification values are rejected."""
        serializer = BusinessSettingsSerializer(data={
            'notification_preferences': {
                'email': {
                    'order_received': 'yes'  # Should be boolean
                }
            }
        })
        assert not serializer.is_valid()
        assert 'notification_preferences' in serializer.errors
    
    def test_all_fields_together(self):
        """Test that all fields can be validated together."""
        serializer = BusinessSettingsSerializer(data={
            'timezone': 'America/Chicago',
            'business_hours': {
                'monday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'tuesday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'wednesday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'thursday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'friday': {'open': '09:00', 'close': '17:00', 'closed': False},
                'saturday': {'open': '10:00', 'close': '14:00', 'closed': False},
                'sunday': {'closed': True}
            },
            'quiet_hours': {
                'enabled': True,
                'start': '22:00',
                'end': '08:00'
            },
            'notification_preferences': {
                'email': {
                    'order_received': True,
                    'low_stock': True,
                    'appointment_booked': True
                },
                'sms': {
                    'critical_alerts': True
                }
            }
        })
        assert serializer.is_valid()
        
        validated = serializer.validated_data
        assert validated['timezone'] == 'America/Chicago'
        assert 'monday' in validated['business_hours']
        assert validated['quiet_hours']['enabled'] is True
        assert 'email' in validated['notification_preferences']
