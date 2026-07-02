import asyncio
from decimal import Decimal
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from delivery.models import Delivery
from delivery.models import DeliveryPartner
from fooddelivery.asgi import application
from markets.models import CommerceArea, CommerceCity, Currency, Market
from operations_access.models import (
    OperationsStaffAreaAccess,
    OperationsStaffProfile,
)
from orders.models import Order, OrderItem, OrderStatusEvent
from payments.models import Payment
from restaurants.models import FoodItem, Restaurant
from restaurants.models import MerchantProfile


TEST_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class OrdersConsumerAuthenticationTests(TransactionTestCase):
    def token_for(self, user):
        return str(AccessToken.for_user(user))

    async def connect(self, token):
        communicator = WebsocketCommunicator(
            application,
            f'/ws/orders/?token={token}',
        )
        connected, _ = await communicator.connect()
        return communicator, connected

    async def assert_connected(self, token):
        communicator, connected = await self.connect(token)
        self.assertTrue(connected)
        self.assertEqual(
            await communicator.receive_json_from(),
            {'type': 'connected'},
        )
        await communicator.disconnect()

    async def assert_rejected(self, path):
        communicator = WebsocketCommunicator(application, path)
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def assert_group_message_received(self, token, group_name):
        communicator, connected = await self.connect(token)
        self.assertTrue(connected)
        self.assertEqual(
            await communicator.receive_json_from(),
            {'type': 'connected'},
        )

        await get_channel_layer().group_send(
            group_name,
            {
                'type': 'realtime.message',
                'payload': {'type': 'group_probe'},
            },
        )
        self.assertEqual(
            await communicator.receive_json_from(),
            {'type': 'group_probe'},
        )
        await communicator.disconnect()

    async def assert_group_message_not_received(self, token, group_name):
        communicator, connected = await self.connect(token)
        self.assertTrue(connected)
        self.assertEqual(
            await communicator.receive_json_from(),
            {'type': 'connected'},
        )

        await get_channel_layer().group_send(
            group_name,
            {
                'type': 'realtime.message',
                'payload': {'type': 'group_probe'},
            },
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(communicator.receive_json_from(), timeout=0.1)
        await communicator.disconnect()

    def test_valid_customer_token_connects(self):
        user = User.objects.create_user(username='ws-customer')

        async_to_sync(self.assert_connected)(self.token_for(user))

    def test_invalid_token_rejects(self):
        async_to_sync(self.assert_rejected)('/ws/orders/?token=not-a-valid-token')

    def test_missing_token_rejects(self):
        async_to_sync(self.assert_rejected)('/ws/orders/')

    def test_expired_token_rejects(self):
        user = User.objects.create_user(username='ws-expired')
        token = AccessToken.for_user(user)
        token.set_exp(from_time=timezone.now() - timedelta(minutes=10), lifetime=timedelta(seconds=1))

        async_to_sync(self.assert_rejected)(f'/ws/orders/?token={token}')

    def test_merchant_token_joins_merchant_group(self):
        user = User.objects.create_user(username='ws-merchant')
        MerchantProfile.objects.create(user=user, is_verified=True)

        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            f'merchant_{user.id}',
        )

    def test_partner_token_joins_partner_group(self):
        user = User.objects.create_user(username='ws-partner')
        DeliveryPartner.objects.create(user=user, partner_name='WS Partner')

        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            f'partner_{user.id}',
        )

    def test_available_verified_partner_token_joins_partners_available_group(self):
        user = User.objects.create_user(username='ws-available-partner')
        DeliveryPartner.objects.create(
            user=user,
            partner_name='WS Available Partner',
            partner_phone='9000000001',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )

        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            'partners_available',
        )

    def test_delivery_available_changed_broadcast_reaches_partner_socket(self):
        user = User.objects.create_user(username='ws-available-broadcast-partner')
        DeliveryPartner.objects.create(
            user=user,
            partner_name='WS Available Broadcast Partner',
            partner_phone='9000000002',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )

        async def assert_available_changed_received():
            communicator, connected = await self.connect(self.token_for(user))
            self.assertTrue(connected)
            self.assertEqual(
                await communicator.receive_json_from(),
                {'type': 'connected'},
            )

            await get_channel_layer().group_send(
                'partners_available',
                {
                    'type': 'realtime.message',
                    'payload': {
                        'type': 'delivery.available_changed',
                        'order_id': 123,
                        'status': 'READY_FOR_PICKUP',
                    },
                },
            )
            self.assertEqual(
                await communicator.receive_json_from(),
                {
                    'type': 'delivery.available_changed',
                    'order_id': 123,
                    'status': 'READY_FOR_PICKUP',
                },
            )
            await communicator.disconnect()

        async_to_sync(assert_available_changed_received)()

    def test_non_partner_token_does_not_join_partners_available_group(self):
        user = User.objects.create_user(username='ws-not-partner')

        async_to_sync(self.assert_group_message_not_received)(
            self.token_for(user),
            'partners_available',
        )

    def test_unavailable_partner_token_does_not_join_partners_available_group(self):
        user = User.objects.create_user(username='ws-unavailable-partner')
        DeliveryPartner.objects.create(
            user=user,
            partner_name='WS Unavailable Partner',
            partner_phone='9000000003',
            transport_details='Bike',
            is_verified=True,
            is_available=False,
        )

        async_to_sync(self.assert_group_message_not_received)(
            self.token_for(user),
            'partners_available',
        )

    def test_staff_token_joins_operations_group(self):
        user = User.objects.create_user(username='ws-operator', is_staff=True)

        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            'operations',
        )

    def test_scoped_operations_profile_joins_only_assigned_operations_groups(self):
        currency = Currency.objects.create(
            code='XOF',
            numeric_code='952',
            name='West African CFA Franc',
        )
        market = Market.objects.create(
            slug='ws-guinea',
            name='WS Guinea',
            country_code='GN',
            default_currency=currency,
            timezone='Africa/Conakry',
        )
        city = CommerceCity.objects.create(
            market=market,
            name='WS Conakry',
            slug='ws-conakry',
        )
        area = CommerceArea.objects.create(
            market=market,
            city=city,
            name='WS Kaloum',
            slug='ws-kaloum',
        )
        user = User.objects.create_user(username='ws-scoped-operator', is_staff=True)
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=OperationsStaffProfile.ROLE_AREA_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        OperationsStaffAreaAccess.objects.create(profile=profile, area=area)

        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            f'operations_area_{area.id}',
        )
        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            f'operations_city_{city.id}',
        )
        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            f'operations_market_{market.id}',
        )
        async_to_sync(self.assert_group_message_received)(
            self.token_for(user),
            'operations_country_GN',
        )
        async_to_sync(self.assert_group_message_not_received)(
            self.token_for(user),
            'operations',
        )


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class OrderBroadcastTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username='broadcast-customer')
        self.merchant = User.objects.create_user(username='broadcast-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.partner_user = User.objects.create_user(username='broadcast-partner')
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Broadcast Partner',
            partner_phone='9000000099',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Broadcast Kitchen',
            rest_email='broadcast@example.com',
            rest_contact='1234567890',
            rest_address='Realtime Road',
            rest_city='Test City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Broadcast Meal',
            food_price=Decimal('150.00'),
            food_categ='Vegetarian',
        )

    async def listen_to_group(self, group):
        layer = get_channel_layer()
        channel = await layer.new_channel()
        await layer.group_add(group, channel)
        return channel

    async def receive_event(self, channel, event_type, attempts=5):
        layer = get_channel_layer()
        seen = []
        for _ in range(attempts):
            message = await asyncio.wait_for(layer.receive(channel), timeout=1)
            payload = message['payload']
            seen.append(payload['type'])
            if payload['type'] == event_type:
                return payload
        self.fail(f'Did not receive {event_type}; saw {seen}.')

    def listen(self, group):
        return async_to_sync(self.listen_to_group)(group)

    def receive(self, channel, event_type):
        return async_to_sync(self.receive_event)(channel, event_type)

    def create_order_with_item(self, status='CONFIRMED'):
        order = Order.objects.create(
            customer=self.customer,
            status=status,
            delivery_address='Customer Street',
            delivery_fee=Decimal('40.00'),
            total_amount=Decimal('190.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price=Decimal('150.00'),
        )
        return order

    def test_order_created_broadcasts_after_commit_to_customer_merchant_and_operations(self):
        customer_channel = self.listen(f'user_{self.customer.id}')
        merchant_channel = self.listen(f'merchant_{self.merchant.id}')
        operations_channel = self.listen('operations')

        from django.db import transaction

        with transaction.atomic():
            order = self.create_order_with_item(status='PLACED')

        expected = {
            'type': 'order.created',
            'order_id': order.id,
            'status': 'PLACED',
        }
        self.assertEqual(self.receive(customer_channel, 'order.created'), expected)
        self.assertEqual(self.receive(merchant_channel, 'order.created'), expected)
        self.assertEqual(self.receive(operations_channel, 'order.created'), expected)
        self.assertTrue(OrderStatusEvent.objects.filter(
            order=order,
            status='PLACED',
        ).exists())

    def test_order_created_broadcasts_to_scoped_operations_groups_when_scope_exists(self):
        currency = Currency.objects.create(
            code='SLE',
            numeric_code='925',
            name='Sierra Leonean Leone',
        )
        market = Market.objects.create(
            slug='broadcast-guinea',
            name='Broadcast Guinea',
            country_code='GN',
            default_currency=currency,
            timezone='Africa/Conakry',
        )
        city = CommerceCity.objects.create(
            market=market,
            name='Broadcast Conakry',
            slug='broadcast-conakry',
        )
        area = CommerceArea.objects.create(
            market=market,
            city=city,
            name='Broadcast Kaloum',
            slug='broadcast-kaloum',
        )
        self.restaurant.market = market
        self.restaurant.country_code = 'GN'
        self.restaurant.city_ref = city
        self.restaurant.area_ref = area
        self.restaurant.save(update_fields=['market', 'country_code', 'city_ref', 'area_ref', 'updated_at'])

        market_channel = self.listen(f'operations_market_{market.id}')
        country_channel = self.listen('operations_country_GN')
        city_channel = self.listen(f'operations_city_{city.id}')
        area_channel = self.listen(f'operations_area_{area.id}')

        from django.db import transaction

        with transaction.atomic():
            order = self.create_order_with_item(status='PLACED')
            order.market = market
            order.pickup_branch = self.restaurant
            order.save(update_fields=['market', 'pickup_branch', 'updated_at'])

        expected = {
            'type': 'order.created',
            'order_id': order.id,
            'status': 'PLACED',
        }
        self.assertEqual(self.receive(market_channel, 'order.created'), expected)
        self.assertEqual(self.receive(country_channel, 'order.created'), expected)
        self.assertEqual(self.receive(city_channel, 'order.created'), expected)
        self.assertEqual(self.receive(area_channel, 'order.created'), expected)

    def test_order_status_change_broadcasts_without_changing_order_behavior(self):
        order = self.create_order_with_item()
        customer_channel = self.listen(f'user_{self.customer.id}')
        merchant_channel = self.listen(f'merchant_{self.merchant.id}')
        operations_channel = self.listen('operations')

        order.status = 'PREPARING'
        order.save(update_fields=['status', 'updated_at'])

        expected = {
            'type': 'order.status_changed',
            'order_id': order.id,
            'status': 'PREPARING',
            'previous_status': 'CONFIRMED',
        }
        self.assertEqual(
            self.receive(customer_channel, 'order.status_changed'),
            expected,
        )
        self.assertEqual(
            self.receive(merchant_channel, 'order.status_changed'),
            expected,
        )
        self.assertEqual(
            self.receive(operations_channel, 'order.status_changed'),
            expected,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'PREPARING')
        self.assertTrue(OrderStatusEvent.objects.filter(
            order=order,
            status='PREPARING',
        ).exists())

    def test_ready_for_pickup_broadcasts_available_delivery_invalidation(self):
        order = self.create_order_with_item(status='PREPARING')
        partners_channel = self.listen('partners_available')
        operations_channel = self.listen('operations')

        order.status = 'READY_FOR_PICKUP'
        order.save(update_fields=['status', 'updated_at'])

        expected = {
            'type': 'delivery.available_changed',
            'order_id': order.id,
            'status': 'READY_FOR_PICKUP',
        }
        self.assertEqual(
            self.receive(partners_channel, 'delivery.available_changed'),
            expected,
        )
        self.assertEqual(
            self.receive(operations_channel, 'delivery.available_changed'),
            expected,
        )

    def test_delivery_status_change_broadcasts_from_partner_status_api(self):
        order = self.create_order_with_item(status='READY_FOR_PICKUP')
        Payment.objects.create(order=order, method='COD', status='PENDING')
        delivery = Delivery.objects.create(
            order=order,
            delivery_partner=self.partner,
        )
        self.partner.is_available = False
        self.partner.save(update_fields=['is_available'])
        customer_channel = self.listen(f'user_{self.customer.id}')
        merchant_channel = self.listen(f'merchant_{self.merchant.id}')
        partner_channel = self.listen(f'partner_{self.partner_user.id}')
        operations_channel = self.listen('operations')

        self.client.force_authenticate(self.partner_user)
        response = self.client.patch(
            f'/api/v1/delivery/partner/{delivery.id}/status/',
            {'status': 'PICKED_UP'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        expected = {
            'type': 'delivery.status_changed',
            'delivery_id': delivery.id,
            'order_id': order.id,
            'status': 'PICKED_UP',
            'previous_status': 'ASSIGNED',
        }
        self.assertEqual(
            self.receive(customer_channel, 'delivery.status_changed'),
            expected,
        )
        self.assertEqual(
            self.receive(merchant_channel, 'delivery.status_changed'),
            expected,
        )
        self.assertEqual(
            self.receive(partner_channel, 'delivery.status_changed'),
            expected,
        )
        self.assertEqual(
            self.receive(operations_channel, 'delivery.status_changed'),
            expected,
        )
        delivery.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(delivery.status, 'PICKED_UP')
        self.assertEqual(order.status, 'READY_FOR_PICKUP')
