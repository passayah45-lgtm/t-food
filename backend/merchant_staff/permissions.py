from dataclasses import dataclass, field

from restaurants.models import Restaurant

from .models import MerchantStaffMember


MANAGE_BRANCHES = 'MANAGE_BRANCHES'
VIEW_BRANCHES = 'VIEW_BRANCHES'
MANAGE_MENU = 'MANAGE_MENU'
VIEW_MENU = 'VIEW_MENU'
VIEW_ORDERS = 'VIEW_ORDERS'
UPDATE_ORDER_STATUS = 'UPDATE_ORDER_STATUS'
VIEW_PAYMENTS = 'VIEW_PAYMENTS'
VIEW_PAYOUTS = 'VIEW_PAYOUTS'
VIEW_LEDGER = 'VIEW_LEDGER'
MANAGE_RIDERS = 'MANAGE_RIDERS'
VIEW_RIDERS = 'VIEW_RIDERS'
MANAGE_STAFF = 'MANAGE_STAFF'
VIEW_ANALYTICS = 'VIEW_ANALYTICS'
MANAGE_SUPPORT = 'MANAGE_SUPPORT'
VIEW_SUPPORT = 'VIEW_SUPPORT'
VIEW_FULFILLMENT = 'VIEW_FULFILLMENT'
MANAGE_FULFILLMENT = 'MANAGE_FULFILLMENT'
VIEW_FINANCE = 'VIEW_FINANCE'
MANAGE_FINANCE = 'MANAGE_FINANCE'


ALL_PERMISSIONS = frozenset({
    MANAGE_BRANCHES,
    VIEW_BRANCHES,
    MANAGE_MENU,
    VIEW_MENU,
    VIEW_ORDERS,
    UPDATE_ORDER_STATUS,
    VIEW_PAYMENTS,
    VIEW_PAYOUTS,
    VIEW_LEDGER,
    MANAGE_RIDERS,
    VIEW_RIDERS,
    MANAGE_STAFF,
    VIEW_ANALYTICS,
    MANAGE_SUPPORT,
    VIEW_SUPPORT,
    VIEW_FULFILLMENT,
    MANAGE_FULFILLMENT,
    VIEW_FINANCE,
    MANAGE_FINANCE,
})

READ_ONLY_PERMISSIONS = frozenset({
    VIEW_BRANCHES,
    VIEW_MENU,
    VIEW_ORDERS,
    VIEW_PAYMENTS,
    VIEW_PAYOUTS,
    VIEW_LEDGER,
    VIEW_RIDERS,
    VIEW_ANALYTICS,
    VIEW_SUPPORT,
    VIEW_FULFILLMENT,
    VIEW_FINANCE,
})

ROLE_PERMISSION_MATRIX = {
    MerchantStaffMember.ROLE_OWNER: ALL_PERMISSIONS,
    MerchantStaffMember.ROLE_ADMIN: frozenset({
        MANAGE_BRANCHES,
        VIEW_BRANCHES,
        MANAGE_MENU,
        VIEW_MENU,
        VIEW_ORDERS,
        UPDATE_ORDER_STATUS,
        VIEW_PAYMENTS,
        VIEW_PAYOUTS,
        MANAGE_RIDERS,
        VIEW_RIDERS,
        MANAGE_STAFF,
        VIEW_ANALYTICS,
        MANAGE_SUPPORT,
        VIEW_SUPPORT,
        VIEW_FULFILLMENT,
        MANAGE_FULFILLMENT,
        VIEW_FINANCE,
    }),
    MerchantStaffMember.ROLE_BRANCH_MANAGER: frozenset({
        MANAGE_BRANCHES,
        VIEW_BRANCHES,
        MANAGE_MENU,
        VIEW_MENU,
        VIEW_ORDERS,
        UPDATE_ORDER_STATUS,
        VIEW_PAYMENTS,
        MANAGE_RIDERS,
        VIEW_RIDERS,
        VIEW_ANALYTICS,
        VIEW_SUPPORT,
        VIEW_FULFILLMENT,
        MANAGE_FULFILLMENT,
    }),
    MerchantStaffMember.ROLE_KITCHEN_STAFF: frozenset({
        VIEW_MENU,
        MANAGE_MENU,
        VIEW_ORDERS,
        UPDATE_ORDER_STATUS,
    }),
    MerchantStaffMember.ROLE_CASHIER: frozenset({
        VIEW_ORDERS,
        VIEW_PAYMENTS,
    }),
    MerchantStaffMember.ROLE_DISPATCHER: frozenset({
        VIEW_ORDERS,
        UPDATE_ORDER_STATUS,
        MANAGE_RIDERS,
        VIEW_RIDERS,
        VIEW_FULFILLMENT,
        MANAGE_FULFILLMENT,
    }),
    MerchantStaffMember.ROLE_CUSTOMER_SUPPORT: frozenset({
        VIEW_ORDERS,
        VIEW_SUPPORT,
        MANAGE_SUPPORT,
        VIEW_FULFILLMENT,
    }),
    MerchantStaffMember.ROLE_FINANCE_STAFF: frozenset({
        VIEW_PAYMENTS,
        VIEW_PAYOUTS,
        VIEW_LEDGER,
        VIEW_FINANCE,
    }),
    MerchantStaffMember.ROLE_VIEWER: READ_ONLY_PERMISSIONS,
}


