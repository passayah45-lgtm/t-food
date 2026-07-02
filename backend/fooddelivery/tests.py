from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.db import OperationalError, connection

from channels.routing import ProtocolTypeRouter

from fooddelivery.celery import app
from fooddelivery.asgi import application
from fooddelivery.routing import websocket_urlpatterns
from fooddelivery.tasks import TFoodTask
from fooddelivery.env_validation import validate_startup_environment


class ProductionEnvironmentValidationTests(SimpleTestCase):
    def test_non_production_environment_does_not_require_launch_variables(self):
        errors = validate_startup_environment('development', True, {})
        self.assertEqual(errors, [])

    def test_production_environment_reports_missing_critical_variables(self):
        errors = validate_startup_environment('production', False, {})

        self.assertIn('DJANGO_SECRET_KEY must be set to a production value.', errors)
        self.assertIn(
            'DATABASE_URL or POSTGRES_PASSWORD must be set for production.',
            errors,
        )

    def test_production_environment_accepts_complete_configuration(self):
        env = {
            'DJANGO_SECRET_KEY': 'a-realistic-production-secret-value-that-is-long',
            'ALLOWED_HOSTS': 't-food.com,www.t-food.com',
            'CSRF_TRUSTED_ORIGINS': 'https://t-food.com,https://www.t-food.com',
            'PUBLIC_APP_URL': 'https://t-food.com',
            'PRIVATE_MEDIA_ROOT': '/app/private_media',
            'DATABASE_URL': 'postgres://tfood:secret@db:5432/tfood',
            'REDIS_URL': 'redis://redis:6379/1',
            'CHANNEL_REDIS_URL': 'redis://redis:6379/4',
            'SECURE_SSL_REDIRECT': 'True',
        }

        errors = validate_startup_environment('production', False, env)
        self.assertEqual(errors, [])


class CeleryConfigurationTests(SimpleTestCase):
    def test_celery_app_uses_django_settings(self):
        self.assertEqual(app.main, 'fooddelivery')
        self.assertEqual(app.conf.task_default_queue, 'default')
        self.assertEqual(app.conf.timezone, settings.TIME_ZONE)

    def test_required_queues_are_configured(self):
        queue_names = {queue.name for queue in settings.CELERY_TASK_QUEUES}

        self.assertEqual(
            queue_names,
            {'critical', 'dispatch', 'notifications', 'maintenance', 'default'},
        )

    def test_task_routes_send_jobs_to_expected_queues(self):
        routes = settings.CELERY_TASK_ROUTES

        self.assertEqual(
            routes['orders.tasks.expire_unpaid_orders_task']['queue'],
            'maintenance',
        )
        self.assertEqual(
            routes['delivery.tasks.notify_pending_delivery_candidates_task']['queue'],
            'dispatch',
        )
        self.assertEqual(
            routes['notifications.tasks.create_notification_task']['queue'],
            'notifications',
        )
        self.assertEqual(
            routes[
                'fooddelivery.tasks.record_celery_beat_heartbeat_task'
            ]['queue'],
            'maintenance',
        )

    def test_task_base_has_retry_policy(self):
        self.assertTrue(TFoodTask.abstract)
        self.assertIn(OperationalError, TFoodTask.autoretry_for)
        self.assertTrue(TFoodTask.retry_backoff)
        self.assertTrue(TFoodTask.retry_jitter)
        self.assertEqual(TFoodTask.retry_kwargs['max_retries'], 3)

    def test_beat_schedule_contains_safe_maintenance_tasks(self):
        schedule = settings.CELERY_BEAT_SCHEDULE

        self.assertEqual(
            schedule['expire-unpaid-orders-every-minute']['task'],
            'orders.tasks.expire_unpaid_orders_task',
        )
        self.assertEqual(
            schedule[
                'notify-pending-delivery-candidates-every-15-seconds'
            ]['task'],
            'delivery.tasks.notify_pending_delivery_candidates_task',
        )
        self.assertEqual(
            schedule['record-celery-beat-heartbeat-every-minute']['task'],
            'fooddelivery.tasks.record_celery_beat_heartbeat_task',
        )


class ChannelsFoundationTests(SimpleTestCase):
    def test_channels_settings_are_configured(self):
        self.assertIn('channels', settings.INSTALLED_APPS)
        self.assertEqual(
            settings.ASGI_APPLICATION,
            'fooddelivery.asgi.application',
        )
        self.assertEqual(
            settings.CHANNEL_LAYERS['default']['BACKEND'],
            'realtime.channel_layers.TFoodRedisChannelLayer',
        )
        self.assertTrue(
            settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0].endswith('/4')
        )

    def test_asgi_application_and_empty_routing_load(self):
        self.assertIsInstance(application, ProtocolTypeRouter)
        self.assertEqual(len(websocket_urlpatterns), 1)
        self.assertEqual(websocket_urlpatterns[0].pattern._route, 'ws/orders/')


class PostGISRuntimeFoundationTests(TestCase):
    def test_gis_app_is_installed(self):
        if not settings.GEODJANGO_AVAILABLE:
            self.skipTest('GeoDjango native libraries are not available locally.')
        self.assertIn('django.contrib.gis', settings.INSTALLED_APPS)

    def test_postgis_extension_is_available_on_postgresql(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostGIS extension check only applies to PostgreSQL.')

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
            )
            self.assertTrue(cursor.fetchone()[0])
