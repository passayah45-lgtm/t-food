import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from markets.models import Currency, Market
from merchant_staff.models import (
    MerchantStaffBranchAccess,
    MerchantStaffMember,
)
from restaurants.models import MerchantProfile, Restaurant
from verifications.constants import SUBJECT_MERCHANT_STAFF
from verifications.models import VerificationDocument


TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_PRIVATE_MEDIA_ROOT = tempfile.mkdtemp()


def upload(name='document.jpg', content=None):
    if content is None:
        buffer = BytesIO()
        Image.new('RGB', (2, 2), color=(255, 122, 0)).save(buffer, format='JPEG')
        content = buffer.getvalue()
    return SimpleUploadedFile(name, content, content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class OperationsStaffApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='ops-staff-admin',
            password='test-password',
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='ops-staff-owner',
            email='ops-staff-owner@example.com',
        )
        self.currency = Currency.objects.create(
            code='GNF',
            numeric_code='324',
            name='Guinean Franc',
            symbol='GNF',
            minor_unit=0,
        )
        self.market = Market.objects.create(
            slug='guinea-ops-staff',
            name='Guinea Ops Staff',
            country_code='GN',
            default_currency=self.currency,
            timezone='Africa/Conakry',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Ops Staff Company',
            market=self.market,
            is_verified=True,
        )
        self.branch = Restaurant.objects.create(
            market=self.market,
            owner=self.owner,
            rest_name='Ops Staff Branch',
            branch_name='Ops Staff Branch',
            country_code='GN',
            rest_email='ops-staff-branch@example.com',
            rest_contact='9000000301',
            rest_address='Main Road',
            rest_city='Conakry',
            is_active=True,
        )
        self.staff_user = User.objects.create_user(
            username='ops-staff-member',
            email='ops-staff-member@example.com',
            first_name='Ops',
            last_name='Staff',
        )
        self.staff = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=self.staff_user,
            role=MerchantStaffMember.ROLE_BRANCH_MANAGER,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
            verification_submitted_at='2026-01-01T00:00:00Z',
            created_by=self.owner,
        )
        MerchantStaffBranchAccess.objects.create(
            staff_member=self.staff,
            branch=self.branch,
            created_by=self.owner,
        )
        self.document = VerificationDocument.objects.create(
            user=self.staff_user,
            subject_type=SUBJECT_MERCHANT_STAFF,
            document_type='NATIONAL_ID',
            file=upload('national-id.jpg'),
        )
        self.customer = User.objects.create_user(username='ops-staff-customer')

    def test_operations_can_list_staff(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/v1/operations/staff/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row['id'], self.staff.id)
        self.assertEqual(row['merchant_company']['id'], self.merchant.id)
        self.assertEqual(row['user']['id'], self.staff_user.id)
        self.assertEqual(row['name'], 'Ops Staff')
        self.assertEqual(row['email'], self.staff_user.email)
        self.assertIn('assigned_branches', row)

    def test_non_operations_denied(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get('/api/v1/operations/staff/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filters_work(self):
        other_user = User.objects.create_user(username='ops-staff-other')
        other_staff = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=other_user,
            role=MerchantStaffMember.ROLE_FINANCE_STAFF,
            membership_status=MerchantStaffMember.STATUS_INACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_REJECTED,
            created_by=self.owner,
        )
        self.client.force_authenticate(self.admin)

        by_role = self.client.get(
            f'/api/v1/operations/staff/?role={self.staff.role}'
        )
        by_membership = self.client.get(
            '/api/v1/operations/staff/?membership_status=INACTIVE'
        )
        by_verification = self.client.get(
            '/api/v1/operations/staff/?verification_status=REJECTED'
        )
        by_branch = self.client.get(
            f'/api/v1/operations/staff/?branch_id={self.branch.id}'
        )
        by_country = self.client.get('/api/v1/operations/staff/?country_code=GN')
        by_market = self.client.get(
            f'/api/v1/operations/staff/?market={self.market.slug}'
        )
        by_merchant = self.client.get(
            f'/api/v1/operations/staff/?merchant_id={self.merchant.id}'
        )

        self.assertEqual([row['id'] for row in by_role.data], [self.staff.id])
        self.assertEqual([row['id'] for row in by_membership.data], [other_staff.id])
        self.assertEqual([row['id'] for row in by_verification.data], [other_staff.id])
        self.assertEqual([row['id'] for row in by_branch.data], [self.staff.id])
        self.assertEqual(len(by_country.data), 2)
        self.assertEqual(len(by_market.data), 2)
        self.assertEqual(len(by_merchant.data), 2)

    def test_operations_can_approve_staff_without_auto_activation(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff.id}/verification/',
            {'action': 'APPROVE'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_VERIFIED,
        )
        self.assertEqual(
            self.staff.membership_status,
            MerchantStaffMember.STATUS_PENDING_VERIFICATION,
        )
        self.assertEqual(self.staff.verification_reviewed_by, self.admin)
        self.assertIsNotNone(self.staff.verification_reviewed_at)

    def test_operations_can_reject_staff_with_reason(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff.id}/verification/',
            {'action': 'REJECT', 'rejection_reason': 'ID photo is blurry.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_REJECTED,
        )
        self.assertEqual(self.staff.verification_rejection_reason, 'ID photo is blurry.')

    def test_reject_requires_reason(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff.id}/verification/',
            {'action': 'REJECT'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rejection_reason', response.data)

    def test_operations_can_suspend_staff_with_reason_and_deactivate(self):
        self.staff.verification_status = MerchantStaffMember.VERIFICATION_VERIFIED
        self.staff.membership_status = MerchantStaffMember.STATUS_ACTIVE
        self.staff.save(update_fields=('verification_status', 'membership_status'))
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff.id}/verification/',
            {'action': 'SUSPEND', 'rejection_reason': 'Investigation required.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_SUSPENDED,
        )
        self.assertEqual(
            self.staff.membership_status,
            MerchantStaffMember.STATUS_INACTIVE,
        )

    def test_operations_can_request_more_info(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/{self.staff.id}/verification/',
            {
                'action': 'REQUEST_MORE_INFO',
                'rejection_reason': 'Upload the back side of your ID.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_MORE_INFO_REQUIRED,
        )

    def test_merchant_cannot_approve_staff_or_access_queue(self):
        self.client.force_authenticate(self.owner)

        queue = self.client.get('/api/v1/operations/staff/')
        approve = self.client.patch(
            f'/api/v1/operations/staff/{self.staff.id}/verification/',
            {'action': 'APPROVE'},
            format='json',
        )

        self.assertEqual(queue.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(approve.status_code, status.HTTP_403_FORBIDDEN)
        self.staff.refresh_from_db()
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_SUBMITTED,
        )

    def test_document_list_works(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            f'/api/v1/operations/staff/{self.staff.id}/documents/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['document_count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.document.id)

    def test_staff_document_review_alias_works(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/v1/operations/staff/documents/{self.document.id}/review/',
            {'action': 'REJECT_DOCUMENT', 'rejection_reason': 'Wrong document.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.document.refresh_from_db()
        self.staff.refresh_from_db()
        self.assertEqual(self.document.status, 'REJECTED')
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_REJECTED,
        )
