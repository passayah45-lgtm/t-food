from dataclasses import dataclass

from markets.models import Market

from .base import PaymentProviderError
from .cod import CODProvider
from .flutterwave import FlutterwaveProvider
from .mtn_mobile_money import MTNMobileMoneyProvider
from .orange_money import OrangeMoneyProvider
from .paystack import PaystackProvider
from .razorpay import RazorpayProvider
from .stripe import StripeProvider
from .stubs import AirtelMoneyProvider
from .wave import WaveProvider


class PaymentProviderResolutionError(PaymentProviderError):
    pass


SUPPORTED_PAYMENT_METHODS = {
    'COD',
    'CARD',
    'MOBILE_MONEY',
    'UPI',
    'WALLET',
    'BANK_TRANSFER',
    'QR_PAYMENT',
}

LIVE_PROVIDERS = (
    CODProvider,
    RazorpayProvider,
)

FUTURE_PROVIDERS = (
    StripeProvider,
    FlutterwaveProvider,
    PaystackProvider,
    WaveProvider,
    OrangeMoneyProvider,
    MTNMobileMoneyProvider,
    AirtelMoneyProvider,
)

PROVIDER_REGISTRY = {
    provider.code: provider
    for provider in (*LIVE_PROVIDERS, *FUTURE_PROVIDERS)
}

DEFAULT_PROVIDER_POLICIES = {
    ('IN', 'UPI'): ('razorpay', ()),
    ('IN', 'CARD'): ('razorpay', ()),
    ('IN', 'WALLET'): ('razorpay', ()),
}


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    provider_code: str
    active: bool = False
    configured: bool = False
    credentials: dict | None = None


@dataclass(frozen=True)
class ProviderSelection:
    preferred_provider: str | None = None
    fallback_providers: tuple[str, ...] = ()


def available_provider_capabilities():
    return [provider().capability() for provider in PROVIDER_REGISTRY.values()]


def default_runtime_configs():
    return {
        'cod': ProviderRuntimeConfig('cod', active=True, configured=True),
        'razorpay': ProviderRuntimeConfig('razorpay', active=True, configured=True),
    }


def _market_from_inputs(market=None, country=None):
    if market:
        return market
    if country:
        return Market.objects.filter(
            country_code=str(country).upper(),
            is_active=True,
        ).select_related('default_currency').first()
    return None


def _country_currency(market=None, country=None, currency=None):
    resolved_market = _market_from_inputs(market=market, country=country)
    resolved_country = (
        str(country).upper()
        if country
        else resolved_market.country_code
        if resolved_market
        else None
    )
    resolved_currency = (
        str(currency).upper()
        if currency
        else resolved_market.default_currency.code
        if resolved_market
        else None
    )
    return resolved_market, resolved_country, resolved_currency


def _placeholder_credentials(provider):
    return {
        field: f'configured-{field}'
        for field in getattr(provider, 'credential_fields', lambda: ())()
    }


