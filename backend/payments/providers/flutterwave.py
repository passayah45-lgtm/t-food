from .base import ExternalPaymentProvider


class FlutterwaveProvider(ExternalPaymentProvider):
    code = 'flutterwave'
    display_name = 'Flutterwave'
    countries = ('NG', 'GH', 'KE', 'UG', 'TZ', 'RW', 'ZA')
    currencies = ('NGN', 'GHS', 'KES', 'UGX', 'TZS', 'RWF', 'ZAR', 'USD')
    payment_methods = ('CARD', 'BANK_TRANSFER', 'MOBILE_MONEY')
    required_credentials = ('public_key', 'secret_key', 'encryption_key', 'webhook_secret')

    def build_create_payment_payload(self, order, payment):
        payload = super().build_create_payment_payload(order, payment)
        payload.update({
            'tx_ref': f'tfood-order-{order.id}-payment-{payment.id}',
            'redirect_url': '',
            'payment_options': 'card,banktransfer,mobilemoney',
        })
        return payload
