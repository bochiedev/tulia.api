"""
Tests for tenant models.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.tenants.models import Tenant, SubscriptionTier, GlobalParty, Customer


@pytest.mark.django_db
class TestSubscriptionTier(TestCase):
    """Test SubscriptionTier model."""
    
    def setUp(self):
        """Set up test data."""
        self.starter_tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
            monthly_messages=1000,
            max_products=100,
            max_services=10,
            payment_facilitation=False,
            transaction_fee_percentage=0,
        )
        
        self.growth_tier = SubscriptionTier.objects.create(
            name='Growth',
            monthly_price=99.00,
            yearly_price=950.00,
            monthly_messages=10000,
            max_products=1000,
            max_services=50,
            payment_facilitation=True,
            transaction_fee_percentage=3.5,
        )
    
    def test_tier_creation(self):
        """Test creating subscription tiers."""
        self.assertEqual(self.starter_tier.name, 'Starter')
        self.assertEqual(self.starter_tier.monthly_price, 29.00)
        self.assertFalse(self.starter_tier.payment_facilitation)
    
    def test_check_limit_within(self):
        """Test checking limits when within bounds."""
        is_within, limit = self.starter_tier.check_limit('max_products', 50)
        self.assertTrue(is_within)
        self.assertEqual(limit, 100)
    
    def test_check_limit_exceeded(self):
        """Test checking limits when exceeded."""
        is_within, limit = self.starter_tier.check_limit('max_products', 150)
        self.assertFalse(is_within)
        self.assertEqual(limit, 100)
    
    def test_check_limit_unlimited(self):
        """Test checking limits when unlimited."""
        enterprise_tier = SubscriptionTier.objects.create(
            name='Enterprise',
            monthly_price=299.00,
            yearly_price=2870.00,
            monthly_messages=None,  # Unlimited
            max_products=None,
            max_services=None,
            payment_facilitation=True,
            transaction_fee_percentage=2.5,
        )
        
        is_within, limit = enterprise_tier.check_limit('max_products', 10000)
        self.assertTrue(is_within)
        self.assertIsNone(limit)


@pytest.mark.django_db
class TestTenant(TestCase):
    """Test Tenant model."""
    
    def setUp(self):
        """Set up test data."""
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
            monthly_messages=1000,
            max_products=100,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            status='trial',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
            twilio_sid='test_sid',
            twilio_token='test_token',
            webhook_secret='test_secret',
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
        )
    
    def test_tenant_creation(self):
        """Test creating a tenant."""
        self.assertEqual(self.tenant.name, 'Test Business')
        self.assertEqual(self.tenant.slug, 'test-business')
        self.assertEqual(self.tenant.status, 'trial')
    
    def test_encrypted_fields(self):
        """Test that sensitive fields are encrypted in TenantSettings."""
        # Create TenantSettings with encrypted fields
        from apps.tenants.models import TenantSettings
        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            twilio_sid='test_sid',
            twilio_token='test_token',
            twilio_webhook_secret='test_secret'
        )
        
        # Retrieve from database
        settings = TenantSettings.objects.get(tenant=self.tenant)
        
        # Should be decrypted when accessed
        self.assertEqual(settings.twilio_sid, 'test_sid')
        self.assertEqual(settings.twilio_token, 'test_token')
        self.assertEqual(settings.twilio_webhook_secret, 'test_secret')
    
    def test_is_active_with_trial(self):
        """Test is_active returns True for valid trial."""
        self.assertTrue(self.tenant.is_active())
    
    def test_is_active_expired_trial(self):
        """Test is_active returns False for expired trial."""
        self.tenant.trial_end_date = timezone.now() - timedelta(days=1)
        self.tenant.save()
        self.assertFalse(self.tenant.is_active())
    
    def test_is_active_with_waived_subscription(self):
        """Test is_active returns True when subscription is waived."""
        self.tenant.subscription_waived = True
        self.tenant.status = 'suspended'
        self.tenant.save()
        self.assertTrue(self.tenant.is_active())
    
    def test_has_valid_trial(self):
        """Test has_valid_trial method."""
        self.assertTrue(self.tenant.has_valid_trial())
        
        # Expire trial
        self.tenant.trial_end_date = timezone.now() - timedelta(days=1)
        self.tenant.save()
        self.assertFalse(self.tenant.has_valid_trial())
    
    def test_days_until_trial_expires(self):
        """Test calculating days until trial expires."""
        days = self.tenant.days_until_trial_expires()
        self.assertGreater(days, 0)
        self.assertLessEqual(days, 14)
    
    def test_bot_persona_defaults(self):
        """Test bot persona fields have correct defaults."""
        self.assertEqual(self.tenant.bot_name, 'Assistant')
        self.assertEqual(self.tenant.tone_style, 'friendly_concise')
        self.assertEqual(self.tenant.default_language, 'en')
        self.assertEqual(self.tenant.max_chattiness_level, 2)
        self.assertEqual(self.tenant.allowed_languages, ['en'])
        self.assertEqual(self.tenant.payment_methods_enabled, {})
        self.assertEqual(self.tenant.escalation_rules, {})
    
    def test_get_allowed_languages(self):
        """Test getting allowed languages with defaults."""
        # Default case
        languages = self.tenant.get_allowed_languages()
        self.assertEqual(languages, ['en'])
        
        # Custom languages
        self.tenant.allowed_languages = ['en', 'sw', 'sheng']
        self.tenant.save()
        languages = self.tenant.get_allowed_languages()
        self.assertEqual(languages, ['en', 'sw', 'sheng'])
    
    def test_is_language_allowed(self):
        """Test checking if language is allowed."""
        # Default - only English allowed
        self.assertTrue(self.tenant.is_language_allowed('en'))
        self.assertFalse(self.tenant.is_language_allowed('sw'))
        
        # Add more languages
        self.tenant.allowed_languages = ['en', 'sw', 'sheng']
        self.tenant.save()
        self.assertTrue(self.tenant.is_language_allowed('sw'))
        self.assertTrue(self.tenant.is_language_allowed('sheng'))
        self.assertFalse(self.tenant.is_language_allowed('fr'))
    
    def test_get_payment_methods(self):
        """Test getting payment methods with defaults."""
        # Default methods
        methods = self.tenant.get_payment_methods()
        expected = {
            'mpesa_stk': True,
            'mpesa_c2b': True,
            'pesapal_card': False
        }
        self.assertEqual(methods, expected)
        
        # Custom methods
        self.tenant.payment_methods_enabled = {'pesapal_card': True}
        self.tenant.save()
        methods = self.tenant.get_payment_methods()
        expected = {
            'mpesa_stk': True,
            'mpesa_c2b': True,
            'pesapal_card': True
        }
        self.assertEqual(methods, expected)
    
    def test_is_payment_method_enabled(self):
        """Test checking if payment method is enabled."""
        # Default settings
        self.assertTrue(self.tenant.is_payment_method_enabled('mpesa_stk'))
        self.assertTrue(self.tenant.is_payment_method_enabled('mpesa_c2b'))
        self.assertFalse(self.tenant.is_payment_method_enabled('pesapal_card'))
        
        # Enable card payments
        self.tenant.payment_methods_enabled = {'pesapal_card': True}
        self.tenant.save()
        self.assertTrue(self.tenant.is_payment_method_enabled('pesapal_card'))
    
    def test_get_escalation_rules(self):
        """Test getting escalation rules with defaults."""
        rules = self.tenant.get_escalation_rules()
        expected = {
            'auto_escalate_payment_disputes': True,
            'auto_escalate_after_failures': 2,
            'auto_escalate_sensitive_content': True,
            'escalation_timeout_minutes': 30
        }
        self.assertEqual(rules, expected)
        
        # Custom rules
        self.tenant.escalation_rules = {'escalation_timeout_minutes': 60}
        self.tenant.save()
        rules = self.tenant.get_escalation_rules()
        expected = {
            'auto_escalate_payment_disputes': True,
            'auto_escalate_after_failures': 2,
            'auto_escalate_sensitive_content': True,
            'escalation_timeout_minutes': 60
        }
        self.assertEqual(rules, expected)


@pytest.mark.django_db
class TestGlobalParty(TestCase):
    """Test GlobalParty model."""
    
    def test_global_party_creation(self):
        """Test creating a global party."""
        party = GlobalParty.objects.create(
            phone_e164='+14155551234'
        )
        
        self.assertIsNotNone(party.id)
        
        # Retrieve and check encryption
        party_retrieved = GlobalParty.objects.get(id=party.id)
        self.assertEqual(party_retrieved.phone_e164, '+14155551234')
    
    def test_unique_phone_constraint(self):
        """Test that phone numbers should be unique (note: encryption prevents DB-level enforcement)."""
        # Note: Due to encryption, the database cannot enforce uniqueness at the DB level
        # since each encryption produces a different ciphertext. Application-level
        # uniqueness checks would be needed for encrypted fields.
        party1 = GlobalParty.objects.create(phone_e164='+14155551234')
        party2 = GlobalParty.objects.create(phone_e164='+14155551234')
        
        # Both records are created (DB can't enforce uniqueness on encrypted data)
        self.assertIsNotNone(party1.id)
        self.assertIsNotNone(party2.id)
        self.assertNotEqual(party1.id, party2.id)


@pytest.mark.django_db
class TestCustomer(TestCase):
    """Test Customer model."""
    
    def setUp(self):
        """Set up test data."""
        self.tier = SubscriptionTier.objects.create(
            name='Starter',
            monthly_price=29.00,
            yearly_price=278.00,
        )
        
        self.tenant = Tenant.objects.create(
            name='Test Business',
            slug='test-business',
            subscription_tier=self.tier,
            whatsapp_number='+14155551234',
            twilio_sid='test_sid',
            twilio_token='test_token',
            webhook_secret='test_secret',
        )
        
        self.global_party = GlobalParty.objects.create(
            phone_e164='+14155559999'
        )
    
    def test_customer_creation(self):
        """Test creating a customer."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
            name='John Doe',
            global_party=self.global_party,
        )
        
        self.assertEqual(customer.name, 'John Doe')
        self.assertEqual(customer.tenant, self.tenant)
    
    def test_encrypted_phone(self):
        """Test that phone number is encrypted."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        # Retrieve and check decryption
        customer_retrieved = Customer.objects.get(id=customer.id)
        self.assertEqual(customer_retrieved.phone_e164, '+14155559999')
    
    def test_unique_tenant_phone_constraint(self):
        """Test that (tenant, phone) combination should be unique (note: encryption prevents DB-level enforcement)."""
        # Note: Due to encryption, the database cannot enforce uniqueness at the DB level
        # Application-level checks are needed to prevent duplicate (tenant, phone) combinations
        customer1 = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        customer2 = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        # Both records are created (DB can't enforce uniqueness on encrypted data)
        self.assertIsNotNone(customer1.id)
        self.assertIsNotNone(customer2.id)
        self.assertNotEqual(customer1.id, customer2.id)
    
    def test_same_phone_different_tenants(self):
        """Test that same phone can exist across different tenants."""
        tenant2 = Tenant.objects.create(
            name='Another Business',
            slug='another-business',
            subscription_tier=self.tier,
            whatsapp_number='+14155555678',
            twilio_sid='test_sid2',
            twilio_token='test_token2',
            webhook_secret='test_secret2',
        )
        
        customer1 = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        customer2 = Customer.objects.create(
            tenant=tenant2,
            phone_e164='+14155559999',
            global_party=self.global_party,
        )
        
        self.assertNotEqual(customer1.id, customer2.id)
        self.assertEqual(customer1.phone_e164, customer2.phone_e164)
    
    def test_update_last_seen(self):
        """Test updating last_seen_at."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        self.assertIsNone(customer.last_seen_at)
        self.assertIsNone(customer.first_interaction_at)
        
        customer.update_last_seen()
        
        self.assertIsNotNone(customer.last_seen_at)
        self.assertIsNotNone(customer.first_interaction_at)
    
    def test_tag_management(self):
        """Test adding and removing tags."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        # Add tag
        customer.add_tag('vip')
        self.assertTrue(customer.has_tag('vip'))
        
        # Add duplicate tag (should not duplicate)
        customer.add_tag('vip')
        self.assertEqual(customer.tags.count('vip'), 1)
        
        # Remove tag
        customer.remove_tag('vip')
        self.assertFalse(customer.has_tag('vip'))
    
    def test_consent_management(self):
        """Test consent flag management."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        # Test default consent flags
        self.assertEqual(customer.consent_flags, {})
        self.assertIsNone(customer.marketing_opt_in)
        self.assertIsNone(customer.language_preference)
        
        # Update consent
        customer.update_consent('marketing', True)
        self.assertTrue(customer.get_consent('marketing'))
        
        # Update marketing opt-in
        customer.marketing_opt_in = True
        customer.save()
        self.assertTrue(customer.has_marketing_consent())
        
        # Test consent flags override
        customer.consent_flags = {'marketing': False}
        customer.marketing_opt_in = None
        customer.save()
        self.assertFalse(customer.has_marketing_consent())
    
    def test_opt_out_all(self):
        """Test opting out of all communications."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
            marketing_opt_in=True,
            consent_flags={'marketing': True, 'notifications': True}
        )
        
        # Opt out of everything
        customer.opt_out_all()
        
        self.assertFalse(customer.marketing_opt_in)
        self.assertFalse(customer.get_consent('marketing'))
        self.assertFalse(customer.get_consent('notifications'))
        self.assertFalse(customer.get_consent('promotional'))
    
    def test_get_effective_language(self):
        """Test getting effective language preference."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
        )
        
        # Default to tenant default
        self.assertEqual(customer.get_effective_language('sw'), 'sw')
        
        # Use language preference if set
        customer.language_preference = 'sw'
        customer.save()
        self.assertEqual(customer.get_effective_language('en'), 'sw')
        
        # Fall back to language field if no preference
        customer.language_preference = None
        customer.language = 'sheng'
        customer.save()
        self.assertEqual(customer.get_effective_language('en'), 'sheng')
    
    def test_language_preference_choices(self):
        """Test language preference field choices."""
        customer = Customer.objects.create(
            tenant=self.tenant,
            phone_e164='+14155559999',
            language_preference='sw'
        )
        
        self.assertEqual(customer.language_preference, 'sw')
        
        # Test all valid choices
        valid_choices = ['en', 'sw', 'sheng', 'mixed']
        for choice in valid_choices:
            customer.language_preference = choice
            customer.save()
            customer.refresh_from_db()
            self.assertEqual(customer.language_preference, choice)