class ProviderResolver:
    def __init__(self, *, selections=None, runtime_configs=None, use_database_configs=True):
        self.selections = {
            key: ProviderSelection(
                preferred_provider=value[0],
                fallback_providers=tuple(value[1]),
            )
            for key, value in DEFAULT_PROVIDER_POLICIES.items()
        }
        if selections:
            self.selections.update({
                (country.upper(), method.upper()): selection
                for (country, method), selection in selections.items()
            })
        self.runtime_configs = default_runtime_configs()
        if runtime_configs:
            self.runtime_configs.update({
                code.lower(): config
                for code, config in runtime_configs.items()
            })
        self.use_database_configs = use_database_configs and not selections and not runtime_configs

    def resolve(
        self,
        *,
        market=None,
        country=None,
        currency=None,
        payment_method=None,
        provider_code=None,
    ):
        resolved_market, resolved_country, resolved_currency = _country_currency(
            market=market,
            country=country,
            currency=currency,
        )
        method = str(payment_method or '').upper()
        if method not in SUPPORTED_PAYMENT_METHODS:
            raise PaymentProviderResolutionError('Unsupported payment method.')
        if not resolved_country:
            raise PaymentProviderResolutionError('Country is required to resolve payment provider.')
        if not resolved_currency:
            raise PaymentProviderResolutionError('Currency is required to resolve payment provider.')

        if method == 'COD' and not provider_code:
            return self._validate_provider(
                'cod',
                country=resolved_country,
                currency=resolved_currency,
                payment_method=method,
            )

        if provider_code:
            return self._validate_provider(
                provider_code,
                country=resolved_country,
                currency=resolved_currency,
                payment_method=method,
            )

        selection = None
        if self.use_database_configs:
            selection = self._load_database_selection(
                market=resolved_market,
                country=resolved_country,
                currency=resolved_currency,
                payment_method=method,
            )
        selection = selection or self.selections.get((resolved_country, method))
        if not selection or not selection.preferred_provider:
            market_label = resolved_market.slug if resolved_market else resolved_country
            raise PaymentProviderResolutionError(
                f'No preferred payment provider configured for {method} in {market_label}.'
            )

        provider_codes = (
            selection.preferred_provider,
            *selection.fallback_providers,
        )
        failures = []
        for candidate in provider_codes:
            try:
                return self._validate_provider(
                    candidate,
                    country=resolved_country,
                    currency=resolved_currency,
                    payment_method=method,
                )
            except PaymentProviderResolutionError as exc:
                failures.append(f'{candidate}: {exc}')

        raise PaymentProviderResolutionError(
            'No configured payment provider is available. '
            + ' | '.join(failures)
        )

    def _load_database_selection(self, *, market, country, currency, payment_method):
        from payments.models import PaymentProviderConfig

        queryset = PaymentProviderConfig.objects.filter(
            country_code=str(country).upper(),
            currency=str(currency).upper(),
            payment_method=str(payment_method).upper(),
        ).order_by('-is_preferred', 'priority', 'provider_code')
        if market:
            queryset = queryset.filter(market=market)
        rows = list(queryset)
        if not rows:
            return None

        preferred = next((row for row in rows if row.is_preferred), None)
        if not preferred:
            return ProviderSelection()

        fallback_rows = [
            row
            for row in rows
            if row.id != preferred.id
        ]
        for row in rows:
            provider_class = PROVIDER_REGISTRY.get(row.provider_code)
            provider = provider_class() if provider_class else None
            credentials = (
                _placeholder_credentials(provider)
                if provider and row.credentials_present
                else {}
            )
            self.runtime_configs[row.provider_code] = ProviderRuntimeConfig(
                row.provider_code,
                active=row.is_active,
                configured=row.credentials_present,
                credentials=credentials,
            )
        return ProviderSelection(
            preferred_provider=preferred.provider_code,
            fallback_providers=tuple(row.provider_code for row in fallback_rows),
        )

    def _validate_provider(self, provider_code, *, country, currency, payment_method):
        code = str(provider_code or '').lower()
        provider_class = PROVIDER_REGISTRY.get(code)
        if not provider_class:
            raise PaymentProviderResolutionError('Unknown payment provider.')
        provider = provider_class()
        if not provider.supports(
            country=country,
            currency=currency,
            payment_method=payment_method,
        ):
            raise PaymentProviderResolutionError(
                f'{provider.display_name} does not support this country, currency, or method.'
            )
        config = self.runtime_configs.get(code)
        if not config or not config.active:
            raise PaymentProviderResolutionError(
                f'{provider.display_name} is not active for this market.'
            )
        if not config.configured:
            raise PaymentProviderResolutionError(
                f'{provider.display_name} is not configured for live payments.'
            )
        credential_check = getattr(provider, 'validate_credentials', lambda value: {'is_configured': True})(
            config.credentials or {}
        )
        if not credential_check.get('is_configured', True):
            raise PaymentProviderResolutionError(
                f'{provider.display_name} is missing required credentials.'
            )
        return provider


def resolve_provider(
    *,
    market=None,
    country=None,
    currency=None,
    payment_method=None,
    provider_code=None,
    selections=None,
    runtime_configs=None,
    use_database_configs=True,
):
    return ProviderResolver(
        selections=selections,
        runtime_configs=runtime_configs,
        use_database_configs=use_database_configs,
    ).resolve(
        market=market,
        country=country,
        currency=currency,
        payment_method=payment_method,
        provider_code=provider_code,
    )
