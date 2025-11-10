"""
Serializers for catalog API endpoints.
"""
from rest_framework import serializers
from apps.catalog.models import Product, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant."""
    
    effective_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        help_text="Effective price (variant price or product price)"
    )
    currency = serializers.CharField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'title', 'sku', 'stock', 'price',
            'effective_price', 'currency', 'attrs', 'metadata',
            'is_in_stock', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'product', 'created_at', 'updated_at']


class ProductVariantCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ProductVariant."""
    
    class Meta:
        model = ProductVariant
        fields = [
            'title', 'sku', 'stock', 'price', 'attrs', 'metadata'
        ]


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for Product list view (without variants)."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    variant_count = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'tenant', 'tenant_name', 'external_source', 'external_id',
            'title', 'description', 'images', 'price', 'currency',
            'sku', 'stock', 'is_active', 'is_in_stock', 'variant_count',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_name', 'created_at', 'updated_at']


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer for Product detail view (with variants)."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    variant_count = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'tenant', 'tenant_name', 'external_source', 'external_id',
            'title', 'description', 'images', 'price', 'currency',
            'sku', 'stock', 'is_active', 'is_in_stock', 'variant_count',
            'variants', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_name', 'created_at', 'updated_at']


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Product."""
    
    variants = ProductVariantCreateSerializer(many=True, required=False)
    
    class Meta:
        model = Product
        fields = [
            'external_source', 'external_id', 'title', 'description',
            'images', 'price', 'currency', 'sku', 'stock', 'is_active',
            'metadata', 'variants'
        ]
    
    def validate(self, data):
        """Validate product data."""
        # If external_source is provided, external_id is required
        if data.get('external_source') and not data.get('external_id'):
            raise serializers.ValidationError({
                'external_id': 'external_id is required when external_source is provided'
            })
        
        # If external_id is provided, external_source is required
        if data.get('external_id') and not data.get('external_source'):
            raise serializers.ValidationError({
                'external_source': 'external_source is required when external_id is provided'
            })
        
        return data


class ProductUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Product."""
    
    class Meta:
        model = Product
        fields = [
            'title', 'description', 'images', 'price', 'currency',
            'sku', 'stock', 'is_active', 'metadata'
        ]
        extra_kwargs = {
            'title': {'required': False},
            'price': {'required': False},
            'currency': {'required': False},
        }


class ProductSearchSerializer(serializers.Serializer):
    """Serializer for product search parameters."""
    
    query = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Search query for title and description"
    )
    is_active = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Filter by active status"
    )
    min_price = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text="Minimum price filter"
    )
    max_price = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text="Maximum price filter"
    )
    external_source = serializers.ChoiceField(
        choices=['woocommerce', 'shopify', 'manual'],
        required=False,
        help_text="Filter by external source"
    )
    in_stock = serializers.BooleanField(
        required=False,
        help_text="Filter by stock availability"
    )
    page = serializers.IntegerField(
        required=False,
        min_value=1,
        default=1,
        help_text="Page number"
    )
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=50,
        help_text="Number of items per page"
    )
    
    def validate(self, data):
        """Validate search parameters."""
        # Ensure min_price <= max_price if both provided
        if 'min_price' in data and 'max_price' in data:
            if data['min_price'] > data['max_price']:
                raise serializers.ValidationError({
                    'min_price': 'min_price must be less than or equal to max_price'
                })
        
        return data
