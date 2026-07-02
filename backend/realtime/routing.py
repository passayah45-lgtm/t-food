from django.urls import path

from .consumers import OrdersConsumer


websocket_urlpatterns = [
    path('ws/orders/', OrdersConsumer.as_asgi()),
]
