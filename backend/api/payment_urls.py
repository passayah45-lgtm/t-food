from django.urls import path
from .payment_views import (
    OrderPaymentVerifyView,
    OrderPaymentView,
    PaymentConfigView,
    RazorpayWebhookView,
)

urlpatterns = [
    path('config/', PaymentConfigView.as_view(), name='api_payment_config'),
    path('webhooks/razorpay/', RazorpayWebhookView.as_view(), name='razorpay_webhook'),
    path('orders/<int:order_id>/', OrderPaymentView.as_view(), name='api_order_payment'),
    path(
        'orders/<int:order_id>/verify/',
        OrderPaymentVerifyView.as_view(),
        name='api_order_payment_verify',
    ),
]
