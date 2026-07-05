from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from restaurants.models import (
    FoodItem,
    MerchantProfile,
    Restaurant,
    RestaurantOperatingHour,
)
from restaurants.services import restaurant_accepting_orders


class RestaurantOperatingHoursTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='hours-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Hours Kitchen',
            rest_email='hours@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.monday_morning = datetime(
            2026, 6, 22, 10, 0, tzinfo=ZoneInfo('Asia/Kolkata')
        )

    def test_restaurant_without_schedule_uses_manual_switch(self):
        self.assertTrue(
            restaurant_accepting_orders(self.restaurant, self.monday_morning)
        )
        self.restaurant.is_open = False
        self.assertFalse(
            restaurant_accepting_orders(self.restaurant, self.monday_morning)
        )

    def test_normal_and_closed_hours(self):
        RestaurantOperatingHour.objects.create(
            restaurant=self.restaurant,
            day_of_week=0,
            opens_at=time(9, 0),
            closes_at=time(17, 0),
        )

        self.assertTrue(
            restaurant_accepting_orders(self.restaurant, self.monday_morning)
        )
        monday_evening = self.monday_morning.replace(hour=18)
        self.assertFalse(
            restaurant_accepting_orders(self.restaurant, monday_evening)
        )

    @override_settings(TIME_ZONE='Asia/Kolkata')
    def test_country_timezone_controls_operating_hours(self):
        restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Conakry Hours Kitchen',
            rest_email='conakry-hours@example.com',
            rest_contact='224620000000',
            rest_address='Kaloum',
            rest_city='Conakry',
            country_code='GN',
            is_active=True,
            is_open=True,
        )
        RestaurantOperatingHour.objects.create(
            restaurant=restaurant,
            day_of_week=0,
            opens_at=time(9, 0),
            closes_at=time(22, 0),
        )
        monday_conakry_evening = datetime(
            2026, 6, 22, 21, 30, tzinfo=ZoneInfo('UTC')
        )
        local_now = timezone.localtime(
            monday_conakry_evening,
            ZoneInfo('Africa/Conakry'),
        )
        entry = restaurant.operating_hours.get(day_of_week=0)
        current_time = local_now.time().replace(tzinfo=None)
        self.assertTrue(restaurant.is_active)
        self.assertTrue(restaurant.is_open)
        self.assertLess(entry.opens_at, entry.closes_at)
        self.assertLessEqual(entry.opens_at, current_time)
        self.assertLess(current_time, entry.closes_at)

        self.assertTrue(
            restaurant_accepting_orders(restaurant, monday_conakry_evening)
        )

    def test_overnight_hours_continue_into_next_day(self):
        RestaurantOperatingHour.objects.create(
            restaurant=self.restaurant,
            day_of_week=0,
            opens_at=time(18, 0),
            closes_at=time(2, 0),
        )
        tuesday_early = self.monday_morning.replace(day=23, hour=1)

        self.assertTrue(
            restaurant_accepting_orders(self.restaurant, tuesday_early)
        )

    def test_closed_day_never_accepts_orders(self):
        RestaurantOperatingHour.objects.create(
            restaurant=self.restaurant,
            day_of_week=0,
            is_closed=True,
        )
        self.assertFalse(
            restaurant_accepting_orders(self.restaurant, self.monday_morning)
        )

    def schedule_payload(self):
        return [
            {
                'day_of_week': day,
                'is_closed': day == 6,
                'opens_at': '09:00',
                'closes_at': '22:00',
            }
            for day in range(7)
        ]

    def test_merchant_can_save_exact_weekly_schedule(self):
        self.client.force_authenticate(self.merchant)
        response = self.client.put(
            f'/api/v1/merchants/restaurants/{self.restaurant.id}/hours/',
            self.schedule_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.restaurant.operating_hours.count(), 7)
        self.assertTrue(self.restaurant.operating_hours.get(day_of_week=6).is_closed)

    def test_incomplete_schedule_is_rejected(self):
        self.client.force_authenticate(self.merchant)
        response = self.client.put(
            f'/api/v1/merchants/restaurants/{self.restaurant.id}/hours/',
            self.schedule_payload()[:6],
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.restaurant.operating_hours.count(), 0)

    def test_checkout_is_rejected_when_schedule_is_closed(self):
        for day in range(7):
            RestaurantOperatingHour.objects.create(
                restaurant=self.restaurant,
                day_of_week=day,
                is_closed=True,
            )
        food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Closed Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        customer = User.objects.create_user(username='hours-customer')
        self.client.force_authenticate(customer)

        response = self.client.post(
            '/api/v1/orders/',
            {
                'delivery_address': 'Customer address',
                'contact_phone': '1234567890',
                'items': [{'food_id': food.id, 'quantity': 1}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('not accepting', str(response.data['items'][0]).lower())
