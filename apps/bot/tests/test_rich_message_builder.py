"""
Tests for RichMessageBuilder service.

Tests WhatsApp interactive message building including:
- Product cards with images and buttons
- Service cards with images and buttons
- List messages for selections
- Button messages for quick replies
- Media messages with captions
- Validation against WhatsApp API limits
"""
import pytest
from decimal import Decimal
from apps.bot.services.rich_message_builder import (
    RichMessageBuilder,
    WhatsAppMessage,
    WhatsAppMessageLimits,
    RichMessageValidationError
)


@pytest.fixture
def builder():
    """Create a RichMessageBuilder instance."""
    return RichMessageBuilder()


@pytest.fixture
def mock_product():
    """Create a mock product for testing."""
    class MockProduct:
        id = 'prod_123'
        title = 'Test Product'
        description = 'This is a test product description'
        price = Decimal('99.99')
        currency = 'USD'
        is_in_stock = True
        stock = 10
        images = ['https://example.com/product.jpg']
    
    return MockProduct()


@pytest.fixture
def mock_service():
    """Create a mock service for testing."""
    class MockService:
        id = 'svc_123'
        title = 'Test Service'
        description = 'This is a test service description'
        currency = 'USD'
        images = ['https://example.com/service.jpg']
        
        def get_price(self):
            return Decimal('149.99')
    
    return MockService()


@pytest.fixture
def mock_service_variant():
    """Create a mock service variant for testing."""
    class MockVariant:
        id = 'var_123'
        duration_minutes = 60
        
        def get_price(self):
            return Decimal('149.99')
    
    return MockVariant()


class TestWhatsAppMessage:
    """Test WhatsAppMessage data structure."""
    
    def test_basic_text_message(self):
        """Test creating a basic text message."""
        message = WhatsAppMessage(body="Hello, world!")
        
        assert message.body == "Hello, world!"
        assert message.message_type == 'text'
        assert message.media_url is None
        assert message.buttons == []
        assert message.list_data is None
        assert message.metadata == {}
    
    def test_message_with_buttons(self):
        """Test creating a message with buttons."""
        buttons = [
            {'id': 'btn1', 'text': 'Option 1'},
            {'id': 'btn2', 'text': 'Option 2'}
        ]
        message = WhatsAppMessage(
            body="Choose an option",
            message_type='button',
            buttons=buttons
        )
        
        assert message.message_type == 'button'
        assert len(message.buttons) == 2
        assert message.buttons[0]['text'] == 'Option 1'
    
    def test_to_dict(self):
        """Test converting message to dictionary."""
        message = WhatsAppMessage(
            body="Test message",
            message_type='text',
            metadata={'key': 'value'}
        )
        
        result = message.to_dict()
        
        assert result['body'] == "Test message"
        assert result['message_type'] == 'text'
        assert result['metadata'] == {'key': 'value'}
    
    def test_fallback_text_with_buttons(self):
        """Test generating fallback text for button messages."""
        buttons = [
            {'id': 'btn1', 'text': 'Yes'},
            {'id': 'btn2', 'text': 'No'}
        ]
        message = WhatsAppMessage(
            body="Do you agree?",
            buttons=buttons
        )
        
        fallback = message.get_fallback_text()
        
        assert "Do you agree?" in fallback
        assert "Options:" in fallback
        assert "1. Yes" in fallback
        assert "2. No" in fallback
    
    def test_fallback_text_with_list(self):
        """Test generating fallback text for list messages."""
        list_data = {
            'sections': [
                {
                    'title': 'Products',
                    'rows': [
                        {'id': '1', 'title': 'Product 1', 'description': 'Desc 1'},
                        {'id': '2', 'title': 'Product 2', 'description': 'Desc 2'}
                    ]
                }
            ]
        }
        message = WhatsAppMessage(
            body="Choose a product",
            list_data=list_data
        )
        
        fallback = message.get_fallback_text()
        
        assert "Choose a product" in fallback
        assert "Products:" in fallback
        assert "1. Product 1 - Desc 1" in fallback
        assert "2. Product 2 - Desc 2" in fallback


