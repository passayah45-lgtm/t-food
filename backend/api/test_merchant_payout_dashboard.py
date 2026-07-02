from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order, OrderItem
from payments.models import Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class MerchantPayoutDashboardApiTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='payout-dashboard-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.other_merchant = User.objects.create_user(username='payout-dashboard-other')
        MerchantProfile.objects.create(user=self.other_merchant, is_verified=True)
        self.customer = User.objects.create_user(username='payout-dashboard-customer')
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Payout Kitchen',
            rest_email='payout-dashboard@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
        )
        other_restaurant = Restaurant.objects.create(
            owner=self.other_merchant,
            rest_name='Other Payout Kitchen',
            rest_email='other-payout-dashboard@example.com',
            rest_contact='1234567891',
            rest_address='Other Road',
            rest_city='Test City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Payout Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        other_food = FoodItem.objects.create(
            restaurant=other_restaurant,
            food_name='Other Meal',
            food_price=Decimal('500.00'),
            food_categ='Vegetarian',
        )
        self.available = self.create_order('AVAILABLE', Decimal('170.00'), self.food)
        self.pending = self.create_order('PENDING', Decimal('90.00'), self.food)
        self.paid = self.create_order('PAID', Decimal('50.00'), self.food)
        self.other_order = self.create_order(
            'AVAILABLE',
            Decimal('425.00'),
            other_food,
        )

    def create_order(self, payout_status, payout, food):
        order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=payout + Decimal('30.00'),
            platform_fee=Decimal('30.00'),
            merchant_payout=payout,
            merchant_payout_status=payout_status,
        )
        OrderItem.objects.create(
            order=order,
            food=food,
            quantity=1,
            price=food.food_price,
            base_price=food.food_price,
        )
        Payment.objects.create(order=order, method='COD', status='SUCCESS')
        return order

    def test_merchant_can_list_owned_payouts_and_totals(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/payouts/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['totals']['AVAILABLE'], Decimal('170.00'))
        self.assertEqual(response.data['totals']['PENDING'], Decimal('90.00'))
        self.assertEqual(response.data['totals']['PAID'], Decimal('50.00'))
        self.assertEqual(response.data['totals']['total'], Decimal('310.00'))
        order_ids = {row['order_id'] for row in response.data['results']}
        self.assertEqual(order_ids, {self.available.id, self.pending.id, self.paid.id})

    def test_merchant_can_filter_payouts_by_status(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/payouts/?status=AVAILABLE')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'AVAILABLE')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['order_id'], self.available.id)

    def test_invalid_payout_status_is_rejected(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/payouts/?status=SENT')

        self.assertEqual(response.status_code, 400)
        self.assertIn('status', response.data)

    def test_non_merchant_cannot_access_payout_dashboard(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/merchants/payouts/')

        self.assertEqual(response.status_code, 403)
