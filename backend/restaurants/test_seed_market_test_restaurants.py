from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from markets.models import Market
from restaurants.models import FoodItem, Restaurant


class SeedMarketTestRestaurantsCommandTests(TestCase):
    def run_command(self):
        output = StringIO()
        call_command('seed_market_test_restaurants', stdout=output)
        return output.getvalue()

    def test_command_creates_guinea_and_india_restaurants(self):
        output = self.run_command()

        self.assertIn('Market test restaurants ready', output)

        guinea = Market.objects.get(country_code='GN')
        india = Market.objects.get(country_code='IN')
        self.assertEqual(guinea.default_currency.code, 'GNF')
        self.assertEqual(india.default_currency.code, 'INR')

        conakry = Restaurant.objects.get(rest_email='conakry.test.kitchen@t-food.test')
        delhi = Restaurant.objects.get(rest_email='delhi.test.kitchen@t-food.test')

        self.assertEqual(conakry.market, guinea)
        self.assertEqual(conakry.country_code, 'GN')
        self.assertEqual(conakry.rest_city, 'Conakry')
        self.assertEqual(conakry.city_ref.slug, 'conakry')
        self.assertEqual(conakry.area_ref.slug, 'kaloum')
        self.assertTrue(conakry.is_active)
        self.assertTrue(conakry.is_open)

        self.assertEqual(delhi.market, india)
        self.assertEqual(delhi.country_code, 'IN')
        self.assertEqual(delhi.rest_city, 'New Delhi')
        self.assertEqual(delhi.city_ref.slug, 'new-delhi')
        self.assertEqual(delhi.area_ref.slug, 'connaught-place')
        self.assertTrue(delhi.is_active)
        self.assertTrue(delhi.is_open)

        self.assertEqual(FoodItem.objects.filter(restaurant=conakry).count(), 2)
        self.assertEqual(FoodItem.objects.filter(restaurant=delhi).count(), 2)

    def test_command_is_idempotent(self):
        self.run_command()
        self.run_command()

        self.assertEqual(Restaurant.objects.filter(rest_email='conakry.test.kitchen@t-food.test').count(), 1)
        self.assertEqual(Restaurant.objects.filter(rest_email='delhi.test.kitchen@t-food.test').count(), 1)
        self.assertEqual(FoodItem.objects.filter(restaurant__rest_email='conakry.test.kitchen@t-food.test').count(), 2)
        self.assertEqual(FoodItem.objects.filter(restaurant__rest_email='delhi.test.kitchen@t-food.test').count(), 2)