class TestRichMessageBuilder:
    """Test RichMessageBuilder service."""
    
    def test_builder_initialization(self, builder):
        """Test builder initializes with limits."""
        assert builder.limits is not None
        assert isinstance(builder.limits, WhatsAppMessageLimits)
    
    def test_build_product_card(self, builder, mock_product):
        """Test building a product card."""
        message = builder.build_product_card(mock_product)
        
        assert isinstance(message, WhatsAppMessage)
        assert 'Test Product' in message.body
        assert '$99.99' in message.body
        assert 'In Stock: 10 available' in message.body
        assert message.media_url == 'https://example.com/product.jpg'
        assert len(message.buttons) > 0
        assert message.metadata['product_id'] == 'prod_123'
    
    def test_build_product_card_custom_actions(self, builder, mock_product):
        """Test building product card with custom actions."""
        message = builder.build_product_card(
            mock_product,
            actions=['buy', 'add_to_cart']
        )
        
        assert len(message.buttons) == 2
        assert any('Buy Now' in btn['text'] for btn in message.buttons)
        assert any('Add to Cart' in btn['text'] for btn in message.buttons)
    
    def test_build_product_card_out_of_stock(self, builder, mock_product):
        """Test building product card for out of stock item."""
        mock_product.is_in_stock = False
        message = builder.build_product_card(mock_product)
        
        assert '❌ Out of Stock' in message.body
    
    def test_build_service_card(self, builder, mock_service):
        """Test building a service card."""
        message = builder.build_service_card(mock_service)
        
        assert isinstance(message, WhatsAppMessage)
        assert 'Test Service' in message.body
        assert '$149.99' in message.body
        assert message.media_url == 'https://example.com/service.jpg'
        assert len(message.buttons) > 0
        assert message.metadata['service_id'] == 'svc_123'
    
    def test_build_service_card_with_variant(self, builder, mock_service, mock_service_variant):
        """Test building service card with variant."""
        message = builder.build_service_card(
            mock_service,
            variant=mock_service_variant
        )
        
        assert '60 minutes' in message.body
        assert message.metadata['variant_id'] == 'var_123'
    
    def test_build_list_message(self, builder):
        """Test building a list message."""
        items = [
            {'id': 'item1', 'title': 'Item 1', 'description': 'Description 1'},
            {'id': 'item2', 'title': 'Item 2', 'description': 'Description 2'},
            {'id': 'item3', 'title': 'Item 3', 'description': 'Description 3'}
        ]
        
        message = builder.build_list_message(
            title='Choose an item',
            items=items,
            button_text='Select'
        )
        
        assert isinstance(message, WhatsAppMessage)
        assert message.message_type == 'list'
        assert message.list_data['title'] == 'Choose an item'
        assert message.list_data['button_text'] == 'Select'
        assert len(message.list_data['sections']) > 0
        assert message.metadata['item_count'] == 3
    
    def test_build_button_message(self, builder):
        """Test building a button message."""
        buttons = [
            {'id': 'yes', 'text': 'Yes'},
            {'id': 'no', 'text': 'No'}
        ]
        
        message = builder.build_button_message(
            text='Do you want to proceed?',
            buttons=buttons
        )
        
        assert isinstance(message, WhatsAppMessage)
        assert message.message_type == 'button'
        assert 'Do you want to proceed?' in message.body
        assert len(message.buttons) == 2
        assert message.metadata['button_count'] == 2
    
    def test_build_button_message_with_header_footer(self, builder):
        """Test building button message with header and footer."""
        buttons = [{'id': 'ok', 'text': 'OK'}]
        
        message = builder.build_button_message(
            text='Main message',
            buttons=buttons,
            header='Important',
            footer='Thank you'
        )
        
        assert '*Important*' in message.body
        assert 'Main message' in message.body
        assert '_Thank you_' in message.body
    
    def test_build_media_message(self, builder):
        """Test building a media message."""
        message = builder.build_media_message(
            media_url='https://example.com/image.jpg',
            caption='Check this out!',
            media_type='image'
        )
        
        assert isinstance(message, WhatsAppMessage)
        assert message.message_type == 'media'
        assert message.media_url == 'https://example.com/image.jpg'
        assert message.body == 'Check this out!'
        assert message.metadata['media_type'] == 'image'
    
    def test_build_media_message_with_buttons(self, builder):
        """Test building media message with buttons."""
        buttons = [{'id': 'buy', 'text': 'Buy Now'}]
        
        message = builder.build_media_message(
            media_url='https://example.com/image.jpg',
            caption='Product image',
            buttons=buttons
        )
        
        assert len(message.buttons) == 1
        assert message.metadata['has_buttons'] is True
    
    def test_format_price_usd(self, builder):
        """Test price formatting for USD."""
        formatted = builder._format_price(Decimal('99.99'), 'USD')
        assert formatted == '$99.99'
    
    def test_format_price_kes(self, builder):
        """Test price formatting for KES."""
        formatted = builder._format_price(Decimal('1000.00'), 'KES')
        assert formatted == 'KSh1,000.00'
    
    def test_format_price_unknown_currency(self, builder):
        """Test price formatting for unknown currency."""
        formatted = builder._format_price(Decimal('50.00'), 'XYZ')
        assert formatted == 'XYZ50.00'


