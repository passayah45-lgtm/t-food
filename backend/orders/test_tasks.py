from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification
from orders.models import Order
from orders.tasks import expire_unpaid_orders_task
from payments.models import Payment


class ExpireUnpaidOrdersTaskTests(TestCase):
    def test_task_expires_order_once(self):
        customer = User.objects.create_user(username='task-expiry-customer')
        order = Order.objects.create(
            customer=customer,
            status='PLACED',
            total_amount=Decimal('100.00'),
            payment_expires_at=timezone.now() - timedelta(minutes=1),
        )
        payment = Payment.objects.create(
            order=order,
            method='CARD',
            status='PENDING',
            provider='RAZORPAY',
        )

        first_result = expire_unpaid_orders_task.apply(kwargs={'batch_size': 100}).get()
        second_result = expire_unpaid_orders_task.apply(kwargs={'batch_size': 100}).get()

        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(first_result, 1)
        self.assertEqual(second_result, 0)
        self.assertEqual(order.status, 'EXPIRED')
        self.assertEqual(payment.status, 'CANCELLED')
        self.assertEqual(
            Notification.objects.filter(
                user=customer,
                order=order,
                kind='PAYMENT',
            ).count(),
            1,
        )

