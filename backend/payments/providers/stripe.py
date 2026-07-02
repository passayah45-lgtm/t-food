from .base import ExternalPaymentProvider


class StripeProvider(ExternalPaymentProvider):
    code = 'stripe'
    display_name = 'Stripe'
    countries = ('US', 'GB', 'FR', 'DE', 'ES', 'IT', 'NL', 'IE')
    currencies = ('USD', 'EUR', 'GBP')
    payment_methods = ('CARD', 'WALLET')
    required_credentials = ('publishable_key', 'secret_key', 'webhook_secret')

    def build_create_payment_payload(self, order, payment):
        payload = super().build_create_payment_payload(order, payment)
        payload.update({
            'mode': 'payment',
            'payment_method_types': ['card'],
            'client_reference_id': str(order.id),
        })
        return payload
