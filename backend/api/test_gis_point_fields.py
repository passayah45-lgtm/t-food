from decimal import Decimal
from io import StringIO
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from customers.models import DeliveryAddress
from delivery.models import Delivery, DeliveryPartner
from orders.models import Order
from restaurants.models import FoodItem, MerchantProfile, Restaurant


def point(longitude='77.594600', latitude='12.971600'):
    if not settings.GEODJANGO_AVAILABLE:
        return f'SRID=4326;POINT({longitude} {latitude})'

    from django.contrib.gis.geos import Point

    return Point(float(longitude), float(latitude), srid=4326)


def point_coordinates(value):
    if hasattr(value, 'x') and hasattr(value, 'y'):
        return round(float(value.x), 6), round(float(value.y), 6)

    match = re.search(r'POINT\s*\(?\s*([-0-9.]+)\s+([-0-9.]+)\s*\)?', str(value))
    if not match:
        raise AssertionError(f'Could not parse point value: {value}')
    return round(float(match.group(1)), 6), round(float(match.group(2)), 6)


class GISPointModelTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='gis-customer')
        self.merchant_user = User.objects.create_user(username='gis-merchant')
        MerchantProfile.objects.create(user=self.merchant_user, is_verified=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='GIS Kitchen',
            rest_email='gis@example.com',
            rest_contact='1234567890',
            rest_address='GIS Road',
            rest_city='Bhubaneswar',
            pickup_latitude=Decimal('20.296100'),
            pickup_longitude=Decimal('85.824500'),
            is_active=True,
            is_open=True,
        )

    def test_models_can_save_null_points(self):
        restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='GIS Null Kitchen',
            rest_email='gis-null@example.com',
            rest_contact='1234567890',
            rest_address='GIS Null Road',
            rest_city='Bhubaneswar',
        )
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='GIS Customer',
            phone='1234567890',
            address='Null Point Street',
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-partner'),
            partner_name='GIS Partner',
            partner_phone='1234567890',
            transport_details='Bike',
        )
        order = Order.objects.create(customer=self.customer)
        delivery = Delivery.objects.create(order=order)

        self.assertIsNone(restaurant.pickup_point)
        self.assertIsNone(address.location_point)
        self.assertIsNone(partner.current_point)
        self.assertIsNone(order.delivery_point)
        self.assertIsNone(delivery.current_point)

    def test_models_can_save_valid_points(self):
        gis_point = point()
        self.restaurant.pickup_point = gis_point
        self.restaurant.save(update_fields=['pickup_point'])

        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='GIS Customer',
            phone='1234567890',
            address='Point Street',
            location_point=gis_point,
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-point-partner'),
            partner_name='GIS Point Partner',
            partner_phone='1234567890',
            transport_details='Bike',
            current_point=gis_point,
        )
        order = Order.objects.create(
            customer=self.customer,
            delivery_point=gis_point,
        )
        delivery = Delivery.objects.create(
            order=order,
            current_point=gis_point,
        )

        self.assertIsNotNone(Restaurant.objects.get(id=self.restaurant.id).pickup_point)
        self.assertIsNotNone(DeliveryAddress.objects.get(id=address.id).location_point)
        self.assertIsNotNone(DeliveryPartner.objects.get(id=partner.id).current_point)
        self.assertIsNotNone(Order.objects.get(id=order.id).delivery_point)
        self.assertIsNotNone(Delivery.objects.get(id=delivery.id).current_point)

    def test_old_lat_lng_fields_still_save_normally(self):
        self.restaurant.pickup_latitude = Decimal('20.300000')
        self.restaurant.pickup_longitude = Decimal('85.820000')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])

        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='GIS Customer',
            phone='1234567890',
            address='Lat Lng Street',
            latitude=Decimal('20.296100'),
            longitude=Decimal('85.824500'),
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-latlng-partner'),
            partner_name='GIS LatLng Partner',
            partner_phone='1234567890',
            transport_details='Bike',
            current_latitude=Decimal('20.296100'),
            current_longitude=Decimal('85.824500'),
        )
        order = Order.objects.create(
            customer=self.customer,
            latitude=Decimal('20.296100'),
            longitude=Decimal('85.824500'),
        )
        delivery = Delivery.objects.create(
            order=order,
            current_latitude=20.2961,
            current_longitude=85.8245,
        )

        self.assertEqual(address.latitude, Decimal('20.296100'))
        self.assertEqual(partner.current_latitude, Decimal('20.296100'))
        self.assertEqual(order.latitude, Decimal('20.296100'))
        self.assertEqual(delivery.current_latitude, 20.2961)


class GISPointWriteSyncTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='gis-sync-customer')
        self.merchant_user = User.objects.create_user(username='gis-sync-merchant')
        MerchantProfile.objects.create(user=self.merchant_user, is_verified=True)

    def create_restaurant(self, latitude=None, longitude=None):
        return Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Sync Kitchen',
            rest_email='sync@example.com',
            rest_contact='1234567890',
            rest_address='Sync Road',
            rest_city='Bhubaneswar',
            pickup_latitude=latitude,
            pickup_longitude=longitude,
            is_active=True,
            is_open=True,
        )

    def test_creating_with_lat_lng_creates_points(self):
        restaurant = self.create_restaurant(Decimal('20.296100'), Decimal('85.824500'))
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Sync Customer',
            phone='1234567890',
            address='Sync Street',
            latitude=Decimal('12.971600'),
            longitude=Decimal('77.594600'),
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-sync-partner'),
            partner_name='GIS Sync Partner',
            partner_phone='1234567890',
            transport_details='Bike',
            current_latitude=Decimal('19.076000'),
            current_longitude=Decimal('72.877700'),
        )
        order = Order.objects.create(
            customer=self.customer,
            latitude=Decimal('28.613900'),
            longitude=Decimal('77.209000'),
        )
        delivery = Delivery.objects.create(
            order=Order.objects.create(customer=self.customer),
            current_latitude=22.5726,
            current_longitude=88.3639,
        )

        self.assertEqual(point_coordinates(restaurant.pickup_point), (85.8245, 20.2961))
        self.assertEqual(point_coordinates(address.location_point), (77.5946, 12.9716))
        self.assertEqual(point_coordinates(partner.current_point), (72.8777, 19.076))
        self.assertEqual(point_coordinates(order.delivery_point), (77.209, 28.6139))
        self.assertEqual(point_coordinates(delivery.current_point), (88.3639, 22.5726))

    def test_updating_lat_lng_updates_points_with_update_fields(self):
        restaurant = self.create_restaurant(Decimal('20.296100'), Decimal('85.824500'))
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Sync Customer',
            phone='1234567890',
            address='Sync Street',
            latitude=Decimal('12.971600'),
            longitude=Decimal('77.594600'),
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-sync-update-partner'),
            partner_name='GIS Sync Update Partner',
            partner_phone='1234567890',
            transport_details='Bike',
            current_latitude=Decimal('19.076000'),
            current_longitude=Decimal('72.877700'),
        )
        order = Order.objects.create(
            customer=self.customer,
            latitude=Decimal('28.613900'),
            longitude=Decimal('77.209000'),
        )
        delivery = Delivery.objects.create(
            order=Order.objects.create(customer=self.customer),
            current_latitude=22.5726,
            current_longitude=88.3639,
        )

        restaurant.pickup_latitude = Decimal('20.300000')
        restaurant.pickup_longitude = Decimal('85.830000')
        restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        address.latitude = Decimal('13.000000')
        address.longitude = Decimal('78.000000')
        address.save(update_fields=['latitude', 'longitude'])
        partner.current_latitude = Decimal('20.000000')
        partner.current_longitude = Decimal('73.000000')
        partner.save(update_fields=['current_latitude', 'current_longitude'])
        order.latitude = Decimal('29.000000')
        order.longitude = Decimal('78.000000')
        order.save(update_fields=['latitude', 'longitude'])
        delivery.current_latitude = 23.0
        delivery.current_longitude = 89.0
        delivery.save(update_fields=['current_latitude', 'current_longitude'])

        restaurant.refresh_from_db()
        address.refresh_from_db()
        partner.refresh_from_db()
        order.refresh_from_db()
        delivery.refresh_from_db()

        self.assertEqual(point_coordinates(restaurant.pickup_point), (85.83, 20.3))
        self.assertEqual(point_coordinates(address.location_point), (78.0, 13.0))
        self.assertEqual(point_coordinates(partner.current_point), (73.0, 20.0))
        self.assertEqual(point_coordinates(order.delivery_point), (78.0, 29.0))
        self.assertEqual(point_coordinates(delivery.current_point), (89.0, 23.0))

    def test_null_lat_lng_leaves_points_null(self):
        restaurant = self.create_restaurant()
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Null Sync Customer',
            phone='1234567890',
            address='Null Sync Street',
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-sync-null-partner'),
            partner_name='GIS Sync Null Partner',
            partner_phone='1234567890',
            transport_details='Bike',
        )
        order = Order.objects.create(customer=self.customer)
        delivery = Delivery.objects.create(order=Order.objects.create(customer=self.customer))

        self.assertIsNone(restaurant.pickup_point)
        self.assertIsNone(address.location_point)
        self.assertIsNone(partner.current_point)
        self.assertIsNone(order.delivery_point)
        self.assertIsNone(delivery.current_point)

    def test_invalid_lat_lng_does_not_create_bad_points(self):
        restaurant = self.create_restaurant(Decimal('91.000000'), Decimal('85.824500'))
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Invalid Sync Customer',
            phone='1234567890',
            address='Invalid Sync Street',
            latitude=Decimal('12.971600'),
            longitude=Decimal('181.000000'),
        )
        partner = DeliveryPartner.objects.create(
            user=User.objects.create_user(username='gis-sync-invalid-partner'),
            partner_name='GIS Sync Invalid Partner',
            partner_phone='1234567890',
            transport_details='Bike',
            current_latitude=Decimal('-91.000000'),
            current_longitude=Decimal('72.877700'),
        )
        order = Order.objects.create(
            customer=self.customer,
            latitude=Decimal('28.613900'),
            longitude=Decimal('-181.000000'),
        )
        delivery = Delivery.objects.create(
            order=Order.objects.create(customer=self.customer),
            current_latitude=95.0,
            current_longitude=88.3639,
        )

        self.assertIsNone(restaurant.pickup_point)
        self.assertIsNone(address.location_point)
        self.assertIsNone(partner.current_point)
        self.assertIsNone(order.delivery_point)
        self.assertIsNone(delivery.current_point)

    def test_existing_point_is_not_overwritten_when_lat_lng_unchanged(self):
        existing_point = point('77.000000', '12.000000')
        restaurant = self.create_restaurant(Decimal('20.296100'), Decimal('85.824500'))
        restaurant.pickup_point = existing_point
        restaurant.save(update_fields=['pickup_point'])

        restaurant.rest_city = 'Cuttack'
        restaurant.save(update_fields=['rest_city'])
        restaurant.refresh_from_db()

        self.assertEqual(point_coordinates(restaurant.pickup_point), (77.0, 12.0))


class GISPointBackfillTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='gis-backfill-customer')
        self.merchant_user = User.objects.create_user(username='gis-backfill-merchant')
        MerchantProfile.objects.create(user=self.merchant_user, is_verified=True)

    def create_restaurant(self, name, latitude=None, longitude=None):
        return Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name=name,
            rest_email=f'{name.lower().replace(" ", "-")}@example.com',
            rest_contact='1234567890',
            rest_address='Backfill Road',
            rest_city='Bhubaneswar',
            pickup_latitude=latitude,
            pickup_longitude=longitude,
            is_active=True,
            is_open=True,
        )

    def create_partner(self, username, latitude=None, longitude=None):
        return DeliveryPartner.objects.create(
            user=User.objects.create_user(username=username),
            partner_name=username,
            partner_phone='1234567890',
            transport_details='Bike',
            current_latitude=latitude,
            current_longitude=longitude,
        )

    def run_backfill(self):
        output = StringIO()
        call_command('backfill_gis_points', stdout=output)
        return output.getvalue()

    def test_backfill_sets_points_from_valid_coordinates(self):
        restaurant = self.create_restaurant(
            'Valid Backfill Kitchen',
            Decimal('20.296100'),
            Decimal('85.824500'),
        )
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Valid Customer',
            phone='1234567890',
            address='Valid Street',
            latitude=Decimal('12.971600'),
            longitude=Decimal('77.594600'),
        )
        partner = self.create_partner(
            'valid-backfill-partner',
            Decimal('19.076000'),
            Decimal('72.877700'),
        )
        order = Order.objects.create(
            customer=self.customer,
            latitude=Decimal('28.613900'),
            longitude=Decimal('77.209000'),
        )
        delivery = Delivery.objects.create(
            order=Order.objects.create(customer=self.customer),
            current_latitude=22.5726,
            current_longitude=88.3639,
        )

        output = self.run_backfill()

        restaurant.refresh_from_db()
        address.refresh_from_db()
        partner.refresh_from_db()
        order.refresh_from_db()
        delivery.refresh_from_db()

        self.assertIn('restaurants: updated=', output)
        self.assertEqual(point_coordinates(restaurant.pickup_point), (85.8245, 20.2961))
        self.assertEqual(point_coordinates(address.location_point), (77.5946, 12.9716))
        self.assertEqual(point_coordinates(partner.current_point), (72.8777, 19.076))
        self.assertEqual(point_coordinates(order.delivery_point), (77.209, 28.6139))
        self.assertEqual(point_coordinates(delivery.current_point), (88.3639, 22.5726))

    def test_backfill_leaves_null_coordinates_null(self):
        restaurant = self.create_restaurant('Null Backfill Kitchen')
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Null Customer',
            phone='1234567890',
            address='Null Street',
        )
        partner = self.create_partner('null-backfill-partner')
        order = Order.objects.create(customer=self.customer)
        delivery = Delivery.objects.create(order=Order.objects.create(customer=self.customer))

        self.run_backfill()

        restaurant.refresh_from_db()
        address.refresh_from_db()
        partner.refresh_from_db()
        order.refresh_from_db()
        delivery.refresh_from_db()

        self.assertIsNone(restaurant.pickup_point)
        self.assertIsNone(address.location_point)
        self.assertIsNone(partner.current_point)
        self.assertIsNone(order.delivery_point)
        self.assertIsNone(delivery.current_point)

    def test_backfill_skips_invalid_coordinates(self):
        restaurant = self.create_restaurant(
            'Invalid Backfill Kitchen',
            Decimal('91.000000'),
            Decimal('85.824500'),
        )
        address = DeliveryAddress.objects.create(
            user=self.customer,
            recipient_name='Invalid Customer',
            phone='1234567890',
            address='Invalid Street',
            latitude=Decimal('12.971600'),
            longitude=Decimal('181.000000'),
        )
        partner = self.create_partner(
            'invalid-backfill-partner',
            Decimal('-91.000000'),
            Decimal('72.877700'),
        )
        order = Order.objects.create(
            customer=self.customer,
            latitude=Decimal('28.613900'),
            longitude=Decimal('-181.000000'),
        )
        delivery = Delivery.objects.create(
            order=Order.objects.create(customer=self.customer),
            current_latitude=95.0,
            current_longitude=88.3639,
        )

        output = self.run_backfill()

        restaurant.refresh_from_db()
        address.refresh_from_db()
        partner.refresh_from_db()
        order.refresh_from_db()
        delivery.refresh_from_db()

        self.assertIn('skipped_invalid=', output)
        self.assertIsNone(restaurant.pickup_point)
        self.assertIsNone(address.location_point)
        self.assertIsNone(partner.current_point)
        self.assertIsNone(order.delivery_point)
        self.assertIsNone(delivery.current_point)

    def test_backfill_is_idempotent_and_does_not_overwrite_existing_points(self):
        existing_point = point('77.000000', '12.000000')
        restaurant = self.create_restaurant(
            'Existing Backfill Kitchen',
            Decimal('20.296100'),
            Decimal('85.824500'),
        )
        restaurant.pickup_point = existing_point
        restaurant.save(update_fields=['pickup_point'])

        self.run_backfill()
        self.run_backfill()

        restaurant.refresh_from_db()
        self.assertEqual(point_coordinates(restaurant.pickup_point), (77.0, 12.0))


class GISPointAPICompatibilityTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='gis-api-customer')
        merchant = User.objects.create_user(username='gis-api-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        self.restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='GIS API Kitchen',
            rest_email='gis-api@example.com',
            rest_contact='1234567890',
            rest_address='GIS API Road',
            rest_city='Bhubaneswar',
            pickup_latitude=Decimal('20.296100'),
            pickup_longitude=Decimal('85.824500'),
            pickup_point=point('85.824500', '20.296100'),
            is_active=True,
            is_open=True,
        )
        FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='GIS Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )

    def test_restaurant_api_does_not_expose_point_field(self):
        response = self.client.get('/api/v1/restaurants/')

        self.assertEqual(response.status_code, 200)
        restaurants = response.data.get('results', response.data)
        self.assertNotIn('pickup_point', restaurants[0])
        self.assertIn('rest_name', restaurants[0])
        self.assertIn('distance_km', restaurants[0])
        self.assertIn('is_serviceable', restaurants[0])

    def test_address_api_does_not_expose_point_field(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            '/api/v1/users/addresses/',
            {
                'recipient_name': 'GIS API Customer',
                'phone': '1234567890',
                'address': 'GIS API Street',
                'latitude': '20.296100',
                'longitude': '85.824500',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn('location_point', response.data)
        self.assertEqual(response.data['latitude'], '20.296100')
        self.assertEqual(response.data['longitude'], '85.824500')
