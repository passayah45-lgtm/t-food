from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class OrderIdempotencyTests(APITestCase):
    def setUp(self):
        merchant = User.objects.create_user(username='retry-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        self.restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='Retry Kitchen',
            rest_email='retry@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Retry Meal',
            food_price=Decimal('100.00'),
            food_categ='Meals',
            is_available=True,
        )
        self.second_restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='Second Kitchen',
            rest_email='second-retry@example.com',
            rest_contact='1234567891',
            rest_address='Second Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.second_food = FoodItem.objects.create(
            restaurant=self.second_restaurant,
            food_name='Second Meal',
            food_price=Decimal('120.00'),
            food_categ='Meals',
            is_available=True,
        )
        self.customer = User.objects.create_user(username='retry-customer')
        self.client.force_authenticate(self.customer)

    def payload(self, client_order_id):
        return {
            'client_order_id': str(client_order_id),
            'delivery_address': '12 Test Street',
            'contact_phone': '1234567890',
            'items': [{'food_id': self.food.id, 'quantity': 1}],
        }

    def payload_for_food(self, food, client_order_id):
        data = self.payload(client_order_id)
        data['items'] = [{'food_id': food.id, 'quantity': 1}]
        return data

    def test_repeated_checkout_returns_original_order(self):
        client_order_id = uuid4()

        first = self.client.post(
            '/api/v1/orders/', self.payload(client_order_id), format='json'
        )
        second = self.client.post(
            '/api/v1/orders/', self.payload(client_order_id), format='json'
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(first.data['merchant_order_code'], second.data['merchant_order_code'])
        self.assertEqual(Order.objects.count(), 1)

    def test_different_checkout_ids_create_different_orders(self):
        first = self.client.post(
            '/api/v1/orders/', self.payload(uuid4()), format='json'
        )
        second = self.client.post(
            '/api/v1/orders/', self.payload(uuid4()), format='json'
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.data['id'], second.data['id'])
        self.assertEqual(Order.objects.count(), 2)

    def test_merchant_order_code_starts_at_one_per_branch(self):
        first = self.client.post(
            '/api/v1/orders/', self.payload_for_food(self.food, uuid4()), format='json'
        )
        second_same_branch = self.client.post(
            '/api/v1/orders/', self.payload_for_food(self.food, uuid4()), format='json'
        )
        first_second_branch = self.client.post(
            '/api/v1/orders/', self.payload_for_food(self.second_food, uuid4()), format='json'
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second_same_branch.status_code, 201)
        self.assertEqual(first_second_branch.status_code, 201)
        self.assertRegex(
            first.data['merchant_order_code'],
            rf'^RETR-{self.restaurant.id}-\d{{8}}-001$',
        )
        self.assertRegex(
            second_same_branch.data['merchant_order_code'],
            rf'^RETR-{self.restaurant.id}-\d{{8}}-002$',
        )
        self.assertRegex(
            first_second_branch.data['merchant_order_code'],
            rf'^SECO-{self.second_restaurant.id}-\d{{8}}-001$',
        )

    def test_checkout_id_is_scoped_to_customer(self):
        client_order_id = uuid4()
        first = self.client.post(
            '/api/v1/orders/', self.payload(client_order_id), format='json'
        )
        other_customer = User.objects.create_user(username='other-customer')
        self.client.force_authenticate(other_customer)
        second = self.client.post(
            '/api/v1/orders/', self.payload(client_order_id), format='json'
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(Order.objects.count(), 2)
