from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from markets.models import Currency, Market
from orders.models import Offer
from restaurants.models import FoodItem, Restaurant


class OperationsOfferManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='promo-admin',
            email='promo-admin@t-food.test',
            password='AdminPass123!',
        )
        self.gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
            },
        )
        self.inr, _ = Currency.objects.get_or_create(
            code='INR',
            defaults={
                'name': 'Indian Rupee',
                'symbol': 'INR',
                'minor_unit': 2,
            },
        )
        self.guinea, _ = Market.objects.get_or_create(
            country_code='GN',
            defaults={
                'name': 'Guinea',
                'slug': 'guinea',
                'default_currency': self.gnf,
                'timezone': 'Africa/Conakry',
            },
        )
        self.india, _ = Market.objects.get_or_create(
            country_code='IN',
            defaults={
                'name': 'India',
                'slug': 'india',
                'default_currency': self.inr,
                'timezone': 'Asia/Kolkata',
            },
        )
        self.customer = User.objects.create_user(username='promo-customer')
        self.restaurant = Restaurant.objects.create(
            rest_name='Conakry Promo Kitchen',
            rest_email='promo-kitchen@example.com',
            rest_contact='+224620000000',
            rest_address='Kaloum',
            rest_city='Conakry',
            market=self.guinea,
            country_code='GN',
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Promo Meal',
            food_price=Decimal('100.00'),
            food_categ='Food',
            is_available=True,
        )

    def test_operations_admin_can_create_market_promo_code(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post('/api/v1/operations/offers/', {
            'market': self.guinea.id,
            'code': 'tfood10',
            'discount_percent': 10,
            'min_order_amount': '0.00',
            'max_uses_per_customer': 1,
            'is_active': True,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['code'], 'TFOOD10')
        self.assertEqual(response.data['market_country_code'], 'GN')
        self.assertTrue(Offer.objects.filter(code='TFOOD10', market=self.guinea).exists())

    def test_market_specific_offer_does_not_apply_to_other_market(self):
        Offer.objects.create(
            market=self.india,
            code='INDIA10',
            discount_percent=10,
            max_uses_per_customer=None,
        )
        self.client.force_authenticate(self.customer)

        response = self.client.post('/api/v1/orders/offers/validate/', {
            'offer_code': 'INDIA10',
            'items': [{'food_id': self.food.id, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('not available for this market', str(response.data['offer_code']).lower())
