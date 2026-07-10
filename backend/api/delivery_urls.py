from django.urls import path
from .delivery_views import (
    AvailableDeliveryClaimView,
    AvailableDeliveryListView,
    PartnerDeliveryListView,
    PartnerDeliveryLocationView,
    PartnerDeliveryStatusView,
    PartnerAvailabilityLocationView,
    PartnerEarningsSummaryView,
    PartnerMerchantInviteListView,
)

urlpatterns = [
    path('available/', AvailableDeliveryListView.as_view(), name='api_available_deliveries'),
    path('availability/location/', PartnerAvailabilityLocationView.as_view(), name='api_partner_availability_location'),
    path('available/<int:delivery_id>/claim/', AvailableDeliveryClaimView.as_view(), name='api_claim_delivery'),
    path('partner/', PartnerDeliveryListView.as_view(), name='api_partner_deliveries'),
    path('partner/earnings/', PartnerEarningsSummaryView.as_view(), name='api_partner_earnings'),
    path('partner/merchant-invites/', PartnerMerchantInviteListView.as_view(), name='api_partner_merchant_invites'),
    path(
        'partner/<int:delivery_id>/status/',
        PartnerDeliveryStatusView.as_view(),
        name='api_partner_delivery_status',
    ),
    path(
        'partner/<int:delivery_id>/location/',
        PartnerDeliveryLocationView.as_view(),
        name='api_partner_delivery_location',
    ),
]
