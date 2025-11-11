"""
URL configuration for catalog app.
"""
from django.urls import path
from apps.catalog.views import (
    ProductListView, ProductDetailView,
    ProductVariantListView, ProductVariantDetailView,
    WooCommerceSyncView, ShopifySyncView
)

app_name = 'catalog'

urlpatterns = [
    # Product endpoints
    path('products', ProductListView.as_view(), name='product-list'),
    path('products/<uuid:product_id>', ProductDetailView.as_view(), name='product-detail'),
    
    # Product variant endpoints
    path('products/<uuid:product_id>/variants', ProductVariantListView.as_view(), name='variant-list'),
    path('products/<uuid:product_id>/variants/<uuid:variant_id>', ProductVariantDetailView.as_view(), name='variant-detail'),
    
    # Catalog sync endpoints
    path('catalog/sync/woocommerce', WooCommerceSyncView.as_view(), name='sync-woocommerce'),
    path('catalog/sync/shopify', ShopifySyncView.as_view(), name='sync-shopify'),
]
