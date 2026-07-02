from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from merchant_staff.models import (
    MerchantStaffBranchAccess,
    MerchantStaffInvite,
    MerchantStaffMember,
)
from restaurants.models import MerchantProfile, Restaurant


class MerchantStaffApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='staff-api-owner',
            email='staff-api-owner@example.com',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Staff API Company',
            phone='9000000201',
            is_verified=True,
        )
        self.branch = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Staff API Branch',
            branch_name='Staff API Branch',
            rest_email='staff-api-branch@example.com',
            rest_contact='9000000202',
            rest_address='Main Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.second_branch = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Staff API Second Branch',
            branch_name='Staff API Second Branch',
            rest_email='staff-api-second-branch@example.com',
            rest_contact='9000000203',
            rest_address='Second Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.other_owner = User.objects.create_user(
            username='staff-api-other-owner',
            email='staff-api-other-owner@example.com',
        )
        self.other_merchant = MerchantProfile.objects.create(
            user=self.other_owner,
            business_name='Other Staff API Company',
            is_verified=True,
        )
        self.other_branch = Restaurant.objects.create(
            owner=self.other_owner,
            rest_name='Other Staff API Branch',
            rest_email='other-staff-api-branch@example.com',
            rest_contact='9000000204',
            rest_address='Other Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.staff_user = User.objects.create_user(
            username='staff-api-member',
            email='staff-api-member@example.com',
            first_name='Staff',
            last_name='Member',
        )
        self.staff = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=self.staff_user,
            role=MerchantStaffMember.ROLE_VIEWER,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
            created_by=self.owner,
        )
        self.verified_staff_user = User.objects.create_user(
            username='staff-api-verified-member',
            email='staff-api-verified@example.com',
        )
        self.verified_staff = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=self.verified_staff_user,
            role=MerchantStaffMember.ROLE_CASHIER,
            membership_status=MerchantStaffMember.STATUS_INACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            created_by=self.owner,
        )
        self.customer = User.objects.create_user(username='staff-api-customer')

    def test_owner_can_list_staff(self):
        MerchantStaffBranchAccess.objects.create(
            staff_member=self.staff,
            branch=self.branch,
            created_by=self.owner,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.get('/api/v1/merchants/staff/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        first = response.data['results'][0]
        self.assertIn('verification_status', first)
        self.assertIn('assigned_branches', first)
        self.assertIn('phone', first)

    def test_owner_can_create_invite_and_token_is_returned(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            '/api/v1/merchants/staff/invite/',
            {
                'name': 'Future Staff',
                'email': 'future-staff@example.com',
                'phone': '9000000205',
                'role': MerchantStaffMember.ROLE_KITCHEN_STAFF,
                'is_company_wide': False,
                'branch_ids': [self.branch.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data['invite_token'])
        invite = MerchantStaffInvite.objects.get(id=response.data['id'])
        self.assertEqual(invite.merchant, self.merchant)
        self.assertEqual(invite.invited_by, self.owner)
        self.assertEqual(list(invite.branches.all()), [self.branch])

    def test_owner_can_update_role(self):
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            f'/api/v1/merchants/staff/{self.staff.id}/',
            {'role': MerchantStaffMember.ROLE_BRANCH_MANAGER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, MerchantStaffMember.ROLE_BRANCH_MANAGER)

    def test_owner_cannot_change_verification_status(self):
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            f'/api/v1/merchants/staff/{self.staff.id}/',
            {'verification_status': MerchantStaffMember.VERIFICATION_VERIFIED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.staff.refresh_from_db()
        self.assertEqual(
            self.staff.verification_status,
            MerchantStaffMember.VERIFICATION_SUBMITTED,
        )

    def test_owner_cannot_activate_unverified_staff(self):
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            f'/api/v1/merchants/staff/{self.staff.id}/',
            {'membership_status': MerchantStaffMember.STATUS_ACTIVE},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('membership_status', response.data)

    def test_owner_can_activate_verified_staff(self):
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            f'/api/v1/merchants/staff/{self.verified_staff.id}/',
            {'membership_status': MerchantStaffMember.STATUS_ACTIVE},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.verified_staff.refresh_from_db()
        self.assertEqual(
            self.verified_staff.membership_status,
            MerchantStaffMember.STATUS_ACTIVE,
        )

    def test_owner_can_deactivate_and_remove_staff(self):
        self.verified_staff.membership_status = MerchantStaffMember.STATUS_ACTIVE
        self.verified_staff.save(update_fields=('membership_status',))
        self.client.force_authenticate(self.owner)

        inactive = self.client.patch(
            f'/api/v1/merchants/staff/{self.verified_staff.id}/',
            {'membership_status': MerchantStaffMember.STATUS_INACTIVE},
            format='json',
        )
        removed = self.client.patch(
            f'/api/v1/merchants/staff/{self.verified_staff.id}/',
            {'membership_status': MerchantStaffMember.STATUS_REMOVED},
            format='json',
        )

        self.assertEqual(inactive.status_code, status.HTTP_200_OK)
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.verified_staff.refresh_from_db()
        self.assertEqual(
            self.verified_staff.membership_status,
            MerchantStaffMember.STATUS_REMOVED,
        )

    def test_owner_can_assign_merchant_owned_branches(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f'/api/v1/merchants/staff/{self.staff.id}/branches/',
            {'branch_ids': [self.branch.id, self.second_branch.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            set(self.staff.branch_access.values_list('branch_id', flat=True)),
            {self.branch.id, self.second_branch.id},
        )

    def test_owner_cannot_assign_another_merchant_branch(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f'/api/v1/merchants/staff/{self.staff.id}/branches/',
            {'branch_ids': [self.other_branch.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_cannot_assign_inactive_branch(self):
        self.branch.is_active = False
        self.branch.save(update_fields=('is_active',))
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f'/api/v1/merchants/staff/{self.staff.id}/branches/',
            {'branch_ids': [self.branch.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removed_staff_cannot_receive_branch_access(self):
        self.staff.membership_status = MerchantStaffMember.STATUS_REMOVED
        self.staff.save(update_fields=('membership_status',))
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            f'/api/v1/merchants/staff/{self.staff.id}/branches/',
            {'branch_ids': [self.branch.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Removed staff', response.data['detail'])

    def test_owner_can_remove_branch_access(self):
        MerchantStaffBranchAccess.objects.create(
            staff_member=self.staff,
            branch=self.branch,
            created_by=self.owner,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.delete(
            f'/api/v1/merchants/staff/{self.staff.id}/branches/{self.branch.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.staff.branch_access.filter(branch=self.branch).exists())

    def test_non_owner_denied(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/merchants/staff/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_cannot_manage_staff_in_this_slice(self):
        self.client.force_authenticate(self.staff_user)

        response = self.client.get('/api/v1/merchants/staff/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_existing_owner_merchant_apis_still_work(self):
        self.client.force_authenticate(self.owner)

        profile = self.client.get('/api/v1/merchants/profile/')
        restaurants = self.client.get('/api/v1/merchants/restaurants/')

        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(restaurants.status_code, status.HTTP_200_OK)
