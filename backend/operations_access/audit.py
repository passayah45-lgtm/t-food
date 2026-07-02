from django.contrib.auth import get_user_model
from django.db.models import Count

from .config import legacy_global_operations_access_enabled
from .models import (
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)


def _user_summary(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


def audit_operations_profiles():
    User = get_user_model()
    superusers = list(User.objects.filter(is_superuser=True).order_by('username', 'id'))
    profiles = OperationsStaffProfile.objects.select_related('user').prefetch_related(
        'market_access',
        'city_access',
        'area_access',
    ).order_by('user__username', 'id')

    legacy_staff = list(
        User.objects.filter(is_staff=True, is_superuser=False)
        .filter(operations_staff_profile__isnull=True)
        .order_by('username', 'id')
    )
    inactive_profiles = [
        profile for profile in profiles
        if profile.status == OperationsStaffProfile.STATUS_INACTIVE
    ]
    suspended_profiles = [
        profile for profile in profiles
        if profile.status == OperationsStaffProfile.STATUS_SUSPENDED
    ]
    profiles_without_scope = [
        profile for profile in profiles
        if (
            profile.status == OperationsStaffProfile.STATUS_ACTIVE
            and profile.role != OperationsStaffProfile.ROLE_GLOBAL_ADMIN
            and profile.role != OperationsStaffProfile.ROLE_VIEWER
            and not profile.market_access.exists()
            and not profile.city_access.exists()
            and not profile.area_access.exists()
        )
    ]

    duplicate_profile_users = list(
        OperationsStaffProfile.objects.values('user_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    duplicate_market_assignments = list(
        OperationsStaffMarketAccess.objects.values('profile_id', 'market_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    duplicate_city_assignments = list(
        OperationsStaffCityAccess.objects.values('profile_id', 'city_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    duplicate_area_assignments = list(
        OperationsStaffAreaAccess.objects.values('profile_id', 'area_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )

    invalid_city_assignments = [
        access for access in OperationsStaffCityAccess.objects.select_related('city', 'city__market')
        if not access.city_id or not access.city.market_id
    ]
    invalid_area_assignments = [
        access for access in OperationsStaffAreaAccess.objects.select_related('area', 'area__city', 'area__market')
        if (
            not access.area_id
            or not access.area.city_id
            or not access.area.market_id
            or access.area.city.market_id != access.area.market_id
        )
    ]

    warnings = []
    if legacy_staff:
        warnings.append(
            'Legacy Django staff users without OperationsStaffProfile require migration before production.'
        )
    if legacy_global_operations_access_enabled():
        warnings.append(
            'Development compatibility mode is enabled; disable ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS before production.'
        )
    if profiles_without_scope:
        warnings.append(
            'Some non-global operations profiles have no assigned market/city/area scope.'
        )
    if inactive_profiles or suspended_profiles:
        warnings.append(
            'Inactive or suspended operations profiles exist and should be reviewed.'
        )
    if duplicate_profile_users or duplicate_market_assignments or duplicate_city_assignments or duplicate_area_assignments:
        warnings.append('Duplicate operations access records were detected.')
    if invalid_city_assignments or invalid_area_assignments:
        warnings.append('Invalid operations scope assignments were detected.')

    fatal = bool(
        duplicate_profile_users
        or duplicate_market_assignments
        or duplicate_city_assignments
        or duplicate_area_assignments
        or invalid_city_assignments
        or invalid_area_assignments
    )

    return {
        'summary': {
            'superusers': len(superusers),
            'operations_users': profiles.count(),
            'legacy_staff_users': len(legacy_staff),
            'inactive_profiles': len(inactive_profiles),
            'suspended_profiles': len(suspended_profiles),
            'profiles_without_scope': len(profiles_without_scope),
            'legacy_compatibility_enabled': legacy_global_operations_access_enabled(),
            'fatal_inconsistencies': fatal,
        },
        'superusers': [_user_summary(user) for user in superusers],
        'legacy_staff_users': [_user_summary(user) for user in legacy_staff],
        'inactive_profiles': [
            {'id': profile.id, 'user': _user_summary(profile.user), 'role': profile.role}
            for profile in inactive_profiles
        ],
        'suspended_profiles': [
            {'id': profile.id, 'user': _user_summary(profile.user), 'role': profile.role}
            for profile in suspended_profiles
        ],
        'profiles_without_scope': [
            {'id': profile.id, 'user': _user_summary(profile.user), 'role': profile.role}
            for profile in profiles_without_scope
        ],
        'duplicate_profile_users': duplicate_profile_users,
        'duplicate_market_assignments': duplicate_market_assignments,
        'duplicate_city_assignments': duplicate_city_assignments,
        'duplicate_area_assignments': duplicate_area_assignments,
        'invalid_city_assignments': [access.id for access in invalid_city_assignments],
        'invalid_area_assignments': [access.id for access in invalid_area_assignments],
        'warnings': warnings,
        'recommended_fixes': [
            'Create an OperationsStaffProfile for every business operations user.',
            'Assign market, city, or area scope to non-global operations profiles.',
            'Disable ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS before staging or production.',
            'Keep Django superusers for developer/admin access only.',
        ],
    }
