import time
from pathlib import Path

from asgiref.sync import async_to_sync
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone


HEARTBEAT_TTL_SECONDS = 180


def monitoring_enabled():
    return getattr(settings, 'MONITORING_ENABLED', True)


def metrics_enabled():
    return getattr(settings, 'METRICS_ENABLED', True)


def _check_result(name, ok, **details):
    payload = {
        'name': name,
        'ok': bool(ok),
    }
    payload.update(details)
    return payload


def check_database():
    started = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return _check_result(
            'database',
            True,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            vendor=connection.vendor,
        )
    except Exception as exc:
        return _check_result(
            'database',
            False,
            error=exc.__class__.__name__,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )


def check_cache():
    started = time.perf_counter()
    key = 'tfood:health:cache'
    try:
        cache.set(key, 'ok', timeout=30)
        ok = cache.get(key) == 'ok'
        return _check_result(
            'cache',
            ok,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception as exc:
        return _check_result(
            'cache',
            False,
            error=exc.__class__.__name__,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )


def check_channel_layer():
    started = time.perf_counter()
    try:
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return _check_result('channel_layer', False, error='not_configured')
        async_to_sync(channel_layer.group_send)(
            'health_check_internal',
            {'type': 'health.noop'},
        )
        return _check_result(
            'channel_layer',
            True,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception as exc:
        return _check_result(
            'channel_layer',
            False,
            error=exc.__class__.__name__,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )


def _path_is_available(path):
    path = Path(path)
    try:
        return path.exists() and path.is_dir()
    except Exception:
        return False


def check_media_storage():
    public_ok = _path_is_available(settings.MEDIA_ROOT)
    private_ok = _path_is_available(settings.PRIVATE_MEDIA_ROOT)
    strict_media = (
        getattr(settings, 'APP_ENV', '').lower() in {'production', 'prod'}
        and not settings.DEBUG
    )
    return _check_result(
        'media_storage',
        (public_ok and private_ok) if strict_media else True,
        public_media_available=public_ok,
        private_media_available=private_ok,
        strict=strict_media,
    )


def heartbeat_key(service_name):
    return f'tfood:heartbeat:{service_name}'


def touch_worker_heartbeat(service_name):
    timestamp = timezone.now().isoformat()
    try:
        cache.set(heartbeat_key(service_name), timestamp, HEARTBEAT_TTL_SECONDS)
    except Exception:
        return False
    return True


def get_worker_heartbeats():
    services = ('dispatch_worker', 'celery_worker', 'celery_beat')
    heartbeats = {}
    for service_name in services:
        try:
            heartbeats[service_name] = cache.get(heartbeat_key(service_name))
        except Exception:
            heartbeats[service_name] = None
    return heartbeats


def get_health_snapshot(include_optional=False):
    checks = [
        check_database(),
        check_cache(),
        check_media_storage(),
    ]
    if include_optional:
        checks.append(check_channel_layer())

    required_ok = all(check['ok'] for check in checks if check['name'] != 'channel_layer')
    snapshot = {
        'status': 'ok' if required_ok else 'degraded',
        'timestamp': timezone.now().isoformat(),
        'checks': checks,
    }
    if include_optional:
        snapshot['worker_heartbeats'] = get_worker_heartbeats()
    return snapshot


def _model_count(app_label, model_name, filters=None):
    try:
        model = apps.get_model(app_label, model_name)
        queryset = model.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return queryset.count()
    except Exception:
        return None


def get_metrics_snapshot():
    """Return safe, aggregate-only launch metrics for future exporters."""
    if not metrics_enabled():
        return {'enabled': False}

    return {
        'enabled': True,
        'timestamp': timezone.now().isoformat(),
        'api': {
            'request_metrics_source': 'application_logs',
            'slow_query_threshold_ms': settings.SLOW_QUERY_THRESHOLD_MS,
        },
        'payments': {
            'failed_payments': _model_count('payments', 'Payment', {'status': 'FAILED'}),
            'failed_refunds': _model_count('payments', 'RefundAudit', {'status': 'FAILED'}),
        },
        'ledger': {
            'transactions': _model_count('ledger', 'LedgerTransaction'),
        },
        'notifications': {
            'realtime_failed_attempts': _model_count(
                'notifications',
                'NotificationDeliveryAttempt',
                {'channel': 'REALTIME', 'status': 'FAILED'},
            ),
        },
        'visual_search': {
            'searches': _model_count('intelligence', 'VisualSearchEvent'),
            'no_result_searches': _model_count(
                'intelligence',
                'VisualSearchEvent',
                {'result_count': 0},
            ),
        },
        'moderation': {
            'pending_review_photos': _model_count(
                'restaurants',
                'ReviewPhoto',
                {'status': 'PENDING'},
            ),
        },
        'verification': {
            'pending_documents': _model_count(
                'verifications',
                'VerificationDocument',
                {'status': 'PENDING'},
            ),
        },
        'workers': get_worker_heartbeats(),
    }
