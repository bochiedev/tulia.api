"""
Catalog API views for products and variants.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import logging

from apps.catalog.models import Product, ProductVariant
from apps.catalog.services import CatalogService
from apps.catalog.serializers import (
    ProductListSerializer, ProductDetailSerializer,
    ProductCreateSerializer, ProductUpdateSerializer,
    ProductSearchSerializer, ProductVariantSerializer,
    ProductVariantCreateSerializer
)
from apps.core.exceptions import FeatureLimitExceeded, SubscriptionInactive
from apps.core.permissions import HasTenantScopes, requires_scopes
from apps.rbac.models import AuditLog

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list endpoints."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductListView(APIView):
    """
    List and create products.
    
    GET /v1/products - List products with search and filtering
    POST /v1/products - Create a new product
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'catalog:view'}
        elif request.method == 'POST':
            self.required_scopes = {'catalog:edit'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="List products",
        description="Retrieve paginated list of products with optional search and filtering",
        parameters=[
            OpenApiParameter(
                name='query',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query for title and description'
            ),
            OpenApiParameter(
                name='is_active',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by active status (default: true)'
            ),
            OpenApiParameter(
                name='min_price',
                type=OpenApiTypes.DECIMAL,
                location=OpenApiParameter.QUERY,
                description='Minimum price filter'
            ),
            OpenApiParameter(
                name='max_price',
                type=OpenApiTypes.DECIMAL,
                location=OpenApiParameter.QUERY,
                description='Maximum price filter'
            ),
            OpenApiParameter(
                name='external_source',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by external source',
                enum=['woocommerce', 'shopify', 'manual']
            ),
            OpenApiParameter(
                name='in_stock',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by stock availability'
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number'
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of items per page (max 100)'
            ),
        ],
        responses={
            200: ProductListSerializer(many=True),
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            }
        },
        tags=['Products']
    )
    def get(self, request):
        """List products with search and filtering."""
        tenant = request.tenant  # Injected by middleware
        
        # Validate query parameters
        search_serializer = ProductSearchSerializer(data=request.query_params)
        if not search_serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid query parameters',
                    'details': search_serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        params = search_serializer.validated_data
        
        try:
            # Build filters dict
            filters = {}
            if 'is_active' in params:
                filters['is_active'] = params['is_active']
            if 'min_price' in params:
                filters['min_price'] = params['min_price']
            if 'max_price' in params:
                filters['max_price'] = params['max_price']
            if 'external_source' in params:
                filters['external_source'] = params['external_source']
            if 'in_stock' in params:
                filters['in_stock'] = params['in_stock']
            
            # Search products
            products = CatalogService.search_products(
                tenant=tenant,
                query=params.get('query'),
                filters=filters,
                limit=1000  # Will be paginated
            )
            
            # Paginate results
            paginator = StandardResultsSetPagination()
            paginator.page_size = params.get('page_size', 50)
            paginated_products = paginator.paginate_queryset(products, request)
            
            # Serialize
            serializer = ProductListSerializer(paginated_products, many=True)
            
            return paginator.get_paginated_response(serializer.data)
        
        except Exception as e:
            logger.error(f"Error listing products: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve products',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Create product",
        description="Create a new product. Feature limit enforcement applies based on subscription tier.",
        request=ProductCreateSerializer,
        responses={
            201: ProductDetailSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            }
        },
        tags=['Products']
    )
    def post(self, request):
        """Create a new product."""
        tenant = request.tenant  # Injected by middleware
        user = getattr(request, 'user', None)
        
        # Validate request data
        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        variants_data = data.pop('variants', [])
        
        try:
            # Create product with feature limit check
            product = CatalogService.create_product(
                tenant=tenant,
                product_data=data,
                check_limits=True
            )
            
            # Create variants if provided
            for variant_data in variants_data:
                CatalogService.create_variant(
                    tenant=tenant,
                    product_id=product.id,
                    variant_data=variant_data
                )
            
            # Reload product with variants
            product = CatalogService.get_product(
                tenant=tenant,
                product_id=product.id,
                include_variants=True
            )
            
            # Serialize response
            response_serializer = ProductDetailSerializer(product)
            
            # Create audit log entry
            AuditLog.log_action(
                action='product_created',
                user=user,
                tenant=tenant,
                target_type='Product',
                target_id=product.id,
                metadata={
                    'title': product.title,
                    'price': str(product.price),
                    'currency': product.currency,
                    'external_source': product.external_source,
                },
                request=request
            )
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except FeatureLimitExceeded as e:
            return Response(
                {
                    'error': e.message,
                    'details': e.details
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        except SubscriptionInactive as e:
            return Response(
                {
                    'error': e.message,
                    'details': e.details
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to create product',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductDetailView(APIView):
    """
    Retrieve, update, or delete a product.
    
    GET /v1/products/{id} - Get product details with variants
    PUT /v1/products/{id} - Update product
    DELETE /v1/products/{id} - Delete product (soft delete)
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'catalog:view'}
        elif request.method in ['PUT', 'PATCH', 'DELETE']:
            self.required_scopes = {'catalog:edit'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="Get product details",
        description="Retrieve detailed product information including all variants",
        responses={
            200: ProductDetailSerializer,
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def get(self, request, product_id):
        """Get product details."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            product = CatalogService.get_product(
                tenant=tenant,
                product_id=product_id,
                include_variants=True
            )
            
            if not product:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ProductDetailSerializer(product)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting product: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve product',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Update product",
        description="Update product information. Cannot update tenant or external source fields.",
        request=ProductUpdateSerializer,
        responses={
            200: ProductDetailSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def put(self, request, product_id):
        """Update product."""
        tenant = request.tenant  # Injected by middleware
        user = getattr(request, 'user', None)
        
        # Validate request data
        serializer = ProductUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            # Get original product for diff
            original_product = CatalogService.get_product(
                tenant=tenant,
                product_id=product_id,
                include_variants=False
            )
            
            if not original_product:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Capture original values for diff
            original_values = {
                'title': original_product.title,
                'price': str(original_product.price),
                'is_active': original_product.is_active,
            }
            
            # Update product
            product = CatalogService.update_product(
                tenant=tenant,
                product_id=product_id,
                product_data=data
            )
            
            # Reload with variants
            product = CatalogService.get_product(
                tenant=tenant,
                product_id=product.id,
                include_variants=True
            )
            
            # Build diff of changed fields
            diff = {
                'before': original_values,
                'after': {
                    'title': product.title,
                    'price': str(product.price),
                    'is_active': product.is_active,
                }
            }
            
            # Create audit log entry
            AuditLog.log_action(
                action='product_updated',
                user=user,
                tenant=tenant,
                target_type='Product',
                target_id=product.id,
                diff=diff,
                metadata={
                    'updated_fields': list(data.keys()),
                },
                request=request
            )
            
            response_serializer = ProductDetailSerializer(product)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to update product',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Delete product",
        description="Soft delete a product. The product will be marked as deleted but not removed from database.",
        responses={
            204: None,
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def delete(self, request, product_id):
        """Delete product (soft delete)."""
        tenant = request.tenant  # Injected by middleware
        user = getattr(request, 'user', None)
        
        try:
            # Get product details before deletion for audit log
            product = CatalogService.get_product(
                tenant=tenant,
                product_id=product_id,
                include_variants=False
            )
            
            if not product:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Capture product info for audit log
            product_info = {
                'title': product.title,
                'price': str(product.price),
                'currency': product.currency,
                'external_source': product.external_source,
            }
            
            # Delete product
            deleted = CatalogService.delete_product(
                tenant=tenant,
                product_id=product_id,
                soft_delete=True
            )
            
            if not deleted:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create audit log entry
            AuditLog.log_action(
                action='product_deleted',
                user=user,
                tenant=tenant,
                target_type='Product',
                target_id=product_id,
                metadata=product_info,
                request=request
            )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to delete product',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductVariantListView(APIView):
    """
    List and create variants for a product.
    
    GET /v1/products/{product_id}/variants - List variants
    POST /v1/products/{product_id}/variants - Create variant
    
    Required scopes:
    - GET: catalog:view
    - POST: catalog:edit
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'catalog:view'}
        elif request.method == 'POST':
            self.required_scopes = {'catalog:edit'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="List product variants",
        description="Retrieve all variants for a specific product",
        responses={
            200: ProductVariantSerializer(many=True),
            403: {'description': 'Forbidden - Missing required scope: catalog:view'},
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def get(self, request, product_id):
        """List product variants."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            product = CatalogService.get_product(
                tenant=tenant,
                product_id=product_id,
                include_variants=True
            )
            
            if not product:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ProductVariantSerializer(product.variants.all(), many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error listing variants: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve variants',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Create product variant",
        description="Create a new variant for a product",
        request=ProductVariantCreateSerializer,
        responses={
            201: ProductVariantSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {'description': 'Forbidden - Missing required scope: catalog:edit'},
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def post(self, request, product_id):
        """Create product variant."""
        tenant = request.tenant  # Injected by middleware
        
        # Validate request data
        serializer = ProductVariantCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            variant = CatalogService.create_variant(
                tenant=tenant,
                product_id=product_id,
                variant_data=data
            )
            
            if not variant:
                return Response(
                    {'error': 'Product not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            response_serializer = ProductVariantSerializer(variant)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(f"Error creating variant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to create variant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductVariantDetailView(APIView):
    """
    Retrieve, update, or delete a product variant.
    
    GET /v1/products/{product_id}/variants/{variant_id} - Get variant details
    PUT /v1/products/{product_id}/variants/{variant_id} - Update variant
    DELETE /v1/products/{product_id}/variants/{variant_id} - Delete variant
    
    Required scopes:
    - GET: catalog:view
    - PUT/DELETE: catalog:edit
    """
    permission_classes = [HasTenantScopes]
    
    def check_permissions(self, request):
        """Set required scopes based on HTTP method before permission check."""
        if request.method == 'GET':
            self.required_scopes = {'catalog:view'}
        elif request.method in ['PUT', 'DELETE']:
            self.required_scopes = {'catalog:edit'}
        super().check_permissions(request)
    
    @extend_schema(
        summary="Get variant details",
        description="Retrieve detailed variant information",
        responses={
            200: ProductVariantSerializer,
            403: {'description': 'Forbidden - Missing required scope: catalog:view'},
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def get(self, request, product_id, variant_id):
        """Get variant details."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            variant = CatalogService.get_variant(tenant=tenant, variant_id=variant_id)
            
            if not variant or str(variant.product.id) != product_id:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ProductVariantSerializer(variant)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error getting variant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to retrieve variant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Update variant",
        description="Update variant information",
        request=ProductVariantCreateSerializer,
        responses={
            200: ProductVariantSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {'description': 'Forbidden - Missing required scope: catalog:edit'},
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def put(self, request, product_id, variant_id):
        """Update variant."""
        tenant = request.tenant  # Injected by middleware
        
        # Validate request data
        serializer = ProductVariantCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            variant = CatalogService.update_variant(
                tenant=tenant,
                variant_id=variant_id,
                variant_data=data
            )
            
            if not variant or str(variant.product.id) != product_id:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            response_serializer = ProductVariantSerializer(variant)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error updating variant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to update variant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Delete variant",
        description="Soft delete a variant",
        responses={
            204: None,
            403: {'description': 'Forbidden - Missing required scope: catalog:edit'},
            404: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Products']
    )
    def delete(self, request, product_id, variant_id):
        """Delete variant (soft delete)."""
        tenant = request.tenant  # Injected by middleware
        
        try:
            # Verify variant belongs to product
            variant = CatalogService.get_variant(tenant=tenant, variant_id=variant_id)
            if not variant or str(variant.product.id) != product_id:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            deleted = CatalogService.delete_variant(
                tenant=tenant,
                variant_id=variant_id,
                soft_delete=True
            )
            
            if not deleted:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except Exception as e:
            logger.error(f"Error deleting variant: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to delete variant',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class WooCommerceSyncView(APIView):
    """
    Trigger WooCommerce product synchronization.
    
    POST /v1/catalog/sync/woocommerce - Sync products from WooCommerce
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    
    @extend_schema(
        summary="Sync WooCommerce products",
        description="""
        Trigger product synchronization from WooCommerce store.
        
        Requires WooCommerce credentials to be configured in tenant metadata:
        - store_url: WooCommerce store URL
        - consumer_key: REST API consumer key
        - consumer_secret: REST API consumer secret
        
        The sync runs asynchronously via Celery task. Returns task ID for tracking.
        
        Example curl:
        ```bash
        curl -X POST https://api.tulia.ai/v1/catalog/sync/woocommerce \\
          -H "X-TENANT-ID: tenant-uuid" \\
          -H "X-TENANT-API-KEY: your-api-key"
        ```
        """,
        request=None,
        responses={
            202: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'accepted'},
                    'message': {'type': 'string'},
                    'task_id': {'type': 'string'},
                    'store_url': {'type': 'string'}
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Catalog Sync']
    )
    def post(self, request):
        """Trigger WooCommerce product sync."""
        tenant = request.tenant  # Injected by middleware
        user = getattr(request, 'user', None)
        
        try:
            # Check if WooCommerce credentials are configured
            woo_config = tenant.metadata.get('woocommerce', {})
            
            if not all([
                woo_config.get('store_url'),
                woo_config.get('consumer_key'),
                woo_config.get('consumer_secret')
            ]):
                return Response(
                    {
                        'error': 'WooCommerce credentials not configured',
                        'details': {
                            'message': 'Please configure WooCommerce store_url, consumer_key, and consumer_secret in tenant metadata'
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import here to avoid circular dependency
            from apps.integrations.tasks import sync_woocommerce_products
            
            # Schedule sync task
            task = sync_woocommerce_products.delay(str(tenant.id))
            
            logger.info(
                f"WooCommerce sync triggered",
                extra={
                    'tenant_id': str(tenant.id),
                    'task_id': task.id,
                    'store_url': woo_config['store_url']
                }
            )
            
            # Create audit log entry
            AuditLog.log_action(
                action='woocommerce_sync_triggered',
                user=user,
                tenant=tenant,
                target_type='Integration',
                target_id=None,
                metadata={
                    'task_id': task.id,
                    'store_url': woo_config['store_url']
                },
                request=request
            )
            
            return Response(
                {
                    'status': 'accepted',
                    'message': 'WooCommerce product sync has been scheduled',
                    'task_id': task.id,
                    'store_url': woo_config['store_url']
                },
                status=status.HTTP_202_ACCEPTED
            )
        
        except Exception as e:
            logger.error(
                f"Error triggering WooCommerce sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'error': str(e)
                },
                exc_info=True
            )
            return Response(
                {
                    'error': 'Failed to trigger WooCommerce sync',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ShopifySyncView(APIView):
    """
    Trigger Shopify product synchronization.
    
    POST /v1/catalog/sync/shopify - Sync products from Shopify
    """
    permission_classes = [HasTenantScopes]
    required_scopes = {'integrations:manage'}
    
    @extend_schema(
        summary="Sync Shopify products",
        description="""
        Trigger product synchronization from Shopify store.
        
        Requires Shopify credentials to be configured in tenant metadata:
        - shop_domain: Shopify store domain (e.g., mystore.myshopify.com)
        - access_token: Admin API access token
        
        The sync runs asynchronously via Celery task. Returns task ID for tracking.
        
        Example curl:
        ```bash
        curl -X POST https://api.tulia.ai/v1/catalog/sync/shopify \\
          -H "X-TENANT-ID: tenant-uuid" \\
          -H "X-TENANT-API-KEY: your-api-key"
        ```
        """,
        request=None,
        responses={
            202: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'accepted'},
                    'message': {'type': 'string'},
                    'task_id': {'type': 'string'},
                    'shop_domain': {'type': 'string'}
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        tags=['Catalog Sync']
    )
    def post(self, request):
        """Trigger Shopify product sync."""
        tenant = request.tenant  # Injected by middleware
        user = getattr(request, 'user', None)
        
        try:
            # Check if Shopify credentials are configured
            shopify_config = tenant.metadata.get('shopify', {})
            
            if not all([
                shopify_config.get('shop_domain'),
                shopify_config.get('access_token')
            ]):
                return Response(
                    {
                        'error': 'Shopify credentials not configured',
                        'details': {
                            'message': 'Please configure Shopify shop_domain and access_token in tenant metadata'
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import here to avoid circular dependency
            from apps.integrations.tasks import sync_shopify_products
            
            # Schedule sync task
            task = sync_shopify_products.delay(str(tenant.id))
            
            logger.info(
                f"Shopify sync triggered",
                extra={
                    'tenant_id': str(tenant.id),
                    'task_id': task.id,
                    'shop_domain': shopify_config['shop_domain']
                }
            )
            
            # Create audit log entry
            AuditLog.log_action(
                action='shopify_sync_triggered',
                user=user,
                tenant=tenant,
                target_type='Integration',
                target_id=None,
                metadata={
                    'task_id': task.id,
                    'shop_domain': shopify_config['shop_domain']
                },
                request=request
            )
            
            return Response(
                {
                    'status': 'accepted',
                    'message': 'Shopify product sync has been scheduled',
                    'task_id': task.id,
                    'shop_domain': shopify_config['shop_domain']
                },
                status=status.HTTP_202_ACCEPTED
            )
        
        except Exception as e:
            logger.error(
                f"Error triggering Shopify sync",
                extra={
                    'tenant_id': str(tenant.id),
                    'error': str(e)
                },
                exc_info=True
            )
            return Response(
                {
                    'error': 'Failed to trigger Shopify sync',
                    'details': {'message': str(e)}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
