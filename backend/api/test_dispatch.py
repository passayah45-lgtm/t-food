from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from rest_framework.test import APITestCase

from delivery.models import Delivery, DeliveryPartner, MerchantRider
from delivery.services import (
    auto_assign_delivery,
    claim_pending_delivery,
    get_branch_preferred_riders,
    get_merchant_preferred_riders,
    get_order_pickup_branch,
    get_preferred_merchant_riders,
    notify_delivery_candidates,
)
from ledger.models import LedgerEntry, LedgerTransaction
from notifications.models import Notification
from orders.models import Order, OrderItem
from payments.models import MerchantPayoutAudit, PartnerPayoutAudit, Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class DispatchApiTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='dispatch-customer')
        self.admin = User.objects.create_user(username='dispatch-admin', is_staff=True)
        self.merchant_user = User.objects.create_user(username='dispatch-merchant')
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Dispatch Merchant',
            is_verified=True,
        )
        self.other_merchant_user = User.objects.create_user(username='other-dispatch-merchant')
        self.other_merchant = MerchantProfile.objects.create(
            user=self.other_merchant_user,
            business_name='Other Dispatch Merchant',
            is_verified=True,
        )
        self.driver_user = User.objects.create_user(username='dispatch-driver')
        self.driver = DeliveryPartner.objects.create(
            user=self.driver_user,
            partner_name='Dispatch Driver',
            partner_phone='9000000010',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )
        self.other_driver_user = User.objects.create_user(username='other-driver')
        self.other_driver = DeliveryPartner.objects.create(
            user=self.other_driver_user,
            partner_name='Other Driver',
            partner_phone='9000000011',
            transport_details='Scooter',
            is_verified=True,
            is_available=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Dispatch Kitchen',
            branch_name='Dispatch Pickup Counter',
            rest_email='dispatch@example.com',
            rest_contact='1234567890',
            rest_address='Kitchen Road',
            rest_city='Test City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Delivery Meal',
            food_price=Decimal('200.00'),
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='READY_FOR_PICKUP',
            delivery_address='Customer Street',
            delivery_fee=Decimal('40.00'),
            merchant_payout=Decimal('180.00'),
            total_amount=Decimal('220.00'),
        )
        OrderItem.objects.create(
            order=self.order, food=self.food, quantity=1, price=Decimal('200.00')
        )
        Payment.objects.create(order=self.order, method='CARD', status='SUCCESS')
        self.delivery = Delivery.objects.create(order=self.order)

    def create_waiting_delivery(
        self,
        *,
        restaurant_name,
        latitude,
        longitude,
        email,
    ):
        restaurant = Restaurant.objects.create(
            rest_name=restaurant_name,
            rest_email=email,
            rest_contact='1234567890',
            rest_address=f'{restaurant_name} Road',
            rest_city='Test City',
            pickup_latitude=Decimal(str(latitude)),
            pickup_longitude=Decimal(str(longitude)),
            is_active=True,
        )
        food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name=f'{restaurant_name} Meal',
            food_price=Decimal('200.00'),
            food_categ='Vegetarian',
        )
        order = Order.objects.create(
            customer=self.customer,
            status='READY_FOR_PICKUP',
            delivery_address='Customer Street',
            delivery_fee=Decimal('40.00'),
            total_amount=Decimal('220.00'),
        )
        OrderItem.objects.create(
            order=order, food=food, quantity=1, price=Decimal('200.00')
        )
        Payment.objects.create(order=order, method='CARD', status='SUCCESS')
        return Delivery.objects.create(order=order)

    def test_available_delivery_can_be_claimed_once(self):
        auto_assign_delivery(self.order)
        self.client.force_authenticate(self.driver_user)
        available = self.client.get('/api/v1/delivery/available/')
        self.assertEqual(available.status_code, 200)
        self.assertEqual(available.data['count'], 1)

        claimed = self.client.post(
            f'/api/v1/delivery/available/{self.delivery.id}/claim/'
        )
        self.assertEqual(claimed.status_code, 200)
        self.delivery.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.delivery.delivery_partner, self.driver)
        self.assertFalse(self.driver.is_available)
        self.assertRegex(self.delivery.confirmation_code, r'^\d{6}$')
        self.assertTrue(Notification.objects.filter(
            user=self.customer,
            title__contains='Delivery partner assigned',
        ).exists())
        self.assertFalse(Notification.objects.filter(
            user=self.other_driver_user,
            title=f'Pickup available for order #{self.order.id}',
        ).exists())

        self.client.force_authenticate(self.other_driver_user)
        second_claim = self.client.post(
            f'/api/v1/delivery/available/{self.delivery.id}/claim/'
        )
        self.assertEqual(second_claim.status_code, 409)

    def test_partner_delivery_payload_includes_pickup_contact_and_distance(self):
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        self.order.pickup_branch = self.restaurant
        self.order.save(update_fields=['pickup_branch'])
        self.driver.current_latitude = Decimal('12.972000')
        self.driver.current_longitude = Decimal('77.595000')
        self.driver.location_updated_at = timezone.now()
        self.driver.save(update_fields=[
            'current_latitude', 'current_longitude', 'location_updated_at',
        ])
        claim_pending_delivery(self.delivery.id, self.driver)

        self.client.force_authenticate(self.driver_user)
        response = self.client.get('/api/v1/delivery/partner/')

        self.assertEqual(response.status_code, 200)
        delivery = response.data['results'][0]
        self.assertEqual(delivery['restaurant_name'], 'Dispatch Kitchen')
        self.assertEqual(delivery['pickup_branch_name'], 'Dispatch Pickup Counter')
        self.assertEqual(delivery['pickup_phone'], '1234567890')
        self.assertIn('Kitchen Road', delivery['pickup_address'])
        self.assertEqual(delivery['pickup_city'], 'Test City')
        self.assertIsNotNone(delivery['pickup_latitude'])
        self.assertIsNotNone(delivery['pickup_longitude'])
        self.assertIsNotNone(delivery['pickup_distance_km'])

    def test_busy_partner_cannot_claim_waiting_delivery(self):
        self.driver.is_available = False
        self.driver.save(update_fields=['is_available'])
        self.client.force_authenticate(self.driver_user)
        response = self.client.post(
            f'/api/v1/delivery/available/{self.delivery.id}/claim/'
        )
        self.assertEqual(response.status_code, 409)
        available = self.client.get('/api/v1/delivery/available/')
        self.assertEqual(available.data['count'], 0)

    def test_ready_order_is_broadcast_without_automatic_assignment(self):
        delivery = auto_assign_delivery(self.order)
        delivery.refresh_from_db()
        self.assertIsNone(delivery.delivery_partner)
        self.assertTrue(Notification.objects.filter(
            user=self.driver_user,
            title=f'Pickup available for order #{self.order.id}',
        ).exists())
        self.assertTrue(Notification.objects.filter(
            user=self.other_driver_user,
            title=f'Pickup available for order #{self.order.id}',
        ).exists())

    def test_customer_receives_shared_partner_location(self):
        claim_pending_delivery(self.delivery.id, self.driver)
        self.client.force_authenticate(self.driver_user)
        updated = self.client.patch(
            f'/api/v1/delivery/partner/{self.delivery.id}/location/',
            {'latitude': 12.9716, 'longitude': 77.5946},
            format='json',
        )
        self.assertEqual(updated.status_code, 200)

        self.client.force_authenticate(self.customer)
        tracking = self.client.get(f'/api/v1/orders/{self.order.id}/')
        self.assertEqual(tracking.status_code, 200)
        self.assertEqual(float(tracking.data['delivery']['current_latitude']), 12.9716)
        self.assertEqual(tracking.data['restaurant']['name'], 'Dispatch Pickup Counter')
        self.assertEqual(tracking.data['restaurant']['phone'], '1234567890')
        self.assertEqual(tracking.data['delivery']['partner_phone'], '9000000010')
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.current_latitude, Decimal('12.971600'))
        self.assertEqual(self.driver.current_longitude, Decimal('77.594600'))
        self.assertIsNotNone(self.driver.location_updated_at)

    def test_assigned_partner_can_mark_delivery_picked_up(self):
        claim_pending_delivery(self.delivery.id, self.driver)
        self.client.force_authenticate(self.driver_user)
        response = self.client.patch(
            f'/api/v1/delivery/partner/{self.delivery.id}/status/',
            {'status': 'PICKED_UP'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.delivery.status, 'PICKED_UP')
        self.assertEqual(self.order.status, 'READY_FOR_PICKUP')

    def test_partner_sees_waiting_pickups_after_finishing_active_delivery(self):
        waiting_delivery = self.create_waiting_delivery(
            restaurant_name='Waiting Dispatch Kitchen',
            latitude='12.971600',
            longitude='77.594600',
            email='waiting-dispatch@example.com',
        )
        claimed = claim_pending_delivery(self.delivery.id, self.driver)
        self.assertIsNotNone(claimed)
        self.driver.current_latitude = Decimal('12.971600')
        self.driver.current_longitude = Decimal('77.594600')
        self.driver.location_updated_at = timezone.now()
        self.driver.save(update_fields=[
            'current_latitude', 'current_longitude', 'location_updated_at',
        ])
        self.driver.refresh_from_db()
        self.assertFalse(self.driver.is_available)

        self.client.force_authenticate(self.driver_user)
        for next_status in ('PICKED_UP', 'ON_THE_WAY'):
            response = self.client.patch(
                f'/api/v1/delivery/partner/{self.delivery.id}/status/',
                {'status': next_status},
                format='json',
            )
            self.assertEqual(response.status_code, 200)

        self.delivery.refresh_from_db()
        delivered = self.client.patch(
            f'/api/v1/delivery/partner/{self.delivery.id}/status/',
            {
                'status': 'DELIVERED',
                'confirmation_code': self.delivery.confirmation_code,
            },
            format='json',
        )
        self.assertEqual(delivered.status_code, 200)
        self.driver.refresh_from_db()
        self.assertTrue(self.driver.is_available)

        available = self.client.get('/api/v1/delivery/available/')
        self.assertEqual(available.status_code, 200)
        self.assertIn(
            waiting_delivery.id,
            [delivery['id'] for delivery in available.data['results']],
        )

    def test_admin_can_assign_and_reassign_waiting_pickup(self):
        self.client.force_authenticate(self.admin)
        assigned = self.client.patch(
            f'/api/v1/operations/dispatch/{self.delivery.id}/assign/',
            {'partner_id': self.driver.id},
            format='json',
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.data['partner_username'], 'dispatch-driver')

        reassigned = self.client.patch(
            f'/api/v1/operations/dispatch/{self.delivery.id}/assign/',
            {'partner_id': self.other_driver.id},
            format='json',
        )
        self.assertEqual(reassigned.status_code, 200)
        self.driver.refresh_from_db()
        self.other_driver.refresh_from_db()
        self.assertTrue(self.driver.is_available)
        self.assertFalse(self.other_driver.is_available)
        self.assertEqual(reassigned.data['partner_username'], 'other-driver')

    def test_non_staff_cannot_use_dispatch_board(self):
        self.client.force_authenticate(self.driver_user)
        response = self.client.get('/api/v1/operations/dispatch/')
        self.assertEqual(response.status_code, 403)

    def test_partner_can_publish_location_and_see_pickup_distance(self):
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        self.client.force_authenticate(self.driver_user)
        location = self.client.patch(
            '/api/v1/delivery/availability/location/',
            {'latitude': 12.9716, 'longitude': 77.5946},
            format='json',
        )
        self.assertEqual(location.status_code, 200)
        available = self.client.get('/api/v1/delivery/available/')
        self.assertEqual(available.status_code, 200)
        self.assertEqual(available.data['results'][0]['pickup_distance_km'], 0.0)

    def test_available_deliveries_are_sorted_by_nearest_pickup(self):
        self.order.status = 'CONFIRMED'
        self.order.save(update_fields=['status'])
        far_delivery = self.create_waiting_delivery(
            restaurant_name='Far Dispatch Kitchen',
            latitude='12.980000',
            longitude='77.600000',
            email='far-dispatch@example.com',
        )
        near_delivery = self.create_waiting_delivery(
            restaurant_name='Near Dispatch Kitchen',
            latitude='12.971600',
            longitude='77.594600',
            email='near-dispatch@example.com',
        )
        self.driver.current_latitude = Decimal('12.971600')
        self.driver.current_longitude = Decimal('77.594600')
        self.driver.location_updated_at = timezone.now()
        self.driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))

        self.client.force_authenticate(self.driver_user)
        response = self.client.get('/api/v1/delivery/available/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]['id'], near_delivery.id)
        self.assertEqual(response.data['results'][1]['id'], far_delivery.id)
        self.assertEqual(response.data['results'][0]['pickup_distance_km'], 0.0)

    def test_available_delivery_distance_falls_back_when_points_are_null(self):
        self.order.status = 'CONFIRMED'
        self.order.save(update_fields=['status'])
        delivery = self.create_waiting_delivery(
            restaurant_name='Fallback Dispatch Kitchen',
            latitude='12.971600',
            longitude='77.594600',
            email='fallback-dispatch@example.com',
        )
        restaurant = delivery.order.items.first().food.restaurant
        restaurant.pickup_point = None
        restaurant.save(update_fields=['pickup_point'])
        self.driver.current_latitude = Decimal('12.971600')
        self.driver.current_longitude = Decimal('77.594600')
        self.driver.location_updated_at = timezone.now()
        self.driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))
        self.driver.current_point = None
        self.driver.save(update_fields=['current_point'])

        self.client.force_authenticate(self.driver_user)
        response = self.client.get('/api/v1/delivery/available/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], delivery.id)
        self.assertEqual(response.data['results'][0]['pickup_distance_km'], 0.0)

    def test_unverified_partner_does_not_receive_delivery_offer(self):
        self.other_driver.is_verified = False
        self.other_driver.save(update_fields=['is_verified'])
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for driver in (self.driver, self.other_driver):
            driver.current_latitude = Decimal('12.971600')
            driver.current_longitude = Decimal('77.594600')
            driver.location_updated_at = now
            driver.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertTrue(Notification.objects.filter(
            user=self.driver_user,
            title=title,
        ).exists())
        self.assertFalse(Notification.objects.filter(
            user=self.other_driver_user,
            title=title,
        ).exists())

    def test_offer_waves_start_nearby_and_expand_to_fallback(self):
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        self.driver.current_latitude = Decimal('12.971600')
        self.driver.current_longitude = Decimal('77.594600')
        self.driver.location_updated_at = now
        self.driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))
        self.other_driver.current_latitude = Decimal('13.500000')
        self.other_driver.current_longitude = Decimal('77.594600')
        self.other_driver.location_updated_at = now
        self.other_driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'
        self.assertTrue(Notification.objects.filter(
            user=self.driver_user, title=title
        ).exists())
        self.assertFalse(Notification.objects.filter(
            user=self.other_driver_user, title=title
        ).exists())

        Delivery.objects.filter(id=self.delivery.id).update(
            delivery_date=now - timedelta(minutes=11)
        )
        self.delivery.refresh_from_db()
        notify_delivery_candidates(self.delivery)
        self.assertTrue(Notification.objects.filter(
            user=self.other_driver_user, title=title
        ).exists())

    def test_merchant_owned_active_verified_rider_is_preferred_first(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertEqual(
            list(get_preferred_merchant_riders(self.order).values_list('id', flat=True)),
            [self.driver.id],
        )
        self.assertTrue(Notification.objects.filter(
            user=self.driver_user,
            title=title,
        ).exists())
        self.assertFalse(Notification.objects.filter(
            user=self.other_driver_user,
            title=title,
        ).exists())

    def test_branch_rider_is_preferred_before_merchant_wide_rider(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            home_restaurant=self.restaurant,
            status=MerchantRider.STATUS_ACTIVE,
        )
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.other_driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertEqual(
            list(get_branch_preferred_riders(self.order).values_list('id', flat=True)),
            [self.driver.id],
        )
        self.assertEqual(
            set(get_merchant_preferred_riders(self.order).values_list('id', flat=True)),
            {self.driver.id, self.other_driver.id},
        )
        self.assertEqual(
            list(get_preferred_merchant_riders(self.order).values_list('id', flat=True)),
            [self.driver.id],
        )
        self.assertTrue(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertFalse(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_dispatch_uses_explicit_pickup_branch_before_order_item_restaurant(self):
        branch_b = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Dispatch Branch B',
            rest_email='dispatch-branch-b@example.com',
            rest_contact='1234567899',
            rest_address='Branch B Road',
            rest_city='Test City',
            pickup_latitude=Decimal('20.000000'),
            pickup_longitude=Decimal('85.000000'),
            is_active=True,
        )
        self.order.pickup_branch = branch_b
        self.order.save(update_fields=['pickup_branch'])
        self.restaurant.pickup_latitude = Decimal('21.000000')
        self.restaurant.pickup_longitude = Decimal('86.000000')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        self.driver.current_latitude = Decimal('21.000000')
        self.driver.current_longitude = Decimal('86.000000')
        self.driver.location_updated_at = timezone.now()
        self.driver.save(update_fields=[
            'current_latitude', 'current_longitude', 'location_updated_at',
        ])
        self.other_driver.current_latitude = Decimal('20.000100')
        self.other_driver.current_longitude = Decimal('85.000100')
        self.other_driver.location_updated_at = timezone.now()
        self.other_driver.save(update_fields=[
            'current_latitude', 'current_longitude', 'location_updated_at',
        ])
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_ACTIVE,
            home_restaurant=self.restaurant,
        )
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.other_driver,
            status=MerchantRider.STATUS_ACTIVE,
            home_restaurant=branch_b,
        )

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertEqual(get_order_pickup_branch(self.order), branch_b)
        self.assertEqual(
            list(get_branch_preferred_riders(self.order).values_list('id', flat=True)),
            [self.other_driver.id],
        )
        self.assertFalse(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertTrue(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_merchant_wide_rider_is_preferred_when_no_branch_rider_eligible(self):
        self.driver.is_available = False
        self.driver.save(update_fields=['is_available'])
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            home_restaurant=self.restaurant,
            status=MerchantRider.STATUS_ACTIVE,
        )
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.other_driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        self.other_driver.current_latitude = Decimal('12.971600')
        self.other_driver.current_longitude = Decimal('77.594600')
        self.other_driver.location_updated_at = now
        self.other_driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertFalse(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertTrue(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_branch_rider_from_another_merchant_is_not_preferred(self):
        MerchantRider.objects.create(
            merchant=self.other_merchant,
            partner=self.other_driver,
            home_restaurant=self.restaurant,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertFalse(get_branch_preferred_riders(self.order).exists())
        self.assertFalse(get_preferred_merchant_riders(self.order).exists())
        self.assertTrue(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertTrue(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_inactive_unverified_or_unavailable_branch_rider_is_not_preferred(self):
        branch_riders = []
        for index, flags in enumerate((
            {'status': MerchantRider.STATUS_INACTIVE, 'verified': True, 'available': True},
            {'status': MerchantRider.STATUS_ACTIVE, 'verified': False, 'available': True},
            {'status': MerchantRider.STATUS_ACTIVE, 'verified': True, 'available': False},
        )):
            user = User.objects.create_user(username=f'branch-ineligible-{index}')
            partner = DeliveryPartner.objects.create(
                user=user,
                partner_name=f'Branch Ineligible {index}',
                partner_phone=f'900000010{index}',
                transport_details='Bike',
                is_verified=flags['verified'],
                is_available=flags['available'],
            )
            MerchantRider.objects.create(
                merchant=self.merchant,
                partner=partner,
                home_restaurant=self.restaurant,
                status=flags['status'],
            )
            branch_riders.append((user, partner))
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        self.driver.current_latitude = Decimal('12.971600')
        self.driver.current_longitude = Decimal('77.594600')
        self.driver.location_updated_at = now
        self.driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))
        for _user, partner in branch_riders:
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertFalse(get_branch_preferred_riders(self.order).exists())
        self.assertTrue(Notification.objects.filter(user=branch_riders[0][0], title=title).exists())
        for user, _partner in branch_riders[1:]:
            self.assertFalse(Notification.objects.filter(user=user, title=title).exists())
        self.assertTrue(Notification.objects.filter(user=self.driver_user, title=title).exists())

    def test_inactive_merchant_rider_is_not_preferred_and_global_fallback_works(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_INACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertFalse(get_preferred_merchant_riders(self.order).exists())
        self.assertTrue(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertTrue(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_unverified_merchant_rider_is_not_preferred(self):
        self.driver.is_verified = False
        self.driver.save(update_fields=['is_verified'])
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        self.other_driver.current_latitude = Decimal('12.971600')
        self.other_driver.current_longitude = Decimal('77.594600')
        self.other_driver.location_updated_at = now
        self.other_driver.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertFalse(get_preferred_merchant_riders(self.order).exists())
        self.assertFalse(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertTrue(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_other_merchants_rider_is_not_preferred_for_order(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        MerchantRider.objects.create(
            merchant=self.other_merchant,
            partner=self.other_driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'

        self.assertEqual(
            set(get_preferred_merchant_riders(self.order).values_list('id', flat=True)),
            {self.driver.id},
        )
        self.assertTrue(Notification.objects.filter(user=self.driver_user, title=title).exists())
        self.assertFalse(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_global_partners_become_eligible_after_preferred_wave(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))

        auto_assign_delivery(self.order)
        title = f'Pickup available for order #{self.order.id}'
        self.assertFalse(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

        Delivery.objects.filter(id=self.delivery.id).update(
            delivery_date=now - timedelta(minutes=3)
        )
        self.delivery.refresh_from_db()
        notify_delivery_candidates(self.delivery)

        self.assertTrue(Notification.objects.filter(user=self.other_driver_user, title=title).exists())

    def test_global_partner_claim_flow_still_works_after_preferred_wave(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.driver,
            status=MerchantRider.STATUS_ACTIVE,
        )
        self.restaurant.pickup_latitude = Decimal('12.971600')
        self.restaurant.pickup_longitude = Decimal('77.594600')
        self.restaurant.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        now = timezone.now()
        for partner in (self.driver, self.other_driver):
            partner.current_latitude = Decimal('12.971600')
            partner.current_longitude = Decimal('77.594600')
            partner.location_updated_at = now
            partner.save(update_fields=(
                'current_latitude', 'current_longitude', 'location_updated_at'
            ))
        Delivery.objects.filter(id=self.delivery.id).update(
            delivery_date=now - timedelta(minutes=3)
        )
        self.delivery.refresh_from_db()

        self.client.force_authenticate(self.other_driver_user)
        response = self.client.post(
            f'/api/v1/delivery/available/{self.delivery.id}/claim/'
        )

        self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_partner, self.other_driver)

    def test_delivery_fee_becomes_available_then_paid_once(self):
        claim_pending_delivery(self.delivery.id, self.driver)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.partner_fee, Decimal('40.00'))
        self.assertEqual(self.delivery.payout_status, 'PENDING')

        self.client.force_authenticate(self.driver_user)
        confirmation_code = self.delivery.confirmation_code
        for next_status in ('PICKED_UP', 'ON_THE_WAY', 'DELIVERED'):
            response = self.client.patch(
                f'/api/v1/delivery/partner/{self.delivery.id}/status/',
                {
                    'status': next_status,
                    **(
                        {'confirmation_code': confirmation_code}
                        if next_status == 'DELIVERED' else {}
                    ),
                },
                format='json',
            )
            self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.delivery.payout_status, 'AVAILABLE')
        self.assertEqual(self.order.merchant_payout_status, 'AVAILABLE')
        partner_available = PartnerPayoutAudit.objects.get(
            delivery=self.delivery,
            status=PartnerPayoutAudit.STATUS_AVAILABLE,
        )
        merchant_available = MerchantPayoutAudit.objects.get(
            order=self.order,
            status=MerchantPayoutAudit.STATUS_AVAILABLE,
        )
        self.assertEqual(partner_available.amount, Decimal('40.00'))
        self.assertEqual(merchant_available.amount, self.order.merchant_payout)
        self.assertEqual(partner_available.currency, 'INR')
        self.assertEqual(merchant_available.currency, 'INR')
        self.assertEqual(
            partner_available.ledger_transaction.transaction_type,
            LedgerTransaction.TYPE_PARTNER_DELIVERY_FEE,
        )
        self.assertEqual(
            merchant_available.ledger_transaction.transaction_type,
            LedgerTransaction.TYPE_MERCHANT_PAYOUT,
        )
        earnings = self.client.get('/api/v1/delivery/partner/earnings/')
        self.assertEqual(earnings.data['available_earnings'], Decimal('40.00'))

        self.client.force_authenticate(self.admin)
        paid = self.client.post(
            f'/api/v1/operations/payouts/partners/{self.delivery.id}/pay/'
        )
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(paid.data['payout_status'], 'PAID')
        partner_paid = PartnerPayoutAudit.objects.get(
            delivery=self.delivery,
            status=PartnerPayoutAudit.STATUS_PAID,
        )
        self.assertEqual(partner_paid.marked_by, self.admin)
        self.assertEqual(partner_paid.amount, Decimal('40.00'))
        self.assertEqual(
            partner_paid.ledger_transaction.transaction_type,
            LedgerTransaction.TYPE_PAYOUT_SETTLEMENT,
        )
        debits = partner_paid.ledger_transaction.entries.filter(
            direction=LedgerEntry.DIRECTION_DEBIT
        ).aggregate(total=Sum('amount'))['total']
        credits = partner_paid.ledger_transaction.entries.filter(
            direction=LedgerEntry.DIRECTION_CREDIT
        ).aggregate(total=Sum('amount'))['total']
        self.assertEqual(debits, credits)
        paid_again = self.client.post(
            f'/api/v1/operations/payouts/partners/{self.delivery.id}/pay/'
        )
        self.assertEqual(paid_again.status_code, 400)
        self.assertEqual(
            PartnerPayoutAudit.objects.filter(delivery=self.delivery).count(),
            2,
        )
        self.assertEqual(
            LedgerTransaction.objects.filter(delivery=self.delivery).count(),
            2,
        )
        self.assertTrue(Notification.objects.filter(
            user=self.driver_user,
            title=f'Payout sent for order #{self.order.id}',
        ).exists())

    def test_delivery_requires_customer_handoff_code(self):
        claim_pending_delivery(self.delivery.id, self.driver)
        self.delivery.refresh_from_db()
        confirmation_code = self.delivery.confirmation_code
        wrong_code = '999999' if confirmation_code != '999999' else '000000'
        Delivery.objects.filter(id=self.delivery.id).update(status='ON_THE_WAY')
        self.client.force_authenticate(self.driver_user)

        partner_list = self.client.get('/api/v1/delivery/partner/')
        self.assertNotIn('confirmation_code', partner_list.data['results'][0])
        wrong = self.client.patch(
            f'/api/v1/delivery/partner/{self.delivery.id}/status/',
            {'status': 'DELIVERED', 'confirmation_code': wrong_code},
            format='json',
        )
        self.assertEqual(wrong.status_code, 400)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, 'ON_THE_WAY')
        self.assertIsNone(self.delivery.confirmation_verified_at)

        correct = self.client.patch(
            f'/api/v1/delivery/partner/{self.delivery.id}/status/',
            {'status': 'DELIVERED', 'confirmation_code': confirmation_code},
            format='json',
        )
        self.assertEqual(correct.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, 'DELIVERED')
        self.assertEqual(self.delivery.confirmation_code, '')
        self.assertIsNotNone(self.delivery.confirmation_verified_at)

    def test_customer_can_see_code_but_other_customer_cannot_access_order(self):
        claim_pending_delivery(self.delivery.id, self.driver)
        self.delivery.refresh_from_db()
        self.client.force_authenticate(self.customer)

        response = self.client.get(f'/api/v1/orders/{self.order.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['delivery']['confirmation_code'],
            self.delivery.confirmation_code,
        )
        stranger = User.objects.create_user(username='delivery-stranger')
        self.client.force_authenticate(stranger)
        self.assertEqual(
            self.client.get(f'/api/v1/orders/{self.order.id}/').status_code,
            404,
        )
