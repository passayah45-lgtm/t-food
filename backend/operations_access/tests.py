from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from io import StringIO
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied

from markets.models import CommerceArea, CommerceCity, Currency, Market
from payments.models import PaymentProviderConfig
from restaurants.models import MerchantProfile
from restaurants.models import Restaurant

from .models import (
    OperationsAccessAudit,
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)
from .audit import audit_operations_profiles
from .config import validate_legacy_operations_access
from .permissions import (
    ALL_OPERATIONS_PERMISSIONS,
    MANAGE_MARKETS,
    MANAGE_OPERATIONS_USERS,
    MANAGE_PROVIDER_CONFIG,
    VIEW_BRANCHES,
    VIEW_DISPATCH,
    VIEW_FINANCE,
    VIEW_GLOBAL_DASHBOARD,
    VIEW_MERCHANTS,
    can_access_area,
    can_access_city,
    can_access_country,
    can_access_market,
    filter_queryset_for_operations_actor,
    get_operations_actor,
    require_operations_permission,
)


class OperationsAccessModelTests(TestCase):
    def setUp(self):
        self.market = Market.objects.get(slug='india')
        self.city = CommerceCity.objects.create(
            market=self.market,
            name='Bhubaneswar',
        )
        self.area = CommerceArea.objects.create(
            city=self.city,
            name='KIIT Area',
        )
        self.creator = User.objects.create_user(
            username='global-admin',
            is_staff=True,
        )
        self.operator = User.objects.create_user(
            username='country-operator',
            is_staff=True,
        )
        self.profile = OperationsStaffProfile.objects.create(
            user=self.operator,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
            permissions=['VIEW_MERCHANTS', 'VIEW_BRANCHES'],
            created_by=self.creator,
            updated_by=self.creator,
        )

    def test_create_operations_staff_profile(self):
        self.assertEqual(self.profile.user, self.operator)
        self.assertEqual(self.profile.role, OperationsStaffProfile.ROLE_COUNTRY_ADMIN)
        self.assertEqual(self.profile.status, OperationsStaffProfile.STATUS_ACTIVE)
        self.assertEqual(self.profile.permissions, ['VIEW_MERCHANTS', 'VIEW_BRANCHES'])

    def test_duplicate_profile_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OperationsStaffProfile.objects.create(
                    user=self.operator,
                    role=OperationsStaffProfile.ROLE_VIEWER,
                )

    def test_market_access_assignment_works(self):
        access = OperationsStaffMarketAccess.objects.create(
            profile=self.profile,
            market=self.market,
            created_by=self.creator,
        )

        self.assertEqual(access.profile, self.profile)
        self.assertEqual(access.market, self.market)

    def test_duplicate_market_access_blocked(self):
        OperationsStaffMarketAccess.objects.create(
            profile=self.profile,
            market=self.market,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OperationsStaffMarketAccess.objects.create(
                    profile=self.profile,
                    market=self.market,
                )

    def test_city_access_assignment_works(self):
        access = OperationsStaffCityAccess.objects.create(
            profile=self.profile,
            city=self.city,
            created_by=self.creator,
        )

        self.assertEqual(access.profile, self.profile)
        self.assertEqual(access.city, self.city)

    def test_duplicate_city_access_blocked(self):
        OperationsStaffCityAccess.objects.create(
            profile=self.profile,
            city=self.city,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OperationsStaffCityAccess.objects.create(
                    profile=self.profile,
                    city=self.city,
                )

    def test_area_access_assignment_works(self):
        access = OperationsStaffAreaAccess.objects.create(
            profile=self.profile,
            area=self.area,
            created_by=self.creator,
        )

        self.assertEqual(access.profile, self.profile)
        self.assertEqual(access.area, self.area)

    def test_duplicate_area_access_blocked(self):
        OperationsStaffAreaAccess.objects.create(
            profile=self.profile,
            area=self.area,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OperationsStaffAreaAccess.objects.create(
                    profile=self.profile,
                    area=self.area,
                )

    def test_inactive_and_suspended_status_store_correctly(self):
        inactive_user = User.objects.create_user(username='inactive-ops')
        suspended_user = User.objects.create_user(username='suspended-ops')

        inactive = OperationsStaffProfile.objects.create(
            user=inactive_user,
            status=OperationsStaffProfile.STATUS_INACTIVE,
        )
        suspended = OperationsStaffProfile.objects.create(
            user=suspended_user,
            status=OperationsStaffProfile.STATUS_SUSPENDED,
        )

        self.assertEqual(inactive.status, OperationsStaffProfile.STATUS_INACTIVE)
        self.assertEqual(suspended.status, OperationsStaffProfile.STATUS_SUSPENDED)

    def test_audit_record_can_be_created(self):
        audit = OperationsAccessAudit.objects.create(
            actor=self.creator,
            action='ASSIGN_MARKET_ACCESS',
            target_type='OperationsStaffProfile',
            target_id=str(self.profile.id),
            scope_type='MARKET',
            scope_id=str(self.market.id),
            metadata={'market': self.market.slug},
        )

        self.assertEqual(audit.actor, self.creator)
        self.assertEqual(audit.action, 'ASSIGN_MARKET_ACCESS')
        self.assertEqual(audit.metadata['market'], 'india')


class OperationsActorPermissionTests(TestCase):
    def setUp(self):
        self.india = Market.objects.get(slug='india')
        gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
            },
        )
        self.guinea = Market.objects.create(
            slug='guinea',
            name='Guinea',
            country_code='GN',
            default_currency=gnf,
            timezone='Africa/Conakry',
        )
        self.india_city = CommerceCity.objects.create(
            market=self.india,
            name='Bhubaneswar',
        )
        self.guinea_city = CommerceCity.objects.create(
            market=self.guinea,
            name='Conakry',
        )
        self.india_area = CommerceArea.objects.create(
            city=self.india_city,
            name='KIIT Area',
        )
        self.guinea_area = CommerceArea.objects.create(
            city=self.guinea_city,
            name='Kaloum',
        )
        self.india_owner = User.objects.create_user(
            username='india-merchant',
            email='india@example.com',
        )
        self.guinea_owner = User.objects.create_user(
            username='guinea-merchant',
            email='guinea@example.com',
        )
        self.india_branch = Restaurant.objects.create(
            owner=self.india_owner,
            market=self.india,
            rest_name='India Branch',
            rest_email='india-branch@example.com',
            rest_contact='1111111111',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            country_code='IN',
            city_ref=self.india_city,
            area_ref=self.india_area,
        )
        self.guinea_branch = Restaurant.objects.create(
            owner=self.guinea_owner,
            market=self.guinea,
            rest_name='Guinea Branch',
            rest_email='guinea-branch@example.com',
            rest_contact='2222222222',
            rest_address='Kaloum Road',
            rest_city='Conakry',
            country_code='GN',
            city_ref=self.guinea_city,
            area_ref=self.guinea_area,
        )

    def create_profile(self, role, username='ops-user', status=OperationsStaffProfile.STATUS_ACTIVE):
        user = User.objects.create_user(username=username, is_staff=True)
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=role,
            status=status,
        )
        return user, profile

    def test_superuser_gets_full_global_access(self):
        user = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='password',
        )

        actor = get_operations_actor(user)

        self.assertTrue(actor.is_superuser)
        self.assertTrue(actor.is_global_scope)
        self.assertEqual(actor.permissions, ALL_OPERATIONS_PERMISSIONS)
        self.assertTrue(actor.can(MANAGE_PROVIDER_CONFIG))
        self.assertTrue(can_access_market(actor, self.guinea))

    @override_settings(ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=True)
    def test_legacy_is_staff_gets_global_access_for_compatibility(self):
        user = User.objects.create_user(username='legacy', is_staff=True)

        actor = get_operations_actor(user)

        self.assertTrue(actor.is_legacy_staff)
        self.assertTrue(actor.is_global_scope)
        self.assertTrue(actor.can(VIEW_GLOBAL_DASHBOARD))
        self.assertTrue(can_access_country(actor, 'GN'))

    @override_settings(ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False)
    def test_legacy_is_staff_denied_when_compatibility_disabled(self):
        user = User.objects.create_user(username='legacy-disabled', is_staff=True)

        actor = get_operations_actor(user)

        self.assertFalse(actor.is_legacy_staff)
        self.assertFalse(actor.is_global_scope)
        self.assertFalse(actor.permissions)
        self.assertFalse(can_access_country(actor, 'GN'))

    def test_global_admin_profile_gets_global_access(self):
        user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            username='global-profile',
        )

        actor = get_operations_actor(user)

        self.assertTrue(actor.has_profile)
        self.assertTrue(actor.is_global_scope)
        self.assertTrue(actor.can(MANAGE_MARKETS))
        self.assertTrue(can_access_city(actor, self.guinea_city))

    def test_country_admin_limited_to_assigned_market_and_country(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            username='country-admin',
        )
        OperationsStaffMarketAccess.objects.create(profile=profile, market=self.guinea)

        actor = get_operations_actor(user)

        self.assertFalse(actor.is_global_scope)
        self.assertIn(self.guinea.id, actor.assigned_market_ids)
        self.assertIn('GN', actor.assigned_country_codes)
        self.assertTrue(actor.can(VIEW_FINANCE))
        self.assertTrue(can_access_market(actor, self.guinea))
        self.assertTrue(can_access_country(actor, 'GN'))
        self.assertFalse(can_access_market(actor, self.india))
        self.assertFalse(can_access_country(actor, 'IN'))

    def test_city_admin_limited_to_assigned_city(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            username='city-admin',
        )
        OperationsStaffCityAccess.objects.create(profile=profile, city=self.guinea_city)

        actor = get_operations_actor(user)

        self.assertIn(self.guinea_city.id, actor.assigned_city_ids)
        self.assertIn(self.guinea.id, actor.assigned_market_ids)
        self.assertTrue(actor.can(VIEW_DISPATCH))
        self.assertTrue(can_access_city(actor, self.guinea_city))
        self.assertFalse(can_access_city(actor, self.india_city))

    def test_area_admin_limited_to_assigned_area(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            username='area-admin',
        )
        OperationsStaffAreaAccess.objects.create(profile=profile, area=self.guinea_area)

        actor = get_operations_actor(user)

        self.assertIn(self.guinea_area.id, actor.assigned_area_ids)
        self.assertIn(self.guinea_city.id, actor.assigned_city_ids)
        self.assertTrue(can_access_area(actor, self.guinea_area))
        self.assertFalse(can_access_area(actor, self.india_area))

    def test_inactive_and_suspended_profiles_get_no_business_permissions(self):
        inactive_user, _inactive = self.create_profile(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            username='inactive-profile',
            status=OperationsStaffProfile.STATUS_INACTIVE,
        )
        suspended_user, _suspended = self.create_profile(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            username='suspended-profile',
            status=OperationsStaffProfile.STATUS_SUSPENDED,
        )

        inactive_actor = get_operations_actor(inactive_user)
        suspended_actor = get_operations_actor(suspended_user)

        self.assertFalse(inactive_actor.permissions)
        self.assertFalse(suspended_actor.permissions)
        self.assertFalse(inactive_actor.is_global_scope)
        self.assertFalse(suspended_actor.is_global_scope)

    def test_permission_matrix_and_explicit_permissions_work(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_VIEWER,
            username='viewer-plus',
        )
        profile.permissions = [MANAGE_PROVIDER_CONFIG]
        profile.save(update_fields=['permissions'])

        actor = get_operations_actor(user)

        self.assertTrue(actor.can(VIEW_MERCHANTS))
        self.assertTrue(actor.can(MANAGE_PROVIDER_CONFIG))
        self.assertFalse(actor.can(MANAGE_MARKETS))

    def test_scope_helpers_work_for_assigned_market_city_and_area(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            username='scope-helper',
        )
        OperationsStaffMarketAccess.objects.create(profile=profile, market=self.guinea)
        actor = get_operations_actor(user)

        self.assertTrue(can_access_market(actor, self.guinea))
        self.assertTrue(can_access_country(actor, 'GN'))
        self.assertTrue(can_access_city(actor, self.guinea_city))
        self.assertTrue(can_access_area(actor, self.guinea_area))
        self.assertFalse(can_access_area(actor, self.india_area))

    def test_queryset_filter_scopes_correctly(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            username='query-scope',
        )
        OperationsStaffAreaAccess.objects.create(profile=profile, area=self.guinea_area)
        actor = get_operations_actor(user)

        scoped = filter_queryset_for_operations_actor(
            Restaurant.objects.order_by('id'),
            actor,
            {
                'market': 'market',
                'country': 'country_code',
                'city': 'city_ref',
                'area': 'area_ref',
            },
        )

        self.assertEqual(list(scoped), [self.guinea_branch])

    def test_queryset_filter_returns_none_without_scope(self):
        user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            username='no-scope',
        )
        actor = get_operations_actor(user)

        scoped = filter_queryset_for_operations_actor(
            Restaurant.objects.all(),
            actor,
            {'market': 'market'},
        )

        self.assertFalse(scoped.exists())

    def test_require_operations_permission(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            username='require-permission',
        )
        OperationsStaffCityAccess.objects.create(profile=profile, city=self.guinea_city)
        actor = get_operations_actor(user)

        self.assertTrue(require_operations_permission(actor, VIEW_BRANCHES))
        with self.assertRaises(PermissionDenied):
            require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)


class OperationsScopedApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.india = Market.objects.get(slug='india')
        gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
            },
        )
        self.guinea = Market.objects.create(
            slug='guinea-scoped-api',
            name='Guinea Scoped API',
            country_code='GN',
            default_currency=gnf,
            timezone='Africa/Conakry',
        )
        self.india_city = CommerceCity.objects.create(
            market=self.india,
            name='Scoped Bhubaneswar',
            slug='scoped-bhubaneswar',
        )
        self.guinea_city = CommerceCity.objects.create(
            market=self.guinea,
            name='Scoped Conakry',
            slug='scoped-conakry',
        )
        self.india_area = CommerceArea.objects.create(
            city=self.india_city,
            name='Scoped KIIT',
            slug='scoped-kiit',
        )
        self.guinea_area = CommerceArea.objects.create(
            city=self.guinea_city,
            name='Scoped Kaloum',
            slug='scoped-kaloum',
        )
        self.india_owner = User.objects.create_user(
            username='scoped-india-owner',
            email='scoped-india@example.com',
        )
        self.guinea_owner = User.objects.create_user(
            username='scoped-guinea-owner',
            email='scoped-guinea@example.com',
        )
        self.india_merchant = MerchantProfile.objects.create(
            user=self.india_owner,
            market=self.india,
            business_name='Scoped India Merchant',
        )
        self.guinea_merchant = MerchantProfile.objects.create(
            user=self.guinea_owner,
            market=self.guinea,
            business_name='Scoped Guinea Merchant',
        )
        self.india_branch = Restaurant.objects.create(
            owner=self.india_owner,
            market=self.india,
            rest_name='Scoped India Branch',
            rest_email='india-branch-scoped@example.com',
            rest_contact='1111111111',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            country_code='IN',
            city_ref=self.india_city,
            area_ref=self.india_area,
            is_active=True,
        )
        self.guinea_branch = Restaurant.objects.create(
            owner=self.guinea_owner,
            market=self.guinea,
            rest_name='Scoped Guinea Branch',
            rest_email='guinea-branch-scoped@example.com',
            rest_contact='2222222222',
            rest_address='Kaloum Road',
            rest_city='Conakry',
            country_code='GN',
            city_ref=self.guinea_city,
            area_ref=self.guinea_area,
            is_active=True,
        )
        PaymentProviderConfig.objects.create(
            market=self.india,
            country_code='IN',
            currency='INR',
            provider_code='razorpay',
            payment_method=PaymentProviderConfig.METHOD_UPI,
            is_active=True,
            is_preferred=True,
            priority=1,
        )
        PaymentProviderConfig.objects.create(
            market=self.guinea,
            country_code='GN',
            currency='GNF',
            provider_code='orange_money',
            payment_method=PaymentProviderConfig.METHOD_MOBILE_MONEY,
            is_active=True,
            is_preferred=True,
            priority=1,
        )

    def create_operations_user(self, role, username, *, market=None, city=None, area=None):
        user = User.objects.create_user(username=username, is_staff=True)
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=role,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        if market:
            OperationsStaffMarketAccess.objects.create(profile=profile, market=market)
        if city:
            OperationsStaffCityAccess.objects.create(profile=profile, city=city)
        if area:
            OperationsStaffAreaAccess.objects.create(profile=profile, area=area)
        return user

    def response_names(self, response):
        return {item['name'] for item in response.data}

    def test_global_admin_superuser_and_legacy_staff_see_all_markets(self):
        global_admin = self.create_operations_user(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            'scoped-global-admin',
        )
        superuser = User.objects.create_superuser(
            username='scoped-superuser',
            email='super@example.com',
            password='password',
        )
        legacy_staff = User.objects.create_user(
            username='scoped-legacy-staff',
            is_staff=True,
        )

        for user in (global_admin, superuser, legacy_staff):
            self.client.force_authenticate(user)
            response = self.client.get('/api/v1/markets/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(self.india.name, self.response_names(response))
            self.assertIn(self.guinea.name, self.response_names(response))

    def test_country_admin_sees_only_assigned_market_and_provider_configs(self):
        user = self.create_operations_user(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'scoped-country-admin',
            market=self.guinea,
        )
        self.client.force_authenticate(user)

        markets = self.client.get('/api/v1/markets/')
        providers = self.client.get('/api/v1/operations/payment-providers/')

        self.assertEqual(markets.status_code, 200)
        self.assertEqual(self.response_names(markets), {self.guinea.name})
        self.assertEqual(providers.status_code, 200)
        provider_codes = {item['provider_code'] for item in providers.data['results']}
        self.assertEqual(provider_codes, {'orange_money'})
        market_ids = {item['id'] for item in providers.data['markets']}
        self.assertEqual(market_ids, {self.guinea.id})
        self.assertNotIn('secret', str(providers.data).lower())

    def test_city_admin_sees_assigned_city_and_scoped_branches(self):
        user = self.create_operations_user(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'scoped-city-admin',
            city=self.guinea_city,
        )
        self.client.force_authenticate(user)

        cities = self.client.get('/api/v1/markets/cities/')
        branches = self.client.get('/api/v1/operations/branches/')

        self.assertEqual(cities.status_code, 200)
        self.assertEqual(self.response_names(cities), {self.guinea_city.name})
        self.assertEqual(branches.status_code, 200)
        branch_names = {item['rest_name'] for item in branches.data}
        self.assertEqual(branch_names, {self.guinea_branch.rest_name})

    def test_area_admin_sees_assigned_area_only(self):
        user = self.create_operations_user(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            'scoped-area-admin',
            area=self.guinea_area,
        )
        self.client.force_authenticate(user)

        areas = self.client.get('/api/v1/markets/areas/')
        branches = self.client.get('/api/v1/operations/branches/')

        self.assertEqual(areas.status_code, 200)
        self.assertEqual(self.response_names(areas), {self.guinea_area.name})
        self.assertEqual(branches.status_code, 200)
        branch_names = {item['rest_name'] for item in branches.data}
        self.assertEqual(branch_names, {self.guinea_branch.rest_name})

    def test_merchant_list_is_scoped_to_assigned_market(self):
        user = self.create_operations_user(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'scoped-merchant-country-admin',
            market=self.guinea,
        )
        self.client.force_authenticate(user)

        response = self.client.get('/api/v1/operations/merchants/')

        self.assertEqual(response.status_code, 200)
        business_names = {item['business_name'] for item in response.data}
        self.assertIn(self.guinea_merchant.business_name, business_names)
        self.assertNotIn(self.india_merchant.business_name, business_names)

    def test_branch_status_is_scoped(self):
        user = self.create_operations_user(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'scoped-branch-status-city-admin',
            city=self.guinea_city,
        )
        self.client.force_authenticate(user)

        allowed = self.client.patch(
            f'/api/v1/operations/branches/{self.guinea_branch.id}/status/',
            {'is_open': False},
            format='json',
        )
        denied = self.client.patch(
            f'/api/v1/operations/branches/{self.india_branch.id}/status/',
            {'is_open': False},
            format='json',
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 404)

    def test_global_admin_can_filter_dashboard_by_market_city_and_area(self):
        user = self.create_operations_user(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            'dashboard-scope-global-admin',
        )
        self.client.force_authenticate(user)

        market_summary = self.client.get('/api/v1/operations/summary/', {
            'market': self.guinea.id,
        })
        city_branches = self.client.get('/api/v1/operations/branches/', {
            'city': self.guinea_city.id,
        })
        area_branches = self.client.get('/api/v1/operations/branches/', {
            'area': self.guinea_area.id,
        })

        self.assertEqual(market_summary.status_code, 200)
        self.assertEqual(market_summary.data['active_restaurants'], 1)
        self.assertEqual(city_branches.status_code, 200)
        self.assertEqual({item['rest_name'] for item in city_branches.data}, {self.guinea_branch.rest_name})
        self.assertEqual(area_branches.status_code, 200)
        self.assertEqual({item['rest_name'] for item in area_branches.data}, {self.guinea_branch.rest_name})


class OperationsAccessApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.india = Market.objects.get(slug='india')
        gnf, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
            },
        )
        self.guinea = Market.objects.create(
            slug='guinea-access-api',
            name='Guinea Access API',
            country_code='GN',
            default_currency=gnf,
            timezone='Africa/Conakry',
        )
        self.india_city = CommerceCity.objects.create(
            market=self.india,
            name='Access Bhubaneswar',
            slug='access-bhubaneswar',
        )
        self.guinea_city = CommerceCity.objects.create(
            market=self.guinea,
            name='Access Conakry',
            slug='access-conakry',
        )
        self.india_area = CommerceArea.objects.create(
            city=self.india_city,
            name='Access KIIT',
            slug='access-kiit',
        )
        self.guinea_area = CommerceArea.objects.create(
            city=self.guinea_city,
            name='Access Kaloum',
            slug='access-kaloum',
        )
        self.global_user = User.objects.create_user(
            username='access-global',
            email='global@example.com',
            is_staff=True,
        )
        self.global_profile = OperationsStaffProfile.objects.create(
            user=self.global_user,
            role=OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )

    def create_profile(self, role, username, *, permissions=None, market=None, city=None, area=None, status=None):
        user = User.objects.create_user(username=username, is_staff=True)
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=role,
            status=status or OperationsStaffProfile.STATUS_ACTIVE,
            permissions=permissions or [],
        )
        if market:
            OperationsStaffMarketAccess.objects.create(profile=profile, market=market)
        if city:
            OperationsStaffCityAccess.objects.create(profile=profile, city=city)
        if area:
            OperationsStaffAreaAccess.objects.create(profile=profile, area=area)
        return user, profile

    def test_access_me_returns_operations_context(self):
        self.client.force_authenticate(self.global_user)

        response = self.client.get('/api/v1/operations/access/me/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_operations_user'])
        self.assertTrue(response.data['is_global_scope'])
        self.assertIn(MANAGE_OPERATIONS_USERS, response.data['permissions'])

    def test_global_admin_can_create_operations_profile(self):
        self.client.force_authenticate(self.global_user)

        response = self.client.post(
            '/api/v1/operations/access/staff/',
            {
                'username': 'new-country-admin',
                'email': 'country@example.com',
                'role': OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
                'status': OperationsStaffProfile.STATUS_ACTIVE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], OperationsStaffProfile.ROLE_COUNTRY_ADMIN)
        self.assertNotIn('password', str(response.data).lower())
        user = User.objects.get(username='new-country-admin')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.has_usable_password())

    def test_global_admin_can_assign_and_remove_scopes(self):
        self.client.force_authenticate(self.global_user)
        _user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'assign-scope-user',
        )

        market_response = self.client.post(
            f'/api/v1/operations/access/staff/{profile.id}/markets/',
            {'market_id': self.guinea.id},
            format='json',
        )
        city_response = self.client.post(
            f'/api/v1/operations/access/staff/{profile.id}/cities/',
            {'city_id': self.guinea_city.id},
            format='json',
        )
        area_response = self.client.post(
            f'/api/v1/operations/access/staff/{profile.id}/areas/',
            {'area_id': self.guinea_area.id},
            format='json',
        )
        delete_response = self.client.delete(
            f'/api/v1/operations/access/staff/{profile.id}/areas/{self.guinea_area.id}/',
        )

        self.assertEqual(market_response.status_code, 200)
        self.assertEqual(city_response.status_code, 200)
        self.assertEqual(area_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(OperationsStaffMarketAccess.objects.filter(profile=profile, market=self.guinea).exists())
        self.assertTrue(OperationsStaffCityAccess.objects.filter(profile=profile, city=self.guinea_city).exists())
        self.assertFalse(OperationsStaffAreaAccess.objects.filter(profile=profile, area=self.guinea_area).exists())

    def test_country_admin_cannot_create_global_admin_or_assign_outside_scope(self):
        country_user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'country-access-manager',
            permissions=[MANAGE_OPERATIONS_USERS],
            market=self.guinea,
        )
        _target_user, target_profile = self.create_profile(
            OperationsStaffProfile.ROLE_VIEWER,
            'country-target',
            market=self.guinea,
        )
        self.client.force_authenticate(country_user)

        create_global = self.client.post(
            '/api/v1/operations/access/staff/',
            {
                'username': 'blocked-global-admin',
                'role': OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
                'status': OperationsStaffProfile.STATUS_ACTIVE,
            },
            format='json',
        )
        assign_outside = self.client.post(
            f'/api/v1/operations/access/staff/{target_profile.id}/markets/',
            {'market_id': self.india.id},
            format='json',
        )

        self.assertEqual(create_global.status_code, 403)
        self.assertEqual(assign_outside.status_code, 403)

    def test_city_admin_cannot_assign_outside_city(self):
        city_user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'city-access-manager',
            permissions=[MANAGE_OPERATIONS_USERS],
            city=self.guinea_city,
        )
        _target_user, target_profile = self.create_profile(
            OperationsStaffProfile.ROLE_VIEWER,
            'city-target',
            city=self.guinea_city,
        )
        self.client.force_authenticate(city_user)

        allowed = self.client.post(
            f'/api/v1/operations/access/staff/{target_profile.id}/cities/',
            {'city_id': self.guinea_city.id},
            format='json',
        )
        denied = self.client.post(
            f'/api/v1/operations/access/staff/{target_profile.id}/cities/',
            {'city_id': self.india_city.id},
            format='json',
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 403)

    def test_area_admin_cannot_assign_outside_area(self):
        area_user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            'area-access-manager',
            permissions=[MANAGE_OPERATIONS_USERS],
            area=self.guinea_area,
        )
        _target_user, target_profile = self.create_profile(
            OperationsStaffProfile.ROLE_VIEWER,
            'area-target',
            area=self.guinea_area,
        )
        self.client.force_authenticate(area_user)

        allowed = self.client.post(
            f'/api/v1/operations/access/staff/{target_profile.id}/areas/',
            {'area_id': self.guinea_area.id},
            format='json',
        )
        denied = self.client.post(
            f'/api/v1/operations/access/staff/{target_profile.id}/areas/',
            {'area_id': self.india_area.id},
            format='json',
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 403)

    def test_suspended_operations_user_denied(self):
        suspended_user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            'suspended-access-manager',
            status=OperationsStaffProfile.STATUS_SUSPENDED,
        )
        self.client.force_authenticate(suspended_user)

        response = self.client.get('/api/v1/operations/access/staff/')

        self.assertEqual(response.status_code, 403)

    @override_settings(ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=True)
    def test_legacy_staff_compatibility_remains(self):
        legacy = User.objects.create_user(username='legacy-access-manager', is_staff=True)
        self.client.force_authenticate(legacy)

        response = self.client.get('/api/v1/operations/access/staff/')

        self.assertEqual(response.status_code, 200)
        usernames = {item['user']['username'] for item in response.data}
        self.assertIn(self.global_user.username, usernames)

    @override_settings(ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False)
    def test_legacy_staff_denied_when_compatibility_disabled(self):
        legacy = User.objects.create_user(username='legacy-access-denied', is_staff=True)
        self.client.force_authenticate(legacy)

        response = self.client.get('/api/v1/operations/access/staff/')

        self.assertEqual(response.status_code, 403)

    def test_minimum_configuration_mode_allows_unscoped_profile(self):
        self.client.force_authenticate(self.global_user)

        create_response = self.client.post(
            '/api/v1/operations/access/staff/',
            {
                'username': 'minimum-config-ops',
                'role': OperationsStaffProfile.ROLE_VIEWER,
                'status': OperationsStaffProfile.STATUS_ACTIVE,
            },
            format='json',
        )
        list_response = self.client.get('/api/v1/operations/access/staff/')

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data['assigned_markets'], [])
        self.assertEqual(create_response.data['assigned_cities'], [])
        self.assertEqual(create_response.data['assigned_areas'], [])
        self.assertEqual(list_response.status_code, 200)


