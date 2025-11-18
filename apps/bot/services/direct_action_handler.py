"""
Direct action handler for streamlined purchase and booking flows.
"""
import logging
from typing import Dict, Any, Optional
from apps.catalog.models import Product
from apps.services.models import Service, Appointment
from apps.orders.models import Order
from apps.messaging.models import Conversation
from apps.bot.services.rich_message_builder import RichMessageBuilder

logger = logging.getLogger(__name__)


class DirectActionHandler:
    """
    Handles direct action buttons for streamlined journeys.
    
    Provides one-click or minimal-step flows for:
    - Buy Now (products)
    - Book Now (services)
    - Add to Cart
    - Check Availability
    """
    
    def __init__(self, tenant, conversation, customer):
        """
        Initialize handler.
        
        Args:
            tenant: Tenant instance
            conversation: Conversation instance
            customer: Customer instance
        """
        self.tenant = tenant
        self.conversation = conversation
        self.customer = customer
        self.message_builder = RichMessageBuilder()
    
    def handle_buy_now(self, product_id: str) -> Dict[str, Any]:
        """
        Handle "Buy Now" action for immediate purchase.
        
        Streamlined flow:
        1. Confirm product and quantity
        2. Pre-fill customer info from history
        3. Collect delivery details (if needed)
        4. Process payment
        
        Args:
            product_id: Product UUID
        
        Returns:
            dict with response message and next_action
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            
            # Check stock
            if not product.is_in_stock:
                return {
                    'success': False,
                    'message': f"Sorry, {product.title} is currently out of stock. Would you like to be notified when it's available?",
                    'next_action': 'stock_notification',
                    'product_id': str(product.id)
                }
            
            # Check if we have customer's delivery info
            has_delivery_info = self._has_delivery_info()
            
            if has_delivery_info:
                # Skip to quantity confirmation
                message = self._build_quick_purchase_message(product)
                return {
                    'success': True,
                    'message': message,
                    'next_action': 'confirm_quantity',
                    'product_id': str(product.id),
                    'skip_steps': ['delivery_info']
                }
            else:
                # Need delivery info first
                message = self._build_delivery_info_request(product)
                return {
                    'success': True,
                    'message': message,
                    'next_action': 'collect_delivery_info',
                    'product_id': str(product.id)
                }
        
        except Product.DoesNotExist:
            logger.error(f"Product not found: {product_id}")
            return {
                'success': False,
                'message': "Sorry, I couldn't find that product. Let me show you our available items.",
                'next_action': 'show_catalog'
            }
        
        except Exception as e:
            logger.error(f"Error in buy_now: {e}", exc_info=True)
            return {
                'success': False,
                'message': "Sorry, something went wrong. Please try again or let me know if you need help.",
                'next_action': 'retry'
            }
    
    def handle_book_now(self, service_id: str, variant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle "Book Now" action for immediate booking.
        
        Streamlined flow:
        1. Show available time slots (today + next 7 days)
        2. One-click slot selection
        3. Confirm booking
        
        Args:
            service_id: Service UUID
            variant_id: Optional ServiceVariant UUID
        
        Returns:
            dict with response message and next_action
        """
        try:
            service = Service.objects.get(id=service_id, tenant=self.tenant)
            
            # Get available slots
            available_slots = self._get_available_slots(service, days_ahead=7)
            
            if not available_slots:
                return {
                    'success': False,
                    'message': f"Sorry, {service.name} doesn't have any available slots in the next week. Would you like to check later dates?",
                    'next_action': 'check_later_dates',
                    'service_id': str(service.id)
                }
            
            # Build slot selection message
            message = self._build_slot_selection_message(service, available_slots)
            
            return {
                'success': True,
                'message': message,
                'next_action': 'select_slot',
                'service_id': str(service.id),
                'variant_id': variant_id,
                'available_slots': available_slots
            }
        
        except Service.DoesNotExist:
            logger.error(f"Service not found: {service_id}")
            return {
                'success': False,
                'message': "Sorry, I couldn't find that service. Let me show you our available services.",
                'next_action': 'show_services'
            }
        
        except Exception as e:
            logger.error(f"Error in book_now: {e}", exc_info=True)
            return {
                'success': False,
                'message': "Sorry, something went wrong. Please try again or let me know if you need help.",
                'next_action': 'retry'
            }
    
    def handle_add_to_cart(self, product_id: str) -> Dict[str, Any]:
        """
        Handle "Add to Cart" action for multi-item purchases.
        
        Args:
            product_id: Product UUID
        
        Returns:
            dict with response message and next_action
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            
            # Add to cart (stored in conversation context)
            cart = self._get_or_create_cart()
            cart_item = self._add_to_cart(cart, product)
            
            message = (
                f"✅ Added {product.title} to your cart!\n\n"
                f"Cart total: {len(cart['items'])} item(s)\n"
                f"Total: {self._format_price(cart['total'])}\n\n"
                f"Would you like to:\n"
                f"• Continue shopping\n"
                f"• Checkout now\n"
                f"• View cart"
            )
            
            buttons = [
                {'id': 'continue_shopping', 'text': '🛍️ Continue Shopping'},
                {'id': 'checkout', 'text': '💳 Checkout'},
                {'id': 'view_cart', 'text': '🛒 View Cart'}
            ]
            
            return {
                'success': True,
                'message': message,
                'buttons': buttons,
                'next_action': 'cart_action',
                'cart': cart
            }
        
        except Product.DoesNotExist:
            logger.error(f"Product not found: {product_id}")
            return {
                'success': False,
                'message': "Sorry, I couldn't find that product.",
                'next_action': 'show_catalog'
            }
        
        except Exception as e:
            logger.error(f"Error in add_to_cart: {e}", exc_info=True)
            return {
                'success': False,
                'message': "Sorry, couldn't add to cart. Please try again.",
                'next_action': 'retry'
            }
    
    def handle_check_availability(self, service_id: str) -> Dict[str, Any]:
        """
        Handle "Check Availability" action.
        
        Args:
            service_id: Service UUID
        
        Returns:
            dict with response message and available slots
        """
        try:
            service = Service.objects.get(id=service_id, tenant=self.tenant)
            
            # Get available slots for next 14 days
            available_slots = self._get_available_slots(service, days_ahead=14)
            
            if not available_slots:
                return {
                    'success': True,
                    'message': f"Sorry, {service.name} is fully booked for the next 2 weeks. Would you like me to notify you when slots open up?",
                    'next_action': 'availability_notification',
                    'service_id': str(service.id)
                }
            
            # Group slots by date
            slots_by_date = self._group_slots_by_date(available_slots)
            
            message = f"📅 Available times for {service.name}:\n\n"
            
            for date, slots in list(slots_by_date.items())[:7]:  # Show first 7 days
                message += f"*{date}*\n"
                for slot in slots[:5]:  # Show first 5 slots per day
                    message += f"  • {slot['time']}\n"
                if len(slots) > 5:
                    message += f"  ... and {len(slots) - 5} more\n"
                message += "\n"
            
            message += "Would you like to book one of these times?"
            
            buttons = [
                {'id': f'book_service_{service.id}', 'text': '📅 Book Now'},
                {'id': 'show_more_dates', 'text': '📆 More Dates'}
            ]
            
            return {
                'success': True,
                'message': message,
                'buttons': buttons,
                'next_action': 'booking_action',
                'service_id': str(service.id),
                'available_slots': available_slots
            }
        
        except Service.DoesNotExist:
            logger.error(f"Service not found: {service_id}")
            return {
                'success': False,
                'message': "Sorry, I couldn't find that service.",
                'next_action': 'show_services'
            }
        
        except Exception as e:
            logger.error(f"Error checking availability: {e}", exc_info=True)
            return {
                'success': False,
                'message': "Sorry, couldn't check availability. Please try again.",
                'next_action': 'retry'
            }
    
    def confirm_purchase(self, product_id: str, quantity: int = 1, delivery_info: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Confirm and process purchase.
        
        Args:
            product_id: Product UUID
            quantity: Quantity to purchase
            delivery_info: Optional delivery information
        
        Returns:
            dict with order details and confirmation
        """
        try:
            product = Product.objects.get(id=product_id, tenant=self.tenant)
            
            # Create order
            order_items = [{
                'product_id': str(product.id),
                'product_name': product.title,
                'quantity': quantity,
                'unit_price': float(product.price),
                'total_price': float(product.price * quantity)
            }]
            
            subtotal = product.price * quantity
            
            order = Order.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                currency=self.tenant.currency,
                subtotal=subtotal,
                shipping=0,
                total=subtotal,
                status='placed',
                items=order_items,
                metadata={'delivery_info': delivery_info or {}}
            )
            
            message = (
                f"✅ Order confirmed!\n\n"
                f"Order #{order.order_number}\n"
                f"{quantity}x {product.title}\n"
                f"Total: {self._format_price(order.total_amount)}\n\n"
                f"We'll send you payment details shortly."
            )
            
            return {
                'success': True,
                'message': message,
                'order_id': str(order.id),
                'order_number': order.order_number,
                'next_action': 'payment'
            }
        
        except Exception as e:
            logger.error(f"Error confirming purchase: {e}", exc_info=True)
            return {
                'success': False,
                'message': "Sorry, couldn't process your order. Please try again.",
                'next_action': 'retry'
            }
    
    def confirm_booking(self, service_id: str, slot_time: str, variant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Confirm and create booking.
        
        Args:
            service_id: Service UUID
            slot_time: Selected time slot (ISO format)
            variant_id: Optional variant UUID
        
        Returns:
            dict with booking details and confirmation
        """
        try:
            service = Service.objects.get(id=service_id, tenant=self.tenant)
            
            # Create appointment
            from datetime import datetime
            slot_datetime = datetime.fromisoformat(slot_time)
            
            appointment = Appointment.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                service=service,
                scheduled_at=slot_datetime,
                duration_minutes=service.duration_minutes,
                status='confirmed'
            )
            
            message = (
                f"✅ Booking confirmed!\n\n"
                f"Service: {service.name}\n"
                f"Date: {slot_datetime.strftime('%A, %B %d, %Y')}\n"
                f"Time: {slot_datetime.strftime('%I:%M %p')}\n"
                f"Duration: {service.duration_minutes} minutes\n\n"
                f"We'll send you a reminder before your appointment."
            )
            
            return {
                'success': True,
                'message': message,
                'appointment_id': str(appointment.id),
                'next_action': 'complete'
            }
        
        except Exception as e:
            logger.error(f"Error confirming booking: {e}", exc_info=True)
            return {
                'success': False,
                'message': "Sorry, couldn't create your booking. Please try again.",
                'next_action': 'retry'
            }
    
    # Helper methods
    
    def _has_delivery_info(self) -> bool:
        """Check if customer has delivery info on file."""
        # Check previous orders
        previous_orders = Order.objects.filter(
            tenant=self.tenant,
            customer=self.customer
        ).exclude(delivery_info={}).first()
        
        return previous_orders is not None
    
    def _get_available_slots(self, service, days_ahead=7):
        """Get available time slots for service."""
        # This would integrate with the availability system
        # For now, return placeholder
        from datetime import datetime, timedelta
        
        slots = []
        base_date = datetime.now()
        
        for day in range(days_ahead):
            date = base_date + timedelta(days=day)
            # Add some sample slots
            for hour in [9, 11, 14, 16]:
                slot_time = date.replace(hour=hour, minute=0, second=0)
                slots.append({
                    'time': slot_time.strftime('%I:%M %p'),
                    'datetime': slot_time.isoformat(),
                    'date': slot_time.strftime('%Y-%m-%d')
                })
        
        return slots
    
    def _group_slots_by_date(self, slots):
        """Group slots by date."""
        from collections import defaultdict
        grouped = defaultdict(list)
        
        for slot in slots:
            date = slot['date']
            grouped[date].append(slot)
        
        return dict(grouped)
    
    def _get_or_create_cart(self):
        """Get or create shopping cart from conversation context."""
        if hasattr(self.conversation, 'context'):
            context = self.conversation.context
            if hasattr(context, 'shopping_cart'):
                return context.shopping_cart
        
        return {'items': [], 'total': 0}
    
    def _add_to_cart(self, cart, product, quantity=1):
        """Add product to cart."""
        cart['items'].append({
            'product_id': str(product.id),
            'name': product.title,
            'quantity': quantity,
            'price': float(product.price)
        })
        cart['total'] = sum(item['price'] * item['quantity'] for item in cart['items'])
        
        # Save to context
        if hasattr(self.conversation, 'context'):
            context = self.conversation.context
            context.shopping_cart = cart
            context.save()
        
        return cart['items'][-1]
    
    def _format_price(self, amount):
        """Format price with currency."""
        return f"{self.tenant.currency} {amount:,.2f}"
    
    def _build_quick_purchase_message(self, product):
        """Build quick purchase confirmation message."""
        return (
            f"Great! Let's get {product.title} for you.\n\n"
            f"Price: {self._format_price(product.price)}\n\n"
            f"How many would you like? (Reply with a number or tap below)"
        )
    
    def _build_delivery_info_request(self, product):
        """Build delivery info request message."""
        return (
            f"Perfect! I'll help you order {product.title}.\n\n"
            f"First, I need your delivery details:\n"
            f"• Full name\n"
            f"• Phone number\n"
            f"• Delivery address\n\n"
            f"You can send them all at once or one by one."
        )
    
    def _build_slot_selection_message(self, service, slots):
        """Build slot selection message."""
        message = f"📅 Available times for {service.name}:\n\n"
        
        # Show first 5 slots
        for i, slot in enumerate(slots[:5], 1):
            message += f"{i}. {slot['date']} at {slot['time']}\n"
        
        if len(slots) > 5:
            message += f"\n... and {len(slots) - 5} more slots available\n"
        
        message += "\nReply with the number of your preferred time, or tap 'More Times' to see all options."
        
        return message
