"""
API views for tenant onboarding management.

Endpoints:
- GET /v1/settings/onboarding - Get onboarding status
- POST /v1/settings/onboarding/complete - Mark step as complete
"""
import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.permissions import HasTenantScopes
from apps.tenants.services.onboarding_service import OnboardingService
from apps.tenants.serializers_onboarding import (
    OnboardingStatusSerializer,
    OnboardingCompleteSerializer
)

logger = logging.getLogger(__name__)


class OnboardingStatusView(APIView):
    """
    Get tenant onboarding status.
    
    Returns completion percentage, status of each step,
    and list of pending required steps.
    
    Required scope: integrations:view OR users:manage
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Check if user has either integrations:view or users:manage scope."""
        self.required_scopes = {'integrations:view', 'users:manage'}
        if not any(scope in request.scopes for scope in self.required_scopes):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Missing required scope: integrations:view or users:manage')
    
    @extend_schema(
        summary="Get onboarding status",
        description="Get tenant onboarding completion status with step details",
        responses={
            200: OnboardingStatusSerializer,
            403: OpenApiResponse(description="Missing required scope"),
        },
        tags=['Onboarding']
    )
    def get(self, request):
        """Get onboarding status for current tenant."""
        # Get onboarding status from service
        onboarding_status = OnboardingService.get_onboarding_status(request.tenant)
        
        # Serialize and return
        serializer = OnboardingStatusSerializer(onboarding_status)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OnboardingCompleteView(APIView):
    """
    Mark an onboarding step as complete.
    
    Accepts step name and marks it as complete with timestamp.
    Automatically checks if all required steps are now complete.
    
    Required scope: integrations:manage OR users:manage
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Check if user has either integrations:manage or users:manage scope."""
        self.required_scopes = {'integrations:manage', 'users:manage'}
        if not any(scope in request.scopes for scope in self.required_scopes):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Missing required scope: integrations:manage or users:manage')
    
    @extend_schema(
        summary="Mark onboarding step as complete",
        description="Mark a specific onboarding step as complete and check overall completion",
        request=OnboardingCompleteSerializer,
        responses={
            200: OnboardingStatusSerializer,
            400: OpenApiResponse(description="Invalid step name"),
            403: OpenApiResponse(description="Missing required scope"),
        },
        tags=['Onboarding']
    )
    def post(self, request):
        """Mark onboarding step as complete."""
        # Validate request data
        serializer = OnboardingCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        step_name = serializer.validated_data['step']
        
        try:
            # Mark step as complete
            OnboardingService.mark_step_complete(request.tenant, step_name)
            
            # Get updated onboarding status
            onboarding_status = OnboardingService.get_onboarding_status(request.tenant)
            
            # Log completion
            logger.info(
                f"Onboarding step '{step_name}' marked complete for tenant {request.tenant.slug}. "
                f"Overall completion: {onboarding_status['completion_percentage']}%"
            )
            
            # Return updated status
            response_serializer = OnboardingStatusSerializer(onboarding_status)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            # Invalid step name (shouldn't happen due to serializer validation)
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                f"Error marking onboarding step complete for tenant {request.tenant.slug}: {str(e)}"
            )
            return Response(
                {'detail': 'Failed to mark step as complete'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
