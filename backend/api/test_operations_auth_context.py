from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from markets.models import CommerceArea, CommerceCity, Currency, Market
from operations_access.models import (
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)
from operations_access.permissions import (
    ALL_OPERATIONS_PERMISSIONS,
    MANAGE_MARKETS,
    VIEW_BRANCHES,
    VIEW_DISPATCH,
    VIEW_MERCHANTS,
)


TEST_REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {},
}


@override_settings(REST_FRAMEWORK=TEST_REST_FRAMEWORK)
class OperationsAuthContextTests(APITestCase):
    def setUp(self):
        cache.clear()
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
            slug='guinea-auth',
            name='Guinea Auth',
            country_code='GN',
            default_currency=gnf,
            timezone='Africa/Conakry',
        )
        self.city = CommerceCity.objects.create(
            market=self.guinea,
            name='Conakry',
        )
        self.area = CommerceArea.objects.create(
            city=self.city,
            name='Kaloum',
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def login(self, username, password='test-password'):
        return self.client.post(
            '/api/v1/auth/login/',
            {'username': username, 'password': password},
            format='json',
        )

    def create_profile(self, role, username, status=OperationsStaffProfile.STATUS_ACTIVE):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='test-password',
            is_staff=True,
        )
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=role,
            status=status,
        )
        return user, profile

    def assert_no_active_operations_permissions(self, data):
        self.assertFalse(data['is_operations_user'])
        self.assertEqual(data['operations_permissions'], [])
        self.assertFalse(data['operations_is_global_scope'])
        self.assertEqual(data['operations_market_ids'], [])
        self.assertEqual(data['operations_country_codes'], [])
        self.assertEqual(data['operations_city_ids'], [])
        self.assertEqual(data['operations_area_ids'], [])

    def test_superuser_login_includes_global_operations_context(self):
        user = User.objects.create_superuser(
            username='ops-superuser',
            email='super@example.com',
            password='test-password',
        )

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_operations_user'])
        self.assertEqual(response.data['operations_role'], OperationsStaffProfile.ROLE_GLOBAL_ADMIN)
        self.assertEqual(response.data['operations_status'], OperationsStaffProfile.STATUS_ACTIVE)
        self.assertTrue(response.data['operations_is_global_scope'])
        self.assertFalse(response.data['operations_is_legacy_staff'])
        self.assertEqual(
            set(response.data['operations_permissions']),
            set(ALL_OPERATIONS_PERMISSIONS),
        )

    def test_legacy_staff_login_includes_legacy_operations_context(self):
        user = User.objects.create_user(
            username='legacy-staff',
            password='test-password',
            is_staff=True,
        )

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_operations_user'])
        self.assertEqual(response.data['operations_role'], 'LEGACY_STAFF')
        self.assertTrue(response.data['operations_is_global_scope'])
        self.assertTrue(response.data['operations_is_legacy_staff'])
        self.assertIn(MANAGE_MARKETS, response.data['operations_permissions'])

    def test_global_admin_profile_login_includes_global_context(self):
        user, _profile = self.create_profile(
            OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            'profile-global-admin',
        )

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_operations_user'])
        self.assertEqual(response.data['operations_role'], OperationsStaffProfile.ROLE_GLOBAL_ADMIN)
        self.assertTrue(response.data['operations_is_global_scope'])
        self.assertFalse(response.data['operations_is_legacy_staff'])
        self.assertIn(MANAGE_MARKETS, response.data['operations_permissions'])

    def test_country_admin_login_includes_assigned_market_and_country_scope(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'profile-country-admin',
        )
        OperationsStaffMarketAccess.objects.create(profile=profile, market=self.guinea)

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_operations_user'])
        self.assertEqual(response.data['operations_role'], OperationsStaffProfile.ROLE_COUNTRY_ADMIN)
        self.assertFalse(response.data['operations_is_global_scope'])
        self.assertEqual(response.data['operations_market_ids'], [self.guinea.id])
        self.assertEqual(response.data['operations_country_codes'], ['GN'])
        self.assertIn(VIEW_MERCHANTS, response.data['operations_permissions'])

    def test_city_admin_login_includes_city_scope(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'profile-city-admin',
        )
        OperationsStaffCityAccess.objects.create(profile=profile, city=self.city)

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['operations_city_ids'], [self.city.id])
        self.assertEqual(response.data['operations_market_ids'], [self.guinea.id])
        self.assertEqual(response.data['operations_country_codes'], ['GN'])
        self.assertIn(VIEW_DISPATCH, response.data['operations_permissions'])

    def test_area_admin_login_includes_area_scope(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            'profile-area-admin',
        )
        OperationsStaffAreaAccess.objects.create(profile=profile, area=self.area)

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['operations_area_ids'], [self.area.id])
        self.assertEqual(response.data['operations_city_ids'], [self.city.id])
        self.assertEqual(response.data['operations_market_ids'], [self.guinea.id])
        self.assertIn(VIEW_BRANCHES, response.data['operations_permissions'])

    def test_inactive_and_suspended_profiles_return_no_active_permissions(self):
        cases = [
            OperationsStaffProfile.STATUS_INACTIVE,
            OperationsStaffProfile.STATUS_SUSPENDED,
        ]
        for profile_status in cases:
            with self.subTest(profile_status=profile_status):
                user, _profile = self.create_profile(
                    OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
                    f'profile-{profile_status.lower()}',
                    status=profile_status,
                )

                response = self.login(user.username)

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                self.assertEqual(response.data['operations_status'], profile_status)
                self.assertEqual(response.data['operations_role'], OperationsStaffProfile.ROLE_GLOBAL_ADMIN)
                self.assert_no_active_operations_permissions(response.data)

    def test_non_operations_user_has_operations_false(self):
        user = User.objects.create_user(
            username='plain-customer',
            password='test-password',
        )

        response = self.login(user.username)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['role'], 'customer')
        self.assertFalse(response.data['is_operations_user'])
        self.assertEqual(response.data['operations_permissions'], [])
        self.assertEqual(response.data['operations_role'], '')

    def test_me_endpoint_includes_operations_context(self):
        user, profile = self.create_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'profile-country-me',
        )
        OperationsStaffMarketAccess.objects.create(profile=profile, market=self.guinea)
        login = self.login(user.username)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )

        response = self.client.get('/api/v1/auth/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['is_operations_user'])
        self.assertEqual(response.data['operations_country_codes'], ['GN'])
