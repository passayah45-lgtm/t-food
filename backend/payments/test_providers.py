from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from ledger.models import LedgerTransaction
from markets.models import Currency, Market
from orders.models import Order, OrderItem
from payments.models import Payment, PaymentProviderConfig
from payments.providers.base import PaymentProviderUnavailable
from payments.providers.flutterwave import FlutterwaveProvider
from payments.providers.mtn_mobile_money import MTNMobileMoneyProvider
from payments.providers.orange_money import OrangeMoneyProvider
from payments.providers.paystack import PaystackProvider
from payments.providers.resolver import (
    PaymentProviderResolutionError,
    ProviderResolver,
    ProviderRuntimeConfig,
    ProviderSelection,
    available_provider_capabilities,
    resolve_provider,
)
from payments.providers.stripe import StripeProvider
from payments.providers.wave import WaveProvider
from payments.services import PaymentService
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class PaymentProviderResolverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.inr, _ = Currency.objects.get_or_create(
            code='INR',
            defaults={
                'numeric_code': '356',
                'name': 'Indian Rupee',
                'symbol': 'Rs.',
            },
        )
        cls.gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
            },
        )
        cls.ngn, _ = Currency.objects.get_or_create(
            code='NGN',
            defaults={
                'numeric_code': '566',
                'name': 'Nigerian Naira',
                'symbol': 'NGN',
            },
        )
        cls.usd, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={
                'numeric_code': '840',
                'name': 'US Dollar',
                'symbol': '$',
            },
        )
        cls.eur, _ = Currency.objects.get_or_create(
            code='EUR',
            defaults={
                'numeric_code': '978',
                'name': 'Euro',
                'symbol': 'EUR',
            },
        )
        cls.india, _ = Market.objects.get_or_create(
            slug='india',
            defaults={
                'name': 'India',
                'country_code': 'IN',
                'default_currency': cls.inr,
            },
        )
        cls.guinea, _ = Market.objects.get_or_create(
            slug='guinea',
            defaults={
                'name': 'Guinea',
                'country_code': 'GN',
                'default_currency': cls.gnf,
                'timezone': 'Africa/Conakry',
                'phone_country_code': '+224',
            },
        )
        cls.nigeria, _ = Market.objects.get_or_create(
            slug='nigeria',
            defaults={
                'name': 'Nigeria',
                'country_code': 'NG',
                'default_currency': cls.ngn,
                'timezone': 'Africa/Lagos',
                'phone_country_code': '+234',
            },
        )
        cls.united_states, _ = Market.objects.get_or_create(
            slug='united-states',
            defaults={
                'name': 'United States',
                'country_code': 'US',
                'default_currency': cls.usd,
                'timezone': 'America/New_York',
                'phone_country_code': '+1',
            },
        )
        cls.france, _ = Market.objects.get_or_create(
            slug='france',
            defaults={
                'name': 'France',
                'country_code': 'FR',
                'default_currency': cls.eur,
                'timezone': 'Europe/Paris',
                'phone_country_code': '+33',
            },
        )

    def provider_config(self, provider_class, *, active=True, configured=True):
        provider = provider_class()
        credentials = {
            field: f'test-{field}'
            for field in getattr(provider, 'credential_fields', lambda: ())()
        }
        return ProviderRuntimeConfig(
            provider.code,
            active=active,
            configured=configured,
            credentials=credentials,
        )

    def test_cod_provider_resolves_for_cash_method(self):
        provider = resolve_provider(market=self.india, payment_method='COD')

        self.assertEqual(provider.code, 'cod')
        self.assertIn('COD', provider.supported_payment_methods())
        self.assertTrue(provider.capabilities()['cash_collection'])

    def test_razorpay_provider_resolves_for_india_online_methods(self):
        provider = resolve_provider(market=self.india, payment_method='UPI')

        self.assertEqual(provider.code, 'razorpay')
        self.assertIn('IN', provider.supported_countries())
        self.assertIn('INR', provider.supported_currencies())
        self.assertIn('UPI', provider.supported_payment_methods())

    def test_provider_code_can_resolve_razorpay(self):
        provider = resolve_provider(
            market=self.india,
            payment_method='CARD',
            provider_code='razorpay',
        )

        self.assertEqual(provider.code, 'razorpay')

    def test_unsupported_country_or_provider_is_rejected_safely(self):
        with self.assertRaises(PaymentProviderResolutionError):
            resolve_provider(market=self.guinea, payment_method='CARD')

        with self.assertRaises(PaymentProviderResolutionError):
            resolve_provider(
                market=self.guinea,
                payment_method='MOBILE_MONEY',
                provider_code='wave',
            )

        with self.assertRaises(PaymentProviderResolutionError):
            resolve_provider(
                market=self.india,
                payment_method='CARD',
                provider_code='missing-provider',
            )

    def test_future_providers_expose_capabilities_without_live_calls(self):
        capabilities = {
            capability.code: capability
            for capability in available_provider_capabilities()
        }

        real_adapter_codes = (
            'stripe',
            'flutterwave',
            'paystack',
            'wave',
            'orange_money',
            'mtn_mobile_money',
        )
        for code in real_adapter_codes:
            self.assertIn(code, capabilities)
            self.assertFalse(capabilities[code].capabilities['live'])
            self.assertTrue(capabilities[code].capabilities['configuration_required'])
            self.assertFalse(capabilities[code].capabilities['external_api_calls_enabled'])

        self.assertIn('airtel_money', capabilities)
        self.assertTrue(capabilities['airtel_money'].capabilities['configuration_only'])

    def test_inactive_future_provider_does_not_make_live_api_calls(self):
        with self.assertRaises(PaymentProviderResolutionError):
            resolve_provider(
                market=self.guinea,
                payment_method='MOBILE_MONEY',
                provider_code='orange_money',
            )

    def test_guinea_resolves_to_preferred_provider_when_configured(self):
        resolver = ProviderResolver(
            selections={
                ('GN', 'MOBILE_MONEY'): ProviderSelection(
                    preferred_provider='wave',
                    fallback_providers=('orange_money', 'mtn_mobile_money'),
                ),
            },
            runtime_configs={
                'wave': self.provider_config(WaveProvider),
                'orange_money': self.provider_config(OrangeMoneyProvider),
                'mtn_mobile_money': self.provider_config(MTNMobileMoneyProvider),
            },
        )

        provider = resolver.resolve(
            market=self.guinea,
            payment_method='MOBILE_MONEY',
        )

        self.assertEqual(provider.code, 'wave')

    def test_guinea_ordered_fallback_provider_works_when_preferred_unavailable(self):
        resolver = ProviderResolver(
            selections={
                ('GN', 'MOBILE_MONEY'): ProviderSelection(
                    preferred_provider='wave',
                    fallback_providers=('orange_money', 'mtn_mobile_money'),
                ),
            },
            runtime_configs={
                'wave': self.provider_config(WaveProvider, active=False),
                'orange_money': self.provider_config(OrangeMoneyProvider),
                'mtn_mobile_money': self.provider_config(MTNMobileMoneyProvider),
            },
        )

        provider = resolver.resolve(
            market=self.guinea,
            payment_method='MOBILE_MONEY',
        )

        self.assertEqual(provider.code, 'orange_money')

    def test_nigeria_resolves_paystack_then_flutterwave_fallback(self):
        resolver = ProviderResolver(
            selections={
                ('NG', 'CARD'): ProviderSelection(
                    preferred_provider='paystack',
                    fallback_providers=('flutterwave',),
                ),
            },
            runtime_configs={
                'paystack': self.provider_config(PaystackProvider),
                'flutterwave': self.provider_config(FlutterwaveProvider),
            },
        )
        provider = resolver.resolve(market=self.nigeria, payment_method='CARD')
        self.assertEqual(provider.code, 'paystack')

        fallback_resolver = ProviderResolver(
            selections={
                ('NG', 'CARD'): ProviderSelection(
                    preferred_provider='paystack',
                    fallback_providers=('flutterwave',),
                ),
            },
            runtime_configs={
                'paystack': self.provider_config(PaystackProvider, configured=False),
                'flutterwave': self.provider_config(FlutterwaveProvider),
            },
        )
        provider = fallback_resolver.resolve(market=self.nigeria, payment_method='CARD')
        self.assertEqual(provider.code, 'flutterwave')

    def test_united_states_and_europe_resolve_to_stripe_when_configured(self):
        resolver = ProviderResolver(
            selections={
                ('US', 'CARD'): ProviderSelection(preferred_provider='stripe'),
                ('FR', 'CARD'): ProviderSelection(preferred_provider='stripe'),
            },
            runtime_configs={
                'stripe': self.provider_config(StripeProvider),
            },
        )

        self.assertEqual(
            resolver.resolve(market=self.united_states, payment_method='CARD').code,
            'stripe',
        )
        self.assertEqual(
            resolver.resolve(market=self.france, payment_method='CARD').code,
            'stripe',
        )

    def test_resolver_rejects_unsupported_currency_country_method_and_inactive_provider(self):
        resolver = ProviderResolver(
            selections={
                ('GN', 'MOBILE_MONEY'): ProviderSelection(preferred_provider='wave'),
            },
            runtime_configs={
                'wave': self.provider_config(WaveProvider),
            },
        )

        with self.assertRaisesMessage(
            PaymentProviderResolutionError,
            'does not support this country, currency, or method',
        ):
            resolver.resolve(
                country='GN',
                currency='USD',
                payment_method='MOBILE_MONEY',
            )

        with self.assertRaisesMessage(
            PaymentProviderResolutionError,
            'No preferred payment provider configured',
        ):
            resolver.resolve(country='ZZ', currency='USD', payment_method='CARD')

        with self.assertRaisesMessage(
            PaymentProviderResolutionError,
            'Unsupported payment method',
        ):
            resolver.resolve(market=self.guinea, payment_method='CRYPTO')

        inactive_resolver = ProviderResolver(
            selections={
                ('GN', 'MOBILE_MONEY'): ProviderSelection(preferred_provider='wave'),
            },
            runtime_configs={
                'wave': self.provider_config(WaveProvider, active=False),
            },
        )
        with self.assertRaisesMessage(
            PaymentProviderResolutionError,
            'No configured payment provider is available.',
        ):
            inactive_resolver.resolve(
                market=self.guinea,
                payment_method='MOBILE_MONEY',
            )

    def test_resolver_uses_database_provider_config_when_present(self):
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='orange_money',
            payment_method='MOBILE_MONEY',
            is_active=True,
            is_preferred=True,
            priority=1,
            credentials_present=True,
        )
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='wave',
            payment_method='MOBILE_MONEY',
            is_active=True,
            priority=2,
            credentials_present=True,
        )

        provider = resolve_provider(
            market=self.guinea,
            payment_method='MOBILE_MONEY',
        )

        self.assertEqual(provider.code, 'orange_money')

    def test_database_provider_config_fallback_order_works(self):
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='orange_money',
            payment_method='MOBILE_MONEY',
            is_active=False,
            is_preferred=True,
            priority=1,
            credentials_present=True,
        )
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='wave',
            payment_method='MOBILE_MONEY',
            is_active=True,
            priority=2,
            credentials_present=True,
        )

        provider = resolve_provider(
            market=self.guinea,
            payment_method='MOBILE_MONEY',
        )

        self.assertEqual(provider.code, 'wave')

    def test_database_provider_config_requires_credentials_present(self):
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='wave',
            payment_method='MOBILE_MONEY',
            is_active=True,
            is_preferred=True,
            priority=1,
            credentials_present=False,
        )

        with self.assertRaisesMessage(
            PaymentProviderResolutionError,
            'No configured payment provider is available.',
        ):
            resolve_provider(
                market=self.guinea,
                payment_method='MOBILE_MONEY',
            )

    def test_database_provider_config_verifies_global_country_routes(self):
        orange_money = PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='orange_money',
            payment_method='MOBILE_MONEY',
            is_active=True,
            is_preferred=True,
            priority=1,
            credentials_present=True,
        )
        wave = PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='wave',
            payment_method='MOBILE_MONEY',
            is_active=True,
            priority=2,
            credentials_present=True,
        )
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='mtn_mobile_money',
            payment_method='MOBILE_MONEY',
            is_active=True,
            priority=3,
            credentials_present=True,
        )
        PaymentProviderConfig.objects.create(
            market=self.india,
            country_code='IN',
            currency='INR',
            provider_code='razorpay',
            payment_method='UPI',
            is_active=True,
            is_preferred=True,
            priority=1,
            credentials_present=True,
        )
        paystack = PaymentProviderConfig.objects.create(
            market=self.nigeria,
            country_code='NG',
            currency='NGN',
            provider_code='paystack',
            payment_method='CARD',
            is_active=True,
            is_preferred=True,
            priority=1,
            credentials_present=True,
        )
        PaymentProviderConfig.objects.create(
            market=self.nigeria,
            country_code='NG',
            currency='NGN',
            provider_code='flutterwave',
            payment_method='CARD',
            is_active=True,
            priority=2,
            credentials_present=True,
        )

        self.assertEqual(
            resolve_provider(market=self.guinea, payment_method='MOBILE_MONEY').code,
            'orange_money',
        )
        orange_money.is_active = False
        orange_money.save(update_fields=['is_active', 'updated_at'])
        self.assertEqual(
            resolve_provider(market=self.guinea, payment_method='MOBILE_MONEY').code,
            'wave',
        )
        wave.is_active = False
        wave.save(update_fields=['is_active', 'updated_at'])
        self.assertEqual(
            resolve_provider(market=self.guinea, payment_method='MOBILE_MONEY').code,
            'mtn_mobile_money',
        )
        self.assertEqual(
            resolve_provider(market=self.india, payment_method='UPI').code,
            'razorpay',
        )
        self.assertEqual(
            resolve_provider(market=self.nigeria, payment_method='CARD').code,
            'paystack',
        )
        paystack.is_active = False
        paystack.save(update_fields=['is_active', 'updated_at'])
        self.assertEqual(
            resolve_provider(market=self.nigeria, payment_method='CARD').code,
            'flutterwave',
        )


