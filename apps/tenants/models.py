"""
Tenant models for multi-tenant isolation.

Implements strict tenant isolation with subscription management,
Twilio configuration, and API key authentication.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.fields import EncryptedCharField, EncryptedTextField


def default_allowed_languages():
    """Default allowed languages for tenant."""
    return ['en']


class TenantManager(models.Manager):
    """Manager for tenant-scoped queries."""
    
    def active(self):
        """Return only active tenants."""
        return self.filter(status__in=['active', 'trial'])
    
    def by_whatsapp_number(self, number):
        """Find tenant by WhatsApp number."""
        return self.filter(whatsapp_number=number).first()
    
    def by_api_key(self, tenant_id, api_key_hash):
        """Validate tenant API key."""
        return self.filter(
            id=tenant_id,
            api_keys__contains=[{'key_hash': api_key_hash}]
        ).first()


class Tenant(BaseModel):
    """
    Tenant model representing an isolated business account.
    
    Each tenant has:
    - Unique WhatsApp number for customer communications
    - Subscription tier with feature limits
    - Twilio credentials for messaging
    - API keys for authentication
    - Isolated customer data, catalogs, and analytics
    """
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trial', 'Free Trial'),
        ('trial_expired', 'Trial Expired'),
        ('suspended', 'Suspended'),
        ('canceled', 'Canceled'),
    ]
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Business name"
    )
    slug = models.SlugField(
        unique=True,
        max_length=100,
        help_text="URL-friendly identifier"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial',
        db_index=True,
        help_text="Current tenant status"
    )
    
    # Subscription
    subscription_tier = models.ForeignKey(
        'SubscriptionTier',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tenants',
        help_text="Current subscription tier"
    )
    subscription_waived = models.BooleanField(
        default=False,
        help_text="Whether subscription fees are waived"
    )
    trial_start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Free trial start date"
    )
    trial_end_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Free trial end date"
    )
    
    # Twilio Configuration
    whatsapp_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="WhatsApp business number (E.164 format)"
    )
    twilio_sid = EncryptedCharField(
        max_length=500,
        help_text="Encrypted Twilio Account SID"
    )
    twilio_token = EncryptedCharField(
        max_length=500,
        help_text="Encrypted Twilio Auth Token"
    )
    webhook_secret = EncryptedCharField(
        max_length=500,
        help_text="Encrypted webhook signature secret"
    )
    
    # API Access
    api_keys = models.JSONField(
        default=list,
        blank=True,
        help_text="List of API key hashes with metadata: [{key_hash, name, created_at}]"
    )
    allowed_origins = models.JSONField(
        default=list,
        blank=True,
        help_text="CORS allowed origins for this tenant"
    )
    
    # Settings
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Tenant timezone for scheduling"
    )
    quiet_hours_start = models.TimeField(
        default='22:00',
        help_text="Start of quiet hours (no automated messages)"
    )
    quiet_hours_end = models.TimeField(
        default='08:00',
        help_text="End of quiet hours"
    )
    
    # Contact Information
    contact_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Primary contact email for notifications"
    )
    contact_phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Primary contact phone"
    )
    
    # Bot Persona Configuration (for LangGraph Agent)
    bot_name = models.CharField(
        max_length=100,
        default="Assistant",
        help_text="Custom bot name for conversations"
    )
    tone_style = models.CharField(
        max_length=50,
        default="friendly_concise",
        choices=[
            ('friendly_concise', 'Friendly & Concise'),
            ('professional', 'Professional'),
            ('casual', 'Casual'),
            ('formal', 'Formal'),
        ],
        help_text="Communication tone and style"
    )
    default_language = models.CharField(
        max_length=10,
        default="en",
        choices=[
            ('en', 'English'),
            ('sw', 'Swahili'),
            ('sheng', 'Sheng'),
        ],
        help_text="Default language for conversations"
    )
    allowed_languages = models.JSONField(
        default=default_allowed_languages,
        blank=True,
        help_text="Languages allowed for this tenant (e.g., ['en', 'sw', 'sheng'])"
    )
    max_chattiness_level = models.IntegerField(
        default=2,
        choices=[
            (0, 'Strictly Business'),
            (1, 'Minimal Friendliness'),
            (2, 'Friendly but Bounded'),
            (3, 'More Friendly'),
        ],
        help_text="Maximum chattiness level for cost control (0-3)"
    )
    payment_methods_enabled = models.JSONField(
        default=dict,
        blank=True,
        help_text="Enabled payment methods: {'mpesa_stk': True, 'mpesa_c2b': True, 'pesapal_card': False}"
    )
    escalation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Human escalation rules and triggers configuration"
    )
    
    # Custom manager
    objects = TenantManager()
    
    class Meta:
        db_table = 'tenants'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['trial_end_date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.slug})"
    
    def is_active(self):
        """Check if tenant has active subscription or valid trial."""
        if self.subscription_waived:
            return True
        
        if self.status == 'active':
            return True
        
        if self.status == 'trial' and self.trial_end_date:
            from django.utils import timezone
            return timezone.now() < self.trial_end_date
        
        return False
    
    def has_valid_trial(self):
        """Check if tenant has a valid free trial."""
        if self.status != 'trial' or not self.trial_end_date:
            return False
        
        from django.utils import timezone
        return timezone.now() < self.trial_end_date
    
    def days_until_trial_expires(self):
        """Calculate days remaining in trial."""
        if not self.has_valid_trial():
            return 0
        
        from django.utils import timezone
        delta = self.trial_end_date - timezone.now()
        return max(0, delta.days)
    
    def get_allowed_languages(self):
        """Get list of allowed languages, defaulting to English if empty."""
        if not self.allowed_languages:
            return ['en']
        return self.allowed_languages
    
    def is_language_allowed(self, language_code):
        """Check if a language is allowed for this tenant."""
        return language_code in self.get_allowed_languages()
    
    def get_payment_methods(self):
        """Get enabled payment methods with defaults."""
        default_methods = {
            'mpesa_stk': True,
            'mpesa_c2b': True, 
            'pesapal_card': False
        }
        if not self.payment_methods_enabled:
            return default_methods
        return {**default_methods, **self.payment_methods_enabled}
    
    def is_payment_method_enabled(self, method):
        """Check if a specific payment method is enabled."""
        return self.get_payment_methods().get(method, False)
    
    def get_escalation_rules(self):
        """Get escalation rules with defaults."""
        default_rules = {
            'auto_escalate_payment_disputes': True,
            'auto_escalate_after_failures': 2,
            'auto_escalate_sensitive_content': True,
            'escalation_timeout_minutes': 30
        }
        if not self.escalation_rules:
            return default_rules
        return {**default_rules, **self.escalation_rules}


class SubscriptionTier(BaseModel):
    """
    Subscription tier defining feature limits and pricing.
    
    Three tiers: Starter, Growth, Enterprise
    Each tier has different limits for messages, products, services, etc.
    """
    
    API_ACCESS_CHOICES = [
        ('none', 'No API Access'),
        ('read', 'Read-Only API'),
        ('full', 'Full API Access'),
    ]
    
    # Basic Information
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Tier name (Starter, Growth, Enterprise)"
    )
    description = models.TextField(
        blank=True,
        help_text="Tier description"
    )
    
    # Pricing
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Monthly subscription price"
    )
    yearly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Yearly subscription price (typically 20% off)"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code"
    )
    
    # Feature Limits (null = unlimited)
    monthly_messages = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum outbound messages per month (null = unlimited)"
    )
    max_products = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum products in catalog (null = unlimited)"
    )
    max_services = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum bookable services (null = unlimited)"
    )
    max_campaign_sends = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum campaign sends per month (null = unlimited)"
    )
    max_daily_outbound = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum daily outbound messages (null = unlimited)"
    )
    
    # Features
    payment_facilitation = models.BooleanField(
        default=False,
        help_text="Enable payment processing and wallet"
    )
    transaction_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Transaction fee percentage for facilitated payments"
    )
    ab_test_variants = models.IntegerField(
        default=2,
        help_text="Maximum A/B test variants allowed"
    )
    priority_support = models.BooleanField(
        default=False,
        help_text="Priority customer support"
    )
    custom_branding = models.BooleanField(
        default=False,
        help_text="Custom branding and templates"
    )
    api_access = models.CharField(
        max_length=10,
        choices=API_ACCESS_CHOICES,
        default='read',
        help_text="API access level"
    )
    
    class Meta:
        db_table = 'subscription_tiers'
        ordering = ['monthly_price']
    
    def __str__(self):
        return self.name
    
    def check_limit(self, feature_name, current_count):
        """
        Check if current count exceeds feature limit.
        
        Args:
            feature_name: Name of the feature (e.g., 'max_products')
            current_count: Current usage count
            
        Returns:
            tuple: (is_within_limit, limit_value)
        """
        limit = getattr(self, feature_name, None)
        
        # None means unlimited
        if limit is None:
            return True, None
        
        return current_count < limit, limit


class SubscriptionManager(models.Manager):
    """Manager for subscription queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get subscription for a specific tenant."""
        return self.filter(tenant=tenant).first()
    
    def active(self):
        """Get all active subscriptions."""
        return self.filter(status='active')
    
    def due_for_billing(self, date=None):
        """Get subscriptions due for billing on a specific date."""
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        return self.filter(status='active', next_billing_date=date)


class Subscription(BaseModel):
    """
    Subscription model representing a tenant's active subscription.
    
    Manages billing cycle, status, and payment tracking.
    Each tenant can have one active subscription at a time.
    """
    
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('canceled', 'Canceled'),
        ('expired', 'Expired'),
    ]
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='subscription',
        help_text="Tenant this subscription belongs to"
    )
    tier = models.ForeignKey(
        SubscriptionTier,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        help_text="Subscription tier"
    )
    
    billing_cycle = models.CharField(
        max_length=10,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly',
        help_text="Billing frequency"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text="Current subscription status"
    )
    
    # Dates
    start_date = models.DateField(
        help_text="Subscription start date"
    )
    next_billing_date = models.DateField(
        db_index=True,
        help_text="Next billing date"
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Cancellation timestamp"
    )
    
    # Payment
    payment_method_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="External payment method identifier"
    )
    
    # Custom manager
    objects = SubscriptionManager()
    
    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_billing_date']),
            models.Index(fields=['tenant', 'status']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.tier.name} ({self.status})"
    
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status == 'active'
    
    def calculate_price(self):
        """Calculate subscription price based on billing cycle."""
        if self.billing_cycle == 'yearly':
            return self.tier.yearly_price
        return self.tier.monthly_price


class SubscriptionDiscountManager(models.Manager):
    """Manager for subscription discount queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get discounts for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def valid_for_tenant(self, tenant):
        """Get valid (non-expired, within usage limit) discounts for a tenant."""
        from django.utils import timezone
        now = timezone.now().date()
        
        # Get all discounts for tenant
        discounts = self.filter(tenant=tenant)
        
        # Filter valid ones
        valid = []
        for discount in discounts:
            if discount.is_valid():
                valid.append(discount.id)
        
        return self.filter(id__in=valid) if valid else self.none()


