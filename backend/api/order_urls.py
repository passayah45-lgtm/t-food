from django.urls import path
from .order_views import (
    OfferValidationView,
    OrderCancelView,
    OrderDetailView,
    OrderListCreateView,
    OrderReorderView,
)

urlpatterns = [
    path('', OrderListCreateView.as_view(), name='api_order_list_create'),
    path('offers/validate/', OfferValidationView.as_view(), name='api_offer_validate'),
    path('<int:pk>/', OrderDetailView.as_view(), name='api_order_detail'),
    path('<int:order_id>/cancel/', OrderCancelView.as_view(), name='api_order_cancel'),
    path('<int:order_id>/reorder/', OrderReorderView.as_view(), name='api_order_reorder'),
]
