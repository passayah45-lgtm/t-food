from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from restaurants.models import MerchantProfile, Restaurant

from .models import (
    MerchantStaffBranchAccess,
    MerchantStaffInvite,
    MerchantStaffMember,
)


class MerchantStaffModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='staff-owner',
            email='owner@example.com',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Staff Test Company',
            is_verified=True,
        )
        self.branch = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Staff Branch',
            rest_email='staff-branch@example.com',
            rest_contact='9000000001',
            rest_address='Main Road',
            rest_city='Test City',
            is_active=True,
            is_open=True,
        )
        self.other_owner = User.objects.create_user(username='other-staff-owner')
        self.other_merchant = MerchantProfile.objects.create(
            user=self.other_owner,
            business_name='Other Staff Company',
            is_verified=True,
        )
        self.other_branch = Restaurant.objects.create(
            owner=self.other_owner,
            rest_name='Other Staff Branch',
            rest_email='other-staff-branch@example.com',
            rest_contact='9000000002',
            rest_address='Other Road',
            rest_city='Other City',
            is_active=True,
            is_open=True,
        )
        self.staff_user = User.objects.create_user(
            username='merchant-staff-user',
            email='staff@example.com',
        )

    def create_staff(self, **overrides):
        defaults = {
            'merchant': self.merchant,
            'user': self.staff_user,
            'role': MerchantStaffMember.ROLE_BRANCH_MANAGER,
            'membership_status': MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            'verification_status': MerchantStaffMember.VERIFICATION_PENDING,
            'created_by': self.owner,
        }
        defaults.update(overrides)
        return MerchantStaffMember.objects.create(**defaults)

    def test_create_staff_member(self):
        staff = self.create_staff()

        self.assertEqual(staff.merchant, self.merchant)
        self.assertEqual(staff.user, self.staff_user)
        self.assertEqual(staff.role, MerchantStaffMember.ROLE_BRANCH_MANAGER)
        self.assertEqual(
            staff.membership_status,
            MerchantStaffMember.STATUS_PENDING_VERIFICATION,
        )
        self.assertEqual(
            staff.verification_status,
            MerchantStaffMember.VERIFICATION_PENDING,
        )

    def test_duplicate_current_merchant_staff_membership_prevented(self):
        self.create_staff()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_staff(role=MerchantStaffMember.ROLE_VIEWER)

    def test_removed_staff_allows_new_membership(self):
        staff = self.create_staff(
            membership_status=MerchantStaffMember.STATUS_REMOVED,
        )
        self.assertEqual(staff.membership_status, MerchantStaffMember.STATUS_REMOVED)

        replacement = self.create_staff(role=MerchantStaffMember.ROLE_VIEWER)

        self.assertEqual(replacement.role, MerchantStaffMember.ROLE_VIEWER)

    def test_active_blocked_when_verification_status_is_not_verified(self):
        staff = MerchantStaffMember(
            merchant=self.merchant,
            user=self.staff_user,
            role=MerchantStaffMember.ROLE_CASHIER,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            staff.full_clean()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MerchantStaffMember.objects.create(
                    merchant=self.merchant,
                    user=self.staff_user,
                    role=MerchantStaffMember.ROLE_CASHIER,
                    membership_status=MerchantStaffMember.STATUS_ACTIVE,
                    verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
                    created_by=self.owner,
                )

    def test_active_allowed_when_verification_status_is_verified(self):
        staff = self.create_staff(
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
        )

        self.assertEqual(staff.membership_status, MerchantStaffMember.STATUS_ACTIVE)
        self.assertEqual(
            staff.verification_status,
            MerchantStaffMember.VERIFICATION_VERIFIED,
        )

    def test_branch_access_allowed_for_merchant_owned_branch(self):
        staff = self.create_staff()
        access = MerchantStaffBranchAccess(
            staff_member=staff,
            branch=self.branch,
            created_by=self.owner,
        )

        access.full_clean()
        access.save()

        self.assertEqual(access.branch, self.branch)

    def test_branch_access_blocked_for_another_merchant_branch(self):
        staff = self.create_staff()
        access = MerchantStaffBranchAccess(
            staff_member=staff,
            branch=self.other_branch,
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_removed_staff_cannot_be_assigned_branch(self):
        staff = self.create_staff(
            membership_status=MerchantStaffMember.STATUS_REMOVED,
        )
        access = MerchantStaffBranchAccess(
            staff_member=staff,
            branch=self.branch,
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_duplicate_branch_access_prevented(self):
        staff = self.create_staff()
        MerchantStaffBranchAccess.objects.create(
            staff_member=staff,
            branch=self.branch,
            created_by=self.owner,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MerchantStaffBranchAccess.objects.create(
                    staff_member=staff,
                    branch=self.branch,
                    created_by=self.owner,
                )

    def test_invite_token_unique_and_invite_can_link_branches(self):
        invite = MerchantStaffInvite.objects.create(
            merchant=self.merchant,
            name='Future Staff',
            email='future@example.com',
            phone='9000000003',
            role=MerchantStaffMember.ROLE_KITCHEN_STAFF,
            invited_by=self.owner,
        )
        invite.branches.add(self.branch)

        self.assertTrue(invite.invite_token)
        self.assertEqual(invite.status, MerchantStaffInvite.STATUS_PENDING)
        self.assertEqual(list(invite.branches.all()), [self.branch])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MerchantStaffInvite.objects.create(
                    merchant=self.merchant,
                    name='Duplicate Token Staff',
                    email='duplicate@example.com',
                    role=MerchantStaffMember.ROLE_VIEWER,
                    invited_by=self.owner,
                    invite_token=invite.invite_token,
                )

    def test_invite_expiry_logic(self):
        active_invite = MerchantStaffInvite.objects.create(
            merchant=self.merchant,
            name='Active Invite',
            role=MerchantStaffMember.ROLE_VIEWER,
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=1),
        )
        expired_invite = MerchantStaffInvite.objects.create(
            merchant=self.merchant,
            name='Expired Invite',
            role=MerchantStaffMember.ROLE_VIEWER,
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        cancelled_invite = MerchantStaffInvite.objects.create(
            merchant=self.merchant,
            name='Cancelled Invite',
            role=MerchantStaffMember.ROLE_VIEWER,
            invited_by=self.owner,
            status=MerchantStaffInvite.STATUS_CANCELLED,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertFalse(active_invite.is_expired())
        self.assertTrue(expired_invite.is_expired())
        self.assertFalse(cancelled_invite.is_expired())