class SubscriptionDiscount(BaseModel):
    """
    Discount applied to a tenant's subscription.
    
    Supports percentage or fixed amount discounts with optional
    expiry dates and usage limits.
    """
    
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='subscription_discounts',
        help_text="Tenant this discount applies to"
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        help_text="Type of discount"
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Discount value (percentage or fixed amount)"
    )
    
    # Optional Constraints
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Discount expiry date (null = no expiry)"
    )
    usage_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of times discount can be applied (null = unlimited)"
    )
    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times discount has been applied"
    )
    
    # Metadata
    code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Optional discount code"
    )
    description = models.TextField(
        blank=True,
        help_text="Discount description"
    )
    
    # Custom manager
    objects = SubscriptionDiscountManager()
    
    class Meta:
        db_table = 'subscription_discounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'expiry_date']),
        ]
    
    def __str__(self):
        if self.discount_type == 'percentage':
            return f"{self.tenant.name} - {self.value}% off"
        return f"{self.tenant.name} - ${self.value} off"
    
    def is_valid(self):
        """Check if discount is still valid."""
        from django.utils import timezone
        
        # Check expiry date
        if self.expiry_date and timezone.now().date() > self.expiry_date:
            return False
        
        # Check usage limit
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False
        
        return True
    
    def calculate_discount(self, base_price):
        """
        Calculate discount amount.
        
        Args:
            base_price: Base subscription price
            
        Returns:
            Decimal: Discount amount
        """
        from decimal import Decimal
        
        if not self.is_valid():
            return Decimal('0')
        
        if self.discount_type == 'percentage':
            return base_price * (self.value / Decimal('100'))
        
        # Fixed amount - don't exceed base price
        return min(self.value, base_price)


