from dataclasses import dataclass, field

from rest_framework.exceptions import PermissionDenied

from .config import legacy_global_operations_access_enabled
from .models import OperationsStaffProfile


VIEW_GLOBAL_DASHBOARD = 'VIEW_GLOBAL_DASHBOARD'
MANAGE_MARKETS = 'MANAGE_MARKETS'
MANAGE_CITIES = 'MANAGE_CITIES'
MANAGE_AREAS = 'MANAGE_AREAS'
VIEW_MERCHANTS = 'VIEW_MERCHANTS'
MANAGE_MERCHANTS = 'MANAGE_MERCHANTS'
VIEW_BRANCHES = 'VIEW_BRANCHES'
MANAGE_BRANCHES = 'MANAGE_BRANCHES'
VIEW_RIDERS = 'VIEW_RIDERS'
MANAGE_RIDERS = 'MANAGE_RIDERS'
VIEW_CUSTOMERS = 'VIEW_CUSTOMERS'
VIEW_ORDERS = 'VIEW_ORDERS'
VIEW_DISPATCH = 'VIEW_DISPATCH'
MANAGE_DISPATCH = 'MANAGE_DISPATCH'
VIEW_SUPPORT = 'VIEW_SUPPORT'
MANAGE_SUPPORT = 'MANAGE_SUPPORT'
VIEW_VERIFICATIONS = 'VIEW_VERIFICATIONS'
MANAGE_VERIFICATIONS = 'MANAGE_VERIFICATIONS'
VIEW_LEDGER = 'VIEW_LEDGER'
VIEW_FINANCE = 'VIEW_FINANCE'
MANAGE_PROVIDER_CONFIG = 'MANAGE_PROVIDER_CONFIG'
VIEW_INTELLIGENCE = 'VIEW_INTELLIGENCE'
MANAGE_OPERATIONS_USERS = 'MANAGE_OPERATIONS_USERS'


ALL_OPERATIONS_PERMISSIONS = frozenset({
    VIEW_GLOBAL_DASHBOARD,
    MANAGE_MARKETS,
    MANAGE_CITIES,
    MANAGE_AREAS,
    VIEW_MERCHANTS,
    MANAGE_MERCHANTS,
    VIEW_BRANCHES,
    MANAGE_BRANCHES,
    VIEW_RIDERS,
    MANAGE_RIDERS,
    VIEW_CUSTOMERS,
    VIEW_ORDERS,
    VIEW_DISPATCH,
    MANAGE_DISPATCH,
    VIEW_SUPPORT,
    MANAGE_SUPPORT,
    VIEW_VERIFICATIONS,
    MANAGE_VERIFICATIONS,
    VIEW_LEDGER,
    VIEW_FINANCE,
    MANAGE_PROVIDER_CONFIG,
    VIEW_INTELLIGENCE,
    MANAGE_OPERATIONS_USERS,
})

READ_ONLY_OPERATIONS_PERMISSIONS = frozenset({
    VIEW_GLOBAL_DASHBOARD,
    VIEW_MERCHANTS,
    VIEW_BRANCHES,
    VIEW_RIDERS,
    VIEW_CUSTOMERS,
    VIEW_ORDERS,
    VIEW_DISPATCH,
    VIEW_SUPPORT,
    VIEW_VERIFICATIONS,
    VIEW_LEDGER,
    VIEW_FINANCE,
    VIEW_INTELLIGENCE,
})

