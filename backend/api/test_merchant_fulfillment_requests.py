from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from ledger.models import LedgerTransaction
from orders.models import Order, OrderItem, OrderStatusEvent
from payments.models import Payment
from delivery.models import Delivery
from restaurants.models import (
    FoodItem,
    MerchantFulfillmentRequest,
    MerchantFulfillmentRequestEvent,
    MerchantNetworkRelationship,
    MerchantProfile,
    Restaurant,
)
from restaurants.services import ensure_fulfillment_settlement_preview


class MerchantFulfillmentRequestApiTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='fulfillment-customer')
        self.merchant_user = User.objects.create_user(username='fulfillment-merchant-a')
        self.fulfillment_user = User.objects.create_user(username='fulfillment-merchant-b')
        self.stranger_user = User.objects.create_user(username='fulfillment-stranger')
        self.operator = User.objects.create_user(
            username='fulfillment-operator',
            is_staff=True,
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Requesting Merchant',
            is_verified=True,
        )
        self.fulfilling_merchant = MerchantProfile.objects.create(
            user=self.fulfillment_user,
            business_name='Fulfilling Merchant',
            is_verified=True,
        )
        self.stranger = MerchantProfile.objects.create(
            user=self.stranger_user,
            business_name='Unrelated Merchant',
            is_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Requesting Kitchen',
            rest_email='requesting-kitchen@example.com',
            rest_contact='9000000301',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            is_active=True,
        )
        self.other_restaurant = Restaurant.objects.create(
            owner=self.stranger_user,
            rest_name='Stranger Kitchen',
            rest_email='stranger-kitchen@example.com',
            rest_contact='9000000302',
            rest_address='Patia Road',
            rest_city='Bhubaneswar',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Network Meal',
            food_price=Decimal('120.00'),
            food_categ='Vegetarian',
        )
        self.other_food = FoodItem.objects.create(
            restaurant=self.other_restaurant,
            food_name='Other Meal',
            food_price=Decimal('140.00'),
            food_categ='Vegetarian',
        )
        self.order = self.create_order(self.food, status='CONFIRMED')
        self.other_order = self.create_order(self.other_food, status='CONFIRMED')
        self.relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.fulfilling_merchant,
            requested_by=self.merchant_user,
            approved_by=self.fulfillment_user,
            status=MerchantNetworkRelationship.STATUS_ACTIVE,
        )

    def create_order(self, food, status='CONFIRMED'):
        order = Order.objects.create(
            customer=self.customer,
            status=status,
            delivery_address='Customer Street',
            subtotal_amount=Decimal('120.00'),
            total_amount=Decimal('140.00'),
            merchant_payout=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=food,
            quantity=1,
            price=food.food_price,
        )
        return order

    def create_request(self):
        return MerchantFulfillmentRequest.objects.create(
            order=self.order,
            requesting_merchant=self.merchant,
            fulfilling_merchant=self.fulfilling_merchant,
            relationship=self.relationship,
            requested_by=self.merchant_user,
        )

    def assert_preview_ledger_transaction(self, fulfillment_request):
        transaction = LedgerTransaction.objects.get(
            fulfillment_request=fulfillment_request,
            transaction_type=LedgerTransaction.TYPE_FULFILLMENT_PREVIEW,
        )
        self.assertEqual(
            transaction.idempotency_key,
            f'fulfillment-preview:{fulfillment_request.id}',
        )
        self.assertEqual(transaction.provider_code, 'FULFILLMENT_PREVIEW')
        self.assertEqual(transaction.debit_total, transaction.credit_total)
        self.assertEqual(transaction.amount, transaction.debit_total)
        self.assertTrue(transaction.metadata['preview_only'])
        self.assertEqual(transaction.entries.count(), 3)
        return transaction

    def test_requesting_merchant_can_create_request(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': self.order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
                'notes': 'Can you help with this order?',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['order_id'], self.order.id)
        self.assertEqual(response.data['status'], MerchantFulfillmentRequest.STATUS_REQUESTED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertEqual(
            response.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_PENDING,
        )
        self.assertTrue(MerchantFulfillmentRequestEvent.objects.filter(
            fulfillment_request_id=response.data['id'],
            event_type=MerchantFulfillmentRequestEvent.EVENT_CREATED,
        ).exists())

    def test_non_owner_cannot_create_request_for_another_merchants_order(self):
        self.client.force_authenticate(self.stranger_user)

        response = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': self.order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('order_id', response.data)

    def test_request_requires_active_relationship(self):
        self.relationship.status = MerchantNetworkRelationship.STATUS_PAUSED
        self.relationship.save(update_fields=['status'])
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': self.order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active merchant collaboration', response.data['fulfilling_merchant_id'][0])

    def test_duplicate_active_request_is_prevented(self):
        self.create_request()
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': self.order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', response.data['detail'])

    def test_fulfilling_merchant_can_accept_and_reject(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.fulfillment_user)

        accepted = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )

        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(accepted.data['status'], MerchantFulfillmentRequest.STATUS_ACCEPTED)
        self.assertEqual(
            accepted.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertTrue(MerchantFulfillmentRequestEvent.objects.filter(
            fulfillment_request=fulfillment_request,
            event_type=MerchantFulfillmentRequestEvent.EVENT_STATUS_CHANGED,
            to_status=MerchantFulfillmentRequest.STATUS_ACCEPTED,
        ).exists())

        rejected_request = MerchantFulfillmentRequest.objects.create(
            order=self.create_order(self.food, status='CONFIRMED'),
            requesting_merchant=self.merchant,
            fulfilling_merchant=self.fulfilling_merchant,
            relationship=self.relationship,
            requested_by=self.merchant_user,
        )
        rejected = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{rejected_request.id}/',
            {'action': 'REJECT'},
            format='json',
        )

        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.data['status'], MerchantFulfillmentRequest.STATUS_REJECTED)
        self.assertEqual(
            rejected.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_REJECTED,
        )

    def test_requesting_merchant_can_cancel(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'CANCEL'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], MerchantFulfillmentRequest.STATUS_CANCELLED)
        self.assertEqual(
            response.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED,
        )

    def test_unrelated_merchant_cannot_view_or_respond(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.stranger_user)

        list_response = self.client.get('/api/v1/merchants/network/fulfillment-requests/')
        patch_response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 0)
        self.assertEqual(patch_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_completed_or_cancelled_orders_cannot_be_requested(self):
        delivered_order = self.create_order(self.food, status='DELIVERED')
        cancelled_order = self.create_order(self.food, status='CANCELLED')
        self.client.force_authenticate(self.merchant_user)

        delivered = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': delivered_order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
            },
            format='json',
        )
        cancelled = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': cancelled_order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
            },
            format='json',
        )

        self.assertEqual(delivered.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cancelled.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preparing_order_cannot_be_requested(self):
        preparing_order = self.create_order(self.food, status='PREPARING')
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            '/api/v1/merchants/network/fulfillment-requests/',
            {
                'order_id': preparing_order.id,
                'fulfilling_merchant_id': self.fulfilling_merchant.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_incoming_and_outgoing_requests(self):
        outgoing = self.create_request()
        incoming_relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.stranger,
            to_merchant=self.merchant,
            requested_by=self.stranger_user,
            status=MerchantNetworkRelationship.STATUS_ACTIVE,
        )
        incoming = MerchantFulfillmentRequest.objects.create(
            order=self.other_order,
            requesting_merchant=self.stranger,
            fulfilling_merchant=self.merchant,
            relationship=incoming_relationship,
            requested_by=self.stranger_user,
        )
        self.client.force_authenticate(self.merchant_user)

        response = self.client.get('/api/v1/merchants/network/fulfillment-requests/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['outgoing'][0]['id'], outgoing.id)
        self.assertEqual(response.data['incoming'][0]['id'], incoming.id)

    def test_operations_can_list_all_fulfillment_requests(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.operator)

        response = self.client.get('/api/v1/operations/fulfillment-requests/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], fulfillment_request.id)
        self.assertEqual(response.data[0]['order_id'], self.order.id)
        self.assertEqual(
            response.data[0]['requesting_merchant']['id'],
            self.merchant.id,
        )
        self.assertEqual(
            response.data[0]['fulfilling_merchant']['id'],
            self.fulfilling_merchant.id,
        )
        self.assertIn('requested_by', response.data[0])
        self.assertIn('responded_by', response.data[0])
        self.assertIn('internal_status', response.data[0])
        self.assertIn('settlement_preview', response.data[0])
        self.assertIn('events', response.data[0])

    def test_non_operations_cannot_list_all_fulfillment_requests(self):
        self.create_request()
        self.client.force_authenticate(self.merchant_user)

        response = self.client.get('/api/v1/operations/fulfillment-requests/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operations_fulfillment_request_status_filter(self):
        accepted_request = self.create_request()
        accepted_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        accepted_request.save(update_fields=['status'])
        MerchantFulfillmentRequest.objects.create(
            order=self.create_order(self.food, status='CONFIRMED'),
            requesting_merchant=self.merchant,
            fulfilling_merchant=self.fulfilling_merchant,
            relationship=self.relationship,
            requested_by=self.merchant_user,
        )
        self.client.force_authenticate(self.operator)

        response = self.client.get(
            '/api/v1/operations/fulfillment-requests/?status=ACCEPTED'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], MerchantFulfillmentRequest.STATUS_ACCEPTED)

    def test_merchant_a_remains_customer_facing_and_customer_api_hides_merchant_b(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.responded_by = self.fulfillment_user
        fulfillment_request.save(update_fields=[
            'status', 'internal_status', 'responded_by', 'updated_at',
        ])
        self.client.force_authenticate(self.customer)

        response = self.client.get(f'/api/v1/orders/{self.order.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_text = str(response.data)
        self.assertIn(str(self.restaurant.id), response_text)
        self.assertNotIn('Fulfilling Merchant', response_text)
        self.assertNotIn('fulfillment-merchant-b', response_text)
        self.assertNotIn('merchant_fulfillment_requests', response.data)
        self.assertNotIn('settlement_preview', response.data)
        self.assertNotIn('operations_note', response.data)

    def test_fulfilling_merchant_cannot_change_customer_facing_order_status(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.fulfillment_user)

        response = self.client.patch(
            f'/api/v1/merchants/orders/{self.order.id}/status/',
            {'status': 'PREPARING'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')

    def test_accepting_fulfillment_does_not_change_money_or_dispatch(self):
        payment = Payment.objects.create(
            order=self.order,
            method='COD',
            status='PENDING',
        )
        original_payout = self.order.merchant_payout
        original_payout_status = self.order.merchant_payout_status
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.fulfillment_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertEqual(self.order.merchant_payout, original_payout)
        self.assertEqual(
            self.order.merchant_payout_status,
            original_payout_status,
        )
        self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(Delivery.objects.filter(order=self.order).exists())
        preview = response.data['settlement_preview']
        self.assertTrue(preview['is_preview_only'])
        self.assertEqual(
            preview['preview_label'],
            'Preview Only — No Financial Settlement Has Been Applied',
        )
        self.assertEqual(preview['original_merchant_payout'], '100.00')
        self.assertEqual(preview['suggested_fulfilling_merchant_share'], '70.00')
        self.assertEqual(preview['suggested_requesting_merchant_share'], '30.00')
        fulfillment_request.refresh_from_db()
        self.assert_preview_ledger_transaction(fulfillment_request)

    def test_settlement_preview_is_stored_as_snapshot_on_acceptance(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.fulfillment_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fulfillment_request.refresh_from_db()
        snapshot = fulfillment_request.settlement_preview
        self.assertEqual(snapshot['original_merchant_payout'], '100.00')
        self.order.merchant_payout = Decimal('200.00')
        self.order.save(update_fields=['merchant_payout'])
        fulfillment_request.refresh_from_db()
        self.assertEqual(
            fulfillment_request.settlement_preview['original_merchant_payout'],
            '100.00',
        )
        self.assertTrue(MerchantFulfillmentRequestEvent.objects.filter(
            fulfillment_request=fulfillment_request,
            event_type=MerchantFulfillmentRequestEvent.EVENT_SETTLEMENT_PREVIEWED,
        ).exists())
        self.assert_preview_ledger_transaction(fulfillment_request)

    def test_settlement_preview_ledger_transaction_is_idempotent(self):
        fulfillment_request = self.create_request()
        first_preview = ensure_fulfillment_settlement_preview(
            fulfillment_request,
            actor=self.operator,
        )
        first_transaction = self.assert_preview_ledger_transaction(fulfillment_request)

        second_preview = ensure_fulfillment_settlement_preview(
            fulfillment_request,
            actor=self.operator,
        )

        self.assertEqual(second_preview, first_preview)
        self.assertEqual(
            LedgerTransaction.objects.filter(
                fulfillment_request=fulfillment_request,
                transaction_type=LedgerTransaction.TYPE_FULFILLMENT_PREVIEW,
            ).count(),
            1,
        )
        self.assertEqual(
            LedgerTransaction.objects.get(id=first_transaction.id).id,
            first_transaction.id,
        )

    def test_fulfilling_merchant_can_perform_internal_actions(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.responded_by = self.fulfillment_user
        fulfillment_request.save(update_fields=[
            'status', 'internal_status', 'responded_by', 'updated_at',
        ])
        self.client.force_authenticate(self.fulfillment_user)

        started = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'START_PREPARATION', 'note': 'Started cooking.'},
            format='json',
        )
        ready = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'READY_FOR_HANDOFF'},
            format='json',
        )
        resolved = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'RESOLVE'},
            format='json',
        )

        self.assertEqual(started.status_code, status.HTTP_200_OK)
        self.assertEqual(
            started.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
        )
        self.assertIsNotNone(started.data['preparation_started_at'])
        self.assertEqual(ready.status_code, status.HTTP_200_OK)
        self.assertEqual(
            ready.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF,
        )
        self.assertIsNotNone(ready.data['ready_for_handoff_at'])
        self.assertEqual(resolved.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resolved.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED,
        )
        self.assertIsNotNone(resolved.data['resolved_at'])
        self.assertEqual(
            MerchantFulfillmentRequestEvent.objects.filter(
                fulfillment_request=fulfillment_request,
                event_type=(
                    MerchantFulfillmentRequestEvent.EVENT_INTERNAL_STATUS_CHANGED
                ),
            ).count(),
            3,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')

    def test_fulfilling_merchant_can_report_unable_to_fulfill(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.fulfillment_user)

        started = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'START_PREPARATION'},
            format='json',
        )
        unable = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'UNABLE_TO_FULFILL', 'note': 'Ingredient unavailable.'},
            format='json',
        )

        self.assertEqual(started.status_code, status.HTTP_200_OK)
        self.assertEqual(unable.status_code, status.HTTP_200_OK)
        self.assertEqual(
            unable.data['internal_status'],
            MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL,
        )
        self.assertEqual(unable.data['blocked_reason'], 'Ingredient unavailable.')

    def test_invalid_internal_transition_is_rejected(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.fulfillment_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'READY_FOR_HANDOFF'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        fulfillment_request.refresh_from_db()
        self.assertEqual(
            fulfillment_request.internal_status,
            MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED,
        )

    def test_requesting_merchant_cannot_perform_internal_actions(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'START_PREPARATION'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fulfilling merchant', response.data['action'][0])

    def test_internal_actions_do_not_touch_customer_realtime_or_financial_state(self):
        payment = Payment.objects.create(
            order=self.order,
            method='COD',
            status='PENDING',
        )
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        original_order_status = self.order.status
        original_payout = self.order.merchant_payout
        original_payout_status = self.order.merchant_payout_status
        status_event_count = OrderStatusEvent.objects.filter(order=self.order).count()
        self.client.force_authenticate(self.fulfillment_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'START_PREPARATION'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.order.status, original_order_status)
        self.assertEqual(self.order.merchant_payout, original_payout)
        self.assertEqual(self.order.merchant_payout_status, original_payout_status)
        self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(Delivery.objects.filter(order=self.order).exists())
        self.assertEqual(
            OrderStatusEvent.objects.filter(order=self.order).count(),
            status_event_count,
        )

    def test_operations_can_cancel_fulfillment_request(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.operator)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'CANCEL', 'note': 'Merchant B cannot continue.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fulfillment_request.refresh_from_db()
        self.assertEqual(fulfillment_request.status, MerchantFulfillmentRequest.STATUS_CANCELLED)
        self.assertEqual(
            fulfillment_request.internal_status,
            MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED,
        )
        self.assertEqual(fulfillment_request.cancelled_by, self.operator)
        self.assertIsNotNone(fulfillment_request.cancelled_at)
        self.assertIn('Merchant B cannot continue.', fulfillment_request.operations_note)
        self.assertTrue(MerchantFulfillmentRequestEvent.objects.filter(
            fulfillment_request=fulfillment_request,
            actor=self.operator,
            from_status=MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
            to_status=MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED,
        ).exists())

    def test_operations_can_resolve_ready_fulfillment_request(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = (
            MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF
        )
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.operator)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'RESOLVE', 'note': 'Verified handoff complete.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fulfillment_request.refresh_from_db()
        self.assertEqual(
            fulfillment_request.internal_status,
            MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED,
        )
        self.assertEqual(fulfillment_request.resolved_by, self.operator)
        self.assertIsNotNone(fulfillment_request.resolved_at)
        self.assertIn('Verified handoff complete.', fulfillment_request.operations_note)
        self.assertTrue(fulfillment_request.settlement_preview['is_preview_only'])
        self.assertEqual(
            fulfillment_request.settlement_preview['preview_label'],
            'Preview Only — No Financial Settlement Has Been Applied',
        )

    def test_operations_resolve_validates_state_without_override(self):
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        self.client.force_authenticate(self.operator)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'RESOLVE'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        fulfillment_request.refresh_from_db()
        self.assertEqual(
            fulfillment_request.internal_status,
            MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
        )

    def test_operations_can_override_internal_status(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.operator)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {
                'action': 'OVERRIDE_STATUS',
                'internal_status': 'IN_PROGRESS',
                'note': 'Manual operations override.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fulfillment_request.refresh_from_db()
        self.assertEqual(
            fulfillment_request.internal_status,
            MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
        )
        self.assertIn('Manual operations override.', fulfillment_request.operations_note)
        self.assertTrue(MerchantFulfillmentRequestEvent.objects.filter(
            fulfillment_request=fulfillment_request,
            actor=self.operator,
            event_type=MerchantFulfillmentRequestEvent.EVENT_INTERNAL_STATUS_CHANGED,
            to_status=MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
        ).exists())

    def test_operations_can_add_note_without_changing_status(self):
        fulfillment_request = self.create_request()
        original_status = fulfillment_request.status
        original_internal_status = fulfillment_request.internal_status
        self.client.force_authenticate(self.operator)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ADD_NOTE', 'note': 'Called both merchants.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fulfillment_request.refresh_from_db()
        self.assertEqual(fulfillment_request.status, original_status)
        self.assertEqual(fulfillment_request.internal_status, original_internal_status)
        self.assertIn('Called both merchants.', fulfillment_request.operations_note)
        self.assertTrue(MerchantFulfillmentRequestEvent.objects.filter(
            fulfillment_request=fulfillment_request,
            actor=self.operator,
            event_type=MerchantFulfillmentRequestEvent.EVENT_NOTE_ADDED,
            from_status=original_internal_status,
            to_status=original_internal_status,
        ).exists())

    def test_non_operations_cannot_control_fulfillment_request(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ADD_NOTE', 'note': 'Not allowed.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operations_actions_do_not_change_customer_order_money_delivery_or_customer_api(self):
        payment = Payment.objects.create(
            order=self.order,
            method='COD',
            status='PENDING',
        )
        fulfillment_request = self.create_request()
        fulfillment_request.status = MerchantFulfillmentRequest.STATUS_ACCEPTED
        fulfillment_request.internal_status = (
            MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF
        )
        fulfillment_request.save(update_fields=['status', 'internal_status', 'updated_at'])
        original_order_status = self.order.status
        original_payout = self.order.merchant_payout
        original_payout_status = self.order.merchant_payout_status
        status_event_count = OrderStatusEvent.objects.filter(order=self.order).count()
        self.client.force_authenticate(self.operator)

        response = self.client.patch(
            f'/api/v1/operations/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'RESOLVE', 'note': 'Operations resolved internally.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.order.status, original_order_status)
        self.assertEqual(self.order.merchant_payout, original_payout)
        self.assertEqual(self.order.merchant_payout_status, original_payout_status)
        self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(Delivery.objects.filter(order=self.order).exists())
        self.assertEqual(
            OrderStatusEvent.objects.filter(order=self.order).count(),
            status_event_count,
        )

        self.client.force_authenticate(self.customer)
        customer_response = self.client.get(f'/api/v1/orders/{self.order.id}/')

        self.assertEqual(customer_response.status_code, status.HTTP_200_OK)
        response_text = str(customer_response.data)
        self.assertIn(str(self.restaurant.id), response_text)
        self.assertNotIn('Fulfilling Merchant', response_text)
        self.assertNotIn('fulfillment-merchant-b', response_text)
        self.assertNotIn('merchant_fulfillment_requests', customer_response.data)
        self.assertNotIn('settlement_preview', customer_response.data)
        self.assertNotIn('operations_note', customer_response.data)

    def test_settlement_preview_includes_delivery_fee_without_mutating_partner_fee(self):
        delivery = Delivery.objects.create(
            order=self.order,
            partner_fee=Decimal('25.00'),
        )
        fulfillment_request = self.create_request()
        payment = Payment.objects.create(
            order=self.order,
            method='COD',
            status='PENDING',
        )
        original_order_payout = self.order.merchant_payout
        original_payout_status = self.order.merchant_payout_status
        original_partner_fee = delivery.partner_fee

        preview = ensure_fulfillment_settlement_preview(
            fulfillment_request,
            actor=self.operator,
            force=True,
        )

        self.order.refresh_from_db()
        delivery.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(preview['delivery_partner_fee'], '25.00')
        self.assertEqual(preview['delivery_fee'], '0.00')
        self.assertEqual(self.order.merchant_payout, original_order_payout)
        self.assertEqual(self.order.merchant_payout_status, original_payout_status)
        self.assertEqual(delivery.partner_fee, original_partner_fee)
        self.assertEqual(payment.status, 'PENDING')

    def test_operations_and_merchant_apis_expose_preview_to_internal_users_only(self):
        fulfillment_request = self.create_request()
        self.client.force_authenticate(self.fulfillment_user)
        accepted = self.client.patch(
            f'/api/v1/merchants/network/fulfillment-requests/{fulfillment_request.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertTrue(accepted.data['settlement_preview']['is_preview_only'])
        self.assertEqual(
            accepted.data['settlement_preview_label'],
            'Preview Only — No Financial Settlement Has Been Applied',
        )

        operations_response = self.client.get('/api/v1/operations/fulfillment-requests/')
        self.assertEqual(operations_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.operator)
        operations_response = self.client.get('/api/v1/operations/fulfillment-requests/')
        self.assertEqual(operations_response.status_code, status.HTTP_200_OK)
        self.assertTrue(operations_response.data[0]['settlement_preview']['is_preview_only'])
        self.assertEqual(
            operations_response.data[0]['settlement_preview_label'],
            'Preview Only — No Financial Settlement Has Been Applied',
        )

        self.client.force_authenticate(self.customer)
        customer_response = self.client.get(f'/api/v1/orders/{self.order.id}/')
        self.assertEqual(customer_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('settlement_preview', customer_response.data)
        self.assertNotIn('settlement_preview_label', customer_response.data)