class SubscriptionEventManager(models.Manager):
    """Manager for subscription event queries with tenant scoping."""
    
    def for_subscription(self, subscription):
        """Get events for a specific subscription."""
        return self.filter(subscription=subscription).order_by('-created_at')
    
    def for_tenant(self, tenant):
        """Get events for all subscriptions of a tenant."""
        return self.filter(subscription__tenant=tenant).order_by('-created_at')
    
    def by_type(self, event_type):
        """Get events of a specific type."""
        return self.filter(event_type=event_type)


class SubscriptionEvent(BaseModel):
    """
    Audit trail for subscription lifecycle events.
    
    Tracks all subscription changes for analytics and compliance.
    """
    
    EVENT_TYPE_CHOICES = [
        ('created', 'Created'),
        ('tier_changed', 'Tier Changed'),
        ('renewed', 'Renewed'),
        ('suspended', 'Suspended'),
        ('canceled', 'Canceled'),
        ('reactivated', 'Reactivated'),
        ('payment_failed', 'Payment Failed'),
        ('payment_succeeded', 'Payment Succeeded'),
    ]
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='events',
        help_text="Subscription this event belongs to"
    )
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of event"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Event metadata (e.g., previous_tier, new_tier, reason)"
    )
    
    # Custom manager
    objects = SubscriptionEventManager()
    
    class Meta:
        db_table = 'subscription_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.subscription.tenant.name} - {self.event_type} at {self.created_at}"


