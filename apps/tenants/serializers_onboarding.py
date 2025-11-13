"""
Serializers for onboarding API endpoints.
"""
from rest_framework import serializers


class OnboardingStepSerializer(serializers.Serializer):
    """Serializer for individual onboarding step status."""
    
    completed = serializers.BooleanField()
    completed_at = serializers.DateTimeField(allow_null=True)


class OnboardingStatusSerializer(serializers.Serializer):
    """
    Serializer for onboarding status response.
    
    Returns:
    - Overall completion status
    - Completion percentage (based on required steps)
    - Status of each required step
    - Status of each optional step
    - List of pending required steps
    """
    
    completed = serializers.BooleanField(
        help_text="Whether all required onboarding steps are complete"
    )
    completion_percentage = serializers.IntegerField(
        help_text="Completion percentage based on required steps (0-100)"
    )
    required_steps = serializers.DictField(
        child=OnboardingStepSerializer(),
        help_text="Status of each required onboarding step"
    )
    optional_steps = serializers.DictField(
        child=OnboardingStepSerializer(),
        help_text="Status of each optional onboarding step"
    )
    pending_steps = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of pending required step names"
    )


class OnboardingCompleteSerializer(serializers.Serializer):
    """
    Serializer for marking an onboarding step as complete.
    """
    
    step = serializers.CharField(
        required=True,
        help_text="Name of the onboarding step to mark as complete"
    )
    
    def validate_step(self, value):
        """Validate that step name is valid."""
        from apps.tenants.services.onboarding_service import OnboardingService
        
        all_steps = OnboardingService.REQUIRED_STEPS + OnboardingService.OPTIONAL_STEPS
        if value not in all_steps:
            raise serializers.ValidationError(
                f"Invalid step name. Must be one of: {', '.join(all_steps)}"
            )
        
        return value
