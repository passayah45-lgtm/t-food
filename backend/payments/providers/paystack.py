from .base import ExternalPaymentProvider


class PaystackProvider(ExternalPaymentProvider):
    code = 'paystack'
    display_name = 'Paystack'
    countries = ('NG', 'GH', 'ZA', 'KE')
    currencies = ('NGN', 'GHS', 'ZAR', 'KES', 'USD')
    payment_methods = ('CARD', 'BANK_TRANSFER', 'MOBILE_MONEY')
    required_credentials = ('public_key', 'secret_key', 'webhook_secret')

    def build_create_payment_payload(self, order, payment):
        payload = super().build_create_payment_payload(order, payment)
        payload.update({
            'reference': f'tfood-order-{order.id}-payment-{payment.id}',
            'channels': ['card', 'bank', 'mobile_money'],
        })
        return payload
