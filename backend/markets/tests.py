from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from customers.models import Customer
from fooddelivery.gis_utils import make_point

from .models import CommerceArea, CommerceCity, Currency, Market
from .money import Money, MoneyError


class MarketFoundationTests(TestCase):
    def test_seeded_india_market_and_inr_currency_exist(self):
        currency = Currency.objects.get(code='INR')
        market = Market.objects.get(slug='india')

        self.assertEqual(currency.numeric_code, '356')
        self.assertEqual(currency.minor_unit, 2)
        self.assertEqual(market.country_code, 'IN')
        self.assertEqual(market.default_currency, currency)
        self.assertTrue(market.is_active)

    def test_market_is_assigned_to_new_rows_without_api_changes(self):
        user = User.objects.create_user(username='market-customer')
        customer = Customer.objects.create(user=user)

        self.assertEqual(customer.market.slug, 'india')

    def test_commerce_city_and_area_create_branch_hierarchy(self):
        market = Market.objects.get(slug='india')
        city = CommerceCity.objects.create(
            market=market,
            name='Bhubaneswar',
            center_point=make_point('85.8245', '20.2961'),
        )
        area = CommerceArea.objects.create(
            city=city,
            name='KIIT Area',
            service_radius_km=Decimal('5.00'),
        )

        self.assertEqual(city.slug, 'bhubaneswar')
        self.assertEqual(area.slug, 'kiit-area')
        self.assertEqual(area.market, market)
        self.assertIsNotNone(city.center_point)

    def test_commerce_city_slug_is_unique_per_market(self):
        market = Market.objects.get(slug='india')
        CommerceCity.objects.create(market=market, name='Conakry', slug='capital')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CommerceCity.objects.create(
                    market=market,
                    name='Duplicate Conakry',
                    slug='capital',
                )

    def test_commerce_area_slug_is_unique_per_city(self):
        market = Market.objects.get(slug='india')
        city = CommerceCity.objects.create(market=market, name='Bhubaneswar')
        CommerceArea.objects.create(city=city, name='KIIT Area', slug='kiit')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CommerceArea.objects.create(
                    city=city,
                    name='Duplicate KIIT',
                    slug='kiit',
                )


class MoneyTests(TestCase):
    def test_money_quantizes_using_currency_minor_unit(self):
        money = Money(Decimal('10.125'), 'INR')

        self.assertEqual(money.amount, Decimal('10.13'))
        self.assertEqual(money.to_minor_units(), 1013)
        self.assertEqual(str(money), 'INR 10.13')

    def test_money_rejects_cross_currency_arithmetic(self):
        with self.assertRaises(MoneyError):
            Money('10.00', 'INR') + Money('1.00', 'USD')

    def test_money_round_trips_minor_units(self):
        money = Money.from_minor_units(12345, 'INR')

        self.assertEqual(money.amount, Decimal('123.45'))
        self.assertEqual(money.as_dict()['minor_amount'], 12345)