class GlobalParty(BaseModel):
    """
    Internal-only linkage of the same phone number across multiple tenants.
    
    Used for deduplication and internal analytics. Never exposed via API.
    Each unique phone number has one GlobalParty record that links to
    multiple Customer records across different tenants.
    """
    
    phone_e164 = EncryptedCharField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text="Encrypted phone number in E.164 format"
    )
    
    class Meta:
        db_table = 'global_parties'
        verbose_name = 'Global Party'
        verbose_name_plural = 'Global Parties'
    
    def __str__(self):
        return f"GlobalParty {self.id}"


class CustomerManager(models.Manager):
    """Manager for customer queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get customers for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def by_phone(self, tenant, phone_e164):
        """Find customer by tenant and phone number."""
        return self.filter(tenant=tenant, phone_e164=phone_e164).first()
    
    def active_in_days(self, tenant, days=7):
        """Get customers active in the last N days."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(tenant=tenant, last_seen_at__gte=cutoff)


class Customer(BaseModel):
    """
    Customer model representing a WhatsApp user within a tenant.
    
    Customers are unique by (tenant_id, phone_e164). The same phone number
    can exist across multiple tenants as separate Customer records.
    
    Each customer has:
    - Encrypted phone number
    - Optional profile information
    - Conversation history
    - Consent preferences
    - Optional link to GlobalParty for internal deduplication
    """
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='customers',
        db_index=True,
        help_text="Tenant this customer belongs to"
    )
    phone_e164 = EncryptedCharField(
        max_length=500,
        db_index=True,
        help_text="Encrypted phone number in E.164 format"
    )
    
    # Profile Information
    name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Customer name (if provided)"
    )
    timezone = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Customer timezone (detected or provided)"
    )
    language = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Preferred language code"
    )
    
    # Metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Customer tags for segmentation (e.g., ['vip', 'new_customer'])"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional customer metadata"
    )
    
    # Payment Preferences
    payment_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Customer payment preferences: {preferred_provider, saved_methods: [{provider, details}]}"
    )
    
    # Consent and Communication Preferences (for LangGraph Agent)
    language_preference = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=[
            ('en', 'English'),
            ('sw', 'Swahili'),
            ('sheng', 'Sheng'),
            ('mixed', 'Mixed'),
        ],
        help_text="Customer's preferred language for conversations"
    )
    marketing_opt_in = models.BooleanField(
        null=True,
        blank=True,
        help_text="Customer consent for marketing communications (null=not set, True=opted in, False=opted out)"
    )
    consent_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed consent flags: {'marketing': True/False, 'notifications': True/False, 'data_processing': True/False}"
    )
    
    # Activity Tracking
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Last interaction timestamp"
    )
    first_interaction_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="First interaction timestamp"
    )
    
    # Internal Linkage (not exposed via API)
    global_party = models.ForeignKey(
        GlobalParty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        help_text="Internal linkage across tenants (not exposed via API)"
    )
    
    # Custom manager
    objects = CustomerManager()
    
    class Meta:
        db_table = 'customers'
        unique_together = [('tenant', 'phone_e164')]
        ordering = ['-last_seen_at']
        indexes = [
            models.Index(fields=['tenant', 'phone_e164']),
            models.Index(fields=['tenant', 'last_seen_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['global_party']),
        ]
    
    def __str__(self):
        name = self.name or 'Unknown'
        return f"{name} ({self.tenant.slug})"
    
    def update_last_seen(self):
        """Update last_seen_at to current time."""
        from django.utils import timezone
        self.last_seen_at = timezone.now()
        if not self.first_interaction_at:
            self.first_interaction_at = self.last_seen_at
        self.save(update_fields=['last_seen_at', 'first_interaction_at'])
    
    def add_tag(self, tag):
        """Add a tag to customer if not already present."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.save(update_fields=['tags'])
    
    def remove_tag(self, tag):
        """Remove a tag from customer."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.save(update_fields=['tags'])
    
    def has_tag(self, tag):
        """Check if customer has a specific tag."""
        return tag in self.tags
    
    def update_consent(self, consent_type, value):
        """Update a specific consent flag."""
        if not self.consent_flags:
            self.consent_flags = {}
        self.consent_flags[consent_type] = value
        self.save(update_fields=['consent_flags'])
    
    def get_consent(self, consent_type, default=None):
        """Get a specific consent flag value."""
        return self.consent_flags.get(consent_type, default)
    
    def has_marketing_consent(self):
        """Check if customer has consented to marketing communications."""
        # Check both the dedicated field and consent_flags
        if self.marketing_opt_in is not None:
            return self.marketing_opt_in
        return self.get_consent('marketing', False)
    
    def opt_out_all(self):
        """Opt customer out of all communications (STOP/UNSUBSCRIBE)."""
        self.marketing_opt_in = False
        self.consent_flags.update({
            'marketing': False,
            'notifications': False,
            'promotional': False
        })
        self.save(update_fields=['marketing_opt_in', 'consent_flags'])
    
    def get_effective_language(self, tenant_default='en'):
        """Get the effective language preference for this customer."""
        return self.language_preference or self.language or tenant_default


class TenantWalletManager(models.Manager):
    """Manager for wallet queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get wallet for a specific tenant."""
        return self.filter(tenant=tenant).first()
    
    def with_balance_above(self, amount):
        """Get wallets with balance above specified amount."""
        return self.filter(balance__gte=amount)


class TenantWallet(BaseModel):
    """
    Wallet for holding tenant funds from facilitated payments.
    
    Each tenant with payment_facilitation enabled has a wallet that:
    - Tracks balance from customer payments (minus platform fees)
    - Supports withdrawals to external accounts
    - Maintains audit trail of all balance changes
    """
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='wallet',
        help_text="Tenant this wallet belongs to"
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Current wallet balance"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code"
    )
    minimum_withdrawal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10,
        help_text="Minimum withdrawal amount"
    )
    
    # Custom manager
    objects = TenantWalletManager()
    
    class Meta:
        db_table = 'tenant_wallets'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} Wallet - {self.currency} {self.balance}"
    
    def has_sufficient_balance(self, amount):
        """Check if wallet has sufficient balance for withdrawal."""
        return self.balance >= amount
    
    def can_withdraw(self, amount):
        """Check if withdrawal amount meets minimum and balance requirements."""
        return amount >= self.minimum_withdrawal and self.has_sufficient_balance(amount)


