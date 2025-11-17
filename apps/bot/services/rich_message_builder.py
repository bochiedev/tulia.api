"""
Rich message builder for WhatsApp interactive messages.

Provides methods for building WhatsApp interactive messages including:
- Product cards with images and buttons
- Service cards with images and buttons
- List messages for selections
- Button messages for quick replies
- Media messages with captions

All messages are validated against WhatsApp API limits.
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class WhatsAppMessageLimits:
    """WhatsApp API message limits and constraints."""
    
    # Button message limits
    MAX_BUTTONS = 3
    MAX_BUTTON_TEXT_LENGTH = 20
    MAX_BUTTON_ID_LENGTH = 256
    
    # List message limits
    MAX_LIST_SECTIONS = 10
    MAX_LIST_ITEMS_PER_SECTION = 10
    MAX_LIST_TITLE_LENGTH = 24
    MAX_LIST_DESCRIPTION_LENGTH = 72
    MAX_LIST_BUTTON_TEXT_LENGTH = 20
    
    # Text limits
    MAX_BODY_LENGTH = 1024
    MAX_HEADER_LENGTH = 60
    MAX_FOOTER_LENGTH = 60
    
    # Media limits
    MAX_CAPTION_LENGTH = 1024


class RichMessageValidationError(Exception):
    """Raised when a rich message fails validation."""
    pass


class WhatsAppMessage:
    """
    Represents a WhatsApp message with optional interactive components.
    
    This is a data structure that can be converted to the format
    required by the Twilio WhatsApp API or other providers.
    """
    
    def __init__(
        self,
        body: str,
        message_type: str = 'text',
        media_url: Optional[str] = None,
        buttons: Optional[List[Dict[str, str]]] = None,
        list_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize WhatsApp message.
        
        Args:
            body: Message text content
            message_type: Type of message ('text', 'button', 'list', 'media')
            media_url: Optional URL for media attachment
            buttons: Optional list of button definitions
            list_data: Optional list message data structure
            metadata: Optional metadata for tracking
        """
        self.body = body
        self.message_type = message_type
        self.media_url = media_url
        self.buttons = buttons or []
        self.list_data = list_data
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        result = {
            'body': self.body,
            'message_type': self.message_type,
        }
        
        if self.media_url:
            result['media_url'] = self.media_url
        
        if self.buttons:
            result['buttons'] = self.buttons
        
        if self.list_data:
            result['list_data'] = self.list_data
        
        if self.metadata:
            result['metadata'] = self.metadata
        
        return result
    
    def get_fallback_text(self) -> str:
        """
        Get plain text fallback for clients that don't support interactive messages.
        
        Returns:
            str: Plain text version of the message
        """
        text = self.body
        
        # Add button options as numbered list
        if self.buttons:
            text += "\n\nOptions:"
            for i, button in enumerate(self.buttons, 1):
                text += f"\n{i}. {button.get('text', '')}"
        
        # Add list items as numbered list
        if self.list_data and self.list_data.get('sections'):
            text += "\n\nOptions:"
            counter = 1
            for section in self.list_data['sections']:
                if section.get('title'):
                    text += f"\n\n{section['title']}:"
                for item in section.get('rows', []):
                    text += f"\n{counter}. {item.get('title', '')}"
                    if item.get('description'):
                        text += f" - {item['description']}"
                    counter += 1
        
        return text


