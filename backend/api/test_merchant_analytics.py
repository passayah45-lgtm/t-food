from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from delivery.models import DeliveryPartner, MerchantRider
from orders.models import Order, OrderItem, OrderStatusEvent
from payments.models import Payment
from restaurants.models import (
    FoodItem,
    MerchantProfile,
    Restaurant,
    RestaurantReview,
)


class MerchantAnalyticsApiTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='analytics-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.other_merchant = User.objects.create_user(username='other-merchant')
        MerchantProfile.objects.create(user=self.other_merchant, is_verified=True)
        self.customer = User.objects.create_user(username='analytics-customer')
        self.other_customer = User.objects.create_user(username='analytics-other-customer')
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Analytics Kitchen',
            rest_email='analytics@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            estimated_prep_minutes=30,
            is_active=True,
            is_open=True,
        )
        self.branch_two = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Analytics Branch Two',
            rest_email='analytics-branch-two@example.com',
            rest_contact='1234567898',
            rest_address='Second Road',
            rest_city='Test City',
            estimated_prep_minutes=15,
            is_active=True,
            is_open=False,
        )
        self.other_restaurant = Restaurant.objects.create(
            owner=self.other_merchant,
            rest_name='Other Kitchen',
            rest_email='other-analytics@example.com',
            rest_contact='1234567899',
            rest_address='Other Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.biryani = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Biryani',
            food_price=Decimal('100.00'),
            food_categ='Non-Vegetarian',
        )
        self.roll = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Roll',
            food_price=Decimal('20.00'),
            food_categ='Vegetarian',
        )
        self.unsold = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Unsold Tea',
            food_price=Decimal('10.00'),
            food_categ='Beverages',
        )
        self.branch_two_item = FoodItem.objects.create(
            restaurant=self.branch_two,
            food_name='Branch Two Meal',
            food_price=Decimal('300.00'),
            food_categ='Vegetarian',
        )
        other_food = FoodItem.objects.create(
            restaurant=self.other_restaurant,
            food_name='Other Meal',
            food_price=Decimal('500.00'),
            food_categ='Vegetarian',
        )
        self.delivered_order = self.create_order(
            status='DELIVERED',
            total_amount=Decimal('220.00'),
            merchant_payout=Decimal('170.00'),
            payment_status='SUCCESS',
            items=[
                (self.biryani, 2, Decimal('100.00')),
                (self.roll, 1, Decimal('20.00')),
            ],
        )
        self.cancelled_order = self.create_order(
            status='CANCELLED',
            total_amount=Decimal('120.00'),
            merchant_payout=Decimal('95.00'),
            payment_status='CANCELLED',
            items=[(self.biryani, 1, Decimal('100.00'))],
        )
        self.other_order = self.create_order(
            status='DELIVERED',
            total_amount=Decimal('500.00'),
            merchant_payout=Decimal('425.00'),
            payment_status='SUCCESS',
            items=[(other_food, 1, Decimal('500.00'))],
            customer=self.other_customer,
        )
        self.branch_two_order = self.create_order(
            status='DELIVERED',
            total_amount=Decimal('300.00'),
            merchant_payout=Decimal('240.00'),
            payment_status='SUCCESS',
            items=[(self.branch_two_item, 1, Decimal('300.00'))],
        )
        partner_user = User.objects.create_user(username='analytics-branch-rider')
        partner = DeliveryPartner.objects.create(
            user=partner_user,
            partner_name='Analytics Branch Rider',
            partner_phone='9000000700',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )
        MerchantRider.objects.create(
            merchant=self.merchant.merchant_profile,
            partner=partner,
            status=MerchantRider.STATUS_ACTIVE,
            home_restaurant=self.restaurant,
        )
        RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=self.delivered_order,
            rating=4,
            comment='Good',
        )
        self.add_timeline(self.delivered_order)

    def create_order(self, status, total_amount, merchant_payout, payment_status, items, customer=None):
        order = Order.objects.create(
            customer=customer or self.customer,
            status=status,
            total_amount=total_amount,
            subtotal_amount=total_amount,
            merchant_payout=merchant_payout,
        )
        for food, quantity, price in items:
            OrderItem.objects.create(
                order=order,
                food=food,
                quantity=quantity,
                price=price,
                base_price=price,
            )
        Payment.objects.create(
            order=order,
            method='COD',
            status=payment_status,
        )
        return order

    def add_timeline(self, order):
        base = timezone.now() - timedelta(minutes=45)
        events = [
            ('CONFIRMED', 'PAYMENT', 0),
            ('PREPARING', 'MERCHANT', 5),
            ('READY_FOR_PICKUP', 'MERCHANT', 25),
        ]
        for status, source, minutes in events:
            event = OrderStatusEvent.objects.create(
                order=order,
                status=status,
                source=source,
                description=status,
            )
            OrderStatusEvent.objects.filter(id=event.id).update(
                created_at=base + timedelta(minutes=minutes)
            )

    def test_merchant_analytics_summarizes_owned_orders(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/analytics/?range=7d')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['range'], '7d')
        self.assertEqual(response.data['scope'], 'company')
        self.assertIsNone(response.data['branch'])
        self.assertEqual(response.data['sales']['delivered_orders'], 2)
        self.assertEqual(response.data['sales']['cancelled_orders'], 1)
        self.assertEqual(response.data['sales']['gross_sales'], Decimal('520.00'))
        self.assertEqual(response.data['sales']['merchant_earnings'], Decimal('410.00'))
        self.assertEqual(response.data['sales']['average_order_value'], Decimal('260.00'))
        self.assertEqual(response.data['sales']['cancellation_rate'], 33.33)
        self.assertEqual(response.data['sales']['delivery_count'], 2)
        self.assertEqual(response.data['order_volume'][0]['orders'], 2)
        self.assertEqual(response.data['order_volume'][0]['gross_sales'], Decimal('520.00'))
        self.assertEqual(response.data['top_items'][0], {
            'item_id': self.biryani.id,
            'name': 'Biryani',
            'quantity': 2,
            'gross_sales': Decimal('200.00'),
        })
        self.assertEqual(response.data['low_items'][0]['name'], 'Unsold Tea')
        self.assertEqual(response.data['ratings']['average_rating'], 4.0)
        self.assertEqual(response.data['ratings']['review_count'], 1)
        self.assertEqual(response.data['ratings']['distribution'][3], {
            'rating': 4,
            'count': 1,
        })
        self.assertEqual(response.data['prep']['estimated_prep_minutes'], 22.5)
        self.assertEqual(response.data['prep']['average_accept_minutes'], 5.0)
        self.assertEqual(response.data['prep']['average_ready_minutes'], 20.0)
        self.assertEqual(response.data['kpis']['gross_sales'], Decimal('520.00'))
        self.assertEqual(response.data['kpis']['net_earnings'], Decimal('410.00'))
        self.assertEqual(response.data['kpis']['delivery_count'], 2)
        self.assertEqual(response.data['kpis']['rider_count'], 1)
        self.assertEqual(response.data['kpis']['active_riders'], 1)
        self.assertEqual(response.data['kpis']['average_prep_time'], 20.0)
        self.assertEqual(response.data['kpis']['average_acceptance_time'], 5.0)
        trend_keys = {row['key'] for row in response.data['revenue_trends']}
        self.assertEqual(trend_keys, {
            'today', 'yesterday', 'last_7_days', 'last_30_days',
            'current_month', 'current_year',
        })
        self.assertIn('revenue_line', response.data['charts'])
        self.assertIn('cancellations', response.data['charts'])
        self.assertIn('rating_distribution', response.data['charts'])
        self.assertEqual(response.data['performance']['best_day']['gross_sales'], Decimal('520.00'))
        self.assertEqual(response.data['performance']['fastest_prep_time']['minutes'], 20.0)
        self.assertEqual(response.data['performance']['most_profitable_item']['name'], 'Branch Two Meal')
        self.assertEqual(response.data['performance']['lowest_performing_item']['name'], 'Unsold Tea')
        self.assertIn('this_week_vs_last_week', response.data['comparison'])
        self.assertIn('this_month_vs_last_month', response.data['comparison'])

    def test_merchant_analytics_supports_expanded_ranges(self):
        self.client.force_authenticate(self.merchant)

        for range_key in ('today', 'yesterday', '7d', '30d', 'month', 'year'):
            response = self.client.get(f'/api/v1/merchants/analytics/?range={range_key}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['range'], range_key)

    def test_branch_analytics_are_isolated_from_company_analytics(self):
        self.client.force_authenticate(self.merchant)

        company = self.client.get('/api/v1/merchants/analytics/?range=7d')
        branch = self.client.get(
            f'/api/v1/merchants/analytics/?range=7d&branch_id={self.restaurant.id}'
        )
        branch_two = self.client.get(
            f'/api/v1/merchants/analytics/?range=7d&branch_id={self.branch_two.id}'
        )

        self.assertEqual(company.status_code, 200)
        self.assertEqual(branch.status_code, 200)
        self.assertEqual(branch_two.status_code, 200)
        self.assertEqual(company.data['scope'], 'company')
        self.assertEqual(branch.data['scope'], 'branch')
        self.assertEqual(branch.data['branch']['id'], self.restaurant.id)
        self.assertEqual(company.data['sales']['delivered_orders'], 2)
        self.assertEqual(company.data['sales']['gross_sales'], Decimal('520.00'))
        self.assertEqual(branch.data['sales']['delivered_orders'], 1)
        self.assertEqual(branch.data['sales']['gross_sales'], Decimal('220.00'))
        self.assertEqual(branch.data['top_items'][0]['name'], 'Biryani')
        self.assertNotEqual(branch.data['top_items'][0]['name'], 'Branch Two Meal')
        self.assertEqual(branch.data['kpis']['rider_count'], 1)
        self.assertEqual(branch.data['kpis']['active_riders'], 1)
        self.assertTrue(branch.data['branch_status']['is_open'])
        self.assertEqual(branch_two.data['sales']['gross_sales'], Decimal('300.00'))
        self.assertEqual(branch_two.data['kpis']['rider_count'], 0)
        self.assertFalse(branch_two.data['branch_status']['is_open'])

    def test_branch_analytics_reject_other_merchant_branch(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get(
            f'/api/v1/merchants/analytics/?branch_id={self.other_restaurant.id}'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('branch_id', response.data)

    def test_merchant_analytics_rejects_invalid_range(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/analytics/?range=lifetime')

        self.assertEqual(response.status_code, 400)
        self.assertIn('range', response.data)

    def test_non_merchant_cannot_access_analytics(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/merchants/analytics/')

        self.assertEqual(response.status_code, 403)
