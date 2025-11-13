"""
Serializers for tenant and wallet API endpoints.
"""
from rest_framework import serializers
from apps.tenants.models import (
    Tenant, TenantWallet, Transaction, WalletAudit
)


class TenantWalletSerializer(serializers.ModelSerializer):
    """Serializer for TenantWallet."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = TenantWallet
        fields = [
            'id', 'tenant', 'tenant_name', 'balance', 'currency',
            'minimum_withdrawal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_name', 'created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    currency = serializers.CharField(read_only=True)
    initiated_by_email = serializers.CharField(source='initiated_by.email', read_only=True, allow_null=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'tenant', 'tenant_name', 'wallet', 'transaction_type',
            'amount', 'fee', 'net_amount', 'currency', 'status',
            'reference_type', 'reference_id', 'metadata', 'notes',
            'initiated_by', 'initiated_by_email', 'approved_by', 'approved_by_email',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'tenant_name', 'wallet', 'currency',
            'initiated_by', 'initiated_by_email', 'approved_by', 'approved_by_email',
            'created_at', 'updated_at'
        ]


class WalletBalanceSerializer(serializers.Serializer):
    """Serializer for wallet balance response."""
    
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    minimum_withdrawal = serializers.DecimalField(max_digits=10, decimal_places=2)


class WithdrawalRequestSerializer(serializers.Serializer):
    """Serializer for withdrawal request."""
    
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        help_text="Withdrawal amount"
    )
    bank_account = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Bank account information"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes"
    )


class WithdrawalProcessSerializer(serializers.Serializer):
    """Serializer for processing withdrawal (admin)."""
    
    action = serializers.ChoiceField(
        choices=['complete', 'fail'],
        help_text="Action to take: complete or fail"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for failure (required if action is 'fail')"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Admin notes"
    )
    
    def validate(self, data):
        """Validate that reason is provided when failing withdrawal."""
        if data['action'] == 'fail' and not data.get('reason'):
            raise serializers.ValidationError({
                'reason': 'Reason is required when failing a withdrawal'
            })
        return data


class WithdrawalApprovalSerializer(serializers.Serializer):
    """Serializer for withdrawal approval with four-eyes validation."""
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Approval notes"
    )


class TransactionFilterSerializer(serializers.Serializer):
    """Serializer for transaction filtering parameters."""
    
    transaction_type = serializers.ChoiceField(
        choices=[
            'customer_payment', 'platform_fee', 'withdrawal', 'refund', 'adjustment'
        ],
        required=False,
        help_text="Filter by transaction type"
    )
    status = serializers.ChoiceField(
        choices=['pending', 'completed', 'failed', 'canceled'],
        required=False,
        help_text="Filter by status"
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Filter by start date (YYYY-MM-DD)"
    )
    end_date = serializers.DateField(
        required=False,
        help_text="Filter by end date (YYYY-MM-DD)"
    )
    page = serializers.IntegerField(
        required=False,
        min_value=1,
        default=1,
        help_text="Page number"
    )
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=50,
        help_text="Number of items per page"
    )



class AdminTenantListSerializer(serializers.ModelSerializer):
    """Serializer for admin tenant list view."""
    
    tier_name = serializers.CharField(source='subscription_tier.name', read_only=True, allow_null=True)
    subscription_status = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'status', 'tier_name',
            'subscription_status', 'subscription_waived',
            'trial_start_date', 'trial_end_date',
            'whatsapp_number', 'contact_email', 'contact_phone',
            'wallet_balance', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_subscription_status(self, obj):
        """Get subscription status."""
        try:
            if hasattr(obj, 'subscription'):
                return obj.subscription.status
            return None
        except:
            return None
    
    def get_wallet_balance(self, obj):
        """Get wallet balance if exists."""
        try:
            if hasattr(obj, 'wallet'):
                return {
                    'balance': float(obj.wallet.balance),
                    'currency': obj.wallet.currency
                }
            return None
        except:
            return None


class AdminTenantDetailSerializer(serializers.ModelSerializer):
    """Serializer for admin tenant detail view."""
    
    tier_name = serializers.CharField(source='subscription_tier.name', read_only=True, allow_null=True)
    subscription = serializers.SerializerMethodField()
    wallet = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'status', 'subscription_tier', 'tier_name',
            'subscription_waived', 'trial_start_date', 'trial_end_date',
            'whatsapp_number', 'contact_email', 'contact_phone',
            'timezone', 'quiet_hours_start', 'quiet_hours_end',
            'allowed_origins', 'subscription', 'wallet',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_subscription(self, obj):
        """Get subscription details."""
        try:
            if hasattr(obj, 'subscription'):
                sub = obj.subscription
                return {
                    'id': str(sub.id),
                    'tier': sub.tier.name,
                    'billing_cycle': sub.billing_cycle,
                    'status': sub.status,
                    'start_date': sub.start_date,
                    'next_billing_date': sub.next_billing_date,
                }
            return None
        except:
            return None
    
    def get_wallet(self, obj):
        """Get wallet details."""
        try:
            if hasattr(obj, 'wallet'):
                wallet = obj.wallet
                return {
                    'id': str(wallet.id),
                    'balance': float(wallet.balance),
                    'currency': wallet.currency,
                    'minimum_withdrawal': float(wallet.minimum_withdrawal),
                }
            return None
        except:
            return None


class AdminSubscriptionChangeSerializer(serializers.Serializer):
    """Serializer for admin subscription tier change."""
    
    tier_id = serializers.UUIDField(
        required=True,
        help_text="ID of the new subscription tier"
    )
    billing_cycle = serializers.ChoiceField(
        choices=['monthly', 'yearly'],
        required=False,
        default='monthly',
        help_text="Billing cycle"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Admin notes for the change"
    )


class AdminSubscriptionWaiverSerializer(serializers.Serializer):
    """Serializer for admin subscription waiver."""
    
    waived = serializers.BooleanField(
        required=True,
        help_text="Whether to waive subscription fees"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Admin notes for the waiver"
    )


# === TENANT MANAGEMENT SERIALIZERS ===

class TenantListSerializer(serializers.ModelSerializer):
    """Serializer for tenant list view."""
    
    role = serializers.SerializerMethodField()
    onboarding_status = serializers.SerializerMethodField()
    tier_name = serializers.CharField(source='subscription_tier.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'status', 'tier_name',
            'whatsapp_number', 'role', 'onboarding_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_role(self, obj):
        """Get user's primary role in this tenant."""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return None
        
        from apps.rbac.models import TenantUser
        tenant_user = TenantUser.objects.get_membership(obj, request.user)
        if not tenant_user:
            return None
        
        # Get first role (primary role)
        user_role = tenant_user.user_roles.select_related('role').first()
        return user_role.role.name if user_role else None
    
    def get_onboarding_status(self, obj):
        """Get onboarding completion status."""
        try:
            if hasattr(obj, 'settings'):
                onboarding = obj.settings.integrations_status.get('onboarding', {})
                if onboarding.get('status') == 'complete':
                    return {'completed': True, 'completion_percentage': 100}
                
                # Calculate completion percentage
                steps = onboarding.get('steps', {})
                total_steps = len(steps)
                completed_steps = sum(1 for step in steps.values() if step.get('completed'))
                
                return {
                    'completed': False,
                    'completion_percentage': int((completed_steps / total_steps * 100)) if total_steps > 0 else 0
                }
            return {'completed': False, 'completion_percentage': 0}
        except:
            return {'completed': False, 'completion_percentage': 0}


