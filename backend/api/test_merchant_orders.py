from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order, OrderItem
from payments.models import Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class MerchantOrderStatusTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='status-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.customer = User.objects.create_user(username='status-customer')
        restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Status Kitchen',
            rest_email='status@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
        )
        food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name='Status Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='CONFIRMED',
            total_amount=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=food,
            quantity=1,
            price=Decimal('100.00'),
        )
        Payment.objects.create(
            order=self.order,
            method='COD',
            status='PENDING',
        )

    def test_merchant_can_accept_confirmed_order(self):
        self.client.force_authenticate(self.merchant)
        response = self.client.patch(
            f'/api/v1/merchants/orders/{self.order.id}/status/',
            {'status': 'PREPARING'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PREPARING')
