"""
Views for feedback collection API.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.permissions import HasTenantScopes
from apps.bot.models_feedback import InteractionFeedback, HumanCorrection
from apps.bot.models import AgentInteraction
from apps.bot.serializers_feedback import (
    InteractionFeedbackSerializer,
    FeedbackSubmitSerializer,
    FeedbackAnalyticsSerializer,
    HumanCorrectionSerializer,
    CorrectionApprovalSerializer,
)

logger = logging.getLogger(__name__)


class FeedbackSubmitView(APIView):
    """
    Submit feedback for a bot interaction.
    
    Required scope: None (public endpoint for customers)
    """
    
    authentication_classes = []  # Allow unauthenticated for customer feedback
    permission_classes = []
    
    @extend_schema(
        request=FeedbackSubmitSerializer,
        responses={201: InteractionFeedbackSerializer},
        description="Submit feedback (thumbs up/down) for a bot interaction"
    )
    def post(self, request):
        """Submit feedback for an interaction."""
        serializer = FeedbackSubmitSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get agent interaction
        interaction = AgentInteraction.objects.get(
            id=serializer.validated_data['agent_interaction_id']
        )
        
        # Check if feedback already exists
        existing_feedback = InteractionFeedback.objects.filter(
            agent_interaction=interaction,
            is_deleted=False
        ).first()
        
        if existing_feedback:
            # Update existing feedback
            existing_feedback.rating = serializer.validated_data['rating']
            existing_feedback.feedback_text = serializer.validated_data.get('feedback_text', '')
            existing_feedback.save()
            
            logger.info(
                f"Updated feedback for interaction {interaction.id}: "
                f"{existing_feedback.rating}"
            )
            
            response_serializer = InteractionFeedbackSerializer(existing_feedback)
            return Response(response_serializer.data)
        
        # Create new feedback
        feedback = InteractionFeedback.objects.create(
            tenant=interaction.tenant,
            agent_interaction=interaction,
            conversation=interaction.conversation,
            customer=interaction.conversation.customer,
            rating=serializer.validated_data['rating'],
            feedback_text=serializer.validated_data.get('feedback_text', ''),
            feedback_source='api'
        )
        
        logger.info(
            f"Created feedback for interaction {interaction.id}: "
            f"{feedback.rating}"
        )
        
        response_serializer = InteractionFeedbackSerializer(feedback)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class FeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View feedback history and analytics.
    
    Required scope: analytics:view
    """
    
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    serializer_class = InteractionFeedbackSerializer
    
    def get_queryset(self):
        """Get feedback for current tenant."""
        return InteractionFeedback.objects.filter(
            tenant=self.request.tenant,
            is_deleted=False
        ).select_related(
            'agent_interaction',
            'conversation',
            'customer'
        ).order_by('-created_at')
    
    @extend_schema(
        responses={200: FeedbackAnalyticsSerializer},
        parameters=[
            OpenApiParameter(
                name='days',
                type=int,
                description='Number of days to analyze (default: 30)',
                required=False
            )
        ],
        description="Get aggregated feedback analytics"
    )
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get feedback analytics."""
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        
        # Get feedback for period
        feedback_qs = InteractionFeedback.objects.filter(
            tenant=request.tenant,
            created_at__gte=since,
            is_deleted=False
        )
        
        total_feedback = feedback_qs.count()
        
        if total_feedback == 0:
            return Response({
                'total_feedback': 0,
                'helpful_count': 0,
                'not_helpful_count': 0,
                'helpful_rate': 0.0,
                'avg_implicit_score': 0.0,
                'feedback_with_comments': 0,
                'user_continued_rate': 0.0,
                'completed_action_rate': 0.0,
                'requested_human_rate': 0.0,
            })
        
        # Calculate metrics
        helpful_count = feedback_qs.filter(rating='helpful').count()
        not_helpful_count = feedback_qs.filter(rating='not_helpful').count()
        helpful_rate = helpful_count / total_feedback if total_feedback > 0 else 0.0
        
        # Calculate implicit scores
        implicit_scores = [
            fb.implicit_satisfaction_score
            for fb in feedback_qs
        ]
        avg_implicit_score = sum(implicit_scores) / len(implicit_scores) if implicit_scores else 0.0
        
        # Count behavioral signals
        feedback_with_comments = feedback_qs.exclude(feedback_text='').count()
        user_continued_count = feedback_qs.filter(user_continued=True).count()
        completed_action_count = feedback_qs.filter(completed_action=True).count()
        requested_human_count = feedback_qs.filter(requested_human=True).count()
        
        analytics = {
            'total_feedback': total_feedback,
            'helpful_count': helpful_count,
            'not_helpful_count': not_helpful_count,
            'helpful_rate': helpful_rate,
            'avg_implicit_score': avg_implicit_score,
            'feedback_with_comments': feedback_with_comments,
            'user_continued_rate': user_continued_count / total_feedback,
            'completed_action_rate': completed_action_count / total_feedback,
            'requested_human_rate': requested_human_count / total_feedback,
        }
        
        serializer = FeedbackAnalyticsSerializer(analytics)
        return Response(serializer.data)


class HumanCorrectionViewSet(viewsets.ModelViewSet):
    """
    Manage human corrections to bot responses.
    
    Required scopes:
    - GET: analytics:view
    - POST/PUT/DELETE: users:manage
    """
    
    permission_classes = [HasTenantScopes]
    serializer_class = HumanCorrectionSerializer
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method."""
        if request.method == 'GET':
            self.required_scopes = {'analytics:view'}
        else:
            self.required_scopes = {'users:manage'}
        super().check_permissions(request)
    
    def get_queryset(self):
        """Get corrections for current tenant."""
        return HumanCorrection.objects.filter(
            tenant=self.request.tenant,
            is_deleted=False
        ).select_related(
            'agent_interaction',
            'conversation',
            'corrected_by',
            'approved_by'
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create correction with tenant and user."""
        serializer.save(
            tenant=self.request.tenant,
            corrected_by=self.request.user
        )
    
    @extend_schema(
        request=CorrectionApprovalSerializer,
        responses={200: HumanCorrectionSerializer},
        description="Approve or reject correction for training"
    )
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve correction for training."""
        correction = self.get_object()
        
        serializer = CorrectionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update approval status
        correction.approved_for_training = serializer.validated_data['approved']
        correction.approved_by = request.user
        correction.approved_at = timezone.now()
        
        if 'quality_score' in serializer.validated_data:
            correction.quality_score = serializer.validated_data['quality_score']
        
        correction.save()
        
        logger.info(
            f"Correction {correction.id} "
            f"{'approved' if correction.approved_for_training else 'rejected'} "
            f"by {request.user.get_full_name()}"
        )
        
        response_serializer = HumanCorrectionSerializer(correction)
        return Response(response_serializer.data)
    
    @extend_schema(
        responses={200: HumanCorrectionSerializer(many=True)},
        description="Get corrections approved for training"
    )
    @action(detail=False, methods=['get'])
    def approved(self, request):
        """Get corrections approved for training."""
        corrections = self.get_queryset().filter(
            approved_for_training=True
        )
        
        serializer = self.get_serializer(corrections, many=True)
        return Response(serializer.data)
