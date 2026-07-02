import json

from payments.gateway import (
    create_razorpay_order,
    verify_razorpay_signature,
    verify_razorpay_webhook_signature,
)

from .base import PaymentProvider


class RazorpayProvider(PaymentProvider):
    code = 'razorpay'
    display_name = 'Razorpay'

    def supported_countries(self):
        return ('IN',)

    def supported_currencies(self):
        return ('INR',)

    def supported_payment_methods(self):
        return ('CARD', 'UPI', 'WALLET')

    def capabilities(self):
        return {
            **super().capabilities(),
            'create_payment': True,
            'customer_confirmation': True,
            'webhook': True,
            'refund': False,
        }

    def create_payment(self, order, payment):
        return create_razorpay_order(order)

    def verify_customer_confirmation(self, payment, payload):
        provider_order_id = payload.get('razorpay_order_id', '')
        payment_id = payload.get('razorpay_payment_id', '')
        signature = payload.get('razorpay_signature', '')
        return (
            provider_order_id == payment.provider_order_id
            and bool(payment_id)
            and bool(signature)
            and verify_razorpay_signature(provider_order_id, payment_id, signature)
        )

    def verify_webhook(self, request):
        return verify_razorpay_webhook_signature(
            request.body,
            request.headers.get('X-Razorpay-Signature', ''),
        )

    def parse_webhook_event(self, request):
        return json.loads(request.body.decode())
