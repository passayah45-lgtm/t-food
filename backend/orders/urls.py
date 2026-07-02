from django.urls import path
from . import views

urlpatterns = [
     path('', views.order_list, name='order_list'),
    path('cart/', views.view_cart, name='view_cart'),

    path('add-to-cart/<int:food_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:food_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),

    path('increase/<int:food_id>/', views.increase_quantity, name='increase_quantity'),
    path('decrease/<int:food_id>/', views.decrease_quantity, name='decrease_quantity'),

    path('place-order/', views.place_order, name='place_order'),
    path('order-success/', views.order_success, name='order_success'),
]
