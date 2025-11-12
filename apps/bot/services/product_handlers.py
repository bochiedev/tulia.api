"""
Product intent handlers for catalog browsing and cart operations.

Handles customer intents related to:
- Browsing products
- Viewing product details
- Checking prices and stock
- Adding items to cart
- Generating checkout links
"""
import logging
from typing import Dict, Any, Optional
from django.db.models import Q

logger = logging.getLogger(__name__)


class ProductHandlerError(Exception):
    """Base exception for product handler errors."""
    pass


class ProductIntentHandler:
    """
    Handler for product-related customer intents.
    
    Processes classified intents and generates appropriate responses
    by querying the catalog and formatting results for WhatsApp delivery.
    """
    
    def __init__(self, tenant, conversation, twilio_service):
        """
        Initialize product handler.
        
        Args:
            tenant: Tenant model instance
            conversation: Conversation model instance
            twilio_service: TwilioService instance for sending messages
        """
        self.tenant = tenant
        self.conversation = conversation
        self.customer = conversation.customer
        self.twilio_service = twilio_service
    
    def handle_greeting(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle GREETING intent.
        
        Args:
            slots: Extracted slots from intent classification
            
        Returns:
            dict: Response with message and action
        """
        customer_name = self.customer.name or "there"
        
        message = f"Hi {customer_name}! 👋 Welcome to {self.tenant.name}.\n\n"
        message += "I can help you:\n"
        message += "• Browse our products\n"
        message += "• Check availability\n"
        message += "• Book services\n"
        message += "• Place orders\n\n"
        message += "What would you like to do today?"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response'
        }
    
    def handle_browse_products(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle BROWSE_PRODUCTS intent.
        
        Args:
            slots: Extracted slots (may include product_query for filtering)
            
        Returns:
            dict: Response with product list
        """
        from apps.catalog.models import Product
        
        # Get active products for tenant
        products = Product.objects.for_tenant(self.tenant).active()
        
        # Apply search filter if query provided
        query = slots.get('product_query')
        if query:
            products = products.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Limit to first 10 products
        products = products[:10]
        
        if not products.exists():
            if query:
                message = f"Sorry, I couldn't find any products matching '{query}'.\n\n"
                message += "Try browsing all products or search for something else."
            else:
                message = "We don't have any products available at the moment.\n\n"
                message += "Please check back later!"
            
            return {
                'message': message,
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format product list
        if query:
            message = f"Here are products matching '{query}':\n\n"
        else:
            message = "Here are our available products:\n\n"
        
        for idx, product in enumerate(products, 1):
            message += f"{idx}. *{product.title}*\n"
            message += f"   {product.currency} {product.price:.2f}\n"
            
            if product.description:
                # Truncate description to 100 chars
                desc = product.description[:100]
                if len(product.description) > 100:
                    desc += "..."
                message += f"   {desc}\n"
            
            if not product.is_in_stock:
                message += "   ⚠️ Out of stock\n"
            
            message += "\n"
        
        message += "Reply with a product name to see more details!"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'product_count': len(products),
                'query': query
            }
        }
    
    def handle_product_details(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle PRODUCT_DETAILS intent.
        
        Args:
            slots: Extracted slots with product_query or product_id
            
        Returns:
            dict: Response with product details
        """
        from apps.catalog.models import Product
        
        product_id = slots.get('product_id')
        product_query = slots.get('product_query')
        
        # Find product
        if product_id:
            try:
                product = Product.objects.for_tenant(self.tenant).get(id=product_id)
            except Product.DoesNotExist:
                return {
                    'message': "Sorry, I couldn't find that product. Please try browsing our catalog.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
        elif product_query:
            products = Product.objects.for_tenant(self.tenant).active().filter(
                title__icontains=product_query
            )[:1]
            
            if not products.exists():
                return {
                    'message': f"Sorry, I couldn't find a product matching '{product_query}'.\n\nTry browsing all products or search for something else.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
            
            product = products[0]
        else:
            return {
                'message': "Which product would you like to know more about?",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Format product details
        message = f"*{product.title}*\n\n"
        
        if product.description:
            message += f"{product.description}\n\n"
        
        message += f"💰 Price: {product.currency} {product.price:.2f}\n"
        
        if product.stock is not None:
            if product.is_in_stock:
                message += f"📦 Stock: {product.stock} available\n"
            else:
                message += "⚠️ Currently out of stock\n"
        else:
            message += "✅ In stock\n"
        
        # Show variants if available
        variants = product.variants.all()
        if variants.exists():
            message += f"\n*Available Options:*\n"
            for variant in variants[:5]:
                price_str = f"{variant.currency} {variant.effective_price:.2f}"
                stock_str = ""
                if not variant.is_in_stock:
                    stock_str = " (Out of stock)"
                message += f"• {variant.title} - {price_str}{stock_str}\n"
        
        message += "\nWould you like to add this to your cart?"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'product_id': str(product.id),
                'product_title': product.title
            }
        }
    
    def handle_price_check(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle PRICE_CHECK intent.
        
        Args:
            slots: Extracted slots with product_query
            
        Returns:
            dict: Response with pricing information
        """
        # Reuse product_details handler as it includes pricing
        return self.handle_product_details(slots)
    
    def handle_add_to_cart(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle ADD_TO_CART intent.
        
        Args:
            slots: Extracted slots with product_id, variant_id, quantity
            
        Returns:
            dict: Response with cart update confirmation
        """
        from apps.catalog.models import Product, ProductVariant
        from apps.orders.models import Cart
        
        product_id = slots.get('product_id')
        variant_id = slots.get('variant_id')
        quantity = int(slots.get('quantity', 1))
        
        if not product_id:
            return {
                'message': "Which product would you like to add to your cart?",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Get product
        try:
            product = Product.objects.for_tenant(self.tenant).get(id=product_id)
        except Product.DoesNotExist:
            return {
                'message': "Sorry, I couldn't find that product.",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Get variant if specified
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                return {
                    'message': "Sorry, that product option is not available.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
        
        # Check stock
        if variant:
            if not variant.has_stock(quantity):
                return {
                    'message': f"Sorry, we only have {variant.stock or 0} of {variant.title} in stock.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
            price = variant.effective_price
            item_title = f"{product.title} - {variant.title}"
        else:
            if not product.has_stock(quantity):
                return {
                    'message': f"Sorry, we only have {product.stock or 0} of {product.title} in stock.",
                    'action': 'send',
                    'message_type': 'bot_response'
                }
            price = product.price
            item_title = product.title
        
        # Get or create cart
        cart, created = Cart.objects.get_or_create(
            conversation=self.conversation,
            defaults={'items': [], 'subtotal': 0}
        )
        
        # Add item to cart
        cart_item = {
            'product_id': str(product.id),
            'variant_id': str(variant.id) if variant else None,
            'title': item_title,
            'quantity': quantity,
            'price': float(price),
            'currency': product.currency
        }
        
        # Check if item already in cart
        existing_item = None
        for idx, item in enumerate(cart.items):
            if (item['product_id'] == cart_item['product_id'] and 
                item.get('variant_id') == cart_item['variant_id']):
                existing_item = idx
                break
        
        if existing_item is not None:
            # Update quantity
            cart.items[existing_item]['quantity'] += quantity
        else:
            # Add new item
            cart.items.append(cart_item)
        
        # Recalculate subtotal
        cart.subtotal = sum(
            item['quantity'] * item['price']
            for item in cart.items
        )
        cart.save()
        
        # Format response
        message = f"✅ Added {quantity}x {item_title} to your cart!\n\n"
        message += f"*Cart Summary:*\n"
        
        for item in cart.items:
            item_total = item['quantity'] * item['price']
            message += f"• {item['quantity']}x {item['title']} - {item['currency']} {item_total:.2f}\n"
        
        message += f"\n*Subtotal:* {product.currency} {cart.subtotal:.2f}\n\n"
        message += "Ready to checkout? Just say 'checkout' or 'complete order'!"
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'cart_id': str(cart.id),
                'item_count': len(cart.items),
                'subtotal': float(cart.subtotal)
            }
        }
    
    def handle_checkout_link(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle CHECKOUT_LINK intent.
        
        Args:
            slots: Extracted slots
            
        Returns:
            dict: Response with checkout link
        """
        from apps.orders.models import Cart, Order
        
        # Get cart
        try:
            cart = Cart.objects.get(conversation=self.conversation)
        except Cart.DoesNotExist:
            return {
                'message': "Your cart is empty. Browse our products and add items to get started!",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        if not cart.items:
            return {
                'message': "Your cart is empty. Browse our products and add items to get started!",
                'action': 'send',
                'message_type': 'bot_response'
            }
        
        # Create order
        order = Order.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            currency=cart.items[0]['currency'],
            subtotal=cart.subtotal,
            shipping=0,  # TODO: Calculate shipping
            total=cart.subtotal,
            status='draft',
            items=cart.items
        )
        
        # Generate checkout link using payment service
        from apps.integrations.services.payment_service import PaymentService, PaymentProviderNotConfigured
        
        try:
            checkout_data = PaymentService.generate_checkout_link(order)
            checkout_link = checkout_data['checkout_url']
            provider = checkout_data.get('provider', 'unknown')
            
            logger.info(
                f"Checkout link generated for order {order.id}",
                extra={
                    'order_id': str(order.id),
                    'provider': provider,
                    'amount': float(order.total)
                }
            )
        except PaymentProviderNotConfigured:
            # Fallback to external checkout if payment facilitation not enabled
            checkout_link = f"https://checkout.example.com/order/{order.id}"
            logger.info(
                f"Payment facilitation not enabled, using external checkout for order {order.id}"
            )
        
        # Format response
        message = f"🛒 *Order Summary*\n\n"
        
        for item in cart.items:
            item_total = item['quantity'] * item['price']
            message += f"• {item['quantity']}x {item['title']}\n"
            message += f"  {item['currency']} {item_total:.2f}\n"
        
        message += f"\n*Subtotal:* {order.currency} {order.subtotal:.2f}\n"
        message += f"*Shipping:* {order.currency} {order.shipping:.2f}\n"
        message += f"*Total:* {order.currency} {order.total:.2f}\n\n"
        message += f"Complete your order here:\n{checkout_link}\n\n"
        message += "Thank you for shopping with us! 🎉"
        
        # Clear cart
        cart.items = []
        cart.subtotal = 0
        cart.save()
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'order_id': str(order.id),
                'total': float(order.total),
                'checkout_link': checkout_link
            }
        }
    
    def send_response(self, response: Dict[str, Any]):
        """
        Send response message via Twilio.
        
        Args:
            response: Response dict from handler
        """
        if response['action'] == 'send':
            try:
                result = self.twilio_service.send_whatsapp(
                    to=self.customer.phone_e164,
                    body=response['message']
                )
                
                # Create message record
                from apps.messaging.models import Message
                Message.objects.create(
                    conversation=self.conversation,
                    direction='out',
                    message_type=response.get('message_type', 'bot_response'),
                    text=response['message'],
                    provider_msg_id=result['sid'],
                    payload=response.get('metadata', {})
                )
                
                logger.info(
                    f"Product handler response sent",
                    extra={
                        'conversation_id': str(self.conversation.id),
                        'message_sid': result['sid']
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to send product handler response",
                    extra={'conversation_id': str(self.conversation.id)},
                    exc_info=True
                )
                raise ProductHandlerError(f"Failed to send response: {str(e)}")


def create_product_handler(tenant, conversation, twilio_service) -> ProductIntentHandler:
    """
    Factory function to create ProductIntentHandler instance.
    
    Args:
        tenant: Tenant model instance
        conversation: Conversation model instance
        twilio_service: TwilioService instance
        
    Returns:
        ProductIntentHandler: Configured handler instance
    """
    return ProductIntentHandler(tenant, conversation, twilio_service)
