from django.urls import path
from .views import payment_page, payment_success

urlpatterns = [
    path('<int:order_id>/', payment_page, name='payment_page'),
    path('success/<int:order_id>/', payment_success, name='payment_success'),
]
    

