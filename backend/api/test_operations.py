from django.contrib.auth.models import User
from decimal import Decimal
from io import BytesIO
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
import tempfile
from PIL import Image

from customers.models import Customer
from notifications.models import Notification
from delivery.models import Delivery, DeliveryPartner, MerchantRider
from ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from markets.models import CommerceArea, CommerceCity, Currency, Market
from orders.models import Order, OrderItem
from payments.models import (
    MerchantPayoutAudit,
    PartnerPayoutAudit,
    Payment,
    PaymentProviderConfig,
    RefundAudit,
)
from restaurants.models import FoodItem, MerchantProfile, Restaurant
from verifications.constants import SUBJECT_MERCHANT, SUBJECT_PARTNER
from verifications.models import VerificationDocument


TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_PRIVATE_MEDIA_ROOT = tempfile.mkdtemp()


def verification_image(name):
    buffer = BytesIO()
    Image.new('RGB', (2, 2), color=(255, 122, 0)).save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class OperationsApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='operator', password='test-password', is_staff=True
        )
        self.customer = User.objects.create_user(
            username='customer', password='test-password', email='customer@example.com',
            first_name='Test', last_name='Customer',
        )
        self.customer_profile = Customer.objects.create(
            user=self.customer, phone='5550001111'
        )
        self.merchant_user = User.objects.create_user(
            username='merchant', password='test-password', email='merchant@example.com'
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user, business_name='Test Kitchen'
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Test Kitchen',
            rest_email='kitchen@example.com',
            rest_contact='1234567890',
            rest_address='Main Street',
            rest_city='Test City',
            is_active=False,
            delivery_radius_km=Decimal('7.50'),
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Launch Bowl',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.partner_user = User.objects.create_user(
            username='driver', password='test-password', email='driver@example.com'
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Test Driver',
            partner_phone='9876543210',
            transport_details='Bike',
        )

    def add_merchant_docs(self):
        for document_type in (
            'OWNER_PROFILE_PHOTO',
            'NATIONAL_ID',
            'RESTAURANT_PHOTO',
        ):
            VerificationDocument.objects.create(
                user=self.merchant_user,
                subject_type=SUBJECT_MERCHANT,
                document_type=document_type,
                file=verification_image(f'{document_type}.jpg'),
            )

    def add_partner_docs(self):
        for document_type in ('PARTNER_PROFILE_PHOTO', 'DRIVING_LICENSE'):
            VerificationDocument.objects.create(
                user=self.partner_user,
                subject_type=SUBJECT_PARTNER,
                document_type=document_type,
                file=verification_image(f'{document_type}.jpg'),
            )

    def ledger_account(self, market, account_type, name):
        return LedgerAccount.objects.create(
            market=market,
            country_code=market.country_code,
            currency=market.default_currency.code,
            account_type=account_type,
            name=name,
            provider_code='TEST',
        )

    def create_ledger_transaction(self, *, market, transaction_type, amount, key, metadata=None):
        debit_account = self.ledger_account(
            market,
            LedgerAccount.ACCOUNT_CASH_CLEARING,
            f'Debit {key}',
        )
        credit_account = self.ledger_account(
            market,
            LedgerAccount.ACCOUNT_PLATFORM,
            f'Credit {key}',
        )
        return LedgerTransaction.objects.create_balanced(
            market=market,
            country_code=market.country_code,
            currency=market.default_currency.code,
            provider_code='TEST',
            transaction_type=transaction_type,
            amount=Decimal(amount),
            idempotency_key=key,
            source_type=(
                'order'
                if transaction_type == LedgerTransaction.TYPE_ORDER_GROSS
                else 'test'
            ),
            source_id=key,
            metadata=metadata or {},
            entries=[
                {
                    'account': debit_account,
                    'direction': LedgerEntry.DIRECTION_DEBIT,
                    'amount': Decimal(amount),
                },
                {
                    'account': credit_account,
                    'direction': LedgerEntry.DIRECTION_CREDIT,
                    'amount': Decimal(amount),
                },
            ],
        )

    def test_non_staff_cannot_access_operations(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get('/api/v1/operations/summary/')
        self.assertEqual(response.status_code, 403)

    def test_non_staff_cannot_access_read_only_operations_lists(self):
        self.client.force_authenticate(self.customer)
        for path in (
            '/api/v1/operations/customers/',
            '/api/v1/operations/restaurants/?status=active',
            '/api/v1/operations/orders/?status=open',
            '/api/v1/operations/revenue/',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)

    def test_admin_can_list_customers_without_passwords(self):
        Order.objects.create(customer=self.customer, status='PLACED', total_amount=Decimal('125.00'))
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/customers/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['name'], 'Test Customer')
        self.assertEqual(response.data[0]['email'], 'customer@example.com')
        self.assertEqual(response.data[0]['phone'], '5550001111')
        self.assertEqual(response.data[0]['total_orders'], 1)
        self.assertIn('created_at', response.data[0])
        self.assertTrue(response.data[0]['is_active'])
        self.assertNotIn('password', response.data[0])

    def test_admin_can_list_active_restaurants(self):
        self.merchant.is_verified = True
        self.merchant.save(update_fields=['is_verified'])
        self.restaurant.refresh_from_db()
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/restaurants/?status=active')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['name'], 'Test Kitchen')
        self.assertEqual(response.data[0]['merchant_business_name'], 'Test Kitchen')
        self.assertTrue(response.data[0]['is_active'])
        self.assertTrue(response.data[0]['merchant_verified'])
        self.assertEqual(response.data[0]['city'], 'Test City')
        self.assertIn('delivery_radius_km', response.data[0])
        self.assertNotIn('password', response.data[0])

    def test_operations_can_list_branches_with_filters_without_passwords(self):
        market = Market.objects.get(slug='india')
        city = CommerceCity.objects.create(market=market, name='Bhubaneswar')
        area = CommerceArea.objects.create(city=city, name='KIIT Area')
        self.merchant.is_verified = True
        self.merchant.save(update_fields=['is_verified'])
        self.restaurant.market = market
        self.restaurant.branch_name = 'KIIT Food Branch'
        self.restaurant.branch_code = 'IN-BBI-KIIT-FOOD'
        self.restaurant.branch_type = Restaurant.BRANCH_TYPE_FOOD
        self.restaurant.country_code = 'IN'
        self.restaurant.city_ref = city
        self.restaurant.area_ref = area
        self.restaurant.is_open = True
        self.restaurant.is_active = True
        self.restaurant.save()
        self.partner.is_verified = True
        self.partner.save(update_fields=['is_verified'])
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.partner,
            home_restaurant=self.restaurant,
            status=MerchantRider.STATUS_ACTIVE,
        )
        order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('160.00'),
            platform_fee=Decimal('16.00'),
            merchant_payout=Decimal('120.00'),
        )
        Payment.objects.create(order=order, method='COD', status='SUCCESS')
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price=Decimal('100.00'),
            base_price=Decimal('100.00'),
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/branches/', {
            'market': 'india',
            'country_code': 'IN',
            'city': 'bhubaneswar',
            'area': 'kiit-area',
            'branch_type': Restaurant.BRANCH_TYPE_FOOD,
            'is_active': 'true',
            'is_open': 'true',
            'merchant_id': self.merchant.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        branch = response.data[0]
        self.assertEqual(branch['branch_id'], self.restaurant.id)
        self.assertEqual(branch['branch_name'], 'KIIT Food Branch')
        self.assertEqual(branch['rest_name'], 'Test Kitchen')
        self.assertEqual(branch['branch_type'], Restaurant.BRANCH_TYPE_FOOD)
        self.assertEqual(branch['merchant_company']['business_name'], 'Test Kitchen')
        self.assertTrue(branch['merchant_verification_status']['is_verified'])
        self.assertEqual(branch['market']['slug'], 'india')
        self.assertEqual(branch['country'], 'IN')
        self.assertEqual(branch['city']['name'], 'Bhubaneswar')
        self.assertEqual(branch['area']['name'], 'KIIT Area')
        self.assertEqual(branch['address'], 'Main Street')
        self.assertEqual(branch['rider_count'], 1)
        self.assertEqual(branch['available_rider_count'], 1)
        self.assertEqual(branch['verified_rider_count'], 1)
        self.assertEqual(len(branch['branch_riders']), 1)
        self.assertEqual(branch['branch_riders'][0]['name'], self.partner.partner_name)
        self.assertTrue(branch['branch_riders'][0]['is_available'])
        self.assertTrue(branch['branch_riders'][0]['is_verified'])
        self.assertEqual(branch['menu_count'], 1)
        self.assertEqual(branch['order_count'], 1)
        self.assertEqual(branch['revenue_summary']['gross_sales'], Decimal('160.00'))
        self.assertEqual(branch['analytics']['orders'], 1)
        self.assertEqual(branch['analytics']['revenue'], Decimal('160.00'))
        self.assertEqual(branch['analytics']['average_order_value'], Decimal('160.00'))
        self.assertEqual(branch['analytics']['rider_count'], 1)
        self.assertEqual(branch['analytics']['available_riders'], 1)
        self.assertEqual(branch['analytics']['verified_riders'], 1)
        self.assertEqual(branch['analytics']['rider_utilization_percent'], 100.0)
        self.assertIn('created_at', branch)
        self.assertIn('updated_at', branch)
        self.assertNotIn('password', str(branch).lower())

        branch_response = self.client.get(
            '/api/v1/operations/branches/',
            {'branch_id': self.restaurant.id},
        )

        self.assertEqual(branch_response.status_code, 200)
        self.assertEqual(len(branch_response.data), 1)
        self.assertEqual(branch_response.data[0]['branch_id'], self.restaurant.id)

    def test_non_staff_cannot_list_branches(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/operations/branches/')

        self.assertEqual(response.status_code, 403)

    def test_operations_can_open_and_close_branch(self):
        self.client.force_authenticate(self.admin)

        close = self.client.patch(
            f'/api/v1/operations/branches/{self.restaurant.id}/status/',
            {'is_open': False},
            format='json',
        )
        self.restaurant.refresh_from_db()
        self.assertEqual(close.status_code, 200)
        self.assertFalse(self.restaurant.is_open)

        open_response = self.client.patch(
            f'/api/v1/operations/branches/{self.restaurant.id}/status/',
            {'is_open': True},
            format='json',
        )
        self.restaurant.refresh_from_db()
        self.assertEqual(open_response.status_code, 200)
        self.assertTrue(self.restaurant.is_open)

    def test_operations_can_activate_verified_merchant_branch(self):
        self.merchant.is_verified = True
        self.merchant.save(update_fields=['is_verified'])
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=['is_active'])
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/branches/{self.restaurant.id}/status/',
            {'is_active': True},
            format='json',
        )

        self.restaurant.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.restaurant.is_active)

    def test_operations_cannot_activate_unverified_merchant_branch(self):
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=['is_active'])
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/branches/{self.restaurant.id}/status/',
            {'is_active': True},
            format='json',
        )

        self.restaurant.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.restaurant.is_active)
        self.assertIn('is_active', response.data)

    def test_admin_can_list_open_orders(self):
        order = Order.objects.create(
            customer=self.customer,
            status='READY_FOR_PICKUP',
            total_amount=Decimal('150.00'),
            platform_fee=Decimal('15.00'),
            merchant_payout=Decimal('105.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price=Decimal('100.00'),
            base_price=Decimal('100.00'),
        )
        Payment.objects.create(order=order, method='COD', status='SUCCESS')
        Delivery.objects.create(order=order, status='ASSIGNED')
        delivered = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('200.00'),
        )
        Payment.objects.create(order=delivered, method='COD', status='SUCCESS')
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/orders/?status=open')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], order.id)
        self.assertEqual(response.data[0]['customer'], 'Test Customer')
        self.assertEqual(response.data[0]['restaurant'], 'Test Kitchen')
        self.assertEqual(response.data[0]['payment_status'], 'SUCCESS')
        self.assertEqual(response.data[0]['delivery_status'], 'ASSIGNED')
        self.assertNotIn('password', response.data[0])

    def test_admin_can_view_revenue_breakdown(self):
        delivered = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('200.00'),
            delivery_fee=Decimal('30.00'),
            platform_fee=Decimal('20.00'),
            merchant_payout=Decimal('150.00'),
            merchant_payout_status='AVAILABLE',
        )
        Payment.objects.create(order=delivered, method='COD', status='SUCCESS')
        Delivery.objects.create(
            order=delivered,
            delivery_partner=self.partner,
            status='DELIVERED',
            partner_fee=Decimal('30.00'),
            payout_status='AVAILABLE',
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/revenue/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['gross_sales'], Decimal('200.00'))
        self.assertEqual(response.data['merchant_earnings'], Decimal('150.00'))
        self.assertEqual(response.data['platform_revenue'], Decimal('20.00'))
        self.assertEqual(response.data['delivery_fees'], Decimal('30.00'))
        self.assertEqual(response.data['pending_payouts'], Decimal('180.00'))
        self.assertIn('today', response.data)
        self.assertIn('week', response.data)
        self.assertIn('month', response.data)
        self.assertIn('year', response.data)
        self.assertNotIn('password', response.data)

    def test_admin_can_view_read_only_ledger_finance_dashboard(self):
        market = Market.objects.get(slug='india')
        order = Order.objects.create(
            customer=self.customer,
            market=market,
            status='DELIVERED',
            total_amount=Decimal('240.00'),
            platform_fee=Decimal('24.00'),
            merchant_payout=Decimal('180.00'),
        )
        payment = Payment.objects.create(
            order=order,
            market=market,
            method='COD',
            status='REFUNDED',
            provider='cod',
        )
        delivery = Delivery.objects.create(
            order=order,
            delivery_partner=self.partner,
            status='DELIVERED',
            partner_fee=Decimal('36.00'),
        )
        order_gross = self.create_ledger_transaction(
            market=market,
            transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
            amount='240.00',
            key='ops-ledger-gross',
            metadata={'platform_fee': '24.00'},
        )
        merchant_payout = self.create_ledger_transaction(
            market=market,
            transaction_type=LedgerTransaction.TYPE_MERCHANT_PAYOUT,
            amount='180.00',
            key='ops-ledger-merchant-payout',
        )
        partner_payout = self.create_ledger_transaction(
            market=market,
            transaction_type=LedgerTransaction.TYPE_PARTNER_DELIVERY_FEE,
            amount='36.00',
            key='ops-ledger-partner-payout',
        )
        refund = self.create_ledger_transaction(
            market=market,
            transaction_type=LedgerTransaction.TYPE_REFUND,
            amount='240.00',
            key='ops-ledger-refund',
        )
        preview = self.create_ledger_transaction(
            market=market,
            transaction_type=LedgerTransaction.TYPE_FULFILLMENT_PREVIEW,
            amount='180.00',
            key='ops-ledger-preview',
        )
        RefundAudit.objects.create(
            order=order,
            payment=payment,
            amount=Decimal('240.00'),
            currency='INR',
            reason='Customer support refund',
            initiated_by=self.admin,
            provider_code='COD',
            status=RefundAudit.STATUS_SUCCEEDED,
            ledger_transaction=refund,
            idempotency_key='ops-ledger-refund-audit',
        )
        MerchantPayoutAudit.objects.create(
            order=order,
            merchant=self.merchant,
            amount=Decimal('180.00'),
            currency='INR',
            market=market,
            country_code='IN',
            status=MerchantPayoutAudit.STATUS_AVAILABLE,
            marked_by=self.admin,
            ledger_transaction=merchant_payout,
            idempotency_key='ops-ledger-merchant-audit',
        )
        PartnerPayoutAudit.objects.create(
            delivery=delivery,
            partner=self.partner,
            amount=Decimal('36.00'),
            currency='INR',
            market=market,
            country_code='IN',
            status=PartnerPayoutAudit.STATUS_AVAILABLE,
            marked_by=self.admin,
            ledger_transaction=partner_payout,
            idempotency_key='ops-ledger-partner-audit',
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/ledger/')

        self.assertEqual(response.status_code, 200)
        summary = response.data['platform_summary']
        self.assertEqual(summary['total_gross_revenue'], Decimal('240.00'))
        self.assertEqual(summary['total_platform_fees'], Decimal('24.00'))
        self.assertEqual(summary['total_merchant_payouts'], Decimal('180.00'))
        self.assertEqual(summary['total_partner_payouts'], Decimal('36.00'))
        self.assertEqual(summary['total_refunds'], Decimal('240.00'))
        self.assertEqual(summary['total_settlement_preview_amount'], Decimal('180.00'))
        self.assertEqual(summary['ledger_transaction_count'], 5)
        self.assertEqual(summary['ledger_entry_count'], 10)
        self.assertEqual(response.data['financial_health']['unbalanced_transactions'], 0)
        self.assertEqual(response.data['financial_health']['status'], 'LEDGER_VERIFIED')
        self.assertTrue(response.data['financial_health']['idempotency_unique_keys_enforced'])
        self.assertIn(
            'INR',
            [row['key'] for row in response.data['breakdowns']['by_currency']],
        )
        self.assertIn(
            'TEST',
            [row['key'] for row in response.data['breakdowns']['by_provider']],
        )
        recent = response.data['recent_activity']
        self.assertTrue(recent['ledger_transactions'])
        self.assertEqual(recent['refund_audits'][0]['ledger_transaction_id'], refund.id)
        self.assertEqual(
            recent['merchant_payout_audits'][0]['ledger_transaction_id'],
            merchant_payout.id,
        )
        self.assertEqual(
            recent['partner_payout_audits'][0]['ledger_transaction_id'],
            partner_payout.id,
        )
        self.assertEqual(
            recent['fulfillment_preview_ledger_entries'][0]['id'],
            preview.id,
        )
        self.assertNotIn('password', str(response.data).lower())

    def test_non_staff_cannot_view_ledger_finance_dashboard(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/operations/ledger/')

        self.assertEqual(response.status_code, 403)

    def test_operations_can_create_and_update_payment_provider_config(self):
        gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'FG',
                'minor_unit': 0,
            },
        )
        guinea, _ = Market.objects.get_or_create(
            slug='guinea',
            defaults={
                'name': 'Guinea',
                'country_code': 'GN',
                'default_currency': gnf,
                'timezone': 'Africa/Conakry',
                'phone_country_code': '+224',
            },
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post('/api/v1/operations/payment-providers/', {
            'market': guinea.id,
            'country_code': 'GN',
            'currency': 'GNF',
            'provider_code': 'wave',
            'payment_method': 'MOBILE_MONEY',
            'is_active': True,
            'is_preferred': True,
            'priority': 1,
            'supports_refund': True,
            'supports_webhook': True,
            'supports_partial_refund': False,
            'credentials_present': True,
            'config_metadata': {'settlement_window': 'T+1'},
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['provider_code'], 'wave')
        self.assertEqual(response.data['provider_display_name'], 'Wave')
        self.assertTrue(response.data['is_active'])
        self.assertTrue(response.data['is_preferred'])
        self.assertTrue(response.data['credentials_present'])
        self.assertNotIn('secret', str(response.data).lower())
        config_id = response.data['id']

        response = self.client.patch(
            f'/api/v1/operations/payment-providers/{config_id}/',
            {'priority': 2, 'is_preferred': False},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['priority'], 2)
        self.assertFalse(response.data['is_preferred'])
        self.assertEqual(
            PaymentProviderConfig.objects.get(id=config_id).updated_by,
            self.admin,
        )

    def test_payment_provider_config_rejects_secret_metadata(self):
        market = Market.objects.get(slug='india')
        self.client.force_authenticate(self.admin)

        response = self.client.post('/api/v1/operations/payment-providers/', {
            'market': market.id,
            'country_code': 'IN',
            'currency': 'INR',
            'provider_code': 'razorpay',
            'payment_method': 'UPI',
            'is_active': True,
            'is_preferred': True,
            'credentials_present': True,
            'config_metadata': {'api_key': 'do-not-store-this'},
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('config_metadata', response.data)

    def test_non_staff_cannot_access_payment_provider_configs(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/operations/payment-providers/')

        self.assertEqual(response.status_code, 403)

    def test_operations_range_filters_date_sensitive_endpoints(self):
        old_user = User.objects.create_user(
            username='old-customer',
            password='test-password',
            email='old@example.com',
        )
        Customer.objects.create(user=old_user, phone='5559990000')
        today_order = Order.objects.create(
            customer=self.customer,
            status='READY_FOR_PICKUP',
            total_amount=Decimal('120.00'),
            delivery_fee=Decimal('20.00'),
            platform_fee=Decimal('12.00'),
            merchant_payout=Decimal('88.00'),
            merchant_payout_status='AVAILABLE',
        )
        OrderItem.objects.create(
            order=today_order,
            food=self.food,
            quantity=1,
            price=Decimal('100.00'),
            base_price=Decimal('100.00'),
        )
        Payment.objects.create(order=today_order, method='COD', status='SUCCESS')
        today_delivery = Delivery.objects.create(
            order=today_order,
            status='ASSIGNED',
        )
        today_ticket = today_order.support_tickets.create(
            customer=self.customer,
            category='ORDER_ISSUE',
            description='Today support issue',
        )
        today_payout_order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('160.00'),
            delivery_fee=Decimal('25.00'),
            platform_fee=Decimal('16.00'),
            merchant_payout=Decimal('119.00'),
            merchant_payout_status='AVAILABLE',
        )
        Payment.objects.create(order=today_payout_order, method='COD', status='SUCCESS')
        today_payout_delivery = Delivery.objects.create(
            order=today_payout_order,
            delivery_partner=self.partner,
            status='DELIVERED',
            partner_fee=Decimal('25.00'),
            payout_status='AVAILABLE',
        )
        old_order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('200.00'),
            delivery_fee=Decimal('30.00'),
            platform_fee=Decimal('20.00'),
            merchant_payout=Decimal('150.00'),
            merchant_payout_status='AVAILABLE',
        )
        Payment.objects.create(order=old_order, method='COD', status='SUCCESS')
        old_delivery = Delivery.objects.create(
            order=old_order,
            delivery_partner=self.partner,
            status='DELIVERED',
            partner_fee=Decimal('30.00'),
            payout_status='AVAILABLE',
        )
        old_ticket = old_order.support_tickets.create(
            customer=self.customer,
            category='ORDER_ISSUE',
            description='Old support issue',
        )
        old_date = timezone.now() - timezone.timedelta(days=10)
        User.objects.filter(id=old_user.id).update(date_joined=old_date)
        Order.objects.filter(id=old_order.id).update(created_at=old_date)
        Delivery.objects.filter(id=old_delivery.id).update(delivery_date=old_date)
        SupportTicket = old_ticket.__class__
        SupportTicket.objects.filter(id=old_ticket.id).update(created_at=old_date)
        self.client.force_authenticate(self.admin)

        customers_today = self.client.get('/api/v1/operations/customers/?range=today')
        customers_month = self.client.get('/api/v1/operations/customers/?range=last_30_days')
        orders_today = self.client.get('/api/v1/operations/orders/?status=open&range=today')
        orders_yesterday = self.client.get('/api/v1/operations/orders/?status=open&range=yesterday')
        revenue_today = self.client.get('/api/v1/operations/revenue/?range=today')
        revenue_month = self.client.get('/api/v1/operations/revenue/?range=last_30_days')
        support_today = self.client.get('/api/v1/operations/support/?range=today')
        dispatch_today = self.client.get('/api/v1/operations/dispatch/?range=today')
        merchant_payouts_today = self.client.get('/api/v1/operations/payouts/merchants/?range=today')
        merchant_payouts_month = self.client.get('/api/v1/operations/payouts/merchants/?range=last_30_days')
        partner_payouts_today = self.client.get('/api/v1/operations/payouts/partners/?range=today')
        partner_payouts_month = self.client.get('/api/v1/operations/payouts/partners/?range=last_30_days')

        self.assertEqual(customers_today.status_code, 200)
        self.assertEqual(customers_month.status_code, 200)
        self.assertEqual(len(customers_today.data), 1)
        self.assertEqual(len(customers_month.data), 2)
        self.assertEqual([order['id'] for order in orders_today.data], [today_order.id])
        self.assertEqual(orders_yesterday.data, [])
        self.assertEqual(revenue_today.data['platform_revenue'], Decimal('16.00'))
        self.assertEqual(revenue_month.data['platform_revenue'], Decimal('36.00'))
        self.assertIn(today_ticket.id, [ticket['id'] for ticket in support_today.data])
        self.assertNotIn(old_ticket.id, [ticket['id'] for ticket in support_today.data])
        self.assertEqual([delivery['id'] for delivery in dispatch_today.data], [today_delivery.id])
        self.assertEqual([payout['id'] for payout in merchant_payouts_today.data], [today_payout_order.id])
        self.assertIn(old_order.id, [payout['id'] for payout in merchant_payouts_month.data])
        self.assertEqual([payout['id'] for payout in partner_payouts_today.data], [today_payout_delivery.id])
        self.assertIn(old_delivery.id, [payout['id'] for payout in partner_payouts_month.data])

    def test_admin_can_approve_and_suspend_merchant(self):
        self.add_merchant_docs()
        self.client.force_authenticate(self.admin)
        approve = self.client.patch(
            f'/api/v1/operations/merchants/{self.merchant.id}/status/',
            {'is_verified': True},
            format='json',
        )
        self.assertEqual(approve.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertTrue(self.restaurant.is_active)
        self.assertTrue(Notification.objects.filter(
            user=self.merchant_user, title='Merchant account approved'
        ).exists())

        suspend = self.client.patch(
            f'/api/v1/operations/merchants/{self.merchant.id}/status/',
            {'is_verified': False},
            format='json',
        )
        self.assertEqual(suspend.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertFalse(self.restaurant.is_active)

    def test_pending_filter_returns_unverified_merchants(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/v1/operations/merchants/?status=pending')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'merchant')

    def test_admin_can_approve_and_suspend_delivery_partner(self):
        self.add_partner_docs()
        self.client.force_authenticate(self.admin)
        approve = self.client.patch(
            f'/api/v1/operations/partners/{self.partner.id}/status/',
            {'is_verified': True},
            format='json',
        )
        self.assertEqual(approve.status_code, 200)
        self.partner.refresh_from_db()
        self.assertTrue(self.partner.is_verified)
        self.assertTrue(self.partner.is_available)
        self.assertTrue(Notification.objects.filter(
            user=self.partner_user,
            title='Delivery partner account approved',
        ).exists())

        suspend = self.client.patch(
            f'/api/v1/operations/partners/{self.partner.id}/status/',
            {'is_verified': False},
            format='json',
        )
        self.assertEqual(suspend.status_code, 200)
        self.partner.refresh_from_db()
        self.assertFalse(self.partner.is_verified)
        self.assertFalse(self.partner.is_available)

    def test_pending_partner_cannot_access_delivery_queue(self):
        self.client.force_authenticate(self.partner_user)
        response = self.client.get('/api/v1/delivery/partner/')
        self.assertEqual(response.status_code, 403)
