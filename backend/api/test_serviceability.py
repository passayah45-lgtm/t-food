from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class RestaurantServiceabilityTests(APITestCase):
    def setUp(self):
        merchant = User.objects.create_user(username='zone-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        self.restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='Zone Kitchen',
            rest_email='zone@example.com',
            rest_contact='1234567890',
            rest_address='Central Bengaluru',
            rest_city='Bengaluru',
            pickup_latitude=Decimal('12.971600'),
            pickup_longitude=Decimal('77.594600'),
            delivery_radius_km=Decimal('5.00'),
            estimated_prep_minutes=20,
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Zone Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.customer = User.objects.create_user(username='zone-customer')
        self.client.force_authenticate(self.customer)

    def payload(self, latitude=None, longitude=None):
        payload = {
            'delivery_address': 'Customer address',
            'contact_phone': '1234567890',
            'items': [{'food_id': self.food.id, 'quantity': 1}],
        }
        if latitude is not None:
            payload['latitude'] = latitude
        if longitude is not None:
            payload['longitude'] = longitude
        return payload

    def test_nearby_address_creates_order_with_distance_and_eta(self):
        response = self.client.post(
            '/api/v1/orders/',
            self.payload('12.980000', '77.600000'),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data['id'])
        self.assertLessEqual(order.delivery_distance_km, Decimal('5.00'))
        self.assertIsNotNone(order.estimated_delivery_at)

    def test_address_outside_delivery_radius_is_rejected(self):
        response = self.client.post(
            '/api/v1/orders/',
            self.payload('13.100000', '77.700000'),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('outside', str(response.data['delivery_address'][0]).lower())
        self.assertFalse(Order.objects.exists())

    def test_precise_location_is_required_for_pinned_restaurant(self):
        response = self.client.post(
            '/api/v1/orders/', self.payload(), format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('precise', str(response.data['latitude'][0]).lower())

    def test_offer_preview_does_not_require_location(self):
        response = self.client.post(
            '/api/v1/orders/offers/validate/',
            {'items': [{'food_id': self.food.id, 'quantity': 1}]},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('100.00'))

    def test_restaurant_list_without_location_keeps_backward_compatible_fields(self):
        response = self.client.get('/api/v1/restaurants/')

        self.assertEqual(response.status_code, 200)
        restaurants = response.data.get('results', response.data)
        self.assertEqual(restaurants[0]['rest_name'], 'Zone Kitchen')
        self.assertIn('distance_km', restaurants[0])
        self.assertIn('is_serviceable', restaurants[0])
        self.assertIsNone(restaurants[0]['distance_km'])
        self.assertIsNone(restaurants[0]['is_serviceable'])
        self.assertTrue(restaurants[0]['merchant_verified'])

    def test_restaurant_list_with_location_returns_distance_and_sorts_nearby(self):
        far_merchant = User.objects.create_user(username='far-merchant')
        MerchantProfile.objects.create(user=far_merchant, is_verified=True)
        far_restaurant = Restaurant.objects.create(
            owner=far_merchant,
            rest_name='Far Kitchen',
            rest_email='far@example.com',
            rest_contact='1234567890',
            rest_address='Far Road',
            rest_city='Bengaluru',
            pickup_latitude=Decimal('13.100000'),
            pickup_longitude=Decimal('77.700000'),
            delivery_radius_km=Decimal('5.00'),
            is_active=True,
            is_open=True,
        )
        FoodItem.objects.create(
            restaurant=far_restaurant,
            food_name='Far Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )

        response = self.client.get(
            '/api/v1/restaurants/',
            {'latitude': '12.971700', 'longitude': '77.594700'},
        )

        self.assertEqual(response.status_code, 200)
        restaurants = response.data.get('results', response.data)
        self.assertEqual(restaurants[0]['rest_name'], 'Zone Kitchen')
        self.assertIsNotNone(restaurants[0]['distance_km'])
        self.assertTrue(restaurants[0]['is_serviceable'])
        far = next(item for item in restaurants if item['rest_name'] == 'Far Kitchen')
        self.assertFalse(far['is_serviceable'])

    def test_restaurant_list_falls_back_to_old_lat_lng_when_point_is_null(self):
        fallback_merchant = User.objects.create_user(username='fallback-merchant')
        MerchantProfile.objects.create(user=fallback_merchant, is_verified=True)
        fallback_restaurant = Restaurant.objects.create(
            owner=fallback_merchant,
            rest_name='Fallback Kitchen',
            rest_email='fallback@example.com',
            rest_contact='1234567890',
            rest_address='Fallback Road',
            rest_city='Bengaluru',
            pickup_latitude=Decimal('12.900000'),
            pickup_longitude=Decimal('77.500000'),
            delivery_radius_km=Decimal('5.00'),
            is_active=True,
            is_open=True,
        )
        fallback_restaurant.pickup_point = None
        fallback_restaurant.save(update_fields=['pickup_point'])
        FoodItem.objects.create(
            restaurant=fallback_restaurant,
            food_name='Fallback Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )

        response = self.client.get(
            '/api/v1/restaurants/',
            {'latitude': '12.900000', 'longitude': '77.500000'},
        )

        self.assertEqual(response.status_code, 200)
        restaurants = response.data.get('results', response.data)
        self.assertEqual(restaurants[0]['rest_name'], 'Fallback Kitchen')
        self.assertIsNotNone(restaurants[0]['distance_km'])
        self.assertTrue(restaurants[0]['is_serviceable'])

    def test_restaurant_search_with_location_returns_matching_nearby_results(self):
        far_merchant = User.objects.create_user(username='search-far-merchant')
        MerchantProfile.objects.create(user=far_merchant, is_verified=True)
        far_restaurant = Restaurant.objects.create(
            owner=far_merchant,
            rest_name='Search Far Kitchen',
            rest_email='search-far@example.com',
            rest_contact='1234567890',
            rest_address='Far Road',
            rest_city='Bengaluru',
            pickup_latitude=Decimal('13.100000'),
            pickup_longitude=Decimal('77.700000'),
            delivery_radius_km=Decimal('5.00'),
            is_active=True,
            is_open=True,
        )
        FoodItem.objects.create(
            restaurant=far_restaurant,
            food_name='Zone Meal Deluxe',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )

        response = self.client.get(
            '/api/v1/restaurants/',
            {
                'search': 'Zone Meal',
                'latitude': '12.971700',
                'longitude': '77.594700',
            },
        )

        self.assertEqual(response.status_code, 200)
        restaurants = response.data.get('results', response.data)
        names = [restaurant['rest_name'] for restaurant in restaurants]
        self.assertIn('Zone Kitchen', names)
        self.assertIn('Search Far Kitchen', names)
        self.assertEqual(restaurants[0]['rest_name'], 'Zone Kitchen')
        self.assertIsNotNone(restaurants[0]['distance_km'])
