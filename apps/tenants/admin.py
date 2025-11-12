"""
Django admin configuration for tenants app.
"""
from django.contrib import admin
from .models import (
    Tenant, TenantSettings, SubscriptionTier, Subscription,
    SubscriptionDiscount, SubscriptionEvent,
    TenantWallet, Transaction, WalletAudit, Customer, GlobalParty
)

# Register models with default admin
admin.site.register(Tenant)
admin.site.register(TenantSettings)
admin.site.register(SubscriptionTier)
admin.site.register(Subscription)
admin.site.register(SubscriptionDiscount)
admin.site.register(SubscriptionEvent)
admin.site.register(TenantWallet)
admin.site.register(Transaction)
admin.site.register(WalletAudit)
admin.site.register(Customer)
admin.site.register(GlobalParty)
