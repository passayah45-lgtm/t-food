from dataclasses import dataclass


class PaymentProviderError(Exception):
    pass


class PaymentProviderUnavailable(PaymentProviderError):
    pass


@dataclass(frozen=True)
class ProviderCapability:
    code: str
    display_name: str
    countries: tuple[str, ...]
    currencies: tuple[str, ...]
    payment_methods: tuple[str, ...]
    capabilities: dict


class PaymentProvider:
    code = ''
    display_name = ''
    active = True

    def supported_countries(self):
        return ()

    def supported_currencies(self):
        return ()

    def supported_payment_methods(self):
        return ()

    def capabilities(self):
        return {
            'create_payment': False,
            'customer_confirmation': False,
            'webhook': False,
            'refund': False,
            'live': self.active,
        }

    def capability(self):
        return ProviderCapability(
            code=self.code,
            display_name=self.display_name,
            countries=tuple(self.supported_countries()),
            currencies=tuple(self.supported_currencies()),
            payment_methods=tuple(self.supported_payment_methods()),
            capabilities=dict(self.capabilities()),
        )

    def supports(self, *, country=None, currency=None, payment_method=None):
        countries = {item.upper() for item in self.supported_countries()}
        currencies = {item.upper() for item in self.supported_currencies()}
        methods = {item.upper() for item in self.supported_payment_methods()}
        return (
            (not country or '*' in countries or country.upper() in countries)
            and (not currency or '*' in currencies or currency.upper() in currencies)
            and (
                not payment_method
                or '*' in methods
                or payment_method.upper() in methods
            )
        )

    def create_payment(self, order, payment):
        raise PaymentProviderUnavailable(
            f'{self.display_name or self.code} cannot create payments.'
        )

    def verify_customer_confirmation(self, payment, payload):
        raise PaymentProviderUnavailable(
            f'{self.display_name or self.code} does not support customer confirmation.'
        )

    def verify_webhook(self, request):
        raise PaymentProviderUnavailable(
            f'{self.display_name or self.code} does not support webhooks.'
        )

    def parse_webhook_event(self, request):
        raise PaymentProviderUnavailable(
            f'{self.display_name or self.code} does not support webhooks.'
        )

    def refund(self, payment, amount, reason):
        raise PaymentProviderUnavailable(
            f'{self.display_name or self.code} does not support refunds yet.'
        )


class CapabilityOnlyProvider(PaymentProvider):
    active = False
    countries = ()
    currencies = ()
    payment_methods = ()

    def supported_countries(self):
        return self.countries

    def supported_currencies(self):
        return self.currencies

    def supported_payment_methods(self):
        return self.payment_methods

    def capabilities(self):
        return {
            **super().capabilities(),
            'configuration_only': True,
        }


class ExternalPaymentProvider(PaymentProvider):
    active = False
    countries = ()
    currencies = ()
    payment_methods = ()
    required_credentials = ()

    def supported_countries(self):
        return self.countries

    def supported_currencies(self):
        return self.currencies

    def supported_payment_methods(self):
        return self.payment_methods

    def credential_fields(self):
        return self.required_credentials

    def credentials_required(self):
        return bool(self.required_credentials)

    def validate_credentials(self, config=None):
        config = config or {}
        missing = [
            field
            for field in self.required_credentials
            if not config.get(field)
        ]
        return {
            'is_configured': not missing,
            'missing_fields': tuple(missing),
        }

    def capabilities(self):
        return {
            **super().capabilities(),
            'create_payment': True,
            'customer_confirmation': False,
            'webhook': True,
            'refund': True,
            'configuration_required': True,
            'external_api_calls_enabled': False,
        }

    def _provider_not_configured(self):
        raise PaymentProviderUnavailable('Provider not configured for live payments.')

    def _currency_for_order(self, order):
        market = getattr(order, 'market', None)
        if market and market.default_currency_id:
            return market.default_currency.code
        return ''

    def build_create_payment_payload(self, order, payment):
        return {
            'provider': self.code,
            'order_id': order.id,
            'payment_id': payment.id,
            'amount': str(order.total_amount),
            'currency': self._currency_for_order(order),
            'payment_method': payment.method,
            'customer': {
                'id': order.customer_id,
                'email': getattr(order.customer, 'email', ''),
                'phone': getattr(order, 'contact_phone', ''),
            },
            'metadata': {
                't_food_order_id': str(order.id),
                't_food_payment_id': str(payment.id),
            },
        }

    def build_refund_payload(self, payment, amount, reason):
        return {
            'provider': self.code,
            'payment_id': payment.id,
            'provider_payment_reference': payment.transaction_id or payment.provider_order_id,
            'amount': str(amount),
            'currency': self._currency_for_order(payment.order),
            'reason': reason or '',
            'metadata': {
                't_food_order_id': str(payment.order_id),
                't_food_payment_id': str(payment.id),
            },
        }

    def build_webhook_context(self, request):
        return {
            'provider': self.code,
            'headers': dict(getattr(request, 'headers', {}) or {}),
            'body_length': len(getattr(request, 'body', b'') or b''),
        }

    def create_payment(self, order, payment):
        self._provider_not_configured()

    def verify_webhook(self, request):
        self._provider_not_configured()

    def parse_webhook_event(self, request):
        self._provider_not_configured()

    def refund(self, payment, amount, reason):
        self._provider_not_configured()