class TransactionManager(models.Manager):
    """Manager for transaction queries with tenant scoping."""
    
    def for_tenant(self, tenant):
        """Get transactions for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_wallet(self, wallet):
        """Get transactions for a specific wallet."""
        return self.filter(wallet=wallet)
    
    def by_type(self, transaction_type):
        """Get transactions of a specific type."""
        return self.filter(transaction_type=transaction_type)
    
    def by_status(self, status):
        """Get transactions with a specific status."""
        return self.filter(status=status)
    
    def pending_withdrawals(self):
        """Get all pending withdrawal transactions."""
        return self.filter(transaction_type='withdrawal', status='pending')
    
    def completed_in_period(self, start_date, end_date):
        """Get completed transactions in a date range."""
        return self.filter(
            status='completed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )


class Transaction(BaseModel):
    """
    Transaction record for all wallet money movements.
    
    Types:
    - customer_payment: Payment from customer for order/appointment
    - platform_fee: Fee charged by platform on facilitated payment
    - withdrawal: Tenant withdrawal to external account
    - refund: Refund to customer
    - adjustment: Manual balance adjustment by admin
    """
    
    TRANSACTION_TYPE_CHOICES = [
        ('customer_payment', 'Customer Payment'),
        ('platform_fee', 'Platform Fee'),
        ('withdrawal', 'Withdrawal'),
        ('refund', 'Refund'),
        ('adjustment', 'Adjustment'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='transactions',
        db_index=True,
        help_text="Tenant this transaction belongs to"
    )
    wallet = models.ForeignKey(
        TenantWallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        db_index=True,
        help_text="Wallet this transaction affects"
    )
    
    transaction_type = models.CharField(
        max_length=30,
        choices=TRANSACTION_TYPE_CHOICES,
        db_index=True,
        help_text="Type of transaction"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Transaction amount (gross)"
    )
    fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Platform fee (for customer_payment type)"
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Net amount after fees"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Transaction status"
    )
    
    # Reference to related entity (Order, Appointment, etc.)
    reference_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of related entity (e.g., 'order', 'appointment')"
    )
    reference_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of related entity"
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional transaction metadata"
    )
    
    # Notes for admin/audit purposes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about the transaction"
    )
    
    # Four-eyes approval tracking
    initiated_by = models.ForeignKey(
        'rbac.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_transactions',
        help_text="User who initiated the transaction (for four-eyes approval)"
    )
    approved_by = models.ForeignKey(
        'rbac.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transactions',
        help_text="User who approved the transaction (for four-eyes approval)"
    )
    
    # Custom manager
    objects = TransactionManager()
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'transaction_type', 'created_at']),
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['transaction_type', 'status', 'created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.transaction_type} - {self.currency} {self.amount}"
    
    @property
    def currency(self):
        """Get currency from wallet."""
        return self.wallet.currency
    
    def is_completed(self):
        """Check if transaction is completed."""
        return self.status == 'completed'
    
    def is_pending(self):
        """Check if transaction is pending."""
        return self.status == 'pending'
    
    def can_be_canceled(self):
        """Check if transaction can be canceled."""
        return self.status == 'pending'


class WalletAuditManager(models.Manager):
    """Manager for wallet audit queries."""
    
    def for_wallet(self, wallet):
        """Get audit records for a specific wallet."""
        return self.filter(wallet=wallet)
    
    def for_transaction(self, transaction):
        """Get audit record for a specific transaction."""
        return self.filter(transaction=transaction).first()


class WalletAudit(BaseModel):
    """
    Audit trail for all wallet balance changes.
    
    Every transaction that affects wallet balance creates an audit record
    showing the previous balance, change amount, and new balance.
    """
    
    wallet = models.ForeignKey(
        TenantWallet,
        on_delete=models.CASCADE,
        related_name='audit_records',
        db_index=True,
        help_text="Wallet this audit record belongs to"
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='audit_records',
        help_text="Transaction that caused this balance change"
    )
    
    previous_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Balance before transaction"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Amount of change (positive for credit, negative for debit)"
    )
    new_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Balance after transaction"
    )
    
    # Custom manager
    objects = WalletAuditManager()
    
    class Meta:
        db_table = 'wallet_audits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'created_at']),
            models.Index(fields=['transaction']),
        ]
    
    def __str__(self):
        return f"{self.wallet.tenant.name} - {self.amount} ({self.previous_balance} → {self.new_balance})"
    
    def is_credit(self):
        """Check if this is a credit (positive) transaction."""
        return self.amount > 0
    
    def is_debit(self):
        """Check if this is a debit (negative) transaction."""
        return self.amount < 0



class TenantSettings(BaseModel):
    """
    Secure storage for tenant configuration and credentials.
    
    Centralizes all tenant-specific settings including:
    - Integration credentials (encrypted)
    - Payment methods (tokenized references)
    - Notification preferences
    - Feature flags
    - Business settings
    
    Security:
    - Sensitive fields use EncryptedCharField/EncryptedTextField
    - Payment cards stored as Stripe tokens only (PCI-DSS compliant)
    - Access controlled via RBAC (integrations:manage, finance:manage)
    - All credential access is audit logged
    """
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        unique=True,
        related_name='settings',
        help_text="Associated tenant"
    )
    
    # === INTEGRATION CREDENTIALS (Encrypted) ===
    
    # Twilio
    twilio_sid = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Twilio Account SID"
    )
    twilio_token = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Twilio Auth Token"
    )
    twilio_webhook_secret = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Twilio webhook signature secret"
    )
    
    # WooCommerce
    woo_store_url = models.URLField(
        null=True,
        blank=True,
        help_text="WooCommerce store URL"
    )
    woo_consumer_key = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted WooCommerce consumer key"
    )
    woo_consumer_secret = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted WooCommerce consumer secret"
    )
    woo_webhook_secret = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted WooCommerce webhook secret"
    )
    
    # Shopify
    shopify_shop_domain = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Shopify shop domain (e.g., mystore.myshopify.com)"
    )
    shopify_access_token = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Shopify Admin API access token"
    )
    shopify_webhook_secret = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Shopify webhook secret"
    )
    
    # WhatsApp Business API (if different from Twilio)
    whatsapp_business_id = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted WhatsApp Business Account ID"
    )
    whatsapp_access_token = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted WhatsApp Business API access token"
    )
    
    # OpenAI / LLM
    openai_api_key = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted OpenAI API key"
    )
    openai_org_id = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted OpenAI organization ID"
    )
    
    # Together AI
    together_api_key = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Together AI API key"
    )
    
    # Google Gemini
    gemini_api_key = EncryptedCharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Encrypted Google Gemini API key"
    )
    
    # LLM Configuration
    llm_provider = models.CharField(
        max_length=50,
        default='openai',
        help_text="LLM provider to use (openai, together, gemini, etc.)"
    )
    llm_timeout = models.FloatField(
        null=True,
        blank=True,
        help_text="Timeout in seconds for LLM API calls"
    )
    llm_max_retries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of retries for LLM API calls"
    )
    
    # === PAYMENT METHODS (Tokenized - PCI-DSS Compliant) ===
    
    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Stripe customer ID for this tenant"
    )
    stripe_payment_methods = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Stripe PaymentMethod IDs: [{id, last4, brand, exp_month, exp_year, is_default}]"
    )
    
    # Payout account (for tenant earnings)
    payout_method = models.CharField(
        max_length=50,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('mobile_money', 'Mobile Money'),
            ('paypal', 'PayPal'),
        ],
        null=True,
        blank=True,
        help_text="Payout method for tenant earnings"
    )
    payout_details = EncryptedTextField(
        null=True,
        blank=True,
        help_text="Encrypted JSON with payout account details"
    )
    
    # === NOTIFICATION PREFERENCES ===
    
    notification_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification preferences by channel and event type"
    )
    
    # === FEATURE FLAGS & PREFERENCES ===
    
    feature_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature flags for gradual rollout and A/B testing"
    )
    
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="Business hours by day of week"
    )
    
    # === INTEGRATION STATUS ===
    
    integrations_status = models.JSONField(
        default=dict,
        blank=True,
        help_text="Status and metadata for each integration"
    )
    
    # === BRANDING & CUSTOMIZATION ===
    
    branding = models.JSONField(
        default=dict,
        blank=True,
        help_text="Branding and customization settings"
    )
    
    # === COMPLIANCE & LEGAL ===
    
    compliance_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="GDPR, data retention, and legal compliance settings"
    )
    
    # === ONBOARDING TRACKING ===
    
    onboarding_status = models.JSONField(
        default=dict,
        blank=True,
        help_text="Onboarding step completion status with timestamps"
    )
    onboarding_completed = models.BooleanField(
        default=False,
        help_text="Whether all required onboarding steps are complete"
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was completed"
    )
    
    # === ADDITIONAL METADATA ===
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional settings metadata (payment provider credentials, etc.)"
    )
    
    # === FEATURE FLAGS ===
    
    feature_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature flags for gradual rollout and A/B testing"
    )
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"
    
    # === HELPER METHODS ===
    
    def has_woocommerce_configured(self) -> bool:
        """Check if WooCommerce credentials are set."""
        return bool(
            self.woo_store_url and 
            self.woo_consumer_key and 
            self.woo_consumer_secret
        )
    
    def has_shopify_configured(self) -> bool:
        """Check if Shopify credentials are set."""
        return bool(
            self.shopify_shop_domain and 
            self.shopify_access_token
        )
    
    def has_twilio_configured(self) -> bool:
        """Check if Twilio credentials are set."""
        return bool(
            self.twilio_sid and 
            self.twilio_token
        )
    
    def get_default_payment_method(self):
        """Get default Stripe payment method."""
        for pm in self.stripe_payment_methods:
            if pm.get('is_default'):
                return pm
        return self.stripe_payment_methods[0] if self.stripe_payment_methods else None
    
    def is_notification_enabled(self, channel: str, event: str) -> bool:
        """
        Check if notification is enabled for channel and event.
        
        Args:
            channel: Notification channel (email, sms, in_app)
            event: Event type (order_received, low_stock, etc.)
            
        Returns:
            bool: True if notification is enabled
        """
        return self.notification_settings.get(channel, {}).get(event, False)
    
    def is_feature_enabled(self, feature: str) -> bool:
        """
        Check if feature flag is enabled.
        
        Args:
            feature: Feature name
            
        Returns:
            bool: True if feature is enabled
        """
        return self.feature_flags.get(feature, False)
    
    def get_integration_status(self, integration: str) -> dict:
        """
        Get status for a specific integration.
        
        Args:
            integration: Integration name (woocommerce, shopify, etc.)
            
        Returns:
            dict: Integration status and metadata
        """
        return self.integrations_status.get(integration, {})
    
    def update_integration_status(self, integration: str, status_data: dict):
        """
        Update status for a specific integration.
        
        Args:
            integration: Integration name
            status_data: Status data to update
        """
        if integration not in self.integrations_status:
            self.integrations_status[integration] = {}
        
        self.integrations_status[integration].update(status_data)
        self.save(update_fields=['integrations_status', 'updated_at'])
    
    def initialize_onboarding_status(self):
        """
        Initialize onboarding status with all steps marked as incomplete.
        
        This should be called when a new tenant is created.
        """
        self.onboarding_status = {
            'twilio_configured': {'completed': False, 'completed_at': None},
            'payment_method_added': {'completed': False, 'completed_at': None},
            'business_settings_configured': {'completed': False, 'completed_at': None},
            'woocommerce_configured': {'completed': False, 'completed_at': None},
            'shopify_configured': {'completed': False, 'completed_at': None},
            'payout_method_configured': {'completed': False, 'completed_at': None},
        }
        self.save(update_fields=['onboarding_status', 'updated_at'])
