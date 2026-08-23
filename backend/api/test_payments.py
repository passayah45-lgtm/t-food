import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

from markets.models import Currency, Market
from orders.models import Order, OrderItem
from payments.models import Payment, PaymentWebhookEvent
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class SecurePaymentTests(APITestCase):
    def setUp(self):
        merchant = User.objects.create_user(username='payment-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        restaurant = Restaurant.objects.create(
            owner=merchant,
            rest_name='Payment Kitchen',
            rest_email='pay@example.com',
            rest_contact='1234567890',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name='Payment Meal',
            food_price=Decimal('100.00'),
            food_categ='Meals',
        )
        self.customer = User.objects.create_user(username='payment-customer')
        self.order = Order.objects.create(
            customer=self.customer,
            delivery_address='12 Test Street',
            contact_phone='1234567890',
            subtotal_amount=Decimal('100.00'),
            total_amount=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=self.order, food=food, quantity=1, price=Decimal('100.00')
        )
        self.client.force_authenticate(self.customer)

    @override_settings(RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET='')
    def test_online_payment_never_succeeds_without_gateway(self):
        response = self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/',
            {'method': 'CARD'},
            format='json',
        )

        self.assertEqual(response.status_code, 503)
        self.order.refresh_from_db()
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(self.order.status, 'PLACED')
        self.assertEqual(payment.status, 'PENDING')
        self.assertIsNone(payment.transaction_id)

    @override_settings(
        RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='test-secret'
    )
    @patch(
        'payments.providers.razorpay.create_razorpay_order',
        return_value='order_gateway_1',
    )
    def test_verified_signature_confirms_online_payment(self, create_order):
        initiation = self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/',
            {'method': 'UPI'},
            format='json',
        )
        self.assertEqual(initiation.status_code, 200)
        self.assertTrue(initiation.data['payment_required'])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PLACED')
        self.assertEqual(self.order.payment.status, 'PENDING')

        payment_id = 'pay_verified_1'
        signature = hmac.new(
            b'test-secret',
            f'order_gateway_1|{payment_id}'.encode(),
            hashlib.sha256,
        ).hexdigest()
        verified = self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/verify/',
            {
                'razorpay_order_id': 'order_gateway_1',
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature,
            },
            format='json',
        )

        self.assertEqual(verified.status_code, 200)
        self.order.refresh_from_db()
        self.order.payment.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertEqual(self.order.payment.status, 'SUCCESS')
        self.assertEqual(self.order.payment.transaction_id, payment_id)

    @override_settings(
        RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='test-secret'
    )
    @patch(
        'payments.providers.razorpay.create_razorpay_order',
        return_value='order_gateway_2',
    )
    def test_invalid_signature_does_not_confirm_order(self, create_order):
        self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/',
            {'method': 'CARD'},
            format='json',
        )
        response = self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/verify/',
            {
                'razorpay_order_id': 'order_gateway_2',
                'razorpay_payment_id': 'pay_unverified',
                'razorpay_signature': 'invalid',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.order.payment.refresh_from_db()
        self.assertEqual(self.order.status, 'PLACED')
        self.assertEqual(self.order.payment.status, 'PENDING')

    def test_cod_still_confirms_without_marking_payment_successful(self):
        first = self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/',
            {'method': 'COD'},
            format='json',
        )
        second = self.client.post(
            f'/api/v1/payments/orders/{self.order.id}/',
            {'method': 'COD'},
            format='json',
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.order.refresh_from_db()
        self.order.payment.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertEqual(self.order.payment.status, 'PENDING')

    def test_checkout_created_market_order_can_continue_to_cod_payment(self):
        gnf = Currency.objects.create(
            code='GNF',
            numeric_code='324',
            name='Guinean Franc',
            symbol='GNF',
            minor_unit=0,
        )
        market = Market.objects.create(
            slug='guinea-checkout',
            name='Guinea',
            country_code='GN',
            default_currency=gnf,
            timezone='Africa/Conakry',
            phone_country_code='+224',
        )
        merchant = User.objects.create_user(username='checkout-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        restaurant = Restaurant.objects.create(
            market=market,
            owner=merchant,
            rest_name='Conakry Checkout Kitchen',
            rest_email='checkout-conakry@example.com',
            rest_contact='+224620000000',
            rest_address='Kaloum',
            rest_city='Conakry',
            country_code='GN',
            is_active=True,
            is_open=True,
        )
        food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name='Poulet yassa',
            food_price=Decimal('7000.00'),
            food_categ='Meals',
            is_available=True,
        )
        response = self.client.post(
            '/api/v1/orders/',
            {
                'delivery_address': 'Kaloum main road',
                'contact_phone': '+224625000000',
                'delivery_instructions': 'Call on arrival',
                'items': [{'food_id': food.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.market, market)

        payment = self.client.post(
            f'/api/v1/payments/orders/{order.id}/',
            {'method': 'COD'},
            format='json',
        )

        self.assertEqual(payment.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')
        self.assertEqual(order.payment.method, 'COD')
        self.assertEqual(order.payment.status, 'PENDING')
        self.assertEqual(order.payment.market, market)

    def test_cod_payment_recovers_market_from_pickup_branch_for_existing_orders(self):
        gnf = Currency.objects.create(
            code='GNF',
            numeric_code='324',
            name='Guinea Test Franc',
            symbol='GNF',
            minor_unit=0,
        )
        market = Market.objects.create(
            slug='guinea-legacy-order',
            name='Guinea Legacy',
            country_code='GL',
            default_currency=gnf,
            timezone='Africa/Conakry',
            phone_country_code='+224',
        )
        merchant = User.objects.create_user(username='legacy-merchant')
        MerchantProfile.objects.create(user=merchant, is_verified=True)
        restaurant = Restaurant.objects.create(
            market=market,
            owner=merchant,
            rest_name='Legacy Market Kitchen',
            rest_email='legacy-market@example.com',
            rest_contact='+224620000001',
            rest_address='Ratoma',
            rest_city='Conakry',
            country_code='GL',
            is_active=True,
            is_open=True,
        )
        order = Order.objects.create(
            customer=self.customer,
            pickup_branch=restaurant,
            delivery_address='Ratoma road',
            contact_phone='+224625000001',
            subtotal_amount=Decimal('100.00'),
            total_amount=Decimal('100.00'),
        )
        Order.objects.filter(id=order.id).update(market=None)
        order.refresh_from_db()

        response = self.client.post(
            f'/api/v1/payments/orders/{order.id}/',
            {'method': 'COD'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.market, market)
        self.assertEqual(order.payment.market, market)

    def webhook_body(self, event_type, amount=10000, payment_id='pay_webhook_1'):
        return json.dumps({
            'event': event_type,
            'payload': {
                'payment': {
                    'entity': {
                        'id': payment_id,
                        'order_id': 'order_webhook_1',
                        'amount': amount,
                        'currency': 'INR',
                    }
                }
            },
        }).encode()

    def create_pending_gateway_payment(self):
        return Payment.objects.create(
            order=self.order,
            method='CARD',
            status='PENDING',
            provider='RAZORPAY',
            provider_order_id='order_webhook_1',
        )

    def post_webhook(self, body, event_id, signature=None):
        signature = signature or hmac.new(
            b'webhook-secret', body, hashlib.sha256
        ).hexdigest()
        return self.client.post(
            '/api/v1/payments/webhooks/razorpay/',
            data=body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature,
            HTTP_X_RAZORPAY_EVENT_ID=event_id,
        )

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_captured_webhook_confirms_order_once(self):
        payment = self.create_pending_gateway_payment()
        body = self.webhook_body('payment.captured')

        first = self.post_webhook(body, 'event-captured-1')
        second = self.post_webhook(body, 'event-captured-1')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['status'], 'processed')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['status'], 'already_processed')
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertEqual(payment.status, 'SUCCESS')
        self.assertEqual(payment.transaction_id, 'pay_webhook_1')
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_invalid_webhook_signature_is_rejected(self):
        payment = self.create_pending_gateway_payment()
        body = self.webhook_body('payment.captured')

        response = self.post_webhook(body, 'event-invalid-1', 'forged')

        self.assertEqual(response.status_code, 401)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(PaymentWebhookEvent.objects.exists())

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_webhook_amount_must_match_order(self):
        payment = self.create_pending_gateway_payment()
        body = self.webhook_body('payment.captured', amount=9999)

        response = self.post_webhook(body, 'event-amount-1')

        self.assertEqual(response.status_code, 400)
        payment.refresh_from_db()
        event = PaymentWebhookEvent.objects.get(event_id='event-amount-1')
        self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(event.processed)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_failed_webhook_cannot_downgrade_success(self):
        payment = self.create_pending_gateway_payment()
        captured = self.webhook_body('payment.captured')
        failed = self.webhook_body(
            'payment.failed', payment_id='pay_failed_after_success'
        )

        self.post_webhook(captured, 'event-captured-2')
        response = self.post_webhook(failed, 'event-failed-1')

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'SUCCESS')
        self.assertEqual(payment.transaction_id, 'pay_webhook_1')

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_late_captured_webhook_restores_expired_order(self):
        payment = self.create_pending_gateway_payment()
        self.order.status = 'EXPIRED'
        self.order.merchant_payout_status = 'CANCELLED'
        self.order.save(update_fields=['status', 'merchant_payout_status'])
        payment.status = 'CANCELLED'
        payment.save(update_fields=['status'])

        response = self.post_webhook(
            self.webhook_body('payment.captured'), 'event-late-capture-1'
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')
        self.assertEqual(self.order.merchant_payout_status, 'PENDING')
        self.assertEqual(payment.status, 'SUCCESS')
