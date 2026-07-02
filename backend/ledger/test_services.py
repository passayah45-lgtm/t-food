from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from delivery.models import Delivery, DeliveryPartner
from orders.models import Order, OrderItem, SupportTicket
from payments.models import Payment
from restaurants.models import (
    FoodItem,
    MerchantFulfillmentRequest,
    MerchantNetworkRelationship,
    MerchantProfile,
    Restaurant,
)

from .models import LedgerTransaction
from .services import (
    record_cod_capture,
    record_fulfillment_preview,
    record_merchant_payout_settled,
    record_online_capture,
    record_order_financials,
    record_partner_payout_settled,
    record_refund,
)


class LedgerWriterServiceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='ledger-customer')
        self.merchant_user = User.objects.create_user(username='ledger-merchant')
        self.fulfillment_user = User.objects.create_user(username='ledger-fulfillment')
        self.partner_user = User.objects.create_user(username='ledger-partner')
        self.operator = User.objects.create_user(username='ledger-operator', is_staff=True)
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Ledger Kitchen',
            is_verified=True,
        )
        self.fulfilling_merchant = MerchantProfile.objects.create(
            user=self.fulfillment_user,
            business_name='Ledger Helper Kitchen',
            is_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Ledger Kitchen',
            rest_email='ledger@example.com',
            rest_contact='9000000001',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Ledger Meal',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            subtotal_amount=Decimal('100.00'),
            delivery_fee=Decimal('20.00'),
            platform_fee=Decimal('10.00'),
            merchant_payout=Decimal('90.00'),
            total_amount=Decimal('120.00'),
            merchant_payout_status='AVAILABLE',
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.food,
            quantity=1,
            price=Decimal('100.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            method='COD',
            status='SUCCESS',
            provider='',
            transaction_id='COD-LEDGER-1',
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Ledger Partner',
            partner_phone='9000000002',
            is_verified=True,
        )
        self.delivery = Delivery.objects.create(
            order=self.order,
            delivery_partner=self.partner,
            status='DELIVERED',
            partner_fee=Decimal('20.00'),
            payout_status='AVAILABLE',
        )
        self.relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.fulfilling_merchant,
            requested_by=self.merchant_user,
            approved_by=self.fulfillment_user,
            status=MerchantNetworkRelationship.STATUS_ACTIVE,
        )
        self.fulfillment_request = MerchantFulfillmentRequest.objects.create(
            order=self.order,
            requesting_merchant=self.merchant,
            fulfilling_merchant=self.fulfilling_merchant,
            relationship=self.relationship,
            requested_by=self.merchant_user,
            status=MerchantFulfillmentRequest.STATUS_ACCEPTED,
            internal_status=MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED,
            settlement_preview={
                'original_merchant_payout': '90.00',
                'suggested_fulfilling_merchant_share': '63.00',
                'suggested_requesting_merchant_share': '27.00',
                'is_preview_only': True,
            },
        )

    def assert_balanced(self, transaction):
        self.assertEqual(transaction.debit_total, transaction.credit_total)
        debits = sum(
            entry.amount for entry in transaction.entries.filter(direction='DEBIT')
        )
        credits = sum(
            entry.amount for entry in transaction.entries.filter(direction='CREDIT')
        )
        self.assertEqual(debits, credits)
        self.assertEqual(transaction.amount, debits)

    def assert_idempotent(self, writer):
        first = writer()
        second = writer()
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            LedgerTransaction.objects.filter(idempotency_key=first.idempotency_key).count(),
            1,
        )
        return first

    def test_record_order_financials_is_balanced_idempotent_and_does_not_mutate_order(self):
        original_status = self.order.status
        original_payout_status = self.order.merchant_payout_status

        transaction = self.assert_idempotent(lambda: record_order_financials(self.order))

        self.assert_balanced(transaction)
        self.assertEqual(transaction.idempotency_key, f'order-financials:{self.order.id}')
        self.assertEqual(transaction.provider_code, 'ORDER')
        self.assertEqual(transaction.currency, self.order.market.default_currency.code)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, original_status)
        self.assertEqual(self.order.merchant_payout_status, original_payout_status)

    def test_record_cod_capture_is_balanced_idempotent_and_does_not_mutate_payment(self):
        original_status = self.payment.status

        transaction = self.assert_idempotent(lambda: record_cod_capture(self.payment))

        self.assert_balanced(transaction)
        self.assertEqual(transaction.provider_code, 'COD')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, original_status)

    def test_record_online_capture_snapshots_provider_code_without_mutating_payment(self):
        self.payment.method = 'CARD'
        self.payment.provider = 'RAZORPAY'
        self.payment.save(update_fields=['method', 'provider'])
        original_status = self.payment.status

        transaction = self.assert_idempotent(
            lambda: record_online_capture(self.payment, 'razorpay')
        )

        self.assert_balanced(transaction)
        self.assertEqual(transaction.provider_code, 'RAZORPAY')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, original_status)

    def test_record_refund_is_balanced_idempotent_and_does_not_mutate_payment(self):
        ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category='QUALITY',
            description='Refund requested for ledger test.',
            refund_status='REQUESTED',
        )
        original_payment_status = self.payment.status
        original_payout_status = self.order.merchant_payout_status

        transaction = self.assert_idempotent(
            lambda: record_refund(
                self.payment,
                Decimal('120.00'),
                'Support approved refund.',
                actor=self.operator,
                support_ticket=ticket,
            )
        )

        self.assert_balanced(transaction)
        self.assertEqual(transaction.transaction_type, LedgerTransaction.TYPE_REFUND)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, original_payment_status)
        self.assertEqual(self.order.merchant_payout_status, original_payout_status)

    def test_record_merchant_payout_settled_is_balanced_idempotent_without_status_change(self):
        original_status = self.order.merchant_payout_status

        transaction = self.assert_idempotent(
            lambda: record_merchant_payout_settled(self.order, actor=self.operator)
        )

        self.assert_balanced(transaction)
        self.assertEqual(transaction.provider_code, 'PAYOUT')
        self.order.refresh_from_db()
        self.assertEqual(self.order.merchant_payout_status, original_status)

    def test_record_partner_payout_settled_is_balanced_idempotent_without_status_change(self):
        original_status = self.delivery.payout_status

        transaction = self.assert_idempotent(
            lambda: record_partner_payout_settled(self.delivery, actor=self.operator)
        )

        self.assert_balanced(transaction)
        self.assertEqual(transaction.provider_code, 'PAYOUT')
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.payout_status, original_status)

    def test_record_fulfillment_preview_is_preview_only_and_does_not_mutate_request(self):
        original_status = self.fulfillment_request.status
        original_internal_status = self.fulfillment_request.internal_status
        original_preview = dict(self.fulfillment_request.settlement_preview)

        transaction = self.assert_idempotent(
            lambda: record_fulfillment_preview(self.fulfillment_request)
        )

        self.assert_balanced(transaction)
        self.assertEqual(transaction.provider_code, 'FULFILLMENT_PREVIEW')
        self.assertTrue(transaction.metadata['preview_only'])
        self.fulfillment_request.refresh_from_db()
        self.assertEqual(self.fulfillment_request.status, original_status)
        self.assertEqual(
            self.fulfillment_request.internal_status,
            original_internal_status,
        )
        self.assertEqual(self.fulfillment_request.settlement_preview, original_preview)

    def test_missing_market_is_rejected_safely(self):
        Order.objects.filter(id=self.order.id).update(market=None)
        self.order.refresh_from_db()

        with self.assertRaises(ValidationError):
            record_order_financials(self.order)
