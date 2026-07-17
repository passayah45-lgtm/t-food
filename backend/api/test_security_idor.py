import tempfile
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from customers.models import Customer, DeliveryAddress
from delivery.models import Delivery, DeliveryPartner, MerchantRider
from ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from markets.models import CommerceArea, CommerceCity, Currency, Market
from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from notifications.models import Notification
from operations_access.models import (
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)
from orders.models import Order, OrderItem, SupportTicket
from payments.models import Payment, PaymentProviderConfig
from restaurants.models import FoodItem, MerchantProfile, Restaurant, RestaurantReview, ReviewPhoto
from verifications.constants import SUBJECT_MERCHANT, VERIFICATION_APPROVED
from verifications.models import VerificationDocument


TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_PRIVATE_MEDIA_ROOT = tempfile.mkdtemp()


def image_upload(name='tfood-proof.jpg'):
    from PIL import Image

    buffer = BytesIO()
    Image.new('RGB', (2, 2), color=(255, 122, 0)).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def response_items(response):
    data = response.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class CrossScopeAuthorizationIdorTests(APITestCase):
    def setUp(self):
        self.gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
            },
        )
        self.inr, _ = Currency.objects.get_or_create(
            code='INR',
            defaults={
                'numeric_code': '356',
                'name': 'Indian Rupee',
                'symbol': 'Rs',
                'minor_unit': 2,
            },
        )
        self.guinea, _ = Market.objects.get_or_create(
            country_code='GN',
            defaults={
                'slug': 'sec-guinea',
                'name': 'Security Guinea',
                'default_currency': self.gnf,
                'timezone': 'Africa/Conakry',
            },
        )
        self.india, _ = Market.objects.get_or_create(
            country_code='IN',
            defaults={
                'slug': 'sec-india',
                'name': 'Security India',
                'default_currency': self.inr,
                'timezone': 'Asia/Kolkata',
            },
        )
        self.conakry = CommerceCity.objects.create(
            market=self.guinea,
            name='Conakry',
            slug='sec-conakry',
        )
        self.kaloum = CommerceArea.objects.create(
            market=self.guinea,
            city=self.conakry,
            name='Kaloum',
            slug='sec-kaloum',
        )
        self.bhubaneswar = CommerceCity.objects.create(
            market=self.india,
            name='Bhubaneswar',
            slug='sec-bhubaneswar',
        )
        self.kiit = CommerceArea.objects.create(
            market=self.india,
            city=self.bhubaneswar,
            name='KIIT Area',
            slug='sec-kiit',
        )

        self.customer_a = User.objects.create_user('sec-customer-a')
        self.customer_b = User.objects.create_user('sec-customer-b')
        Customer.objects.create(user=self.customer_a, phone='620000001')
        Customer.objects.create(user=self.customer_b, phone='620000002')
        self.address_b = DeliveryAddress.objects.create(
            user=self.customer_b,
            label='HOME',
            recipient_name='T-Food Customer',
            phone='620000002',
            address='Kaloum, Conakry',
            market=self.guinea,
        )

        self.merchant_a_user = User.objects.create_user('sec-merchant-a')
        self.merchant_b_user = User.objects.create_user('sec-merchant-b')
        self.merchant_a = MerchantProfile.objects.create(
            user=self.merchant_a_user,
            business_name='T-Food Guinea Merchant',
            market=self.guinea,
            is_verified=True,
            verification_status=VERIFICATION_APPROVED,
        )
        self.merchant_b = MerchantProfile.objects.create(
            user=self.merchant_b_user,
            business_name='T-Food India Merchant',
            market=self.india,
            is_verified=True,
            verification_status=VERIFICATION_APPROVED,
        )
        self.branch_a = Restaurant.objects.create(
            owner=self.merchant_a_user,
            market=self.guinea,
            country_code='GN',
            city_ref=self.conakry,
            area_ref=self.kaloum,
            rest_name='T-Food Kaloum Branch',
            branch_name='T-Food Kaloum Branch',
            rest_email='sec-gn@example.com',
            rest_contact='620000010',
            rest_address='Kaloum',
            rest_city='Conakry',
            is_active=True,
            is_open=True,
        )
        self.branch_b = Restaurant.objects.create(
            owner=self.merchant_b_user,
            market=self.india,
            country_code='IN',
            city_ref=self.bhubaneswar,
            area_ref=self.kiit,
            rest_name='T-Food KIIT Branch',
            branch_name='T-Food KIIT Branch',
            rest_email='sec-in@example.com',
            rest_contact='910000010',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.item_a = FoodItem.objects.create(
            restaurant=self.branch_a,
            food_name='T-Food Rice Bowl',
            food_price=Decimal('100.00'),
            food_categ='Vegetarian',
        )
        self.item_b = FoodItem.objects.create(
            restaurant=self.branch_b,
            food_name='T-Food Dosa',
            food_price=Decimal('120.00'),
            food_categ='Vegetarian',
        )

        self.order_a = self.create_order(self.customer_a, self.branch_a, self.item_a, self.guinea)
        self.order_b = self.create_order(self.customer_b, self.branch_b, self.item_b, self.india)
        self.payment_a = Payment.objects.create(
            order=self.order_a,
            market=self.guinea,
            method='COD',
            status='SUCCESS',
            provider='COD',
        )
        self.payment_b = Payment.objects.create(
            order=self.order_b,
            market=self.india,
            method='COD',
            status='SUCCESS',
            provider='COD',
        )
        self.ticket_b = SupportTicket.objects.create(
            customer=self.customer_b,
            order=self.order_b,
            category='PAYMENT',
            description='T-Food support request',
        )
        self.notification_a = Notification.objects.create(
            user=self.customer_a,
            title='T-Food A',
            message='A',
            kind='ORDER',
            category='ORDER',
            recipient_type='CUSTOMER',
        )
        self.notification_b = Notification.objects.create(
            user=self.customer_b,
            title='T-Food B',
            message='B',
            kind='ORDER',
            category='ORDER',
            recipient_type='CUSTOMER',
        )

        self.partner_a_user = User.objects.create_user('sec-partner-a')
        self.partner_b_user = User.objects.create_user('sec-partner-b')
        self.partner_a = DeliveryPartner.objects.create(
            user=self.partner_a_user,
            partner_name='T-Food Guinea Rider',
            partner_phone='620000021',
            transport_details='Bike',
            market=self.guinea,
            is_verified=True,
            is_available=True,
        )
        self.partner_b = DeliveryPartner.objects.create(
            user=self.partner_b_user,
            partner_name='T-Food India Rider',
            partner_phone='910000021',
            transport_details='Bike',
            market=self.india,
            is_verified=True,
            is_available=True,
        )
        self.delivery_a = Delivery.objects.create(
            order=self.order_a,
            market=self.guinea,
            delivery_partner=self.partner_a,
            status='ASSIGNED',
            partner_fee=Decimal('20.00'),
        )
        self.delivery_b = Delivery.objects.create(
            order=self.order_b,
            market=self.india,
            delivery_partner=self.partner_b,
            status='DELIVERED',
            partner_fee=Decimal('25.00'),
            payout_status='AVAILABLE',
        )

        self.staff_user = User.objects.create_user('sec-branch-staff')
        self.staff = MerchantStaffMember.objects.create(
            merchant=self.merchant_a,
            user=self.staff_user,
            role=MerchantStaffMember.ROLE_BRANCH_MANAGER,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            is_company_wide=False,
        )
        MerchantStaffBranchAccess.objects.create(
            staff_member=self.staff,
            branch=self.branch_a,
        )
        self.finance_user = User.objects.create_user('sec-finance-staff')
        MerchantStaffMember.objects.create(
            merchant=self.merchant_a,
            user=self.finance_user,
            role=MerchantStaffMember.ROLE_FINANCE_STAFF,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            is_company_wide=True,
        )
        self.viewer_user = User.objects.create_user('sec-viewer-staff')
        MerchantStaffMember.objects.create(
            merchant=self.merchant_a,
            user=self.viewer_user,
            role=MerchantStaffMember.ROLE_VIEWER,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            is_company_wide=True,
        )
        self.unverified_staff_user = User.objects.create_user('sec-unverified-staff')
        MerchantStaffMember.objects.create(
            merchant=self.merchant_a,
            user=self.unverified_staff_user,
            role=MerchantStaffMember.ROLE_BRANCH_MANAGER,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
            is_company_wide=True,
        )
        self.rider_link_a = MerchantRider.objects.create(
            merchant=self.merchant_a,
            partner=self.partner_a,
            status=MerchantRider.STATUS_ACTIVE,
            home_restaurant=self.branch_a,
        )

        self.country_admin = User.objects.create_user('sec-country-admin', is_staff=True)
        self.country_profile = OperationsStaffProfile.objects.create(
            user=self.country_admin,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        OperationsStaffMarketAccess.objects.create(
            profile=self.country_profile,
            market=self.guinea,
        )
        self.no_scope_admin = User.objects.create_user('sec-no-scope-admin', is_staff=True)
        OperationsStaffProfile.objects.create(
            user=self.no_scope_admin,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        self.legacy_staff = User.objects.create_user('sec-legacy-staff', is_staff=True)

        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='orange_money',
            payment_method='MOBILE_MONEY',
            is_active=True,
            priority=1,
            credentials_present=False,
        )
        PaymentProviderConfig.objects.create(
            market=self.india,
            country_code='IN',
            currency='INR',
            provider_code='razorpay',
            payment_method='UPI',
            is_active=True,
            priority=1,
            credentials_present=True,
        )
        self.ledger_gn = self.create_ledger(self.guinea, self.gnf, 'GN', 'sec-ledger-gn')
        self.ledger_in = self.create_ledger(self.india, self.inr, 'IN', 'sec-ledger-in')

        self.document = VerificationDocument.objects.create(
            user=self.merchant_a_user,
            subject_type=SUBJECT_MERCHANT,
            document_type='NATIONAL_ID',
            file=image_upload('tfood-id.jpg'),
        )

        self.review_a = RestaurantReview.objects.create(
            restaurant=self.branch_a,
            customer=self.customer_a,
            order=self.order_a,
            rating=5,
            comment='T-Food review',
        )
        self.photo_a = ReviewPhoto.objects.create(
            review=self.review_a,
            uploaded_by=self.customer_a,
            image=image_upload('pending-review.jpg'),
            caption='T-Food photo',
        )

    def create_order(self, customer, branch, item, market):
        order = Order.objects.create(
            customer=customer,
            market=market,
            pickup_branch=branch,
            status='DELIVERED',
            delivery_address='T-Food address',
            contact_phone='620000000',
            subtotal_amount=Decimal('100.00'),
            total_amount=Decimal('120.00'),
            delivery_fee=Decimal('20.00'),
            merchant_payout=Decimal('85.00'),
            merchant_payout_status='AVAILABLE',
        )
        OrderItem.objects.create(order=order, food=item, quantity=1, price=item.food_price)
        return order

    def create_ledger(self, market, currency, country_code, key):
        platform = LedgerAccount.objects.create(
            market=market,
            country_code=country_code,
            currency=currency.code,
            account_type=LedgerAccount.ACCOUNT_PLATFORM,
            name=f'T-Food Platform {country_code}',
        )
        customer = LedgerAccount.objects.create(
            market=market,
            country_code=country_code,
            currency=currency.code,
            account_type=LedgerAccount.ACCOUNT_CUSTOMER,
            name=f'T-Food Customer {country_code}',
        )
        return LedgerTransaction.objects.create_balanced(
            market=market,
            country_code=country_code,
            currency=currency.code,
            provider_code='COD',
            transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
            idempotency_key=key,
            entries=[
                {
                    'account': customer,
                    'direction': LedgerEntry.DIRECTION_DEBIT,
                    'amount': Decimal('120.00'),
                },
                {
                    'account': platform,
                    'direction': LedgerEntry.DIRECTION_CREDIT,
                    'amount': Decimal('120.00'),
                },
            ],
        )

    def ids(self, response):
        collected = set()
        for item in response_items(response):
            if not isinstance(item, dict):
                continue
            for key in ('id', 'branch_id', 'restaurant_id', 'order_id'):
                if key in item:
                    collected.add(item[key])
        return collected

    def test_customer_scope_blocks_cross_customer_objects(self):
        self.client.force_authenticate(self.customer_a)

        self.assertEqual(self.client.get(f'/api/v1/orders/{self.order_b.id}/').status_code, 404)
        self.assertEqual(
            self.client.post(f'/api/v1/payments/orders/{self.order_b.id}/', {'method': 'COD'}).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f'/api/v1/users/addresses/{self.address_b.id}/').status_code,
            404,
        )
        self.assertEqual(
            self.client.post('/api/v1/support/tickets/', {
                'order': self.order_b.id,
                'category': 'PAYMENT',
                'description': 'Should fail',
            }).status_code,
            400,
        )
        notifications = self.client.get('/api/v1/notifications/')
        self.assertEqual(notifications.status_code, 200)
        self.assertIn(self.notification_a.id, self.ids(notifications))
        self.assertNotIn(self.notification_b.id, self.ids(notifications))

    def test_merchant_owner_cannot_access_another_merchant_objects(self):
        self.client.force_authenticate(self.merchant_a_user)

        self.assertEqual(
            self.client.get(f'/api/v1/merchants/restaurants/{self.branch_b.id}/').status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/v1/merchants/restaurants/{self.branch_b.id}/items/{self.item_b.id}/',
                {'food_name': 'Wrong Merchant Edit'},
                format='json',
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/v1/merchants/riders/{self.rider_link_a.id + 10000}/status/',
                {'status': MerchantRider.STATUS_INACTIVE},
                format='json',
            ).status_code,
            404,
        )
        self.client.force_authenticate(self.merchant_b_user)
        staff_response = self.client.get('/api/v1/merchants/staff/')
        self.assertEqual(staff_response.status_code, 200)
        staff_ids = self.ids(staff_response)
        self.assertNotIn(self.staff.id, staff_ids)
        payout_response = self.client.get('/api/v1/merchants/payouts/')
        self.assertEqual(payout_response.status_code, 200)
        self.assertNotIn(self.order_a.id, self.ids(payout_response))

    def test_merchant_staff_role_and_branch_scope_is_enforced(self):
        self.client.force_authenticate(self.staff_user)
        branches = self.client.get('/api/v1/merchants/restaurants/')
        self.assertEqual(branches.status_code, 200)
        self.assertIn(self.branch_a.id, self.ids(branches))
        self.assertNotIn(self.branch_b.id, self.ids(branches))
        self.assertEqual(self.client.get('/api/v1/merchants/payouts/').status_code, 403)

        self.client.force_authenticate(self.finance_user)
        self.assertEqual(self.client.get('/api/v1/merchants/riders/').status_code, 403)

        self.client.force_authenticate(self.viewer_user)
        self.assertEqual(
            self.client.patch(
                f'/api/v1/merchants/restaurants/{self.branch_a.id}/',
                {'is_open': False},
                format='json',
            ).status_code,
            403,
        )

        self.client.force_authenticate(self.unverified_staff_user)
        self.assertEqual(self.client.get('/api/v1/merchants/restaurants/').status_code, 403)

    def test_delivery_partner_scope_is_enforced(self):
        self.client.force_authenticate(self.partner_b_user)

        deliveries = self.client.get('/api/v1/delivery/partner/')
        self.assertEqual(deliveries.status_code, 200)
        self.assertNotIn(self.delivery_a.id, self.ids(deliveries))
        self.assertEqual(
            self.client.patch(
                f'/api/v1/delivery/partner/{self.delivery_a.id}/status/',
                {'status': 'PICKED_UP'},
                format='json',
            ).status_code,
            404,
        )
        earnings = self.client.get('/api/v1/delivery/partner/earnings/')
        self.assertEqual(earnings.status_code, 200)
        self.assertNotContains(earnings, 'sec-customer-a', status_code=200)

    def test_operations_country_scope_filters_sensitive_views(self):
        self.client.force_authenticate(self.country_admin)

        for path, excluded_id in (
            ('/api/v1/operations/branches/', self.branch_b.id),
            ('/api/v1/operations/payment-providers/', None),
            ('/api/v1/operations/review-photos/', None),
            ('/api/v1/operations/notifications/', None),
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            if excluded_id is not None:
                self.assertNotIn(excluded_id, self.ids(response))
            self.assertNotIn('Security India', str(response.data), path)
            sensitive_payload = (
                response.data.get('results', response.data)
                if isinstance(response.data, dict)
                else response.data
            )
            self.assertNotIn('razorpay', str(sensitive_payload), path)

        ledger = self.client.get('/api/v1/operations/ledger/')
        self.assertEqual(ledger.status_code, 200)
        self.assertEqual(
            ledger.data['platform_summary']['ledger_transaction_count'],
            1,
        )
        self.assertEqual(
            ledger.data['recent_activity']['ledger_transactions'][0]['country_code'],
            'GN',
        )

    def test_operations_user_without_scope_gets_empty_results(self):
        self.client.force_authenticate(self.no_scope_admin)

        branches = self.client.get('/api/v1/operations/branches/')
        self.assertEqual(branches.status_code, 200)
        self.assertEqual(response_items(branches), [])

        ledger = self.client.get('/api/v1/operations/ledger/')
        self.assertEqual(ledger.status_code, 200)
        self.assertEqual(ledger.data['platform_summary']['ledger_transaction_count'], 0)

    def test_legacy_staff_global_compatibility_is_preserved(self):
        self.client.force_authenticate(self.legacy_staff)

        branches = self.client.get('/api/v1/operations/branches/')
        self.assertEqual(branches.status_code, 200)
        self.assertIn(self.branch_a.id, self.ids(branches))
        self.assertIn(self.branch_b.id, self.ids(branches))

    def test_private_media_and_review_photo_scope_is_enforced(self):
        self.client.force_authenticate(self.customer_b)

        download = self.client.get(f'/api/v1/verifications/documents/{self.document.id}/download/')
        self.assertEqual(download.status_code, 403)
        raw_document = self.client.get(f'/media/{self.document.file.name}')
        self.assertEqual(raw_document.status_code, 404)

        preview = self.client.get(f'/api/v1/restaurants/review-photos/{self.photo_a.id}/preview/')
        self.assertEqual(preview.status_code, 403)
        raw_photo = self.client.get(f'/media/{self.photo_a.image.name}')
        self.assertEqual(raw_photo.status_code, 404)

        self.photo_a.status = ReviewPhoto.STATUS_APPROVED
        self.photo_a.reviewed_by = self.country_admin
        self.photo_a.reviewed_at = timezone.now()
        self.photo_a.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        public_reviews = self.client.get(f'/api/v1/restaurants/{self.branch_a.id}/reviews/')
        self.assertEqual(public_reviews.status_code, 200)
        self.assertContains(public_reviews, '/media/reviews/photos/approved/', status_code=200)

    def test_review_photo_upload_requires_own_delivered_order_review(self):
        self.client.force_authenticate(self.customer_b)

        response = self.client.post(
            f'/api/v1/restaurants/{self.branch_a.id}/reviews/{self.review_a.id}/photos/',
            {'image': image_upload('wrong-review.jpg')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 403)

    def test_visual_search_does_not_expose_uploaded_image(self):
        self.client.force_authenticate(self.customer_a)

        response = self.client.post(
            '/api/v1/intelligence/visual-product-search/',
            {'image': image_upload('rice-product.jpg')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('predicted_labels', response.data)
        self.assertNotIn('image_url', response.data)
        self.assertNotIn('uploaded_image', response.data)
        self.assertNotContains(response, '/media/', status_code=200)
