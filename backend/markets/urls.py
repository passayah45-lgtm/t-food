from django.urls import path

from .api_views import (
    CommerceAreaListView,
    CommerceCityListView,
    CurrencyListCreateView,
    MarketListView,
)


urlpatterns = [
    path('', MarketListView.as_view(), name='api_market_list'),
    path('currencies/', CurrencyListCreateView.as_view(), name='api_currency_list'),
    path('cities/', CommerceCityListView.as_view(), name='api_market_cities'),
    path('areas/', CommerceAreaListView.as_view(), name='api_market_areas'),
]
