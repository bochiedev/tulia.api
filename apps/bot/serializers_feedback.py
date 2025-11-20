"""
Serializers for feedback collection API.
"""

from rest_framework import serializers
from apps.bot.models_feedback import InteractionFeedback, HumanCorrection


class InteractionFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for interaction feedback."""
    
    implicit_satisfaction_score = serializers.ReadOnlyField()
    
    class Meta:
        model = InteractionFeedback
        fields = [
            'id',
            'agent_interaction',
            'conversation',
            'customer',
            'rating',
            'feedback_text',
            'user_continued',
            'completed_action',
            'requested_human',
            'response_time_seconds',
            'implicit_satisfaction_score',
            'feedback_source',
            'metadata',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'conversation',
            'customer',
            'implicit_satisfaction_score',
            'created_at',
        ]


class FeedbackSubmitSerializer(serializers.Serializer):
    """Serializer for submitting feedback."""
    
    agent_interaction_id = serializers.IntegerField(required=True)
    rating = serializers.ChoiceField(
        choices=['helpful', 'not_helpful'],
        required=True
    )
    feedback_text = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000
    )
    
    def validate_agent_interaction_id(self, value):
        """Validate that agent interaction exists and belongs to tenant."""
        from apps.bot.models import AgentInteraction
        
        request = self.context.get('request')
        if not request or not hasattr(request, 'tenant'):
            raise serializers.ValidationError("Tenant context required")
        
        try:
            interaction = AgentInteraction.objects.get(
                id=value,
                tenant=request.tenant
            )
        except AgentInteraction.DoesNotExist:
            raise serializers.ValidationError("Agent interaction not found")
        
        return value


class FeedbackAnalyticsSerializer(serializers.Serializer):
    """Serializer for feedback analytics."""
    
    total_feedback = serializers.IntegerField()
    helpful_count = serializers.IntegerField()
    not_helpful_count = serializers.IntegerField()
    helpful_rate = serializers.FloatField()
    avg_implicit_score = serializers.FloatField()
    feedback_with_comments = serializers.IntegerField()
    user_continued_rate = serializers.FloatField()
    completed_action_rate = serializers.FloatField()
    requested_human_rate = serializers.FloatField()


class HumanCorrectionSerializer(serializers.ModelSerializer):
    """Serializer for human corrections."""
    
    corrected_by_name = serializers.CharField(
        source='corrected_by.get_full_name',
        read_only=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = HumanCorrection
        fields = [
            'id',
            'agent_interaction',
            'conversation',
            'bot_response',
            'human_response',
            'correction_reason',
            'correction_category',
            'corrected_by',
            'corrected_by_name',
            'approved_for_training',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'quality_score',
            'metadata',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'corrected_by_name',
            'approved_by_name',
            'created_at',
        ]


class CorrectionApprovalSerializer(serializers.Serializer):
    """Serializer for approving corrections for training."""
    
    approved = serializers.BooleanField(required=True)
    quality_score = serializers.FloatField(
        required=False,
        min_value=0.0,
        max_value=5.0
    )
