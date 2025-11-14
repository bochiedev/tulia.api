"""
Bot API views for agent configuration.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse
import logging

from apps.bot.models import AgentConfiguration
from apps.bot.serializers import (
    AgentConfigurationSerializer,
    AgentConfigurationUpdateSerializer
)
from apps.bot.services import AgentConfigurationService
from apps.core.permissions import HasTenantScopes

logger = logging.getLogger(__name__)


class AgentConfigurationView(APIView):
    """
    Retrieve and update agent configuration for the authenticated tenant.
    
    GET /v1/bot/agent-config - Get current agent configuration
    PUT /v1/bot/agent-config - Update agent configuration
    
    Required scope: integrations:manage
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    
    @extend_schema(
        summary="Get agent configuration",
        description="Retrieve the AI agent configuration for the authenticated tenant. "
                    "If no configuration exists, returns default configuration.",
        responses={
            200: AgentConfigurationSerializer,
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            404: OpenApiResponse(description="Not found - Tenant does not exist"),
        },
        tags=['Bot']
    )
    def get(self, request):
        """
        Get agent configuration for the authenticated tenant.
        
        Returns the current configuration or creates a default one if none exists.
        
        Example:
            curl -X GET https://api.tulia.ai/v1/bot/agent-config \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        try:
            tenant = request.tenant
            
            # Get or create configuration
            config = AgentConfigurationService.get_or_create_configuration(tenant)
            
            # Serialize and return
            serializer = AgentConfigurationSerializer(config)
            
            logger.info(
                f"Retrieved agent configuration for tenant {tenant.id}",
                extra={
                    'tenant_id': str(tenant.id),
                    'agent_name': config.agent_name,
                    'default_model': config.default_model
                }
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error retrieving agent configuration: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve agent configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Update agent configuration",
        description="Update the AI agent configuration for the authenticated tenant. "
                    "Supports partial updates - only provided fields will be updated.",
        request=AgentConfigurationUpdateSerializer,
        responses={
            200: AgentConfigurationSerializer,
            400: OpenApiResponse(description="Bad request - Invalid configuration data"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            404: OpenApiResponse(description="Not found - Tenant does not exist"),
        },
        tags=['Bot']
    )
    def put(self, request):
        """
        Update agent configuration for the authenticated tenant.
        
        Validates and updates the configuration. Supports partial updates.
        Cache is automatically invalidated after update.
        
        Example:
            curl -X PUT https://api.tulia.ai/v1/bot/agent-config \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>" \
                -H "Content-Type: application/json" \
                -d '{
                    "agent_name": "Sarah",
                    "tone": "friendly",
                    "default_model": "gpt-4o",
                    "confidence_threshold": 0.75
                }'
        """
        try:
            tenant = request.tenant
            
            # Validate input
            serializer = AgentConfigurationUpdateSerializer(data=request.data, partial=True)
            if not serializer.is_valid():
                logger.warning(
                    f"Invalid agent configuration data for tenant {tenant.id}",
                    extra={
                        'tenant_id': str(tenant.id),
                        'errors': serializer.errors
                    }
                )
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Update configuration
            config = AgentConfigurationService.update_configuration(
                tenant,
                serializer.validated_data
            )
            
            # Return updated configuration
            response_serializer = AgentConfigurationSerializer(config)
            
            logger.info(
                f"Updated agent configuration for tenant {tenant.id}",
                extra={
                    'tenant_id': str(tenant.id),
                    'updated_fields': list(serializer.validated_data.keys()),
                    'agent_name': config.agent_name
                }
            )
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error updating agent configuration: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to update agent configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
