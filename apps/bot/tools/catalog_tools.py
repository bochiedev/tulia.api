"""
Catalog and product search tools for LangGraph orchestration.
"""

from typing import Any, Dict, Optional, List
from apps.bot.tools.base import BaseTool, ToolResponse, validate_required_params, validate_uuid


class CatalogSearchTool(BaseTool):
    """
    Search products in tenant catalog with semantic search and filters.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - query: Search query string
    
    Optional parameters:
    - category: Product category filter
    - min_price: Minimum price filter
    - max_price: Maximum price filter
    - in_stock: Filter by stock availability
    - limit: Maximum number of results (default: 6, max: 50)
    """
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tenant_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the tenant"
                },
                "request_id": {
                    "type": "string", 
                    "format": "uuid",
                    "description": "UUID for request tracing"
                },
                "conversation_id": {
                    "type": "string",
                    "format": "uuid", 
                    "description": "UUID for conversation context"
                },
                "query": {
                    "type": "string",
                    "description": "Search query for products"
                },
                "category": {
                    "type": "string",
                    "description": "Product category filter (optional)"
                },
                "min_price": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Minimum price filter (optional)"
                },
                "max_price": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Maximum price filter (optional)"
                },
                "in_stock": {
                    "type": "boolean",
                    "description": "Filter by stock availability (optional)"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 6,
                    "description": "Maximum number of results"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "query"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Search products in tenant catalog.
        
        Returns:
            ToolResponse with search results including:
            - products: List of matching products
            - total_matches_estimate: Estimated total matches
            - query_used: The search query that was used
            - filters_applied: Filters that were applied
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "query"])
        if error:
            return ToolResponse(success=False, error=error, error_code="MISSING_PARAMS")
        
        # Validate UUIDs
        for field in ["tenant_id", "request_id", "conversation_id"]:
            error = validate_uuid(kwargs[field], field)
            if error:
                return ToolResponse(success=False, error=error, error_code="INVALID_UUID")
        
        tenant_id = kwargs["tenant_id"]
        request_id = kwargs["request_id"]
        conversation_id = kwargs["conversation_id"]
        query = kwargs["query"]
        category = kwargs.get("category")
        min_price = kwargs.get("min_price")
        max_price = kwargs.get("max_price")
        in_stock = kwargs.get("in_stock")
        limit = kwargs.get("limit", 6)
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.catalog.models import Product
            from django.db.models import Q
            
            # Build base query with tenant scoping
            queryset = Product.objects.filter(
                tenant_id=tenant_id,
                is_active=True
            ).select_related('category').prefetch_related('variants')
            
            # Apply text search (simple implementation - can be enhanced with full-text search)
            if query:
                search_q = Q(name__icontains=query) | Q(description__icontains=query)
                queryset = queryset.filter(search_q)
            
            # Apply filters
            filters_applied = {}
            
            if category:
                queryset = queryset.filter(category__icontains=category)
                filters_applied["category"] = category
            
            if min_price is not None:
                queryset = queryset.filter(price__gte=min_price)
                filters_applied["min_price"] = min_price
            
            if max_price is not None:
                queryset = queryset.filter(price__lte=max_price)
                filters_applied["max_price"] = max_price
            
            if in_stock is not None:
                if in_stock:
                    queryset = queryset.filter(stock_quantity__gt=0)
                else:
                    queryset = queryset.filter(stock_quantity=0)
                filters_applied["in_stock"] = in_stock
            
            # Get total count estimate
            total_matches_estimate = queryset.count()
            
            # Apply limit and get results
            products = queryset[:limit]
            
            # Build product data
            product_list = []
            for product in products:
                product_data = {
                    "product_id": str(product.id),
                    "name": product.name,
                    "description": product.description,
                    "price": float(product.price) if product.price else None,
                    "currency": getattr(product, 'currency', 'KES'),
                    "category": product.category,
                    "stock_quantity": product.stock_quantity,
                    "in_stock": product.stock_quantity > 0,
                    "image_url": getattr(product, 'image_url', None),
                    "sku": getattr(product, 'sku', None),
                }
                product_list.append(product_data)
            
            # Build response data
            data = {
                "products": product_list,
                "total_matches_estimate": total_matches_estimate,
                "query_used": query,
                "filters_applied": filters_applied,
                "results_count": len(product_list),
                "limit_applied": limit
            }
            
            self.log_tool_execution(
                "catalog_search", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Exception as e:
            error_msg = f"Failed to search catalog: {str(e)}"
            self.log_tool_execution(
                "catalog_search", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="SEARCH_ERROR"
            )


class CatalogGetItemTool(BaseTool):
    """
    Get detailed product information by product ID.
    
    Required parameters:
    - tenant_id: UUID of the tenant
    - request_id: UUID for request tracing
    - conversation_id: UUID for conversation context
    - product_id: UUID of the product
    """
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tenant_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the tenant"
                },
                "request_id": {
                    "type": "string", 
                    "format": "uuid",
                    "description": "UUID for request tracing"
                },
                "conversation_id": {
                    "type": "string",
                    "format": "uuid", 
                    "description": "UUID for conversation context"
                },
                "product_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the product"
                }
            },
            "required": ["tenant_id", "request_id", "conversation_id", "product_id"],
            "additionalProperties": False
        }
    
    def execute(self, **kwargs) -> ToolResponse:
        """
        Get detailed product information by product ID.
        
        Returns:
            ToolResponse with product details including:
            - product_id: UUID of the product
            - name: Product name
            - description: Full product description
            - price: Product price
            - currency: Price currency
            - category: Product category
            - stock_quantity: Available stock
            - in_stock: Stock availability boolean
            - variants: Product variants (if any)
            - specifications: Product specifications
            - images: Product images
        """
        # Validate required parameters
        error = validate_required_params(kwargs, ["tenant_id", "request_id", "conversation_id", "product_id"])
        if error:
            return ToolResponse(success=False, error=error, error_code="MISSING_PARAMS")
        
        # Validate UUIDs
        for field in ["tenant_id", "request_id", "conversation_id", "product_id"]:
            error = validate_uuid(kwargs[field], field)
            if error:
                return ToolResponse(success=False, error=error, error_code="INVALID_UUID")
        
        tenant_id = kwargs["tenant_id"]
        request_id = kwargs["request_id"]
        conversation_id = kwargs["conversation_id"]
        product_id = kwargs["product_id"]
        
        try:
            # Validate tenant access
            if not self.validate_tenant_access(tenant_id):
                return ToolResponse(
                    success=False, 
                    error="Invalid or inactive tenant",
                    error_code="INVALID_TENANT"
                )
            
            from apps.catalog.models import Product, ProductVariant
            
            # Get product with tenant scoping
            product = Product.objects.select_related('tenant').get(
                id=product_id,
                tenant_id=tenant_id,
                is_active=True
            )
            
            # Get product variants if they exist
            variants = []
            if hasattr(product, 'variants'):
                for variant in product.variants.filter(is_active=True):
                    variant_data = {
                        "variant_id": str(variant.id),
                        "name": variant.name,
                        "price": float(variant.price) if variant.price else None,
                        "stock_quantity": variant.stock_quantity,
                        "sku": getattr(variant, 'sku', None),
                        "attributes": getattr(variant, 'attributes', {}),
                    }
                    variants.append(variant_data)
            
            # Build product data
            data = {
                "product_id": str(product.id),
                "name": product.name,
                "description": product.description,
                "price": float(product.price) if product.price else None,
                "currency": getattr(product, 'currency', 'KES'),
                "category": product.category,
                "stock_quantity": product.stock_quantity,
                "in_stock": product.stock_quantity > 0,
                "sku": getattr(product, 'sku', None),
                "specifications": getattr(product, 'specifications', {}),
                "metadata": getattr(product, 'metadata', {}),
                "variants": variants,
                "images": getattr(product, 'images', []),
                "created_at": product.created_at.isoformat(),
                "updated_at": product.updated_at.isoformat(),
            }
            
            self.log_tool_execution(
                "catalog_get_item", tenant_id, request_id, conversation_id, True
            )
            
            return ToolResponse(success=True, data=data)
            
        except Product.DoesNotExist:
            error_msg = f"Product {product_id} not found in tenant {tenant_id}"
            self.log_tool_execution(
                "catalog_get_item", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="PRODUCT_NOT_FOUND"
            )
        except Exception as e:
            error_msg = f"Failed to get product: {str(e)}"
            self.log_tool_execution(
                "catalog_get_item", tenant_id, request_id, conversation_id, False, error_msg
            )
            return ToolResponse(
                success=False, 
                error=error_msg,
                error_code="FETCH_ERROR"
            )