class OperationsAccessAuditTests(TestCase):
    def test_audit_reports_legacy_staff_and_ignores_superuser(self):
        User.objects.create_superuser(
            username='audit-superuser',
            email='audit-super@example.com',
            password='password',
        )
        legacy = User.objects.create_user(
            username='audit-legacy-staff',
            email='legacy@example.com',
            is_staff=True,
        )

        report = audit_operations_profiles()

        usernames = {user['username'] for user in report['legacy_staff_users']}
        superusernames = {user['username'] for user in report['superusers']}
        self.assertIn(legacy.username, usernames)
        self.assertNotIn('audit-superuser', usernames)
        self.assertIn('audit-superuser', superusernames)
        self.assertEqual(report['summary']['legacy_staff_users'], 1)

    def test_audit_reports_inactive_suspended_and_unscoped_profiles(self):
        inactive_user = User.objects.create_user(username='audit-inactive', is_staff=True)
        suspended_user = User.objects.create_user(username='audit-suspended', is_staff=True)
        unscoped_user = User.objects.create_user(username='audit-unscoped', is_staff=True)
        OperationsStaffProfile.objects.create(
            user=inactive_user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_INACTIVE,
        )
        OperationsStaffProfile.objects.create(
            user=suspended_user,
            role=OperationsStaffProfile.ROLE_CITY_ADMIN,
            status=OperationsStaffProfile.STATUS_SUSPENDED,
        )
        OperationsStaffProfile.objects.create(
            user=unscoped_user,
            role=OperationsStaffProfile.ROLE_AREA_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )

        report = audit_operations_profiles()

        self.assertEqual(report['summary']['inactive_profiles'], 1)
        self.assertEqual(report['summary']['suspended_profiles'], 1)
        self.assertEqual(report['summary']['profiles_without_scope'], 1)
        self.assertFalse(report['summary']['fatal_inconsistencies'])

    def test_audit_management_command_outputs_summary(self):
        User.objects.create_user(username='audit-command-legacy', is_staff=True)
        output = StringIO()

        call_command('audit_operations_access', stdout=output)

        value = output.getvalue()
        self.assertIn('Operations Access Audit', value)
        self.assertIn('Legacy staff users without profile: 1', value)
        self.assertIn('Operations access audit completed.', value)

    def test_production_mode_rejects_enabled_legacy_compatibility(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_legacy_operations_access('production', True)

    def test_staging_mode_allows_disabled_legacy_compatibility(self):
        validate_legacy_operations_access('staging', False)


class LegacyOperationsUserMigrationCommandTests(TestCase):
    def test_dry_run_changes_nothing(self):
        legacy = User.objects.create_user(username='dry-run-legacy', is_staff=True)
        output = StringIO()

        call_command('migrate_legacy_operations_users', '--dry-run', stdout=output)

        self.assertFalse(
            OperationsStaffProfile.objects.filter(user=legacy).exists()
        )
        value = output.getvalue()
        self.assertIn('Dry run: True', value)
        self.assertIn('would create profile for dry-run-legacy', value)
        self.assertIn('No changes were made', value)

    def test_viewer_profiles_created_for_legacy_staff(self):
        legacy = User.objects.create_user(username='viewer-legacy', is_staff=True)
        output = StringIO()

        call_command('migrate_legacy_operations_users', stdout=output)

        profile = OperationsStaffProfile.objects.get(user=legacy)
        self.assertEqual(profile.role, OperationsStaffProfile.ROLE_VIEWER)
        self.assertEqual(profile.status, OperationsStaffProfile.STATUS_ACTIVE)
        self.assertIn('Created 1 OperationsStaffProfile', output.getvalue())

    def test_superusers_are_ignored(self):
        superuser = User.objects.create_superuser(
            username='migration-superuser',
            email='migration-super@example.com',
            password='password',
        )
        output = StringIO()

        call_command('migrate_legacy_operations_users', stdout=output)

        self.assertFalse(
            OperationsStaffProfile.objects.filter(user=superuser).exists()
        )
        self.assertIn('No legacy operations users require migration', output.getvalue())

    def test_inactive_users_get_inactive_profile(self):
        legacy = User.objects.create_user(
            username='inactive-legacy',
            is_staff=True,
            is_active=False,
        )

        call_command('migrate_legacy_operations_users', stdout=StringIO())

        profile = OperationsStaffProfile.objects.get(user=legacy)
        self.assertEqual(profile.status, OperationsStaffProfile.STATUS_INACTIVE)

    def test_global_admin_is_not_a_valid_migration_role(self):
        User.objects.create_user(username='no-global-auto', is_staff=True)
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                'migrate_legacy_operations_users',
                '--role',
                OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
                stdout=output,
            )

        self.assertFalse(OperationsStaffProfile.objects.exists())

    def test_command_can_target_one_user_and_assign_market_scope(self):
        target = User.objects.create_user(username='target-legacy', is_staff=True)
        other = User.objects.create_user(username='other-legacy', is_staff=True)
        market = Market.objects.get(slug='india')

        call_command(
            'migrate_legacy_operations_users',
            '--user-id',
            str(target.id),
            '--role',
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            '--market-id',
            str(market.id),
            stdout=StringIO(),
        )

        profile = OperationsStaffProfile.objects.get(user=target)
        self.assertEqual(profile.role, OperationsStaffProfile.ROLE_COUNTRY_ADMIN)
        self.assertTrue(
            OperationsStaffMarketAccess.objects.filter(
                profile=profile,
                market=market,
            ).exists()
        )
        self.assertFalse(
            OperationsStaffProfile.objects.filter(user=other).exists()
        )

    @override_settings(ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS=False)
    def test_profiled_user_works_when_legacy_compatibility_disabled(self):
        legacy = User.objects.create_user(username='locked-down-legacy', is_staff=True)

        call_command('migrate_legacy_operations_users', stdout=StringIO())

        actor = get_operations_actor(legacy)
        self.assertTrue(actor.has_profile)
        self.assertFalse(actor.is_legacy_staff)
        self.assertTrue(actor.can(VIEW_GLOBAL_DASHBOARD))

    def test_audit_has_no_legacy_staff_after_migration(self):
        User.objects.create_user(username='audit-cleanup-legacy', is_staff=True)

        call_command('migrate_legacy_operations_users', stdout=StringIO())
        report = audit_operations_profiles()

        self.assertEqual(report['summary']['legacy_staff_users'], 0)
        self.assertEqual(report['summary']['profiles_without_scope'], 0)
        self.assertNotIn(
            'Legacy Django staff users without OperationsStaffProfile require migration before production.',
            report['warnings'],
        )
