"""
Serializers for order API endpoints.
"""
from rest_framework import serializers
from apps.orders.models import Order, Cart


class CartItemSerializer(serializers.Serializer):
    """Serializer for cart item (embedded in Cart)."""
    
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(allow_null=True, required=False)
    title = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3)


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart."""
    
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    conversation_id = serializers.UUIDField(source='conversation.id', read_only=True)
    
    class Meta:
        model = Cart
        fields = [
            'id', 'conversation_id', 'items', 'item_count',
            'subtotal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.Serializer):
    """Serializer for order item (embedded in Order)."""
    
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(allow_null=True, required=False)
    title = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3, required=False, allow_null=True)


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for Order list view."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone_e164', read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'tenant_name', 'customer', 'customer_name',
            'customer_phone', 'currency', 'subtotal', 'shipping', 'total',
            'status', 'item_count', 'payment_ref', 'paid_at', 'fulfilled_at',
            'tracking_number', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_name', 'customer_name', 'customer_phone',
            'created_at', 'updated_at'
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    """Serializer for Order detail view (with items)."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone_e164', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    checkout_url = serializers.SerializerMethodField()
    payment_provider = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'tenant_name', 'customer', 'customer_name',
            'customer_phone', 'currency', 'subtotal', 'shipping', 'total',
            'status', 'items', 'item_count', 'payment_ref', 'paid_at',
            'fulfilled_at', 'tracking_number', 'checkout_url', 'payment_provider',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_name', 'customer_name', 'customer_phone',
            'checkout_url', 'payment_provider', 'created_at', 'updated_at'
        ]
    
    def get_checkout_url(self, obj):
        """Generate checkout URL for unpaid orders."""
        # Only generate checkout URL for draft/placed orders
        if obj.status not in ['draft', 'placed']:
            return None
        
        # If payment_ref exists, try to retrieve existing checkout URL
        if obj.payment_ref:
            # For Stripe, we can reconstruct the checkout URL
            if obj.payment_ref.startswith('cs_'):  # Stripe session ID
                return f"https://checkout.stripe.com/c/pay/{obj.payment_ref}"
            # For other providers, return None (would need to be stored in metadata)
            return obj.metadata.get('checkout_url')
        
        return None
    
    def get_payment_provider(self, obj):
        """Get payment provider for the order."""
        from apps.integrations.services.payment_service import PaymentService
        
        provider = PaymentService.get_configured_provider(obj.tenant)
        return provider if provider else 'external'


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Order."""
    
    items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = [
            'customer', 'currency', 'subtotal', 'shipping', 'total',
            'status', 'items', 'payment_ref', 'metadata'
        ]
    
    def validate_customer(self, value):
        """Ensure customer belongs to request tenant."""
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            if value.tenant_id != request.tenant.id:
                raise serializers.ValidationError(
                    "Customer does not belong to your tenant"
                )
        return value
    
    def validate(self, data):
        """Validate order data."""
        # Ensure items list is not empty
        if not data.get('items'):
            raise serializers.ValidationError({
                'items': 'Order must contain at least one item'
            })
        
        # Validate total matches subtotal + shipping
        calculated_total = data['subtotal'] + data.get('shipping', 0)
        if abs(calculated_total - data['total']) > 0.01:  # Allow for rounding
            raise serializers.ValidationError({
                'total': f'Total must equal subtotal + shipping ({calculated_total})'
            })
        
        return data
    
    def create(self, validated_data):
        """Create order with tenant from request context."""
        # Tenant is injected by view from request.tenant
        validated_data['tenant'] = self.context['request'].tenant
        return super().create(validated_data)


class OrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Order (status changes)."""
    
    class Meta:
        model = Order
        fields = ['status', 'payment_ref', 'tracking_number', 'metadata']
    
    def validate_status(self, value):
        """Validate status transitions."""
        instance = self.instance
        if not instance:
            return value
        
        # Define valid status transitions
        valid_transitions = {
            'draft': ['placed', 'canceled'],
            'placed': ['paid', 'canceled'],
            'paid': ['fulfilled', 'canceled'],
            'fulfilled': [],  # Terminal state
            'canceled': []  # Terminal state
        }
        
        current_status = instance.status
        if value not in valid_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Cannot transition from '{current_status}' to '{value}'"
            )
        
        return value
