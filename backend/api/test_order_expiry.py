from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from notifications.models import Notification
from orders.models import Order
from orders.services import expire_unpaid_orders
from payments.models import Payment


class OrderExpiryTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='expiry-customer')

    def create_order(self, status='PLACED', minutes=-1):
        return Order.objects.create(
            customer=self.customer,
            status=status,
            total_amount=Decimal('100.00'),
            payment_expires_at=timezone.now() + timedelta(minutes=minutes),
        )

    def test_past_due_unpaid_order_expires(self):
        order = self.create_order()
        payment = Payment.objects.create(
            order=order, method='CARD', status='PENDING', provider='RAZORPAY'
        )

        expired = expire_unpaid_orders()

        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(expired, 1)
        self.assertEqual(order.status, 'EXPIRED')
        self.assertEqual(order.merchant_payout_status, 'CANCELLED')
        self.assertEqual(payment.status, 'CANCELLED')
        self.assertTrue(Notification.objects.filter(user=self.customer, order=order).exists())

    def test_future_unpaid_order_remains_open(self):
        order = self.create_order(minutes=10)

        expired = expire_unpaid_orders()

        order.refresh_from_db()
        self.assertEqual(expired, 0)
        self.assertEqual(order.status, 'PLACED')

    def test_confirmed_order_never_expires(self):
        order = self.create_order(status='CONFIRMED')
        Payment.objects.create(order=order, method='COD', status='PENDING')

        expired = expire_unpaid_orders()

        order.refresh_from_db()
        self.assertEqual(expired, 0)
        self.assertEqual(order.status, 'CONFIRMED')

    def test_successful_payment_is_not_cancelled(self):
        order = self.create_order()
        payment = Payment.objects.create(order=order, method='CARD', status='SUCCESS')

        expired = expire_unpaid_orders()

        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(expired, 0)
        self.assertEqual(order.status, 'PLACED')
        self.assertEqual(payment.status, 'SUCCESS')
        self.assertIsNone(order.payment_expires_at)