ROLE_PERMISSION_MATRIX = {
    OperationsStaffProfile.ROLE_GLOBAL_ADMIN: ALL_OPERATIONS_PERMISSIONS,
    OperationsStaffProfile.ROLE_COUNTRY_ADMIN: frozenset({
        VIEW_GLOBAL_DASHBOARD,
        MANAGE_CITIES,
        MANAGE_AREAS,
        VIEW_MERCHANTS,
        MANAGE_MERCHANTS,
        VIEW_BRANCHES,
        MANAGE_BRANCHES,
        VIEW_RIDERS,
        MANAGE_RIDERS,
        VIEW_CUSTOMERS,
        VIEW_ORDERS,
        VIEW_DISPATCH,
        MANAGE_DISPATCH,
        VIEW_SUPPORT,
        MANAGE_SUPPORT,
        VIEW_VERIFICATIONS,
        MANAGE_VERIFICATIONS,
        VIEW_LEDGER,
        VIEW_FINANCE,
        MANAGE_PROVIDER_CONFIG,
        VIEW_INTELLIGENCE,
    }),
    OperationsStaffProfile.ROLE_CITY_ADMIN: frozenset({
        VIEW_MERCHANTS,
        VIEW_BRANCHES,
        MANAGE_BRANCHES,
        VIEW_RIDERS,
        MANAGE_RIDERS,
        VIEW_CUSTOMERS,
        VIEW_ORDERS,
        VIEW_DISPATCH,
        MANAGE_DISPATCH,
        VIEW_SUPPORT,
        MANAGE_SUPPORT,
        VIEW_VERIFICATIONS,
        MANAGE_VERIFICATIONS,
        VIEW_INTELLIGENCE,
    }),
    OperationsStaffProfile.ROLE_AREA_ADMIN: frozenset({
        VIEW_MERCHANTS,
        VIEW_BRANCHES,
        VIEW_RIDERS,
        MANAGE_RIDERS,
        VIEW_ORDERS,
        VIEW_DISPATCH,
        MANAGE_DISPATCH,
        VIEW_SUPPORT,
        MANAGE_SUPPORT,
        VIEW_VERIFICATIONS,
        VIEW_INTELLIGENCE,
    }),
    OperationsStaffProfile.ROLE_OPERATIONS_STAFF: frozenset({
        VIEW_MERCHANTS,
        VIEW_BRANCHES,
        VIEW_RIDERS,
        VIEW_CUSTOMERS,
        VIEW_ORDERS,
        VIEW_DISPATCH,
        MANAGE_DISPATCH,
        VIEW_SUPPORT,
        MANAGE_SUPPORT,
        VIEW_VERIFICATIONS,
        MANAGE_VERIFICATIONS,
        VIEW_INTELLIGENCE,
    }),
    OperationsStaffProfile.ROLE_SUPPORT_STAFF: frozenset({
        VIEW_CUSTOMERS,
        VIEW_ORDERS,
        VIEW_SUPPORT,
        MANAGE_SUPPORT,
    }),
    OperationsStaffProfile.ROLE_FINANCE_STAFF: frozenset({
        VIEW_MERCHANTS,
        VIEW_RIDERS,
        VIEW_ORDERS,
        VIEW_LEDGER,
        VIEW_FINANCE,
    }),
    OperationsStaffProfile.ROLE_VERIFICATION_REVIEWER: frozenset({
        VIEW_MERCHANTS,
        VIEW_RIDERS,
        VIEW_VERIFICATIONS,
        MANAGE_VERIFICATIONS,
    }),
    OperationsStaffProfile.ROLE_DISPATCH_OPERATOR: frozenset({
        VIEW_BRANCHES,
        VIEW_RIDERS,
        VIEW_ORDERS,
        VIEW_DISPATCH,
        MANAGE_DISPATCH,
    }),
    OperationsStaffProfile.ROLE_VIEWER: READ_ONLY_OPERATIONS_PERMISSIONS,
}


@dataclass(frozen=True)
class OperationsActor:
    user: object
    is_authenticated: bool = False
    is_superuser: bool = False
    is_legacy_staff: bool = False
    has_profile: bool = False
    role: str = ''
    status: str = ''
    permissions: frozenset = field(default_factory=frozenset)
    assigned_market_ids: tuple = field(default_factory=tuple)
    assigned_country_codes: tuple = field(default_factory=tuple)
    assigned_city_ids: tuple = field(default_factory=tuple)
    assigned_area_ids: tuple = field(default_factory=tuple)
    is_global_scope: bool = False

    def can(self, permission):
        return permission in self.permissions


def _normalize_country_codes(values):
    return tuple(sorted({str(value).upper() for value in values if value}))


def _profile_is_active(profile):
    return profile and profile.status == OperationsStaffProfile.STATUS_ACTIVE


def _profile_permissions(profile):
    role_permissions = ROLE_PERMISSION_MATRIX.get(profile.role, frozenset())
    explicit_permissions = set(profile.permissions or [])
    if not explicit_permissions:
        return role_permissions
    return frozenset(role_permissions | explicit_permissions)


