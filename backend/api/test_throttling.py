from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle


TEST_REST_FRAMEWORK = {
    **settings.REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        **settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],
        'anon': '2/day',
        'user': '2/day',
        'auth_login': '2/minute',
        'password_reset': '2/hour',
    },
}


@override_settings(REST_FRAMEWORK=TEST_REST_FRAMEWORK)
class ApiThrottleTests(APITestCase):
    def setUp(self):
        self.original_rates = SimpleRateThrottle.THROTTLE_RATES
        SimpleRateThrottle.THROTTLE_RATES = (
            TEST_REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        )
        cache.clear()

    def tearDown(self):
        cache.clear()
        SimpleRateThrottle.THROTTLE_RATES = self.original_rates

    def test_login_is_throttled_after_repeated_attempts(self):
        responses = [
            self.client.post(
                '/api/v1/auth/login/',
                {'username': 'missing-user', 'password': 'wrong-password'},
                format='json',
            )
            for _ in range(3)
        ]

        self.assertEqual(responses[0].status_code, 401)
        self.assertEqual(responses[1].status_code, 401)
        self.assertEqual(responses[2].status_code, 429)

    def test_password_reset_is_throttled(self):
        responses = [
            self.client.post(
                '/api/v1/auth/password-reset/',
                {'email': f'unknown{index}@example.com'},
                format='json',
            )
            for index in range(3)
        ]

        self.assertEqual(responses[0].status_code, 200)
        self.assertEqual(responses[1].status_code, 200)
        self.assertEqual(responses[2].status_code, 429)

    def test_authenticated_api_uses_per_user_limit(self):
        user = User.objects.create_user(username='throttled-customer')
        self.client.force_authenticate(user)

        responses = [self.client.get('/api/v1/users/profile/') for _ in range(3)]

        self.assertEqual(responses[0].status_code, 200)
        self.assertEqual(responses[1].status_code, 200)
        self.assertEqual(responses[2].status_code, 429)

    def test_health_check_is_never_throttled(self):
        responses = [self.client.get('/api/v1/health/') for _ in range(4)]

        self.assertTrue(all(response.status_code == 200 for response in responses))
