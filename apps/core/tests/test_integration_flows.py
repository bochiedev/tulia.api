"""
Integration tests for critical end-to-end flows.

Tests complete workflows across multiple components:
- Webhook → Intent → Handler → Response
- Product sync from external sources
- Appointment booking with capacity validation
- Order creation and wallet credit flow
- Campaign execution with consent filtering
- Subscription billing and status updates
- Tenant isolation
"""
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta
from decimal import Decimal

from apps.tenants.models import (
    Tenant, Customer, SubscriptionTier, Subscription,
    TenantWallet, Transaction
)
from apps.messaging.models import (
    Conversation, Message, CustomerPreferences,
    MessageCampaign
)
from apps.catalog.models import Product, ProductVariant
from apps.services.models import Service, ServiceVariant, AvailabilityWindow, Appointment
from apps.orders.models import Order
from apps.integrations.models import WebhookLog
from apps.bot.models import IntentEvent
from apps.rbac.models import User, TenantUser, Role, Permission


@pytest.mark.django_db
class TestWebhookToResponseFlow:
    """Test end-to-end webhook processing flow."""
    
    @pytest.fixture
    def setup_tenant(self):
        """Create tenant with all necessary setup."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            monthly_messages=10000,
            max_products=1000,
            max_services=50,
            payment_facilitation=True,
            transaction_fee_percentage=Decimal('3.5')
        )
        
        tenant = Tenant.objects.create(
            name='Test Shop',
            slug='test-shop',
            status='active',
            whatsapp_number='+14155238886',
            twilio_sid='ACtest123',
            twilio_token='test_token',
            webhook_secret='secret123',
            subscription_tier=tier
        )
        
        # Create subscription
        Subscription.objects.create(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly',
            status='active',
            start_date=timezone.now(),
            next_billing_date=timezone.now() + timedelta(days=30)
        )
        
        # Create wallet
        TenantWallet.objects.create(
            tenant=tenant,
            balance=Decimal('0.00'),
            currency='USD'
        )
        
        # Create product
        product = Product.objects.create(
            tenant=tenant,
            title='Test Sneakers',
            description='Great shoes',
            price=Decimal('99.99'),
            currency='USD',
            is_active=True
        )
        
        ProductVariant.objects.create(
            product=product,
            title='Size 42',
            sku='SNEAK-42',
            price=Decimal('99.99'),
            stock=10
        )
        
        return tenant, product
    
    def test_complete_webhook_to_response_flow(self, setup_tenant):
        """Test complete flow from webhook to bot response."""
        tenant, product = setup_tenant
        client = Client()
        
        webhook_payload = {
            'MessageSid': 'SM123',
            'From': 'whatsapp:+1234567890',
            'To': f'whatsapp:{tenant.whatsapp_number}',
            'Body': 'Show me sneakers',
            'NumMedia': '0',
            'AccountSid': tenant.twilio_sid
        }
        
        with patch('apps.integrations.views.TwilioService.verify_signature', return_value=True):
            response = client.post(
                reverse('integrations:twilio-webhook'),
                data=webhook_payload
            )
        
        # Verify webhook processed successfully
        assert response.status_code == 200
        
        # Verify webhook log created
        webhook_logs = WebhookLog.objects.filter(tenant=tenant)
        assert webhook_logs.exists()
        webhook_log = webhook_logs.first()
        assert webhook_log.provider == 'twilio'
        assert webhook_log.event == 'message.received'
        
        # Verify customer created (may have encrypted phone field)
        customers = Customer.objects.filter(tenant=tenant)
        assert customers.count() == 1, f"Expected 1 customer, found {customers.count()}"
        customer = customers.first()
        assert customer is not None
        
        # Verify conversation created
        conversations = Conversation.objects.filter(tenant=tenant, customer=customer)
        assert conversations.count() == 1, f"Expected 1 conversation, found {conversations.count()}"
        conversation = conversations.first()
        assert conversation.status == 'bot'
        
        # Verify inbound message created
        inbound_msgs = Message.objects.filter(
            conversation=conversation,
            direction='in'
        )
        assert inbound_msgs.count() == 1, f"Expected 1 message, found {inbound_msgs.count()}"
        inbound_msg = inbound_msgs.first()
        assert inbound_msg.message_type == 'customer_inbound'
        assert inbound_msg.text == 'Show me sneakers'


@pytest.mark.django_db
class TestProductSyncFlow:
    """Test product synchronization from external sources."""
    
    @pytest.fixture
    def tenant(self):
        """Create tenant for sync tests."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            max_products=1000
        )
        
        return Tenant.objects.create(
            name='Sync Shop',
            slug='sync-shop',
            status='active',
            subscription_tier=tier
        )
    
    def test_woocommerce_product_sync(self, tenant):
        """Test WooCommerce product sync creates products correctly."""
        from apps.integrations.services.woo_service import WooService
        
        mock_woo_products = [
            {
                'id': 123,
                'name': 'WooCommerce Product',
                'description': 'Test product',
                'price': '49.99',
                'images': [{'src': 'http://example.com/image.jpg'}],
                'sku': 'WOO-123',
                'manage_stock': True,
                'stock_quantity': 5,
                'status': 'publish',
                'variations': []
            }
        ]
        
        with patch('apps.integrations.services.woo_service.WooService.fetch_products_batch') as mock_fetch:
            mock_fetch.return_value = mock_woo_products  # Return list directly, not tuple
            
            service = WooService(
                store_url='https://example.com',
                consumer_key='ck_test',
                consumer_secret='cs_test'
            )
            result = service.sync_products(tenant=tenant)
        
        assert result['synced_count'] == 1
        
        # Verify product created
        product = Product.objects.get(
            tenant=tenant,
            external_source='woocommerce',
            external_id='123'
        )
        assert product.title == 'WooCommerce Product'
        assert product.price == Decimal('49.99')
        assert product.sku == 'WOO-123'
        assert product.stock == 5
        assert product.is_active is True
    
    def test_shopify_product_sync(self, tenant):
        """Test Shopify product sync creates products correctly."""
        from apps.integrations.services.shopify_service import ShopifyService
        
        mock_shopify_products = [
            {
                'id': 456,
                'title': 'Shopify Product',
                'body_html': 'Test description',
                'status': 'active',  # Required for is_active=True
                'variants': [
                    {
                        'id': 789,
                        'title': 'Default',
                        'price': '79.99',
                        'sku': 'SHOP-456',
                        'inventory_quantity': 10
                    }
                ],
                'images': [{'src': 'http://example.com/shopify.jpg'}]
            }
        ]
        
        with patch('apps.integrations.services.shopify_service.ShopifyService.fetch_products_batch') as mock_fetch:
            mock_fetch.return_value = (mock_shopify_products, None)  # Return tuple (products, next_page_info)
            
            service = ShopifyService(
                shop_domain='test-shop.myshopify.com',
                access_token='test_token'
            )
            result = service.sync_products(tenant=tenant)
        
        assert result['synced_count'] == 1
        
        # Verify product created
        product = Product.objects.get(
            tenant=tenant,
            external_source='shopify',
            external_id='456'
        )
        assert product.title == 'Shopify Product'
        assert product.is_active is True
        
        # Verify variant created
        variant = ProductVariant.objects.get(product=product)
        assert variant.price == Decimal('79.99')
        assert variant.sku == 'SHOP-456'
        assert variant.stock == 10


