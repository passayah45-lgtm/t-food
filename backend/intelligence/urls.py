from django.urls import path

from .views import (
    AssistantChatView,
    CustomerRecommendationsView,
    MerchantInsightsView,
    OperationsInsightsView,
    RecommendationEventCreateView,
    SearchEventCreateView,
    VisualProductSearchView,
)


urlpatterns = [
    path('assistant/', AssistantChatView.as_view(), name='intelligence_assistant'),
    path('events/', RecommendationEventCreateView.as_view(), name='intelligence_events'),
    path('search-events/', SearchEventCreateView.as_view(), name='intelligence_search_events'),
    path(
        'visual-product-search/',
        VisualProductSearchView.as_view(),
        name='visual_product_search',
    ),
    path(
        'customer/recommendations/',
        CustomerRecommendationsView.as_view(),
        name='intelligence_customer_recommendations',
    ),
    path(
        'merchant/insights/',
        MerchantInsightsView.as_view(),
        name='intelligence_merchant_insights',
    ),
    path(
        'operations/insights/',
        OperationsInsightsView.as_view(),
        name='intelligence_operations_insights',
    ),
]
