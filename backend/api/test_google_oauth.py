from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from customers.models import Customer
from delivery.models import DeliveryPartner
from restaurants.models import MerchantProfile


GOOGLE_TEST_SETTINGS = {
    **settings.REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        **settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],
        'auth_google_start': '100/hour',
        'auth_google_callback': '100/hour',
    },
}


@override_settings(
    GOOGLE_OAUTH_ENABLED=True,
    GOOGLE_OAUTH_CLIENT_ID='google-client-id',
    GOOGLE_OAUTH_CLIENT_SECRET='google-client-secret',
    GOOGLE_OAUTH_REDIRECT_URI='https://tfood.test/api/v1/auth/google/callback/',
    PUBLIC_APP_URL='https://tfood.test',
    REST_FRAMEWORK=GOOGLE_TEST_SETTINGS,
)
class GoogleOAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(GOOGLE_OAUTH_ENABLED=False)
    def test_google_config_disabled(self):
        response = self.client.get('/api/v1/auth/google/config/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['enabled'])

    def test_google_start_redirects_to_google(self):
        response = self.client.get('/api/v1/auth/google/start/?role=partner&next=/orders')

        self.assertEqual(response.status_code, 302)
        self.assertIn('https://accounts.google.com/o/oauth2/v2/auth', response['Location'])
        self.assertIn('client_id=google-client-id', response['Location'])

    @patch('api.auth_views._fetch_google_userinfo')
    @patch('api.auth_views._exchange_google_code')
    def test_google_callback_creates_customer_account(self, exchange, userinfo):
        exchange.return_value = {'access_token': 'google-token'}
        userinfo.return_value = {
            'email': 'new.customer@example.com',
            'email_verified': True,
            'given_name': 'New',
            'family_name': 'Customer',
        }
        state = signing.dumps(
            {'role': 'customer', 'next': '/orders'},
            salt='t-food.google-oauth-state',
        )

        response = self.client.get(f'/api/v1/auth/google/callback/?code=ok&state={state}')

        self.assertEqual(response.status_code, 302)
        self.assertIn('https://tfood.test/auth/google/callback#', response['Location'])
        user = User.objects.get(email='new.customer@example.com')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(Customer.objects.filter(user=user).exists())

    @patch('api.auth_views._fetch_google_userinfo')
    @patch('api.auth_views._exchange_google_code')
    def test_google_callback_without_role_does_not_create_customer(self, exchange, userinfo):
        exchange.return_value = {'access_token': 'google-token'}
        userinfo.return_value = {
            'email': 'new.no.role@example.com',
            'email_verified': True,
            'given_name': 'No',
            'family_name': 'Role',
        }
        state = signing.dumps(
            {'role': '', 'next': '/'},
            salt='t-food.google-oauth-state',
        )

        response = self.client.get(f'/api/v1/auth/google/callback/?code=ok&state={state}')

        self.assertEqual(response.status_code, 302)
        self.assertIn('error=role_required', response['Location'])
        self.assertFalse(User.objects.filter(email='new.no.role@example.com').exists())

    @patch('api.auth_views._fetch_google_userinfo')
    @patch('api.auth_views._exchange_google_code')
    def test_google_callback_creates_partner_account(self, exchange, userinfo):
        exchange.return_value = {'access_token': 'google-token'}
        userinfo.return_value = {
            'email': 'new.partner@example.com',
            'email_verified': True,
            'given_name': 'New',
            'family_name': 'Partner',
        }
        state = signing.dumps(
            {'role': 'partner', 'next': '/partner/dashboard'},
            salt='t-food.google-oauth-state',
        )

        response = self.client.get(f'/api/v1/auth/google/callback/?code=ok&state={state}')

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='new.partner@example.com')
        self.assertTrue(DeliveryPartner.objects.filter(user=user).exists())
        self.assertFalse(Customer.objects.filter(user=user).exists())

    @patch('api.auth_views._fetch_google_userinfo')
    @patch('api.auth_views._exchange_google_code')
    def test_google_callback_creates_merchant_account(self, exchange, userinfo):
        exchange.return_value = {'access_token': 'google-token'}
        userinfo.return_value = {
            'email': 'new.merchant@example.com',
            'email_verified': True,
            'given_name': 'New',
            'family_name': 'Merchant',
        }
        state = signing.dumps(
            {'role': 'merchant', 'next': '/merchant/dashboard'},
            salt='t-food.google-oauth-state',
        )

        response = self.client.get(f'/api/v1/auth/google/callback/?code=ok&state={state}')

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='new.merchant@example.com')
        self.assertTrue(MerchantProfile.objects.filter(user=user).exists())
        self.assertFalse(Customer.objects.filter(user=user).exists())

    @patch('api.auth_views._fetch_google_userinfo')
    @patch('api.auth_views._exchange_google_code')
    def test_google_callback_rejects_unverified_email(self, exchange, userinfo):
        exchange.return_value = {'access_token': 'google-token'}
        userinfo.return_value = {
            'email': 'unverified@example.com',
            'email_verified': False,
        }
        state = signing.dumps(
            {'role': 'customer', 'next': '/'},
            salt='t-food.google-oauth-state',
        )

        response = self.client.get(f'/api/v1/auth/google/callback/?code=ok&state={state}')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='unverified@example.com').exists())
