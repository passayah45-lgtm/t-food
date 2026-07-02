from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from merchant_staff.permissions import (
    ALL_PERMISSIONS,
    ROLE_PERMISSION_MATRIX,
)
from restaurants.models import MerchantProfile, Restaurant


TEST_REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {},
}


@override_settings(REST_FRAMEWORK=TEST_REST_FRAMEWORK)
class MerchantStaffAuthContextTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='auth-owner',
            email='auth-owner@example.com',
            password='test-password',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Auth Merchant',
            is_verified=True,
        )
        self.branch_a = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Auth Branch A',
            rest_email='auth-a@example.com',
            rest_contact='9000000401',
            rest_address='A Road',
            rest_city='Bhubaneswar',
            is_active=True,
        )
        self.branch_b = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Auth Branch B',
            rest_email='auth-b@example.com',
            rest_contact='9000000402',
            rest_address='B Road',
            rest_city='Bhubaneswar',
            is_active=True,
        )

    def login(self, username, password='test-password'):
        return self.client.post(
            '/api/v1/auth/login/',
            {'username': username, 'password': password},
            format='json',
        )

    def create_staff(self, role, **overrides):
        user = overrides.pop('user', None) or User.objects.create_user(
            username=f'auth-{role.lower()}-{User.objects.count()}',
            email=f'{role.lower()}@example.com',
            password='test-password',
        )
        defaults = {
            'merchant': self.merchant,
            'user': user,
            'role': role,
            'membership_status': MerchantStaffMember.STATUS_ACTIVE,
            'verification_status': MerchantStaffMember.VERIFICATION_VERIFIED,
            'is_company_wide': False,
            'created_by': self.owner,
        }
        defaults.update(overrides)
        staff = MerchantStaffMember.objects.create(**defaults)
        return staff

    def test_owner_login_unchanged_and_includes_owner_context(self):
        response = self.login('auth-owner')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['role'], 'merchant')
        self.assertTrue(response.data['is_merchant_owner'])
        self.assertFalse(response.data['is_merchant_staff'])
        self.assertEqual(response.data['merchant_id'], self.merchant.id)
        self.assertIsNone(response.data['staff_member_id'])
        self.assertEqual(
            set(response.data['branch_ids']),
            {self.branch_a.id, self.branch_b.id},
        )
        self.assertEqual(set(response.data['permissions']), set(ALL_PERMISSIONS))

    def test_verified_active_staff_login_includes_staff_context(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_BRANCH_MANAGER)
        MerchantStaffBranchAccess.objects.create(
            staff_member=staff,
            branch=self.branch_a,
            created_by=self.owner,
        )

        response = self.login(staff.user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data['is_merchant_owner'])
        self.assertTrue(response.data['is_merchant_staff'])
        self.assertEqual(response.data['merchant_id'], self.merchant.id)
        self.assertEqual(response.data['staff_member_id'], staff.id)
        self.assertEqual(response.data['staff_role'], staff.role)
        self.assertEqual(
            response.data['membership_status'],
            MerchantStaffMember.STATUS_ACTIVE,
        )
        self.assertEqual(
            response.data['verification_status'],
            MerchantStaffMember.VERIFICATION_VERIFIED,
        )
        self.assertEqual(response.data['branch_ids'], [self.branch_a.id])
        self.assertEqual(
            set(response.data['permissions']),
            set(ROLE_PERMISSION_MATRIX[staff.role]),
        )

    def test_unverified_staff_login_has_no_operational_permissions(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_ADMIN,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
        )

        response = self.login(staff.user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data['is_merchant_staff'])
        self.assertIsNone(response.data['merchant_id'])
        self.assertIsNone(response.data['staff_member_id'])
        self.assertEqual(response.data['branch_ids'], [])
        self.assertEqual(response.data['permissions'], [])
        self.assertEqual(
            response.data['membership_status'],
            MerchantStaffMember.STATUS_PENDING_VERIFICATION,
        )
        self.assertEqual(
            response.data['verification_status'],
            MerchantStaffMember.VERIFICATION_SUBMITTED,
        )

    def test_rejected_suspended_and_removed_staff_have_no_staff_context(self):
        cases = [
            (
                MerchantStaffMember.STATUS_INACTIVE,
                MerchantStaffMember.VERIFICATION_REJECTED,
            ),
            (
                MerchantStaffMember.STATUS_INACTIVE,
                MerchantStaffMember.VERIFICATION_SUSPENDED,
            ),
            (
                MerchantStaffMember.STATUS_REMOVED,
                MerchantStaffMember.VERIFICATION_VERIFIED,
            ),
        ]
        for membership_status, verification_status in cases:
            with self.subTest(
                membership_status=membership_status,
                verification_status=verification_status,
            ):
                staff = self.create_staff(
                    MerchantStaffMember.ROLE_VIEWER,
                    membership_status=membership_status,
                    verification_status=verification_status,
                )

                response = self.login(staff.user.username)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertFalse(response.data['is_merchant_staff'])
                self.assertIsNone(response.data['merchant_id'])
                self.assertEqual(response.data['permissions'], [])

    def test_inactive_user_cannot_authenticate(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_ADMIN)
        staff.user.is_active = False
        staff.user.save(update_fields=('is_active',))

        response = self.login(staff.user.username)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_company_wide_staff_gets_all_merchant_branch_ids(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_CUSTOMER_SUPPORT,
            is_company_wide=True,
        )

        response = self.login(staff.user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_merchant_staff'])
        self.assertTrue(response.data['is_company_wide'])
        self.assertEqual(
            set(response.data['branch_ids']),
            {self.branch_a.id, self.branch_b.id},
        )

    def test_verification_document_details_are_not_leaked(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_CASHIER)
        response = self.login(staff.user.username)

        response_text = str(response.data).lower()
        self.assertNotIn('documents', response.data)
        self.assertNotIn('file_url', response_text)
        self.assertNotIn('rejection_reason', response_text)

    def test_me_endpoint_includes_same_context(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_CASHIER)
        login = self.login(staff.user.username)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )

        response = self.client.get('/api/v1/auth/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_merchant_staff'])
        self.assertEqual(response.data['staff_member_id'], staff.id)
