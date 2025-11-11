"""
URL configuration for orders API endpoints.
"""
from django.urls import path
from apps.orders.views import OrderListView, OrderDetailView

urlpatterns = [
    # Order endpoints
    path('', OrderListView.as_view(), name='order-list'),
    path('<uuid:order_id>', OrderDetailView.as_view(), name='order-detail'),
]
