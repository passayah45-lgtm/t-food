from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order, OrderStatusEvent


class OrderTimelineTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='timeline-customer')

    def test_creation_and_status_changes_are_recorded(self):
        order = Order.objects.create(
            customer=self.customer,
            total_amount=Decimal('100.00'),
        )
        order.status = 'CONFIRMED'
        order.save(update_fields=['status', 'updated_at'])
        order.status = 'PREPARING'
        order.save(update_fields=['status', 'updated_at'])

        events = list(order.status_events.values_list('status', 'source'))
        self.assertEqual(events, [
            ('PLACED', 'CHECKOUT'),
            ('CONFIRMED', 'PAYMENT'),
            ('PREPARING', 'MERCHANT'),
        ])

    def test_non_status_update_does_not_create_duplicate_event(self):
        order = Order.objects.create(
            customer=self.customer,
            total_amount=Decimal('100.00'),
        )

        order.loyalty_points_awarded = True
        order.save(update_fields=['loyalty_points_awarded', 'updated_at'])

        self.assertEqual(order.status_events.count(), 1)

    def test_customer_order_api_includes_timeline(self):
        order = Order.objects.create(
            customer=self.customer,
            total_amount=Decimal('100.00'),
        )
        order.status = 'CONFIRMED'
        order.save(update_fields=['status', 'updated_at'])
        self.client.force_authenticate(self.customer)

        response = self.client.get(f'/api/v1/orders/{order.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [event['status'] for event in response.data['timeline']],
            ['PLACED', 'CONFIRMED'],
        )
        self.assertEqual(response.data['timeline'][1]['source_display'], 'Payment')

    def test_events_are_deleted_with_order(self):
        order = Order.objects.create(customer=self.customer)
        event_id = order.status_events.get().id

        order.delete()

        self.assertFalse(OrderStatusEvent.objects.filter(id=event_id).exists())
