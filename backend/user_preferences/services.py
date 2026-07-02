from django.conf import settings

from markets.models import Currency

from .models import UserPreference


PLATFORM_DEFAULT_CURRENCY = getattr(settings, 'PLATFORM_DEFAULT_CURRENCY', 'INR')


def platform_default_currency():
    currency = Currency.objects.filter(
        code=PLATFORM_DEFAULT_CURRENCY,
        is_active=True,
    ).first()
    if currency:
        return currency
    return Currency.objects.filter(is_active=True).order_by('code').first()


def market_default_currency(market):
    if market and getattr(market, 'default_currency_id', None):
        return market.default_currency
    return None


def fallback_currency_for_user(user, preference=None):
    if preference and preference.preferred_currency_id:
        return preference.preferred_currency
    market = getattr(preference, 'preferred_market', None) if preference else None
    market_currency = market_default_currency(market)
    if market_currency:
        return market_currency
    return platform_default_currency()


def ensure_user_preference(user):
    if not user or not getattr(user, 'id', None):
        return None
    preference, _ = UserPreference.objects.get_or_create(user=user)
    return preference
