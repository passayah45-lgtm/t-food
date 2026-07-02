from django.contrib.auth.models import User
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
import tempfile
from PIL import Image

from delivery.models import DeliveryPartner
from markets.models import Currency, Market
from merchant_staff.models import MerchantStaffMember
from restaurants.models import MerchantProfile, Restaurant
from verifications.constants import (
    SUBJECT_MERCHANT,
    SUBJECT_MERCHANT_STAFF,
    SUBJECT_PARTNER,
    VERIFICATION_APPROVED,
    VERIFICATION_REJECTED,
)
from verifications.models import VerificationDocument, VerificationDocumentRequirement


TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_PRIVATE_MEDIA_ROOT = tempfile.mkdtemp()


def upload(name='document.jpg', content=None):
    if content is None:
        buffer = BytesIO()
        Image.new('RGB', (2, 2), color=(255, 122, 0)).save(buffer, format='JPEG')
        content = buffer.getvalue()
    return SimpleUploadedFile(name, content, content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class VerificationDocumentApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='verification-admin',
            password='test-password',
            is_staff=True,
        )
        self.merchant_user = User.objects.create_user(
            username='verification-merchant',
            password='test-password',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Verification Kitchen',
        )
        self.currency = Currency.objects.create(
            code='GNF',
            numeric_code='324',
            name='Guinean Franc',
            symbol='FG',
            minor_unit=0,
        )
        self.market = Market.objects.create(
            slug='guinea-verification-test',
            name='Guinea Verification Test',
            country_code='GN',
            default_currency=self.currency,
            timezone='Africa/Conakry',
        )
        self.merchant.market = self.market
        self.merchant.save(update_fields=('market',))
        self.restaurant = Restaurant.objects.create(
            market=self.market,
            owner=self.merchant_user,
            rest_name='Verification Kitchen',
            rest_email='verification@example.com',
            rest_contact='1234567890',
            rest_address='Main Street',
            rest_city='Test City',
            is_active=False,
        )
        self.partner_user = User.objects.create_user(
            username='verification-partner',
            password='test-password',
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Verification Partner',
            partner_phone='9876543210',
            transport_details='Bike',
        )
        self.other_user = User.objects.create_user(
            username='verification-other',
            password='test-password',
        )
        MerchantProfile.objects.create(user=self.other_user)
        self.staff_user = User.objects.create_user(
            username='verification-staff',
            password='test-password',
        )
        self.staff_member = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=self.staff_user,
            role=MerchantStaffMember.ROLE_KITCHEN_STAFF,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
        )

    def post_merchant_doc(self, document_type='NATIONAL_ID'):
        return self.client.post(
            '/api/v1/verifications/merchant/documents/',
            {
                'document_type': document_type,
                'file': upload(f'{document_type}.jpg'),
            },
            format='multipart',
        )

    def post_partner_doc(self, document_type='DRIVING_LICENSE'):
        return self.client.post(
            '/api/v1/verifications/partner/documents/',
            {
                'document_type': document_type,
                'file': upload(f'{document_type}.jpg'),
            },
            format='multipart',
        )

    def post_staff_doc(self, document_type='NATIONAL_ID'):
        return self.client.post(
            '/api/v1/verifications/staff/documents/',
            {
                'document_type': document_type,
                'file': upload(f'{document_type}.jpg'),
            },
            format='multipart',
        )

    def add_required_merchant_documents(self):
        self.client.force_authenticate(self.merchant_user)
        for document_type in (
            'OWNER_PROFILE_PHOTO',
            'NATIONAL_ID',
            'RESTAURANT_PHOTO',
        ):
            response = self.post_merchant_doc(document_type)
            self.assertEqual(response.status_code, 201, response.data)

    def add_required_partner_documents(self):
        self.client.force_authenticate(self.partner_user)
        for document_type in ('PARTNER_PROFILE_PHOTO', 'DRIVING_LICENSE'):
            response = self.post_partner_doc(document_type)
            self.assertEqual(response.status_code, 201, response.data)

    def test_merchant_document_upload(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.post_merchant_doc('NATIONAL_ID')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['subject_type'], SUBJECT_MERCHANT)
        self.assertEqual(response.data['document_type'], 'NATIONAL_ID')
        self.assertIn('/api/v1/verifications/documents/', response.data['file_url'])
        self.assertNotIn('/media/', response.data['file_url'])
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.verification_status, 'SUBMITTED')

    def test_owner_downloads_own_verification_document(self):
        self.client.force_authenticate(self.merchant_user)
        upload_response = self.post_merchant_doc('NATIONAL_ID')

        response = self.client.get(upload_response.data['file_url'])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content)

    def test_another_user_denied_verification_document_download(self):
        self.client.force_authenticate(self.merchant_user)
        upload_response = self.post_merchant_doc('NATIONAL_ID')
        self.client.force_authenticate(self.other_user)

        response = self.client.get(upload_response.data['file_url'])

        self.assertEqual(response.status_code, 403)

    def test_raw_media_path_does_not_expose_verification_document(self):
        self.client.force_authenticate(self.merchant_user)
        upload_response = self.post_merchant_doc('NATIONAL_ID')
        document = VerificationDocument.objects.get(id=upload_response.data['id'])

        response = self.client.get(f'/media/{document.file.name}')

        self.assertEqual(response.status_code, 404)

    def test_partner_document_upload(self):
        self.client.force_authenticate(self.partner_user)

        response = self.post_partner_doc('DRIVING_LICENSE')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['subject_type'], SUBJECT_PARTNER)
        self.assertEqual(response.data['document_type'], 'DRIVING_LICENSE')
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.verification_status, 'SUBMITTED')

    def test_staff_document_upload(self):
        self.client.force_authenticate(self.staff_user)

        response = self.post_staff_doc('NATIONAL_ID')

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['subject_type'], SUBJECT_MERCHANT_STAFF)
        self.assertEqual(response.data['document_type'], 'NATIONAL_ID')
        self.staff_member.refresh_from_db()
        self.assertEqual(
            self.staff_member.verification_status,
            MerchantStaffMember.VERIFICATION_SUBMITTED,
        )

    def test_staff_document_belongs_to_correct_staff_member(self):
        other_staff_user = User.objects.create_user(
            username='verification-other-staff',
            password='test-password',
        )
        MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=other_staff_user,
            role=MerchantStaffMember.ROLE_VIEWER,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
        )
        self.client.force_authenticate(self.staff_user)
        upload_response = self.post_staff_doc('PASSPORT')
        self.assertEqual(upload_response.status_code, 201, upload_response.data)

        self.client.force_authenticate(other_staff_user)
        response = self.client.get('/api/v1/verifications/staff/documents/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])

    def test_market_document_requirements_control_staff_upload_types(self):
        VerificationDocumentRequirement.objects.create(
            market=self.market,
            subject_type=SUBJECT_MERCHANT_STAFF,
            document_type='PASSPORT',
            display_name='Passport',
            is_required=True,
            is_active=True,
        )
        self.client.force_authenticate(self.staff_user)

        rejected = self.post_staff_doc('NATIONAL_ID')
        accepted = self.post_staff_doc('PASSPORT')

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 201, accepted.data)

    def test_ownership_isolation(self):
        self.client.force_authenticate(self.merchant_user)
        self.post_merchant_doc('NATIONAL_ID')

        self.client.force_authenticate(self.other_user)
        response = self.client.get('/api/v1/verifications/merchant/documents/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])

    def test_invalid_document_type_is_rejected(self):
        self.client.force_authenticate(self.partner_user)

        response = self.post_partner_doc('RESTAURANT_PHOTO')

        self.assertEqual(response.status_code, 400)
        self.assertIn('document_type', response.data)

    def test_approval_blocked_when_merchant_documents_missing(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/merchants/{self.merchant.id}/status/',
            {'is_verified': True},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('documents', response.data)
        self.merchant.refresh_from_db()
        self.assertFalse(self.merchant.is_verified)

    def test_merchant_approval_works_when_required_documents_exist(self):
        self.add_required_merchant_documents()
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/merchants/{self.merchant.id}/status/',
            {'is_verified': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.merchant.refresh_from_db()
        self.restaurant.refresh_from_db()
        self.assertTrue(self.merchant.is_verified)
        self.assertTrue(self.restaurant.is_active)
        self.assertEqual(self.merchant.verification_status, VERIFICATION_APPROVED)

    def test_partner_approval_works_when_required_documents_exist(self):
        self.add_required_partner_documents()
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/partners/{self.partner.id}/status/',
            {'is_verified': True},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.partner.refresh_from_db()
        self.assertTrue(self.partner.is_verified)
        self.assertTrue(self.partner.is_available)
        self.assertEqual(self.partner.verification_status, VERIFICATION_APPROVED)

    def test_partner_approval_blocked_when_documents_missing(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/partners/{self.partner.id}/status/',
            {'is_verified': True},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('documents', response.data)
        self.partner.refresh_from_db()
        self.assertFalse(self.partner.is_verified)

    def test_operations_can_approve_staff_when_required_documents_exist(self):
        self.client.force_authenticate(self.staff_user)
        upload_response = self.post_staff_doc('NATIONAL_ID')
        self.assertEqual(upload_response.status_code, 201, upload_response.data)
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff_member.id}/status/',
            {'action': 'APPROVE'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.staff_member.refresh_from_db()
        self.assertEqual(
            self.staff_member.verification_status,
            MerchantStaffMember.VERIFICATION_VERIFIED,
        )
        self.assertEqual(
            VerificationDocument.objects.get(id=upload_response.data['id']).status,
            'APPROVED',
        )

    def test_operations_can_reject_staff(self):
        self.client.force_authenticate(self.staff_user)
        upload_response = self.post_staff_doc('NATIONAL_ID')
        self.assertEqual(upload_response.status_code, 201, upload_response.data)
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff_member.id}/status/',
            {'action': 'REJECT', 'rejection_reason': 'Document is unreadable.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.staff_member.refresh_from_db()
        self.assertEqual(
            self.staff_member.verification_status,
            MerchantStaffMember.VERIFICATION_REJECTED,
        )
        self.assertEqual(
            self.staff_member.verification_rejection_reason,
            'Document is unreadable.',
        )

    def test_merchant_cannot_approve_staff(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff_member.id}/status/',
            {'action': 'APPROVE'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.staff_member.refresh_from_db()
        self.assertEqual(
            self.staff_member.verification_status,
            MerchantStaffMember.VERIFICATION_PENDING,
        )

    def test_merchant_cannot_change_staff_verification_status(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff_member.id}/status/',
            {
                'action': 'REJECT',
                'rejection_reason': 'Merchant should not be able to reject.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.staff_member.refresh_from_db()
        self.assertEqual(
            self.staff_member.verification_status,
            MerchantStaffMember.VERIFICATION_PENDING,
        )

    def test_rejection_reason_is_saved(self):
        self.add_required_partner_documents()
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/partners/{self.partner.id}/status/',
            {'is_verified': False, 'rejection_reason': 'License photo is blurry.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.partner.refresh_from_db()
        self.assertFalse(self.partner.is_verified)
        self.assertEqual(self.partner.verification_status, VERIFICATION_REJECTED)
        self.assertEqual(
            self.partner.verification_rejection_reason,
            'License photo is blurry.',
        )

    def test_operations_can_review_individual_document(self):
        self.client.force_authenticate(self.merchant_user)
        upload_response = self.post_merchant_doc('NATIONAL_ID')
        document_id = upload_response.data['id']
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/verification-documents/{document_id}/review/',
            {'status': 'REJECTED', 'rejection_reason': 'Wrong side uploaded.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        document = VerificationDocument.objects.get(id=document_id)
        self.assertEqual(document.status, 'REJECTED')
        self.assertEqual(document.rejection_reason, 'Wrong side uploaded.')
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.verification_status, VERIFICATION_REJECTED)
