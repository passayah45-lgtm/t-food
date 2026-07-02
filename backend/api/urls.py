from django.urls import path, include
from .health_views import HealthView

urlpatterns = [
    path('health/', HealthView.as_view(), name='api_health'),
    path('auth/',          include('api.auth_urls')),
    path('users/',         include('api.user_urls')),
    path('restaurants/',   include('api.restaurant_urls')),
    path('merchants/',     include('api.merchant_urls')),
    path('orders/',        include('api.order_urls')),
    path('payments/',      include('api.payment_urls')),
    path('delivery/',      include('api.delivery_urls')),
    path('markets/',       include('markets.urls')),
    path('notifications/', include('api.notification_urls')),
    path('preferences/',   include('user_preferences.urls')),
    path('operations/',    include('api.operations_urls')),
    path('verifications/', include('api.verification_urls')),
    path('intelligence/',  include('intelligence.urls')),
    path('support/',       include('api.support_urls')),
]
