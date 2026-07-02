from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from rest_framework.test import APITestCase

from ledger.models import LedgerEntry, LedgerTransaction
from notifications.models import Notification
from orders.models import Order, SupportTicket
from payments.models import Payment, RefundAudit
from restaurants.models import (
    MerchantFulfillmentRequest,
    MerchantNetworkRelationship,
    MerchantProfile,
)


class SupportApiTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='support-customer', password='test-password'
        )
        self.other_customer = User.objects.create_user(
            username='other-customer', password='test-password'
        )
        self.admin = User.objects.create_user(
            username='support-admin', password='test-password', is_staff=True
        )
        self.merchant_user = User.objects.create_user(username='support-merchant-a')
        self.fulfillment_user = User.objects.create_user(username='support-merchant-b')
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Support Merchant A',
            is_verified=True,
        )
        self.fulfilling_merchant = MerchantProfile.objects.create(
            user=self.fulfillment_user,
            business_name='Support Merchant B',
            is_verified=True,
        )
        self.relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.fulfilling_merchant,
            requested_by=self.merchant_user,
            approved_by=self.fulfillment_user,
            status=MerchantNetworkRelationship.STATUS_ACTIVE,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            subtotal_amount=Decimal('500.00'),
            total_amount=Decimal('540.00'),
            platform_fee=Decimal('75.00'),
            merchant_payout=Decimal('425.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            method='CARD',
            status='SUCCESS',
            transaction_id='TEST-PAYMENT',
        )

    def create_fulfillment_request(self):
        return MerchantFulfillmentRequest.objects.create(
            order=self.order,
            requesting_merchant=self.merchant,
            fulfilling_merchant=self.fulfilling_merchant,
            relationship=self.relationship,
            requested_by=self.merchant_user,
            responded_by=self.fulfillment_user,
            status=MerchantFulfillmentRequest.STATUS_ACCEPTED,
            internal_status=MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
            operations_note='Merchant B is preparing replacement items.',
            settlement_preview={'is_preview_only': True},
        )

    def create_ticket(self, request_refund=True):
        self.client.force_authenticate(self.customer)
        return self.client.post('/api/v1/support/tickets/', {
            'order': self.order.id,
            'category': 'QUALITY',
            'description': 'The delivered meal was not in acceptable condition.',
            'request_refund': request_refund,
        }, format='json')

    def test_customer_can_create_and_list_ticket(self):
        created = self.create_ticket()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['refund_status'], 'REQUESTED')
        listed = self.client.get('/api/v1/support/tickets/')
        self.assertEqual(listed.data['count'], 1)

    def test_customer_cannot_create_duplicate_active_ticket(self):
        self.assertEqual(self.create_ticket().status_code, 201)
        duplicate = self.create_ticket()
        self.assertEqual(duplicate.status_code, 400)

    def test_customer_cannot_submit_ticket_for_another_order(self):
        self.client.force_authenticate(self.other_customer)
        response = self.client.post('/api/v1/support/tickets/', {
            'order': self.order.id,
            'category': 'OTHER',
            'description': 'This order does not belong to this customer.',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_non_staff_cannot_resolve_ticket(self):
        ticket_id = self.create_ticket().data['id']
        self.client.force_authenticate(self.other_customer)
        response = self.client.patch(
            f'/api/v1/operations/support/{ticket_id}/status/',
            {'status': 'RESOLVED', 'resolution': 'Resolved.'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RefundAudit.objects.exists())
        self.assertFalse(LedgerTransaction.objects.exists())

    def test_admin_refund_updates_payment_ticket_notification_and_revenue(self):
        ticket_id = self.create_ticket().data['id']
        self.client.force_authenticate(self.admin)
        before = self.client.get('/api/v1/operations/summary/')
        self.assertEqual(before.data['platform_revenue'], Decimal('75.00'))

        resolved = self.client.patch(
            f'/api/v1/operations/support/{ticket_id}/status/',
            {
                'status': 'RESOLVED',
                'resolution': 'A full refund was approved after review.',
                'issue_refund': True,
            },
            format='json',
        )
        self.assertEqual(resolved.status_code, 200)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        ticket = SupportTicket.objects.get(id=ticket_id)
        self.assertEqual(self.payment.status, 'REFUNDED')
        self.assertEqual(ticket.refund_status, 'APPROVED')
        self.assertEqual(ticket.refunded_amount, Decimal('540.00'))
        self.assertEqual(self.order.merchant_payout_status, 'CANCELLED')
        self.assertTrue(Notification.objects.filter(
            user=self.customer,
            title__contains=f'Support ticket #{ticket_id}',
        ).exists())

        after = self.client.get('/api/v1/operations/summary/')
        self.assertEqual(after.data['platform_revenue'], 0)

        audit = RefundAudit.objects.select_related(
            'ledger_transaction', 'initiated_by', 'order', 'payment'
        ).get(support_ticket=ticket)
        self.assertEqual(audit.order, self.order)
        self.assertEqual(audit.payment, self.payment)
        self.assertEqual(audit.amount, Decimal('540.00'))
        self.assertEqual(audit.currency, 'INR')
        self.assertEqual(audit.reason, 'A full refund was approved after review.')
        self.assertEqual(audit.initiated_by, self.admin)
        self.assertEqual(audit.provider_code, 'CARD')
        self.assertEqual(audit.status, RefundAudit.STATUS_SUCCEEDED)
        self.assertEqual(audit.idempotency_key, f'refund:{self.order.id}:{ticket.id}')
        self.assertIsNotNone(audit.ledger_transaction)
        self.assertEqual(
            audit.ledger_transaction.transaction_type,
            LedgerTransaction.TYPE_REFUND,
        )
        self.assertEqual(audit.ledger_transaction.currency, 'INR')
        debits = audit.ledger_transaction.entries.filter(
            direction=LedgerEntry.DIRECTION_DEBIT
        ).aggregate(total=Sum('amount'))['total']
        credits = audit.ledger_transaction.entries.filter(
            direction=LedgerEntry.DIRECTION_CREDIT
        ).aggregate(total=Sum('amount'))['total']
        self.assertEqual(debits, credits)

    def test_refund_retry_does_not_duplicate_audit_or_ledger(self):
        ticket_id = self.create_ticket().data['id']
        self.client.force_authenticate(self.admin)
        payload = {
            'status': 'RESOLVED',
            'resolution': 'A full refund was approved after review.',
            'issue_refund': True,
        }

        first = self.client.patch(
            f'/api/v1/operations/support/{ticket_id}/status/',
            payload,
            format='json',
        )
        second = self.client.patch(
            f'/api/v1/operations/support/{ticket_id}/status/',
            payload,
            format='json',
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(RefundAudit.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.filter(
            transaction_type=LedgerTransaction.TYPE_REFUND
        ).count(), 1)
        audit = RefundAudit.objects.get()
        self.assertEqual(audit.ledger_transaction_id, LedgerTransaction.objects.get().id)

    def test_operations_support_view_includes_internal_fulfillment_context(self):
        fulfillment_request = self.create_fulfillment_request()
        ticket_id = self.create_ticket().data['id']

        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/v1/operations/support/')

        self.assertEqual(response.status_code, 200)
        ticket = next(item for item in response.data if item['id'] == ticket_id)
        context = ticket['fulfillment_context']
        self.assertTrue(context['has_fulfillment_request'])
        self.assertEqual(context['fulfillment_request_id'], fulfillment_request.id)
        self.assertEqual(
            context['fulfilling_merchant']['business_name'],
            'Support Merchant B',
        )
        self.assertEqual(context['internal_status'], 'IN_PROGRESS')
        self.assertEqual(context['settlement_preview_status'], 'AVAILABLE')
        self.assertNotIn('settlement_preview', context)

    def test_customer_support_view_does_not_expose_fulfillment_context(self):
        self.create_fulfillment_request()
        self.create_ticket()

        self.client.force_authenticate(self.customer)
        response = self.client.get('/api/v1/support/tickets/')

        self.assertEqual(response.status_code, 200)
        ticket = response.data['results'][0]
        self.assertNotIn('fulfillment_context', ticket)
        self.assertNotIn('refund_audits', ticket)
        self.assertNotIn('ledger_transaction', str(ticket))
        self.assertNotIn('fulfilling_merchant', str(ticket))
        self.assertNotIn('Support Merchant B', str(ticket))

    def test_refund_does_not_mutate_fulfillment_request_or_preview(self):
        fulfillment_request = self.create_fulfillment_request()
        original_preview = dict(fulfillment_request.settlement_preview)
        original_status = fulfillment_request.status
        original_internal_status = fulfillment_request.internal_status
        ticket_id = self.create_ticket().data['id']

        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/v1/operations/support/{ticket_id}/status/',
            {
                'status': 'RESOLVED',
                'resolution': 'A full refund was approved after review.',
                'issue_refund': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        fulfillment_request.refresh_from_db()
        self.assertEqual(self.payment.status, 'REFUNDED')
        self.assertEqual(self.order.merchant_payout_status, 'CANCELLED')
        self.assertEqual(fulfillment_request.status, original_status)
        self.assertEqual(fulfillment_request.internal_status, original_internal_status)
        self.assertEqual(fulfillment_request.settlement_preview, original_preview)
