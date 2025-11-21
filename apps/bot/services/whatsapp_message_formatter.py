"""
WhatsApp Message Formatter for the sales orchestration refactor.

This service converts BotAction objects into WhatsApp-compatible messages.

Design principles:
- Format messages in detected language
- Build rich WhatsApp messages (lists, buttons, cards)
- Fallback to plain text when rich messages fail
- Keep messages short and focused
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class WhatsAppMessageFormatter:
    """
    Format BotAction objects into WhatsApp messages.
    
    Responsibilities:
    - Convert BotAction to Twilio-compatible message payloads
    - Build WhatsApp list messages for products/services
    - Build WhatsApp button messages for confirmations
    - Build payment messages with order summaries
    - Fallback to plain text when rich messages fail
    - Format messages in detected language
    """
    
    # WhatsApp limits
    MAX_LIST_ITEMS = 10
    MAX_BUTTONS = 3
    MAX_BODY_LENGTH = 1024
    
    def format_action(
        self,
        action,  # BotAction
        language: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Convert BotAction to Twilio-compatible messages.
        
        Args:
            action: BotAction object from handler
            language: Detected language(s) ['en'], ['sw'], ['sheng']
            
        Returns:
            List of message payloads to send via Twilio
        """
        messages = []
        
        try:
            if action.type == "TEXT":
                # Simple text message
                messages.append({
                    'body': action.text,
                    'type': 'text'
                })
            
            elif action.type == "LIST":
                # WhatsApp list message
                list_message = self._build_list_from_action(action, language)
                messages.append(list_message)
            
            elif action.type == "BUTTONS":
                # WhatsApp button message
                button_message = self._build_buttons_from_action(action, language)
                messages.append(button_message)
            
            elif action.type == "PRODUCT_CARDS":
                # Product list message
                if action.rich_payload and 'products' in action.rich_payload:
                    product_message = self.build_product_list(
                        action.rich_payload['products'],
                        language
                    )
                    messages.append(product_message)
                else:
                    # Fallback to text
                    messages.append({
                        'body': action.text or "Here are our products",
                        'type': 'text'
                    })
            
            elif action.type == "HANDOFF":
                # Human handoff message
                messages.append({
                    'body': action.text or self._get_handoff_message(language),
                    'type': 'text'
                })
            
            else:
                # Unknown type, fallback to text
                messages.append({
                    'body': action.text or "I'm here to help!",
                    'type': 'text'
                })
        
        except Exception as e:
            logger.error(f"Error formatting action: {e}")
            # Fallback to plain text
            messages.append({
                'body': action.text or "I'm here to help!",
                'type': 'text'
            })
        
        return messages
    
    def build_product_list(
        self,
        products: List[Dict[str, Any]],
        language: List[str]
    ) -> Dict[str, Any]:
        """
        Build WhatsApp list message for products.
        
        Args:
            products: List of product dicts with id, name, price, etc.
            language: Detected language(s)
            
        Returns:
            Dict with WhatsApp list message structure
        """
        # Limit to 10 products
        products = products[:self.MAX_LIST_ITEMS]
        
        # Build list items
        items = []
        for i, product in enumerate(products):
            item = {
                'id': f"product_{product.get('id', i)}",
                'title': product.get('name', 'Product')[:24],  # Max 24 chars
                'description': self._format_product_description(product, language)[:72]  # Max 72 chars
            }
            items.append(item)
        
        # Build message
        header_text = self._get_text('products_header', language)
        body_text = self._get_text('products_body', language)
        button_text = self._get_text('view_products', language)
        
        return {
            'type': 'list',
            'body': body_text,
            'header': header_text,
            'button_text': button_text,
            'sections': [
                {
                    'title': self._get_text('our_products', language),
                    'rows': items
                }
            ]
        }
    
    def build_button_message(
        self,
        text: str,
        buttons: List[Dict[str, str]],
        language: List[str]
    ) -> Dict[str, Any]:
        """
        Build WhatsApp button message.
        
        Args:
            text: Message text
            buttons: List of button dicts with 'id' and 'title' keys
            language: Detected language(s)
            
        Returns:
            Dict with WhatsApp button message structure
        """
        # Limit to 3 buttons
        buttons = buttons[:self.MAX_BUTTONS]
        
        # Format buttons
        formatted_buttons = []
        for button in buttons:
            formatted_buttons.append({
                'id': button.get('id', 'btn'),
                'title': button.get('title', 'Option')[:20]  # Max 20 chars
            })
        
        return {
            'type': 'buttons',
            'body': text[:self.MAX_BODY_LENGTH],
            'buttons': formatted_buttons
        }
    
    def build_payment_message(
        self,
        order_summary: Dict[str, Any],
        payment_link: Optional[str],
        language: List[str]
    ) -> Dict[str, Any]:
        """
        Build message with order summary and payment link.
        
        Args:
            order_summary: Dict with order details (items, total, etc.)
            payment_link: Optional payment link URL
            language: Detected language(s)
            
        Returns:
            Dict with message structure
        """
        # Build order summary text
        text = self._get_text('order_summary', language) + "\n\n"
        
        # Add items
        for item in order_summary.get('items', []):
            text += f"• {item.get('name')} x{item.get('quantity', 1)}\n"
            text += f"  {self._format_price(item.get('price', 0), order_summary.get('currency', 'KES'))}\n"
        
        # Add total
        text += f"\n{self._get_text('total', language)}: "
        text += self._format_price(
            order_summary.get('total', 0),
            order_summary.get('currency', 'KES')
        )
        
        # Add payment link if provided
        if payment_link:
            text += f"\n\n{self._get_text('payment_link', language)}:\n{payment_link}"
        
        return {
            'type': 'text',
            'body': text[:self.MAX_BODY_LENGTH]
        }
    
    def _build_list_from_action(
        self,
        action,
        language: List[str]
    ) -> Dict[str, Any]:
        """Build list message from BotAction."""
        if not action.rich_payload:
            # Fallback to text
            return {
                'type': 'text',
                'body': action.text or "Here are your options"
            }
        
        items = action.rich_payload.get('items', [])
        if not items:
            return {
                'type': 'text',
                'body': action.text or "No options available"
            }
        
        # Build list
        return {
            'type': 'list',
            'body': action.text or "Select an option",
            'button_text': action.rich_payload.get('button_text', 'View Options'),
            'sections': [
                {
                    'title': action.rich_payload.get('section_title', 'Options'),
                    'rows': items[:self.MAX_LIST_ITEMS]
                }
            ]
        }
    
    def _build_buttons_from_action(
        self,
        action,
        language: List[str]
    ) -> Dict[str, Any]:
        """Build button message from BotAction."""
        if not action.rich_payload or 'buttons' not in action.rich_payload:
            # Fallback to text
            return {
                'type': 'text',
                'body': action.text or "Please respond"
            }
        
        buttons = action.rich_payload['buttons']
        return self.build_button_message(
            action.text or "Choose an option",
            buttons,
            language
        )
    
    def _format_product_description(
        self,
        product: Dict[str, Any],
        language: List[str]
    ) -> str:
        """Format product description for list item."""
        price = self._format_price(
            product.get('price', 0),
            product.get('currency', 'KES')
        )
        
        description = f"{price}"
        
        if product.get('category'):
            description += f" • {product['category']}"
        
        return description
    
    def _format_price(self, amount: float, currency: str = 'KES') -> str:
        """Format price with currency."""
        if currency == 'KES':
            return f"KES {amount:,.0f}"
        elif currency == 'USD':
            return f"${amount:,.2f}"
        else:
            return f"{currency} {amount:,.2f}"
    
    def _get_text(self, key: str, language: List[str]) -> str:
        """Get translated text for a key."""
        # Simple translation dictionary
        translations = {
            'en': {
                'products_header': 'Our Products',
                'products_body': 'Select a product to view details',
                'view_products': 'View Products',
                'our_products': 'Products',
                'order_summary': 'Order Summary',
                'total': 'Total',
                'payment_link': 'Pay here',
            },
            'sw': {
                'products_header': 'Bidhaa Zetu',
                'products_body': 'Chagua bidhaa kuona maelezo',
                'view_products': 'Tazama Bidhaa',
                'our_products': 'Bidhaa',
                'order_summary': 'Muhtasari wa Agizo',
                'total': 'Jumla',
                'payment_link': 'Lipa hapa',
            },
            'sheng': {
                'products_header': 'Vitu Zetu',
                'products_body': 'Chagua kitu uone details',
                'view_products': 'Cheki Vitu',
                'our_products': 'Vitu',
                'order_summary': 'Summary ya Order',
                'total': 'Total',
                'payment_link': 'Lipa hapa',
            }
        }
        
        # Determine language
        lang = 'en'  # Default
        if 'sw' in language:
            lang = 'sw'
        elif 'sheng' in language:
            lang = 'sheng'
        
        return translations.get(lang, {}).get(key, translations['en'].get(key, key))
    
    def _get_handoff_message(self, language: List[str]) -> str:
        """Get human handoff message in appropriate language."""
        messages = {
            'en': "Let me connect you with someone from our team who can help you better.",
            'sw': "Wacha nikuunganishe na mtu kutoka kwa timu yetu atakayeweza kukusaidia vizuri zaidi.",
            'sheng': "Wacha nikuconnect na mse wa team yetu atakusaidia poa."
        }
        
        lang = 'en'
        if 'sw' in language:
            lang = 'sw'
        elif 'sheng' in language:
            lang = 'sheng'
        
        return messages.get(lang, messages['en'])


__all__ = ['WhatsAppMessageFormatter']