class TestValidation:
    """Test message validation against WhatsApp limits."""
    
    def test_validate_button_count_limit(self, builder):
        """Test validation fails with too many buttons."""
        buttons = [
            {'id': f'btn{i}', 'text': f'Button {i}'}
            for i in range(5)  # More than MAX_BUTTONS (3)
        ]
        
        with pytest.raises(RichMessageValidationError) as exc_info:
            builder.build_button_message('Choose', buttons)
        
        assert 'maximum is 3' in str(exc_info.value)
    
    def test_validate_button_text_length(self, builder):
        """Test validation fails with button text too long."""
        buttons = [
            {'id': 'btn1', 'text': 'X' * 25}  # Exceeds MAX_BUTTON_TEXT_LENGTH (20)
        ]
        
        with pytest.raises(RichMessageValidationError) as exc_info:
            builder.build_button_message('Choose', buttons)
        
        assert 'Button text' in str(exc_info.value)
        assert 'exceeds' in str(exc_info.value)
    
    def test_validate_list_title_length(self, builder):
        """Test validation fails with list title too long."""
        items = [{'id': '1', 'title': 'Item 1'}]
        
        with pytest.raises(RichMessageValidationError) as exc_info:
            builder.build_list_message(
                title='X' * 30,  # Exceeds MAX_LIST_TITLE_LENGTH (24)
                items=items
            )
        
        assert 'List title exceeds' in str(exc_info.value)
    
    def test_validate_caption_length(self, builder):
        """Test validation fails with caption too long."""
        with pytest.raises(RichMessageValidationError) as exc_info:
            builder.build_media_message(
                media_url='https://example.com/image.jpg',
                caption='X' * 1100  # Exceeds MAX_CAPTION_LENGTH (1024)
            )
        
        assert 'Caption exceeds' in str(exc_info.value)
    
    def test_validate_message_method(self, builder):
        """Test validate_message method."""
        message = WhatsAppMessage(body="Valid message")
        
        # Should not raise exception
        assert builder.validate_message(message) is True
    
    def test_validate_message_fails_on_long_body(self, builder):
        """Test validate_message fails on body too long."""
        message = WhatsAppMessage(body='X' * 1100)  # Exceeds MAX_BODY_LENGTH
        
        with pytest.raises(RichMessageValidationError) as exc_info:
            builder.validate_message(message)
        
        assert 'Message body exceeds' in str(exc_info.value)
    
    def test_list_sections_auto_split(self, builder):
        """Test list items are automatically split into sections."""
        # Create more items than MAX_LIST_ITEMS_PER_SECTION (10)
        items = [
            {'id': f'item{i}', 'title': f'Item {i}', 'description': f'Desc {i}'}
            for i in range(15)
        ]
        
        message = builder.build_list_message('Choose', items)
        
        # Should create 2 sections
        assert len(message.list_data['sections']) == 2
        assert len(message.list_data['sections'][0]['rows']) == 10
        assert len(message.list_data['sections'][1]['rows']) == 5


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_product_without_image(self, builder, mock_product):
        """Test building product card without image."""
        mock_product.images = []
        message = builder.build_product_card(mock_product)
        
        assert message.media_url is None
        assert message.message_type in ['button', 'text']
    
    def test_product_without_stock_info(self, builder, mock_product):
        """Test building product card without stock information."""
        mock_product.stock = None
        message = builder.build_product_card(mock_product, include_stock=True)
        
        assert '✅ In Stock' in message.body
    
    def test_service_without_price(self, builder, mock_service):
        """Test building service card without price."""
        mock_service.get_price = lambda: None
        message = builder.build_service_card(mock_service)
        
        # Should not crash, just omit price
        assert isinstance(message, WhatsAppMessage)
    
    def test_list_items_missing_fields(self, builder):
        """Test list building with items missing required fields."""
        items = [
            {'id': 'item1', 'title': 'Item 1'},
            {'title': 'Item 2'},  # Missing 'id'
            {'id': 'item3'}  # Missing 'title'
        ]
        
        message = builder.build_list_message('Choose', items)
        
        # Should only include valid items
        total_items = sum(len(s['rows']) for s in message.list_data['sections'])
        assert total_items == 1  # Only item1 is valid
    
    def test_long_product_description_truncation(self, builder, mock_product):
        """Test long product descriptions are truncated."""
        mock_product.description = 'X' * 2000  # Very long description
        
        message = builder.build_product_card(mock_product)
        
        # Should not exceed body limit
        assert len(message.body) <= WhatsAppMessageLimits.MAX_BODY_LENGTH
        assert '...' in message.body  # Truncation indicator
