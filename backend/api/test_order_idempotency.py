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
        restaurant = Restaurant.objects.create(
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
            restaurant=restaurant,
            food_name='Retry Meal',
            food_price=Decimal('100.00'),
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
