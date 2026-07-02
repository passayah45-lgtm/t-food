from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order
from restaurants.models import (
    FoodItem,
    FoodOption,
    FoodOptionGroup,
    MerchantProfile,
    Restaurant,
)


class MenuCustomizationTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='customizer')
        self.restaurant = Restaurant.objects.create(
            rest_name='Custom Kitchen',
            rest_email='custom@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Pizza',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.size = FoodOptionGroup.objects.create(
            food=self.food, name='Size', min_select=1, max_select=1
        )
        self.small = FoodOption.objects.create(
            group=self.size, name='Small', price_delta=Decimal('0.00')
        )
        self.large = FoodOption.objects.create(
            group=self.size, name='Large', price_delta=Decimal('40.00')
        )
        self.client.force_authenticate(self.customer)

    def payload(self, items):
        return {
            'delivery_address': 'Customer address',
            'contact_phone': '1234567890',
            'items': items,
        }

    def test_required_group_is_enforced(self):
        response = self.client.post(
            '/api/v1/orders/',
            self.payload([{'food_id': self.food.id, 'quantity': 1}]),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('select at least', str(response.data).lower())

    def test_server_prices_and_snapshots_selected_options(self):
        response = self.client.post(
            '/api/v1/orders/',
            self.payload([{
                'food_id': self.food.id,
                'quantity': 2,
                'option_ids': [self.large.id],
            }]),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data['id'])
        line = order.items.get()
        self.assertEqual(order.subtotal_amount, Decimal('280.00'))
        self.assertEqual(line.base_price, Decimal('100.00'))
        self.assertEqual(line.price, Decimal('140.00'))
        self.assertEqual(line.selected_options[0]['name'], 'Large')

    def test_option_from_another_item_is_rejected(self):
        other_food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Burger',
            food_price=Decimal('80.00'),
            food_categ='Vegetarian',
        )
        other_group = FoodOptionGroup.objects.create(
            food=other_food, name='Extras', min_select=0, max_select=1
        )
        other_option = FoodOption.objects.create(
            group=other_group, name='Cheese', price_delta=Decimal('10.00')
        )

        response = self.client.post(
            '/api/v1/orders/',
            self.payload([{
                'food_id': self.food.id,
                'quantity': 1,
                'option_ids': [self.small.id, other_option.id],
            }]),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('invalid', str(response.data).lower())

    def test_same_food_can_have_separate_variants(self):
        response = self.client.post(
            '/api/v1/orders/',
            self.payload([
                {'food_id': self.food.id, 'quantity': 1, 'option_ids': [self.small.id]},
                {'food_id': self.food.id, 'quantity': 1, 'option_ids': [self.large.id]},
            ]),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal_amount, Decimal('240.00'))


class MerchantMenuCustomizationTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='menu-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Merchant Kitchen',
            rest_email='merchant-options@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Wrap',
            food_price=Decimal('90.00'),
            food_categ='Vegetarian',
        )
        self.client.force_authenticate(self.merchant)

    def test_merchant_can_create_and_update_nested_options(self):
        url = (
            f'/api/v1/merchants/restaurants/{self.restaurant.id}/items/'
            f'{self.food.id}/options/'
        )
        created = self.client.put(url, [{
            'name': 'Spice',
            'min_select': 1,
            'max_select': 1,
            'options': [
                {'name': 'Mild', 'price_delta': '0.00', 'is_available': True},
                {'name': 'Hot', 'price_delta': '5.00', 'is_available': True},
            ],
        }], format='json')

        self.assertEqual(created.status_code, 200)
        group = created.data['option_groups'][0]
        group['name'] = 'Heat level'
        updated = self.client.put(url, [group], format='json')
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.food.option_groups.get().name, 'Heat level')

