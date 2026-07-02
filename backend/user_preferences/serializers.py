from rest_framework import serializers

from markets.models import Currency, Market

from .models import UserPreference
from .services import fallback_currency_for_user


def choice_payload(choices):
    return [{'code': code, 'label': label} for code, label in choices]


class CurrencyPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ('id', 'code', 'name', 'symbol', 'minor_unit')


class MarketPreferenceSerializer(serializers.ModelSerializer):
    default_currency = CurrencyPreferenceSerializer(read_only=True)

    class Meta:
        model = Market
        fields = ('id', 'slug', 'name', 'country_code', 'default_currency', 'timezone')


class UserPreferenceSerializer(serializers.ModelSerializer):
    preferred_market = serializers.PrimaryKeyRelatedField(
        queryset=Market.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    preferred_currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    preferred_market_detail = MarketPreferenceSerializer(
        source='preferred_market',
        read_only=True,
    )
    preferred_currency_detail = CurrencyPreferenceSerializer(
        source='preferred_currency',
        read_only=True,
    )
    effective_currency = serializers.SerializerMethodField()

    class Meta:
        model = UserPreference
        fields = (
            'id', 'language', 'preferred_country', 'preferred_market',
            'preferred_market_detail', 'theme', 'accent_color', 'timezone',
            'date_format', 'time_format', 'number_format',
            'preferred_currency', 'preferred_currency_detail',
            'effective_currency', 'currency_display',
            'large_text', 'high_contrast', 'reduced_motion',
            'keyboard_focus_enhanced', 'preference_version', 'metadata',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'preference_version', 'created_at', 'updated_at',
            'preferred_market_detail', 'preferred_currency_detail',
            'effective_currency',
        )

    def get_effective_currency(self, obj):
        currency = fallback_currency_for_user(obj.user, obj)
        if not currency:
            return None
        return CurrencyPreferenceSerializer(currency).data

    def validate_language(self, value):
        return str(value or UserPreference.LANGUAGE_ENGLISH).strip().lower()

    def validate_preferred_country(self, value):
        value = str(value or '').strip().upper()
        if value and len(value) != 2:
            raise serializers.ValidationError('Use a two-letter country code.')
        return value

    def validate_timezone(self, value):
        return str(value or '').strip()[:64]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.preference_version += 1
        instance.save()
        return instance


class PreferenceOptionsSerializer(serializers.Serializer):
    def to_representation(self, instance):
        currencies = Currency.objects.filter(is_active=True).order_by('code')
        markets = Market.objects.filter(is_active=True).select_related(
            'default_currency',
        ).order_by('name')
        return {
            'languages': choice_payload(UserPreference.LANGUAGE_CHOICES),
            'themes': choice_payload(UserPreference.THEME_CHOICES),
            'accent_colors': choice_payload(UserPreference.ACCENT_CHOICES),
            'date_formats': choice_payload(UserPreference.DATE_FORMAT_CHOICES),
            'time_formats': choice_payload(UserPreference.TIME_FORMAT_CHOICES),
            'number_formats': choice_payload(UserPreference.NUMBER_FORMAT_CHOICES),
            'currency_display_styles': choice_payload(
                UserPreference.CURRENCY_DISPLAY_CHOICES
            ),
            'supported_currencies': CurrencyPreferenceSerializer(
                currencies,
                many=True,
            ).data,
            'markets': MarketPreferenceSerializer(markets, many=True).data,
            'accessibility_options': [
                {'code': 'large_text', 'label': 'Large text'},
                {'code': 'high_contrast', 'label': 'High contrast'},
                {'code': 'reduced_motion', 'label': 'Reduced motion'},
                {
                    'code': 'keyboard_focus_enhanced',
                    'label': 'Enhanced keyboard focus',
                },
            ],
        }