@dataclass(frozen=True)
class MerchantActor:
    user: object
    is_owner: bool = False
    is_staff: bool = False
    merchant: object = None
    staff_member: object = None
    role: str = ''
    membership_status: str = ''
    verification_status: str = ''
    is_company_wide: bool = False
    branch_ids: tuple = field(default_factory=tuple)
    permissions: frozenset = field(default_factory=frozenset)

    @property
    def has_merchant_access(self):
        return bool(self.merchant_id and self.permissions)

    @property
    def merchant_id(self):
        return self.merchant.id if self.merchant else None

    def has_permission(self, permission):
        return permission in self.permissions


def _merchant_branch_ids(merchant):
    if not merchant:
        return tuple()
    return tuple(
        Restaurant.objects.filter(owner=merchant.user)
        .order_by('id')
        .values_list('id', flat=True)
    )


def _staff_is_operational(staff_member):
    return (
        staff_member
        and staff_member.user.is_active
        and staff_member.membership_status == MerchantStaffMember.STATUS_ACTIVE
        and staff_member.verification_status == MerchantStaffMember.VERIFICATION_VERIFIED
    )


def _staff_branch_ids(staff_member):
    if not staff_member:
        return tuple()
    if staff_member.is_company_wide:
        return _merchant_branch_ids(staff_member.merchant)
    return tuple(
        staff_member.branch_access.order_by('branch_id')
        .values_list('branch_id', flat=True)
    )


def get_merchant_actor(user, merchant=None):
    if not user or not getattr(user, 'is_authenticated', False) or not user.is_active:
        return MerchantActor(user=user)

    owner_profile = getattr(user, 'merchant_profile', None)
    if owner_profile and (merchant is None or owner_profile.id == merchant.id):
        return MerchantActor(
            user=user,
            is_owner=True,
            merchant=owner_profile,
            role=MerchantStaffMember.ROLE_OWNER,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            is_company_wide=True,
            branch_ids=_merchant_branch_ids(owner_profile),
            permissions=ALL_PERMISSIONS,
        )

    memberships = (
        MerchantStaffMember.objects
        .select_related('merchant', 'merchant__user', 'user')
        .prefetch_related('branch_access')
        .filter(user=user)
        .exclude(membership_status=MerchantStaffMember.STATUS_REMOVED)
        .order_by('id')
    )
    if merchant is not None:
        memberships = memberships.filter(merchant=merchant)
    staff_member = memberships.first()
    if not staff_member:
        return MerchantActor(user=user)

    operational = _staff_is_operational(staff_member)
    return MerchantActor(
        user=user,
        is_staff=True,
        merchant=staff_member.merchant,
        staff_member=staff_member,
        role=staff_member.role,
        membership_status=staff_member.membership_status,
        verification_status=staff_member.verification_status,
        is_company_wide=staff_member.is_company_wide,
        branch_ids=_staff_branch_ids(staff_member) if operational else tuple(),
        permissions=(
            ROLE_PERMISSION_MATRIX.get(staff_member.role, frozenset())
            if operational else frozenset()
        ),
    )


def permitted_branch_ids(actor):
    return tuple(actor.branch_ids) if actor and actor.permissions else tuple()


def can_access_branch(actor, branch):
    if not actor or not branch or not actor.permissions:
        return False
    if actor.is_owner:
        return branch.owner_id == actor.merchant.user_id
    if actor.is_company_wide:
        return branch.owner_id == actor.merchant.user_id
    return branch.id in actor.branch_ids


def filter_queryset_for_actor(queryset, actor, branch_field):
    branch_ids = permitted_branch_ids(actor)
    if not branch_ids:
        return queryset.none()
    if branch_field in ('id', 'pk'):
        return queryset.filter(**{f'{branch_field}__in': branch_ids})
    return queryset.filter(**{f'{branch_field}__id__in': branch_ids})
