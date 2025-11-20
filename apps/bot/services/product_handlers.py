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
        Handle CHECKOUT_LINK intent with complete purchase guidance flow.
        
        This method implements the complete checkout guidance flow:
        1. Validates cart has items
        2. Confirms product selection with customer
        3. Confirms quantities
        4. Creates order
        5. Generates payment link or instructions
        6. Provides clear next steps
        
        Args:
            slots: Extracted slots (may include confirmation flags)
            
        Returns:
            dict: Response with checkout guidance
        """
        from apps.orders.models import Cart, Order
        from apps.bot.services.rich_message_builder import RichMessageBuilder
        
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
        
        # Check if this is a confirmation step
        checkout_step = slots.get('checkout_step', 'confirm_items')
        
        if checkout_step == 'confirm_items':
            # Step 1: Confirm product selection
            return self._confirm_product_selection(cart)
        
        elif checkout_step == 'confirm_quantity':
            # Step 2: Confirm quantities
            return self._confirm_quantities(cart)
        
        elif checkout_step == 'generate_payment':
            # Step 3: Generate payment link and complete checkout
            return self._generate_checkout_payment(cart)
        
        else:
            # Default: start with product confirmation
            return self._confirm_product_selection(cart)
    
    def _confirm_product_selection(self, cart) -> Dict[str, Any]:
        """
        Step 1: Confirm product selection with customer.
        
        Args:
            cart: Cart instance
            
        Returns:
            dict: Response asking for product confirmation
        """
        message = "🛒 *Let's review your order*\n\n"
        message += "*Items in your cart:*\n"
        
        for idx, item in enumerate(cart.items, 1):
            message += f"{idx}. {item['title']}\n"
            message += f"   Qty: {item['quantity']} × {item['currency']} {item['price']:.2f}\n"
            item_total = item['quantity'] * item['price']
            message += f"   Subtotal: {item['currency']} {item_total:.2f}\n\n"
        
        message += f"*Cart Total:* {cart.items[0]['currency']} {cart.subtotal:.2f}\n\n"
        message += "Is this correct? Reply 'yes' to continue or 'modify' to make changes."
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'checkout_step': 'confirm_items',
                'cart_id': str(cart.id),
                'item_count': len(cart.items)
            }
        }
    
    def _confirm_quantities(self, cart) -> Dict[str, Any]:
        """
        Step 2: Confirm quantities with customer.
        
        Args:
            cart: Cart instance
            
        Returns:
            dict: Response asking for quantity confirmation
        """
        message = "✅ *Product selection confirmed!*\n\n"
        message += "Let's verify the quantities:\n\n"
        
        for idx, item in enumerate(cart.items, 1):
            message += f"{idx}. {item['title']}\n"
            message += f"   Quantity: *{item['quantity']}*\n\n"
        
        message += "Are these quantities correct? Reply 'yes' to proceed to payment or 'change' to adjust."
        
        return {
            'message': message,
            'action': 'send',
            'message_type': 'bot_response',
            'metadata': {
                'checkout_step': 'confirm_quantity',
                'cart_id': str(cart.id)
            }
        }
    
    def _generate_checkout_payment(self, cart) -> Dict[str, Any]:
        """
        Step 3: Generate payment link and complete checkout.
        
        Args:
            cart: Cart instance
            
        Returns:
            dict: Response with payment link or instructions
        """
        from apps.orders.models import Order
        from apps.integrations.services.payment_service import (
            PaymentService, 
            PaymentProviderNotConfigured,
            PaymentProcessingError
        )
        from apps.bot.services.rich_message_builder import RichMessageBuilder
        
        # Create order
        order = Order.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            currency=cart.items[0]['currency'],
            subtotal=cart.subtotal,
            shipping=0,  # TODO: Calculate shipping
            total=cart.subtotal,
            status='placed',  # Mark as placed, not draft
            items=cart.items
        )
        
        logger.info(
            f"Order created for checkout",
            extra={
                'order_id': str(order.id),
                'customer_id': str(self.customer.id),
                'total': float(order.total)
            }
        )
        
        # Generate checkout link using payment service
        checkout_link = None
        payment_instructions = None
        provider = None
        
        try:
            checkout_data = PaymentService.generate_checkout_link(order)
            checkout_link = checkout_data.get('checkout_url')
            provider = checkout_data.get('provider', 'unknown')
            
            # Handle M-Pesa STK push (no URL)
            if provider == PaymentService.PROVIDER_MPESA and not checkout_link:
                payment_instructions = checkout_data.get(
                    'customer_message',
                    'Please check your phone for the M-Pesa payment prompt.'
                )
            
            logger.info(
                f"Checkout link generated for order {order.id}",
                extra={
                    'order_id': str(order.id),
                    'provider': provider,
                    'amount': float(order.total),
                    'has_link': bool(checkout_link)
                }
            )
            
        except PaymentProviderNotConfigured as e:
            # Fallback: provide manual payment instructions
            logger.warning(
                f"Payment provider not configured for tenant {self.tenant.id}",
                extra={'order_id': str(order.id)}
            )
            payment_instructions = (
                f"Please contact us to complete payment for your order.\n\n"
                f"Order ID: {order.id}\n"
                f"Total: {order.currency} {order.total:.2f}\n\n"
                f"We'll send you payment details shortly."
            )
            
        except PaymentProcessingError as e:
            # Log error and provide fallback
            logger.error(
                f"Payment processing error for order {order.id}: {str(e)}",
                extra={'order_id': str(order.id)},
                exc_info=True
            )
            payment_instructions = (
                f"We're experiencing technical difficulties with payment processing.\n\n"
                f"Order ID: {order.id}\n"
                f"Total: {order.currency} {order.total:.2f}\n\n"
                f"Our team will contact you shortly to complete your order."
            )
        
        # Build checkout message using rich message builder
        message_builder = RichMessageBuilder()
        
        order_summary = {
            'items': [
                {
                    'title': item['title'],
                    'quantity': item['quantity'],
                    'price': item['price']
                }
                for item in cart.items
            ],
            'total': float(order.total),
            'currency': order.currency,
            'customer_info': {
                'name': self.customer.name,
                'phone': str(self.customer.phone_e164)
            }
        }
        
        try:
            # Use rich message builder for checkout message
            rich_message = message_builder.build_checkout_message(
                order_summary=order_summary,
                payment_link=checkout_link,
                payment_instructions=payment_instructions
            )
            
            message = rich_message.body
            
        except Exception as e:
            # Fallback to simple text message
            logger.warning(
                f"Failed to build rich checkout message: {str(e)}",
                extra={'order_id': str(order.id)}
            )
            
            message = f"✅ *Order Confirmed!*\n\n"
            message += f"Order ID: {order.id}\n\n"
            
            for item in cart.items:
                item_total = item['quantity'] * item['price']
                message += f"• {item['quantity']}x {item['title']}\n"
                message += f"  {item['currency']} {item_total:.2f}\n"
            
            message += f"\n*Total:* {order.currency} {order.total:.2f}\n\n"
            
            if checkout_link:
                message += f"💳 *Complete Payment:*\n{checkout_link}\n\n"
            elif payment_instructions:
                message += f"💳 *Payment Instructions:*\n{payment_instructions}\n\n"
            
            message += "Thank you for your order! 🎉"
        
        # Clear cart after successful order creation
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
                'checkout_link': checkout_link,
                'provider': provider,
                'checkout_step': 'complete'
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