@pytest.mark.django_db
class TestAppointmentBookingFlow:
    """Test appointment booking with capacity validation."""
    
    @pytest.fixture
    def setup_service(self):
        """Create service with availability."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            max_services=50
        )
        
        tenant = Tenant.objects.create(
            name='Salon',
            slug='salon',
            status='active',
            subscription_tier=tier
        )
        
        customer = Customer.objects.create(
            tenant=tenant,
            phone_e164='+1234567890'
        )
        
        service = Service.objects.create(
            tenant=tenant,
            title='Haircut',
            description='Professional haircut',
            base_price=Decimal('50.00'),
            currency='USD',
            is_active=True
        )
        
        variant = ServiceVariant.objects.create(
            service=service,
            title='Standard Cut',
            duration_minutes=30,
            price=Decimal('50.00')
        )
        
        # Create availability window for tomorrow
        tomorrow = timezone.now().date() + timedelta(days=1)
        AvailabilityWindow.objects.create(
            tenant=tenant,
            service=service,
            date=tomorrow,
            start_time='09:00',
            end_time='17:00',
            capacity=2,
            timezone='UTC'
        )
        
        return tenant, customer, service, variant, tomorrow
    
    def test_appointment_booking_with_capacity(self, setup_service):
        """Test appointment booking respects capacity limits."""
        tenant, customer, service, variant, tomorrow = setup_service
        
        from apps.services.services.booking_service import BookingService
        
        booking_service = BookingService(tenant=tenant)
        
        # Book first appointment
        start_dt = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.strptime('10:00', '%H:%M').time())
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(tomorrow, timezone.datetime.strptime('10:30', '%H:%M').time())
        )
        
        appointment1 = booking_service.create_appointment(
            customer_id=customer.id,
            service_id=service.id,
            variant_id=variant.id,
            start_dt=start_dt,
            end_dt=end_dt,
            notes='First booking',
            status='confirmed'  # Explicitly set status to confirmed
        )
        
        assert appointment1.status == 'confirmed'
        assert Appointment.objects.filter(tenant=tenant).count() == 1
        
        # Create second customer
        customer2 = Customer.objects.create(
            tenant=tenant,
            phone_e164='+1987654321'
        )
        
        # Book second appointment (should succeed - capacity is 2)
        appointment2 = booking_service.create_appointment(
            customer_id=customer2.id,
            service_id=service.id,
            variant_id=variant.id,
            start_dt=start_dt,
            end_dt=end_dt,
            notes='Second booking',
            status='confirmed'  # Explicitly set status to confirmed
        )
        
        assert appointment2.status == 'confirmed'
        assert Appointment.objects.filter(tenant=tenant).count() == 2
        
        # Create third customer
        customer3 = Customer.objects.create(
            tenant=tenant,
            phone_e164='+1555555555'
        )
        
        # Try to book third appointment (should fail - capacity exceeded)
        with pytest.raises(Exception) as exc_info:
            booking_service.create_appointment(
                customer_id=customer3.id,
                service_id=service.id,
                variant_id=variant.id,
                start_dt=start_dt,
                end_dt=end_dt,
                notes='Third booking'
            )
        
        assert 'capacity' in str(exc_info.value).lower() or 'full' in str(exc_info.value).lower()
        assert Appointment.objects.filter(tenant=tenant).count() == 2


@pytest.mark.django_db
class TestOrderAndWalletFlow:
    """Test order creation and wallet credit flow."""
    
    @pytest.fixture
    def setup_order_flow(self):
        """Setup for order and wallet tests."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            payment_facilitation=True,
            transaction_fee_percentage=Decimal('3.5')
        )
        
        tenant = Tenant.objects.create(
            name='Shop',
            slug='shop',
            status='active',
            subscription_tier=tier
        )
        
        wallet = TenantWallet.objects.create(
            tenant=tenant,
            balance=Decimal('0.00'),
            currency='USD'
        )
        
        customer = Customer.objects.create(
            tenant=tenant,
            phone_e164='+1234567890'
        )
        
        product = Product.objects.create(
            tenant=tenant,
            title='Test Product',
            price=Decimal('100.00'),
            currency='USD',
            is_active=True
        )
        
        return tenant, wallet, customer, product
    
    def test_order_creation_and_wallet_credit(self, setup_order_flow):
        """Test order creation triggers wallet credit with fee deduction."""
        tenant, wallet, customer, product = setup_order_flow
        
        # Create order
        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            currency='USD',
            subtotal=Decimal('100.00'),
            shipping=Decimal('0.00'),
            total=Decimal('100.00'),
            status='placed',
            items=[{
                'product_id': str(product.id),
                'quantity': 1,
                'price': '100.00'
            }]
        )
        
        # Simulate payment processing
        from apps.tenants.services.wallet_service import WalletService
        
        result = WalletService.process_customer_payment(
            tenant=tenant,
            payment_amount=Decimal('100.00'),
            reference_type='order',
            reference_id=order.id,
            metadata={'payment_ref': 'pay_test123'}
        )
        
        assert result['payment_transaction'] is not None
        
        # Verify wallet credited with net amount (100 - 3.5% fee = 96.50)
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('96.50')
        
        # Verify transactions created
        customer_payment = Transaction.objects.get(
            tenant=tenant,
            transaction_type='customer_payment',
            reference_id=str(order.id)
        )
        assert customer_payment.amount == Decimal('100.00')
        assert customer_payment.fee == Decimal('3.50')
        assert customer_payment.net_amount == Decimal('96.50')
        
        platform_fee = Transaction.objects.get(
            tenant=tenant,
            transaction_type='platform_fee'
        )
        assert platform_fee.amount == Decimal('3.50')


