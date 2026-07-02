from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from customers.models import FavoriteRestaurant
from orders.models import Order, OrderItem
from restaurants.models import FoodItem, Restaurant


class CustomerRetentionApiTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='customer-one', password='test-password'
        )
        self.other_customer = User.objects.create_user(
            username='customer-two', password='test-password'
        )
        self.restaurant = Restaurant.objects.create(
            rest_name='Favorite Kitchen',
            rest_email='favorite@example.com',
            rest_contact='1234567890',
            rest_address='Main Street',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.available_food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Fresh Bowl',
            food_price=Decimal('150.00'),
            food_categ='Vegetarian',
            is_available=True,
        )
        self.unavailable_food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Old Special',
            food_price=Decimal('90.00'),
            food_categ='Vegetarian',
            is_available=False,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            total_amount=Decimal('330.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.available_food,
            quantity=2,
            price=Decimal('120.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.unavailable_food,
            quantity=1,
            price=Decimal('90.00'),
        )

    def test_customer_can_toggle_and_list_favorite(self):
        self.client.force_authenticate(self.customer)
        toggle_url = f'/api/v1/restaurants/{self.restaurant.id}/favorite/'
        added = self.client.post(toggle_url)
        self.assertEqual(added.status_code, 200)
        self.assertTrue(added.data['is_favorite'])
        self.assertTrue(FavoriteRestaurant.objects.filter(
            user=self.customer, restaurant=self.restaurant
        ).exists())

        favorites = self.client.get('/api/v1/restaurants/favorites/')
        self.assertEqual(favorites.status_code, 200)
        self.assertEqual(favorites.data['count'], 1)
        self.assertTrue(favorites.data['results'][0]['is_favorite'])

        removed = self.client.post(toggle_url)
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(removed.data['is_favorite'])

    def test_favorites_are_private_to_each_customer(self):
        FavoriteRestaurant.objects.create(
            user=self.customer,
            restaurant=self.restaurant,
        )
        self.client.force_authenticate(self.other_customer)
        favorites = self.client.get('/api/v1/restaurants/favorites/')
        self.assertEqual(favorites.data['count'], 0)

    def test_reorder_uses_current_price_and_skips_unavailable_items(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get(f'/api/v1/orders/{self.order.id}/reorder/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['food_price'], Decimal('150.00'))
        self.assertEqual(response.data['items'][0]['quantity'], 2)
        self.assertEqual(response.data['unavailable_items'], ['Old Special'])

    def test_customer_cannot_reorder_another_customers_order(self):
        self.client.force_authenticate(self.other_customer)
        response = self.client.get(f'/api/v1/orders/{self.order.id}/reorder/')
        self.assertEqual(response.status_code, 404)

    def test_reorder_rejects_closed_restaurant(self):
        self.restaurant.is_open = False
        self.restaurant.save(update_fields=['is_open'])
        self.client.force_authenticate(self.customer)
        response = self.client.get(f'/api/v1/orders/{self.order.id}/reorder/')
        self.assertEqual(response.status_code, 400)
