from .base import ExternalPaymentProvider


class WaveProvider(ExternalPaymentProvider):
    code = 'wave'
    display_name = 'Wave'
    countries = ('GN', 'SN', 'CI')
    currencies = ('GNF', 'XOF')
    payment_methods = ('MOBILE_MONEY', 'WALLET')
    required_credentials = ('api_key', 'webhook_secret')

    def build_create_payment_payload(self, order, payment):
        payload = super().build_create_payment_payload(order, payment)
        payload.update({
            'checkout_reference': f'tfood-order-{order.id}-payment-{payment.id}',
            'customer_phone': order.contact_phone,
        })
        return payload