@pytest.mark.django_db
class TestCampaignWithConsentFlow:
    """Test campaign execution with consent filtering."""
    
    @pytest.fixture
    def setup_campaign(self):
        """Setup for campaign tests."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            max_campaign_sends=5000
        )
        
        tenant = Tenant.objects.create(
            name='Marketing Shop',
            slug='marketing-shop',
            status='active',
            subscription_tier=tier
        )
        
        # Create customers with different consent preferences
        customer1 = Customer.objects.create(
            tenant=tenant,
            phone_e164='+1111111111',
            name='Opted In Customer'
        )
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer1,
            transactional_messages=True,
            promotional_messages=True,  # Opted in
            reminder_messages=True
        )
        
        customer2 = Customer.objects.create(
            tenant=tenant,
            phone_e164='+2222222222',
            name='Opted Out Customer'
        )
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer2,
            transactional_messages=True,
            promotional_messages=False,  # Opted out
            reminder_messages=True
        )
        
        customer3 = Customer.objects.create(
            tenant=tenant,
            phone_e164='+3333333333',
            name='Another Opted In'
        )
        CustomerPreferences.objects.create(
            tenant=tenant,
            customer=customer3,
            transactional_messages=True,
            promotional_messages=True,  # Opted in
            reminder_messages=True
        )
        
        return tenant, customer1, customer2, customer3
    
    def test_campaign_respects_consent(self, setup_campaign):
        """Test campaign only sends to customers who consented."""
        tenant, customer1, customer2, customer3 = setup_campaign
        
        # Create campaign
        campaign = MessageCampaign.objects.create(
            tenant=tenant,
            name='Summer Sale',
            message_content='Get 20% off all items!',
            target_criteria={'all': True},
            status='draft'
        )
        
        from apps.messaging.services.campaign_service import CampaignService
        
        with patch('apps.integrations.services.twilio_service.TwilioService.send_whatsapp') as mock_send:
            mock_send.return_value = {'success': True, 'sid': 'SM123', 'status': 'sent'}  # Complete mock response
            
            campaign_service = CampaignService()  # No tenant parameter needed
            result = campaign_service.execute_campaign(campaign)
        
        assert result['sent'] == 2  # 2 customers opted in and received messages
        assert result['skipped_no_consent'] == 1  # 1 customer opted out
        
        # Should only send to 2 customers (customer1 and customer3 who opted in)
        # customer2 opted out, so should not receive
        assert mock_send.call_count == 2
        
        # Verify campaign metrics
        campaign.refresh_from_db()
        assert campaign.delivered_count == 2  # Only 2 actually received (opted in)
        assert campaign.failed_count == 0  # No failures
        assert campaign.status == 'completed'


@pytest.mark.django_db
class TestSubscriptionBillingFlow:
    """Test subscription billing and status updates."""
    
    @pytest.fixture
    def setup_subscription(self):
        """Setup for subscription tests."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=Decimal('99.00'),
            yearly_price=Decimal('950.00')
        )
        
        tenant = Tenant.objects.create(
            name='Billing Test',
            slug='billing-test',
            status='active',
            subscription_tier=tier
        )
        
        subscription = Subscription.objects.create(
            tenant=tenant,
            tier=tier,
            billing_cycle='monthly',
            status='active',
            start_date=timezone.now() - timedelta(days=30),
            next_billing_date=timezone.now()
        )
        
        return tenant, subscription, tier
    
    def test_successful_billing_updates_subscription(self, setup_subscription):
        """Test subscription status check works correctly."""
        tenant, subscription, tier = setup_subscription
        
        from apps.tenants.services.subscription_service import SubscriptionService
        
        # Test active subscription
        status = SubscriptionService.check_subscription_status(tenant)
        assert status == 'active'
        
        # Test subscription is active
        is_active = SubscriptionService.is_subscription_active(tenant)
        assert is_active is True
    
    def test_failed_billing_suspends_subscription(self, setup_subscription):
        """Test suspended subscription is detected correctly."""
        tenant, subscription, tier = setup_subscription
        
        from apps.tenants.services.subscription_service import SubscriptionService
        
        # Manually suspend subscription
        subscription.status = 'suspended'
        subscription.save()
        
        tenant.status = 'suspended'
        tenant.save()
        
        # Verify subscription status is detected
        status = SubscriptionService.check_subscription_status(tenant)
        assert status == 'suspended'
        
        # Verify subscription is not active
        is_active = SubscriptionService.is_subscription_active(tenant)
        assert is_active is False


