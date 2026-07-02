import json
import logging
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings

from fooddelivery.logging import JsonFormatter
from fooddelivery.observability import (
    get_health_snapshot,
    get_metrics_snapshot,
    touch_worker_heartbeat,
)


class HealthEndpointObservabilityTests(TestCase):
    def test_health_endpoint_returns_dependency_checks(self):
        response = Client().get('/api/v1/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ok')
        check_names = {check['name'] for check in response.data['checks']}
        self.assertIn('database', check_names)
        self.assertIn('cache', check_names)
        self.assertIn('media_storage', check_names)

    def test_detailed_health_includes_optional_readiness_without_secrets(self):
        response = Client().get('/api/v1/health/?detail=1')

        self.assertEqual(response.status_code, 200)
        self.assertIn('worker_heartbeats', response.data)
        serialized = json.dumps(response.data)
        self.assertNotIn('DJANGO_SECRET_KEY', serialized)
        self.assertNotIn('RAZORPAY_KEY_SECRET', serialized)
        self.assertNotIn('PRIVATE_MEDIA_ROOT', serialized)

    def test_degraded_dependency_is_reported_safely(self):
        with mock.patch(
            'fooddelivery.observability.check_cache',
            return_value={'name': 'cache', 'ok': False, 'error': 'ConnectionError'},
        ):
            snapshot = get_health_snapshot()

        self.assertEqual(snapshot['status'], 'degraded')
        self.assertEqual(snapshot['checks'][1]['error'], 'ConnectionError')

    def test_metrics_snapshot_is_aggregate_only(self):
        snapshot = get_metrics_snapshot()

        self.assertTrue(snapshot['enabled'])
        self.assertIn('payments', snapshot)
        self.assertIn('notifications', snapshot)
        serialized = json.dumps(snapshot)
        self.assertNotIn('provider_secret', serialized)
        self.assertNotIn('private_media', serialized)

    def test_worker_heartbeat_can_be_recorded(self):
        self.assertTrue(touch_worker_heartbeat('dispatch_worker'))

        response = Client().get('/api/v1/health/?detail=1')

        self.assertIn('dispatch_worker', response.data['worker_heartbeats'])


class StructuredLoggingTests(SimpleTestCase):
    def test_json_formatter_includes_safe_extra_fields(self):
        record = logging.LogRecord(
            name='test.logger',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='Observed request',
            args=(),
            exc_info=None,
        )
        record.operation = 'http_request'
        record.duration_ms = 12.5
        record.request_id = 'request-123'
        record.user_id = 7
        record.password = 'do-not-log'
        record.jwt = 'token'

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload['operation'], 'http_request')
        self.assertEqual(payload['duration_ms'], 12.5)
        self.assertEqual(payload['request_id'], 'request-123')
        self.assertEqual(payload['user_id'], 7)
        self.assertNotIn('password', payload)
        self.assertNotIn('jwt', payload)

    @override_settings(METRICS_ENABLED=False)
    def test_metrics_can_be_disabled(self):
        self.assertEqual(get_metrics_snapshot(), {'enabled': False})
