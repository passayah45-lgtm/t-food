from django.urls import path
from .views import restaurant_menu, restaurant_list

urlpatterns = [
    path('', restaurant_list, name='restaurant_list'),
    path('<int:restaurant_id>/', restaurant_menu, name='restaurant_menu'),
]