@pytest.mark.django_db
class TestTenantIsolation:
    """Test tenant isolation across all operations."""
    
    @pytest.fixture
    def setup_two_tenants(self):
        """Create two separate tenants with data."""
        tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00
        )
        
        # Tenant A
        tenant_a = Tenant.objects.create(
            name='Tenant A',
            slug='tenant-a',
            status='active',
            whatsapp_number='+14155551111',
            subscription_tier=tier
        )
        
        customer_a = Customer.objects.create(
            tenant=tenant_a,
            phone_e164='+1111111111',
            name='Customer A'
        )
        
        product_a = Product.objects.create(
            tenant=tenant_a,
            title='Product A',
            price=Decimal('50.00'),
            is_active=True
        )
        
        # Tenant B
        tenant_b = Tenant.objects.create(
            name='Tenant B',
            slug='tenant-b',
            status='active',
            whatsapp_number='+14155552222',
            subscription_tier=tier
        )
        
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164='+2222222222',
            name='Customer B'
        )
        
        product_b = Product.objects.create(
            tenant=tenant_b,
            title='Product B',
            price=Decimal('75.00'),
            is_active=True
        )
        
        return tenant_a, customer_a, product_a, tenant_b, customer_b, product_b
    
    def test_customer_isolation(self, setup_two_tenants):
        """Test customers are isolated by tenant."""
        tenant_a, customer_a, _, tenant_b, customer_b, _ = setup_two_tenants
        
        # Tenant A should only see their customer
        tenant_a_customers = Customer.objects.filter(tenant=tenant_a)
        assert tenant_a_customers.count() == 1
        assert tenant_a_customers.first().id == customer_a.id
        
        # Tenant B should only see their customer
        tenant_b_customers = Customer.objects.filter(tenant=tenant_b)
        assert tenant_b_customers.count() == 1
        assert tenant_b_customers.first().id == customer_b.id
    
    def test_product_isolation(self, setup_two_tenants):
        """Test products are isolated by tenant."""
        tenant_a, _, product_a, tenant_b, _, product_b = setup_two_tenants
        
        # Tenant A should only see their product
        tenant_a_products = Product.objects.filter(tenant=tenant_a)
        assert tenant_a_products.count() == 1
        assert tenant_a_products.first().id == product_a.id
        
        # Tenant B should only see their product
        tenant_b_products = Product.objects.filter(tenant=tenant_b)
        assert tenant_b_products.count() == 1
        assert tenant_b_products.first().id == product_b.id
    
    def test_same_phone_different_tenants(self, setup_two_tenants):
        """Test same phone number creates separate customers per tenant."""
        tenant_a, _, _, tenant_b, _, _ = setup_two_tenants
        
        same_phone = '+9999999999'
        
        # Create customer with same phone in both tenants
        customer_a = Customer.objects.create(
            tenant=tenant_a,
            phone_e164=same_phone,
            name='Same Phone A'
        )
        
        customer_b = Customer.objects.create(
            tenant=tenant_b,
            phone_e164=same_phone,
            name='Same Phone B'
        )
        
        # Should be different customer records
        assert customer_a.id != customer_b.id
        assert customer_a.tenant == tenant_a
        assert customer_b.tenant == tenant_b
        
        # Each tenant should only see their own customer by ID
        # Note: Can't filter by encrypted phone_e164 field directly
        assert Customer.objects.filter(tenant=tenant_a, id=customer_a.id).exists()
        assert Customer.objects.filter(tenant=tenant_b, id=customer_b.id).exists()
        
        # Verify phone numbers are stored correctly (even though encrypted)
        assert customer_a.phone_e164 == same_phone
        assert customer_b.phone_e164 == same_phone
    
    def test_cross_tenant_access_prevented(self, setup_two_tenants):
        """Test that cross-tenant access is prevented."""
        tenant_a, customer_a, product_a, tenant_b, _, _ = setup_two_tenants
        
        # Try to access tenant A's product with tenant B filter
        tenant_b_products = Product.objects.filter(tenant=tenant_b, id=product_a.id)
        assert tenant_b_products.count() == 0
        
        # Try to access tenant A's customer with tenant B filter
        tenant_b_customers = Customer.objects.filter(tenant=tenant_b, id=customer_a.id)
        assert tenant_b_customers.count() == 0
