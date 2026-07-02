from django.urls import path
from . import views

urlpatterns = [
    path(
        'partner/dashboard/',
        views.partner_dashboard,
        name='partner_dashboard'   
    ),
     path('update/<int:delivery_id>/', views.update_delivery_status, name='update_delivery_status'),
     # TRACKING
    path('update-location/<int:delivery_id>/', views.update_location, name='update_location'),
    path('track/<int:order_id>/', views.track_order, name='track_order'),
    path('location/<int:order_id>/', views.get_delivery_location, name='get_delivery_location'),
]
