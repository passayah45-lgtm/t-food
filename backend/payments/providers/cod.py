from markets.models import Market

from .base import PaymentProvider


class CODProvider(PaymentProvider):
    code = 'cod'
    display_name = 'Cash on Delivery'

    def supported_countries(self):
        countries = list(
            Market.objects.filter(is_active=True)
            .values_list('country_code', flat=True)
            .distinct()
        )
        return tuple(countries) or ('*',)

    def supported_currencies(self):
        currencies = list(
            Market.objects.filter(is_active=True)
            .values_list('default_currency__code', flat=True)
            .distinct()
        )
        return tuple(currencies) or ('*',)

    def supported_payment_methods(self):
        return ('COD',)

    def capabilities(self):
        return {
            **super().capabilities(),
            'create_payment': True,
            'customer_confirmation': True,
            'cash_collection': True,
            'online_capture': False,
            'webhook': False,
            'refund': False,
        }

    def create_payment(self, order, payment):
        return {
            'payment_required': False,
            'provider': self.code,
            'order_id': order.id,
        }

    def verify_customer_confirmation(self, payment, payload):
        return True

    def verify_webhook(self, request):
        return False

    def parse_webhook_event(self, request):
        return None