class TenantDetailSerializer(serializers.ModelSerializer):
    """Serializer for tenant detail view."""
    
    role = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    onboarding_status = serializers.SerializerMethodField()
    tier_name = serializers.CharField(source='subscription_tier.name', read_only=True, allow_null=True)
    subscription = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'status', 'subscription_tier', 'tier_name',
            'subscription_waived', 'trial_start_date', 'trial_end_date',
            'whatsapp_number', 'contact_email', 'contact_phone',
            'timezone', 'quiet_hours_start', 'quiet_hours_end',
            'role', 'roles', 'onboarding_status', 'subscription',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_role(self, obj):
        """Get user's primary role in this tenant."""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return None
        
        from apps.rbac.models import TenantUser
        tenant_user = TenantUser.objects.get_membership(obj, request.user)
        if not tenant_user:
            return None
        
        # Get first role (primary role)
        user_role = tenant_user.user_roles.select_related('role').first()
        return user_role.role.name if user_role else None
    
    def get_roles(self, obj):
        """Get all user's roles in this tenant."""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return []
        
        from apps.rbac.models import TenantUser
        tenant_user = TenantUser.objects.get_membership(obj, request.user)
        if not tenant_user:
            return []
        
        return [ur.role.name for ur in tenant_user.user_roles.select_related('role')]
    
    def get_onboarding_status(self, obj):
        """Get detailed onboarding status."""
        try:
            if hasattr(obj, 'settings'):
                onboarding = obj.settings.integrations_status.get('onboarding', {})
                if onboarding.get('status') == 'complete':
                    return {
                        'completed': True,
                        'completion_percentage': 100,
                        'pending_steps': []
                    }
                
                # Calculate completion and pending steps
                steps = onboarding.get('steps', {})
                total_steps = len(steps)
                completed_steps = sum(1 for step in steps.values() if step.get('completed'))
                pending_steps = [name for name, data in steps.items() if not data.get('completed')]
                
                return {
                    'completed': False,
                    'completion_percentage': int((completed_steps / total_steps * 100)) if total_steps > 0 else 0,
                    'pending_steps': pending_steps
                }
            return {'completed': False, 'completion_percentage': 0, 'pending_steps': []}
        except:
            return {'completed': False, 'completion_percentage': 0, 'pending_steps': []}
    
    def get_subscription(self, obj):
        """Get subscription details."""
        try:
            if hasattr(obj, 'subscription'):
                sub = obj.subscription
                return {
                    'id': str(sub.id),
                    'tier': sub.tier.name,
                    'billing_cycle': sub.billing_cycle,
                    'status': sub.status,
                    'start_date': sub.start_date,
                    'next_billing_date': sub.next_billing_date,
                }
            return None
        except:
            return None


