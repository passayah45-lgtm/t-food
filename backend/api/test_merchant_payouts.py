from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from rest_framework.test import APITestCase

from ledger.models import LedgerEntry, LedgerTransaction
from notifications.models import Notification
from orders.models import Order, OrderItem, SupportTicket
from payments.models import MerchantPayoutAudit, Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class MerchantPayoutApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='settlement-admin', is_staff=True)
        self.merchant = User.objects.create_user(username='settlement-merchant')
        MerchantProfile.objects.create(
            user=self.merchant,
            business_name='Settlement Kitchen',
            is_verified=True,
        )
        self.customer = User.objects.create_user(username='settlement-customer')
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Settlement Kitchen',
            rest_email='settlement@example.com',
            rest_contact='1234567890',
            rest_address='Settlement Road',
            rest_city='Test City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Settlement Meal',
            food_price=Decimal('200.00'),
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('220.00'),
            merchant_payout=Decimal('170.00'),
            merchant_payout_status='AVAILABLE',
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.food,
            quantity=1,
            price=Decimal('200.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            method='CARD',
            status='SUCCESS',
        )

    def test_admin_can_pay_merchant_settlement_once(self):
        self.client.force_authenticate(self.admin)
        payouts = self.client.get('/api/v1/operations/payouts/merchants/')
        self.assertEqual(payouts.status_code, 200)
        self.assertEqual(len(payouts.data), 1)

        paid = self.client.post(
            f'/api/v1/operations/payouts/merchants/{self.order.id}/pay/'
        )
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(paid.data['merchant_payout_status'], 'PAID')
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.merchant_paid_at)
        self.assertTrue(Notification.objects.filter(
            user=self.merchant,
            title=f'Merchant payout sent for order #{self.order.id}',
        ).exists())
        paid_audit = MerchantPayoutAudit.objects.get(
            order=self.order,
            status=MerchantPayoutAudit.STATUS_PAID,
        )
        self.assertEqual(paid_audit.amount, Decimal('170.00'))
        self.assertEqual(paid_audit.currency, 'INR')
        self.assertEqual(paid_audit.marked_by, self.admin)
        self.assertIsNotNone(paid_audit.paid_at)
        self.assertEqual(
            paid_audit.ledger_transaction.transaction_type,
            LedgerTransaction.TYPE_PAYOUT_SETTLEMENT,
        )
        debits = paid_audit.ledger_transaction.entries.filter(
            direction=LedgerEntry.DIRECTION_DEBIT
        ).aggregate(total=Sum('amount'))['total']
        credits = paid_audit.ledger_transaction.entries.filter(
            direction=LedgerEntry.DIRECTION_CREDIT
        ).aggregate(total=Sum('amount'))['total']
        self.assertEqual(debits, credits)

        paid_again = self.client.post(
            f'/api/v1/operations/payouts/merchants/{self.order.id}/pay/'
        )
        self.assertEqual(paid_again.status_code, 400)
        self.assertEqual(MerchantPayoutAudit.objects.filter(
            order=self.order,
            status=MerchantPayoutAudit.STATUS_PAID,
        ).count(), 1)
        self.assertEqual(LedgerTransaction.objects.filter(
            order=self.order,
            transaction_type=LedgerTransaction.TYPE_PAYOUT_SETTLEMENT,
        ).count(), 1)

    def test_paid_merchant_settlement_blocks_automatic_refund(self):
        self.order.merchant_payout_status = 'PAID'
        self.order.save(update_fields=['merchant_payout_status'])
        ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category='QUALITY',
            description='Refund requested after settlement.',
            refund_status='REQUESTED',
        )
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/v1/operations/support/{ticket.id}/status/',
            {
                'status': 'RESOLVED',
                'resolution': 'Refund approved after review.',
                'issue_refund': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'SUCCESS')

    def test_refund_cancels_unpaid_merchant_settlement(self):
        ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category='QUALITY',
            description='Refund requested before settlement.',
            refund_status='REQUESTED',
        )
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/v1/operations/support/{ticket.id}/status/',
            {
                'status': 'RESOLVED',
                'resolution': 'Full refund approved.',
                'issue_refund': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.merchant_payout_status, 'CANCELLED')
