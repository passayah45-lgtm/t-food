from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Offer, Order
from restaurants.models import FoodItem, Restaurant


class OfferUsageLimitTests(APITestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(
            rest_name='Offer Kitchen',
            rest_email='offers@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Offer Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.customer = User.objects.create_user(username='offer-customer')
        self.offer = Offer.objects.create(
            code='LIMIT10',
            discount_percent=10,
            max_uses_per_customer=1,
        )
        self.client.force_authenticate(self.customer)

    def payload(self, client_order_id=None, code='LIMIT10'):
        return {
            'client_order_id': str(client_order_id or uuid4()),
            'delivery_address': 'Customer address',
            'contact_phone': '1234567890',
            'offer_code': code,
            'items': [{'food_id': self.food.id, 'quantity': 1}],
        }

    def test_customer_cannot_reuse_limited_offer(self):
        first = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )
        second = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertIn('already used', str(second.data['offer_code']).lower())

    def test_cancelled_order_releases_offer_reservation(self):
        first = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )
        order = Order.objects.get(id=first.data['id'])
        order.status = 'CANCELLED'
        order.save(update_fields=['status', 'updated_at'])

        second = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )

        self.assertEqual(second.status_code, 201)

    def test_global_offer_cap_applies_across_customers(self):
        self.offer.max_uses_total = 1
        self.offer.max_uses_per_customer = None
        self.offer.save(update_fields=['max_uses_total', 'max_uses_per_customer'])
        first = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )
        other_customer = User.objects.create_user(username='other-offer-customer')
        self.client.force_authenticate(other_customer)

        second = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertIn('usage limit', str(second.data['offer_code']).lower())

    def test_first_order_offer_rejects_existing_active_order(self):
        first_only = Offer.objects.create(
            code='FIRST20',
            discount_percent=20,
            first_order_only=True,
            max_uses_per_customer=None,
        )
        Order.objects.create(customer=self.customer, total_amount=Decimal('50.00'))

        response = self.client.post(
            '/api/v1/orders/', self.payload(code=first_only.code), format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('first order', str(response.data['offer_code']).lower())

    def test_idempotent_retry_returns_order_after_offer_is_consumed(self):
        client_order_id = uuid4()
        payload = self.payload(client_order_id=client_order_id)

        first = self.client.post('/api/v1/orders/', payload, format='json')
        retry = self.client.post('/api/v1/orders/', payload, format='json')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.data['id'], retry.data['id'])
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 1)
