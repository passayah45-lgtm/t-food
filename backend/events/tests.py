from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase

from fooddelivery.correlation import reset_correlation_id, set_correlation_id
from orders.models import Order

from .models import InboxEvent, OutboxEvent
from .services import publish_event, record_inbox_event


class EventFoundationTests(TestCase):
    def test_publish_event_creates_pending_outbox_event_with_correlation_id(self):
        token = set_correlation_id('test-correlation-id')
        try:
            event = publish_event(
                event_name='test.event',
                aggregate_type='test',
                aggregate_id='1',
                payload={'ok': True},
            )
        finally:
            reset_correlation_id(token)

        self.assertEqual(event.status, OutboxEvent.STATUS_PENDING)
        self.assertEqual(event.headers['correlation_id'], 'test-correlation-id')

    def test_inbox_event_is_idempotent_per_consumer(self):
        event_id = uuid4()
        first, created_first = record_inbox_event(
            event_id=event_id,
            consumer='test-consumer',
            event_name='test.event',
            payload={'value': 1},
        )
        second, created_second = record_inbox_event(
            event_id=event_id,
            consumer='test-consumer',
            event_name='test.event',
            payload={'value': 1},
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(InboxEvent.objects.count(), 1)

    def test_order_created_and_status_changed_publish_outbox_events(self):
        user = User.objects.create_user(username='event-customer')
        order = Order.objects.create(customer=user, total_amount='125.00')

        created_event = OutboxEvent.objects.get(event_name='order.created')
        self.assertEqual(created_event.aggregate_id, str(order.id))
        self.assertEqual(created_event.payload['status'], 'PLACED')

        order.status = 'CONFIRMED'
        order.save(update_fields=['status', 'updated_at'])

        changed_event = OutboxEvent.objects.get(event_name='order.status_changed')
        self.assertEqual(changed_event.payload['previous_status'], 'PLACED')
        self.assertEqual(changed_event.payload['status'], 'CONFIRMED')

    def test_relay_outbox_events_marks_pending_events_published(self):
        publish_event(
            event_name='test.relay',
            aggregate_type='test',
            aggregate_id='1',
            payload={'ok': True},
        )

        call_command('relay_outbox_events', limit=10)

        event = OutboxEvent.objects.get(event_name='test.relay')
        self.assertEqual(event.status, OutboxEvent.STATUS_PUBLISHED)
        self.assertIsNotNone(event.published_at)


class CorrelationMiddlewareTests(TestCase):
    def test_correlation_id_header_is_echoed(self):
        response = Client().get(
            '/api/v1/health/',
            HTTP_X_CORRELATION_ID='request-123',
        )

        self.assertEqual(response['X-Correlation-ID'], 'request-123')

