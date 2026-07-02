from django.urls import path
from .user_views import (
    ChangePasswordView,
    CustomerProfileView,
    DeliveryAddressDetailView,
    DeliveryAddressListCreateView,
    DeliveryPartnerProfileView,
)

urlpatterns = [
    path('profile/',         CustomerProfileView.as_view(),       name='api_customer_profile'),
    path('partner/profile/', DeliveryPartnerProfileView.as_view(), name='api_partner_profile'),
    path('change-password/', ChangePasswordView.as_view(),        name='api_change_password'),
    path('addresses/', DeliveryAddressListCreateView.as_view(), name='api_addresses'),
    path('addresses/<int:pk>/', DeliveryAddressDetailView.as_view(), name='api_address_detail'),
]