class PaymentProviderWrapperTests(TestCase):
    def setUp(self):
        currency, _ = Currency.objects.get_or_create(
            code='INR',
            defaults={
                'numeric_code': '356',
                'name': 'Indian Rupee',
                'symbol': 'Rs.',
            },
        )
        self.market, _ = Market.objects.get_or_create(
            slug='india',
            defaults={
                'name': 'India',
                'country_code': 'IN',
                'default_currency': currency,
            },
        )
        merchant = User.objects.create_user(username='provider-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='Provider Kitchen',
            rest_email='provider@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name='Provider Meal',
            food_price=Decimal('100.00'),
            food_categ='Meals',
        )
        self.customer = User.objects.create_user(username='provider-customer')
        self.order = Order.objects.create(
            customer=self.customer,
            market=self.market,
            delivery_address='12 Test Street',
            contact_phone='1234567890',
            subtotal_amount=Decimal('100.00'),
            total_amount=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=food,
            quantity=1,
            price=Decimal('100.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            market=self.market,
            method='CARD',
            status='PENDING',
            provider='RAZORPAY',
            provider_order_id='order_provider_1',
        )

    @override_settings(RAZORPAY_KEY_SECRET='test-secret')
    def test_razorpay_provider_wraps_existing_signature_check(self):
        provider = resolve_provider(
            market=self.market,
            payment_method='CARD',
            provider_code='razorpay',
        )

        self.assertFalse(provider.verify_customer_confirmation(self.payment, {}))

    def test_cod_provider_does_not_support_webhooks_or_online_capture(self):
        provider = resolve_provider(market=self.market, payment_method='COD')

        self.assertFalse(provider.verify_webhook(None))
        self.assertIsNone(provider.parse_webhook_event(None))
        with self.assertRaises(PaymentProviderUnavailable):
            provider.refund(self.payment, Decimal('10.00'), 'test')

    def test_real_international_adapters_are_safe_without_configuration(self):
        providers = (
            StripeProvider(),
            FlutterwaveProvider(),
            PaystackProvider(),
            WaveProvider(),
            OrangeMoneyProvider(),
            MTNMobileMoneyProvider(),
        )

        for provider in providers:
            with self.subTest(provider=provider.code):
                self.assertTrue(provider.code)
                self.assertTrue(provider.display_name)
                self.assertTrue(provider.supported_countries())
                self.assertTrue(provider.supported_currencies())
                self.assertTrue(provider.supported_payment_methods())
                self.assertTrue(provider.credentials_required())
                self.assertTrue(provider.credential_fields())
                validation = provider.validate_credentials({})
                self.assertFalse(validation['is_configured'])
                self.assertEqual(
                    set(validation['missing_fields']),
                    set(provider.credential_fields()),
                )
                valid_config = {
                    field: f'test-{field}'
                    for field in provider.credential_fields()
                }
                self.assertTrue(provider.validate_credentials(valid_config)['is_configured'])
                create_payload = provider.build_create_payment_payload(
                    self.order,
                    self.payment,
                )
                refund_payload = provider.build_refund_payload(
                    self.payment,
                    Decimal('10.00'),
                    'test refund',
                )
                self.assertIsInstance(create_payload, dict)
                self.assertIsInstance(refund_payload, dict)
                self.assertEqual(create_payload['provider'], provider.code)
                self.assertEqual(refund_payload['provider'], provider.code)
                self.assertEqual(create_payload['order_id'], self.order.id)
                self.assertEqual(refund_payload['payment_id'], self.payment.id)
                webhook_context = provider.build_webhook_context(None)
                self.assertIsInstance(webhook_context, dict)
                self.assertEqual(webhook_context['provider'], provider.code)
                with self.assertRaisesMessage(
                    PaymentProviderUnavailable,
                    'Provider not configured for live payments.',
                ):
                    provider.create_payment(self.order, self.payment)
                with self.assertRaisesMessage(
                    PaymentProviderUnavailable,
                    'Provider not configured for live payments.',
                ):
                    provider.verify_webhook(None)
                with self.assertRaisesMessage(
                    PaymentProviderUnavailable,
                    'Provider not configured for live payments.',
                ):
                    provider.parse_webhook_event(None)
                with self.assertRaisesMessage(
                    PaymentProviderUnavailable,
                    'Provider not configured for live payments.',
                ):
                    provider.refund(self.payment, Decimal('10.00'), 'test')


class PaymentProviderCompatibilityTests(APITestCase):
    def setUp(self):
        currency, _ = Currency.objects.get_or_create(
            code='INR',
            defaults={
                'numeric_code': '356',
                'name': 'Indian Rupee',
                'symbol': 'Rs.',
            },
        )
        self.market, _ = Market.objects.get_or_create(
            slug='india',
            defaults={
                'name': 'India',
                'country_code': 'IN',
                'default_currency': currency,
            },
        )
        merchant = User.objects.create_user(username='provider-api-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='Provider API Kitchen',
            rest_email='provider-api@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name='Provider API Meal',
            food_price=Decimal('100.00'),
            food_categ='Meals',
        )
        self.customer = User.objects.create_user(username='provider-api-customer')
        self.client.force_authenticate(self.customer)

    def create_order(self):
        order = Order.objects.create(
            customer=self.customer,
            market=self.market,
            delivery_address='12 Test Street',
            contact_phone='1234567890',
            subtotal_amount=Decimal('100.00'),
            total_amount=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price=Decimal('100.00'),
        )
        return order

    def test_cod_checkout_behavior_is_unchanged_and_writes_no_ledger(self):
        order = self.create_order()

        response = self.client.post(
            f'/api/v1/payments/orders/{order.id}/',
            {'method': 'COD'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')
        self.assertEqual(order.payment.method, 'COD')
        self.assertEqual(order.payment.status, 'PENDING')
        self.assertFalse(LedgerTransaction.objects.exists())

    def test_payment_service_cod_confirmation_is_idempotent(self):
        order = self.create_order()
        service = PaymentService()

        first = service.create_payment(order, 'COD', user=self.customer)
        order.refresh_from_db()
        second = service.create_payment(order, 'COD', user=self.customer)

        self.assertEqual(first.payment.id, second.payment.id)
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)
        self.assertEqual(order.status, 'CONFIRMED')
        self.assertEqual(first.payment.status, 'PENDING')
        self.assertFalse(LedgerTransaction.objects.exists())

    def test_payment_service_rejects_unsupported_provider_safely(self):
        order = self.create_order()

        with self.assertRaises(PaymentProviderResolutionError):
            PaymentService().create_payment(
                order,
                'CARD',
                user=self.customer,
                provider_code='missing-provider',
            )

        self.assertFalse(Payment.objects.filter(order=order).exists())
        self.assertEqual(order.status, 'PLACED')
        self.assertFalse(LedgerTransaction.objects.exists())

    @override_settings(
        RAZORPAY_KEY_ID='rzp_test_key',
        RAZORPAY_KEY_SECRET='test-secret',
    )
    @patch(
        'payments.providers.razorpay.create_razorpay_order',
        return_value='order_gateway_1',
    )
    def test_razorpay_checkout_behavior_is_unchanged_and_writes_no_ledger(
        self,
        create_order,
    ):
        order = self.create_order()

        response = self.client.post(
            f'/api/v1/payments/orders/{order.id}/',
            {'method': 'CARD'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['payment_required'])
        self.assertEqual(response.data['provider'], 'razorpay')
        order.refresh_from_db()
        self.assertEqual(order.status, 'PLACED')
        self.assertEqual(order.payment.status, 'PENDING')
        self.assertEqual(order.payment.provider, 'RAZORPAY')
        self.assertFalse(LedgerTransaction.objects.exists())
