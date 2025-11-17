"""
Bot API views for agent configuration and knowledge base management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django.db import transaction
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
import logging
import csv
import io
import json

from apps.bot.models import AgentConfiguration, KnowledgeEntry
from apps.bot.serializers import (
    AgentConfigurationSerializer,
    AgentConfigurationUpdateSerializer,
    KnowledgeEntrySerializer,
    KnowledgeEntryCreateSerializer,
    KnowledgeEntryUpdateSerializer,
    KnowledgeEntrySearchSerializer,
    KnowledgeEntryBulkImportSerializer,
)
from apps.bot.services import AgentConfigurationService, KnowledgeBaseService
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
            429: OpenApiResponse(description="Too many requests - Rate limit exceeded"),
        },
        tags=['Bot']
    )
    @method_decorator(ratelimit(key='header:x-tenant-id', rate='5/m', method='PUT'))
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



class KnowledgeEntryPagination(PageNumberPagination):
    """Pagination for knowledge entry list."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class KnowledgeEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing knowledge base entries.
    
    Provides full CRUD operations for knowledge entries with semantic search,
    bulk import, and tenant isolation.
    
    All endpoints require 'integrations:manage' scope.
    
    Endpoints:
    - GET /v1/bot/knowledge - List all entries
    - POST /v1/bot/knowledge - Create new entry
    - GET /v1/bot/knowledge/{id} - Get specific entry
    - PUT /v1/bot/knowledge/{id} - Update entry
    - PATCH /v1/bot/knowledge/{id} - Partial update entry
    - DELETE /v1/bot/knowledge/{id} - Delete (deactivate) entry
    - GET /v1/bot/knowledge/search?q=query - Semantic search
    - POST /v1/bot/knowledge/bulk-import - Bulk import entries
    
    Required scope: integrations:manage
    """
    
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    pagination_class = KnowledgeEntryPagination
    
    def get_queryset(self):
        """
        Get knowledge entries for authenticated tenant.
        
        Filters by tenant and optionally by entry_type, category, and is_active.
        """
        queryset = KnowledgeEntry.objects.filter(tenant=self.request.tenant)
        
        # Filter by entry_type
        entry_type = self.request.query_params.get('entry_type')
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by is_active (default: show only active)
        is_active = self.request.query_params.get('is_active', 'true')
        if is_active.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() == 'false':
            queryset = queryset.filter(is_active=False)
        # 'all' shows both active and inactive
        
        return queryset.order_by('-priority', '-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return KnowledgeEntryCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return KnowledgeEntryUpdateSerializer
        elif self.action == 'search':
            return KnowledgeEntrySearchSerializer
        elif self.action == 'bulk_import':
            return KnowledgeEntryBulkImportSerializer
        return KnowledgeEntrySerializer
    
    @extend_schema(
        summary="List knowledge entries",
        description="Retrieve all knowledge base entries for the authenticated tenant. "
                    "Supports filtering by entry_type, category, and is_active.",
        parameters=[
            OpenApiParameter(
                name='entry_type',
                type=str,
                description='Filter by entry type (faq, policy, product_info, service_info, procedure, general)',
                required=False
            ),
            OpenApiParameter(
                name='category',
                type=str,
                description='Filter by category',
                required=False
            ),
            OpenApiParameter(
                name='is_active',
                type=str,
                description='Filter by active status (true, false, all). Default: true',
                required=False
            ),
        ],
        responses={
            200: KnowledgeEntrySerializer(many=True),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
        },
        tags=['Bot - Knowledge Base']
    )
    def list(self, request, *args, **kwargs):
        """
        List all knowledge entries for the tenant.
        
        Example:
            curl -X GET https://api.tulia.ai/v1/bot/knowledge?entry_type=faq \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create knowledge entry",
        description="Create a new knowledge base entry. Automatically generates semantic "
                    "embeddings for search functionality.",
        request=KnowledgeEntryCreateSerializer,
        responses={
            201: KnowledgeEntrySerializer,
            400: OpenApiResponse(description="Bad request - Invalid entry data"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            429: OpenApiResponse(description="Too many requests - Rate limit exceeded"),
        },
        tags=['Bot - Knowledge Base']
    )
    @method_decorator(ratelimit(key='header:x-tenant-id', rate='10/m', method='POST'))
    def create(self, request, *args, **kwargs):
        """
        Create a new knowledge entry.
        
        Example:
            curl -X POST https://api.tulia.ai/v1/bot/knowledge \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>" \
                -H "Content-Type: application/json" \
                -d '{
                    "entry_type": "faq",
                    "title": "What are your business hours?",
                    "content": "We are open Monday-Friday 9am-5pm EST.",
                    "category": "general",
                    "keywords_list": ["hours", "schedule", "open"],
                    "priority": 80
                }'
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Use KnowledgeBaseService to create entry with embedding
            kb_service = KnowledgeBaseService()
            
            keywords_list = serializer.validated_data.pop('keywords_list', [])
            
            entry = kb_service.create_entry(
                tenant=request.tenant,
                entry_type=serializer.validated_data['entry_type'],
                title=serializer.validated_data['title'],
                content=serializer.validated_data['content'],
                category=serializer.validated_data.get('category', ''),
                keywords=keywords_list,
                metadata=serializer.validated_data.get('metadata', {}),
                priority=serializer.validated_data.get('priority', 0),
                is_active=serializer.validated_data.get('is_active', True),
            )
            
            logger.info(
                f"Created knowledge entry {entry.id} for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'entry_id': str(entry.id),
                    'entry_type': entry.entry_type,
                    'title': entry.title[:50]
                }
            )
            
            response_serializer = KnowledgeEntrySerializer(entry)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(
                f"Error creating knowledge entry: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to create knowledge entry'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Get knowledge entry",
        description="Retrieve a specific knowledge entry by ID.",
        responses={
            200: KnowledgeEntrySerializer,
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            404: OpenApiResponse(description="Not found - Entry does not exist"),
        },
        tags=['Bot - Knowledge Base']
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific knowledge entry.
        
        Example:
            curl -X GET https://api.tulia.ai/v1/bot/knowledge/{id} \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Update knowledge entry",
        description="Update a knowledge entry. Regenerates embeddings if title or content changed.",
        request=KnowledgeEntryUpdateSerializer,
        responses={
            200: KnowledgeEntrySerializer,
            400: OpenApiResponse(description="Bad request - Invalid entry data"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            404: OpenApiResponse(description="Not found - Entry does not exist"),
        },
        tags=['Bot - Knowledge Base']
    )
    def update(self, request, *args, **kwargs):
        """
        Update a knowledge entry (full update).
        
        Example:
            curl -X PUT https://api.tulia.ai/v1/bot/knowledge/{id} \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>" \
                -H "Content-Type: application/json" \
                -d '{
                    "entry_type": "faq",
                    "title": "Updated question",
                    "content": "Updated answer",
                    "priority": 90
                }'
        """
        return self._update_entry(request, partial=False, *args, **kwargs)
    
    @extend_schema(
        summary="Partial update knowledge entry",
        description="Partially update a knowledge entry. Only provided fields will be updated.",
        request=KnowledgeEntryUpdateSerializer,
        responses={
            200: KnowledgeEntrySerializer,
            400: OpenApiResponse(description="Bad request - Invalid entry data"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            404: OpenApiResponse(description="Not found - Entry does not exist"),
        },
        tags=['Bot - Knowledge Base']
    )
    def partial_update(self, request, *args, **kwargs):
        """
        Partially update a knowledge entry.
        
        Example:
            curl -X PATCH https://api.tulia.ai/v1/bot/knowledge/{id} \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>" \
                -H "Content-Type: application/json" \
                -d '{"priority": 95}'
        """
        return self._update_entry(request, partial=True, *args, **kwargs)
    
    def _update_entry(self, request, partial=False, *args, **kwargs):
        """Internal method to handle both full and partial updates."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Use KnowledgeBaseService to update entry
            kb_service = KnowledgeBaseService()
            
            update_data = serializer.validated_data.copy()
            keywords_list = update_data.pop('keywords_list', None)
            
            entry = kb_service.update_entry(
                entry_id=str(instance.id),
                title=update_data.get('title'),
                content=update_data.get('content'),
                category=update_data.get('category'),
                keywords=keywords_list,
                metadata=update_data.get('metadata'),
                priority=update_data.get('priority'),
                is_active=update_data.get('is_active'),
            )
            
            logger.info(
                f"Updated knowledge entry {entry.id} for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'entry_id': str(entry.id),
                    'version': entry.version
                }
            )
            
            response_serializer = KnowledgeEntrySerializer(entry)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except KnowledgeEntry.DoesNotExist:
            return Response(
                {'error': 'Knowledge entry not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(
                f"Error updating knowledge entry: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to update knowledge entry'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Delete knowledge entry",
        description="Soft delete a knowledge entry (sets is_active=False).",
        responses={
            204: OpenApiResponse(description="No content - Entry deleted successfully"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            404: OpenApiResponse(description="Not found - Entry does not exist"),
        },
        tags=['Bot - Knowledge Base']
    )
    def destroy(self, request, *args, **kwargs):
        """
        Delete (deactivate) a knowledge entry.
        
        Example:
            curl -X DELETE https://api.tulia.ai/v1/bot/knowledge/{id} \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        instance = self.get_object()
        
        try:
            # Use KnowledgeBaseService to soft delete
            kb_service = KnowledgeBaseService()
            kb_service.delete_entry(str(instance.id))
            
            logger.info(
                f"Deleted knowledge entry {instance.id} for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'entry_id': str(instance.id)
                }
            )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(
                f"Error deleting knowledge entry: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to delete knowledge entry'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Search knowledge entries",
        description="Search knowledge base using semantic similarity. Returns entries ranked by relevance.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=str,
                description='Search query',
                required=True
            ),
            OpenApiParameter(
                name='entry_type',
                type=str,
                description='Filter by entry type (comma-separated for multiple)',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                description='Maximum number of results (default: 5, max: 20)',
                required=False
            ),
            OpenApiParameter(
                name='min_similarity',
                type=float,
                description='Minimum similarity score 0.0-1.0 (default: 0.7)',
                required=False
            ),
        ],
        responses={
            200: KnowledgeEntrySearchSerializer(many=True),
            400: OpenApiResponse(description="Bad request - Missing or invalid query parameter"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
            429: OpenApiResponse(description="Too many requests - Rate limit exceeded"),
        },
        tags=['Bot - Knowledge Base']
    )
    @method_decorator(ratelimit(key='header:x-tenant-id', rate='60/m', method='GET'))
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search knowledge base using semantic similarity.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/knowledge/search?q=business%20hours&limit=5" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        query = request.query_params.get('q')
        if not query:
            return Response(
                {'error': 'Query parameter "q" is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse optional parameters
        entry_types_str = request.query_params.get('entry_type')
        entry_types = entry_types_str.split(',') if entry_types_str else None
        
        try:
            limit = int(request.query_params.get('limit', 5))
            limit = min(max(1, limit), 20)  # Clamp between 1 and 20
        except ValueError:
            limit = 5
        
        try:
            min_similarity = float(request.query_params.get('min_similarity', 0.7))
            min_similarity = min(max(0.0, min_similarity), 1.0)  # Clamp between 0 and 1
        except ValueError:
            min_similarity = 0.7
        
        try:
            # Use KnowledgeBaseService for semantic search
            kb_service = KnowledgeBaseService()
            results = kb_service.search(
                tenant=request.tenant,
                query=query,
                entry_types=entry_types,
                limit=limit,
                min_similarity=min_similarity
            )
            
            # Format results
            formatted_results = [
                {
                    'entry': KnowledgeEntrySerializer(entry).data,
                    'similarity_score': score
                }
                for entry, score in results
            ]
            
            logger.info(
                f"Knowledge search for tenant {request.tenant.id}: "
                f"query='{query[:50]}', found={len(results)} results",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'query': query[:100],
                    'results_count': len(results)
                }
            )
            
            return Response(formatted_results, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error searching knowledge base: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to search knowledge base'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Bulk import knowledge entries",
        description="Import multiple knowledge entries at once. Accepts JSON array or CSV data. "
                    "Maximum 100 entries per request.",
        request=KnowledgeEntryBulkImportSerializer,
        responses={
            201: OpenApiResponse(
                description="Created - Returns summary of import results",
                response={
                    'type': 'object',
                    'properties': {
                        'success_count': {'type': 'integer'},
                        'error_count': {'type': 'integer'},
                        'errors': {'type': 'array', 'items': {'type': 'object'}},
                        'created_ids': {'type': 'array', 'items': {'type': 'string'}},
                    }
                }
            ),
            400: OpenApiResponse(description="Bad request - Invalid import data"),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'integrations:manage'"),
        },
        tags=['Bot - Knowledge Base']
    )
    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """
        Bulk import knowledge entries from JSON or CSV.
        
        JSON Example:
            curl -X POST https://api.tulia.ai/v1/bot/knowledge/bulk-import \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>" \
                -H "Content-Type: application/json" \
                -d '{
                    "entries": [
                        {
                            "entry_type": "faq",
                            "title": "Question 1",
                            "content": "Answer 1",
                            "category": "general",
                            "keywords_list": ["keyword1"],
                            "priority": 50
                        },
                        {
                            "entry_type": "policy",
                            "title": "Policy 1",
                            "content": "Policy details",
                            "priority": 80
                        }
                    ]
                }'
        
        CSV Example:
            curl -X POST https://api.tulia.ai/v1/bot/knowledge/bulk-import \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>" \
                -H "Content-Type: text/csv" \
                --data-binary @knowledge_entries.csv
        """
        content_type = request.content_type
        
        # Parse CSV if content type is CSV
        if 'csv' in content_type.lower():
            try:
                entries_data = self._parse_csv(request.body.decode('utf-8'))
            except Exception as e:
                logger.error(f"Error parsing CSV: {str(e)}")
                return Response(
                    {'error': f'Failed to parse CSV: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Assume JSON
            entries_data = request.data.get('entries', [])
        
        # Validate
        serializer = KnowledgeEntryBulkImportSerializer(data={'entries': entries_data})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Import entries
        kb_service = KnowledgeBaseService()
        success_count = 0
        error_count = 0
        errors = []
        created_ids = []
        
        with transaction.atomic():
            for idx, entry_data in enumerate(serializer.validated_data['entries']):
                try:
                    keywords_list = entry_data.get('keywords_list', [])
                    
                    entry = kb_service.create_entry(
                        tenant=request.tenant,
                        entry_type=entry_data['entry_type'],
                        title=entry_data['title'],
                        content=entry_data['content'],
                        category=entry_data.get('category', ''),
                        keywords=keywords_list,
                        metadata=entry_data.get('metadata', {}),
                        priority=entry_data.get('priority', 0),
                        is_active=entry_data.get('is_active', True),
                    )
                    
                    success_count += 1
                    created_ids.append(str(entry.id))
                    
                except Exception as e:
                    error_count += 1
                    errors.append({
                        'index': idx,
                        'title': entry_data.get('title', 'Unknown'),
                        'error': str(e)
                    })
                    logger.error(
                        f"Error importing entry {idx}: {str(e)}",
                        extra={'tenant_id': str(request.tenant.id)}
                    )
        
        logger.info(
            f"Bulk import for tenant {request.tenant.id}: "
            f"success={success_count}, errors={error_count}",
            extra={
                'tenant_id': str(request.tenant.id),
                'success_count': success_count,
                'error_count': error_count
            }
        )
        
        return Response(
            {
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors,
                'created_ids': created_ids,
            },
            status=status.HTTP_201_CREATED
        )
    
    def _parse_csv(self, csv_content: str) -> list:
        """
        Parse CSV content into list of entry dictionaries.
        
        Expected CSV columns:
        - entry_type (required)
        - title (required)
        - content (required)
        - category (optional)
        - keywords (optional, comma-separated)
        - priority (optional, integer)
        - is_active (optional, true/false)
        """
        entries = []
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            # Parse keywords
            keywords_str = row.get('keywords', '')
            keywords_list = [k.strip() for k in keywords_str.split(',') if k.strip()]
            
            # Parse priority
            priority = 0
            if 'priority' in row and row['priority']:
                try:
                    priority = int(row['priority'])
                except ValueError:
                    priority = 0
            
            # Parse is_active
            is_active = True
            if 'is_active' in row and row['is_active']:
                is_active = row['is_active'].lower() in ['true', '1', 'yes']
            
            entry = {
                'entry_type': row.get('entry_type', '').strip(),
                'title': row.get('title', '').strip(),
                'content': row.get('content', '').strip(),
                'category': row.get('category', '').strip(),
                'keywords_list': keywords_list,
                'priority': priority,
                'is_active': is_active,
                'metadata': {}
            }
            
            entries.append(entry)
        
        return entries



class AgentAnalyticsView(APIView):
    """
    Agent analytics and statistics for monitoring AI agent performance.
    
    Provides insights into:
    - Conversation statistics (total interactions, average confidence, etc.)
    - Handoff analytics (handoff rate, reasons, trends)
    - Cost tracking (token usage, estimated costs by model)
    - Common topics and intents
    
    All endpoints require 'analytics:view' scope.
    
    Endpoints:
    - GET /v1/bot/analytics/conversations - Conversation statistics
    - GET /v1/bot/analytics/handoffs - Handoff analytics
    - GET /v1/bot/analytics/costs - Cost tracking
    - GET /v1/bot/analytics/topics - Common topics and intents
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get conversation statistics",
        description="Retrieve statistics about AI agent conversations including total interactions, "
                    "average confidence scores, response times, and message type distribution.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=str,
                description='Start date for analytics (YYYY-MM-DD). Default: 30 days ago',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                description='End date for analytics (YYYY-MM-DD). Default: today',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Conversation statistics",
                response={
                    'type': 'object',
                    'properties': {
                        'total_interactions': {'type': 'integer'},
                        'total_conversations': {'type': 'integer'},
                        'average_confidence': {'type': 'number'},
                        'average_processing_time_ms': {'type': 'number'},
                        'high_confidence_rate': {'type': 'number'},
                        'low_confidence_rate': {'type': 'number'},
                        'message_type_distribution': {
                            'type': 'object',
                            'properties': {
                                'text': {'type': 'integer'},
                                'button': {'type': 'integer'},
                                'list': {'type': 'integer'},
                                'media': {'type': 'integer'},
                            }
                        },
                        'model_usage': {
                            'type': 'object',
                            'additionalProperties': {'type': 'integer'}
                        },
                    }
                }
            ),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
        },
        tags=['Bot - Analytics']
    )
    def get(self, request):
        """
        Get conversation statistics for the authenticated tenant.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/analytics/conversations?start_date=2024-01-01" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        from datetime import datetime, timedelta
        from django.db.models import Avg, Count, Q
        from apps.bot.models import AgentInteraction
        
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
        
        try:
            # Get interactions for tenant in date range
            interactions = AgentInteraction.objects.filter(
                conversation__tenant=request.tenant,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Calculate statistics
            total_interactions = interactions.count()
            
            if total_interactions == 0:
                return Response({
                    'total_interactions': 0,
                    'total_conversations': 0,
                    'average_confidence': 0.0,
                    'average_processing_time_ms': 0.0,
                    'high_confidence_rate': 0.0,
                    'low_confidence_rate': 0.0,
                    'message_type_distribution': {
                        'text': 0,
                        'button': 0,
                        'list': 0,
                        'media': 0,
                    },
                    'model_usage': {},
                }, status=status.HTTP_200_OK)
            
            # Aggregate statistics
            stats = interactions.aggregate(
                avg_confidence=Avg('confidence_score'),
                avg_processing_time=Avg('processing_time_ms'),
                unique_conversations=Count('conversation', distinct=True),
                high_confidence_count=Count('id', filter=Q(confidence_score__gte=0.7)),
                low_confidence_count=Count('id', filter=Q(confidence_score__lt=0.7)),
            )
            
            # Message type distribution
            message_type_dist = interactions.values('message_type').annotate(
                count=Count('id')
            )
            message_type_distribution = {
                'text': 0,
                'button': 0,
                'list': 0,
                'media': 0,
            }
            for item in message_type_dist:
                message_type_distribution[item['message_type']] = item['count']
            
            # Model usage
            model_usage_data = interactions.values('model_used').annotate(
                count=Count('id')
            )
            model_usage = {item['model_used']: item['count'] for item in model_usage_data}
            
            # Calculate rates
            high_confidence_rate = stats['high_confidence_count'] / total_interactions if total_interactions > 0 else 0.0
            low_confidence_rate = stats['low_confidence_count'] / total_interactions if total_interactions > 0 else 0.0
            
            result = {
                'total_interactions': total_interactions,
                'total_conversations': stats['unique_conversations'],
                'average_confidence': round(stats['avg_confidence'] or 0.0, 3),
                'average_processing_time_ms': round(stats['avg_processing_time'] or 0.0, 2),
                'high_confidence_rate': round(high_confidence_rate, 3),
                'low_confidence_rate': round(low_confidence_rate, 3),
                'message_type_distribution': message_type_distribution,
                'model_usage': model_usage,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
            }
            
            logger.info(
                f"Retrieved conversation statistics for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'total_interactions': total_interactions,
                    'date_range': f"{start_date} to {end_date}"
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error retrieving conversation statistics: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve conversation statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgentHandoffAnalyticsView(APIView):
    """
    Handoff analytics for monitoring when and why the AI agent escalates to humans.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get handoff analytics",
        description="Retrieve analytics about handoffs to human agents including handoff rate, "
                    "reasons, and trends over time.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=str,
                description='Start date for analytics (YYYY-MM-DD). Default: 30 days ago',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                description='End date for analytics (YYYY-MM-DD). Default: today',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Handoff analytics",
                response={
                    'type': 'object',
                    'properties': {
                        'total_handoffs': {'type': 'integer'},
                        'handoff_rate': {'type': 'number'},
                        'handoff_reasons': {
                            'type': 'object',
                            'additionalProperties': {'type': 'integer'}
                        },
                        'average_attempts_before_handoff': {'type': 'number'},
                    }
                }
            ),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
        },
        tags=['Bot - Analytics']
    )
    def get(self, request):
        """
        Get handoff analytics for the authenticated tenant.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/analytics/handoffs" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        from datetime import datetime, timedelta
        from django.db.models import Count, Avg
        from apps.bot.models import AgentInteraction
        
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
                start_date = datetime.strptime(start_date, '%Y-%m-% d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid start_date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            start_date = end_date - timedelta(days=30)
        
        try:
            # Get interactions for tenant in date range
            interactions = AgentInteraction.objects.filter(
                conversation__tenant=request.tenant,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_interactions = interactions.count()
            
            if total_interactions == 0:
                return Response({
                    'total_handoffs': 0,
                    'handoff_rate': 0.0,
                    'handoff_reasons': {},
                    'average_attempts_before_handoff': 0.0,
                    'date_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                    }
                }, status=status.HTTP_200_OK)
            
            # Get handoff interactions
            handoffs = interactions.filter(handoff_triggered=True)
            total_handoffs = handoffs.count()
            
            # Calculate handoff rate
            handoff_rate = total_handoffs / total_interactions if total_interactions > 0 else 0.0
            
            # Get handoff reasons
            handoff_reasons_data = handoffs.exclude(
                handoff_reason=''
            ).values('handoff_reason').annotate(
                count=Count('id')
            ).order_by('-count')
            
            handoff_reasons = {
                item['handoff_reason']: item['count']
                for item in handoff_reasons_data
            }
            
            # Calculate average attempts before handoff
            # (count interactions per conversation before handoff)
            conversations_with_handoff = handoffs.values_list('conversation_id', flat=True).distinct()
            
            attempts_before_handoff = []
            for conv_id in conversations_with_handoff:
                conv_interactions = interactions.filter(
                    conversation_id=conv_id
                ).order_by('created_at')
                
                # Find first handoff
                first_handoff_idx = None
                for idx, interaction in enumerate(conv_interactions):
                    if interaction.handoff_triggered:
                        first_handoff_idx = idx
                        break
                
                if first_handoff_idx is not None:
                    attempts_before_handoff.append(first_handoff_idx + 1)
            
            avg_attempts = sum(attempts_before_handoff) / len(attempts_before_handoff) if attempts_before_handoff else 0.0
            
            result = {
                'total_handoffs': total_handoffs,
                'handoff_rate': round(handoff_rate, 3),
                'handoff_reasons': handoff_reasons,
                'average_attempts_before_handoff': round(avg_attempts, 2),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
            }
            
            logger.info(
                f"Retrieved handoff analytics for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'total_handoffs': total_handoffs,
                    'handoff_rate': handoff_rate
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error retrieving handoff analytics: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve handoff analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgentCostAnalyticsView(APIView):
    """
    Cost tracking analytics for monitoring AI agent token usage and costs.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get cost tracking analytics",
        description="Retrieve cost analytics including total token usage, estimated costs by model, "
                    "and cost trends over time.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=str,
                description='Start date for analytics (YYYY-MM-DD). Default: 30 days ago',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                description='End date for analytics (YYYY-MM-DD). Default: today',
                required=False
            ),
            OpenApiParameter(
                name='group_by',
                type=str,
                description='Group results by: day, week, month, model. Default: model',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Cost analytics",
                response={
                    'type': 'object',
                    'properties': {
                        'total_tokens': {'type': 'integer'},
                        'total_cost': {'type': 'string'},
                        'average_cost_per_interaction': {'type': 'string'},
                        'cost_by_model': {
                            'type': 'object',
                            'additionalProperties': {
                                'type': 'object',
                                'properties': {
                                    'total_tokens': {'type': 'integer'},
                                    'total_cost': {'type': 'string'},
                                    'interaction_count': {'type': 'integer'},
                                }
                            }
                        },
                    }
                }
            ),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
        },
        tags=['Bot - Analytics']
    )
    def get(self, request):
        """
        Get cost tracking analytics for the authenticated tenant.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/analytics/costs?group_by=model" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        from datetime import datetime, timedelta
        from django.db.models import Sum, Avg, Count
        from apps.bot.models import AgentInteraction
        
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
        
        group_by = request.query_params.get('group_by', 'model')
        
        try:
            # Get interactions for tenant in date range
            interactions = AgentInteraction.objects.filter(
                conversation__tenant=request.tenant,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_interactions = interactions.count()
            
            if total_interactions == 0:
                return Response({
                    'total_tokens': 0,
                    'total_cost': '0.000000',
                    'average_cost_per_interaction': '0.000000',
                    'cost_by_model': {},
                    'date_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                    }
                }, status=status.HTTP_200_OK)
            
            # Calculate total tokens and cost
            totals = interactions.aggregate(
                total_cost=Sum('estimated_cost'),
                avg_cost=Avg('estimated_cost')
            )
            
            # Calculate total tokens from token_usage JSON field
            total_tokens = 0
            for interaction in interactions:
                total_tokens += interaction.get_total_tokens()
            
            # Cost by model
            cost_by_model_data = interactions.values('model_used').annotate(
                total_cost=Sum('estimated_cost'),
                interaction_count=Count('id')
            )
            
            cost_by_model = {}
            for item in cost_by_model_data:
                model = item['model_used']
                
                # Calculate tokens for this model
                model_interactions = interactions.filter(model_used=model)
                model_tokens = sum(i.get_total_tokens() for i in model_interactions)
                
                cost_by_model[model] = {
                    'total_tokens': model_tokens,
                    'total_cost': str(item['total_cost']),
                    'interaction_count': item['interaction_count'],
                    'average_cost_per_interaction': str(item['total_cost'] / item['interaction_count']) if item['interaction_count'] > 0 else '0.000000'
                }
            
            result = {
                'total_tokens': total_tokens,
                'total_cost': str(totals['total_cost'] or 0),
                'average_cost_per_interaction': str(totals['avg_cost'] or 0),
                'cost_by_model': cost_by_model,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
            }
            
            logger.info(
                f"Retrieved cost analytics for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'total_cost': str(totals['total_cost']),
                    'total_tokens': total_tokens
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error retrieving cost analytics: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve cost analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgentTopicsAnalyticsView(APIView):
    """
    Topic and intent analytics for understanding common customer inquiries.
    
    Required scope: analytics:view
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'analytics:view'}
    
    @extend_schema(
        summary="Get common topics and intents",
        description="Retrieve analytics about common topics and intents detected in customer messages.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=str,
                description='Start date for analytics (YYYY-MM-DD). Default: 30 days ago',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                description='End date for analytics (YYYY-MM-DD). Default: today',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                description='Maximum number of topics to return. Default: 10',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Topic analytics",
                response={
                    'type': 'object',
                    'properties': {
                        'common_intents': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'intent': {'type': 'string'},
                                    'count': {'type': 'integer'},
                                    'percentage': {'type': 'number'},
                                }
                            }
                        },
                        'total_unique_intents': {'type': 'integer'},
                    }
                }
            ),
            403: OpenApiResponse(description="Forbidden - Missing required scope 'analytics:view'"),
        },
        tags=['Bot - Analytics']
    )
    def get(self, request):
        """
        Get common topics and intents for the authenticated tenant.
        
        Example:
            curl -X GET "https://api.tulia.ai/v1/bot/analytics/topics?limit=10" \
                -H "X-TENANT-ID: <tenant-id>" \
                -H "X-TENANT-API-KEY: <api-key>"
        """
        from datetime import datetime, timedelta
        from collections import Counter
        from apps.bot.models import AgentInteraction
        
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
        
        try:
            limit = int(request.query_params.get('limit', 10))
            limit = min(max(1, limit), 50)  # Clamp between 1 and 50
        except ValueError:
            limit = 10
        
        try:
            # Get interactions for tenant in date range
            interactions = AgentInteraction.objects.filter(
                conversation__tenant=request.tenant,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            total_interactions = interactions.count()
            
            if total_interactions == 0:
                return Response({
                    'common_intents': [],
                    'total_unique_intents': 0,
                    'date_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                    }
                }, status=status.HTTP_200_OK)
            
            # Extract all intents from detected_intents JSON field
            intent_counter = Counter()
            
            for interaction in interactions:
                intent_names = interaction.get_intent_names()
                for intent_name in intent_names:
                    if intent_name:  # Skip empty strings
                        intent_counter[intent_name] += 1
            
            # Get top intents
            common_intents = []
            for intent, count in intent_counter.most_common(limit):
                percentage = (count / total_interactions) * 100
                common_intents.append({
                    'intent': intent,
                    'count': count,
                    'percentage': round(percentage, 2)
                })
            
            result = {
                'common_intents': common_intents,
                'total_unique_intents': len(intent_counter),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
            }
            
            logger.info(
                f"Retrieved topic analytics for tenant {request.tenant.id}",
                extra={
                    'tenant_id': str(request.tenant.id),
                    'total_unique_intents': len(intent_counter),
                    'top_intent': common_intents[0]['intent'] if common_intents else None
                }
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error retrieving topic analytics: {str(e)}",
                extra={'tenant_id': str(request.tenant.id)},
                exc_info=True
            )
            return Response(
                {'error': 'Failed to retrieve topic analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
