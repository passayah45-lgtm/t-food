from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ledger.models import LedgerTransaction
from markets.models import Currency, Market
from notifications.models import (
    Notification,
    NotificationDevice,
    NotificationPreference,
)
from notifications.preferences import ensure_default_preferences
from orders.models import Order

from .models import UserPreference
from .services import ensure_user_preference, fallback_currency_for_user


class UserPreferenceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.inr, _ = Currency.objects.get_or_create(
            code='INR',
            defaults={
                'numeric_code': '356',
                'name': 'Indian Rupee',
                'symbol': '₹',
                'minor_unit': 2,
            },
        )
        self.gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'FG',
                'minor_unit': 0,
            },
        )
        self.usd, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={
                'numeric_code': '840',
                'name': 'US Dollar',
                'symbol': '$',
                'minor_unit': 2,
            },
        )
        self.guinea, _ = Market.objects.get_or_create(
            slug='guinea-preferences',
            defaults={
                'name': 'Guinea',
                'country_code': 'GN',
                'default_currency': self.gnf,
                'timezone': 'Africa/Conakry',
                'phone_country_code': '+224',
            },
        )
        self.user = User.objects.create_user(
            username='tfood-pref-user',
            email='prefs@t-food.test',
            password='StrongPass123!',
            first_name='T-Food',
            last_name='User',
        )
        self.other_user = User.objects.create_user(
            username='tfood-other-pref-user',
            email='other-prefs@t-food.test',
            password='StrongPass123!',
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.user)

    def test_user_preference_auto_created(self):
        self.authenticate()

        response = self.client.get('/api/v1/preferences/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserPreference.objects.filter(user=self.user).exists())
        self.assertEqual(response.data['language'], UserPreference.LANGUAGE_ENGLISH)
        self.assertEqual(response.data['theme'], UserPreference.THEME_SYSTEM)
        self.assertEqual(response.data['accent_color'], UserPreference.ACCENT_ORANGE)

    def test_update_preferences(self):
        self.authenticate()

        response = self.client.patch('/api/v1/preferences/', {
            'language': 'fr',
            'preferred_country': 'gn',
            'preferred_market': self.guinea.id,
            'theme': UserPreference.THEME_DARK,
            'accent_color': UserPreference.ACCENT_TEAL,
            'timezone': 'Africa/Conakry',
            'date_format': UserPreference.DATE_DD_MM_YYYY,
            'time_format': UserPreference.TIME_24,
            'number_format': UserPreference.NUMBER_FR,
            'large_text': True,
            'high_contrast': True,
            'metadata': {'source': 't-food'},
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        preference = UserPreference.objects.get(user=self.user)
        self.assertEqual(preference.language, 'fr')
        self.assertEqual(preference.preferred_country, 'GN')
        self.assertEqual(preference.preferred_market, self.guinea)
        self.assertEqual(preference.theme, UserPreference.THEME_DARK)
        self.assertEqual(preference.accent_color, UserPreference.ACCENT_TEAL)
        self.assertTrue(preference.large_text)
        self.assertTrue(preference.high_contrast)
        self.assertGreater(preference.preference_version, 1)

    def test_preferred_currency_and_display_saved(self):
        self.authenticate()

        response = self.client.patch('/api/v1/preferences/', {
            'preferred_currency': self.usd.id,
            'currency_display': UserPreference.CURRENCY_DISPLAY_CODE,
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        preference = UserPreference.objects.get(user=self.user)
        self.assertEqual(preference.preferred_currency, self.usd)
        self.assertEqual(
            preference.currency_display,
            UserPreference.CURRENCY_DISPLAY_CODE,
        )
        self.assertEqual(response.data['effective_currency']['code'], 'USD')

    def test_fallback_currency_uses_market_then_platform(self):
        preference = ensure_user_preference(self.user)
        preference.preferred_market = self.guinea
        preference.save(update_fields=['preferred_market', 'updated_at'])

        self.assertEqual(fallback_currency_for_user(self.user, preference), self.gnf)

        preference.preferred_market = None
        preference.save(update_fields=['preferred_market', 'updated_at'])
        self.assertIsNotNone(fallback_currency_for_user(self.user, preference))

    def test_login_and_me_return_preferences(self):
        login = self.client.post('/api/v1/auth/login/', {
            'username': 'tfood-pref-user',
            'password': 'StrongPass123!',
        }, format='json')
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn('preferences', login.data)
        self.assertEqual(
            login.data['preference_version'],
            login.data['preferences']['preference_version'],
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        me = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertIn('preferences', me.data)

    def test_user_cannot_modify_another_users_preferences(self):
        other_preference = ensure_user_preference(self.other_user)
        self.authenticate()

        response = self.client.patch('/api/v1/preferences/', {
            'language': 'fr',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        other_preference.refresh_from_db()
        self.assertEqual(other_preference.language, UserPreference.LANGUAGE_ENGLISH)

    def test_options_endpoint_returns_supported_choices(self):
        self.authenticate()

        response = self.client.get('/api/v1/preferences/options/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('languages', response.data)
        self.assertIn('themes', response.data)
        self.assertIn('accent_colors', response.data)
        self.assertIn('currency_display_styles', response.data)
        self.assertIn('supported_currencies', response.data)
        self.assertIn('accessibility_options', response.data)

    def test_notification_preference_and_device_remain_compatible(self):
        ensure_default_preferences(self.user)
        before_count = NotificationPreference.objects.filter(user=self.user).count()
        NotificationDevice.objects.create(
            user=self.user,
            device_type=NotificationDevice.DEVICE_WEB,
            device_identifier='t-food-browser',
        )
        self.authenticate()

        response = self.client.patch('/api/v1/preferences/', {
            'language': 'fr',
            'currency_display': UserPreference.CURRENCY_DISPLAY_NAME,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(),
            before_count,
        )
        self.assertTrue(
            NotificationDevice.objects.filter(
                user=self.user,
                device_identifier='t-food-browser',
            ).exists()
        )

    def test_minimum_configuration_mode_safe(self):
        user = User.objects.create_user(
            username='tfood-min-config-pref',
            password='StrongPass123!',
        )
        self.authenticate(user)

        response = self.client.get('/api/v1/preferences/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['language'], 'en')
        self.assertIn('effective_currency', response.data)

    def test_currency_preference_does_not_change_financial_amounts(self):
        order = Order.objects.create(
            customer=self.user,
            market=self.guinea,
            status='PENDING',
            delivery_address='T-Food Conakry',
            contact_phone='620000000',
            subtotal_amount=Decimal('100.00'),
            delivery_fee=Decimal('20.00'),
            total_amount=Decimal('120.00'),
            merchant_payout=Decimal('80.00'),
        )
        ledger_count = LedgerTransaction.objects.count()
        payment_count = Notification.objects.count()
        self.authenticate()

        response = self.client.patch('/api/v1/preferences/', {
            'preferred_currency': self.usd.id,
            'currency_display': UserPreference.CURRENCY_DISPLAY_CODE,
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal('120.00'))
        self.assertEqual(order.delivery_fee, Decimal('20.00'))
        self.assertEqual(LedgerTransaction.objects.count(), ledger_count)
        self.assertEqual(Notification.objects.count(), payment_count)