class TenantCreateSerializer(serializers.Serializer):
    """Serializer for tenant creation."""
    
    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Business name"
    )
    slug = serializers.SlugField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="URL-friendly identifier (auto-generated if not provided)"
    )
    whatsapp_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        help_text="WhatsApp business number in E.164 format (optional)"
    )
    
    def validate_name(self, value):
        """Validate business name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Business name cannot be empty")
        return value.strip()
    
    def validate_slug(self, value):
        """Validate slug is unique if provided."""
        if value:
            from apps.tenants.models import Tenant
            if Tenant.objects.filter(slug=value).exists():
                raise serializers.ValidationError(f"Slug '{value}' is already taken")
        return value
    
    def validate_whatsapp_number(self, value):
        """Validate WhatsApp number format if provided."""
        if value:
            # Basic E.164 validation
            if not value.startswith('+'):
                raise serializers.ValidationError("WhatsApp number must be in E.164 format (start with +)")
            if not value[1:].isdigit():
                raise serializers.ValidationError("WhatsApp number must contain only digits after +")
            if len(value) < 8 or len(value) > 16:
                raise serializers.ValidationError("WhatsApp number must be between 8 and 16 characters")
        return value


class TenantUpdateSerializer(serializers.Serializer):
    """Serializer for tenant update."""
    
    name = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Business name"
    )
    contact_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        help_text="Primary contact email"
    )
    contact_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        help_text="Primary contact phone"
    )
    timezone = serializers.CharField(
        max_length=50,
        required=False,
        help_text="Tenant timezone"
    )
    
    def validate_name(self, value):
        """Validate business name is not empty."""
        if value is not None and (not value or not value.strip()):
            raise serializers.ValidationError("Business name cannot be empty")
        return value.strip() if value else value


class TenantMemberSerializer(serializers.Serializer):
    """Serializer for tenant member."""
    
    id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    roles = serializers.SerializerMethodField()
    invite_status = serializers.CharField(read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)
    last_seen_at = serializers.DateTimeField(read_only=True)
    
    def get_roles(self, obj):
        """Get user's roles in this tenant."""
        return [ur.role.name for ur in obj.user_roles.select_related('role')]


class TenantMemberInviteSerializer(serializers.Serializer):
    """Serializer for inviting a member to tenant."""
    
    email = serializers.EmailField(
        required=True,
        help_text="Email address of user to invite"
    )
    roles = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        help_text="List of role names to assign (e.g., ['Admin', 'Catalog Manager'])"
    )
    
    def validate_email(self, value):
        """Validate email format."""
        return value.lower().strip()
    
    def validate_roles(self, value):
        """Validate roles list is not empty."""
        if not value:
            raise serializers.ValidationError("At least one role must be specified")
        return value