class RichMessageBuilder:
    """
    Service for building WhatsApp interactive messages.
    
    Provides methods to create rich, interactive messages including:
    - Product cards with images and action buttons
    - Service cards with images and action buttons
    - List messages for selections
    - Button messages for quick replies
    
    All messages are validated against WhatsApp API limits.
    """
    
    def __init__(self):
        """Initialize the rich message builder."""
        self.limits = WhatsAppMessageLimits()
    
    def build_product_card(
        self,
        product,
        actions: Optional[List[str]] = None,
        include_stock: bool = True
    ) -> WhatsAppMessage:
        """
        Build a product card with image and action buttons.
        
        Args:
            product: Product model instance
            actions: List of action types ('buy', 'details', 'add_to_cart')
            include_stock: Whether to include stock information
            
        Returns:
            WhatsAppMessage: Rich message with product card
            
        Raises:
            RichMessageValidationError: If message validation fails
            
        Example:
            >>> builder = RichMessageBuilder()
            >>> product = Product.objects.get(id=product_id)
            >>> message = builder.build_product_card(product, actions=['buy', 'details'])
        """
        actions = actions or ['buy', 'details']
        
        # Build message body
        body = f"*{product.title}*\n\n"
        
        if product.description:
            # Truncate description if too long
            max_desc_length = self.limits.MAX_BODY_LENGTH - len(body) - 200
            description = product.description[:max_desc_length]
            if len(product.description) > max_desc_length:
                description += "..."
            body += f"{description}\n\n"
        
        # Add price
        body += f"💰 Price: {self._format_price(product.price, product.currency)}\n"
        
        # Add stock information
        if include_stock:
            if product.is_in_stock:
                if product.stock is not None:
                    body += f"📦 In Stock: {product.stock} available\n"
                else:
                    body += f"✅ In Stock\n"
            else:
                body += f"❌ Out of Stock\n"
        
        # Validate body length
        if len(body) > self.limits.MAX_BODY_LENGTH:
            raise RichMessageValidationError(
                f"Product card body exceeds {self.limits.MAX_BODY_LENGTH} characters"
            )
        
        # Build action buttons
        buttons = self._build_product_buttons(product, actions)
        
        # Get product image
        media_url = None
        if product.images and len(product.images) > 0:
            media_url = product.images[0]
        
        return WhatsAppMessage(
            body=body,
            message_type='button' if buttons else 'media' if media_url else 'text',
            media_url=media_url,
            buttons=buttons,
            metadata={
                'product_id': str(product.id),
                'product_title': product.title,
                'price': str(product.price)
            }
        )
    
    def build_service_card(
        self,
        service,
        actions: Optional[List[str]] = None,
        variant=None
    ) -> WhatsAppMessage:
        """
        Build a service card with image and action buttons.
        
        Args:
            service: Service model instance
            actions: List of action types ('book', 'availability', 'details')
            variant: Optional ServiceVariant instance
            
        Returns:
            WhatsAppMessage: Rich message with service card
            
        Raises:
            RichMessageValidationError: If message validation fails
            
        Example:
            >>> builder = RichMessageBuilder()
            >>> service = Service.objects.get(id=service_id)
            >>> message = builder.build_service_card(service, actions=['book', 'availability'])
        """
        actions = actions or ['book', 'availability']
        
        # Build message body
        body = f"*{service.title}*\n\n"
        
        if service.description:
            # Truncate description if too long
            max_desc_length = self.limits.MAX_BODY_LENGTH - len(body) - 200
            description = service.description[:max_desc_length]
            if len(service.description) > max_desc_length:
                description += "..."
            body += f"{description}\n\n"
        
        # Add variant information if provided
        if variant:
            body += f"⏱️ Duration: {variant.duration_minutes} minutes\n"
            price = variant.get_price()
        else:
            price = service.get_price()
        
        # Add price
        if price:
            body += f"💰 Price: {self._format_price(price, service.currency)}\n"
        
        # Validate body length
        if len(body) > self.limits.MAX_BODY_LENGTH:
            raise RichMessageValidationError(
                f"Service card body exceeds {self.limits.MAX_BODY_LENGTH} characters"
            )
        
        # Build action buttons
        buttons = self._build_service_buttons(service, actions, variant)
        
        # Get service image
        media_url = None
        if service.images and len(service.images) > 0:
            media_url = service.images[0]
        
        return WhatsAppMessage(
            body=body,
            message_type='button' if buttons else 'media' if media_url else 'text',
            media_url=media_url,
            buttons=buttons,
            metadata={
                'service_id': str(service.id),
                'service_title': service.title,
                'variant_id': str(variant.id) if variant else None,
                'price': str(price) if price else None
            }
        )
    
    def build_list_message(
        self,
        title: str,
        items: List[Dict[str, Any]],
        button_text: str = "Select",
        sections: Optional[List[Dict[str, Any]]] = None,
        body: Optional[str] = None
    ) -> WhatsAppMessage:
        """
        Build an interactive list message for selections.
        
        Args:
            title: List message title
            items: List of items (each with 'id', 'title', 'description')
            button_text: Text for the list button
            sections: Optional pre-built sections structure
            body: Optional message body text
            
        Returns:
            WhatsAppMessage: Rich message with list
            
        Raises:
            RichMessageValidationError: If message validation fails
            
        Example:
            >>> builder = RichMessageBuilder()
            >>> items = [
            ...     {'id': 'prod_1', 'title': 'Product 1', 'description': 'Description 1'},
            ...     {'id': 'prod_2', 'title': 'Product 2', 'description': 'Description 2'}
            ... ]
            >>> message = builder.build_list_message('Choose a product', items)
        """
        # Validate title length
        if len(title) > self.limits.MAX_LIST_TITLE_LENGTH:
            raise RichMessageValidationError(
                f"List title exceeds {self.limits.MAX_LIST_TITLE_LENGTH} characters"
            )
        
        # Validate button text length
        if len(button_text) > self.limits.MAX_LIST_BUTTON_TEXT_LENGTH:
            raise RichMessageValidationError(
                f"List button text exceeds {self.limits.MAX_LIST_BUTTON_TEXT_LENGTH} characters"
            )
        
        # Build sections if not provided
        if sections is None:
            sections = self._build_list_sections(items)
        
        # Validate sections
        if len(sections) > self.limits.MAX_LIST_SECTIONS:
            raise RichMessageValidationError(
                f"List has {len(sections)} sections, maximum is {self.limits.MAX_LIST_SECTIONS}"
            )
        
        for section in sections:
            rows = section.get('rows', [])
            if len(rows) > self.limits.MAX_LIST_ITEMS_PER_SECTION:
                raise RichMessageValidationError(
                    f"Section has {len(rows)} items, maximum is {self.limits.MAX_LIST_ITEMS_PER_SECTION}"
                )
        
        # Build message body
        if body is None:
            body = f"Please select from the options below:"
        
        # Validate body length
        if len(body) > self.limits.MAX_BODY_LENGTH:
            raise RichMessageValidationError(
                f"List message body exceeds {self.limits.MAX_BODY_LENGTH} characters"
            )
        
        list_data = {
            'title': title,
            'button_text': button_text,
            'sections': sections
        }
        
        return WhatsAppMessage(
            body=body,
            message_type='list',
            list_data=list_data,
            metadata={
                'list_title': title,
                'item_count': sum(len(s.get('rows', [])) for s in sections)
            }
        )
    
    def build_button_message(
        self,
        text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None
    ) -> WhatsAppMessage:
        """
        Build a message with quick reply buttons.
        
        Args:
            text: Message body text
            buttons: List of button definitions (each with 'id' and 'text')
            header: Optional header text
            footer: Optional footer text
            
        Returns:
            WhatsAppMessage: Rich message with buttons
            
        Raises:
            RichMessageValidationError: If message validation fails
            
        Example:
            >>> builder = RichMessageBuilder()
            >>> buttons = [
            ...     {'id': 'yes', 'text': 'Yes'},
            ...     {'id': 'no', 'text': 'No'}
            ... ]
            >>> message = builder.build_button_message('Do you want to proceed?', buttons)
        """
        # Validate button count
        if len(buttons) > self.limits.MAX_BUTTONS:
            raise RichMessageValidationError(
                f"Message has {len(buttons)} buttons, maximum is {self.limits.MAX_BUTTONS}"
            )
        
        # Validate button text lengths
        for button in buttons:
            button_text = button.get('text', '')
            if len(button_text) > self.limits.MAX_BUTTON_TEXT_LENGTH:
                raise RichMessageValidationError(
                    f"Button text '{button_text}' exceeds {self.limits.MAX_BUTTON_TEXT_LENGTH} characters"
                )
            
            button_id = button.get('id', '')
            if len(button_id) > self.limits.MAX_BUTTON_ID_LENGTH:
                raise RichMessageValidationError(
                    f"Button ID exceeds {self.limits.MAX_BUTTON_ID_LENGTH} characters"
                )
        
        # Build full message body
        full_body = ""
        
        if header:
            if len(header) > self.limits.MAX_HEADER_LENGTH:
                raise RichMessageValidationError(
                    f"Header exceeds {self.limits.MAX_HEADER_LENGTH} characters"
                )
            full_body += f"*{header}*\n\n"
        
        full_body += text
        
        if footer:
            if len(footer) > self.limits.MAX_FOOTER_LENGTH:
                raise RichMessageValidationError(
                    f"Footer exceeds {self.limits.MAX_FOOTER_LENGTH} characters"
                )
            full_body += f"\n\n_{footer}_"
        
        # Validate total body length
        if len(full_body) > self.limits.MAX_BODY_LENGTH:
            raise RichMessageValidationError(
                f"Button message body exceeds {self.limits.MAX_BODY_LENGTH} characters"
            )
        
        return WhatsAppMessage(
            body=full_body,
            message_type='button',
            buttons=buttons,
            metadata={
                'button_count': len(buttons)
            }
        )
    
    def build_media_message(
        self,
        media_url: str,
        caption: str,
        media_type: str = 'image',
        buttons: Optional[List[Dict[str, str]]] = None
    ) -> WhatsAppMessage:
        """
        Build a media message with optional caption and buttons.
        
        Args:
            media_url: URL of the media file
            caption: Caption text for the media
            media_type: Type of media ('image', 'video', 'document')
            buttons: Optional action buttons
            
        Returns:
            WhatsAppMessage: Rich message with media
            
        Raises:
            RichMessageValidationError: If message validation fails
            
        Example:
            >>> builder = RichMessageBuilder()
            >>> message = builder.build_media_message(
            ...     'https://example.com/image.jpg',
            ...     'Check out this product!',
            ...     buttons=[{'id': 'buy', 'text': 'Buy Now'}]
            ... )
        """
        # Validate caption length
        if len(caption) > self.limits.MAX_CAPTION_LENGTH:
            raise RichMessageValidationError(
                f"Caption exceeds {self.limits.MAX_CAPTION_LENGTH} characters"
            )
        
        # Validate buttons if provided
        if buttons:
            if len(buttons) > self.limits.MAX_BUTTONS:
                raise RichMessageValidationError(
                    f"Message has {len(buttons)} buttons, maximum is {self.limits.MAX_BUTTONS}"
                )
            
            for button in buttons:
                button_text = button.get('text', '')
                if len(button_text) > self.limits.MAX_BUTTON_TEXT_LENGTH:
                    raise RichMessageValidationError(
                        f"Button text exceeds {self.limits.MAX_BUTTON_TEXT_LENGTH} characters"
                    )
        
        return WhatsAppMessage(
            body=caption,
            message_type='media',
            media_url=media_url,
            buttons=buttons,
            metadata={
                'media_type': media_type,
                'has_buttons': bool(buttons)
            }
        )
    
    # Helper methods
    
    def _format_price(self, price: Decimal, currency: str) -> str:
        """
        Format price with currency symbol.
        
        Args:
            price: Price amount
            currency: Currency code
            
        Returns:
            str: Formatted price string
        """
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'KES': 'KSh',
            'UGX': 'USh',
            'TZS': 'TSh',
            'NGN': '₦',
            'ZAR': 'R'
        }
        
        symbol = currency_symbols.get(currency, currency)
        return f"{symbol}{price:,.2f}"
    
    def _build_product_buttons(
        self,
        product,
        actions: List[str]
    ) -> List[Dict[str, str]]:
        """
        Build action buttons for product card.
        
        Args:
            product: Product instance
            actions: List of action types
            
        Returns:
            List of button definitions
        """
        buttons = []
        
        action_map = {
            'buy': {'id': f'buy_product_{product.id}', 'text': '🛒 Buy Now'},
            'details': {'id': f'product_details_{product.id}', 'text': 'ℹ️ More Details'},
            'add_to_cart': {'id': f'add_to_cart_{product.id}', 'text': '➕ Add to Cart'}
        }
        
        for action in actions:
            if action in action_map and len(buttons) < self.limits.MAX_BUTTONS:
                buttons.append(action_map[action])
        
        return buttons
    
    def _build_service_buttons(
        self,
        service,
        actions: List[str],
        variant=None
    ) -> List[Dict[str, str]]:
        """
        Build action buttons for service card.
        
        Args:
            service: Service instance
            actions: List of action types
            variant: Optional variant instance
            
        Returns:
            List of button definitions
        """
        buttons = []
        
        variant_id = variant.id if variant else 'default'
        
        action_map = {
            'book': {'id': f'book_service_{service.id}_{variant_id}', 'text': '📅 Book Now'},
            'availability': {'id': f'check_availability_{service.id}', 'text': '🕐 Check Times'},
            'details': {'id': f'service_details_{service.id}', 'text': 'ℹ️ More Details'}
        }
        
        for action in actions:
            if action in action_map and len(buttons) < self.limits.MAX_BUTTONS:
                buttons.append(action_map[action])
        
        return buttons
    
    def _build_list_sections(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build list sections from items.
        
        Args:
            items: List of items with 'id', 'title', 'description'
            
        Returns:
            List of section definitions
        """
        # Group items into sections if there are many
        max_items_per_section = self.limits.MAX_LIST_ITEMS_PER_SECTION
        
        sections = []
        current_section_items = []
        
        for item in items:
            # Validate item structure
            if 'id' not in item or 'title' not in item:
                logger.warning(f"List item missing required fields: {item}")
                continue
            
            # Truncate title and description if needed
            title = item['title'][:self.limits.MAX_LIST_TITLE_LENGTH]
            description = item.get('description', '')[:self.limits.MAX_LIST_DESCRIPTION_LENGTH]
            
            current_section_items.append({
                'id': str(item['id']),
                'title': title,
                'description': description
            })
            
            # Create new section if current one is full
            if len(current_section_items) >= max_items_per_section:
                sections.append({
                    'title': f"Options {len(sections) + 1}",
                    'rows': current_section_items
                })
                current_section_items = []
        
        # Add remaining items
        if current_section_items:
            sections.append({
                'title': f"Options {len(sections) + 1}" if sections else "Options",
                'rows': current_section_items
            })
        
        return sections
    
    def validate_message(self, message: WhatsAppMessage) -> bool:
        """
        Validate a WhatsApp message against API limits.
        
        Args:
            message: WhatsAppMessage instance to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            RichMessageValidationError: If validation fails
        """
        # Validate body length
        if len(message.body) > self.limits.MAX_BODY_LENGTH:
            raise RichMessageValidationError(
                f"Message body exceeds {self.limits.MAX_BODY_LENGTH} characters"
            )
        
        # Validate buttons
        if message.buttons:
            if len(message.buttons) > self.limits.MAX_BUTTONS:
                raise RichMessageValidationError(
                    f"Message has {len(message.buttons)} buttons, maximum is {self.limits.MAX_BUTTONS}"
                )
            
            for button in message.buttons:
                if len(button.get('text', '')) > self.limits.MAX_BUTTON_TEXT_LENGTH:
                    raise RichMessageValidationError(
                        f"Button text exceeds {self.limits.MAX_BUTTON_TEXT_LENGTH} characters"
                    )
        
        # Validate list data
        if message.list_data:
            sections = message.list_data.get('sections', [])
            if len(sections) > self.limits.MAX_LIST_SECTIONS:
                raise RichMessageValidationError(
                    f"List has {len(sections)} sections, maximum is {self.limits.MAX_LIST_SECTIONS}"
                )
            
            for section in sections:
                rows = section.get('rows', [])
                if len(rows) > self.limits.MAX_LIST_ITEMS_PER_SECTION:
                    raise RichMessageValidationError(
                        f"Section has {len(rows)} items, maximum is {self.limits.MAX_LIST_ITEMS_PER_SECTION}"
                    )
        
        return True
