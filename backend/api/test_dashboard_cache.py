from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from fooddelivery.dashboard_cache import (
    cache_key_for_scope,
    get_cached_response_data,
    set_cached_response_data,
)
from markets.models import CommerceCity, Currency, Market
from operations_access.models import (
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)


@override_settings(DASHBOARD_CACHE_ENABLED=True)
class SafeDashboardCacheTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.currency, _ = Currency.objects.get_or_create(
            code='GNF',
            defaults={
                'name': 'Guinean franc',
                'numeric_code': '324',
                'minor_unit': 0,
            },
        )

    def tearDown(self):
        cache.clear()

    def make_market(self, slug, name, country_code):
        return Market.objects.create(
            slug=slug,
            name=name,
            country_code=country_code,
            default_currency=self.currency,
            timezone='UTC',
            is_active=True,
        )

    def test_market_list_uses_short_lived_cache(self):
        first_market = self.make_market('guinea-cache', 'Guinea Cache', 'GN')

        first_response = self.client.get('/api/v1/markets/')
        self.assertEqual(first_response.status_code, 200)
        first_ids = {row['id'] for row in first_response.data}
        self.assertIn(first_market.id, first_ids)

        second_market = self.make_market('cache-later', 'Cache Later', 'CL')
        second_response = self.client.get('/api/v1/markets/')
        second_ids = {row['id'] for row in second_response.data}

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_ids, first_ids)
        self.assertNotIn(second_market.id, second_ids)

    def test_scoped_operations_market_cache_does_not_leak(self):
        guinea = self.make_market('guinea-scoped-cache', 'Guinea Scoped Cache', 'GN')
        india = Market.objects.get(slug='india')
        guinea_user = User.objects.create_user(username='ops-guinea-cache')
        india_user = User.objects.create_user(username='ops-india-cache')
        guinea_profile = OperationsStaffProfile.objects.create(
            user=guinea_user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        india_profile = OperationsStaffProfile.objects.create(
            user=india_user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        OperationsStaffMarketAccess.objects.create(profile=guinea_profile, market=guinea)
        OperationsStaffMarketAccess.objects.create(profile=india_profile, market=india)

        self.client.force_authenticate(guinea_user)
        guinea_response = self.client.get('/api/v1/markets/')
        self.client.force_authenticate(india_user)
        india_response = self.client.get('/api/v1/markets/')

        self.assertEqual(guinea_response.status_code, 200)
        self.assertEqual(india_response.status_code, 200)
        self.assertEqual([row['id'] for row in guinea_response.data], [guinea.id])
        self.assertEqual([row['id'] for row in india_response.data], [india.id])

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'dashboard-cache-test',
        }
    })
    def test_cache_helper_works_with_local_memory_fallback(self):
        key = cache_key_for_scope('test:fallback', None, {'market': 'gn'})
        self.assertTrue(key.startswith('tf:v1:dashboard:test:fallback:'))

        set_cached_response_data(
            'test:fallback',
            {'ok': True},
            timeout=5,
            params={'market': 'gn'},
        )

        self.assertEqual(
            get_cached_response_data('test:fallback', params={'market': 'gn'}),
            {'ok': True},
        )

    def test_city_list_cache_handles_minimum_configuration_mode(self):
        response = self.client.get('/api/v1/markets/cities/?country_code=ZZ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        CommerceCity.objects.create(
            market=self.make_market('zz-cache', 'ZZ Cache', 'ZZ'),
            name='Later City',
        )
        cached_response = self.client.get('/api/v1/markets/cities/?country_code=ZZ')
        self.assertEqual(cached_response.status_code, 200)
        self.assertEqual(cached_response.data, [])

    def test_mutable_order_create_path_does_not_use_dashboard_cache(self):
        with patch('fooddelivery.dashboard_cache.set_cached_response_data') as cache_set:
            response = self.client.post('/api/v1/orders/', {}, format='json')

        self.assertIn(response.status_code, (400, 401, 403))
        cache_set.assert_not_called()
