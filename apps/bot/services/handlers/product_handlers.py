"""
Product browsing and selection handlers for the sales orchestration refactor.

These handlers implement deterministic product browsing logic without LLMs.
"""
from typing import Dict, Any
from django.utils import timezone

from apps.catalog.models import Product
from apps.bot.services.business_logic_router import BotAction
from apps.bot.services.intent_detection_engine import IntentResult
from apps.bot.models import ConversationContext
from apps.tenants.models import Tenant, Customer


def handle_browse_products(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Show products from database.
    NO LLM calls.
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
    """
    # Extract filters from slots
    category = intent_result.slots.get('category')
    budget_max = intent_result.slots.get('budget')
    
    # Query database (tenant-scoped)
    products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        deleted_at__isnull=True
    )
    
    # Apply filters if provided
    if category:
        # Search in title, description, or metadata
        products = products.filter(
            models.Q(title__icontains=category) |
            models.Q(description__icontains=category) |
            models.Q(metadata__category__icontains=category)
        )
    
    if budget_max:
        try:
            budget_value = float(budget_max)
            products = products.filter(price__lte=budget_value)
        except (ValueError, TypeError):
            pass  # Ignore invalid budget
    
    # Limit to 10 products (Requirement 5.2)
    products = products[:10]
    
    # Handle empty catalog (Requirement 5.5)
    if not products.exists():
        # Try without filters
        all_products = Product.objects.filter(
            tenant=tenant,
            is_active=True,
            deleted_at__isnull=True
        )[:10]
        
        if not all_products.exists():
            # No products at all
            return BotAction(
                type="TEXT",
                text="We don't have any products available at the moment. Would you like to speak with someone from our team?",
                new_context={
                    'current_flow': 'empty_catalog',
                    'awaiting_response': True,
                    'last_question': 'empty_catalog_handoff',
                },
                side_effects=['empty_catalog']
            )
        
        # Show all products with explanation
        products = all_products
        text = _format_no_match_message(category, budget_max, intent_result.language)
    else:
        text = _format_products_intro(len(products), intent_result.language)
    
    # Serialize products for display
    product_list = []
    for i, product in enumerate(products, 1):
        product_list.append({
            'id': str(product.id),
            'position': i,
            'title': product.title,
            'price': float(product.price),
            'currency': product.currency,
            'description': product.description[:100] if product.description else '',
            'image': product.images[0] if product.images else None,
            'in_stock': product.has_stock(),
        })
    
    # Store last_menu in context (Requirement 5.3)
    return BotAction(
        type="PRODUCT_CARDS",
        text=text,
        rich_payload={
            'products': product_list
        },
        new_context={
            'last_menu': {
                'type': 'products',
                'items': [{'id': p['id'], 'position': p['position']} for p in product_list],
                'timestamp': timezone.now().isoformat(),
            },
            'last_menu_timestamp': timezone.now(),
            'current_flow': 'browsing_products',
            'awaiting_response': False,
        },
        side_effects=['products_displayed']
    )


def _format_products_intro(count: int, language: list) -> str:
    """Format introduction message for products."""
    if 'sw' in language or 'sheng' in language:
        return f"Hizi ni bidhaa zetu ({count}):"
    return f"Here are our products ({count}):"


def _format_no_match_message(category: str, budget: Any, language: list) -> str:
    """Format message when no products match filters."""
    if 'sw' in language or 'sheng' in language:
        if category and budget:
            return f"Hatujapata bidhaa za '{category}' chini ya {budget}, lakini hizi ni bidhaa zetu:"
        elif category:
            return f"Hatujapata bidhaa za '{category}', lakini hizi ni bidhaa zetu:"
        elif budget:
            return f"Hatujapata bidhaa chini ya {budget}, lakini hizi ni bidhaa zetu:"
        return "Hizi ni bidhaa zetu:"
    
    if category and budget:
        return f"We couldn't find '{category}' products under {budget}, but here are our products:"
    elif category:
        return f"We couldn't find '{category}' products, but here are our products:"
    elif budget:
        return f"We couldn't find products under {budget}, but here are our products:"
    return "Here are our products:"


def handle_product_details(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Show product details.
    NO LLM calls.
    
    Requirements: 6.1, 6.4, 6.5
    """
    # Get product from slots or context
    product_id = intent_result.slots.get('product_id')
    selected_item = intent_result.slots.get('selected_item')
    
    if not product_id and selected_item:
        product_id = selected_item.get('id')
    
    if not product_id:
        # No product specified
        return BotAction(
            type="TEXT",
            text="Which product would you like to know more about? Please select a number from the list.",
            new_context={
                'current_flow': 'browsing_products',
                'awaiting_response': True,
                'last_question': 'product_selection',
            }
        )
    
    # Query product (tenant-scoped)
    try:
        product = Product.objects.get(
            id=product_id,
            tenant=tenant,
            is_active=True,
            deleted_at__isnull=True
        )
    except Product.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Sorry, that product is no longer available. Would you like to see other products?",
            new_context={
                'current_flow': 'browsing_products',
                'awaiting_response': True,
                'last_question': 'product_not_found',
            }
        )
    
    # Format product details
    text = _format_product_details(product, intent_result.language)
    
    # Update context
    context.last_product_viewed = product
    context.save(update_fields=['last_product_viewed'])
    
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': f'order_{product.id}', 'title': 'Order Now'},
                {'id': 'browse_more', 'title': 'Browse More'},
            ]
        },
        new_context={
            'current_flow': 'product_details',
            'awaiting_response': True,
            'last_question': 'order_or_browse',
            'entities': {
                'product_id': str(product.id),
                'product_name': product.title,
                'product_price': float(product.price),
            }
        },
        side_effects=['product_viewed']
    )


