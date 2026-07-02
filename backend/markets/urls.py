from django.urls import path

from .api_views import CommerceAreaListView, CommerceCityListView, MarketListView


urlpatterns = [
    path('', MarketListView.as_view(), name='api_market_list'),
    path('cities/', CommerceCityListView.as_view(), name='api_market_cities'),
    path('areas/', CommerceAreaListView.as_view(), name='api_market_areas'),
]
