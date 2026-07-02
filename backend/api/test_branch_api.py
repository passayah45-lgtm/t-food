from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from delivery.models import Delivery
from markets.models import CommerceArea, CommerceCity, Market
from orders.models import Order, SupportTicket
from payments.models import Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class BranchApiCompatibilityTests(APITestCase):
    def setUp(self):
        self.market = Market.objects.get(slug='india')
        self.city = CommerceCity.objects.create(
            market=self.market,
            name='Bhubaneswar',
        )
        self.area = CommerceArea.objects.create(
            city=self.city,
            name='KIIT Area',
        )
        self.merchant_user = User.objects.create_user(
            username='branch-api-merchant',
            email='branch-api-merchant@example.com',
        )
        self.manager = User.objects.create_user(
            username='branch-api-manager',
            first_name='Branch',
            last_name='Manager',
        )
        self.profile = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Branch API Company',
            is_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            market=self.market,
            owner=self.merchant_user,
            rest_name='Branch API Kitchen',
            rest_email='branch-api-kitchen@example.com',
            rest_contact='9000000000',
            rest_address='Campus Road',
            rest_city='Bhubaneswar',
            branch_name='KIIT Food Branch',
            branch_code='IN-BBI-KIIT-FOOD',
            branch_type=Restaurant.BRANCH_TYPE_FOOD,
            country_code='IN',
            city_ref=self.city,
            area_ref=self.area,
            branch_manager=self.manager,
            pickup_latitude=Decimal('20.353000'),
            pickup_longitude=Decimal('85.819000'),
            delivery_radius_km=Decimal('10.00'),
            is_active=True,
            is_open=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Branch Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )

    def restaurant_results(self, response):
        return response.data.get('results', response.data)

    def test_public_restaurant_api_keeps_old_fields_and_adds_branch_fields(self):
        response = self.client.get('/api/v1/restaurants/')

        self.assertEqual(response.status_code, 200)
        restaurants = self.restaurant_results(response)
        branch = next(item for item in restaurants if item['id'] == self.restaurant.id)
        self.assertEqual(branch['rest_name'], 'Branch API Kitchen')
        self.assertEqual(branch['rest_city'], 'Bhubaneswar')
        self.assertEqual(branch['branch_name'], 'KIIT Food Branch')
        self.assertEqual(branch['branch_code'], 'IN-BBI-KIIT-FOOD')
        self.assertEqual(branch['branch_type'], Restaurant.BRANCH_TYPE_FOOD)
        self.assertEqual(branch['country_code'], 'IN')
        self.assertEqual(branch['city'], 'Bhubaneswar')
        self.assertEqual(branch['area'], 'KIIT Area')
        self.assertEqual(branch['city_ref'], self.city.id)
        self.assertEqual(branch['area_ref'], self.area.id)
        self.assertEqual(branch['branch_manager_name'], 'Branch Manager')

    def test_public_restaurant_filters_by_branch_fields(self):
        other_merchant = User.objects.create_user(username='branch-api-other-merchant')
        MerchantProfile.objects.create(user=other_merchant, is_verified=True)
        other_city = CommerceCity.objects.create(
            market=self.market,
            name='Cuttack',
        )
        other_area = CommerceArea.objects.create(city=other_city, name='College Square')
        Restaurant.objects.create(
            market=self.market,
            owner=other_merchant,
            rest_name='Other Grocery',
            rest_email='branch-api-other@example.com',
            rest_contact='9000000001',
            rest_address='Other Road',
            rest_city='Cuttack',
            branch_type=Restaurant.BRANCH_TYPE_GROCERY,
            country_code='IN',
            city_ref=other_city,
            area_ref=other_area,
            is_active=True,
        )

        response = self.client.get('/api/v1/restaurants/', {
            'country_code': 'IN',
            'city': 'bhubaneswar',
            'area': 'kiit-area',
            'branch_type': Restaurant.BRANCH_TYPE_FOOD,
            'market': 'india',
        })

        self.assertEqual(response.status_code, 200)
        restaurants = self.restaurant_results(response)
        self.assertEqual([item['id'] for item in restaurants], [self.restaurant.id])

    def test_merchant_old_create_payload_still_works(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post('/api/v1/merchants/restaurants/', {
            'rest_name': 'Old Payload Kitchen',
            'rest_email': 'old-payload-kitchen@example.com',
            'rest_contact': '9000000002',
            'rest_address': 'Old Payload Road',
            'rest_city': 'Bhubaneswar',
            'delivery_fee': '0.00',
            'min_order_amount': '0.00',
            'delivery_radius_km': '10.00',
            'estimated_prep_minutes': 20,
            'pickup_latitude': '20.353000',
            'pickup_longitude': '85.819000',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        restaurant = Restaurant.objects.get(id=response.data['id'])
        self.assertEqual(restaurant.rest_name, 'Old Payload Kitchen')
        self.assertEqual(restaurant.branch_name, 'Old Payload Kitchen')
        self.assertEqual(restaurant.branch_type, Restaurant.BRANCH_TYPE_FOOD)

    def test_merchant_can_create_and_update_branch_fields(self):
        self.client.force_authenticate(self.merchant_user)

        create_response = self.client.post('/api/v1/merchants/restaurants/', {
            'rest_name': 'Merchant Branch Store',
            'rest_email': 'merchant-branch-store@example.com',
            'rest_contact': '9000000003',
            'rest_address': 'Branch Road',
            'rest_city': 'Bhubaneswar',
            'branch_name': 'Merchant Grocery Branch',
            'branch_code': 'IN-BBI-KIIT-GROCERY',
            'branch_type': Restaurant.BRANCH_TYPE_GROCERY,
            'country_code': 'IN',
            'city_ref': self.city.id,
            'area_ref': self.area.id,
            'branch_manager': self.manager.id,
            'delivery_fee': '0.00',
            'min_order_amount': '0.00',
            'delivery_radius_km': '10.00',
            'estimated_prep_minutes': 20,
        }, format='json')

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data['branch_name'], 'Merchant Grocery Branch')
        self.assertEqual(create_response.data['city'], 'Bhubaneswar')
        self.assertEqual(create_response.data['area'], 'KIIT Area')

        update_response = self.client.patch(
            f'/api/v1/merchants/restaurants/{create_response.data["id"]}/',
            {
                'branch_name': 'Updated Retail Branch',
                'branch_type': Restaurant.BRANCH_TYPE_RETAIL,
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data['branch_name'], 'Updated Retail Branch')
        self.assertEqual(update_response.data['branch_type'], Restaurant.BRANCH_TYPE_RETAIL)

    def test_geography_endpoints_return_cities_and_areas(self):
        cities = self.client.get('/api/v1/markets/cities/', {
            'market': 'india',
            'country_code': 'IN',
        })
        areas = self.client.get('/api/v1/markets/areas/', {
            'city': self.city.slug,
            'country_code': 'IN',
        })

        self.assertEqual(cities.status_code, 200)
        self.assertEqual(areas.status_code, 200)
        self.assertEqual(cities.data[0]['name'], 'Bhubaneswar')
        self.assertEqual(cities.data[0]['country_code'], 'IN')
        self.assertEqual(areas.data[0]['name'], 'KIIT Area')
        self.assertEqual(areas.data[0]['city'], self.city.id)

    def test_operations_restaurant_endpoint_includes_branch_fields(self):
        operator = User.objects.create_superuser(
            username='branch-api-operator',
            email='branch-api-operator@example.com',
            password='password',
        )
        self.client.force_authenticate(operator)

        response = self.client.get('/api/v1/operations/restaurants/', {
            'branch_type': Restaurant.BRANCH_TYPE_FOOD,
            'city': 'bhubaneswar',
        })

        self.assertEqual(response.status_code, 200)
        branch = next(item for item in response.data if item['id'] == self.restaurant.id)
        self.assertEqual(branch['branch_name'], 'KIIT Food Branch')
        self.assertEqual(branch['branch_code'], 'IN-BBI-KIIT-FOOD')
        self.assertEqual(branch['country_code'], 'IN')
        self.assertEqual(branch['area'], 'KIIT Area')

    def test_checkout_still_works_with_branch_restaurant(self):
        customer = User.objects.create_user(username='branch-api-customer')
        self.client.force_authenticate(customer)

        response = self.client.post('/api/v1/orders/', {
            'delivery_address': 'Customer Address',
            'contact_phone': '9000000004',
            'latitude': '20.354000',
            'longitude': '85.820000',
            'items': [{'food_id': self.food.id, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.pickup_branch, self.restaurant)
        self.assertNotIn('pickup_branch', response.data)

    def test_merchant_orders_expose_pickup_branch_fields(self):
        customer = User.objects.create_user(username='branch-api-order-customer')
        order = Order.objects.create(
            customer=customer,
            status='CONFIRMED',
            pickup_branch=self.restaurant,
            delivery_address='Customer Address',
            contact_phone='9000000005',
            total_amount=Decimal('100.00'),
        )
        Payment.objects.create(order=order, method='COD', status='SUCCESS')
        order.items.create(food=self.food, quantity=1, price=Decimal('100.00'))
        self.client.force_authenticate(self.merchant_user)

        response = self.client.get('/api/v1/merchants/orders/')

        self.assertEqual(response.status_code, 200)
        merchant_orders = response.data.get('results', response.data)
        merchant_order = next(item for item in merchant_orders if item['id'] == order.id)
        self.assertEqual(merchant_order['pickup_branch'], self.restaurant.id)
        self.assertEqual(merchant_order['pickup_branch_name'], 'KIIT Food Branch')
        self.assertEqual(merchant_order['branch_type'], Restaurant.BRANCH_TYPE_FOOD)

    def test_operations_orders_dispatch_and_support_expose_pickup_branch_fields(self):
        operator = User.objects.create_superuser(
            username='branch-api-ops-order',
            email='branch-api-ops-order@example.com',
            password='password',
        )
        customer = User.objects.create_user(username='branch-api-ops-customer')
        order = Order.objects.create(
            customer=customer,
            status='READY_FOR_PICKUP',
            pickup_branch=self.restaurant,
            delivery_address='Customer Address',
            contact_phone='9000000006',
            total_amount=Decimal('100.00'),
        )
        Payment.objects.create(order=order, method='COD', status='SUCCESS')
        order.items.create(food=self.food, quantity=1, price=Decimal('100.00'))
        Delivery.objects.create(order=order)
        SupportTicket.objects.create(
            customer=customer,
            order=order,
            category='OTHER',
            description='Need help',
        )
        self.client.force_authenticate(operator)

        orders = self.client.get('/api/v1/operations/orders/?status=open')
        dispatch = self.client.get('/api/v1/operations/dispatch/')
        support = self.client.get('/api/v1/operations/support/')

        self.assertEqual(orders.status_code, 200)
        self.assertEqual(dispatch.status_code, 200)
        self.assertEqual(support.status_code, 200)
        operation_order = next(item for item in orders.data if item['id'] == order.id)
        operation_dispatch = next(
            item for item in dispatch.data if item['order_id'] == order.id
        )
        operation_ticket = next(
            item for item in support.data if item['order_id'] == order.id
        )
        for payload in (operation_order, operation_dispatch, operation_ticket):
            self.assertEqual(payload['pickup_branch'], self.restaurant.id)
            self.assertEqual(payload['pickup_branch_name'], 'KIIT Food Branch')
            self.assertEqual(payload['branch_type'], Restaurant.BRANCH_TYPE_FOOD)

    def test_restaurant_search_with_location_still_works_with_branch_fields(self):
        response = self.client.get('/api/v1/restaurants/', {
            'search': 'Branch Meal',
            'latitude': '20.354000',
            'longitude': '85.820000',
        })

        self.assertEqual(response.status_code, 200)
        restaurants = self.restaurant_results(response)
        self.assertEqual(restaurants[0]['id'], self.restaurant.id)
        self.assertIn('distance_km', restaurants[0])
        self.assertIn('is_serviceable', restaurants[0])