def _format_product_details(product: Product, language: list) -> str:
    """Format product details message."""
    stock_status = "In stock" if product.has_stock() else "Out of stock"
    if 'sw' in language or 'sheng' in language:
        stock_status = "Iko" if product.has_stock() else "Haiko"
    
    details = [
        f"📦 {product.title}",
        f"💰 {product.currency} {product.price}",
        f"📊 {stock_status}",
    ]
    
    if product.description:
        details.append(f"\n{product.description[:200]}")
    
    if 'sw' in language or 'sheng' in language:
        details.append("\nUnataka kuorder?")
    else:
        details.append("\nWould you like to order this?")
    
    return "\n".join(details)


def handle_place_order(
    intent_result: IntentResult,
    context: ConversationContext,
    tenant: Tenant,
    customer: Customer
) -> BotAction:
    """
    Handle order placement and creation.
    NO LLM calls.
    
    Requirements: 6.5, 7.1, 7.2
    """
    # Get product from context
    product_id = context.get_entity('product_id')
    
    if not product_id:
        return BotAction(
            type="TEXT",
            text="Please select a product first. Would you like to browse our products?",
            new_context={
                'current_flow': 'browsing_products',
                'awaiting_response': True,
            }
        )
    
    # Get quantity from slots or context
    quantity = intent_result.slots.get('quantity')
    if not quantity:
        quantity = context.get_entity('quantity', 1)
    
    # Validate product exists and is available (Requirement 7.2)
    try:
        product = Product.objects.get(
            id=product_id,
            tenant=tenant,
            is_active=True,
            deleted_at__isnull=True
        )
    except Product.DoesNotExist:
        return BotAction(
            type="TEXT",
            text="Sorry, that product is no longer available.",
            new_context={
                'current_flow': '',
                'awaiting_response': False,
            }
        )
    
    # Check stock
    if not product.has_stock(quantity):
        available = product.stock if product.stock is not None else 0
        return BotAction(
            type="TEXT",
            text=f"Sorry, we only have {available} units available. Would you like to order that amount?",
            new_context={
                'current_flow': 'checkout',
                'awaiting_response': True,
                'last_question': 'adjust_quantity',
                'entities': {
                    'product_id': str(product.id),
                    'available_quantity': available,
                }
            }
        )
    
    # Calculate totals
    subtotal = product.price * quantity
    shipping = 0  # TODO: Calculate shipping based on tenant settings
    total = subtotal + shipping
    
    # Create order with PENDING_PAYMENT status (Requirement 7.2)
    from apps.orders.models import Order
    
    order = Order.objects.create(
        tenant=tenant,
        customer=customer,
        currency=product.currency,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        status='draft',  # Will be 'placed' after payment
        items=[{
            'product_id': str(product.id),
            'product_name': product.title,
            'quantity': quantity,
            'price': float(product.price),
            'subtotal': float(subtotal),
        }],
        metadata={
            'created_via': 'bot',
            'conversation_id': str(context.conversation.id),
        }
    )
    
    # Format order summary
    text = _format_order_created(order, product, quantity, intent_result.language)
    
    # Ask for payment method (Requirement 7.3)
    return BotAction(
        type="BUTTONS",
        text=text,
        rich_payload={
            'buttons': [
                {'id': 'pay_mpesa', 'title': 'M-Pesa'},
                {'id': 'pay_card', 'title': 'Card Payment'},
                {'id': 'pay_manual', 'title': 'Manual Payment'},
            ]
        },
        new_context={
            'current_flow': 'payment',
            'awaiting_response': True,
            'last_question': 'payment_method',
            'entities': {
                'order_id': str(order.id),
                'total': float(total),
                'currency': product.currency,
            }
        },
        side_effects=['order_created']
    )


def _format_order_summary(product: Product, quantity: int, total: Any, language: list) -> str:
    """Format order summary message."""
    if 'sw' in language or 'sheng' in language:
        return f"""📋 Muhtasari wa Order:

📦 Bidhaa: {product.title}
🔢 Idadi: {quantity}
💰 Jumla: {product.currency} {total}

Unataka kuendelea?"""
    
    return f"""📋 Order Summary:

📦 Product: {product.title}
🔢 Quantity: {quantity}
💰 Total: {product.currency} {total}

Would you like to proceed?"""


def _format_order_created(order: Any, product: Product, quantity: int, language: list) -> str:
    """Format order created message."""
    if 'sw' in language or 'sheng' in language:
        return f"""✅ Order Imetengenezwa!

📋 Order #{order.id}
📦 {product.title} x {quantity}
💰 Jumla: {order.currency} {order.total}

Chagua njia ya malipo:"""
    
    return f"""✅ Order Created!

📋 Order #{order.id}
📦 {product.title} x {quantity}
💰 Total: {order.currency} {order.total}

Choose payment method:"""


# Import Django models at module level
from django.db import models
