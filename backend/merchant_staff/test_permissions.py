from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from restaurants.models import MerchantProfile, Restaurant

from .models import MerchantStaffBranchAccess, MerchantStaffMember
from .permissions import (
    ALL_PERMISSIONS,
    MANAGE_BRANCHES,
    MANAGE_FINANCE,
    MANAGE_MENU,
    MANAGE_RIDERS,
    MANAGE_STAFF,
    MANAGE_SUPPORT,
    READ_ONLY_PERMISSIONS,
    ROLE_PERMISSION_MATRIX,
    UPDATE_ORDER_STATUS,
    VIEW_ANALYTICS,
    VIEW_FINANCE,
    VIEW_FULFILLMENT,
    VIEW_LEDGER,
    VIEW_ORDERS,
    VIEW_PAYMENTS,
    VIEW_PAYOUTS,
    VIEW_SUPPORT,
    can_access_branch,
    filter_queryset_for_actor,
    get_merchant_actor,
    permitted_branch_ids,
)


class MerchantStaffPermissionServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='permission-owner',
            email='owner@example.com',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Permission Company',
            is_verified=True,
        )
        self.branch_a = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Permission Branch A',
            rest_email='permission-a@example.com',
            rest_contact='9000000101',
            rest_address='A Road',
            rest_city='City',
            is_active=True,
            is_open=True,
        )
        self.branch_b = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Permission Branch B',
            rest_email='permission-b@example.com',
            rest_contact='9000000102',
            rest_address='B Road',
            rest_city='City',
            is_active=True,
            is_open=True,
        )
        self.other_owner = User.objects.create_user(username='permission-other-owner')
        self.other_merchant = MerchantProfile.objects.create(
            user=self.other_owner,
            business_name='Other Permission Company',
            is_verified=True,
        )
        self.other_branch = Restaurant.objects.create(
            owner=self.other_owner,
            rest_name='Other Permission Branch',
            rest_email='permission-other@example.com',
            rest_contact='9000000103',
            rest_address='Other Road',
            rest_city='Other City',
            is_active=True,
            is_open=True,
        )

    def create_staff(self, role, **overrides):
        user = overrides.pop('user', None) or User.objects.create_user(
            username=f'permission-{role.lower()}-{User.objects.count()}',
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
        return MerchantStaffMember.objects.create(**defaults)

    def grant_branch(self, staff, branch):
        return MerchantStaffBranchAccess.objects.create(
            staff_member=staff,
            branch=branch,
            created_by=self.owner,
        )

    def test_owner_gets_full_access(self):
        actor = get_merchant_actor(self.owner)

        self.assertTrue(actor.is_owner)
        self.assertFalse(actor.is_staff)
        self.assertEqual(actor.merchant, self.merchant)
        self.assertEqual(actor.role, MerchantStaffMember.ROLE_OWNER)
        self.assertEqual(actor.permissions, ALL_PERMISSIONS)
        self.assertEqual(
            set(permitted_branch_ids(actor)),
            {self.branch_a.id, self.branch_b.id},
        )
        self.assertTrue(can_access_branch(actor, self.branch_a))
        self.assertFalse(can_access_branch(actor, self.other_branch))

    def test_verified_active_admin_gets_permissions(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_ADMIN,
            is_company_wide=True,
        )

        actor = get_merchant_actor(staff.user)

        self.assertTrue(actor.is_staff)
        self.assertFalse(actor.is_owner)
        self.assertEqual(actor.merchant, self.merchant)
        self.assertIn(MANAGE_STAFF, actor.permissions)
        self.assertIn(MANAGE_MENU, actor.permissions)
        self.assertIn(VIEW_FINANCE, actor.permissions)
        self.assertNotIn(MANAGE_FINANCE, actor.permissions)

    def test_unverified_staff_gets_no_operational_permissions(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_ADMIN,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
        )
        self.grant_branch(staff, self.branch_a)

        actor = get_merchant_actor(staff.user)

        self.assertTrue(actor.is_staff)
        self.assertEqual(actor.permissions, frozenset())
        self.assertEqual(actor.branch_ids, tuple())

    def test_rejected_staff_gets_no_operational_permissions(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_BRANCH_MANAGER,
            membership_status=MerchantStaffMember.STATUS_INACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_REJECTED,
        )
        self.grant_branch(staff, self.branch_a)

        actor = get_merchant_actor(staff.user)

        self.assertEqual(actor.permissions, frozenset())
        self.assertFalse(can_access_branch(actor, self.branch_a))

    def test_suspended_staff_gets_no_operational_permissions(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_FINANCE_STAFF,
            membership_status=MerchantStaffMember.STATUS_INACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_SUSPENDED,
        )

        actor = get_merchant_actor(staff.user)

        self.assertEqual(actor.permissions, frozenset())

    def test_removed_staff_gets_no_operational_permissions(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_VIEWER,
            membership_status=MerchantStaffMember.STATUS_REMOVED,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
        )

        actor = get_merchant_actor(staff.user)

        self.assertFalse(actor.is_staff)
        self.assertIsNone(actor.merchant)
        self.assertEqual(actor.permissions, frozenset())

    def test_inactive_user_gets_no_operational_permissions(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_ADMIN)
        staff.user.is_active = False
        staff.user.save(update_fields=('is_active',))

        actor = get_merchant_actor(staff.user)

        self.assertFalse(actor.is_staff)
        self.assertEqual(actor.permissions, frozenset())

    def test_branch_manager_limited_to_assigned_branch(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_BRANCH_MANAGER)
        self.grant_branch(staff, self.branch_a)

        actor = get_merchant_actor(staff.user)

        self.assertEqual(actor.branch_ids, (self.branch_a.id,))
        self.assertTrue(can_access_branch(actor, self.branch_a))
        self.assertFalse(can_access_branch(actor, self.branch_b))
        self.assertFalse(can_access_branch(actor, self.other_branch))
        self.assertIn(MANAGE_BRANCHES, actor.permissions)
        self.assertIn(VIEW_ANALYTICS, actor.permissions)

    def test_company_wide_staff_can_access_all_merchant_branches(self):
        staff = self.create_staff(
            MerchantStaffMember.ROLE_CUSTOMER_SUPPORT,
            is_company_wide=True,
        )

        actor = get_merchant_actor(staff.user)

        self.assertEqual(
            set(actor.branch_ids),
            {self.branch_a.id, self.branch_b.id},
        )
        self.assertTrue(can_access_branch(actor, self.branch_a))
        self.assertTrue(can_access_branch(actor, self.branch_b))
        self.assertFalse(can_access_branch(actor, self.other_branch))

    def test_filter_queryset_for_actor_limits_branch_records(self):
        staff = self.create_staff(MerchantStaffMember.ROLE_BRANCH_MANAGER)
        self.grant_branch(staff, self.branch_a)
        actor = get_merchant_actor(staff.user)

        branches = filter_queryset_for_actor(Restaurant.objects.all(), actor, 'id')

        self.assertEqual(list(branches), [self.branch_a])

    def test_filter_queryset_for_actor_returns_none_without_access(self):
        actor = get_merchant_actor(AnonymousUser())

        branches = filter_queryset_for_actor(Restaurant.objects.all(), actor, 'id')

        self.assertEqual(list(branches), [])

    def test_role_permission_matrix(self):
        expected = {
            MerchantStaffMember.ROLE_OWNER: ALL_PERMISSIONS,
            MerchantStaffMember.ROLE_ADMIN: {
                MANAGE_BRANCHES,
                MANAGE_MENU,
                VIEW_ORDERS,
                UPDATE_ORDER_STATUS,
                VIEW_PAYMENTS,
                VIEW_PAYOUTS,
                MANAGE_RIDERS,
                MANAGE_STAFF,
                VIEW_ANALYTICS,
                MANAGE_SUPPORT,
                VIEW_SUPPORT,
                VIEW_FULFILLMENT,
                MANAGE_SUPPORT,
                VIEW_FINANCE,
            },
            MerchantStaffMember.ROLE_BRANCH_MANAGER: {
                MANAGE_BRANCHES,
                MANAGE_MENU,
                VIEW_ORDERS,
                UPDATE_ORDER_STATUS,
                VIEW_PAYMENTS,
                MANAGE_RIDERS,
                VIEW_ANALYTICS,
                VIEW_SUPPORT,
                VIEW_FULFILLMENT,
            },
            MerchantStaffMember.ROLE_KITCHEN_STAFF: {
                VIEW_ORDERS,
                UPDATE_ORDER_STATUS,
            },
            MerchantStaffMember.ROLE_CASHIER: {
                VIEW_ORDERS,
                VIEW_PAYMENTS,
            },
            MerchantStaffMember.ROLE_DISPATCHER: {
                VIEW_ORDERS,
                UPDATE_ORDER_STATUS,
                MANAGE_RIDERS,
                VIEW_FULFILLMENT,
            },
            MerchantStaffMember.ROLE_CUSTOMER_SUPPORT: {
                VIEW_ORDERS,
                VIEW_SUPPORT,
                MANAGE_SUPPORT,
                VIEW_FULFILLMENT,
            },
            MerchantStaffMember.ROLE_FINANCE_STAFF: {
                VIEW_PAYMENTS,
                VIEW_PAYOUTS,
                VIEW_LEDGER,
                VIEW_FINANCE,
            },
            MerchantStaffMember.ROLE_VIEWER: READ_ONLY_PERMISSIONS,
        }

        for role, minimum_permissions in expected.items():
            with self.subTest(role=role):
                self.assertTrue(
                    set(minimum_permissions).issubset(
                        set(ROLE_PERMISSION_MATRIX[role])
                    )
                )

    def test_each_role_actor_gets_matrix_permissions(self):
        for role in dict(MerchantStaffMember.ROLE_CHOICES):
            if role == MerchantStaffMember.ROLE_OWNER:
                continue
            with self.subTest(role=role):
                staff = self.create_staff(role)
                self.grant_branch(staff, self.branch_a)

                actor = get_merchant_actor(staff.user)

                self.assertEqual(actor.permissions, ROLE_PERMISSION_MATRIX[role])