def _profile_scope(profile):
    market_access = profile.market_access.select_related('market').all()
    city_access = profile.city_access.select_related('city', 'city__market').all()
    area_access = profile.area_access.select_related('area', 'area__market', 'area__city').all()

    market_ids = {access.market_id for access in market_access}
    market_ids.update(access.city.market_id for access in city_access)
    market_ids.update(access.area.market_id for access in area_access)

    country_codes = {access.market.country_code for access in market_access}
    country_codes.update(access.city.market.country_code for access in city_access)
    country_codes.update(access.area.market.country_code for access in area_access)

    city_ids = {access.city_id for access in city_access}
    city_ids.update(access.area.city_id for access in area_access)

    area_ids = {access.area_id for access in area_access}

    return {
        'assigned_market_ids': tuple(sorted(market_ids)),
        'assigned_country_codes': _normalize_country_codes(country_codes),
        'assigned_city_ids': tuple(sorted(city_ids)),
        'assigned_area_ids': tuple(sorted(area_ids)),
    }


def _global_actor(user, *, is_superuser=False, is_legacy_staff=False, has_profile=False, role=''):
    return OperationsActor(
        user=user,
        is_authenticated=True,
        is_superuser=is_superuser,
        is_legacy_staff=is_legacy_staff,
        has_profile=has_profile,
        role=role,
        status=OperationsStaffProfile.STATUS_ACTIVE,
        permissions=ALL_OPERATIONS_PERMISSIONS,
        is_global_scope=True,
    )


def get_operations_actor(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return OperationsActor(user=user)

    if user.is_superuser:
        return _global_actor(
            user,
            is_superuser=True,
            role=OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
        )

    profile = getattr(user, 'operations_staff_profile', None)
    if profile:
        if not _profile_is_active(profile):
            return OperationsActor(
                user=user,
                is_authenticated=True,
                has_profile=True,
                role=profile.role,
                status=profile.status,
            )
        if profile.role == OperationsStaffProfile.ROLE_GLOBAL_ADMIN:
            return _global_actor(
                user,
                has_profile=True,
                role=profile.role,
            )
        return OperationsActor(
            user=user,
            is_authenticated=True,
            has_profile=True,
            role=profile.role,
            status=profile.status,
            permissions=_profile_permissions(profile),
            **_profile_scope(profile),
        )

    if user.is_staff and legacy_global_operations_access_enabled():
        return _global_actor(
            user,
            is_legacy_staff=True,
            role='LEGACY_STAFF',
        )

    return OperationsActor(user=user, is_authenticated=True)


def can_access_market(actor, market):
    if not actor or not market or not actor.permissions:
        return False
    if actor.is_global_scope:
        return True
    return market.id in actor.assigned_market_ids


def can_access_country(actor, country_code):
    if not actor or not country_code or not actor.permissions:
        return False
    if actor.is_global_scope:
        return True
    return str(country_code).upper() in actor.assigned_country_codes


def can_access_city(actor, city):
    if not actor or not city or not actor.permissions:
        return False
    if actor.is_global_scope:
        return True
    return city.id in actor.assigned_city_ids or city.market_id in actor.assigned_market_ids


def can_access_area(actor, area):
    if not actor or not area or not actor.permissions:
        return False
    if actor.is_global_scope:
        return True
    return (
        area.id in actor.assigned_area_ids
        or area.city_id in actor.assigned_city_ids
        or area.market_id in actor.assigned_market_ids
    )


def _scope_filter_kwargs(actor, scope_field_map):
    filters = {}
    market_field = scope_field_map.get('market')
    country_field = scope_field_map.get('country')
    city_field = scope_field_map.get('city')
    area_field = scope_field_map.get('area')

    if actor.assigned_area_ids and area_field:
        filters[f'{area_field}__id__in'] = actor.assigned_area_ids
    elif actor.assigned_city_ids and city_field:
        filters[f'{city_field}__id__in'] = actor.assigned_city_ids
    elif actor.assigned_market_ids and market_field:
        if market_field == 'self':
            filters['id__in'] = actor.assigned_market_ids
        else:
            filters[f'{market_field}__id__in'] = actor.assigned_market_ids
    elif actor.assigned_country_codes and country_field:
        filters[f'{country_field}__in'] = actor.assigned_country_codes
    return filters


def filter_queryset_for_operations_actor(queryset, actor, scope_field_map):
    if not actor or not actor.permissions:
        return queryset.none()
    if actor.is_global_scope:
        return queryset
    filters = _scope_filter_kwargs(actor, scope_field_map)
    if not filters:
        return queryset.none()
    return queryset.filter(**filters).distinct()


def require_operations_permission(actor, permission):
    if actor and actor.can(permission):
        return True
    raise PermissionDenied('You do not have permission for this operations action.')
