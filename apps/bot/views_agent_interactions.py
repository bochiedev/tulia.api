"""
Agent Interaction API views for analytics and monitoring.

Provides endpoints for viewing and analyzing AI agent interactions
with proper RBAC enforcement and tenant isolation.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from datetime import datetime, timedelta
from django.db.models import Avg, Count, Sum, Q
import logging

from apps.bot.models import AgentInteraction
from apps.bot.serializers import (
    AgentInteractionSerializer,
    AgentInteractionListSerializer,
    AgentInteractionStatsSerializer,
)
from apps.core.permissions import HasTenantScopes

logger = logging.getLogger(__name__)


class AgentInteractionPagination(PageNumberPagination):
    """Pagination for agent interaction list."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class AgentInteractionListView(APIView):
    """
    List agent interactions for the authenticated tenant.
    
    GET /v1/bot/interactions - List all interactions with filtering
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    pagination_class = AgentInteractionPagination
    
    @extend_schema(
        summary="List agent interactions",
        description="Retrieve all AI agent interactions for the authenticated tenant. "
                    "Supports filtering by conversation, model, confidence, handoff status, and date range.",
        parameters=[
            OpenApiParameter(
                name='conversation_id',
                type=str,
                description='Filter by conversation ID',
                required=False
            ),
            OpenApiParameter(
                name='model_used',
                type=str,
                description='Filter by model name',
                required=False
            ),
            OpenApiParameter(
                name='handoff_triggered',
                type=str,
                description='Filter by handoff status (true/false)',
                required=False
            ),
            OpenApiParameter(
                name='min_confidence',
                type=float,
                description='Minimum confidence score (0.0-1.0)',
                required=False
            ),
            OpenApiParameter(
                name='max_confidence',
                type=float,
                description='Maximum confidence score (0.0-1.0)',
                required=False
            ),
            OpenApiParameter(
                name='start_date',
                type=str,
                description='Start date (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                description='End date (YYYY-MM-DD)',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=int,
                description='Page number',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                description='Page size (max 200)',
                required=False
            ),
        ],
        responses={
            200: AgentInteractionListSerializer(many=True),
            400: OpenApiResponse(description="Bad request - Invalid filter parameters"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
        },
        tags=['Bot - Agent Interactions']
    )
    def get(self, request):
        """
        List agent interactions with filtering.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/interactions?model_used=gpt-4o&page=1" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        try:
            # Start with tenant-scoped queryset
            queryset = AgentInteraction.objects.for_tenant(request.tenant)
            
            # Apply filters
            conversation_id = request.query_params.get('conversation_id')
            if conversation_id:
                queryset = queryset.filter(conversation_id=conversation_id)
            
            model_used = request.query_params.get('model_used')
            if model_used:
                queryset = queryset.filter(model_used=model_used)
            
            handoff_triggered = request.query_params.get('handoff_triggered')
            if handoff_triggered:
                if handoff_triggered.lower() == 'true':
                    queryset = queryset.filter(handoff_triggered=True)
                elif handoff_triggered.lower() == 'false':
                    queryset = queryset.filter(handoff_triggered=False)
            
            min_confidence = request.query_params.get('min_confidence')
            if min_confidence:
                try:
                    min_conf = float(min_confidence)
                    queryset = queryset.filter(confidence_score__gte=min_conf)
                except ValueError:
                    return Response(
                        {'error': 'Invalid min_confidence value'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            max_confidence = request.query_params.get('max_confidence')
            if max_confidence:
                try:
                    max_conf = float(max_confidence)
                    queryset = queryset.filter(confidence_score__lte=max_conf)
                except ValueError:
                    return Response(
                        {'error': 'Invalid max_confidence value'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Date range filters
            start_date = request.query_params.get('start_date')
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__gte=start_dt)
                except ValueError:
                    return Response(
                        {'error': 'Invalid start_date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            end_date = request.query_params.get('end_date')
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__lte=end_dt)
                except ValueError:
                    return Response(
                        {'error': 'Invalid end_date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Order by most recent first
            queryset = queryset.order_by('-created_at')
            
            # Paginate
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            
            if page is not None:
                serializer = AgentInteractionListSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = AgentInteractionListSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error listing agent interactions: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to list agent interactions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgentInteractionDetailView(APIView):
    """
    Retrieve a specific agent interaction by ID.
    
    GET /v1/bot/interactions/{id} - Get interaction details
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get agent interaction details",
        description="Retrieve detailed information about a specific agent interaction.",
        responses={
            200: AgentInteractionSerializer,
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
            404: OpenApiResponse(description="Not found - Interaction does not exist"),
        },
        tags=['Bot - Agent Interactions']
    )
    def get(self, request, interaction_id):
        """
        Get a specific agent interaction.
        
        Example:
            curl -X GET https://api.tulia.ai/v1/bot/interactions/{id} \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        try:
            # Get interaction with tenant scoping
            interaction = AgentInteraction.objects.for_tenant(request.tenant).get(
                id=interaction_id
            )
            
            serializer = AgentInteractionSerializer(interaction)
            
            logger.info(
                f"Retrieved agent interaction {interaction_id} for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'interaction_id': str(interaction_id)
                }
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except AgentInteraction.DoesNotExist:
            return Response(
                {'error': 'Agent interaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(
                f"Error retrieving agent interaction: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve agent interaction'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgentInteractionStatsView(APIView):
    """
    Get aggregated statistics for agent interactions.
    
    GET /v1/bot/interactions/stats - Get interaction statistics
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get agent interaction statistics",
        description="Retrieve aggregated statistics about agent interactions including "
                    "total interactions, costs, confidence scores, handoff rates, and more.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=str,
                description='Start date (YYYY-MM-DD). Default: 30 days ago',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                description='End date (YYYY-MM-DD). Default: today',
                required=False
            ),
        ],
        responses={
            200: AgentInteractionStatsSerializer,
            400: OpenApiResponse(description="Bad request - Invalid date parameters"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
        },
        tags=['Bot - Agent Interactions']
    )
    def get(self, request):
        """
        Get aggregated statistics for agent interactions.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/interactions/stats?start_date=2024-01-01" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        try:
            # Parse date range
            end_date = request.query_params.get('end_date')
            if end_date:
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {'error': 'Invalid end_date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                end_date = datetime.now().date()
            
            start_date = request.query_params.get('start_date')
            if start_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {'error': 'Invalid start_date format. Use YYYY-MM-DD'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                start_date = end_date - timedelta(days=30)
            
            # Get interactions for tenant in date range
            interactions = AgentInteraction.objects.filter(
                conversation__tenant=request.tenant,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_interactions = interactions.count()
            
            if total_interactions == 0:
                return Response({
                    'total_interactions': 0,
                    'total_cost': '0.000000',
                    'avg_confidence': 0.0,
                    'handoff_count': 0,
                    'handoff_rate': 0.0,
                    'interactions_by_model': {},
                    'cost_by_model': {},
                    'interactions_by_type': {},
                    'high_confidence_count': 0,
                    'low_confidence_count': 0,
                    'avg_processing_time_ms': 0.0,
                    'avg_tokens': 0.0,
                }, status=status.HTTP_200_OK)
            
            # Aggregate statistics
            stats = interactions.aggregate(
                total_cost=Sum('estimated_cost'),
                avg_confidence=Avg('confidence_score'),
                handoff_count=Count('id', filter=Q(handoff_triggered=True)),
                high_confidence_count=Count('id', filter=Q(confidence_score__gte=0.7)),
                low_confidence_count=Count('id', filter=Q(confidence_score__lt=0.7)),
                avg_processing_time=Avg('processing_time_ms'),
            )
            
            # Calculate handoff rate
            handoff_rate = stats['handoff_count'] / total_interactions if total_interactions > 0 else 0.0
            
            # Interactions by model
            interactions_by_model_data = interactions.values('model_used').annotate(
                count=Count('id')
            )
            interactions_by_model = {
                item['model_used']: item['count']
                for item in interactions_by_model_data
            }
            
            # Cost by model
            cost_by_model_data = interactions.values('model_used').annotate(
                total_cost=Sum('estimated_cost')
            )
            cost_by_model = {
                item['model_used']: str(item['total_cost'])
                for item in cost_by_model_data
            }
            
            # Interactions by message type
            interactions_by_type_data = interactions.values('message_type').annotate(
                count=Count('id')
            )
            interactions_by_type = {
                item['message_type']: item['count']
                for item in interactions_by_type_data
            }
            
            # Calculate average tokens
            total_tokens = sum(i.get_total_tokens() for i in interactions)
            avg_tokens = total_tokens / total_interactions if total_interactions > 0 else 0.0
            
            result = {
                'total_interactions': total_interactions,
                'total_cost': str(stats['total_cost'] or 0),
                'avg_confidence': round(stats['avg_confidence'] or 0.0, 3),
                'handoff_count': stats['handoff_count'],
                'handoff_rate': round(handoff_rate, 3),
                'interactions_by_model': interactions_by_model,
                'cost_by_model': cost_by_model,
                'interactions_by_type': interactions_by_type,
                'high_confidence_count': stats['high_confidence_count'],
                'low_confidence_count': stats['low_confidence_count'],
                'avg_processing_time_ms': round(stats['avg_processing_time'] or 0.0, 2),
                'avg_tokens': round(avg_tokens, 2),
            }
            
            logger.info(
                f"Retrieved agent interaction stats for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'total_interactions': total_interactions,
                    'date_range': f"{start_date} to {end_date}"
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error retrieving agent interaction stats: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve agent interaction statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
